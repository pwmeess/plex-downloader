import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import naming  # noqa: E402


class GuessTests(unittest.TestCase):
    def check_movie(self, filename, name, ext):
        g = naming.guess(filename)
        self.assertEqual(g["kind"], "movie", filename)
        self.assertEqual(g["name"], name)
        self.assertEqual(g["ext"], ext)

    def test_movies(self):
        self.check_movie("The.33.2015.PL.720p.BRRip.XviD.ac3-GUN.mp4", "The 33 (2015)", ".mp4")
        self.check_movie("2001.A.Space.Odyssey.1968.1080p.BluRay.x264.mkv", "2001 A Space Odyssey (1968)", ".mkv")
        self.check_movie("Blade.Runner.2049.2017.2160p.mkv", "Blade Runner 2049 (2017)", ".mkv")
        self.check_movie("1917.2019.PL.1080p.mkv", "1917 (2019)", ".mkv")
        self.check_movie("Ojciec_Chrzestny_1972_Lektor_PL.avi", "Ojciec Chrzestny (1972)", ".avi")

    def test_tv(self):
        g = naming.guess("Breaking.Bad.S02E05.720p.HDTV.mkv")
        self.assertEqual((g["kind"], g["show"], g["season"], g["episode"]), ("tv", "Breaking Bad", 2, 5))
        g = naming.guess("House.of.the.Dragon.2022.S02E01.1080p.mkv")
        self.assertEqual(g["show"], "House of the Dragon (2022)")

    def test_link_names(self):
        """Names taken from download links: site prefixes, percent-encoding, bare resolutions, 'Episode N'."""
        cd = ('attachment; filename="EXAMPLE-SITE.COM%20-%20[NEW%20Release]%20Some%20Show%20Name%20'
              'Episode%202%20Subtitle%20English%20(720).mp4"')
        fn = naming.filename_from_content_disposition(cd)
        self.assertNotIn("%20", fn)
        g = naming.guess(fn)
        self.assertEqual((g["kind"], g["show"], g["season"], g["episode"], g["ext"]), ("tv", "Some Show Name", 1, 2, ".mp4"))
        self.check_movie("www.files-site.net - The Last Harbor 2019 (1080).mkv", "The Last Harbor (2019)", ".mkv")
        self.check_movie("Night Train (720).mp4", "Night Train", ".mp4")
        self.check_movie("Movie.Title.2020.Subtitles.EN.mkv", "Movie Title (2020)", ".mkv")
        g = naming.guess("Polar Station Season 2 Episode 05 1080p.mkv")
        self.assertEqual((g["kind"], g["show"], g["season"], g["episode"]), ("tv", "Polar Station", 2, 5))
        g = naming.guess("Ranczo.Sezon.3.Odcinek.7.PL.mp4")
        self.assertEqual((g["kind"], g["show"], g["season"], g["episode"]), ("tv", "Ranczo", 3, 7))
        g = naming.guess("Dark.2017.Ep.03.mkv")
        self.assertEqual((g["show"], g["episode"]), ("Dark (2017)", 3))
        self.check_movie("Star.Wars.Episode.1.The.Phantom.Menace.1999.1080p.mkv",
                         "Star Wars Episode 1 The Phantom Menace (1999)", ".mkv")
        # titles with dots and dashes must not be cut as site names
        self.check_movie("Mr.Robot - The.Movie.2016.mkv", "Mr Robot - The Movie (2016)", ".mkv")
        self.check_movie("Dr.No.1962.1080p.mkv", "Dr No (1962)", ".mkv")

    def test_targets(self):
        folder, fname = naming.movie_target("/m/Movies", "The 33 (2015)", ".mp4")
        self.assertEqual(os.path.join(folder, fname), "/m/Movies/The 33 (2015)/The 33 (2015).mp4")
        folder, fname = naming.tv_target("/m/TV Shows", "Breaking Bad", 2, 5, "", ".mkv")
        self.assertEqual(os.path.join(folder, fname), "/m/TV Shows/Breaking Bad/Season 02/Breaking Bad - S02E05.mkv")

    def test_sanitize_blocks_traversal(self):
        self.assertEqual(naming.sanitize("../../etc"), "etc")
        self.assertNotIn("/", naming.sanitize("a/b\\c"))
        with self.assertRaises(ValueError):
            naming.movie_target("/m", "..", ".mkv")

    def test_content_disposition(self):
        self.assertEqual(naming.filename_from_content_disposition(
            "attachment; filename*=UTF-8''Gwiezdne%20wojny.mkv"), "Gwiezdne wojny.mkv")
        self.assertEqual(naming.filename_from_content_disposition('inline; filename="a b.mp4"'), "a b.mp4")


if __name__ == "__main__":
    unittest.main()
