"""資料存取：清單（profile）、校準、設定、使用紀錄。

資料夾結構（都在專案根目錄下，可直接用檔案總管開啟）：
  清單/<名稱>.json     每個清單＝房名 + 建房方式 + 分配方式
  資料/calibration.json  校準座標 + 校準當時的環境（Zoom 版本、螢幕）
  資料/settings.json     等待時間、上次使用的清單、置頂
  資料/anchor.png        畫面錨點截圖（結束時比對用）
  紀錄/usage.jsonl       每次執行的紀錄
  紀錄/env_history.jsonl 環境變化紀錄
"""
import json
import re
import shutil
import sys
import time
from pathlib import Path

# 資料放在程式旁邊：原始碼版是專案資料夾，打包成 exe 後是 exe 所在資料夾（整包帶著走）
ROOT = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
PROFILE_DIR = ROOT / "清單"
DATA_DIR = ROOT / "資料"
LOG_DIR = ROOT / "紀錄"

DEFAULT_DELAY = {"hover": 0.12, "dialog": 0.3, "after": 0.15}
DEFAULT_SETTINGS = {"delay": DEFAULT_DELAY, "last_profile": "", "topmost": True}
DEFAULT_PROFILE = {"names": [], "mode": "create_rename", "assign": "allow"}


def _read(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_name(name):
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "未命名"


def init():
    for d in (PROFILE_DIR, DATA_DIR, LOG_DIR):
        d.mkdir(exist_ok=True)
    if not list_profiles():
        save_profile("範例", {**DEFAULT_PROFILE, "names": [f"第{n}組" for n in "一二三四五"]})


# ---- 清單 ----
def list_profiles():
    return sorted(p.stem for p in PROFILE_DIR.glob("*.json"))


def load_profile(name):
    d = _read(PROFILE_DIR / f"{_safe_name(name)}.json", {})
    return {**DEFAULT_PROFILE, **d}


def save_profile(name, data):
    _write(PROFILE_DIR / f"{_safe_name(name)}.json", data)


def archive_profile(name):
    """不直接刪除，改搬到 清單/_已移除/，需要時可自行還原。"""
    src = PROFILE_DIR / f"{_safe_name(name)}.json"
    if src.exists():
        dst_dir = PROFILE_DIR / "_已移除"
        dst_dir.mkdir(exist_ok=True)
        shutil.move(str(src), str(dst_dir / f"{src.stem}_{time.strftime('%Y%m%d_%H%M%S')}.json"))


# ---- 設定 / 校準 ----
def load_settings():
    st = _read(DATA_DIR / "settings.json", {})
    return {**DEFAULT_SETTINGS, **st, "delay": {**DEFAULT_DELAY, **st.get("delay", {})}}


def save_settings(st):
    _write(DATA_DIR / "settings.json", st)


def load_calibration():
    cal = _read(DATA_DIR / "calibration.json", {})
    return {"points": cal.get("points", {}), "env": cal.get("env", {}), "blue": cal.get("blue"),
            "captured_at": cal.get("captured_at", "")}


def save_calibration(cal):
    _write(DATA_DIR / "calibration.json", cal)


# ---- 紀錄 ----
def _append(path, entry):
    entry = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), **entry}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def log_usage(entry):
    _append(LOG_DIR / "usage.jsonl", entry)


def log_env(entry):
    _append(LOG_DIR / "env_history.jsonl", entry)
