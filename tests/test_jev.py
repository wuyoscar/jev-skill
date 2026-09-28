import contextlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
import socket
import ssl
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/jev/scripts"))
import jev


def request(kind="choice"):
    question = {"type": kind, "instructions": "Judge the evidence."}
    if kind == "choice":
        question["criteria"] = {"continue": "Enough evidence", "review": "Unclear"}
    elif kind == "score":
        question["criteria"] = ["Low", "Medium", "High"]
    return {"model": jev.DEFAULT_MODEL, "state": {"evidence": "Synthetic"}, "questions": {"q": question}}


def choice(label="continue", probability=0.95):
    return {"answers": {"q": {"type": "choice", "choice": label,
                              "probabilities": {"continue": probability, "review": 1 - probability},
                              "confidence": 0.01}}, "usage": {"cost": 0.001}}


class RequestTests(unittest.TestCase):
    def test_all_types(self):
        for kind in ["choice", "score", "noul"]:
            self.assertEqual(jev.validate_request(request(kind)), request(kind))

    def test_noul_criteria(self):
        value = request("noul")
        value["questions"]["q"]["criteria"] = {"true": "Established", "false": "Not established"}
        jev.validate_request(value)
        value["questions"]["q"]["criteria"].pop("false")
        with self.assertRaises(jev.JevError):
            jev.validate_request(value)

    def test_reject_bad_requests(self):
        for payload in [[], {}, {**request(), "messages": []}, {**request(), "questions": {}},
                        {**request(), "state": None}, {**request(), "state": True},
                        {**request(), "state": 42}, {**request(), "model": ""}]:
            with self.subTest(payload=payload), self.assertRaises(jev.JevError):
                jev.validate_request(payload)
        for kind, criteria in [("choice", []), ("choice", {"one": "only"}),
                               ("score", ["one"]), ("score", list(range(11))),
                               ("noul", None), ("text", {}), ("score", [1, 2]),
                               ("choice", {"a": 1, "b": 2})]:
            payload = request()
            payload["questions"]["q"].update(type=kind, criteria=criteria)
            with self.subTest(kind=kind), self.assertRaises(jev.JevError):
                jev.validate_request(payload)

    def test_nonfinite_json(self):
        for value in ["NaN", "Infinity", "-Infinity"]:
            with self.assertRaises(jev.JevError):
                jev.load_json('{"value":' + value + '}')

    def test_assets_valid(self):
        assets = Path(__file__).resolve().parents[1] / "skills/jev/assets"
        for path in assets.glob("*.json"):
            payload = json.loads(path.read_text())
            if "questions" in payload:
                with self.subTest(path=path.name):
                    jev.validate_request({"model": jev.DEFAULT_MODEL, **payload})


