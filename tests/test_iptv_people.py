import unittest
from unittest.mock import patch
from flask import Flask

from tests import test_iptv_movie_availability as fixtures
from services.iptv_routes import register_iptv_routes
from services.iptv_provider_manager import IPTVProviderManager


class IPTVPeopleTests(unittest.TestCase):
    setUp = fixtures.MovieAvailabilityTests.setUp

    def test_person_filter_groups_versions_and_filters_before_pagination(self):
        result = self.store.list_movies({"view": "cp", "category": "film", "person_id": 3,
                                         "person_role": "actor"}, page=1, page_size=1)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["tmdb_id"], 550)
        wrong_role = self.store.list_movies({"view": "cp", "person_id": 3, "person_role": "director"})
        self.assertEqual(wrong_role["total"], 0)
        absent = self.store.list_movies({"view": "cp", "person_id": 999, "person_role": "actor"})
        self.assertEqual(absent["total"], 0)

    def test_invalid_person_filter_is_rejected(self):
        for filters in ({"person_role": "actor"}, {"person_id": -1, "person_role": "actor"},
                        {"person_id": 3, "person_role": "writer"}):
            with self.assertRaises(ValueError):
                self.store.list_movies({"view": "cp", **filters})

    def test_iptv_bio_uses_iptv_settings_and_normalizes_payload(self):
        manager = IPTVProviderManager(self.root, migrate_legacy=False)
        self.addCleanup(manager.close)
        app = Flask(__name__)
        register_iptv_routes(app, lambda: manager)
        with patch("services.iptv_routes.IPTVTMDBClient") as client:
            client.return_value.person.return_value = {
                "id": 3, "name": "Actor One", "biography": "Biography", "profile_path": "/actor.jpg"}
            response = app.test_client().get(f"/api/iptv/providers/{self.provider_id}/people/3")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["biography"], "Biography")
        self.assertEqual(response.json["profile_url"], "https://image.tmdb.org/t/p/w342/actor.jpg")
        client.assert_called_once_with(manager.metadata_settings)
