# -*- coding: utf-8 -*-
"""
DNS 缓存清理工具 (Windows 10/11/12)
- 支持一键刷新全部 DNS 缓存
- 支持指定单个域名，仅刷新该域名的缓存记录
- 基于 tkinter 开发，零第三方依赖
"""

import ctypes
import datetime
import subprocess
import sys
import threading

import tkinter as tk
from tkinter import messagebox, ttk


APP_NAME = "DNS缓存清理工具"
DEFAULT_WIN_VER = "Windows 10 / 11 / 12"

DNS_ERROR_SUCCESS = 0


def is_admin():
    """判断当前进程是否以管理员权限运行。"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def run_as_admin():
    """以管理员权限重新运行当前进程（UAC 提示）。"""
    try:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1
        )
        return True
    except Exception:
        return False


def flush_all():
    """刷新全部 DNS 缓存，返回 (成功与否, 输出信息)。"""
    try:
        proc = subprocess.Popen(
            ["ipconfig", "/flushdns"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            encoding="gbk",
            errors="ignore",
        )
        out, err = proc.communicate(timeout=30)
        if proc.returncode == 0:
            return True, (out or "").strip()
        return False, (err or out or "").strip()
    except FileNotFoundError:
        return False, "未找到 ipconfig 命令，请确认当前为 Windows 系统。"
    except Exception as e:
        return False, f"执行失败：{e}"


def flush_domain(domain):
    """
    通过 dnsapi.dll 的 DnsFlushResolverCacheEntry_W 仅刷新指定域名的缓存记录。
    该接口存在于 dnsapi.dll 中，可在管理员权限下删除指定名称的缓存条目。
    """
    try:
        dnsapi = ctypes.WinDLL("dnsapi")
        func = dnsapi.DnsFlushResolverCacheEntry_W
        func.argtypes = [ctypes.c_wchar_p]
        func.restype = ctypes.c_ulong
        result = func(domain)
        if result == DNS_ERROR_SUCCESS:
            return True, f"成功刷新域名 [{domain}] 的 DNS 缓存。"
        return False, f"刷新域名 [{domain}] 失败，DNS 状态码: 0x{result:08X}。"
    except Exception as e:
        return False, f"刷新域名 [{domain}] 时出错：{e}"


class DnsFlushApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("560x520")
        self.root.minsize(520, 460)
        self.root.configure(bg="#f4f6f9")

        self.admin = is_admin()
        self.busy = False

        self._build_header()
        self._build_form()
        self._build_control()
        self._build_console()
        self._build_footer()

        if not self.admin:
            self._log(
                "提示：当前未以管理员身份运行。刷新 DNS 需要管理员权限，请点击【以管理员运行】。",
                color="#c9302c",
            )

    # ---------- 界面构建 ----------
    def _build_header(self):
        header = tk.Frame(self.root, bg="#2c3e50")
        header.pack(fill="x")
        title = tk.Label(
            header,
            text="DNS 缓存清理工具",
            bg="#2c3e50",
            fg="white",
            font=("Microsoft YaHei", 16, "bold"),
        )
        title.pack(pady=12)
        sub = tk.Label(
            header,
            text=DEFAULT_WIN_VER,
            bg="#2c3e50",
            fg="#bdc3c7",
            font=("Microsoft YaHei", 9),
        )
        sub.pack(pady=(0, 12))

    def _build_form(self):
        form = tk.Frame(self.root, bg="#f4f6f9")
        form.pack(fill="x", padx=20, pady=14)

        tk.Label(
            form, text="指定域名：", bg="#f4f6f9",
            font=("Microsoft YaHei", 11),
        ).pack(side="left", padx=(0, 8))
        self.domain_var = tk.StringVar()
        self.domain_entry = tk.Entry(
            form, textvariable=self.domain_var, font=("Microsoft YaHei", 11),
            width=34, relief="solid", bd=1,
        )
        self.domain_entry.pack(side="left", ipady=4)

        hint = tk.Label(
            form, text="例：example.com，留空仅用于“刷新全部”",
            bg="#f4f6f9", fg="#888888", font=("Microsoft YaHei", 9),
        )
        hint.pack(anchor="w", pady=(6, 0))

    def _build_control(self):
        ctrl = tk.Frame(self.root, bg="#f4f6f9")
        ctrl.pack(fill="x", padx=20, pady=6)

        self.btn_flush_all = tk.Button(
            ctrl, text="刷新全部 DNS 缓存", command=self.on_flush_all,
            bg="#3498db", fg="white", font=("Microsoft YaHei", 11, "bold"),
            relief="flat", cursor="hand2", padx=16, pady=8,
        )
        self.btn_flush_all.pack(side="left", padx=(0, 12))

        self.btn_flush_domain = tk.Button(
            ctrl, text="刷新指定域名", command=self.on_flush_domain,
            bg="#e67e22", fg="white", font=("Microsoft YaHei", 11, "bold"),
            relief="flat", cursor="hand2", padx=16, pady=8,
        )
        self.btn_flush_domain.pack(side="left", padx=(0, 12))

        self.btn_admin = tk.Button(
            ctrl, text="以管理员运行", command=self.on_admin,
            bg="#e74c3c", fg="white", font=("Microsoft YaHei", 10),
            relief="flat", cursor="hand2", padx=12, pady=8,
        )
        self.btn_admin.pack(side="left")

    def _build_console(self):
        console_box = tk.Frame(self.root, bg="#1e272e")
        console_box.pack(fill="both", expand=True, padx=20, pady=10)

        self.console = tk.Text(
            console_box, bg="#1e272e", fg="#e1e1e1",
            font=("Consolas", 10), relief="flat", wrap="word",
            state="disabled", cursor="arrow",
        )
        self.console.pack(fill="both", expand=True, side="left")

        scroll = tk.Scrollbar(console_box, command=self.console.yview)
        scroll.pack(side="right", fill="y")
        self.console.configure(yscrollcommand=scroll.set)

    def _build_footer(self):
        f = tk.Frame(self.root, bg="#f4f6f9")
        f.pack(fill="x", padx=20, pady=(0, 12))
        status = (
            "管理员权限：" + ("已授予" if self.admin else "未授予")
        )
        self.status_label = tk.Label(
            f, text=status, bg="#f4f6f9", fg="#666666",
            font=("Microsoft YaHei", 9),
        )
        self.status_label.pack(side="left")

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tk.Label(
            f, text=now, bg="#f4f6f9", fg="#aaaaaa", font=("Microsoft YaHei", 9),
        ).pack(side="right")

    # ---------- 功能逻辑 ----------
    def _log(self, msg, color="#e1e1e1"):
        self.console.configure(state="normal")
        tag = f"c{color[1:]}"
        self.console.tag_configure(tag, foreground=color)
        line = f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}\n"
        self.console.insert("end", line, tag)
        self.console.see("end")
        self.console.configure(state="disabled")

    def _set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.btn_flush_all.configure(state=state)
        self.btn_flush_domain.configure(state=state)
        self.domain_entry.configure(state="disabled" if busy else "normal")

    def _report(self, ok, msg, label):
        color = "#7bed9f" if ok else "#ff6b6b"
        self._log(f"[{label}] {msg}", color=color)

    def on_flush_all(self):
        if self.busy:
            return
        if not self.admin:
            messagebox.showwarning(APP_NAME, "请先点击【以管理员运行】获取管理员权限。")
            return
        self._set_busy(True)
        self._log("开始刷新全部 DNS 缓存...", color="#f9ca24")

        def worker():
            ok, out = flush_all()
            self.root.after(0, self._finish_flush_all, ok, out)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_flush_all(self, ok, out):
        self._report(ok, out or ("刷新全部 DNS 缓存成功。" if ok else "无输出。"), "刷新全部")
        self._set_busy(False)

    def on_flush_domain(self):
        if self.busy:
            return
        domain = self.domain_var.get().strip()
        if not domain:
            messagebox.showwarning(APP_NAME, "请输入要刷新的域名。")
            return
        if not self.admin:
            messagebox.showwarning(APP_NAME, "请先点击【以管理员运行】获取管理员权限。")
            return
        if not self._is_valid_domain(domain):
            messagebox.showwarning(APP_NAME, "域名格式不正确，请输入合法的域名。")
            return

        self._set_busy(True)
        self._log(f"开始刷新域名 [{domain}] 的 DNS 缓存...", color="#f9ca24")

        def worker():
            ok, out = flush_domain(domain)
            if not ok:
                # 单个域名刷新失败时，降级为刷新全部缓存（同样会清除该域名记录）
                ok2, out2 = flush_all()
                extra = "\n已降级为刷新全部 DNS 缓存。"
                ok, out = ok2, out + extra + out2
            self.root.after(0, self._finish_flush_domain, ok, out)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_flush_domain(self, ok, out):
        self._report(ok, out, "指定域名")
        self._set_busy(False)

    @staticmethod
    def _is_valid_domain(domain):
        if len(domain) > 253:
            return False
        labels = domain.split(".")
        if len(labels) < 2:
            return False
        for label in labels:
            if not label or len(label) > 63:
                return False
            if not (label[0].isalnum() and label[-1].isalnum()):
                return False
            for ch in label:
                if not (ch.isalnum() or ch in ("-", "_")):
                    return False
        return True

    def on_admin(self):
        if self.admin:
            messagebox.showinfo(APP_NAME, "当前已是管理员权限运行。")
            return
        if run_as_admin():
            self.root.destroy()
        else:
            messagebox.showerror(APP_NAME, "未能获取管理员权限，请手动右键以管理员身份运行。")


def main():
    if sys.platform != "win32":
        print("该工具仅支持 Windows 10/11/12 系统。")
        return
    root = tk.Tk()
    DnsFlushApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()