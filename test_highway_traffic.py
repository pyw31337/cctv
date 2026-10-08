"""Fixture-based tests for highway traffic / ITS parsing (no live calls).

Fixtures follow the samples in NomaDamas/k-skill
highway-traffic-status/tests/test_highway_traffic.py (MIT License).
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import highway_traffic as ht

os.environ.setdefault('CCTV_DISABLE_STARTUP_JOBS', '1')

try:
    import server.app as server_app
except ImportError:  # Keep the data-only suite usable without server extras.
    server_app = None


TRAFFIC_PAYLOAD = {
    "count": 3,
    "list": [
        {"routeName": "경부선", "routeNo": "0010", "conzoneName": "구서IC-영락IC", "conzoneId": "0010CZE010",
         "updownTypeCode": "E", "speed": "89", "trafficAmout": "20", "grade": "1",
         "stdDate": "20260721", "stdHour": "1530", "timeAvg": "73"},
        {"routeName": "경부선", "routeNo": "0010", "conzoneName": "서울TG-양재IC", "conzoneId": "0010CZE900",
         "updownTypeCode": "S", "speed": "35", "trafficAmout": "88", "grade": "3",
         "stdDate": "20260721", "stdHour": "1530", "timeAvg": "140"},
        {"routeName": "서해안선", "routeNo": "0150", "conzoneName": "매송IC-비봉IC", "conzoneId": "0150CZE010",
         "updownTypeCode": "S", "speed": "97", "trafficAmout": "12", "grade": "1",
         "stdDate": "20260721", "stdHour": "1530", "timeAvg": "60"},
    ],
}

EXDATA_KEY_ERROR = {"count": 0, "list": None, "message": "인증키가 유효하지 않습니다.", "code": "ERROR"}

CCTV_XML = """<?xml version='1.0' encoding='UTF-8'?>
<response>
    <coordtype>1</coordtype>
    <datacount>2</datacount>
    <data>
        <cctvtype>1</cctvtype>
        <cctvurl>http://cctvsec.example/stream1</cctvurl>
        <coordy>37.42889</coordy>
        <cctvformat>HLS</cctvformat>
        <cctvname>[수도권제1순환선] 성남</cctvname>
        <coordx>127.12361</coordx>
    </data>
    <data>
        <cctvtype>1</cctvtype>
        <cctvurl>http://cctvsec.example/stream2</cctvurl>
        <coordy>37.5</coordy>
        <cctvformat>HLS</cctvformat>
        <cctvname>[경부선] 서울TG</cctvname>
        <coordx>127.0</coordx>
    </data>
