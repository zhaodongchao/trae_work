# -*- coding: utf-8 -*-
"""
Windows 系统垃圾清理 GUI 工具
兼容：Windows 10 / Windows 11
技术栈：Python 3.x + tkinter（标准库，无需额外依赖）

功能说明：
- 扫描系统常见垃圾目录（临时文件、浏览器缓存、回收站、日志、更新缓存、缩略图缓存等）
- 异步扫描与清理，UI 不卡死
- 分类展示、勾选控制、二次确认、进度条、实时日志、日志导出
- 异常捕获与安全防护（跳过占用/权限不足文件，不碰用户文档）
"""

import os
import sys
import time
import shutil
import threading
import logging
import tempfile
import ctypes
import glob
from datetime import datetime
from pathlib import Path
from tkinter import (
    Tk, Toplevel, StringVar, BooleanVar, IntVar,
    Menu, PhotoImage, END, NORMAL, DISABLED, BOTH, X, Y, LEFT, RIGHT, TOP, BOTTOM,
    W, E, N, S, HORIZONTAL, VERTICAL, CENTER, YES, NO, CANCEL, messagebox, filedialog
)
from tkinter import ttk

# 仅在 Windows 下注册 SHEmptyRecycleBinW
if sys.platform == "win32":
    try:
        _SHEmptyRecycleBinW = ctypes.windll.shell32.SHEmptyRecycleBinW
    except Exception:
        _SHEmptyRecycleBinW = None
else:
    _SHEmptyRecycleBinW = None


