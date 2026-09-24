import json
import os
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import requests


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
        original_limit = server_app.RATE_LIMIT_PROXY_MAX_REQUESTS
        server_app.RATE_LIMIT_PROXY_MAX_REQUESTS = 1
        try:
            client = server_app.app.test_client()
            self.assertEqual(client.get('/proxy').status_code, 400)
            response = client.get('/proxy')
            self.assertEqual(response.status_code, 429)
            self.assertIn('Retry-After', response.headers)
        finally:
            server_app.RATE_LIMIT_PROXY_MAX_REQUESTS = original_limit

    def test_proxy_playback_has_more_headroom_than_resolvers(self):
        original = (server_app.RATE_LIMIT_MAX_REQUESTS, server_app.RATE_LIMIT_PROXY_MAX_REQUESTS)
        server_app.RATE_LIMIT_MAX_REQUESTS, server_app.RATE_LIMIT_PROXY_MAX_REQUESTS = 2, 5
        self.addCleanup(lambda: setattr(server_app, 'RATE_LIMIT_MAX_REQUESTS', original[0]))
        self.addCleanup(lambda: setattr(server_app, 'RATE_LIMIT_PROXY_MAX_REQUESTS', original[1]))
        client = server_app.app.test_client()
        self.assertEqual([client.get('/kb').status_code for _ in range(3)], [400, 400, 429])
        self.assertEqual([client.get('/proxy').status_code for _ in range(5)], [400] * 5)

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

    def test_static_route_serves_only_public_assets(self):
        client = server_app.app.test_client()
        for path in ('/.git/config', '/.env.example', '/server/app.py', '/scripts/sentinel.py',
                     '/deploy_to_oracle.sh', '/CLAUDE.md', '/oracle_key'):
            response = client.get(path)
            self.assertEqual(response.status_code, 404, path)
            response.close()
        for path in ('/index.html', '/js/app.js', '/css/style.css', '/data/status.json', '/site.webmanifest'):
            response = client.get(path)
            self.assertEqual(response.status_code, 200, path)
            response.close()

    def test_utic_key_referer_is_only_sent_to_utic_hosts(self):
        seen = []

        def capture(url, headers, **_kwargs):
            seen.append(headers)
            raise RuntimeError('stop')

        client = server_app.app.test_client()
        with patch.dict(os.environ, {'UTIC_API_KEY': 'SECRETKEY'}), \
                patch.object(server_app, 'is_safe_proxy_target', return_value=True), \
                patch.object(server_app, 'fetch_upstream', side_effect=capture):
            client.get('/proxy?url=https://attacker.example/steal?x=utic.go.kr')
            client.get('/proxy?url=https://www.utic.go.kr/live.m3u8')

        self.assertNotIn('SECRETKEY', json.dumps(seen[0]))
        self.assertIn('key=SECRETKEY', seen[1]['Referer'])

    def test_redirect_hop_drops_utic_key_outside_utic(self):
        headers = {'Referer': f'{server_app.UTIC_GUIDE_REFERER}?key=SECRETKEY', 'User-Agent': 'x'}
        foreign = server_app.headers_for_redirect_hop(headers, 'https://cdn.example/live.m3u8')
        self.assertEqual(foreign['Referer'], server_app.UTIC_GUIDE_REFERER)
        self.assertIs(server_app.headers_for_redirect_hop(headers, 'https://www.utic.go.kr/a'), headers)

    def test_log_text_redacts_keys_in_exception_messages(self):
        text = server_app.redact_text_for_log(
            "Max retries exceeded with url: /jsp/map/x.jsp?key=SECRETKEY&cctvid=L1"
        )
        self.assertNotIn('SECRETKEY', text)
        self.assertIn('cctvid=L1', text)

    def test_dynamic_providers_reject_foreign_or_private_urls(self):
        client = server_app.app.test_client()
        with patch.object(server_app.requests, 'get', side_effect=AssertionError('must not fetch')):
            for path in (
                '/skyline?url=http://169.254.169.254/latest/meta-data/',
                '/whatsupcam?url=http://127.0.0.1:8080/health',
                '/whatsupcam?slug=../../admin',
                '/roundshot?url=https://attacker.example/page',
                '/kb?cctvip=1%26cctvIp%3D2',
                '/daejeon?id=CCTV08/../../x',
            ):
                self.assertEqual(client.get(path).status_code, 400, path)

    def test_provider_fetch_does_not_follow_redirects_off_domain(self):
        class Redirect:
            is_redirect = True
            headers = {'Location': 'http://169.254.169.254/latest/meta-data/'}

            def close(self):
                pass

        with patch.object(server_app, '_resolve_host_ips', return_value=('93.184.216.34',)), \
                patch.object(server_app.requests, 'get', return_value=Redirect()) as get:
            with self.assertRaises(ValueError):
                server_app.fetch_provider_page(
                    'https://www.skylinewebcams.com/en/webcam.html', server_app.SKYLINE_DOMAINS, {}, 5
                )
        self.assertEqual(get.call_count, 1)

    def test_roundshot_only_redirects_to_roundshot_images(self):
        class Page:
            status_code = 200
            is_redirect = False

            def __init__(self, image):
                self.text = f'<meta property="og:image" content="{image}">'

        client = server_app.app.test_client()
        source = '/roundshot?url=https://zermatt.roundshot.com/blauherd'
        with patch.object(server_app, '_resolve_host_ips', return_value=('93.184.216.34',)):
            with patch.object(server_app.requests, 'get', return_value=Page('/cams/2091')):
                response = client.get(source)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers['Location'], 'https://zermatt.roundshot.com/cams/2091')
            with patch.object(server_app.requests, 'get', return_value=Page('https://attacker.example/x.jpg')):
                self.assertEqual(client.get(source).status_code, 502)

    def _stale_z3_state(self):
        saved = {key: value for key, value in server_app._z3_cache.items() if key != 'lock'}
        self.addCleanup(server_app._z3_cache.update, saved)
        server_app.set_z3_cache_data(
            {'E1': 'https://cctvsec.ktict.co.kr/E1/old'}, 'github-stale',
            server_app.parse_z3_fetched('2026-09-07T12:01:51Z'),
        )
        server_app._z3_cache['fetched'] = server_app.utc_now() - timedelta(hours=1)
        server_app._z3_cache['last_attempt'] = None
        server_app._z3_cache['last_forced_attempt'] = None

    def test_failed_z3_refresh_is_not_retried_by_every_request(self):
        self._stale_z3_state()
        with patch.object(server_app, 'load_z3_cache_payload', return_value=(None, None)), \
                patch.object(server_app.requests, 'get', side_effect=requests.ConnectionError('github down')), \
                patch.object(server_app, '_refresh_z3_from_its', return_value=False) as its_refresh:
            for _ in range(5):
                self.assertEqual(server_app.get_z3_app_url('E1'), 'https://cctvsec.ktict.co.kr/E1/old')
        self.assertEqual(its_refresh.call_count, 1)

    def test_z3_lookup_does_not_wait_for_in_flight_refresh(self):
        self._stale_z3_state()
        lock = server_app._z3_cache['lock']
        lock.acquire()  # another request is mid-refresh
        try:
            with patch.object(server_app, '_refresh_z3_cache', side_effect=AssertionError('must not refresh')):
                self.assertEqual(server_app.get_z3_app_url('E1'), 'https://cctvsec.ktict.co.kr/E1/old')
        finally:
            lock.release()

    def test_expired_z3_tokens_force_one_its_refresh_per_window(self):
        self._stale_z3_state()
        with patch.object(server_app, '_refresh_z3_from_its', return_value=False) as its_refresh:
            for _ in range(4):
                response, refreshed = server_app.retry_z3_with_fresh_cache(
                    'E1', 'NTIC_1', 'HTTP 403', 'https://cctvsec.ktict.co.kr/E1/old'
                )
                self.assertIsNone(response)
                self.assertFalse(refreshed)
        self.assertEqual(its_refresh.call_count, 1)

    def test_newer_stale_local_z3_cache_replaces_older_memory(self):
        self._stale_z3_state()
        newer = server_app.parse_z3_fetched('2026-09-20T00:00:00Z')
        with patch.object(server_app, 'load_z3_cache_payload',
                          return_value=({'E1': 'https://cctvsec.ktict.co.kr/E1/newer'}, newer)), \
                patch.object(server_app.requests, 'get', side_effect=requests.ConnectionError('github down')), \
                patch.object(server_app, '_refresh_z3_from_its', return_value=False):
            self.assertEqual(server_app.get_z3_app_url('E1'), 'https://cctvsec.ktict.co.kr/E1/newer')

    def test_rate_limit_separates_clients_behind_local_proxy(self):
        original_limit = server_app.RATE_LIMIT_PROXY_MAX_REQUESTS
        server_app.RATE_LIMIT_PROXY_MAX_REQUESTS = 1
        self.addCleanup(setattr, server_app, 'RATE_LIMIT_PROXY_MAX_REQUESTS', original_limit)
        client = server_app.app.test_client()
        via_caddy = lambda ip: {'X-Forwarded-For': ip}  # noqa: E731 - test client peer is 127.0.0.1
        self.assertEqual(client.get('/proxy', headers=via_caddy('198.51.100.1')).status_code, 400)
        self.assertEqual(client.get('/proxy', headers=via_caddy('198.51.100.2')).status_code, 400)
        self.assertEqual(client.get('/proxy', headers=via_caddy('198.51.100.1')).status_code, 429)

    def test_rate_limit_ignores_forwarded_header_from_direct_clients(self):
        original_limit = server_app.RATE_LIMIT_PROXY_MAX_REQUESTS
        server_app.RATE_LIMIT_PROXY_MAX_REQUESTS = 1
        self.addCleanup(setattr, server_app, 'RATE_LIMIT_PROXY_MAX_REQUESTS', original_limit)
        client = server_app.app.test_client()
        direct = {'REMOTE_ADDR': '203.0.113.9'}
        self.assertEqual(client.get('/proxy', headers={'X-Forwarded-For': '1.1.1.1'}, environ_base=direct).status_code, 400)
        self.assertEqual(client.get('/proxy', headers={'X-Forwarded-For': '2.2.2.2'}, environ_base=direct).status_code, 429)

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
