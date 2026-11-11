"""Posters from video frames (ffmpeg); skipped when ffmpeg is not installed."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import thumbgen  # noqa: E402


@unittest.skipUnless(thumbgen.available(), "ffmpeg not installed")
class FrameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.video = os.path.join(cls.tmp, "Home Video (2020)", "Home Video (2020).mp4")
        os.makedirs(os.path.dirname(cls.video))
        # 1 s black, then 9 s test pattern – the black start must not be chosen
        subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "color=black:s=320x180:d=1",
                        "-f", "lavfi", "-i", "testsrc=s=320x180:d=9", "-filter_complex", "[0][1]concat=n=2:v=1",
                        "-pix_fmt", "yuv420p", cls.video], check=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_best_and_candidates(self):
        self.assertAlmostEqual(thumbgen.duration(self.video), 10, delta=0.5)
        self.assertLess(thumbgen.score(self.video, 0.2), thumbgen.score(self.video, 5))
        data = thumbgen.best(self.video)
        self.assertEqual(data[:3], b"\xff\xd8\xff")
        frames = thumbgen.candidates(self.video, 3)
        self.assertEqual(len(frames), 3)
        self.assertTrue(all(d[:3] == b"\xff\xd8\xff" for _t, d in frames))

    def test_first_video_skips_trailers(self):
        root = os.path.dirname(self.video)
        os.makedirs(os.path.join(root, "Trailers"), exist_ok=True)
        with open(os.path.join(root, "Trailers", "big.mp4"), "wb") as f:
            f.write(b"0" * 10_000_000)
        self.assertEqual(thumbgen.first_video(root, lambda n: n.endswith(".mp4")), self.video)

    def test_bad_file(self):
        bad = os.path.join(self.tmp, "bad.mkv")
        with open(bad, "wb") as f:
            f.write(b"not a video")
        with self.assertRaises(thumbgen.FrameError):
            thumbgen.best(bad)


if __name__ == "__main__":
    unittest.main()
