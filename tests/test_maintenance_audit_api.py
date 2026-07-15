import unittest
from unittest.mock import patch

import app


class MaintenanceAuditApiTest(unittest.TestCase):
    def test_workspace_contract_exposes_only_unmatched_and_authoritative_review_rows(self):
        maintenance = {
            "source": "catalog",
            "summary": {
                "unmatched_files": 1,
                "identity_issues": 33,
                "verification_gaps": 32,
                "automated_identity_checks": 177,
                "hard_conflicts": 0,
                "metadata_drift": 184,
            },
            "storage": {"groups": []},
            "upgrades": {"items": []},
            "identity": {
                "items": [{"path": "E:/Movies/Unmatched.mkv"}],
                "verification": [{"path": f"E:/Movies/Diagnostic-{index}.mkv"} for index in range(32)],
            },
        }
        identity_review = {
            "id": "audit-1",
            "status": "completed",
            "shadow_mode": True,
            "mutates_metadata": False,
            "outcome_counts": {"actionable": 1},
            "proposals": [{"id": "proposal-1", "classification": "actionable"}],
        }

        with patch.object(app, "_maintenance_audit_from_catalog", return_value=maintenance), \
                patch.object(app, "_get_identity_audit_coordinator") as coordinator:
            coordinator.return_value.status.return_value = identity_review
            response = app.app.test_client().get("/api/maintenance/audit")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["summary"]["actionable_identities"], 1)
        self.assertEqual(payload["summary"]["identity_issues"], 2)
        self.assertNotIn("verification_gaps", payload["summary"])
        self.assertNotIn("automated_identity_checks", payload["summary"])
        self.assertEqual(payload["identity"], {"items": maintenance["identity"]["items"]})
        self.assertEqual(payload["identity_review"]["proposals"], identity_review["proposals"])
        self.assertTrue(payload["identity_review"]["shadow_mode"])
        self.assertFalse(payload["identity_review"]["mutates_metadata"])

    def test_section_contract_returns_only_requested_paginated_projection(self):
        maintenance = {
            "source": "catalog",
            "generation": 12,
            "generated_at": 123.0,
            "summary": {"duplicate_groups": 2, "unmatched_files": 0},
            "storage": {
                "groups": [
                    {"title": "Alpha (2001)", "files": [{"filename": "Alpha.mkv", "path": "E:/Alpha.mkv"}]},
                    {"title": "Beta (2002)", "files": [{"filename": "Beta.mkv", "path": "E:/Beta.mkv"}]},
                ]
            },
            "upgrades": {"items": []},
            "identity": {"items": [], "verification": []},
        }
        with patch.object(app, "_maintenance_audit_from_catalog", return_value=maintenance), \
                patch.object(app, "_get_identity_audit_coordinator") as coordinator:
            coordinator.return_value.status.return_value = {"status": "idle", "proposals": []}
            response = app.app.test_client().get(
                "/api/maintenance/audit?section=storage&q=beta&page=1&page_size=1"
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["generation"], 12)
        self.assertEqual([group["title"] for group in payload["storage"]["groups"]], ["Beta (2002)"])
        self.assertEqual(payload["storage"]["pagination"]["total"], 1)
        self.assertNotIn("upgrades", payload)
        self.assertNotIn("identity", payload)
        self.assertNotIn("identity_review", payload)

    def test_invalid_section_is_rejected(self):
        with patch.object(app, "_maintenance_audit_from_catalog", return_value={"summary": {}}), \
                patch.object(app, "_get_identity_audit_coordinator") as coordinator:
            coordinator.return_value.status.return_value = {"status": "idle", "proposals": []}
            response = app.app.test_client().get("/api/maintenance/audit?section=legacy")
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
