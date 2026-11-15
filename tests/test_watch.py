"""“Where to watch”: streaming availability from the TMDB details response (watch/providers = JustWatch data)."""
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import movieinfo  # noqa: E402


def P(pid, name, prio):
    return {"provider_id": pid, "provider_name": name, "logo_path": "/l%d.png" % pid, "display_priority": prio}


DETAILS = {
    "id": 274, "title": "Milczenie owiec", "original_title": "The Silence of the Lambs", "release_date": "1991-02-14",
    "overview": "x", "credits": {"cast": [], "crew": []}, "external_ids": {},
    "watch/providers": {"results": {
        "PL": {"link": "https://www.themoviedb.org/movie/274/watch?locale=PL",
               "flatrate": [P(8, "Netflix", 2), P(119, "Prime Video", 1)], "rent": [P(2, "Apple TV", 3)]},
        "US": {"link": "L", "free": [P(1, "A", 1)], "ads": [P(1, "A", 1), P(300, "Pluto TV", 2)], "buy": [P(2, "Apple TV", 3)]},
    }},
}


class TestWatch(unittest.TestCase):
    def test_groups_and_order(self):
        w = movieinfo._watch(DETAILS, "PL")
        self.assertEqual([p["name"] for p in w["flatrate"]], ["Prime Video", "Netflix"])   # display_priority
        self.assertEqual(w["rent"][0]["logo"], movieinfo.IMG + "w92/l2.png")
        self.assertEqual(w["buy"], [])
        self.assertTrue(w["any"])
        self.assertEqual(w["link"], "https://www.themoviedb.org/movie/274/watch?locale=PL")

    def test_free_and_ads_together(self):
        w = movieinfo._watch(DETAILS, "US")
        self.assertEqual([p["name"] for p in w["free"]], ["A", "Pluto TV"])
        self.assertNotIn("ads", w)

    def test_country_without_data(self):
        w = movieinfo._watch(DETAILS, "DE")
        self.assertFalse(w["any"])
        self.assertEqual(w["country"], "DE")

    def test_country_choice(self):
        with mock.patch.object(movieinfo.config, "get", return_value={"watch_country": "de"}):
            self.assertEqual(movieinfo.watch_country(), "DE")
        with mock.patch.object(movieinfo.config, "get", return_value={"watch_country": ""}), \
                mock.patch.object(movieinfo, "tmdb_language", return_value="pl-PL"):
            self.assertEqual(movieinfo.watch_country(), "PL")
        with mock.patch.object(movieinfo.config, "get", return_value={}), \
                mock.patch.object(movieinfo, "tmdb_language", return_value="en-US"):
            self.assertEqual(movieinfo.watch_country(), "US")

    def test_one_request_for_details(self):
        calls = []

        def fake_get(path, **params):
            calls.append((path, params))
            return DETAILS
        with mock.patch.object(movieinfo, "_get", side_effect=fake_get), \
                mock.patch.object(movieinfo, "watch_country", return_value="PL"):
            info = movieinfo.details("movie", 274)
        self.assertEqual(len(calls), 1)
        self.assertIn("watch/providers", calls[0][1]["append_to_response"])
        self.assertEqual(info["watch"]["country"], "PL")


if __name__ == "__main__":
    unittest.main()
