import unittest
from unittest.mock import Mock, patch

import requests

import validate_cctv_data as validator


SAMPLE_DATA = [
    {"name": "마석사거리", "url": "https://example.test/media/L1.m3u8"},
    {"name": "마석윗3", "url": "https://example.test/media/L2.m3u8"},
    {"name": "창현A앞4", "url": "https://example.test/media/L3.m3u8"},
    {"name": "심학중사거리", "url": "https://trafficcctv.paju.go.kr/live.m3u8"},
]


class StreamAccessTests(unittest.TestCase):
    @patch("validate_cctv_data.time.sleep")
    def test_retries_transient_failures(self, _sleep):
        request_get = Mock(
            side_effect=[
                requests.Timeout("first timeout"),
                Mock(status_code=503),
                Mock(status_code=200),
            ]
        )

        issue = validator.check_stream_access("https://example.test/a.m3u8", request_get=request_get)

        self.assertIsNone(issue)
        self.assertEqual(request_get.call_count, 3)

    @patch("validate_cctv_data.time.sleep")
    def test_reports_failure_after_all_attempts(self, _sleep):
        request_get = Mock(side_effect=requests.Timeout("offline"))

        issue = validator.check_stream_access("https://example.test/a.m3u8", request_get=request_get)

        self.assertIn("일시 접근 실패", issue)
        self.assertEqual(request_get.call_count, 3)


class CriticalSampleTests(unittest.TestCase):
    def test_network_failures_are_warnings_by_default(self):
        errors, warnings = validator.validate_critical_samples(
            SAMPLE_DATA,
            access_checker=lambda _url: "스트림 일시 접근 실패 (timeout)",
        )

        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 4)

    def test_strict_network_mode_keeps_previous_fatal_behavior(self):
        errors, warnings = validator.validate_critical_samples(
            SAMPLE_DATA,
            strict_network=True,
            access_checker=lambda _url: "스트림 일시 접근 실패 (timeout)",
        )

        self.assertEqual(len(errors), 4)
        self.assertEqual(warnings, [])

    def test_configuration_errors_remain_fatal(self):
        invalid = [dict(item) for item in SAMPLE_DATA]
        invalid[0]["url"] = "https://example.test/not-the-required-path.m3u8"

        errors, _warnings = validator.validate_critical_samples(
            invalid,
            access_checker=lambda _url: None,
        )

        self.assertTrue(any("예상 패턴" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