# ============================================================
# 日志类：负责统一格式化、缓存与 UI 回调
# ============================================================
class AppLogger:
    """线程安全的内存日志记录器，同时可向 UI 回调推送新行。"""

    def __init__(self, ui_callback=None):
        self.ui_callback = ui_callback
        self._lock = threading.Lock()
        self._lines = []

    def log(self, message, level="INFO"):
        """记录一条日志。"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] [{level}] {message}"
        with self._lock:
            self._lines.append(line)
        if self.ui_callback:
            self.ui_callback(line)

    def get_text(self):
        """获取完整日志文本。"""
        with self._lock:
            return "\n".join(self._lines)

    def clear(self):
        """清空日志。"""
        with self._lock:
            self._lines.clear()

    def export(self, file_path):
        """导出日志到本地 txt 文件。"""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self.get_text())
            return True
        except Exception as e:
            self.log(f"导出日志失败: {e}", "ERROR")
            return False


# ============================================================
# 扫描类：负责发现并统计各类垃圾文件
# ============================================================
class JunkScanner:
    """多线程异步扫描器，支持停止扫描。"""

    # 分类定义：key -> 显示名称/说明/安全级别
    CATEGORIES = {
        "user_temp": {
            "name": "用户临时文件 (%TEMP%)",
            "desc": "当前用户临时目录中的缓存与临时文件",
            "safe": True,
        },
        "windows_temp": {
            "name": "Windows 系统临时文件 (C:\\Windows\\Temp)",
            "desc": "Windows 系统级临时目录，通常需要管理员权限",
            "safe": True,
        },
        "edge_cache": {
            "name": "Microsoft Edge 浏览器缓存",
            "desc": "Edge 浏览器默认用户配置缓存",
            "safe": True,
        },
        "chrome_cache": {
            "name": "Google Chrome 浏览器缓存",
            "desc": "Chrome 浏览器默认用户配置缓存",
            "safe": True,
        },
        "download_temp": {
            "name": "浏览器下载缓存 / 临时下载文件",
            "desc": "浏览器下载过程中产生的临时文件",
            "safe": True,
        },
        "recycle_bin": {
            "name": "回收站",
            "desc": "回收站中的已删除文件（清理后不可恢复）",
            "safe": True,
            "special": True,
        },
        "log_files": {
            "name": "系统与应用程序日志文件",
            "desc": "Windows 及常见程序产生的 .log 日志",
            "safe": True,
        },
        "update_cache": {
            "name": "Windows 更新缓存",
            "desc": "SoftwareDistribution\\Download 目录中的更新安装包",
            "safe": True,
        },
        "thumbnail_cache": {
            "name": "缩略图缓存",
            "desc": "Windows 资源管理器生成的缩略图数据库",
            "safe": True,
        },
    }

    def __init__(self, logger):
        self.logger = logger
        self.stop_event = threading.Event()
        self.results = {}

    def stop(self):
        """请求停止扫描。"""
        self.stop_event.set()

    def reset(self):
        """重置扫描状态。"""
        self.stop_event.clear()
        self.results = {}

    def _safe_iterdir(self, path):
        """安全遍历目录，捕获权限/不存在等异常。"""
        try:
            p = Path(path)
            if not p.exists():
                return []
            return list(p.rglob("*"))
        except PermissionError:
            self.logger.log(f"无权限访问目录: {path}", "WARN")
            return []
        except Exception as e:
            self.logger.log(f"遍历目录失败 {path}: {e}", "WARN")
            return []

    def _calc_size_and_files(self, entries):
        """计算文件列表的总大小与数量，返回 (total_size, file_count, sample_files)。"""
        total_size = 0
        file_count = 0
        samples = []
        for entry in entries:
            if self.stop_event.is_set():
                break
            try:
                if entry.is_file():
                    size = entry.stat().st_size
                    total_size += size
                    file_count += 1
                    if len(samples) < 20:
                        samples.append((str(entry), size))
            except (PermissionError, OSError, FileNotFoundError):
                continue
            except Exception:
                continue
        return total_size, file_count, samples

    def _scan_user_temp(self):
        """扫描用户临时目录。"""
        temp_dir = os.environ.get("TEMP") or tempfile.gettempdir()
        entries = self._safe_iterdir(temp_dir)
        return self._calc_size_and_files(entries)

    def _scan_windows_temp(self):
        """扫描 Windows 系统临时目录。"""
        path = r"C:\Windows\Temp"
        entries = self._safe_iterdir(path)
        return self._calc_size_and_files(entries)

    def _scan_edge_cache(self):
        """扫描 Edge 缓存目录。"""
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        paths = [
            os.path.join(local_appdata, r"Microsoft\Edge\User Data\Default\Cache"),
            os.path.join(local_appdata, r"Microsoft\Edge\User Data\Default\Code Cache"),
        ]
        entries = []
        for p in paths:
            entries.extend(self._safe_iterdir(p))
        return self._calc_size_and_files(entries)

    def _scan_chrome_cache(self):
        """扫描 Chrome 缓存目录。"""
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        paths = [
            os.path.join(local_appdata, r"Google\Chrome\User Data\Default\Cache"),
            os.path.join(local_appdata, r"Google\Chrome\User Data\Default\Code Cache"),
        ]
        entries = []
        for p in paths:
            entries.extend(self._safe_iterdir(p))
        return self._calc_size_and_files(entries)

    def _scan_download_temp(self):
        """扫描浏览器下载临时文件。"""
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        paths = [
            os.path.join(local_appdata, r"Microsoft\Edge\User Data\Default\Downloads"),
            os.path.join(local_appdata, r"Google\Chrome\User Data\Default\Downloads"),
            os.path.join(os.environ.get("TEMP", ""), "*.crdownload"),
            os.path.join(os.environ.get("TEMP", ""), "*.partial"),
        ]
        entries = []
        for p in paths:
            if p.endswith("*"):
                entries.extend(Path(p).parent.glob(Path(p).name))
            else:
                entries.extend(self._safe_iterdir(p))
        return self._calc_size_and_files(entries)

    def _scan_recycle_bin(self):
        """扫描回收站内容。"""
        entries = self._safe_iterdir(r"C:\$Recycle.Bin")
        return self._calc_size_and_files(entries)

    def _scan_log_files(self):
        """扫描常见日志文件。"""
        targets = [
            os.environ.get("TEMP") or tempfile.gettempdir(),
            r"C:\Windows\Temp",
            r"C:\Windows\Logs",
        ]
        entries = []
        for d in targets:
            if not d or not os.path.isdir(d):
                continue
            try:
                for pattern in ("*.log", "*.txt"):
                    entries.extend(Path(d).rglob(pattern))
            except Exception as e:
                self.logger.log(f"扫描日志失败 {d}: {e}", "WARN")
        return self._calc_size_and_files(entries)

    def _scan_update_cache(self):
        """扫描 Windows 更新缓存。"""
        entries = self._safe_iterdir(r"C:\Windows\SoftwareDistribution\Download")
        return self._calc_size_and_files(entries)

    def _scan_thumbnail_cache(self):
        """扫描缩略图缓存数据库。"""
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        path = os.path.join(local_appdata, r"Microsoft\Windows\Explorer")
        entries = []
        if os.path.isdir(path):
            try:
                entries = list(Path(path).glob("thumbcache_*.db"))
            except Exception as e:
                self.logger.log(f"扫描缩略图缓存失败: {e}", "WARN")
        return self._calc_size_and_files(entries)

    def scan_all(self, progress_callback=None):
        """
        执行全部分类扫描。
        progress_callback(current, total, category_name) 用于 UI 刷新。
        返回 dict: category_key -> {name, size, count, samples, safe, special}。
        """
        self.reset()
        scanners = [
            ("user_temp", self._scan_user_temp),
            ("windows_temp", self._scan_windows_temp),
            ("edge_cache", self._scan_edge_cache),
            ("chrome_cache", self._scan_chrome_cache),
            ("download_temp", self._scan_download_temp),
            ("recycle_bin", self._scan_recycle_bin),
            ("log_files", self._scan_log_files),
            ("update_cache", self._scan_update_cache),
            ("thumbnail_cache", self._scan_thumbnail_cache),
        ]
        total = len(scanners)
        for idx, (key, scanner_func) in enumerate(scanners, start=1):
            if self.stop_event.is_set():
                break
            cat_info = self.CATEGORIES.get(key, {})
            if progress_callback:
                progress_callback(idx, total, cat_info.get("name", key))
            self.logger.log(f"正在扫描: {cat_info.get('name', key)}")
            size, count, samples = scanner_func()
            self.results[key] = {
                "key": key,
                "name": cat_info.get("name", key),
                "desc": cat_info.get("desc", ""),
                "safe": cat_info.get("safe", True),
                "special": cat_info.get("special", False),
                "size": size,
                "count": count,
                "samples": samples,
                "selected": True,  # 默认勾选
            }
        return self.results


# ============================================================
# 清理类：负责安全删除选中的垃圾文件
# ============================================================
class JunkCleaner:
    """多线程异步清理器，带进度回调。"""

    def __init__(self, logger):
        self.logger = logger
        self.stop_event = threading.Event()
        self.stats = {"success": 0, "fail": 0, "total_size": 0}

    def stop(self):
        """请求停止清理。"""
        self.stop_event.set()

    def reset(self):
        """重置清理状态。"""
        self.stop_event.clear()
        self.stats = {"success": 0, "fail": 0, "total_size": 0}

    def _delete_file(self, file_path):
        """删除单个文件，捕获常见异常。"""
        try:
            os.remove(file_path)
            return True
        except PermissionError:
            self.logger.log(f"权限不足，跳过: {file_path}", "WARN")
        except FileNotFoundError:
            self.logger.log(f"文件已不存在: {file_path}", "WARN")
        except OSError as e:
            # 文件被占用等
            self.logger.log(f"无法删除（可能正被占用）: {file_path} - {e}", "WARN")
        except Exception as e:
            self.logger.log(f"删除异常: {file_path} - {e}", "ERROR")
        return False

    def _delete_directory(self, dir_path):
        """尝试删除空目录。"""
        try:
            os.rmdir(dir_path)
        except Exception:
            pass  # 非空或权限不足时静默忽略

    def _empty_recycle_bin(self):
        """调用 Windows API 清空回收站。"""
        if _SHEmptyRecycleBinW is not None:
            try:
                # SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
                flags = 0x00000001 | 0x00000002 | 0x00000004
                _SHEmptyRecycleBinW(None, None, flags)
                self.logger.log("回收站已清空", "INFO")
                return True
            except Exception as e:
                self.logger.log(f"调用系统 API 清空回收站失败: {e}", "WARN")
        # 降级方案：尝试手动删除 C:\$Recycle.Bin 下可见内容
        self.logger.log("尝试手动清理回收站内容...", "INFO")
        return False

    def clean(self, scan_results, selected_keys, progress_callback=None):
        """
        执行清理。
        scan_results: JunkScanner.scan_all 的返回结果
        selected_keys: 用户勾选的分类 key 列表
        progress_callback(processed, total, current_path) 用于 UI 刷新
        """
        self.reset()
        # 收集待删除文件清单
        all_files = []
        recycle_bin_selected = False
        for key in selected_keys:
            item = scan_results.get(key)
            if not item:
                continue
            if key == "recycle_bin":
                recycle_bin_selected = True
                # 回收站走系统 API，不单独删除文件
                continue
            for sample in item.get("samples", []):
                all_files.append(sample[0])

        total = len(all_files)
        self.logger.log(f"准备清理 {total} 个文件（回收站单独处理）")

        # 删除普通文件
        for idx, file_path in enumerate(all_files, start=1):
            if self.stop_event.is_set():
                self.logger.log("用户取消清理", "WARN")
                break
            if progress_callback:
                progress_callback(idx, total, file_path)
            if self._delete_file(file_path):
                self.stats["success"] += 1
                try:
                    self.stats["total_size"] += os.path.getsize(file_path) if os.path.exists(file_path) else 0
                except Exception:
                    pass
            else:
                self.stats["fail"] += 1

        # 处理回收站
        if recycle_bin_selected and not self.stop_event.is_set():
            if progress_callback:
                progress_callback(total, total, "正在清空回收站...")
            self.logger.log("开始清空回收站", "INFO")
            if not self._empty_recycle_bin():
                # 手动清理兜底
                for entry in JunkScanner(None)._safe_iterdir(r"C:\$Recycle.Bin"):
                    if self.stop_event.is_set():
                        break
                    if entry.is_file() and self._delete_file(str(entry)):
                        self.stats["success"] += 1
                    elif entry.is_dir():
                        try:
                            shutil.rmtree(str(entry), ignore_errors=True)
                            self.stats["success"] += 1
                        except Exception as e:
                            self.logger.log(f"回收站目录清理失败: {entry} - {e}", "WARN")
                            self.stats["fail"] += 1

        self.logger.log(
            f"清理完成：成功 {self.stats['success']} 个，失败 {self.stats['fail']} 个",
            "INFO",
        )
        return self.stats


# ============================================================
# UI 类：tkinter 主界面
# ============================================================
class SystemClearApp:
    """系统清理工具主窗口。"""

    def __init__(self, root):
        self.root = root
        self.root.title("Windows 系统垃圾清理工具")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        # 窗口居中
        self._center_window()

        # 核心组件
        self.logger = AppLogger(ui_callback=self._on_new_log)
        self.scanner = JunkScanner(self.logger)
        self.cleaner = JunkCleaner(self.logger)

        # 状态变量
        self.scan_results = {}
        self.is_scanning = False
        self.is_cleaning = False
        self.tree_items = {}  # iid -> category_key
        self.checkbox_images = {}

        # 扫描/清理线程
        self._scan_thread = None
        self._clean_thread = None

        self._build_ui()
        self._init_menu()

        self.logger.log("程序已启动，建议先关闭占用临时文件的软件后再扫描清理。", "INFO")

    def _center_window(self):
        """将窗口居中显示。"""
        self.root.update_idletasks()
        width = 900
        height = 700
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _build_ui(self):
        """构建主界面布局。"""
        # 主容器
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=3)  # 垃圾清单区
        main_frame.rowconfigure(3, weight=2)  # 日志区

        # ① 顶部操作区
        top_frame = ttk.Frame(main_frame)
        top_frame.grid(row=0, column=0, sticky=EW, pady=(0, 10))

        self.btn_scan = ttk.Button(
            top_frame, text="开始扫描", command=self._on_start_scan
        )
        self.btn_scan.pack(side=LEFT, padx=5)

        self.btn_export_log = ttk.Button(
            top_frame, text="导出日志", command=self._on_export_log
        )
        self.btn_export_log.pack(side=LEFT, padx=5)

        self.btn_about = ttk.Button(
            top_frame, text="关于", command=self._show_about
        )
        self.btn_about.pack(side=RIGHT, padx=5)

        self.lbl_summary = ttk.Label(top_frame, text="就绪")
        self.lbl_summary.pack(side=LEFT, padx=20)

        # ② 中间垃圾清单区
        list_frame = ttk.LabelFrame(main_frame, text="垃圾文件分类清单", padding=5)
        list_frame.grid(row=1, column=0, sticky=NSEW, pady=(0, 10))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        # Treeview：勾选列、分类、大小、数量、说明
        columns = ("size", "count", "desc")
        self.tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="tree headings",
            selectmode="browse",
        )
        self.tree.heading("#0", text="勾选 / 分类", anchor=W)
        self.tree.heading("size", text="占用大小", anchor=CENTER)
        self.tree.heading("count", text="文件数量", anchor=CENTER)
        self.tree.heading("desc", text="说明", anchor=W)
        self.tree.column("#0", width=260, minwidth=180)
        self.tree.column("size", width=100, anchor=CENTER)
        self.tree.column("count", width=80, anchor=CENTER)
        self.tree.column("desc", width=400, anchor=W)
        self.tree.grid(row=0, column=0, sticky=NSEW)

        # 滚动条
        vsb = ttk.Scrollbar(list_frame, orient=VERTICAL, command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky=NS)
        self.tree.configure(yscrollcommand=vsb.set)

        hsb = ttk.Scrollbar(list_frame, orient=HORIZONTAL, command=self.tree.xview)
        hsb.grid(row=1, column=0, sticky=EW)
        self.tree.configure(xscrollcommand=hsb.set)

        # 点击事件：切换勾选
        self.tree.bind("<Button-1>", self._on_tree_click)

        # ③ 进度展示区
        progress_frame = ttk.LabelFrame(main_frame, text="进度", padding=5)
        progress_frame.grid(row=2, column=0, sticky=EW, pady=(0, 10))
        progress_frame.columnconfigure(0, weight=1)

        self.progress_var = IntVar(value=0)
        self.progress_bar = ttk.Progressbar(
            progress_frame, orient=HORIZONTAL, mode="determinate", variable=self.progress_var
        )
        self.progress_bar.grid(row=0, column=0, sticky=EW, padx=5, pady=5)

        self.lbl_current = ttk.Label(progress_frame, text="等待操作...")
        self.lbl_current.grid(row=1, column=0, sticky=W, padx=5)

        # 开始清理按钮放在进度区右侧
        self.btn_clean = ttk.Button(
            progress_frame, text="开始清理", command=self._on_start_clean, state=DISABLED
        )
        self.btn_clean.grid(row=0, column=1, rowspan=2, padx=5, pady=5)

        # ④ 底部日志区
        log_frame = ttk.LabelFrame(main_frame, text="运行日志", padding=5)
        log_frame.grid(row=3, column=0, sticky=NSEW)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.txt_log = tk.Text(
            log_frame,
            wrap="none",
            state=DISABLED,
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="white",
            font=("Consolas", 10),
        )
        self.txt_log.grid(row=0, column=0, sticky=NSEW)

        log_vsb = ttk.Scrollbar(log_frame, orient=VERTICAL, command=self.txt_log.yview)
        log_vsb.grid(row=0, column=1, sticky=NS)
        self.txt_log.configure(yscrollcommand=log_vsb.set)

        log_hsb = ttk.Scrollbar(log_frame, orient=HORIZONTAL, command=self.txt_log.xview)
        log_hsb.grid(row=1, column=0, sticky=EW)
        self.txt_log.configure(xscrollcommand=log_hsb.set)

    def _init_menu(self):
        """初始化菜单栏。"""
        menubar = Menu(self.root)
        file_menu = Menu(menubar, tearoff=0)
        file_menu.add_command(label="导出日志", command=self._on_export_log)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)
        menubar.add_cascade(label="文件", menu=file_menu)

        help_menu = Menu(menubar, tearoff=0)
        help_menu.add_command(label="关于", command=self._show_about)
        menubar.add_cascade(label="帮助", menu=help_menu)
        self.root.config(menu=menubar)

    def _on_new_log(self, line):
        """UI 日志回调（由 Logger 在新线程调用）。"""
        self.root.after(0, lambda: self._append_log(line))

    def _append_log(self, line):
        """在日志文本框追加一行。"""
        self.txt_log.config(state=NORMAL)
        self.txt_log.insert(END, line + "\n")
        self.txt_log.see(END)
        self.txt_log.config(state=DISABLED)

    def _format_size(self, size_bytes):
        """将字节大小格式化为人类可读字符串。"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 ** 2:
            return f"{size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024 ** 3:
            return f"{size_bytes / (1024 ** 2):.2f} MB"
        else:
            return f"{size_bytes / (1024 ** 3):.2f} GB"

    def _on_tree_click(self, event):
        """处理树形列表点击，切换勾选状态。"""
        region = self.tree.identify_region(event.x, event.y)
        if region not in ("tree", "cell"):
            return
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        key = self.tree_items.get(iid)
        if not key:
            return
        # 仅当点击第一列（勾选列）时才切换
        column = self.tree.identify_column(event.x)
        if column == "#0":
            self._toggle_selection(iid, key)

    def _toggle_selection(self, iid, key):
        """切换某一项的勾选状态。"""
        item = self.scan_results.get(key)
        if not item:
            return
        item["selected"] = not item["selected"]
        self._update_tree_item(iid, item)
        self._update_summary()

    def _update_tree_item(self, iid, item):
        """更新树节点显示（勾选符号）。"""
        checked = "☑" if item["selected"] else "☐"
        self.tree.item(
            iid,
            text=f"{checked} {item['name']}",
            values=(self._format_size(item["size"]), item["count"], item["desc"]),
        )

    def _on_start_scan(self):
        """点击开始扫描。"""
        if self.is_scanning:
            messagebox.showinfo("提示", "扫描正在进行中，请稍候。")
            return
        self.is_scanning = True
        self.btn_scan.config(text="扫描中...", state=DISABLED)
        self.btn_clean.config(state=DISABLED)
        self.tree.delete(*self.tree.get_children())
        self.tree_items.clear()
        self.scan_results.clear()
        self.progress_var.set(0)
        self.lbl_current.config(text="正在初始化扫描...")
        self.logger.clear()
        self.logger.log("开始扫描系统垃圾文件...", "INFO")

        self._scan_thread = threading.Thread(target=self._scan_worker, daemon=True)
        self._scan_thread.start()

    def _scan_worker(self):
        """扫描工作线程。"""
        try:
            results = self.scanner.scan_all(progress_callback=self._scan_progress)
            self.root.after(0, lambda: self._on_scan_finished(results))
        except Exception as e:
            self.logger.log(f"扫描过程发生异常: {e}", "ERROR")
            self.root.after(0, self._on_scan_finished, {})

    def _scan_progress(self, current, total, name):
        """扫描进度回调（工作线程）。"""
        pct = int(current / total * 100) if total > 0 else 0
        self.root.after(0, lambda: self._set_progress(pct, f"正在扫描: {name}"))

    def _on_scan_finished(self, results):
        """扫描完成后的 UI 更新（主线程）。"""
        self.is_scanning = False
        self.scan_results = results
        self._populate_tree()
        self._update_summary()
        self.btn_scan.config(text="开始扫描", state=NORMAL)
        if results:
            self.btn_clean.config(state=NORMAL)
            self.lbl_current.config(text="扫描完成，请勾选需要清理的项目后点击【开始清理】")
            self.logger.log("扫描完成", "INFO")
        else:
            self.lbl_current.config(text="扫描未完成或未获取到结果")
            self.logger.log("扫描未完成", "WARN")
        self.progress_var.set(100)

    def _populate_tree(self):
        """将扫描结果填充到树形列表。"""
        self.tree.delete(*self.tree.get_children())
        self.tree_items.clear()
        for key, item in self.scan_results.items():
            iid = self.tree.insert(
                "",
                END,
                text="",
                values=(self._format_size(item["size"]), item["count"], item["desc"]),
                open=False,
            )
            self.tree_items[iid] = key
            self._update_tree_item(iid, item)
            # 展开显示样例文件
            for sample_path, sample_size in item.get("samples", [])[:5]:
                self.tree.insert(
                    iid,
                    END,
                    text=f"  └─ {os.path.basename(sample_path)}",
                    values=(self._format_size(sample_size), "", sample_path),
                )

    def _update_summary(self):
        """更新顶部汇总信息。"""
        total_size = 0
        total_count = 0
        selected_count = 0
        for item in self.scan_results.values():
            if item.get("selected"):
                total_size += item.get("size", 0)
                total_count += item.get("count", 0)
                selected_count += 1
        self.lbl_summary.config(
            text=f"已选 {selected_count} 项 | 约 {self._format_size(total_size)} | {total_count} 个文件"
        )

    def _on_start_clean(self):
        """点击开始清理，先进行二次确认。"""
        if self.is_cleaning:
            messagebox.showinfo("提示", "清理正在进行中，请稍候。")
            return
        selected_keys = [k for k, v in self.scan_results.items() if v.get("selected")]
        if not selected_keys:
            messagebox.showwarning("警告", "请至少勾选一项需要清理的分类。")
            return

        # 回收站特殊提示
        if "recycle_bin" in selected_keys:
            if not messagebox.askyesno(
                "回收站清理确认",
                "您勾选了【回收站】，清空后文件将无法恢复。\n\n是否继续？",
                icon="warning",
            ):
                return

        # 汇总确认信息
        total_size = 0
        total_count = 0
        detail_lines = []
        for key in selected_keys:
            item = self.scan_results.get(key, {})
            size = item.get("size", 0)
            count = item.get("count", 0)
            total_size += size
            total_count += count
            detail_lines.append(f"  • {item.get('name', key)}：{self._format_size(size)}，{count} 个文件")

        confirm_msg = (
            "请确认以下清理操作：\n\n"
            f"即将清理文件总数：{total_count}\n"
            f"预计释放空间：{self._format_size(total_size)}\n"
            f"勾选项目数：{len(selected_keys)}\n\n"
            "勾选项目清单：\n" + "\n".join(detail_lines) + "\n\n"
            "注意：临时文件将被直接删除，回收站内容将被清空。\n"
            "此操作不可撤销，是否继续？"
        )
        if not messagebox.askyesno("二次确认", confirm_msg, icon="warning"):
            self.logger.log("用户取消清理", "INFO")
            return

        # 开始清理
        self.is_cleaning = True
        self.btn_clean.config(text="清理中...", state=DISABLED)
        self.btn_scan.config(state=DISABLED)
        self.progress_var.set(0)
        self.lbl_current.config(text="正在准备清理...")
        self.logger.log("用户确认清理，开始执行删除...", "INFO")

        self._clean_thread = threading.Thread(
            target=self._clean_worker, args=(selected_keys,), daemon=True
        )
        self._clean_thread.start()

    def _clean_worker(self, selected_keys):
        """清理工作线程。"""
        try:
            stats = self.cleaner.clean(
                self.scan_results,
                selected_keys,
                progress_callback=self._clean_progress,
            )
            self.root.after(0, lambda: self._on_clean_finished(stats))
        except Exception as e:
            self.logger.log(f"清理过程发生异常: {e}", "ERROR")
            self.root.after(0, self._on_clean_finished, None)

    def _clean_progress(self, processed, total, current_path):
        """清理进度回调（工作线程）。"""
        pct = int(processed / total * 100) if total > 0 else 0
        display = current_path if len(current_path) < 80 else "..." + current_path[-77:]
        self.root.after(0, lambda: self._set_progress(pct, f"[{processed}/{total}] {display}"))

    def _on_clean_finished(self, stats):
        """清理完成后的 UI 更新（主线程）。"""
        self.is_cleaning = False
        self.btn_clean.config(text="开始清理", state=NORMAL)
        self.btn_scan.config(state=NORMAL)
        if stats:
            self.lbl_current.config(
                text=f"清理完成：成功 {stats['success']} 个，失败 {stats['fail']} 个"
            )
            self.progress_var.set(100)
        else:
            self.lbl_current.config(text="清理过程出现异常")
        # 清理完成后重新扫描一次，刷新列表
        self.logger.log("建议重新扫描以查看最新状态。", "INFO")

    def _set_progress(self, value, text):
        """设置进度条和当前文件文本。"""
        self.progress_var.set(value)
        self.lbl_current.config(text=text)

    def _on_export_log(self):
        """导出日志按钮。"""
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            initialfile=f"system_clear_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        )
        if not path:
            return
        if self.logger.export(path):
            messagebox.showinfo("导出成功", f"日志已保存到:\n{path}")
        else:
            messagebox.showerror("导出失败", "无法保存日志文件，请检查路径权限。")

    def _show_about(self):
        """显示关于窗口。"""
        about = Toplevel(self.root)
        about.title("关于")
        about.geometry("400x250")
        about.resizable(False, False)
        about.transient(self.root)
        about.grab_set()
        self._center_child(about)

        ttk.Label(
            about,
            text="Windows 系统垃圾清理工具",
            font=("Microsoft YaHei", 14, "bold"),
        ).pack(pady=15)

        ttk.Label(
            about,
            text="适配系统：Windows 10 / Windows 11\n"
                 "开发框架：Python 3.x + tkinter\n"
                 "开源/自用工具，请谨慎操作重要数据。",
            justify=CENTER,
        ).pack(pady=5)

        ttk.Button(about, text="确定", command=about.destroy).pack(pady=20)

    def _center_child(self, child):
        """将子窗口居中于父窗口。"""
        self.root.update_idletasks()
        child.update_idletasks()
        px = self.root.winfo_x() + (self.root.winfo_width() - child.winfo_width()) // 2
        py = self.root.winfo_y() + (self.root.winfo_height() - child.winfo_height()) // 2
        child.geometry(f"+{px}+{py}")


def main():
    """程序入口。"""
    root = Tk()
    # 尝试设置 DPI 感知（Windows 高分辨率屏幕）
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    app = SystemClearApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