class ReportTests(unittest.TestCase):
    def test_uses_probability_not_api_confidence(self):
        report = jev.build_report(request(), choice())
        self.assertEqual(report["decisions"]["q"]["status"], "selected")
        self.assertFalse(report["policy"]["executes_actions"])
        self.assertEqual(report["response"]["usage"]["cost"], 0.001)

    def test_abstains_when_unclear(self):
        for response in [choice(probability=0.6), choice("review", 0.01), choice(probability=0.5)]:
            self.assertEqual(jev.build_report(request(), response)["decisions"]["q"]["status"], "needs_review")

    def test_margin(self):
        self.assertEqual(jev.build_report(request(), choice(probability=0.8), min_margin=0.7)
                         ["decisions"]["q"]["status"], "needs_review")

    def test_bad_response(self):
        for response in [{}, {"answers": {}}, {"answers": {"q": {"type": "score"}}},
                         choice("missing"), choice(probability=float("nan")), choice(probability=True),
                         choice(probability=1.5), choice("review", 0.99)]:
            with self.subTest(response=response), self.assertRaises(jev.JevError):
                jev.build_report(request(), response)

    def test_missing_distribution_label(self):
        response = choice()
        response["answers"]["q"]["probabilities"].pop("review")
        with self.assertRaises(jev.JevError):
            jev.build_report(request(), response)

    def test_invalid_distribution_not_selected(self):
        response = choice()
        response["answers"]["q"]["probabilities"] = {"continue": 1, "review": 0.5}
        with self.assertRaises(jev.JevError):
            jev.build_report(request(), response)

    def test_defer_needs_review(self):
        payload = request()
        payload["questions"]["q"]["criteria"] = {"work": "Work", "defer": "Not enough evidence"}
        response = {"answers": {"q": {"type": "choice", "choice": "defer",
                    "probabilities": {"work": 0, "defer": 1}, "confidence": 1}}}
        self.assertEqual(jev.build_report(payload, response)["decisions"]["q"]["status"], "needs_review")

    def test_large_candidate_set_cannot_hide_invalid_distribution(self):
        payload = request()
        payload["questions"]["q"]["criteria"] = {f"c{i}": "Candidate" for i in range(255)}
        response = {"answers": {"q": {"type": "choice", "choice": "c0", "confidence": 1,
                    "probabilities": {f"c{i}": 1 if i == 0 else 0.004 for i in range(255)}}}}
        with self.assertRaises(jev.JevError):
            jev.build_report(payload, response)

    def test_noul_true_false_and_uncertain(self):
        for probability, value, status in [(0.98, True, "selected"), (0.02, False, "selected"),
                                           (0.5, False, "needs_review"), (0.7, True, "needs_review")]:
            result = jev.build_report(request("noul"), {"answers": {"q": {"type": "noul", "noul": probability}}})
            self.assertEqual((result["decisions"]["q"]["value"], result["decisions"]["q"]["status"]), (value, status))

    def test_score_not_probability(self):
        def response(score):
            return {"answers": {"q": {"type": "score", "score": score,
                    "probabilities": {"0": 0, "1": 0.25, "2": 0.75},
                    "legend": {"0": "Low", "1": "Medium", "2": "High"}, "confidence": 0.5}}}
        result = jev.build_report(request("score"), response(1.75))
        self.assertEqual(result["decisions"]["q"], {"status": "scored", "value": 1.75, "levels": ["Low", "Medium", "High"]})
        for score in [True, -1, 3, float("inf")]:
            with self.assertRaises(jev.JevError):
                jev.build_report(request("score"), response(score))
        with self.assertRaises(jev.JevError):
            jev.build_report(request("score"), {"answers": {"q": {"type": "score", "score": 1}}})


