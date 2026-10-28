import unittest
from unittest.mock import patch

from scripts.run_daily_quality_maintenance import run_check


class DailyQualityMaintenanceTests(unittest.TestCase):
    def test_failed_check_is_recorded_without_throwing(self):
        result = run_check("broken", ["bash", "-c", "exit 7"], 10)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["exit_code"], 7)

    def test_timeout_is_recorded(self):
        result = run_check("slow", ["bash", "-c", "sleep 1"], 0)
        self.assertEqual(result["status"], "timeout")


if __name__ == "__main__":
    unittest.main()
