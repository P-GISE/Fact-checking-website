import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
import threading
import unittest


SCRIPT = Path(__file__).resolve().parents[3] / "devtools/check-web-security.py"
HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "no-store",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy":
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
}


class WebSecuritySmokeTests(unittest.TestCase):
    def run_smoke(self, statuses, expected_exit, mode=None, missing_header=None):
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append((self.path, self.headers.get("Origin")))
                self.send_response(statuses[self.path])
                for name, value in HEADERS.items():
                    if name != missing_header:
                        self.send_header(name, value)
                self.end_headers()

            def log_message(self, *args):
                pass

        with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
            thread.start()
            try:
                command = [
                    sys.executable, "-B", str(SCRIPT),
                    "--base-url", f"http://127.0.0.1:{server.server_port}",
                ]
                if mode is not None:
                    command.extend(["--auth-mode", mode])
                result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            finally:
                server.shutdown()
                thread.join()

        self.assertEqual(result.returncode, expected_exit, result.stdout + result.stderr)
        self.assertEqual(requests, [
            ("/api/health", None),
            ("/api/not-found", None),
            ("/api/media/not-an-id", None),
            ("/api/analyses", "https://untrusted.example"),
        ])
        report = json.loads(result.stdout)
        self.assertEqual(report["passed"], expected_exit == 0)
        self.assertEqual([check["status"] for check in report["checks"]], list(statuses.values()))
        return report

    def test_account_mode_accepts_401_for_both_protected_paths(self):
        report = self.run_smoke({
            "/api/health": 200, "/api/not-found": 401,
            "/api/media/not-an-id": 401, "/api/analyses": 403,
        }, 0, mode="account")
        self.assertTrue(all(check["passed"] for check in report["checks"]))

    def test_account_mode_rejects_unprotected_404_and_400(self):
        report = self.run_smoke({
            "/api/health": 200, "/api/not-found": 404,
            "/api/media/not-an-id": 400, "/api/analyses": 403,
        }, 1, mode="account")
        self.assertEqual([check["passed"] for check in report["checks"]], [True, False, False, True])
        self.assertEqual([check["expectedStatus"] for check in report["checks"]], [200, 401, 401, 403])
        self.assertTrue(all(not check["failedHeaders"] for check in report["checks"]))

    def test_local_mode_and_default_accept_original_404_and_400(self):
        for mode in (None, "local"):
            with self.subTest(mode=mode):
                report = self.run_smoke({
                    "/api/health": 200, "/api/not-found": 404,
                    "/api/media/not-an-id": 400, "/api/analyses": 403,
                }, 0, mode=mode)
                self.assertTrue(all(check["passed"] for check in report["checks"]))

    def test_missing_required_header_fails_in_both_modes(self):
        for mode, not_found, invalid_media in (("local", 404, 400), ("account", 401, 401)):
            for header in HEADERS:
                with self.subTest(mode=mode, header=header):
                    report = self.run_smoke({
                        "/api/health": 200, "/api/not-found": not_found,
                        "/api/media/not-an-id": invalid_media, "/api/analyses": 403,
                    }, 1, mode=mode, missing_header=header)
                    self.assertTrue(all(not check["passed"] for check in report["checks"]))
                    self.assertTrue(all(check["failedHeaders"] == [header] for check in report["checks"]))


if __name__ == "__main__":
    unittest.main()
