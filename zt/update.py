"""檢查更新與自動更新。只在使用者按下選單、並再次確認後才連網下載。

流程（exe 單檔版）：查最新 Release → 使用者確認 → 下載 exe → 核對 SHA256 →
把正在執行的自己改名為 .old（Windows 不能覆蓋執行中的 exe，但可以改名）→ 新檔就位 → 自動重啟。
原始碼版或資料夾不可寫入時，只開啟下載頁面。
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = "AIXAI-tools/AIXAI-zoom-breakout-helper"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
ISSUES_URL = f"https://github.com/{REPO}/issues/new/choose"
ASSET_NAME = "AIXAI-zoom-breakout-helper.exe"
ALLOWED_HOSTS = ("github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com")
USER_AGENT = "AIXAI-zoom-breakout-helper-updater"
TEST_API_ENV = "AIXAI_UPDATE_API"  # 僅供測試：指向本機假伺服器（此時允許 127.0.0.1 的 http）
MAX_SIZE = 200 << 20  # 下載上限 200 MB，避免被導向到異常大的檔案


class UpdateError(Exception):
    """更新失敗，訊息已是使用者看得懂的中文。"""


def _parse(version):
    """'v1.2.3' → (1, 2, 3)；無法解析的部分視為 0。"""
    nums = []
    for part in version.lstrip("vV").split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        nums.append(int(digits) if digits else 0)
    return tuple(nums)


def _testing():
    return bool(os.environ.get(TEST_API_ENV))


def url_allowed(url):
    """下載網址必須是 GitHub 的 https（測試模式才允許本機）。"""
    u = urllib.parse.urlparse(url)
    if _testing() and u.scheme == "http" and u.hostname == "127.0.0.1":
        return True
    return u.scheme == "https" and u.hostname in ALLOWED_HOSTS


def check(current, timeout=8):
    """回傳 {"status": "new" | "latest" | "none", "tag", "url", "asset_url", "size", "sha256"}；
    網路錯誤會丟出例外。none = 專案還沒發布過任何版本。"""
    req = urllib.request.Request(os.environ.get(TEST_API_ENV) or API,
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"status": "none", "tag": "", "url": RELEASES_PAGE}
        raise
    tag = data.get("tag_name", "")
    info = {"status": "new" if _parse(tag) > _parse(current) else "latest", "tag": tag,
            "url": data.get("html_url") or RELEASES_PAGE, "asset_url": "", "size": 0, "sha256": ""}
    asset = next((a for a in data.get("assets", []) if a.get("name") == ASSET_NAME), None)
    if asset:
        info["asset_url"], info["size"] = asset.get("browser_download_url", ""), int(asset.get("size") or 0)
        digest = (asset.get("digest") or "").removeprefix("sha256:").lower()
        in_body = re.search(r"\b[0-9a-f]{64}\b", (data.get("body") or "").lower())
        body_hash = in_body.group(0) if in_body else ""
        if digest and body_hash and digest != body_hash:
            raise UpdateError("Release 內記載的兩個 SHA256 不一致，為安全起見不更新。")
        info["sha256"] = digest or body_hash
    return info


def exe_path():
    return Path(sys.executable)


def can_self_update():
    """只有打包成 exe、且 exe 所在資料夾可寫入時才能自動更新。"""
    return bool(getattr(sys, "frozen", False)) and os.access(exe_path().parent, os.W_OK)


def download_verified(info, dest, progress=None, timeout=30):
    """下載到 dest 並核對 SHA256；任何不符都會刪掉下載的暫存檔並丟 UpdateError。"""
    url, want = info.get("asset_url", ""), info.get("sha256", "")
    if not url or not want:
        raise UpdateError("這個版本沒有提供可自動下載的檔案或 SHA256，請改到下載頁手動更新。")
    if not url_allowed(url):
        raise UpdateError("下載網址不在允許的 GitHub 網域內，為安全起見不更新。")
    dest = Path(dest)
    h, total = hashlib.sha256(), 0
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r, open(dest, "wb") as f:
            if not url_allowed(r.geturl()):  # 轉址後的最終網址也要在允許範圍內
                raise UpdateError("下載被轉址到不允許的網域，為安全起見不更新。")
            size = int(r.headers.get("Content-Length") or info.get("size") or 0)
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_SIZE:
                    raise UpdateError("下載檔案異常地大，已中止。")
                h.update(chunk)
                f.write(chunk)
                if progress and size:
                    progress(min(total * 100 // size, 100))
        if info.get("size") and total != info["size"]:
            raise UpdateError("下載的檔案大小與 Release 記載不符。")
        if h.hexdigest() != want.lower():
            raise UpdateError("下載檔案的 SHA256 與 Release 記載不符，已中止，原程式沒有被改動。")
    except UpdateError:
        _discard(dest)
        raise
    except OSError as e:
        _discard(dest)
        raise UpdateError(f"下載失敗：{e}") from e


def _discard(path):
    try:
        Path(path).unlink()
    except OSError:
        pass


def apply_update(new_path, exe=None):
    """把 new_path 換成正在執行的 exe：目前的 exe 先改名成 .old，再把新檔改名就位；失敗會還原。"""
    exe = Path(exe) if exe else exe_path()
    old = exe.with_name(exe.name + ".old")
    _discard(old)  # 上一次更新留下的
    os.replace(exe, old)
    try:
        os.replace(new_path, exe)
    except OSError as e:
        os.replace(old, exe)  # 還原，原程式完好
        raise UpdateError(f"替換檔案失敗，已還原：{e}") from e


def restart_command(exe):
    """重啟用的命令列（字串）。刻意用單一字串交給 Windows：用清單形式的話，Python 會把內層引號
    加上反斜線跳脫，`start "" "路徑"` 會被拆壞（Windows 會說找不到 '\'）。
    用 ping 當 2 秒延遲：背景（無主控台）程序裡 timeout 指令會直接失敗。"""
    return f'cmd.exe /c ping -n 3 127.0.0.1 >nul & start "" "{exe}"'


def restart(exe=None):
    """約 2 秒後以全新的程序啟動 exe（等目前這個程序先結束）。
    PYINSTALLER_RESET_ENVIRONMENT=1：讓單檔 exe 的新程序不要沿用目前程序的暫存解壓資料夾。"""
    exe = Path(exe) if exe else exe_path()
    env = {**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"}
    flags = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED_PROCESS | NEW_PROCESS_GROUP | NO_WINDOW
    subprocess.Popen(restart_command(exe), env=env, creationflags=flags, close_fds=True)


def cleanup_old():
    """啟動時清掉上次更新留下的 .old（正在執行的 exe 無法被刪，但新啟動時舊程序已結束）。"""
    if getattr(sys, "frozen", False):
        _discard(exe_path().with_name(exe_path().name + ".old"))
