"""檢查更新：只比對版本並提醒，不下載、不自動覆蓋。只有使用者按下選單時才會連網。"""
import json
import urllib.error
import urllib.request

REPO = "AIXAI-tools/AIXAI-zoom-breakout-helper"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"


def _parse(version):
    """'v1.2.3' → (1, 2, 3)；無法解析的部分視為 0。"""
    nums = []
    for part in version.lstrip("vV").split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        nums.append(int(digits) if digits else 0)
    return tuple(nums)


def check(current, timeout=8):
    """回傳 {"status": "new" | "latest" | "none", "tag", "url"}；網路錯誤會丟出例外。
    none = 專案還沒發布過任何版本。"""
    req = urllib.request.Request(API, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "AIXAI-zoom-breakout-helper"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"status": "none", "tag": "", "url": RELEASES_PAGE}
        raise
    tag = data.get("tag_name", "")
    newer = _parse(tag) > _parse(current)
    return {"status": "new" if newer else "latest", "tag": tag, "url": data.get("html_url") or RELEASES_PAGE}
