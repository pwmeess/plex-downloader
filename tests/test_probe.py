"""probe(): redirects to a web page must not produce a strange file name."""
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import downloader  # noqa: E402


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, head_only):
        if self.path.startswith("/dload/"):          # redirect to a login page with an encoded path
            self.send_response(302)
            self.send_header("Location", "/login/L2Rsb2FkL3gvMTA4MC8xMjM0NS0xMDgwcC5tcDQ")
            self.end_headers()
        elif self.path.startswith("/login/"):
            body = b"<html>please log in</html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if not head_only:
                self.wfile.write(body)
        elif self.path.startswith("/files/"):        # normal file behind a redirect to a CDN name
            self.send_response(302)
            self.send_header("Location", "/cdn/Real.Movie.2020.1080p.mkv")
            self.end_headers()
        else:
            self.send_response(200)
            self.send_header("Content-Type", "video/x-matroska")
            self.send_header("Content-Length", "1000")
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()

    def do_HEAD(self):
        self._send(True)

    def do_GET(self):
        self._send(False)


class ProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), H)
        cls.base = "http://127.0.0.1:%d" % cls.srv.server_port
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_redirect_to_web_page(self):
        r = downloader.probe(self.base + "/dload/x/1080/12345-1080p.mp4")
        self.assertTrue(r["page"])
        self.assertEqual(r["filename"], "12345-1080p.mp4")
        self.assertEqual(r["ext"], ".mp4")

    def test_redirect_to_file(self):
        r = downloader.probe(self.base + "/files/abc")
        self.assertFalse(r["page"])
        self.assertEqual(r["filename"], "Real.Movie.2020.1080p.mkv")
        self.assertEqual(r["size"], 1000)


if __name__ == "__main__":
    unittest.main()
