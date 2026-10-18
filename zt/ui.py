"""極簡視窗外框：取代 Windows 原生又大的標題列。

細標題列（整條都能拖曳）：左 ☰ 選單（選用）、中間標題、右 ▁ 收合、✕ 關閉。
右下角 ◢ 可拉大縮小。
"""
import ctypes
import ctypes.wintypes
import sys
import tkinter as tk
from pathlib import Path

BAR_BG, BAR_FG, BORDER = "#2b2b2b", "#eeeeee", "#777777"
FONT_FAMILY, FONT_SIZE = "Microsoft JhengHei", 10  # 全程式統一字型，只在這裡改
FONT = (FONT_FAMILY, FONT_SIZE)
SIZE_RATIO = 1 / 6  # 預設視窗大小 = 螢幕寬、高各 1/6
MIN_DEFAULT_H = 300  # 預設高度下限（像素）
BW = 6  # 邊框寬度（像素）；邊框本身就是四邊拖拉改大小的把手


def compact(win, title, on_close=None, menu=None, resizable=True, min_size=(200, 120)):
    """把 win 改成自製外框，回傳放內容用的 body Frame。
    回傳 (body, bar_widgets)；bar_widgets["menu_btn"] 可用來更新 ☰ 的文字。"""
    win.overrideredirect(True)
    win.configure(bg=BORDER)

    bar = tk.Frame(win, bg=BAR_BG)
    bar.pack(side="top", fill="x", padx=BW, pady=(BW, 0))
    body = tk.Frame(win)
    body.pack(side="top", fill="both", expand=True, padx=BW, pady=(0, BW))
    widgets = {}

    def label(text, **kw):
        return tk.Label(bar, text=text, bg=BAR_BG, fg=BAR_FG, font=FONT, **kw)

    if menu is not None:
        b = label(" ☰ ", cursor="hand2")
        b.pack(side="left")
        b.bind("<Button-1>", lambda e: menu.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height()))
        widgets["menu_btn"] = b
    ttl = label(title)
    ttl.pack(side="left", padx=4)
    close = label(" ✕ ", cursor="hand2")
    close.pack(side="right")
    close.bind("<Button-1>", lambda e: (on_close or win.destroy)())
    state = {"collapsed": False, "geo": None}
    fold = label(" ▁ ", cursor="hand2")
    fold.pack(side="right")

    def toggle(_e=None):
        if state["collapsed"]:
            body.pack(side="top", fill="both", expand=True, padx=BW, pady=(0, BW))
            win.geometry(state["geo"])
        else:
            state["geo"] = f"{win.winfo_width()}x{win.winfo_height()}"
            body.pack_forget()
            win.update_idletasks()
            win.geometry(f"{win.winfo_width()}x{bar.winfo_reqheight() + 2 * BW}")
        state["collapsed"] = not state["collapsed"]

    fold.bind("<Button-1>", toggle)

    # 整條標題列拖曳
    drag = {}

    def start(e):
        drag["dx"], drag["dy"] = e.x_root - win.winfo_x(), e.y_root - win.winfo_y()

    def move(e):
        win.geometry(f"+{e.x_root - drag['dx']}+{e.y_root - drag['dy']}")

    for w in (bar, ttl):
        w.bind("<Button-1>", start)
        w.bind("<B1-Motion>", move)

    if resizable:
        _edge_resize(win, min_size, state)
    return body, widgets


def resource_path(rel):
    """程式內附的資源路徑：打包成 exe 後在暫存解壓目錄，原始碼版在專案資料夾。"""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / rel


def apply_icon(root):
    """視窗與工作列 icon（default=True 讓之後開的子視窗也套用）。找不到檔案就略過。"""
    try:
        root.iconbitmap(default=str(resource_path("assets/icon.ico")))
    except tk.TclError:
        pass


def apply_fonts(root):
    """把 Tk 的所有預設字型（按鈕、輸入框、選單、下拉清單、表格）統一成 FONT。"""
    from tkinter import font as tkfont, ttk
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont",
                 "TkCaptionFont", "TkSmallCaptionFont", "TkIconFont", "TkTooltipFont"):
        tkfont.nametofont(name).configure(family=FONT_FAMILY, size=FONT_SIZE)
    tkfont.nametofont("TkFixedFont").configure(family=FONT_FAMILY, size=FONT_SIZE)
    root.option_add("*TCombobox*Listbox.font", FONT)
    ttk.Style(root).configure("Treeview", rowheight=int(FONT_SIZE * 2.4))


NO_LINE_START = "，。、；：！？」』）)】》,.;:!?"  # 這些符號不放在行首
CLAUSE_END = "，。；：、）」』】》"  # 優先在這些符號後面斷行
NO_LINE_END = "「『（(【《"  # 這些符號不放在行尾


def _can_break(a, b):
    """a、b 是相鄰兩字，能否在中間斷行。"""
    if b in NO_LINE_START or b == " " or a in NO_LINE_END:
        return False
    if a.isascii() and b.isascii() and a.isalnum() and b.isalnum():  # F8、Fn 這類英數不拆開
        return False
    return True


