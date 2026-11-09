import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wizard  # noqa: E402


class WizardTests(unittest.TestCase):
    def test_mounts_parsing(self):
        tmp = tempfile.mkdtemp(dir=wizard.home_dir())  # not under /tmp (skipped as a system folder)
        disk = os.path.join(tmp, "ssd 1T")
        os.makedirs(disk)
        proc = os.path.join(tmp, "mounts")
        with open(proc, "w") as f:
            f.write("/dev/root / ext4 rw 0 0\nproc /proc proc rw 0 0\ntmpfs /run tmpfs rw 0 0\n"
                    "/dev/mmcblk0p1 /boot/firmware vfat rw 0 0\n"
                    "/dev/sda1 %s ext4 rw 0 0\n//192.168.1.10/plex %s cifs rw 0 0\n"
                    % (disk.replace(" ", "\\040"), tmp))
        m = wizard.mounts(proc)
        import shutil
        self.addCleanup(shutil.rmtree, tmp, True)
        self.assertEqual([x["mount"] for x in m], ["/", disk, tmp])
        self.assertTrue(m[0]["root"])
        self.assertTrue(m[2]["network"])
        self.assertFalse(m[1]["network"])

    def test_allowed(self):
        self.assertTrue(wizard.allowed(os.path.join(wizard.home_dir(), "Plex", "Movies")))
        self.assertFalse(wizard.allowed("/etc/plex"))
        self.assertFalse(wizard.allowed("/"))
        self.assertFalse(wizard.allowed("relative/path"))
        self.assertTrue(wizard.allowed("/media/ssd/Plex/Movies", ["/media/ssd"]))
        self.assertFalse(wizard.allowed("/media/other/Movies", ["/media/ssd"]))

    def test_check_and_create(self):
        base = tempfile.mkdtemp(dir=wizard.home_dir())
        try:
            target = os.path.join(base, "Plex", "Movies")
            self.assertFalse(wizard.check([target])[0]["exists"])
            created, problems = wizard.create([target, "/etc/nope"])
            self.assertEqual(created, [target])
            self.assertEqual(len(problems), 1)
            r = wizard.check([target])[0]
            self.assertTrue(r["exists"] and r["writable"])
        finally:
            import shutil
            shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