</response>
"""

ITS_KEY_ERROR = json.dumps({"header": {"resultCode": 4005, "resultMsg": "존재하지 않는 인증키입니다."}, "body": ""})


class ItsParsingTests(unittest.TestCase):
    def test_xml_success_is_parsed_first(self):
        items = ht.parse_its_cctv_response(CCTV_XML, 200)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[1]["cctvname"], "[경부선] 서울TG")
        self.assertEqual(items[0]["coordx"], "127.12361")
        self.assertEqual(items[0]["cctvformat"], "HLS")

    def test_empty_xml_response_is_not_an_error(self):
        self.assertEqual(ht.parse_its_cctv_response("<response><datacount>0</datacount></response>", 200), [])

    def test_legacy_json_success_still_supported(self):
        body = json.dumps({"response": {"data": [{"cctvname": "a", "cctvurl": "u", "coordx": "127", "coordy": "37"}]}})
        self.assertEqual(len(ht.parse_its_cctv_response(body, 200)), 1)

    def test_http_401_is_key_problem(self):
        with self.assertRaises(ht.KeyProblemError) as ctx:
            ht.parse_its_cctv_response(ITS_KEY_ERROR, 401)
        self.assertIn("4005", str(ctx.exception))

    def test_result_code_4005_without_401_is_key_problem(self):
        with self.assertRaises(ht.KeyProblemError):
            ht.parse_its_cctv_response(ITS_KEY_ERROR, 200)

    def test_html_block_page_is_upstream_error_not_key_problem(self):
        with self.assertRaises(ht.UpstreamError) as ctx:
            ht.parse_its_cctv_response("<html>blocked</html>", 200)
        self.assertNotIsInstance(ctx.exception, ht.KeyProblemError)

    def test_garbage_is_upstream_error(self):
        with self.assertRaises(ht.UpstreamError):
            ht.parse_its_cctv_response("Service Unavailable", 200)


class ExdataTrafficTests(unittest.TestCase):
    def test_url_uses_demo_key_and_json(self):
        url = ht.build_exdata_traffic_url("")
        self.assertIn("data.ex.co.kr/openapi/odtraffic/trafficAmountByRealtime", url)
        self.assertIn("key=test", url)
        self.assertIn("type=json", url)

    def test_key_error_payload_is_key_problem(self):
        with self.assertRaises(ht.KeyProblemError):
            ht.check_exdata_payload(EXDATA_KEY_ERROR)

    def test_other_error_payload_is_upstream_error(self):
        with self.assertRaises(ht.UpstreamError) as ctx:
            ht.check_exdata_payload({"code": "ERROR", "message": "점검 중"})
        self.assertNotIsInstance(ctx.exception, ht.KeyProblemError)

    def test_sections_are_normalized(self):
        sections = ht.normalize_exdata_traffic(TRAFFIC_PAYLOAD["list"])
        jam = sections[1]
        self.assertEqual(jam["routeName"], "경부선")
        self.assertEqual(jam["conzoneId"], "0010CZE900")
        self.assertEqual(jam["conzoneName"], "서울TG-양재IC")
        self.assertEqual(jam["grade"], 3)
        self.assertEqual(jam["congestion"], "정체")
        self.assertEqual(jam["speed"], 35)
        self.assertEqual(jam["observed_at"], "2026-07-21T15:30:00+09:00")
        # Raw code only; no unverified 상행/하행 label.
        self.assertEqual(jam["directionCode"], "S")
        self.assertNotIn("direction", jam)

    def test_route_summary_marks_congested_route(self):
        snapshot = ht.build_traffic_snapshot(TRAFFIC_PAYLOAD["list"], fetched_at="2026-07-21T06:31:00Z", demo_key=True)
        routes = {route["routeName"]: route for route in snapshot["routes"]}
        self.assertEqual(routes["경부선"]["grade"], 3)
        self.assertEqual(routes["경부선"]["congestedSections"], 1)
        self.assertEqual(routes["경부선"]["avgSpeed"], 62)
        self.assertEqual(routes["서해안선"]["congestion"], "원활")
        self.assertEqual(snapshot["routes"][0]["routeName"], "경부선")
        self.assertEqual(snapshot["observed_at"], "2026-07-21T15:30:00+09:00")
        self.assertTrue(snapshot["demo_key"])

    def test_bad_values_do_not_crash(self):
        sections = ht.normalize_exdata_traffic([{"grade": "9", "speed": "-", "stdDate": "x"}, "junk"])
        self.assertEqual(len(sections), 1)
        self.assertIsNone(sections[0]["grade"])
        self.assertIsNone(sections[0]["speed"])
        self.assertIsNone(sections[0]["observed_at"])


    def test_detector_rows_collapse_to_worst_reading_per_conzone(self):
        rows = [
            {"routeName": "경부선", "routeNo": "0010", "conzoneId": "C1", "conzoneName": "A-B", "updownTypeCode": "E",
             "grade": "1", "speed": "90", "stdDate": "20260721", "stdHour": "1525"},
            {"routeName": "경부선", "routeNo": "0010", "conzoneId": "C1", "conzoneName": "A-B", "updownTypeCode": "E",
             "grade": "3", "speed": "22", "stdDate": "20260721", "stdHour": "1520"},
            {"routeName": "경부선", "routeNo": "0010", "conzoneId": "C1", "conzoneName": "A-B", "updownTypeCode": "S",
             "grade": "2", "speed": "50", "stdDate": "20260721", "stdHour": "1530"},
            {"routeName": "경부선", "routeNo": "0010", "conzoneId": "C1", "conzoneName": "A-B", "updownTypeCode": "E",
             "grade": "", "speed": "-1", "stdDate": "20260721", "stdHour": "1530"},
        ]
        snapshot = ht.build_traffic_snapshot(rows, fetched_at="x", demo_key=True)
        self.assertEqual(len(snapshot["sections"]), 2)
        east = next(s for s in snapshot["sections"] if s["directionCode"] == "E")
        self.assertEqual((east["grade"], east["speed"]), (3, 22))
        self.assertEqual(east["observed_at"], "2026-07-21T15:30:00+09:00")
        self.assertEqual(snapshot["routes"][0]["sections"], 2)


class KeyResolutionTests(unittest.TestCase):
    def test_missing_env_falls_back_to_demo_key_with_warning(self):
        messages = []
        with patch.dict(os.environ, {"ITS_API_KEY": ""}):
            key, is_demo = ht.resolve_api_key("ITS_API_KEY", demo_key="test", label="ITS", log=messages.append)
        self.assertEqual((key, is_demo), ("test", True))
        self.assertTrue(messages and "demo key" in messages[0])

    def test_env_key_wins(self):
        with patch.dict(os.environ, {"ITS_API_KEY": " real-key "}):
            self.assertEqual(ht.resolve_api_key("ITS_API_KEY", demo_key="test", label="ITS"), ("real-key", False))


class FakeResponse:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text


class CollectorTests(unittest.TestCase):
    def setUp(self):
        import collect_cctv_data

        self.collector = collect_cctv_data
        self.collector.SOURCE_ISSUES.clear()

    def tearDown(self):
        self.collector.SOURCE_ISSUES.clear()

    def test_fetch_its_parses_xml_with_demo_key(self):
        seen = {}

        def fake_get(url, params=None, timeout=None):
            seen.update(params)
            return FakeResponse(200, CCTV_XML)

        with patch.dict(os.environ, {"ITS_API_KEY": ""}), patch.object(self.collector.requests, "get", side_effect=fake_get):
            items = self.collector.fetch_its_data()
        self.assertEqual(seen["apiKey"], "test")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["source"], "NTIC")
        self.assertTrue(items[0]["url"].startswith("http://cctvsec.example/"))
        categories = [issue["category"] for issue in self.collector.SOURCE_ISSUES]
        self.assertEqual(categories, ["key_problem"])  # demo-key warning only
        self.assertEqual(self.collector.SOURCE_ISSUES[0]["status"], "warning")

    def test_fetch_its_records_key_problem_on_401(self):
        with patch.dict(os.environ, {"ITS_API_KEY": "revoked"}), patch.object(
            self.collector.requests, "get", return_value=FakeResponse(401, ITS_KEY_ERROR)
        ):
            self.assertEqual(self.collector.fetch_its_data(), [])
        self.assertEqual(len(self.collector.SOURCE_ISSUES), 1)
        issue = self.collector.SOURCE_ISSUES[0]
        self.assertEqual((issue["category"], issue["status"]), ("key_problem", "error"))
        self.assertNotIn("revoked", issue["message"])

    def test_missing_utic_key_is_recorded(self):
        with patch.dict(os.environ, {"UTIC_API_KEY": "", "UTIC_KEY": ""}), patch.object(self.collector.requests, "get") as get:
            self.assertEqual(self.collector.fetch_utic_data(), [])
        get.assert_not_called()
        self.assertEqual(self.collector.SOURCE_ISSUES[0]["source"], "UTIC")
        self.assertEqual(self.collector.SOURCE_ISSUES[0]["category"], "key_problem")

    def test_issues_are_written_to_workflow_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "workflow_status.json"
            count = self.collector.report_source_issues(
                [{"source": "ITS", "message": "ITS_API_KEY rejected", "category": "key_problem", "status": "error"}],
                output=output,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(count, 1)
        event = payload["events"][-1]
        self.assertEqual(event["workflow"], "Update CCTV Data")
        self.assertEqual(event["category"], "key_problem")
        self.assertIn("인증키 문제", event["message"])
        self.assertEqual(payload["summary"]["key_problem_events"], 1)


@unittest.skipUnless(server_app is not None, 'server runtime dependencies are not installed')
class HighwayTrafficEndpointTests(unittest.TestCase):
    def setUp(self):
        server_app.rate_limit_buckets.clear()
        cache = server_app._highway_traffic_cache
        cache.update({'snapshot': None, 'fetched_mono': None, 'last_attempt': None, 'last_error': None, 'preferred_route': None})

    def _json_response(self, payload, status=200):
        class Response:
            status_code = status

            def json(self_inner):
                return payload

        return Response()

    def test_endpoint_returns_normalized_snapshot_and_caches(self):
        with patch.object(server_app.requests, 'get', return_value=self._json_response(TRAFFIC_PAYLOAD)) as get:
            client = server_app.app.test_client()
            first = client.get('/highway-traffic')
            second = client.get('/highway-traffic')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(get.call_count, 1)  # second request served from cache
        body = first.get_json()
        self.assertTrue(body['ok'])
        self.assertFalse(body['stale'])
        self.assertEqual(body['observed_at'], '2026-07-21T15:30:00+09:00')
        section = body['sections'][1]
        for key in ('routeName', 'conzoneId', 'conzoneName', 'grade', 'congestion', 'speed', 'observed_at'):
            self.assertIn(key, section)
        self.assertEqual(second.get_json()['sections'], body['sections'])

    def test_serves_last_good_snapshot_when_upstream_fails(self):
        client = server_app.app.test_client()
        with patch.object(server_app.requests, 'get', return_value=self._json_response(TRAFFIC_PAYLOAD)):
            self.assertEqual(client.get('/highway-traffic').status_code, 200)
        cache = server_app._highway_traffic_cache
        cache['fetched_mono'] -= server_app.HIGHWAY_TRAFFIC_TTL_SECONDS + 1
        cache['last_attempt'] -= server_app.HIGHWAY_TRAFFIC_RETRY_SECONDS + 1
        with patch.object(server_app.requests, 'get', side_effect=server_app.requests.ConnectionError('key=secret reset')):
            response = client.get('/highway-traffic')
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body['stale'])
        self.assertEqual(body['error'], 'upstream_unreachable')
        self.assertEqual(len(body['sections']), 3)

    def test_key_problem_without_snapshot_is_503(self):
        with patch.object(server_app.requests, 'get', return_value=self._json_response(EXDATA_KEY_ERROR)):
            response = server_app.app.test_client().get('/highway-traffic')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()['error'], 'key_problem')

    def test_failed_attempt_is_not_retried_inside_retry_window(self):
        client = server_app.app.test_client()
        with patch.object(server_app.requests, 'get', side_effect=server_app.requests.Timeout('slow')) as get:
            self.assertEqual(client.get('/highway-traffic').status_code, 503)
            self.assertEqual(client.get('/highway-traffic').status_code, 503)
        self.assertEqual(get.call_count, 3)  # direct + 2 relays once, then retry window

    def test_relays_are_used_when_direct_route_is_unreachable(self):
        calls = []
        oracle_prefix = server_app.PUBLIC_PROXY_BASE.rstrip('/') + '/proxy?url='
        worker_prefix = server_app.WORKER_PROXY_BASE.rstrip('/') + '/proxy?url='

        def fake_get(url, **kwargs):
            calls.append(url)
            if url.startswith(ht.EXDATA_TRAFFIC_URL):
                raise server_app.requests.ConnectTimeout('key=test geo-blocked')
            if url.startswith(oracle_prefix):
                return self._json_response(None, status=502)
            return self._json_response(TRAFFIC_PAYLOAD)

        client = server_app.app.test_client()
        with patch.object(server_app.requests, 'get', side_effect=fake_get):
            response = client.get('/highway-traffic')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['ok'])
        self.assertEqual(len(calls), 3)
        self.assertTrue(calls[1].startswith(oracle_prefix))
        self.assertTrue(calls[2].startswith(worker_prefix))
        self.assertIn('data.ex.co.kr', server_app.unquote(calls[2]))
        self.assertEqual(server_app._highway_traffic_cache['preferred_route'], 'worker')

        # The next refresh goes to the route that worked last time first.
        cache = server_app._highway_traffic_cache
        cache['fetched_mono'] -= server_app.HIGHWAY_TRAFFIC_TTL_SECONDS + 1
        cache['last_attempt'] -= server_app.HIGHWAY_TRAFFIC_RETRY_SECONDS + 1
        calls.clear()
        with patch.object(server_app.requests, 'get', side_effect=fake_get):
            self.assertEqual(client.get('/highway-traffic').status_code, 200)
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0].startswith(worker_prefix))

    def test_oracle_relay_is_tried_before_worker(self):
        calls = []

        def fake_get(url, **kwargs):
            calls.append(url)
            if url.startswith(ht.EXDATA_TRAFFIC_URL):
                raise server_app.requests.ConnectTimeout('blocked')
            return self._json_response(TRAFFIC_PAYLOAD)

        with patch.object(server_app.requests, 'get', side_effect=fake_get):
            self.assertEqual(server_app.app.test_client().get('/highway-traffic').status_code, 200)
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[1].startswith(server_app.PUBLIC_PROXY_BASE.rstrip('/') + '/proxy?url='))
        self.assertEqual(server_app._highway_traffic_cache['preferred_route'], 'oracle')

    def test_relay_error_page_falls_back_to_other_routes(self):
        server_app._highway_traffic_cache['preferred_route'] = 'worker'

        def fake_get(url, **kwargs):
            if url.startswith(server_app.WORKER_PROXY_BASE.rstrip('/')):
                return self._json_response(None, status=522)
            return self._json_response(TRAFFIC_PAYLOAD)

        with patch.object(server_app.requests, 'get', side_effect=fake_get) as get:
            response = server_app.app.test_client().get('/highway-traffic')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(server_app._highway_traffic_cache['preferred_route'], 'direct')

    def test_key_problem_is_not_retried_through_relay(self):
        with patch.object(server_app.requests, 'get', return_value=self._json_response(None, status=401)) as get:
            response = server_app.app.test_client().get('/highway-traffic')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()['error'], 'key_problem')
        self.assertEqual(get.call_count, 1)

    def test_snapshot_is_gzipped_for_clients_that_accept_it(self):
        with patch.object(server_app.requests, 'get', return_value=self._json_response(TRAFFIC_PAYLOAD)):
            response = server_app.app.test_client().get('/highway-traffic', headers={'Accept-Encoding': 'gzip, br'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('Content-Encoding'), 'gzip')
        import gzip as _gzip
        body = json.loads(_gzip.decompress(response.data).decode('utf-8'))
        self.assertTrue(body['ok'])

    def test_endpoint_is_rate_limited(self):
        self.assertIn('/highway-traffic', server_app.RATE_LIMITED_PATHS)
        original = server_app.RATE_LIMIT_MAX_REQUESTS
        server_app.RATE_LIMIT_MAX_REQUESTS = 1
        try:
            with patch.object(server_app.requests, 'get', return_value=self._json_response(TRAFFIC_PAYLOAD)):
                client = server_app.app.test_client()
                self.assertEqual(client.get('/highway-traffic').status_code, 200)
                self.assertEqual(client.get('/highway-traffic').status_code, 429)
        finally:
            server_app.RATE_LIMIT_MAX_REQUESTS = original


if __name__ == '__main__':
    unittest.main()
