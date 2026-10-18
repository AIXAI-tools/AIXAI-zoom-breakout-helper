"""畫面操作模組：建房、改名、結束後的畫面檢查。

建房方式（BUILD_MODES）與分配方式（ASSIGN_MODES）是登錄表，
之後要加新方式，只要在表裡多一列並寫對應函式。
"""
import ctypes
import time

import pyautogui
import pyperclip
from PIL import Image, ImageChops, ImageStat

from . import store

pyautogui.PAUSE = 0.02  # 每個動作之間的預設停頓，越小越快
VK_ESC = 0x1B

ASSIGN_MODES = {  # key: (顯示名稱, 校準點 key)
    "auto": ("自動指派", "radio_auto"),
    "manual": ("手動指派", "radio_manual"),
    "allow": ("允許與會者選擇", "radio_allow"),
}
BUILD_MODES = {  # key: (顯示名稱, 說明, 是否建房, 是否改名)
    "create_rename": ("建房＋改名", "先開啟「建立分組討論室」視窗再執行", True, True),
    "rename_only": ("只改名", "房間已存在，依清單從第 1 間開始改名", False, True),
    "create_only": ("只建房", "先開啟「建立分組討論室」視窗再執行", True, False),
}

ANCHOR_SIZE = (120, 32)
ANCHOR_PATH = store.DATA_DIR / "anchor.png"
ANCHOR_TOLERANCE = 25  # 平均色差（0~255），超過視為畫面異常


class Aborted(Exception):
    pass


def key_down(vk):
    return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)


def _check_abort():
    if key_down(VK_ESC):
        raise Aborted()


# ---- 影像輔助 ----
def sample_color(pos):
    return list(pyautogui.pixel(*pos))


def _anchor_region(pos):
    w, h = ANCHOR_SIZE
    return (max(pos[0] - w // 2, 0), max(pos[1] - h // 2, 0), w, h)


def save_anchor(pos):
    pyautogui.screenshot(region=_anchor_region(pos)).save(ANCHOR_PATH)


def anchor_matches(pos):
    """目前畫面在錨點位置的樣子，與校準時是否相近。"""
    if not ANCHOR_PATH.exists():
        return True
    ref = Image.open(ANCHOR_PATH).convert("RGB")
    now = pyautogui.screenshot(region=_anchor_region(pos)).convert("RGB")
    if ref.size != now.size:
        return False
    diff = ImageChops.difference(ref, now)
    return sum(ImageStat.Stat(diff).mean) / 3 <= ANCHOR_TOLERANCE


def find_blue(center, blue, half_w=80, up=250, down=250, tol=40, min_pixels=300):
    """在 center 附近找藍色按鈕（「是」），回傳中心座標；找不到回傳 None。"""
    if not blue:
        return None
    sw, sh = pyautogui.size()
    left, top = max(center[0] - half_w, 0), max(center[1] - up, 0)
    right, bottom = min(center[0] + half_w, sw), min(center[1] + down, sh)
    img = pyautogui.screenshot(region=(left, top, right - left, bottom - top)).convert("RGB")
    px, (w, h) = img.load(), img.size
    xs = ys = n = 0
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r, g, b = px[x, y]
            if abs(r - blue[0]) < tol and abs(g - blue[1]) < tol and abs(b - blue[2]) < tol:
                xs += x
                ys += y
                n += 1
    if n * 4 < min_pixels:
        return None
    return (left + xs // n, top + ys // n)


# ---- 建房 ----
def create_rooms(p, count, assign, status):
    radio_key = ASSIGN_MODES[assign][1]
    for k in ("count", "create", radio_key):
        if k not in p:
            raise RuntimeError(f"尚未校準「{k}」，請從校準選單補校準")
    time.sleep(0.5)
    pyautogui.click(*p["count"])
    pyautogui.hotkey("ctrl", "a")
    pyautogui.write(str(count))
    pyautogui.click(*p[radio_key])
    pyautogui.click(*p["create"])
    status(f"已建立 {count} 間")
    time.sleep(1.5)  # 等房間列表出現


# ---- 改名 ----
def rename_all(p, names, delay, blue, status):
    """依清單改名。回傳 {"done", "skipped", "dialog_stuck"}。"""
    for k in ("row1", "rename", "yes", "row2"):
        if k not in p:
            raise RuntimeError(f"尚未校準「{k}」，請從校準選單補校準")
    row1, rename, yes, row2 = p["row1"], p["rename"], p["yes"], p["row2"]
    dy = row2[1] - row1[1]
    off = (rename[0] - row1[0], rename[1] - row1[1])
    yes_off = (yes[0] - rename[0], yes[1] - rename[1])
    n = len(names)
    ys = [row1[1] + dy * i for i in range(n)]
    screen_h = pyautogui.size()[1]
    todo = [i for i in range(n) if ys[i] < screen_h - 20]
    skipped = [i for i in range(n) if i not in todo]  # 超出螢幕下緣的房間不處理

    done = 0
    last_click = None

    def one(i, y):
        nonlocal done, last_click
        _check_abort()
        x = row1[0]
        pyautogui.moveTo(x, y)  # 先 hover，「改名」才會浮現
        time.sleep(delay["hover"])
        rx, ry = x + off[0], y + off[1]
        pyautogui.click(rx, ry)
        time.sleep(delay["dialog"])  # 等改名視窗出現
        pyperclip.copy(names[i])
        pyautogui.hotkey("ctrl", "a")
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.05)
        guess = (rx + yes_off[0], ry + yes_off[1])
        target = find_blue(guess, blue) or guess  # 改名視窗若翻到上方，用顏色找「是」
        pyautogui.click(*target)
        time.sleep(delay["after"])
        last_click = guess
        done += 1
        status(f"已改名 {done}/{n}：{names[i]}")

    time.sleep(0.5)
    for i in todo:
        one(i, ys[i])
    stuck = bool(last_click and blue and find_blue(last_click, blue))
    return {"done": done, "skipped": skipped, "dialog_stuck": stuck}


def verify_end(p, result):
    """結束後檢查畫面是否正常，回傳問題清單（空表示正常）。"""
    problems = []
    if result.get("dialog_stuck"):
        problems.append("改名視窗似乎還開著")
    if "anchor" in p and not anchor_matches(p["anchor"]):
        problems.append("畫面不像已建立好的分組討論室")
    return problems


def record_usage(entry):
    store.log_usage(entry)