class TransportTests(unittest.TestCase):
    def test_local_socket_timeouts_distinguish_headers_and_body(self):
        release = threading.Event()

        class StalledResponse(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                if self.path == '/body':
                    self.send_response(200)
                    self.send_header('Content-Length', '2')
                    self.end_headers()
                    self.wfile.flush()
                release.wait(2)

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), StalledResponse)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            for suffix, phase, status in [('headers', 'connect_or_headers', None),
                                          ('body', 'response_body', 200)]:
                url = f'http://127.0.0.1:{server.server_port}/{suffix}'
                with self.subTest(phase=phase), patch.object(jev, 'DECISIONS_URL', url), \
                        patch.dict(os.environ, {'OPENROUTER_API_KEY':'local-only-dummy'}):
                    with self.assertRaises(jev.JevError) as raised:
                        jev.request_decisions(request(), timeout=0.1)
                    self.assertEqual(raised.exception.error_kind, 'timeout')
                    self.assertEqual(raised.exception.phase, phase)
                    self.assertEqual(raised.exception.http_status, status)
        finally:
            release.set()
            server.shutdown()
            server.server_close()
            worker.join()

    def test_transport_failure_keeps_safe_kind_and_phase(self):
        failures = [
            (TimeoutError("private-detail"), "timeout"),
            (urllib.error.URLError(TimeoutError("private-detail")), "timeout"),
            (urllib.error.URLError(socket.gaierror(-2, "private-detail")), "dns"),
            (urllib.error.URLError(ssl.SSLError("private-detail")), "tls"),
            (ConnectionRefusedError("private-detail"), "connection"),
        ]
        for failure, kind in failures:
            with self.subTest(kind=kind), patch.dict(os.environ, {"OPENROUTER_API_KEY": "secret-test"}), \
                    patch("jev.urllib.request.build_opener") as opener:
                opener.return_value.open.side_effect = failure
                with self.assertRaises(jev.JevError) as raised:
                    jev.request_decisions(request())
                self.assertEqual(raised.exception.error_kind, kind)
                self.assertEqual(raised.exception.phase, "connect_or_headers")
                self.assertIsNone(raised.exception.http_status)
                self.assertNotIn("private-detail", str(raised.exception))
                self.assertNotIn("secret-test", str(raised.exception))
                opener.return_value.open.assert_called_once()

    def test_body_timeout_keeps_received_http_status(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "secret-test"}), \
                patch("jev.urllib.request.build_opener") as opener:
            response = opener.return_value.open.return_value.__enter__.return_value
            response.status = 200
            response.read.side_effect = TimeoutError("private-detail")
            with self.assertRaises(jev.JevError) as raised:
                jev.request_decisions(request())
            self.assertEqual(raised.exception.error_kind, "timeout")
            self.assertEqual(raised.exception.phase, "response_body")
            self.assertEqual(raised.exception.http_status, 200)
            self.assertNotIn("private-detail", str(raised.exception))
            opener.return_value.open.assert_called_once()

    def test_malformed_key_is_rejected_without_leaking_it(self):
        for key in ["secret-first\nsecret-second", "secret\rheader", "secret key", "secret-密钥"]:
            with patch.dict(os.environ, {"OPENROUTER_API_KEY": key}), patch("jev.urllib.request.build_opener") as opener:
                with self.assertRaises(jev.JevError) as error:
                    jev.request_decisions(request())
                self.assertNotIn("secret", str(error.exception))
                opener.assert_not_called()

    def test_missing_key_before_network(self):
        with patch.dict(os.environ, {}, clear=True), patch("jev.urllib.request.build_opener") as opener:
            with self.assertRaises(jev.JevError):
                jev.request_decisions(request())
            opener.assert_not_called()

    def test_refuses_other_endpoints_and_redirects(self):
        with self.assertRaises(jev.JevError):
            jev.http_json("https://untrusted.example/", request())
        self.assertIsNone(jev.NoRedirect().redirect_request(None, None, 302, "", {}, "https://untrusted.example/"))

    def test_correct_endpoint_auth_and_no_retries(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "secret-test"}), patch("jev.urllib.request.build_opener") as opener:
            response = opener.return_value.open.return_value.__enter__.return_value
            response.read.return_value = json.dumps(choice()).encode()
            jev.request_decisions(request())
            sent = opener.return_value.open.call_args.args[0]
            self.assertEqual(sent.full_url, jev.DECISIONS_URL)
            self.assertEqual(sent.get_header("Authorization"), "Bearer secret-test")
            self.assertEqual(json.loads(sent.data), request())
            opener.return_value.open.assert_called_once()

    def test_error_does_not_print_provider_body_or_key(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "secret-test"}), patch("jev.urllib.request.build_opener") as opener:
            opener.return_value.open.side_effect = urllib.error.HTTPError(
                jev.DECISIONS_URL, 429, "secret-test", {}, io.BytesIO(b"private-record"))
            with self.assertRaisesRegex(jev.JevError, "HTTP 429") as error:
                jev.request_decisions(request())
            self.assertNotIn("secret-test", str(error.exception))
            self.assertNotIn("private-record", str(error.exception))
            self.assertEqual(error.exception.http_status, 429)
            opener.return_value.open.assert_called_once()


