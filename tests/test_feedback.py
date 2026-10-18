"""回報送出端測試：用本機假收件伺服器驗證協定行為。執行：python -m unittest discover -s tests"""
import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from zt import feedback  # noqa: E402


def serve(responses):
    """responses：依序處理每個 POST；每項 = ("redirect", json) | ("status", code) | ("json", obj)。"""
    log = []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8"))
            log.append(body)
            kind, val = responses[min(len(log), len(responses)) - 1]
            if kind == "status":
                self.send_response(val)
                self.end_headers()
            elif kind == "redirect":  # 模擬 Google Apps Script：302 轉址，結果用 GET 讀
                self.server.result = val
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/result")
                self.end_headers()
            else:
                self._json(val)

        def do_GET(self):
            self._json(self.server.result)

        def _json(self, obj):
            raw = json.dumps(obj).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}/exec", log


class SendTests(unittest.TestCase):
    def run_send(self, responses, **kw):
        srv, url, log = serve(responses)
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)  # 後註冊先執行：先停止服務，再關閉 socket
        try:
            feedback.send("標題", "內文", endpoint=url, retry_delay=0, timeout=3, **kw)
        finally:
            self.log = log

    def test_ok_follows_redirect_and_payload_fields(self):
        self.run_send([("redirect", {"ok": True})])
        self.assertEqual(len(self.log), 1)
        p = self.log[0]
        self.assertEqual((p["tool"], p["pass"], p["title"], p["body"]),
                         (feedback.TOOL, feedback.PASS, "標題", "內文"))
        self.assertEqual(len(p["id"]), 24)
        self.assertEqual(p["files"], [])

    def test_5xx_retries_with_same_id(self):
        self.run_send([("status", 503), ("redirect", {"ok": True})])
        self.assertEqual(len(self.log), 2)
        self.assertEqual(self.log[0]["id"], self.log[1]["id"])

    def test_relay_error_is_not_retried(self):
        with self.assertRaises(feedback.RelayError) as cm:
            self.run_send([("redirect", {"ok": False, "error": "daily_limit"})])
        self.assertEqual(cm.exception.code, "daily_limit")
        self.assertEqual(len(self.log), 1)
        self.assertIn("上限", feedback.ERROR_TEXT["daily_limit"])

    def test_gives_up_after_three_attempts(self):
        with self.assertRaises(feedback.RelayConnectionError):
            self.run_send([("status", 500)])
        self.assertEqual(len(self.log), 3)

    def test_unreachable_server(self):
        with self.assertRaises(feedback.RelayConnectionError):
            feedback.send("t", "b", endpoint="http://127.0.0.1:9/exec", retry_delay=0, timeout=1)


class BuildTests(unittest.TestCase):
    def test_title_from_first_line_and_masking(self):
        import os
        home = os.path.expanduser("~")
        title, body = feedback.build(f"第一行問題\n路徑 {home}/x", "a@b.c", with_diag=False)
        self.assertEqual(title, "第一行問題")
        self.assertNotIn(home, body)
        self.assertIn("%USERPROFILE%", body)
        self.assertIn("a@b.c", body)
        self.assertNotIn("診斷資訊", body)

    def test_diagnostics_excludes_profile_names(self):
        _, body = feedback.build("x", "", with_diag=True)
        self.assertIn("## 診斷資訊", body)
        self.assertIn("工具版本", body)
        self.assertNotIn("profile", body)

    def test_empty_contact_placeholder(self):
        _, body = feedback.build("x", "  ", with_diag=False)
        self.assertIn("（未提供）", body)


if __name__ == "__main__":
    unittest.main()
