import unittest
from unittest.mock import patch

import app


class ReactRouteTest(unittest.TestCase):
    def test_react_sections_serve_built_index(self):
        client = app.app.test_client()

        response = client.get("/discover")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<div id="root"></div>', response.data)

    def test_root_does_not_fall_back_to_legacy_template_when_frontend_missing(self):
        client = app.app.test_client()

        with patch.object(app.os.path, "exists", return_value=False):
            response = client.get("/")

        self.assertEqual(response.status_code, 503)
        self.assertIn(b"React frontend has not been built", response.data)

    def test_legacy_route_is_not_public(self):
        client = app.app.test_client()

        response = client.get("/legacy")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