class BochaProviderTests(unittest.TestCase):
    def test_unknown_provider_is_rejected(self):
        with self.assertRaises(jev.JevError):
            jev.request_decisions(request("noul"), provider="untrusted")

    def test_bocha_uses_documented_endpoint_and_primary_key(self):
        response = {"answers": {"q": {"type": "noul", "noul": 0.97}}}
        with patch.dict(os.environ, {"BOCHA_JEV_API_KEY": "bocha-secret"}, clear=True), \
                patch("jev.urllib.request.build_opener") as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value = json.dumps(response).encode()
            self.assertEqual(jev.request_decisions(request("noul"), provider="bocha"), response)
            sent = opener.return_value.open.call_args.args[0]
            self.assertEqual(sent.full_url, jev.BOCHA_URL)
            self.assertEqual(sent.get_header("Authorization"), "Bearer bocha-secret")
            opener.return_value.open.assert_called_once()

    def test_bocha_falls_back_to_bocha_search_key(self):
        with patch.dict(os.environ, {"BOCHA_SEARCH_API_KEY": "search-secret"}, clear=True), \
                patch("jev.urllib.request.build_opener") as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value = b'{"answers":{}}'
            jev.request_decisions(request("noul"), provider="bocha")
            sent = opener.return_value.open.call_args.args[0]
            self.assertEqual(sent.full_url, jev.BOCHA_URL)
            self.assertEqual(sent.get_header("Authorization"), "Bearer search-secret")
            opener.return_value.open.assert_called_once()

    def test_bocha_other_provider_keys_are_not_used(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "or-secret", "TYPESAFE_API_KEY": "ts-secret"}, clear=True), \
                patch("jev.urllib.request.build_opener") as opener:
            with self.assertRaisesRegex(jev.JevError, "BOCHA_JEV_API_KEY"):
                jev.request_decisions(request("noul"), provider="bocha")
            opener.assert_not_called()

    def test_bocha_rejects_malformed_key_without_network(self):
        with patch.dict(os.environ, {"BOCHA_JEV_API_KEY": "secret-key\nsecret-header"}, clear=True), \
                patch("jev.urllib.request.build_opener") as opener:
            with self.assertRaises(jev.JevError) as error:
                jev.request_decisions(request("noul"), provider="bocha")
            self.assertNotIn("secret", str(error.exception))
            opener.assert_not_called()

    def test_setup_report_lists_bocha_availability(self):
        for env, expected in [({}, False), ({"BOCHA_SEARCH_API_KEY": "search-secret"}, True),
                              ({"BOCHA_JEV_API_KEY": "bocha-secret"}, True)]:
            with self.subTest(env=env), patch.dict(os.environ, env, clear=True):
                report = jev.setup_report()
            self.assertEqual(report["available"]["bocha"], expected)
            self.assertFalse(report["available"]["openrouter"])
            self.assertFalse(report["available"]["typesafe"])

    def test_bocha_dry_run_maps_bundled_models_only(self):
        payload = {"state": "fixture", "questions": {
            "q": {"type": "noul", "instructions": "Judge this fixture."}}}
        for model_id, expected in [(None, "bocha-jev-v1"), (jev.DEFAULT_MODEL, "bocha-jev-v1"),
                                   (jev.TYPESAFE_MODEL, "bocha-jev-v1"), ("bocha-jev-latest", "bocha-jev-latest")]:
            body = json.dumps(payload if model_id is None else {**payload, "model": model_id})
            output = io.StringIO()
            with self.subTest(model=model_id), patch.dict(os.environ, {}, clear=True), \
                    patch("sys.stdin", io.StringIO(body)), patch("jev.request_decisions") as network, \
                    contextlib.redirect_stdout(output):
                self.assertEqual(jev.main(["decide", "-", "--provider", "bocha", "--dry-run"]), 0)
                network.assert_not_called()
            self.assertEqual(json.loads(output.getvalue())["model"], expected)
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), \
                patch("sys.stdin", io.StringIO(json.dumps({**payload, "model": jev.DEFAULT_MODEL}))), \
                patch("jev.request_decisions") as network, contextlib.redirect_stdout(output):
            self.assertEqual(jev.main(["decide", "-", "--provider", "bocha", "--dry-run",
                                       "--model", "jev-latest"]), 0)
            network.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["model"], "jev-latest")

    def test_bocha_cli_full_mock_response_reports_transport(self):
        payload = {"model": jev.DEFAULT_MODEL, "state": "我的订单被重复扣款，请退还多收的费用。", "questions": {
            "refund": {"type": "noul", "instructions": "客户是否要求退款？"}}}
        response = {"model": "bocha-jev-v1", "answers": {"refund": {"type": "noul", "noul": 0.99}},
                    "usage": {"input_tokens": 12, "output_tokens": 0}, "metadata": {"inference_ms": 8}}
        output = io.StringIO()
        with patch.dict(os.environ, {"BOCHA_JEV_API_KEY": "bocha-secret"}, clear=True), \
                patch("sys.stdin", io.StringIO(json.dumps(payload))), \
                patch("jev.urllib.request.build_opener") as opener, contextlib.redirect_stdout(output):
            opener.return_value.open.return_value.__enter__.return_value.read.return_value = json.dumps(response).encode()
            self.assertEqual(jev.main(["decide", "-", "--provider", "bocha"]), 0)
            sent = opener.return_value.open.call_args.args[0]
            self.assertEqual(sent.full_url, jev.BOCHA_URL)
            self.assertEqual(json.loads(sent.data)["model"], jev.BOCHA_MODEL)
        result = json.loads(output.getvalue())
        self.assertEqual(result["transport"], "bocha")
        self.assertEqual(result["decisions"]["refund"],
                         {"status": "selected", "value": True, "probability": 0.99})
        self.assertEqual(result["response"], response)
        self.assertNotIn("bocha-secret", output.getvalue())


