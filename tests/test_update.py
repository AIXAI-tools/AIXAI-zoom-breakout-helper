"""更新機制測試：用本機假 GitHub 驗證版本比對、雜湊核對、網域白名單與替換還原。
執行：python -m unittest discover -s tests"""
import hashlib
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from zt import update  # noqa: E402

PAYLOAD = b"MZ-fake-new-exe-" * 4096


def serve(release):
    """release：/api 回傳的 JSON（dict）；/asset.exe 回傳 PAYLOAD。"""
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path == "/api":
                raw, ctype = json.dumps(release).encode("utf-8"), "application/json"
            else:
                raw, ctype = PAYLOAD, "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"


def release_json(base, tag="v9.0.0", digest=None, body_hash=None, size=len(PAYLOAD)):
    h = hashlib.sha256(PAYLOAD).hexdigest()
    asset = {"name": update.ASSET_NAME, "browser_download_url": f"{base}/asset.exe", "size": size}
    if digest != "":
        asset["digest"] = f"sha256:{digest or h}"
    return {"tag_name": tag, "html_url": f"{base}/page", "assets": [asset],
            "body": f"SHA256：\n```\n{body_hash or h}\n```\n"}


class Base(unittest.TestCase):
    def start(self, **kw):
        # 先建立伺服器取得 port，再把 asset 網址指回自己
        self.srv, base = serve({})
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)
        self.base = base
        self.srv.RequestHandlerClass  # 保持參考
        self.srv.release = release_json(base, **kw)
        # 重新綁定回應內容
        handler = self.srv.RequestHandlerClass
        rel = self.srv.release

        class H(handler):
            def do_GET(inner):
                if inner.path == "/api":
                    raw, ctype = json.dumps(rel).encode("utf-8"), "application/json"
                else:
                    raw, ctype = PAYLOAD, "application/octet-stream"
                inner.send_response(200)
                inner.send_header("Content-Type", ctype)
                inner.send_header("Content-Length", str(len(raw)))
                inner.end_headers()
                inner.wfile.write(raw)

        self.srv.RequestHandlerClass = H
        patcher = mock.patch.dict(os.environ, {update.TEST_API_ENV: f"{base}/api"})
        patcher.start()
        self.addCleanup(patcher.stop)


class CheckTests(Base):
    def test_new_version_has_asset_info(self):
        self.start(tag="v9.0.0")
        info = update.check("1.2.0")
        self.assertEqual(info["status"], "new")
        self.assertEqual(info["sha256"], hashlib.sha256(PAYLOAD).hexdigest())
        self.assertTrue(info["asset_url"].endswith("/asset.exe"))
        self.assertEqual(info["size"], len(PAYLOAD))

    def test_latest_when_same_version(self):
        self.start(tag="v1.2.0")
        self.assertEqual(update.check("1.2.0")["status"], "latest")

    def test_hash_from_body_when_no_digest(self):
        self.start(digest="")
        self.assertEqual(update.check("1.0.0")["sha256"], hashlib.sha256(PAYLOAD).hexdigest())

    def test_digest_and_body_mismatch_refuses(self):
        self.start(body_hash="0" * 64)
        with self.assertRaises(update.UpdateError):
            update.check("1.0.0")

    def test_version_compare(self):
        self.assertTrue(update._parse("v1.2.10") > update._parse("1.2.9"))
        self.assertFalse(update._parse("v1.0.0") > update._parse("1.0.0"))


class UrlTests(unittest.TestCase):
    def test_allowlist(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(update.TEST_API_ENV, None)
            ok = update.url_allowed
            self.assertTrue(ok("https://github.com/AIXAI-tools/x/releases/download/v1/x.exe"))
            self.assertTrue(ok("https://objects.githubusercontent.com/abc"))
            self.assertFalse(ok("https://evil.example.com/x.exe"))
            self.assertFalse(ok("http://github.com/x.exe"))              # 非 https
            self.assertFalse(ok("https://github.com.evil.com/x.exe"))     # 假冒網域
            self.assertFalse(ok("http://127.0.0.1:1/x.exe"))              # 非測試模式不允許本機

    def test_local_only_in_test_mode(self):
        with mock.patch.dict(os.environ, {update.TEST_API_ENV: "http://127.0.0.1:1/api"}):
            self.assertTrue(update.url_allowed("http://127.0.0.1:5/asset.exe"))
            self.assertFalse(update.url_allowed("http://example.com/asset.exe"))


class DownloadTests(Base):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dest = Path(self.tmp.name) / "new.download"

    def test_download_ok_reports_progress(self):
        self.start()
        seen = []
        update.download_verified(update.check("1.0.0"), self.dest, progress=seen.append)
        self.assertEqual(self.dest.read_bytes(), PAYLOAD)
        self.assertEqual(seen[-1], 100)

    def test_bad_hash_deletes_file_and_raises(self):
        self.start()
        info = update.check("1.0.0")
        info["sha256"] = "f" * 64
        with self.assertRaises(update.UpdateError):
            update.download_verified(info, self.dest)
        self.assertFalse(self.dest.exists())

    def test_size_mismatch_raises(self):
        self.start(size=123)
        with self.assertRaises(update.UpdateError):
            update.download_verified(update.check("1.0.0"), self.dest)
        self.assertFalse(self.dest.exists())

    def test_missing_hash_refuses_without_downloading(self):
        with self.assertRaises(update.UpdateError):
            update.download_verified({"asset_url": "https://github.com/x", "sha256": ""}, self.dest)

    def test_disallowed_host_refuses(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(update.TEST_API_ENV, None)
            with self.assertRaises(update.UpdateError):
                update.download_verified({"asset_url": "https://evil.example.com/a.exe", "sha256": "a" * 64}, self.dest)


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d = Path(self.tmp.name)
        self.exe, self.new = d / "app.exe", d / "app.exe.download"
        self.exe.write_bytes(b"old")

    def test_swap_keeps_old_copy(self):
        self.new.write_bytes(b"new")
        update.apply_update(self.new, self.exe)
        self.assertEqual(self.exe.read_bytes(), b"new")
        self.assertEqual(self.exe.with_name("app.exe.old").read_bytes(), b"old")
        self.assertFalse(self.new.exists())

    def test_failure_restores_original(self):
        # 新檔不存在 → 第二步改名失敗，原 exe 必須完好
        with self.assertRaises(update.UpdateError):
            update.apply_update(self.new, self.exe)
        self.assertEqual(self.exe.read_bytes(), b"old")

    def test_second_update_replaces_previous_old(self):
        self.exe.with_name("app.exe.old").write_bytes(b"ancient")
        self.new.write_bytes(b"new")
        update.apply_update(self.new, self.exe)
        self.assertEqual(self.exe.with_name("app.exe.old").read_bytes(), b"old")

    def test_restart_command_keeps_quotes_and_avoids_timeout(self):
        cmd = update.restart_command(Path(r"C:\Users\Tyler's OBS\a b\app.exe"))
        self.assertIn(' start "" "', cmd)            # 空標題與路徑都要保持原樣的雙引號
        self.assertNotIn('\\"', cmd)                 # 不能有被跳脫的引號（這就是先前的 bug）
        self.assertNotIn("timeout", cmd)             # 無主控台時 timeout 會失敗
        self.assertTrue(cmd.endswith('app.exe"'))

    def test_not_frozen_cannot_self_update(self):
        self.assertFalse(update.can_self_update())  # 原始碼執行時一定不是 frozen


if __name__ == "__main__":
    unittest.main()
