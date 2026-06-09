import unittest

import app


class ReactRouteTest(unittest.TestCase):
    def test_react_sections_serve_built_index(self):
        client = app.app.test_client()

        response = client.get("/discover")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<div id="root"></div>', response.data)


if __name__ == "__main__":
    unittest.main()
