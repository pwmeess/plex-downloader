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
        os.makedirs(cls.a); os.makedirs(cls.b)
        with open(os.environ["PLEXDL_CONFIG"], "w") as f:
            json.dump({"require_mount": False, "disks": [
                {"id": "a", "label": "A", "mount": os.path.join(cls.tmp, "a"), "paths": {"movies": cls.a}},
                {"id": "b", "label": "B", "mount": os.path.join(cls.tmp, "b"), "paths": {"movies": cls.b}}]}, f)
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
