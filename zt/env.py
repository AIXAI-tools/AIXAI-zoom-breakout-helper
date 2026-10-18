"""環境偵測：Zoom 版本、螢幕解析度、縮放比例。"""
import ctypes
import os
from ctypes import wintypes
from pathlib import Path


class _FixedFileInfo(ctypes.Structure):
    _fields_ = [(n, wintypes.DWORD) for n in (
        "dwSignature", "dwStrucVersion", "dwFileVersionMS", "dwFileVersionLS",
        "dwProductVersionMS", "dwProductVersionLS", "dwFileFlagsMask", "dwFileFlags",
        "dwFileOS", "dwFileType", "dwFileSubtype", "dwFileDateMS", "dwFileDateLS")]


def _file_version(path):
    ver = ctypes.windll.version
    size = ver.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        return None
    buf = ctypes.create_string_buffer(size)
    if not ver.GetFileVersionInfoW(str(path), 0, size, buf):
        return None
    ptr, length = ctypes.c_void_p(), ctypes.c_uint()
    if not ver.VerQueryValueW(buf, "\\", ctypes.byref(ptr), ctypes.byref(length)):
        return None
    info = ctypes.cast(ptr, ctypes.POINTER(_FixedFileInfo)).contents
    ms, ls = info.dwFileVersionMS, info.dwFileVersionLS
    return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"


def zoom_version():
    candidates = [
        Path(os.environ.get("APPDATA", "")) / "Zoom" / "bin" / "Zoom.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Zoom" / "bin" / "Zoom.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Zoom" / "bin" / "Zoom.exe",
    ]
    for p in candidates:
        if p.exists():
            return _file_version(p) or "未知"
    return "找不到 Zoom"


def current_env():
    u = ctypes.windll.user32
    try:
        dpi = int(u.GetDpiForSystem())
    except Exception:
        dpi = 96
    return {"zoom_version": zoom_version(), "screen": [u.GetSystemMetrics(0), u.GetSystemMetrics(1)],
            "dpi": dpi}


LABELS = {"zoom_version": "Zoom 版本", "screen": "螢幕解析度", "dpi": "縮放 DPI"}


def diff(saved, now):
    """回傳人看得懂的差異清單；saved 為空表示舊校準沒有環境紀錄。"""
    if not saved:
        return ["舊校準沒有環境紀錄"]
    return [f"{LABELS[k]}：{saved.get(k)} → {now.get(k)}" for k in LABELS if saved.get(k) != now.get(k)]
