"""回報視窗：說明＋聯絡方式＋診斷資訊勾選，送出前顯示將送出的完整內容，由使用者自己按送出。

送出走 feedback-relay（zt/feedback.py）。失敗時把整理好的內容複製到剪貼簿，並問要不要改用 GitHub Issues。
"""
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

import pyperclip

from . import feedback, ui, update


class ReportDialog:
    def __init__(self, app):
        self.app = app
        self.win = win = tk.Toplevel(app)
        win.attributes("-topmost", True)
        box, _ = ui.compact(win, "回報問題", resizable=False)
        self.sending = False
        width = max(app.winfo_width(), 420) - 2 * ui.BW
        tk.Frame(box, width=width, height=1, bg=ui.BG).pack()  # 固定寬度

        ttk.Label(box, text="說明（必填）：發生了什麼事？", style="Head.TLabel").pack(anchor="w", padx=8, pady=(6, 2))
        self.desc = self._text(box, 4)
        ttk.Label(box, text="聯絡方式（選填，例如 email）").pack(anchor="w", padx=8, pady=(6, 2))
        self.contact = tk.Entry(box, font=ui.FONT, bg=ui.FIELD, fg=ui.TEXT, insertbackground=ui.GOLD,
                                relief="flat", highlightthickness=1, highlightbackground=ui.LINE,
                                highlightcolor=ui.BLUE)
        self.contact.pack(fill="x", padx=8, ipady=4)
        self.contact.bind("<Button-1>", lambda e: self.contact.focus_force())
        self.contact.bind("<KeyRelease>", lambda e: self.refresh_preview())

        self.diag = tk.BooleanVar(value=True)
        ttk.Checkbutton(box, text="附上診斷資訊（版本、環境、最近執行結果；不含清單與房名）",
                        variable=self.diag, command=self.refresh_preview).pack(anchor="w", padx=8, pady=(8, 2))

        ttk.Label(box, text="將送出的完整內容（唯讀）：", style="Muted.TLabel").pack(anchor="w", padx=8, pady=(4, 2))
        self.preview = self._text(box, 7, readonly=True, scroll=True)

        ttk.Label(box, text="回報會寄給開發者，並保存在開發者的 Google 帳號（不公開）。詳見 PRIVACY.md。",
                  style="Muted.TLabel", wraplength=width - 20).pack(anchor="w", padx=8, pady=(6, 2))
        self.status = tk.StringVar()
        ttk.Label(box, textvariable=self.status, style="Warn.TLabel", wraplength=width - 20).pack(
            anchor="w", padx=8)
        row = ttk.Frame(box)
        row.pack(fill="x", padx=8, pady=(4, 8))
        self.send_btn = ttk.Button(row, text="送出", style="Accent.TButton", command=self.on_send)
        self.send_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(row, text="取消", command=win.destroy).pack(side="left", padx=(4, 0))

        self.desc.bind("<KeyRelease>", lambda e: self.refresh_preview())
        self.refresh_preview()
        win.update_idletasks()
        ui.place(win, app.winfo_x(), app.winfo_y() + app.winfo_height() - win.winfo_reqheight())
        win.after(100, self.desc.focus_force)

    def _text(self, parent, height, readonly=False, scroll=False):
        holder = ttk.Frame(parent)
        holder.pack(fill="x", padx=8)
        t = tk.Text(holder, height=height, width=10, font=ui.FONT, wrap="word", bg=ui.FIELD, fg=ui.TEXT,
                    insertbackground=ui.GOLD, selectbackground="#1f3b66", selectforeground=ui.TEXT,
                    relief="flat", bd=0, padx=8, pady=6, highlightthickness=1,
                    highlightbackground=ui.LINE, highlightcolor=ui.BLUE)
        if scroll:
            sb = ttk.Scrollbar(holder, command=t.yview)
            t.configure(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y")
        t.pack(side="left", fill="x", expand=True)
        t.bind("<Button-1>", lambda e: t.focus_force())
        if readonly:
            t.configure(state="disabled", fg=ui.MUTED)
        return t

    def content(self):
        return feedback.build(self.desc.get("1.0", "end"), self.contact.get(), self.diag.get())

    def refresh_preview(self):
        _, body = self.content()
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", body)
        self.preview.configure(state="disabled")

    def on_send(self):
        if self.sending:
            return
        if not self.desc.get("1.0", "end").strip():
            self.status.set("請先寫下說明。")
            return
        self.sending = True
        self.send_btn.configure(state="disabled")
        self.status.set("送出中…（連線不穩時最多重試 3 次，請稍候）")
        title, body = self.content()
        threading.Thread(target=self._worker, args=(title, body), daemon=True).start()

    def _worker(self, title, body):
        try:
            feedback.send(title, body)
        except feedback.RelayError as e:
            msg = feedback.ERROR_TEXT.get(e.code, f"回報服務回應了未知的錯誤（{e.code}）。")
            self.win.after(0, self._failed, body, msg)
        except feedback.RelayConnectionError as e:
            self.win.after(0, self._failed, body, f"連不到回報服務。\n{e}")
        except Exception as e:  # 不讓任何意外讓視窗卡住
            self.win.after(0, self._failed, body, f"送出時發生錯誤：{e}")
        else:
            self.win.after(0, self._done)

    def _done(self):
        self.app.status.set("回報已送出，謝謝！")
        messagebox.showinfo("回報問題", "已送出，謝謝你的回報！", parent=self.win)
        self.win.destroy()

    def _failed(self, body, reason):
        self.sending = False
        self.send_btn.configure(state="normal")
        try:
            pyperclip.copy(body)
            copied = "已把內容複製到剪貼簿。"
        except Exception:
            copied = ""
        self.status.set("送出失敗")
        if messagebox.askyesno("回報問題", f"{reason}\n\n{copied}要改到 GitHub Issues 回報嗎？"
                               "（會開啟網頁，貼上剛才複製的內容即可）", parent=self.win):
            webbrowser.open(update.ISSUES_URL)