class CLITests(unittest.TestCase):
    def test_huge_integer_field_is_a_validation_error(self):
        with self.assertRaises(jev.JevError):
            jev.number(10**400, 0, 1, 'probability')

    def test_overflow_json_number_is_rejected(self):
        with self.assertRaises(jev.JevError):
            jev.load_json('{"usage":{"cost":1e999}}')

    @unittest.skipUnless(hasattr(sys, "set_int_max_str_digits"),
                         "Python has no integer-string conversion limit")
    def test_oversized_json_integer_returns_cli_error(self):
        self.addCleanup(sys.set_int_max_str_digits, sys.get_int_max_str_digits())
        sys.set_int_max_str_digits(4300)
        payload = request()
        payload["state"] = {"count": "oversized"}
        raw = json.dumps(payload).replace('"oversized"', '9' * 5000)
        output, errors = io.StringIO(), io.StringIO()
        with patch("sys.stdin", io.StringIO(raw)), patch("jev.request_decisions") as api, \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = jev.main(["decide", "-"])
        self.assertEqual(code, 1)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(json.loads(errors.getvalue()),
                         {"error": "JSON integer exceeds supported range"})
        api.assert_not_called()

    def test_duplicate_json_fields_are_rejected(self):
        with self.assertRaises(jev.JevError):
            jev.load_json('{"model":"first","model":"second"}')


    def test_incomplete_http_body_is_safe_json_error(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "secret-test"}), \
                patch("jev.urllib.request.build_opener") as opener:
            response = opener.return_value.open.return_value.__enter__.return_value
            response.status = 200
            response.read.side_effect = http.client.IncompleteRead(b"private body", 5)
            code, output, errors = self.call(["decide", "-"], request())
            self.assertEqual(code, 1)
            self.assertEqual(output, "")
            detail = json.loads(errors)
            self.assertEqual(detail['error_kind'], 'connection')
            self.assertEqual(detail['phase'], 'response_body')
            self.assertEqual(detail['http_status'], 200)
            self.assertNotIn('private body', errors)


    def test_timeout_diagnostic_reaches_cli_json(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "secret-test"}), \
                patch("jev.urllib.request.build_opener") as opener:
            opener.return_value.open.side_effect = TimeoutError("private-detail")
            code, output, errors = self.call(["decide", "-"], request())
            self.assertEqual(code, 1)
            self.assertEqual(output, "")
            detail = json.loads(errors)
            self.assertEqual(detail['error_kind'], 'timeout')
            self.assertEqual(detail['phase'], 'connect_or_headers')
            self.assertIsNone(detail['http_status'])
            self.assertNotIn('private-detail', errors)
            self.assertNotIn('secret-test', errors)
            opener.return_value.open.assert_called_once()

    def test_usage_error_is_not_review_exit(self):
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors), self.assertRaises(SystemExit) as stopped:
            jev.main(["decide"])
        self.assertEqual(stopped.exception.code, 1)
        self.assertIn("error", json.loads(errors.getvalue()))

    def call(self, args, payload):
        output, errors = io.StringIO(), io.StringIO()
        with patch("sys.stdin", io.StringIO(json.dumps(payload))), contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = jev.main(args)
        return code, output.getvalue(), errors.getvalue()

    def test_dry_run_never_calls_network(self):
        with patch("jev.request_decisions") as api:
            code, output, _ = self.call(["decide", "-", "--dry-run"], request())
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output), request())
            api.assert_not_called()

    def test_missing_key_does_not_simulate_decisions(self):
        for environment in ({}, {"OPENROUTER_API_KEY": ""}):
            with self.subTest(environment=environment), \
                    patch.dict(os.environ, environment, clear=True), \
                    patch("jev.urllib.request.build_opener") as opener:
                code, output, errors = self.call(["decide", "-"], request())
                self.assertEqual(code, 1)
                self.assertEqual(output, "")
                self.assertIn("OPENROUTER_API_KEY", json.loads(errors)["error"])
                opener.assert_not_called()

    def test_bad_threshold_no_spend(self):
        with patch("jev.request_decisions") as api:
            code, _, _ = self.call(["decide", "-", "--min-probability", "nan"], request())
            self.assertEqual(code, 1)
            api.assert_not_called()

    def test_exit_review(self):
        with patch("jev.request_decisions", return_value=choice(probability=0.6)):
            code, output, _ = self.call(["decide", "-"], request())
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(output)["decisions"]["q"]["status"], "needs_review")

    def test_empty_request(self):
        code, output, errors = self.call(["decide", "-"], [])
        self.assertEqual(code, 1)
        self.assertEqual(output, "")
        self.assertIn("error", json.loads(errors))


if __name__ == "__main__":
    unittest.main()
