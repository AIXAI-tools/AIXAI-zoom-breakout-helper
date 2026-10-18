"""Zoom 分組討論室批次建立／改名小工具（極簡視窗版）。

主視窗只有：清單下拉、房名框（可捲動）、執行鈕、狀態列。
其餘功能全在上方選單：清單、選項、校準、檢視。
中斷：執行中按 Esc，或把滑鼠甩到螢幕左上角。
"""
import ctypes
import os
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import messagebox, simpledialog, ttk

import pyautogui

# 讓座標與實際螢幕像素一致（避免縮放比例造成偏移）
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

from zt import __version__ as VERSION  # noqa: E402  (需在 DPI 設定之後匯入)
from zt import actions, calib, env, store, ui, update  # noqa: E402

VK_ESC, VK_F8 = 0x1B, 0x77
DELAY_LABELS = {"hover": "hover 等待（秒）", "dialog": "改名視窗等待（秒）", "after": "每間之間等待（秒）"}


def key_down(vk):
    return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        store.init()
        self.settings = store.load_settings()
        self.calib = store.load_calibration()
        self.busy = False
        self.cal = None
        self.props = None
        self.profile = self.settings.get("last_profile") or store.list_profiles()[0]
        if self.profile not in store.list_profiles():
            self.profile = store.list_profiles()[0]

        self.title("zoom分組小工具")  # 無邊框後標題只會顯示在工作列
        ui.apply_fonts(self)
        ui.apply_theme(self)
        ui.apply_icon(self)
        self.attributes("-topmost", bool(self.settings.get("topmost", True)))
        self.mode_var = tk.StringVar()
        self.assign_var = tk.StringVar()
        self.top_var = tk.BooleanVar(value=bool(self.settings.get("topmost", True)))

        self.build_menu()
        body, self.bar_widgets = ui.compact(self, "zoom分組小工具", on_close=self.on_close, menu=self.menubar,
                                            min_size=(200, 160))

        self.combo = ttk.Combobox(body, state="readonly")
        self.combo.pack(fill="x", padx=6, pady=(4, 2))
        self.combo.bind("<<ComboboxSelected>>", self.on_switch)

        # 底部先 pack，房名框才不會把它們擠出視窗
        # 狀態列固定單行，過長就截斷；點一下可看全文，避免長訊息把房名框擠掉
        self.status = tk.StringVar(value="就緒")
        self.status_short = tk.StringVar(value="就緒")
        self.status.trace_add("write", self.on_status_change)
        lbl = self.status_lbl = ttk.Label(body, textvariable=self.status_short, style="Status.TLabel", cursor="hand2")
        lbl.pack(side="bottom", fill="x", padx=6, pady=(0, 2))
        lbl.bind("<Button-1>", lambda e: messagebox.showinfo("狀態", self.status.get()))
        ttk.Button(body, text="▶ 執行", style="Accent.TButton", command=self.on_run).pack(
            side="bottom", fill="x", padx=6, pady=2)

        frame = ttk.Frame(body)
        frame.pack(fill="both", expand=True, padx=6)
        self.text = tk.Text(frame, height=3, width=10, font=ui.FONT, wrap="none", bg=ui.FIELD, fg=ui.TEXT,
                            insertbackground=ui.GOLD, selectbackground="#1f3b66", selectforeground=ui.TEXT,
                            relief="flat", bd=0, padx=8, pady=6, highlightthickness=1,
                            highlightbackground=ui.LINE, highlightcolor=ui.BLUE)
        sb = ttk.Scrollbar(frame, command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.bind("<Button-1>", lambda e: self.text.focus_force())  # 無邊框視窗要手動取得鍵盤焦點

        self.refresh_profiles()
        # 預設大小 = 螢幕 1/6，但不小於內容（至少看得到 3 行房名）所需；放在右下角
        self.update_idletasks()
        self.geometry(ui.default_geometry(self.winfo_reqwidth(), self.winfo_reqheight()))
        self.after(200, lambda: ui.show_in_taskbar(self))
        self.after(500, self.check_env)

    def on_status_change(self, *_):
        text = self.status.get().replace("\n", " ")
        self.status_short.set(text if len(text) <= 12 else text[:11] + "…")
        self.status_lbl.configure(style="Warn.TLabel" if text.startswith("⚠") else "Status.TLabel")

    # ---- 選單 ----
    def build_menu(self):
        bar = tk.Menu(self, tearoff=0)  # tearoff=0：拿掉選單最上面那條虛線
        m = tk.Menu(bar, tearoff=0)
        m.add_command(label="新增清單…", command=lambda: self.new_profile(copy=False))
        m.add_command(label="另存目前清單為…", command=lambda: self.new_profile(copy=True))
        m.add_command(label="移除目前清單", command=self.remove_profile)
        m.add_separator()
        m.add_command(label="開啟清單資料夾", command=lambda: os.startfile(store.PROFILE_DIR))
        bar.add_cascade(label="清單", menu=m)

        m = tk.Menu(bar, tearoff=0)
        for k, (label, hint, *_r) in actions.BUILD_MODES.items():
            m.add_radiobutton(label=f"{label}　{hint}", value=k, variable=self.mode_var,
                              command=self.on_mode_change)
        m.add_separator()
        for k, (label, _) in actions.ASSIGN_MODES.items():
            m.add_radiobutton(label=f"分配：{label}", value=k, variable=self.assign_var,
                              command=self.on_mode_change)
        m.add_separator()
        m.add_checkbutton(label="視窗置頂", variable=self.top_var, command=self.on_topmost)
        bar.add_cascade(label="選項", menu=m)

        self.cal_menu = tk.Menu(bar, tearoff=0)
        self.cal_menu.add_command(label="完整引導校準", command=lambda: self.calibrate())
        one = tk.Menu(self.cal_menu, tearoff=0)
        for key, label, _, req in calib.STEPS:
            one.add_command(label=label + ("" if req else "（選用）"),
                            command=lambda k=key: self.calibrate([k]))
        self.cal_menu.add_cascade(label="重校準單項", menu=one)
        self.cal_menu.add_command(label="清除全部校準", command=self.clear_calib)
        bar.add_cascade(label="校準", menu=self.cal_menu)
        self.menubar = bar

        m = tk.Menu(bar, tearoff=0)
        m.add_command(label="屬性與環境", command=self.show_props)
        m.add_command(label="開啟紀錄資料夾", command=lambda: os.startfile(store.LOG_DIR))
        m.add_separator()
        m.add_command(label=f"檢查更新（目前 v{VERSION}）", command=self.check_update)
        bar.add_cascade(label="檢視", menu=m)

    # ---- 清單 ----
    def refresh_profiles(self):
        names = store.list_profiles()
        self.combo["values"] = names
        self.combo.set(self.profile)
        data = store.load_profile(self.profile)
        self.mode_var.set(data["mode"])
        self.assign_var.set(data["assign"])
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(data["names"]))
        self.show_mode_hint()

    def names(self):
        return [ln.strip() for ln in self.text.get("1.0", "end").splitlines() if ln.strip()]

    def save_profile(self):
        store.save_profile(self.profile, {"names": self.names(), "mode": self.mode_var.get(),
                                          "assign": self.assign_var.get()})

    def on_switch(self, _e=None):
        self.save_profile()
        self.profile = self.combo.get()
        self.refresh_profiles()

    def new_profile(self, copy):
        name = simpledialog.askstring("清單名稱", "請輸入清單名稱：", parent=self)
        if not name:
            return
        self.save_profile()
        if not copy:
            store.save_profile(name, dict(store.DEFAULT_PROFILE))
        else:
            store.save_profile(name, {"names": self.names(), "mode": self.mode_var.get(),
                                      "assign": self.assign_var.get()})
        self.profile = name
        self.refresh_profiles()

    def remove_profile(self):
        if len(store.list_profiles()) < 2:
            self.status.set("至少要保留一個清單")
            return
        if messagebox.askyesno("移除清單", f"移除「{self.profile}」？\n檔案會搬到 清單/_已移除/，可自行還原。"):
            store.archive_profile(self.profile)
            self.profile = store.list_profiles()[0]
            self.refresh_profiles()

    def on_mode_change(self):
        self.save_profile()
        self.show_mode_hint()

    def show_mode_hint(self):
        label, hint, *_r = actions.BUILD_MODES[self.mode_var.get()]
        self.status.set(f"{label}：{hint}")

    def on_topmost(self):
        self.attributes("-topmost", self.top_var.get())
        self.settings["topmost"] = self.top_var.get()
        store.save_settings(self.settings)

    def on_close(self):
        self.save_profile()
        self.settings["last_profile"] = self.profile
        store.save_settings(self.settings)
        self.destroy()

    # ---- 環境檢查（只提醒，不強制）----
    def check_env(self):
        if not self.calib["points"]:
            self.set_cal_warn("尚未校準 → 選單「校準」→「完整引導校準」")
            return
        diffs = env.diff(self.calib["env"], env.current_env())
        if diffs:
            store.log_env({"event": "env_changed", "diff": diffs})
            self.set_cal_warn("環境有變，建議重新校準（" + "；".join(diffs) + "）")

    def set_cal_warn(self, msg):
        self.status.set("⚠ " + msg)

    # ---- 校準（置頂小說明視窗，主執行緒輪詢 F8 / Esc）----
    def calibrate(self, keys=None):
        if self.busy or self.cal:
            return
        steps = [s for s in calib.STEPS if keys is None or s[0] in keys]
        win = tk.Toplevel(self)
        win.attributes("-topmost", True)
        box, _ = ui.compact(win, "校準", on_close=lambda: self.cal_end("校準已結束"), resizable=False)
        head, hint = tk.StringVar(), tk.StringVar()
        mw = self.winfo_width()  # 寬度與主視窗一致，不留多餘空白
        wrap = mw - 2 * ui.BW - 16
        tk.Frame(box, width=mw - 2 * ui.BW, height=1, bg=ui.BG).pack()
        # 按鈕列先 pack 到底部，文字區高度固定時按鈕位置也固定
        row = ttk.Frame(box)
        row.pack(side="bottom", fill="x", padx=8, pady=(0, 4))
        ttk.Button(row, text="跳過 (Esc)", command=self.cal_skip).pack(side="left")
        ttk.Button(row, text="結束校準", command=lambda: self.cal_end("校準已結束")).pack(side="right")
        ttk.Label(box, text="※ 筆電請按 Fn + F8", style="Hint.TLabel").pack(
            side="bottom", anchor="w", padx=8, pady=(0, 2))  # 固定提醒，每一步都顯示
        ttk.Label(box, textvariable=head, style="Head.TLabel").pack(
            anchor="w", padx=8, pady=(4, 0))
        ttk.Label(box, textvariable=hint, justify="left").pack(anchor="w", padx=8, pady=2)
        # f8/esc 初值 True：避免把開始前就按住的鍵當成新的按下
        self.cal = {"steps": steps, "i": 0, "win": win, "head": head, "hint": hint, "wrap": wrap,
                    "f8": True, "esc": True, "got": 0, "full": keys is None}
        # 先逐步量出最高的一步，視窗高度固定，之後每一步都不再變動
        tallest = 0
        for i in range(len(steps)):
            self.cal["i"] = i
            self.cal_show()
            win.update_idletasks()
            tallest = max(tallest, win.winfo_reqheight())
        self.cal["i"] = 0
        self.cal_show()
        win.geometry(f"{mw}x{tallest}")
        ui.place(win, self.winfo_x(), self.winfo_y() - tallest, margin=0)  # 緊貼主視窗上緣，往上長
        self.after(300, self.cal_poll)

    def cal_show(self):
        c = self.cal
        _, label, hint, req = c["steps"][c["i"]]
        c["head"].set(ui.wrap_text(f"{c['i'] + 1}/{len(c['steps'])}　{label}（{'必要' if req else '選用，Esc 跳過'}）",
                                   c["wrap"], bold=True))
        c["hint"].set(ui.wrap_text(hint, c["wrap"]))

    def cal_next(self):
        c = self.cal
        c["i"] += 1
        if c["i"] >= len(c["steps"]):
            self.cal_end(f"校準完成（記錄 {c['got']} 項）")
        else:
            self.cal_show()

    def cal_skip(self):
        if not self.cal:
            return
        if self.cal["steps"][self.cal["i"]][3]:
            self.cal["head"].set("這一步是必要的，不能跳過；要放棄請按「結束校準」")
        else:
            self.cal_next()

    def cal_record(self, key):
        pos = list(pyautogui.position())
        self.calib["points"][key] = pos
        if key == "yes":
            self.calib["blue"] = actions.sample_color(pos)  # 記下「是」的藍色，改名時用來找按鈕
        elif key == "anchor":
            actions.save_anchor(pos)
        self.cal["got"] += 1

    def cal_poll(self):
        c = self.cal
        if not c:
            return
        f8, esc = key_down(VK_F8), key_down(VK_ESC)
        if f8 and not c["f8"]:
            self.cal_record(c["steps"][c["i"]][0])
            self.cal_next()
        elif esc and not c["esc"]:
            self.cal_skip()
        if self.cal:
            self.cal["f8"], self.cal["esc"] = f8, esc
            self.after(30, self.cal_poll)

    def cal_end(self, msg):
        if not self.cal:
            return
        got, full = self.cal["got"], self.cal["full"]
        self.cal["win"].destroy()
        self.cal = None
        if got:
            if full:
                self.calib["env"] = env.current_env()
            self.calib["captured_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            store.save_calibration(self.calib)
            store.log_env({"event": "calibrated", "full": full, "env": env.current_env()})
        self.status.set(msg)
        self.refresh_props()

    def clear_calib(self):
        if messagebox.askyesno("清除校準", "確定清除全部座標？"):
            self.calib = {"points": {}, "env": {}, "blue": None, "captured_at": ""}
            store.save_calibration(self.calib)
            self.set_cal_warn("尚未校準")
            self.refresh_props()

    # ---- 檢查更新（只提醒，不自動更新）----
    def check_update(self):
        self.status.set("檢查更新中…")
        threading.Thread(target=self._check_update_worker, daemon=True).start()

    def _check_update_worker(self):
        try:
            r = update.check(VERSION)
        except Exception as e:  # 網路不通、被防火牆擋、GitHub 暫時異常等
            self.after(0, self._update_result, None, str(e))
        else:
            self.after(0, self._update_result, r, "")

    def _update_result(self, r, err):
        if r is None:
            self.status.set("檢查更新失敗")
            messagebox.showerror("檢查更新", f"無法連到 GitHub，請確認網路後再試。\n\n詳細：{err}")
        elif r["status"] == "new":
            self.status.set(f"有新版本 {r['tag']}")
            if messagebox.askyesno("檢查更新", f"有新版本 {r['tag']}（目前 v{VERSION}）。\n要開啟下載頁面嗎？"):
                webbrowser.open(r["url"])
        elif r["status"] == "latest":
            self.status.set("已是最新版")
            messagebox.showinfo("檢查更新", f"目前 v{VERSION} 已是最新版。")
        else:
            self.status.set("尚未發布正式版本")
            messagebox.showinfo("檢查更新", "專案目前還沒有發布任何正式版本。")

    # ---- 屬性與環境 ----
    def show_props(self):
        if self.props and self.props.winfo_exists():
            self.props.lift()
            return
        w = self.props = tk.Toplevel(self)
        w.attributes("-topmost", True)
        box, _ = ui.compact(w, f"屬性 v{VERSION}", resizable=False)
        self.env_label = ttk.Label(box, justify="left", style="Muted.TLabel")
        self.env_label.pack(anchor="w", padx=8, pady=(8, 2))
        self.tree = ttk.Treeview(box, columns=("pos", "req"), height=len(calib.STEPS), selectmode="browse")
        self.tree.heading("#0", text="項目（雙擊重校準）", anchor="w")
        self.tree.heading("pos", text="座標")
        self.tree.heading("req", text="")
        self.tree.column("#0", width=230)
        self.tree.column("pos", width=140, anchor="center")
        self.tree.column("req", width=70, anchor="center")
        self.tree.pack(padx=8, pady=4)
        self.tree.bind("<Double-1>", lambda e: self.tree.selection() and self.calibrate([self.tree.selection()[0]]))
        grid = ttk.Frame(box)
        grid.pack(fill="x", padx=8)
        self.delay_vars = {}
        for r, (k, lab) in enumerate(DELAY_LABELS.items()):
            ttk.Label(grid, text=lab).grid(row=r, column=0, sticky="w")
            v = tk.DoubleVar(value=self.settings["delay"][k])
            ttk.Spinbox(grid, from_=0.05, to=3, increment=0.05, width=6, textvariable=v).grid(
                row=r, column=1, padx=6, pady=1)
            self.delay_vars[k] = v
        ttk.Button(box, text="儲存等待時間", command=self.save_delays).pack(anchor="w", padx=8, pady=8)
        self.refresh_props()
        w.update_idletasks()  # 放在主視窗左邊，並確保不超出螢幕
        ui.place(w, self.winfo_x() - w.winfo_reqwidth() - 10, self.winfo_y() + self.winfo_height() - w.winfo_reqheight())

    def refresh_props(self):
        if not (self.props and self.props.winfo_exists()):
            return
        now, saved = env.current_env(), self.calib["env"]
        self.env_label.config(text=(
            f"現在：Zoom {now['zoom_version']}｜{now['screen'][0]}×{now['screen'][1]}｜DPI {now['dpi']}\n"
            f"校準時：{('Zoom ' + saved['zoom_version'] + '｜' + str(saved['screen'][0]) + '×' + str(saved['screen'][1]) + '｜DPI ' + str(saved['dpi'])) if saved else '無紀錄'}\n"
            f"校準時間：{self.calib['captured_at'] or '—'}"))
        self.tree.delete(*self.tree.get_children())
        for key, label, _, req in calib.STEPS:
            pos = self.calib["points"].get(key)
            self.tree.insert("", "end", iid=key, text=label,
                             values=(f"{pos[0]}, {pos[1]}" if pos else "未校準", "必要" if req else "選用"))

    def save_delays(self):
        for k, v in self.delay_vars.items():
            try:
                self.settings["delay"][k] = round(float(v.get()), 2)
            except (tk.TclError, ValueError):
                pass
        store.save_settings(self.settings)
        self.status.set("等待時間已儲存")

    # ---- 執行 ----
    def on_run(self):
        if self.busy or self.cal:
            return
        self.save_profile()
        names = self.names()
        mode = self.mode_var.get()
        _, _, do_create, do_rename = actions.BUILD_MODES[mode]
        if not names:
            self.status.set("房名清單是空的")
            return
        self.busy = True
        threading.Thread(target=self.worker, args=(names, mode, do_create, do_rename), daemon=True).start()

    def worker(self, names, mode, do_create, do_rename):
        p = self.calib["points"]
        result, problems, outcome = {}, [], "ok"
        try:
            if do_create:
                actions.create_rooms(p, len(names), self.assign_var.get(), self.set_status)
            if do_rename:
                result = actions.rename_all(p, names, self.settings["delay"], self.calib["blue"], self.set_status)
                problems = actions.verify_end(p, result)
                if result["skipped"]:
                    problems.append(f"{len(result['skipped'])} 間超出螢幕下緣沒改（請把分組視窗拉高或放大）")
            if problems:
                outcome = "abnormal"
                self.set_status("⚠ 完成但" + "；".join(problems) + "。建議重新校準")
            elif do_rename:
                self.set_status(f"完成，共改名 {result['done']} 間")
        except actions.Aborted:
            outcome = "aborted"
            self.set_status("已中斷")
        except pyautogui.FailSafeException:
            outcome = "aborted"
            self.set_status("已中斷（滑鼠移到左上角）")
        except Exception as e:  # 顯示給使用者看
            outcome = "error"
            self.set_status(f"發生錯誤：{e}")
        finally:
            self.busy = False
            store.log_usage({"profile": self.profile, "mode": mode, "rooms": len(names),
                             "outcome": outcome, "problems": problems, "env": env.current_env()})

    def set_status(self, msg):
        self.after(0, self.status.set, msg)


if __name__ == "__main__":
    App().mainloop()
