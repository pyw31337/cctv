import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault('CCTV_DISABLE_STARTUP_JOBS', '1')

try:
    import server.app as server_app
except ImportError:  # Keep the data-only test suite usable without server extras.
    server_app = None


@unittest.skipUnless(server_app is not None, 'server runtime dependencies are not installed')
class ServerResilienceTests(unittest.TestCase):
    def setUp(self):
        server_app.rate_limit_buckets.clear()

    def test_stream_rejects_private_network_target(self):
        response = server_app.app.test_client().get(
            '/stream?url=http://127.0.0.1:8080/live'
        )
        self.assertEqual(response.status_code, 400)

    def test_proxy_rejects_oversized_response(self):
        class Response:
            headers = {'Content-Length': str(server_app.MAX_PROXY_RESPONSE_BYTES + 1)}

            def iter_content(self, chunk_size=None):
                self.fail('oversized response should be rejected before reading')

        with self.assertRaises(ValueError):
            server_app.read_upstream_body(Response())

    def test_proxy_does_not_return_internal_exception(self):
        with patch.object(server_app, 'fetch_upstream', side_effect=RuntimeError('private detail')):
            response = server_app.app.test_client().get('/proxy?url=https://example.com/live')
        self.assertEqual(response.status_code, 502)
        self.assertNotIn(b'private detail', response.data)

    def test_rate_limit_returns_retry_after(self):
        original_limit = server_app.RATE_LIMIT_MAX_REQUESTS
        server_app.RATE_LIMIT_MAX_REQUESTS = 1
        try:
            client = server_app.app.test_client()
            self.assertEqual(client.get('/proxy').status_code, 400)
            response = client.get('/proxy')
            self.assertEqual(response.status_code, 429)
            self.assertIn('Retry-After', response.headers)
        finally:
            server_app.RATE_LIMIT_MAX_REQUESTS = original_limit

    def test_corrupt_status_serves_last_good_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'canary.json'
            path.write_text(json.dumps({'service_status': 'OK'}), encoding='utf-8')
            original_path = server_app.CANARY_STATUS_FILE
            server_app.CANARY_STATUS_FILE = str(path)
            try:
                client = server_app.app.test_client()
                self.assertEqual(client.get('/canary-status').status_code, 200)
                path.write_text('{broken', encoding='utf-8')
                response = client.get('/canary-status')
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.get_json()['_stale'])
            finally:
                server_app.CANARY_STATUS_FILE = original_path

    def test_log_url_redacts_query_secrets(self):
        redacted = server_app.redact_url_for_log(
            'https://example.com/live?key=secret&token=hidden&camera=7'
        )
        self.assertNotIn('secret', redacted)
        self.assertNotIn('hidden', redacted)
        self.assertIn('camera=7', redacted)

    def test_kill_stream_removes_terminated_process_and_files(self):
        class TerminatedProcess:
            def poll(self):
                return 1

            def send_signal(self, _signal):
                return None

            def wait(self, timeout=None):
                return 1

        stream_id = 'c' * 32
        with tempfile.TemporaryDirectory() as directory:
            original_hls_dir = server_app.HLS_DIR
            server_app.HLS_DIR = directory
            stream_dir = Path(directory) / stream_id
            stream_dir.mkdir()
            server_app.streams[stream_id] = {
                'process': TerminatedProcess(),
                'last_access': 0,
                'url': 'https://example.com/live',
            }
            try:
                server_app.kill_stream(stream_id)
                self.assertNotIn(stream_id, server_app.streams)
                self.assertFalse(stream_dir.exists())
            finally:
                server_app.HLS_DIR = original_hls_dir


if __name__ == '__main__':
    unittest.main()