def wrap_text(text, width, font=FONT, bold=False):
    """依實際字寬斷行（Tk 自己只會在空白處換行，中文整串會斷得很怪）。
    保留原有的換行；標點不落在行首、開括號不落在行尾、英數字不拆開。"""
    from tkinter import font as tkfont
    f = tkfont.Font(font=font + (("bold",) if bold else ()))
    out = []
    for para in text.split("\n"):
        line = ""
        for ch in para:
            if line and f.measure(line + ch) > width:
                nxt = line + ch
                ok = [i for i in range(len(line), 0, -1) if _can_break(nxt[i - 1], nxt[i])]
                # 優先在子句標點後斷（語意完整），沒有合適的才在字與字之間斷
                clause = [i for i in ok if nxt[i - 1] in CLAUSE_END and i >= len(line) // 2]
                k = (clause or ok or [len(line)])[0]
                out.append(line[:k].rstrip())
                line = line[k:].lstrip()
            line += ch
        out.append(line)
    return "\n".join(out)


def work_area():
    """螢幕可用範圍（扣掉工作列）：(left, top, right, bottom)。"""
    r = ctypes.wintypes.RECT()
    ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(r), 0)  # SPI_GETWORKAREA
    return r.left, r.top, r.right, r.bottom


def default_geometry(min_w=0, min_h=0, margin=12):
    """預設大小為螢幕 1/6（不小於內容所需的 min_w × min_h），放在可用範圍的右下角。"""
    left, top, right, bottom = work_area()
    w = max(int(ctypes.windll.user32.GetSystemMetrics(0) * SIZE_RATIO), min_w)
    h = max(int(ctypes.windll.user32.GetSystemMetrics(1) * SIZE_RATIO), min_h, MIN_DEFAULT_H)
    return f"{w}x{h}+{right - w - margin}+{bottom - h - margin}"


def place(win, x, y, margin=12):
    """把 win 放在 (x, y)，但保證整個視窗都在螢幕可用範圍內，不會跑出螢幕。"""
    win.update_idletasks()
    left, top, right, bottom = work_area()
    w, h = win.winfo_reqwidth(), win.winfo_reqheight()
    x = min(max(x, left + margin), right - w - margin)
    y = min(max(y, top + margin), bottom - h - margin)
    win.geometry(f"+{x}+{y}")


def place_top_right(win, margin=12):
    left, top, right, bottom = work_area()
    place(win, right, top + margin, margin)


def show_in_taskbar(win):
    """無邊框視窗預設不出現在工作列；補上，避免視窗被蓋住後找不到。"""
    u = ctypes.windll.user32
    win.update_idletasks()
    hwnd = u.GetParent(win.winfo_id()) or win.winfo_id()
    ex = u.GetWindowLongW(hwnd, -20)
    u.SetWindowLongW(hwnd, -20, (ex & ~0x80) | 0x40000)  # 移除 TOOLWINDOW、加上 APPWINDOW
    win.withdraw()
    win.after(30, win.deiconify)


_CURSORS = {"l": "size_we", "r": "size_we", "t": "size_ns", "b": "size_ns",
            "lt": "size_nw_se", "rb": "size_nw_se", "rt": "size_ne_sw", "lb": "size_ne_sw"}


def _edge_resize(win, min_size, state):
    """四邊與四角都能拖拉改大小：只在滑鼠位於視窗邊框（win 本身，不是子元件）時觸發。"""
    drag = {}

    def edge(e):
        if e.widget is not win or state["collapsed"]:
            return ""
        w, h = win.winfo_width(), win.winfo_height()
        g = BW + 2
        return ("l" if e.x < g else "r" if e.x > w - g else "") + ("t" if e.y < g else "b" if e.y > h - g else "")

    def motion(e):
        # 滑鼠移進內容區（子元件）時 edge() 回傳 ""，游標會被重設，避免殘留拉伸箭頭
        win.configure(cursor=_CURSORS.get(drag["edge"] if drag else edge(e), ""))

    def press(e):
        d = edge(e)
        if d:
            drag.update(edge=d, x=e.x_root, y=e.y_root, wx=win.winfo_x(), wy=win.winfo_y(),
                        w=win.winfo_width(), h=win.winfo_height())

    def move(e):
        if not drag:
            return
        d, dx, dy = drag["edge"], e.x_root - drag["x"], e.y_root - drag["y"]
        x, y, w, h = drag["wx"], drag["wy"], drag["w"], drag["h"]
        if "r" in d:
            w = max(drag["w"] + dx, min_size[0])
        if "b" in d:
            h = max(drag["h"] + dy, min_size[1])
        if "l" in d:
            w = max(drag["w"] - dx, min_size[0])
            x = drag["wx"] + drag["w"] - w
        if "t" in d:
            h = max(drag["h"] - dy, min_size[1])
            y = drag["wy"] + drag["h"] - h
        win.geometry(f"{w}x{h}+{x}+{y}")

    win.bind("<Motion>", motion, add="+")
    win.bind("<Button-1>", press, add="+")
    win.bind("<B1-Motion>", move, add="+")
    win.bind("<ButtonRelease-1>", lambda e: drag.clear(), add="+")
