import unittest

from services.movie_identity import ownership_keys
from services.authoritative_identity import resolve_authoritative_identity


class AuthoritativeIdentityTest(unittest.TestCase):
    def test_accepted_identity_survives_missing_provider_payload(self):
        resolved = resolve_authoritative_identity(
            {
                "metadata_status": "accepted",
                "tmdb_id": "93",
                "accepted_title": "Anatomy of a Murder",
                "accepted_year": "1959",
                "display_provider": "tmdb",
            },
            provider_metadata={},
            fallback={"title": "Anatomy.of.a.Murder", "year": "1959"},
        )

        self.assertEqual(resolved["identity_state"], "accepted")
        self.assertEqual(resolved["enrichment_state"], "incomplete")
        self.assertEqual(resolved["title"], "Anatomy of a Murder")
        self.assertEqual(resolved["tmdb_id"], "93")

    def test_enrichment_failure_cannot_demote_an_accepted_identity(self):
        resolved = resolve_authoritative_identity(
            {
                "identity_status": "accepted",
                "identity_title": "Alien",
                "identity_year": "1979",
                "tmdb_id": "348",
                "enrichment_status": "unavailable",
            },
            provider_metadata={"error": "provider unavailable"},
        )

        self.assertEqual(resolved["identity_state"], "accepted")
        self.assertEqual(resolved["enrichment_state"], "unavailable")

    def test_unaccepted_candidate_is_not_promoted_by_display_provider(self):
        resolved = resolve_authoritative_identity(
            {
                "identity_status": "review",
                "display_provider": "tmdb",
                "candidate_tmdb": {"tmdb_id": "661852", "title": "The Phantom Menace", "year": "2020"},
            },
            provider_metadata={"tmdb_id": "661852", "title": "The Phantom Menace", "year": "2020"},
        )

        self.assertEqual(resolved["identity_state"], "review")

    def test_ownership_never_uses_a_yearless_title(self):
        self.assertEqual(ownership_keys({"title": "Crash", "year": ""}), [])
        self.assertEqual(
            ownership_keys({"title": "Crash", "year": "1996"}),
            ["title:crash|1996"],
        )


if __name__ == "__main__":
    unittest.main()
