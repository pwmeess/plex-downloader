"""File manager – editing the Plex name (folder, files, subtitles, poster) and own posters."""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def touch(path, data=b"x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


class RenameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.m = os.path.join(cls.tmp, "a", "Plex", "Movies")
        cls.tv = os.path.join(cls.tmp, "a", "Plex", "TV Shows")
        os.makedirs(cls.m); os.makedirs(cls.tv)
        import config
        cls.saved = (config.CONFIG_PATH, config.BACKUP_DIR, config._config)
        config.CONFIG_PATH = os.path.join(cls.tmp, "config.json")
        config.BACKUP_DIR = os.path.join(cls.tmp, "backups")
        with open(config.CONFIG_PATH, "w") as f:
            json.dump({"require_mount": False, "disks": [{"id": "a", "label": "A", "mount": os.path.join(cls.tmp, "a"),
                                                         "paths": {"movies": cls.m, "tv": cls.tv}}]}, f)
        config._config = None
        config.load()
        import filemanager
        cls.fm = filemanager

    @classmethod
    def tearDownClass(cls):
        import config
        config.CONFIG_PATH, config.BACKUP_DIR, config._config = cls.saved
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_movie_folder(self):
        old = "Avatar Extended Collectors Edition (2009)"
        d = os.path.join(self.m, old)
        touch(os.path.join(d, old + ".mkv"))
        touch(os.path.join(d, old + " - 4K.mkv"))
        touch(os.path.join(d, old + ".pl.srt"))
        touch(os.path.join(d, old + ".thumb.jpg"))
        touch(os.path.join(d, "Trailers", "trailer.mp4"))
        info = self.fm.item_details("a", "movies", old)
        self.assertEqual({f["name"]: f["version"] for f in info["files"]}, {old + ".mkv": "", old + " - 4K.mkv": "4K"})
        dry = self.fm.rename_item("a", "movies", old, "Avatar", 2009, "19995", "Extended Collectors Edition",
                                  {old + ".mkv": "1080p"}, dry=True)
        new = "Avatar (2009) {tmdb-19995} {edition-Extended Collectors Edition}"
        self.assertEqual(dry["new_name"], new)
        self.assertTrue(os.path.isdir(d))                         # dry run changes nothing
        self.fm.rename_item("a", "movies", old, "Avatar", 2009, "19995", "Extended Collectors Edition",
                            {old + ".mkv": "1080p"})
        nd = os.path.join(self.m, new)
        self.assertEqual(sorted(os.listdir(nd)), sorted([
            new + " - 1080p.mkv", new + " - 1080p.pl.srt", new + " - 4K.mkv", new + ".thumb.jpg", "Trailers"]))
        self.assertTrue(os.path.isfile(os.path.join(nd, "Trailers", "trailer.mp4")))
        # back again, only the title changes; versions are kept
        self.fm.rename_item("a", "movies", new, "Avatar", 2009, "", "", {})
        self.assertIn("Avatar (2009) - 4K.mkv", os.listdir(os.path.join(self.m, "Avatar (2009)")))

    def test_conflict_and_bad_input(self):
        touch(os.path.join(self.m, "One (2001)", "One (2001).mkv"))
        touch(os.path.join(self.m, "Two (2002)", "Two (2002).mkv"))
        with self.assertRaises(self.fm.FMError):
            self.fm.rename_item("a", "movies", "One (2001)", "Two", 2002)
        with self.assertRaises(self.fm.FMError):
            self.fm.rename_item("a", "movies", "One (2001)", "", 2001)
        with self.assertRaises(self.fm.FMError):
            self.fm.rename_item("a", "movies", "One (2001)", "One", 2001, "12a")
        with self.assertRaises(self.fm.FMError):
            self.fm.rename_item("a", "movies", "../One (2001)", "One", 2001)

    def test_loose_file(self):
        touch(os.path.join(self.m, "loose.movie.2005.mkv"))
        touch(os.path.join(self.m, "loose.movie.2005.thumb.jpg"))
        self.fm.rename_item("a", "movies", "loose.movie.2005.mkv", "Loose Movie", 2005)
        self.assertTrue(os.path.isfile(os.path.join(self.m, "Loose Movie (2005).mkv")))
        self.assertTrue(os.path.isfile(os.path.join(self.m, "Loose Movie (2005).thumb.jpg")))

    def test_tv_show(self):
        touch(os.path.join(self.tv, "Show", "Season 01", "Show - S01E01.mkv"))
        touch(os.path.join(self.tv, "Show", "Season 01", "Show - S01E01.pl.srt"))
        self.fm.rename_item("a", "tv", "Show", "Good Show", 2020, "1234", "ignored")
        root = os.path.join(self.tv, "Good Show (2020) {tmdb-1234}", "Season 01")
        self.assertEqual(sorted(os.listdir(root)), ["Good Show (2020) - S01E01.mkv", "Good Show (2020) - S01E01.pl.srt"])

    def test_own_poster(self):
        touch(os.path.join(self.m, "Pic (2003)", "Pic (2003).mkv"))
        touch(os.path.join(self.m, "Pic (2003)", "Pic (2003).thumb.png"))
        with self.assertRaises(self.fm.FMError):
            self.fm.save_thumb("a", "movies", "Pic (2003)", b"<svg>")
        self.fm.save_thumb("a", "movies", "Pic (2003)", b"\xff\xd8\xff\xe0" + b"0" * 100)
        self.assertEqual(sorted(os.listdir(os.path.join(self.m, "Pic (2003)"))), ["Pic (2003).mkv", "Pic (2003).thumb.jpg"])


if __name__ == "__main__":
    unittest.main()
