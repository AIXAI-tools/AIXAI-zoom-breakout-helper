"""「直接送出」回報：把回報送到 feedback-relay 收件程式（協定見 feedback-relay/PROTOCOL.md）。

只用標準函式庫。收件服務偶爾卡住或直接斷線，所以每次嘗試各自逾時；
連線失敗或 HTTP 5xx 會用同一個回報 ID 重試（收件端同一個 ID 只收一次）；
收件端回的錯誤（例如 daily_limit）不重試。
"""
import json
import os
import platform
import secrets
import time
import urllib.error
import urllib.request

from . import __version__, env, store

ENDPOINT = "https://script.google.com/macros/s/AKfycbwwgrA7unx2l2cNDO9h8YLX74Nu4OX1099WJAD-0OPEhAz8llSV1PS3YYESMXEXecRJ7Q/exec"
TOOL = "AIXAI-zoom-breakout-helper"  # = GitHub repo 名
PASS = "aixai-zoom-breakout-helper-feedback-1"  # 工具識別碼（會公開在原始碼，用途是辨識與限流，不是機密）
USER_AGENT = f"AIXAI-zoom-breakout-helper/{__version__}"

ERROR_TEXT = {  # 收件端錯誤碼 → 使用者看得懂的中文
    "bad_request": "回報服務拒絕了這份回報（內容空白，或工具設定有誤）。",
    "too_many_files": "附件太多。",
    "bad_file_type": "附件格式不支援。",
    "too_large": "附件太大。",
    "daily_limit": "今天的回報量已達上限，請明天再試。",
    "busy": "回報服務目前忙碌，請稍後再試。",
}


class RelayError(Exception):
    """收件端拒絕：bad_request、too_many_files、bad_file_type、too_large、daily_limit、busy。"""

    def __init__(self, code):
        super().__init__(f"relay: {code}")
        self.code = code


class RelayConnectionError(Exception):
    """所有嘗試都連不到收件端。"""


def new_id():
    """一次按下「送出」的識別碼，重試時沿用。"""
    return secrets.token_hex(12)


def _mask(text):
    """遮蔽使用者資料夾路徑，避免洩漏電腦使用者名稱。"""
    home = os.path.expanduser("~")
    return text.replace(home, "%USERPROFILE%") if home else text


def _recent_usage(n=5):
    """最近 n 次執行結果。刻意不含清單名稱與房名（可能是個人內容）。"""
    path = store.LOG_DIR / "usage.jsonl"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-n:]
    except OSError:
        return []
    out = []
    for ln in lines:
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        probs = "；".join(d.get("problems", [])) or "無"
        out.append(f"{d.get('time', '?')}｜{d.get('mode', '?')}｜{d.get('rooms', '?')} 間｜"
                   f"{d.get('outcome', '?')}｜問題：{probs}")
    return out


def diagnostics():
    """診斷資訊（Markdown）。內容不含 Cookie、密碼、Token，也不含清單名稱。"""
    e = env.current_env()
    cal = store.load_calibration()
    done = len(cal["points"])
    lines = [f"- 工具版本：v{__version__}",
             f"- Zoom 版本：{e['zoom_version']}",
             f"- 螢幕：{e['screen'][0]}×{e['screen'][1]}，DPI {e['dpi']}",
             f"- 作業系統：{platform.platform()}",
             f"- 已校準項目：{done} 項（校準時間：{cal['captured_at'] or '無'}）"]
    recent = _recent_usage()
    if recent:
        lines.append("- 最近執行：")
        lines += [f"  - {r}" for r in recent]
    return _mask("\n".join(lines))


def build(description, contact, with_diag):
    """回傳 (標題, 內文)。內文就是會送出的完整內容，送出前要讓使用者看到。"""
    description, contact = _mask(description.strip()), _mask(contact.strip())
    title = (description.splitlines() or ["使用者回報"])[0][:40] or "使用者回報"
    parts = ["## 說明", description, "", "## 聯絡方式", contact or "（未提供）"]
    if with_diag:
        parts += ["", "## 診斷資訊", diagnostics()]
    return title, "\n".join(parts)


def send(title, body, endpoint=ENDPOINT, attempts=3, timeout=45, retry_delay=2):
    """送出一份回報。成功回傳 None；被拒絕丟 RelayError；連不上丟 RelayConnectionError。"""
    payload = json.dumps({"pass": PASS, "tool": TOOL, "id": new_id(), "title": title, "body": body,
                          "files": [], "want_reply": False}, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    last = None
    for attempt in range(attempts):
        if attempt:
            time.sleep(retry_delay)
        req = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")
        try:
            # 收件端以轉址回應；urllib 會自動以 GET 跟隨。
            with urllib.request.urlopen(req, timeout=timeout) as r:
                status, raw = r.status, r.read(64 << 10)
        except urllib.error.HTTPError as e:
            e.close()
            if e.code >= 500:
                last = e
                continue
            raise RelayConnectionError(f"非預期的回應（HTTP {e.code}）") from e
        except OSError as e:  # 逾時、斷線（含 RemoteDisconnected）、DNS
            last = e
            continue
        try:
            res = json.loads(raw.decode("utf-8"))
        except ValueError as e:
            raise RelayConnectionError(f"非預期的回應（HTTP {status}）") from e
        if not res.get("ok"):
            raise RelayError(str(res.get("error")))
        return
    raise RelayConnectionError(f"試了 {attempts} 次仍連不到回報服務：{last}")
