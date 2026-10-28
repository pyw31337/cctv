import unittest
from datetime import datetime, timezone

from scripts.build_recovery_plan import build_plan


class RecoveryPlanTests(unittest.TestCase):
    def test_normal_mode_keeps_safe_actions_only(self):
        plan = build_plan({"service_status": "OK", "cache": {"z3": {"severity": "ok"}}}, {"overall_status": "OK"}, datetime.now(timezone.utc))
        self.assertEqual(plan["mode"], "NORMAL")
        self.assertIn("preserve_last_known_good_catalog", plan["automatic_actions"])
        self.assertNotIn("refresh_z3_cache", plan["automatic_actions"])

    def test_service_impact_requests_recovery_without_mapping_promotion(self):
        plan = build_plan({"service_status": "SERVICE_IMPACT", "cache": {"z3": {"severity": "danger", "age_hours": 55}}}, {"overall_status": "SERVICE_IMPACT"}, datetime.now(timezone.utc))
        self.assertEqual(plan["mode"], "RECOVERY_REQUIRED")
        self.assertIn("refresh_z3_cache", plan["automatic_actions"])
        self.assertEqual(plan["safety"]["mapping_promotion"], "blocked_until_independent_verification")


if __name__ == "__main__":
    unittest.main()
