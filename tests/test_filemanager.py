"""Bezpieczeństwo menedżera plików: ścieżki, weryfikacja kopii, usuwanie."""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class FMTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        os.environ["PLEXDL_CONFIG"] = os.path.join(cls.tmp, "config.json")
        os.environ["PLEXDL_FORCE_COPY"] = "1"
        cls.a = os.path.join(cls.tmp, "a", "Plex", "Movies")
        cls.b = os.path.join(cls.tmp, "b", "Plex", "Movies")
        cls.ta = os.path.join(cls.tmp, "a", "Plex", "TV Shows")
        cls.tb = os.path.join(cls.tmp, "b", "Plex", "TV Shows")
        for d in (cls.a, cls.b, cls.ta, cls.tb):
            os.makedirs(d)
        with open(os.environ["PLEXDL_CONFIG"], "w") as f:
            json.dump({"require_mount": False, "disks": [
                {"id": "a", "label": "A", "mount": os.path.join(cls.tmp, "a"), "paths": {"movies": cls.a, "tv": cls.ta}},
                {"id": "b", "label": "B", "mount": os.path.join(cls.tmp, "b"), "paths": {"movies": cls.b, "tv": cls.tb}}]}, f)
        import config
        config.CONFIG_PATH = os.environ["PLEXDL_CONFIG"]
        config.BACKUP_DIR = os.path.join(cls.tmp, "backups")
        config._config = None
        config.load()
        import filemanager
        cls.fm = filemanager

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def make(self, base, name, size=200000):
        d = os.path.join(base, name)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, name + ".mkv"), "wb") as f:
            f.write(os.urandom(size))
        return d

    def wait(self, op):
        for _ in range(100):
            if op["status"] not in ("queued", "running"):
                return op
            time.sleep(0.05)
        self.fail("operacja nie zakończyła się")

    def test_extras_not_counted(self):
        d = self.make(self.a, "Extras (2010)")
        os.makedirs(os.path.join(d, "Trailers"))
        with open(os.path.join(d, "Trailers", "trailer.mp4"), "wb") as f:
            f.write(b"x" * 100)
        info = self.fm.scan_item(d, "movie")
        self.assertEqual(info["videos"], 1)
        self.assertTrue(info["extras"])
        plain = self.make(self.a, "Plain (2011)")
        self.assertFalse(self.fm.scan_item(plain, "movie")["extras"])

    def test_folder_dates_preserved(self):
        src = self.make(self.a, "Old (1999)")
        old = time.time() - 86400 * 400
        os.utime(src, (old, old))
        plan = self.fm.plan_move("a", "movies", ["Old (1999)"], "b", "movies")
        self.assertEqual(self.wait(self.fm.ops.move(plan))["status"], "done")
        self.assertAlmostEqual(os.stat(os.path.join(self.b, "Old (1999)")).st_mtime, old, delta=2)

    def test_move_without_verification(self):
        self.make(self.a, "Fast (2001)")
        plan = self.fm.plan_move("a", "movies", ["Fast (2001)"], "b", "movies")
        op = self.fm.ops.move(plan, verify=False)
        self.assertEqual(op["total"], plan["total"])  # only the copy stage is counted
        done = self.wait(op)
        self.assertEqual(done["status"], "done")
        self.assertEqual(done["verified"], 0)
        self.assertEqual(done["copied"], plan["total"])
        self.assertTrue(os.path.isdir(os.path.join(self.b, "Fast (2001)")))

    def test_progress_counters_with_verification(self):
        self.make(self.a, "Slow (2002)")
        plan = self.fm.plan_move("a", "movies", ["Slow (2002)"], "b", "movies")
        done = self.wait(self.fm.ops.move(plan))
        self.assertEqual(done["total"], plan["total"] * 2)
        self.assertEqual(done["copied"], plan["total"])
        self.assertEqual(done["verified"], plan["total"])

    def test_move_selected_episodes(self):
        show = os.path.join(self.ta, "Show")
        for se, ep in ((1, 1), (1, 2), (2, 1)):
            d = os.path.join(show, "Season %02d" % se)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "Show - S%02dE%02d.mkv" % (se, ep)), "wb") as f:
                f.write(os.urandom(5000))
        with open(os.path.join(show, "Season 01", "Show - S01E02.pl.srt"), "w") as f:
            f.write("1\n")
        eps = self.fm.list_episodes("a", "tv", "Show")
        codes = [e["code"] for s in eps["seasons"] for e in s["episodes"]]
        self.assertEqual(codes, ["S01E01", "S01E02", "S02E01"])
        plan = self.fm.plan_episodes("a", "tv", "Show", ["Season 01/Show - S01E02.mkv"], "b", "tv")
        self.assertTrue(plan["ok"], plan["problems"])
        self.assertEqual(self.wait(self.fm.ops.move(plan))["status"], "done")
        dst = os.path.join(self.tb, "Show", "Season 01")
        self.assertTrue(os.path.isfile(os.path.join(dst, "Show - S01E02.mkv")))
        self.assertTrue(os.path.isfile(os.path.join(dst, "Show - S01E02.pl.srt")))
        self.assertFalse(os.path.exists(os.path.join(show, "Season 01", "Show - S01E02.mkv")))
        self.assertTrue(os.path.isfile(os.path.join(show, "Season 01", "Show - S01E01.mkv")))
        self.assertTrue(os.path.isfile(os.path.join(show, "Season 02", "Show - S02E01.mkv")))

    def test_episodes_without_season_folders(self):
        """Episodes directly in the show folder (no Season 01) – error 500 in 1.4.0-beta2."""
        show = os.path.join(self.ta, "Flat Show")
        os.makedirs(show)
        for ep in (1, 2):
            with open(os.path.join(show, "Flat Show - S01E%02d.mkv" % ep), "wb") as f:
                f.write(os.urandom(3000))
        eps = self.fm.list_episodes("a", "tv", "Flat Show")
        self.assertEqual(len(eps["seasons"]), 1)
        self.assertEqual([e["code"] for e in eps["seasons"][0]["episodes"]], ["S01E01", "S01E02"])
        plan = self.fm.plan_episodes("a", "tv", "Flat Show", ["Flat Show - S01E02.mkv"], "b", "tv")
        self.assertTrue(plan["ok"], plan["problems"])
        self.assertEqual(self.wait(self.fm.ops.move(plan))["status"], "done")
        self.assertTrue(os.path.isfile(os.path.join(self.tb, "Flat Show", "Flat Show - S01E02.mkv")))
        with self.assertRaises(self.fm.FMError):
            self.fm.list_episodes("a", "movies", "Flat Show")

    def test_scan_paths(self):
        m = os.path.join(self.tmp, "scan")
        os.makedirs(os.path.join(m, "Plex", "Filmy")); os.makedirs(os.path.join(m, "Plex", "Seriale"))
        r = self.fm.scan_paths(m, [{"id": "movies", "label": "Movies", "folder": "Movies"},
                                   {"id": "tv", "label": "TV Shows", "folder": "TV Shows"},
                                   {"id": "kids", "label": "Kids", "folder": "Kids"}])
        self.assertEqual(r["movies"]["status"], "found")
        self.assertTrue(r["movies"]["path"].endswith("Filmy"))
        self.assertEqual(r["tv"]["status"], "found")
        self.assertEqual(r["kids"]["status"], "missing")

    def test_scan_disk_names(self):
        """Folder names only: plural / spelling variants, non-video folders skipped, odd names suggested."""
        m = os.path.join(self.tmp, "scan3")
        for d in ("Plex 512/Movies", "Plex 512/TV-Shows", "Plex 512/Home Videos", "Plex 512/Movies02",
                  "Plex 512/Music/Artist/Album", "Zdjęcia/2020", "Muzyka"):
            os.makedirs(os.path.join(m, d))
        cats = [{"id": "movies", "label": "Filmy", "folder": "Movies"}, {"id": "tv", "label": "Seriale", "folder": "TV Shows"},
                {"id": "kids", "label": "Dla dzieci", "folder": "Kids"},
                {"id": "home", "label": "Domowe wideo", "folder": "Home Video"}]
        res, extras = self.fm.scan_disk(m, cats)
        self.assertEqual(res["movies"]["path"], os.path.join(m, "Plex 512", "Movies"))
        self.assertEqual(res["tv"]["path"], os.path.join(m, "Plex 512", "TV-Shows"))
        self.assertEqual(res["home"]["path"], os.path.join(m, "Plex 512", "Home Videos"))
        self.assertEqual(res["kids"]["status"], "missing")
        self.assertEqual([(x["name"], x["guess"]) for x in extras], [("Movies02", "movies")])

    def test_scan_paths_other_device(self):
        """A path copied from another Pi is moved onto this mount point; folder names from other disks count."""
        m = os.path.join(self.tmp, "scan2")
        os.makedirs(os.path.join(m, "Plex 1T", "Home Video")); os.makedirs(os.path.join(m, "Plex 1T", "reddot"))
        cats = [{"id": "home", "label": "Domowe wideo", "folder": "Domowe wideo"},
                {"id": "red", "label": "Red", "folder": "Red", "names": ["reddot"]}]
        r = self.fm.scan_paths(m, cats, {"home": "/plex_media_1024/Plex 1T/Home Video"})
        self.assertEqual(r["home"], {"path": os.path.join(m, "Plex 1T", "Home Video"), "status": "found"})
        self.assertEqual(r["red"]["path"], os.path.join(m, "Plex 1T", "reddot"))

    def test_actlog_rotation(self):
        import actlog
        os.environ["PLEXDL_LOGS"] = os.path.join(self.tmp, "logs")
        old = actlog.LIMIT
        actlog.LIMIT = 400
        try:
            for i in range(40):
                actlog.write("MOVE", "item %d: A → B" % i)
            info = actlog.info()
            self.assertGreaterEqual(len(info["backups"]), 2)
            self.assertLessEqual(os.path.getsize(actlog.log_path()), 400)
            self.assertIn("MOVE", actlog.read())
            actlog.delete_backups()
            self.assertEqual(actlog.info()["backups"], [])
        finally:
            actlog.LIMIT = old
            del os.environ["PLEXDL_LOGS"]

    def test_traversal_rejected(self):
        for bad in ("..", "../x", "a/b", ".hidden", ""):
            with self.assertRaises(self.fm.FMError):
                self.fm.item_path(self.a, bad)

    def test_move_verified(self):
        src = self.make(self.a, "Film OK (2001)")
        plan = self.fm.plan_move("a", "movies", ["Film OK (2001)"], "b", "movies")
        self.assertTrue(plan["ok"]) ; self.assertFalse(plan["same_fs"])
        op = self.wait(self.fm.ops.move(plan))
        self.assertEqual(op["status"], "done", op)
        self.assertFalse(os.path.exists(src))
        self.assertTrue(os.path.isfile(os.path.join(self.b, "Film OK (2001)", "Film OK (2001).mkv")))

    def test_corrupted_copy_keeps_original(self):
        src = self.make(self.a, "Film Zly (2002)")
        orig = self.fm.Ops._hash
        self.fm.Ops._hash = lambda self_, op, path: "zly-skrot"
        try:
            plan = self.fm.plan_move("a", "movies", ["Film Zly (2002)"], "b", "movies")
            op = self.wait(self.fm.ops.move(plan))
        finally:
            self.fm.Ops._hash = orig
        self.assertEqual(op["status"], "error")
        self.assertTrue(os.path.isfile(os.path.join(src, "Film Zly (2002).mkv")), "oryginał musi zostać")
        self.assertFalse(os.path.exists(os.path.join(self.b, "Film Zly (2002)")), "brak niepełnej kopii")
        tmp = os.path.join(os.path.dirname(self.b), ".plexdl-tmp")
        self.assertFalse(os.path.isdir(tmp) and os.listdir(tmp), "folder tymczasowy posprzątany")

    def test_conflict_blocks(self):
        self.make(self.a, "Duplikat (2003)")
        self.make(self.b, "Duplikat (2003)")
        plan = self.fm.plan_move("a", "movies", ["Duplikat (2003)"], "b", "movies")
        self.assertFalse(plan["ok"])

    def test_busy_blocks(self):
        d = self.make(self.a, "Pobierany (2004)")
        plan = self.fm.plan_move("a", "movies", ["Pobierany (2004)"], "b", "movies", busy=[d])
        self.assertFalse(plan["ok"])
        r = self.fm.delete("a", "movies", ["Pobierany (2004)"], busy=[d])
        self.assertEqual(r["removed"], [])
        self.assertTrue(os.path.isdir(d))

    def test_delete(self):
        d = self.make(self.a, "Do usuniecia (2005)")
        r = self.fm.delete("a", "movies", ["Do usuniecia (2005)", "../../etc"])
        self.assertEqual(r["removed"], ["Do usuniecia (2005)"])
        self.assertFalse(os.path.exists(d))
        self.assertEqual(len(r["problems"]), 1)


if __name__ == "__main__":
    unittest.main()
