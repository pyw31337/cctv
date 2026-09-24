import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import sentinel


# Built from parts so the fixture's conflict markers don't trip `git diff --check`.
CONFLICTED_STATUS = "\n".join([
    '{',
    '  "regions": {"BUSAN": {"status": "OK"}},',
    '  "time": {',
    '<' * 7 + ' HEAD',
    '    "generated_at": "2026-09-07T06:32:42Z"',
    '=' * 7,
    '    "generated_at": "2026-09-06T12:00:03Z"',
    '>' * 7 + ' e6befc2bc (AUTO: Local Z3 cache refresh [skip ci])',
    '  }',
    '}',
    '',
])


class SentinelResilienceTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.dir = Path(directory.name)
        patcher = patch.object(sentinel, 'LOG_FILE', str(self.dir / 'sentinel.log'))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(setattr, sentinel, 'RUN_DEADLINE', None)

    def test_conflict_marked_status_is_recovered_keeping_first_side(self):
        path = self.dir / 'status.json'
        path.write_text(CONFLICTED_STATUS, encoding='utf-8')
        data = sentinel.load_status_file(str(path))
        self.assertEqual(data['regions']['BUSAN']['status'], 'OK')
        self.assertEqual(data['time']['generated_at'], '2026-09-07T06:32:42Z')

    def test_unrecoverable_status_starts_fresh_and_keeps_a_copy(self):
        path = self.dir / 'status.json'
        path.write_text('{"regions": {broken', encoding='utf-8')
        self.assertEqual(sentinel.load_status_file(str(path)), {})
        self.assertEqual(len(list(self.dir.glob('status.json.corrupt-*'))), 1)

    def _run_region(self, cameras, check):
        with patch.object(sentinel, 'select_representative_cameras',
                          side_effect=lambda _r, cams, _t, current_status=None: (cams, len(cams), 0, 0)), \
                patch.object(sentinel, 'check_camera', side_effect=check), \
                patch.dict('os.environ', {'CCTV_SENTINEL_MAX_WORKERS': '2'}):
            return sentinel.test_region('BUSAN', cameras, current_status={}, target_size=len(cameras))

    def test_deadline_saves_partial_results_without_counting_skipped_cameras(self):
        def slow_ok(_region, cam):
            time.sleep(0.3)
            sentinel.set_probe_result(cam, True)
            return True

        cameras = [{'id': f'CAM_{i}', 'source': 'BUSAN_ITS'} for i in range(10)]
        sentinel.RUN_DEADLINE = time.monotonic() + 0.45
        started = time.monotonic()
        result = self._run_region(cameras, slow_ok)
        self.assertLess(time.monotonic() - started, 2.0)
        self.assertGreater(result['skipped'], 0)
        self.assertEqual(result['checked'], len(result['sample_ids']))
        self.assertEqual(result['failed'], 0)
        self.assertEqual(result['status'], 'OK')

    def test_rate_limited_checks_are_not_camera_failures(self):
        def check(_region, cam):
            limited = cam['id'] == 'CAM_1'
            sentinel.set_probe_result(cam, not limited, reason='http_error' if limited else 'ok',
                                      status_code=429 if limited else 200)
            return not limited

        cameras = [{'id': 'CAM_0', 'source': 'BUSAN_ITS'}, {'id': 'CAM_1', 'source': 'BUSAN_ITS'}]
        result = self._run_region(cameras, check)
        self.assertEqual(result['checked'], 1)
        self.assertEqual(result['failed'], 0)
        self.assertEqual(result['skipped'], 1)
        self.assertNotIn('CAM_1', result['sample_ids'])

    def test_fatal_error_exits_non_zero(self):
        with patch.object(sentinel, 'load_json', side_effect=RuntimeError('boom')):
            with self.assertRaises(SystemExit) as raised:
                sentinel.run_sentinel()
        self.assertEqual(raised.exception.code, 1)


if __name__ == '__main__':
    unittest.main()
