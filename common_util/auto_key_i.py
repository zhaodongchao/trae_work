import json
import os
import sys
import time
import random
import threading
import logging
import queue
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox

from PIL import Image, ImageDraw, ImageFont
import pystray
from pynput.keyboard import Controller, Listener, Key
from pynput.mouse import Controller as MouseController


def app_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def load_config(filename="config.json"):
    defaults = {
        "key": "i",
        "interval": 7.0,
        "jitter": 1.0,
        "press_duration_min": 0.05,
        "press_duration_max": 0.25,
        "mouse_jitter_enabled": True,
        "mouse_jitter_range": 8,
        "mouse_jitter_delay_min": 0.03,
        "mouse_jitter_delay_max": 0.12,
        "combo_keys": [],
        "hotkey_start": "f9",
        "hotkey_stop": "f10",
        "hotkey_exit": "f12",
        "auto_stop_minutes": 0,
        "log_to_file": True,
        "log_file": "auto_key_i.log",
    }
    path = os.path.join(app_base_dir(), filename)
    if not os.path.exists(path) and getattr(sys, "frozen", False):
        path = os.path.join(sys._MEIPASS, filename)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            defaults.update(cfg)
        except Exception as e:
            print(f"读取配置文件失败: {e}，使用默认配置")
    return defaults


CFG = load_config()


def setup_logging():
    handlers = [logging.StreamHandler(sys.stdout)]
    if CFG.get("log_to_file"):
        log_path = os.path.join(app_base_dir(), CFG.get("log_file", "auto_key_i.log"))
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
    )


setup_logging()
logger = logging.getLogger("AutoKeyI")


def parse_key(name):
    try:
        return Key[name.lower()]
    except KeyError:
        return None


def key_to_controller_arg(name):
    name = name.strip().lower()
    if len(name) == 1:
        return name
    special = parse_key(name)
    if special is not None:
        return special
    return name


class AutoKey:
    def __init__(self):
        self.running = False
        self.thread = None
        self.keyboard = Controller()
        self.mouse = MouseController()
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.start_time = None

    def start(self):
        with self.lock:
            if self.running:
                logger.info("已经在运行中")
                return
            self.running = True
            self.stop_event.clear()
            self.start_time = datetime.now()
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()
            logger.info("已启动")

    def stop(self):
        with self.lock:
            if not self.running:
                return
            self.running = False
            self.stop_event.set()
            if self.thread:
                self.thread.join(timeout=2)
            logger.info("已停止")

    def _jitter_mouse(self):
        if not CFG.get("mouse_jitter_enabled", True):
            return
        try:
            r = CFG.get("mouse_jitter_range", 8)
            dx = random.randint(-r, r)
            dy = random.randint(-r, r)
            self.mouse.move(dx, dy)
            time.sleep(random.uniform(
                CFG.get("mouse_jitter_delay_min", 0.03),
                CFG.get("mouse_jitter_delay_max", 0.12),
            ))
            self.mouse.move(-dx, -dy)
        except Exception as e:
            logger.debug(f"鼠标抖动失败: {e}")

    def _loop(self):
        key = CFG.get("key", "i")
        interval = CFG.get("interval", 7.0)
        jitter = CFG.get("jitter", 1.0)
        press_min = CFG.get("press_duration_min", 0.05)
        press_max = CFG.get("press_duration_max", 0.25)
        auto_stop = CFG.get("auto_stop_minutes", 0)

        while not self.stop_event.is_set():
            if auto_stop > 0 and self.start_time:
                elapsed = (datetime.now() - self.start_time).total_seconds() / 60
                if elapsed >= auto_stop:
                    logger.info(f"已达到设定运行时间 {auto_stop} 分钟，自动停止")
                    self.stop()
                    break

            press_duration = random.uniform(press_min, press_max)
            combo_names = [n.lower() for n in CFG.get("combo_keys", [])]
            combo_keys = [k for name in combo_names for k in [parse_key(name)] if k is not None]
            target = key_to_controller_arg(key)
            all_keys = combo_keys + [target]

            for k in all_keys:
                self.keyboard.press(k)
            time.sleep(press_duration)
            for k in reversed(all_keys):
                self.keyboard.release(k)

            combo_str = "+".join(combo_names).upper()
            key_label = key.upper()
            display_key = f"{combo_str}+{key_label}" if combo_str else key_label
            logger.info(f"已按下 {display_key} 键，持续 {press_duration:.3f} 秒")

            self._jitter_mouse()

            sleep_time = interval + random.uniform(-jitter, jitter)
            if self.stop_event.wait(max(0.5, sleep_time)):
                break


auto = AutoKey()
tray_icon = None


class QueueHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        try:
            self.log_queue.put(self.format(record))
        except Exception:
            pass


def create_icon_image():
    width = 64
    height = 64
    image = Image.new("RGB", (width, height), color=(30, 120, 220))
    dc = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 36)
    except Exception:
        font = ImageFont.load_default()
    dc.text((width // 2, height // 2), CFG.get("key", "i").upper(), font=font, fill="white", anchor="mm")
    return image


class AppUI:
    def __init__(self, root):
        self.root = root
        self.root.title("自动按键工具")
        self.root.geometry("520x620")
        self.root.resizable(False, False)
        self.log_queue = queue.Queue()
        self._build_ui()
        self._apply_config()
        self._add_log_handler()
        self._start_tray()
        self._poll_log()
        self._poll_status()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="按键:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.entry_key = ttk.Entry(frame, width=10)
        self.entry_key.grid(row=0, column=1, sticky=tk.W, pady=5)

        self.var_ctrl = tk.BooleanVar()
        self.var_shift = tk.BooleanVar()
        self.var_alt = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Ctrl", variable=self.var_ctrl).grid(row=0, column=2, sticky=tk.W, pady=5, padx=(10, 0))
        ttk.Checkbutton(frame, text="Shift", variable=self.var_shift).grid(row=0, column=3, sticky=tk.W, pady=5)
        ttk.Checkbutton(frame, text="Alt", variable=self.var_alt).grid(row=0, column=4, sticky=tk.W, pady=5)

        ttk.Label(frame, text="间隔(秒):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.entry_interval = ttk.Entry(frame, width=10)
        self.entry_interval.grid(row=1, column=1, sticky=tk.W, pady=5)

        ttk.Label(frame, text="浮动(秒):").grid(row=1, column=2, sticky=tk.W, pady=5, padx=(10, 0))
        self.entry_jitter = ttk.Entry(frame, width=10)
        self.entry_jitter.grid(row=1, column=3, sticky=tk.W, pady=5)

        ttk.Label(frame, text="按键时长最小(秒):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.entry_press_min = ttk.Entry(frame, width=10)
        self.entry_press_min.grid(row=2, column=1, sticky=tk.W, pady=5)

        ttk.Label(frame, text="最大(秒):").grid(row=2, column=2, sticky=tk.W, pady=5, padx=(10, 0))
        self.entry_press_max = ttk.Entry(frame, width=10)
        self.entry_press_max.grid(row=2, column=3, sticky=tk.W, pady=5)

        self.var_mouse = tk.BooleanVar()
        ttk.Checkbutton(frame, text="启用鼠标抖动", variable=self.var_mouse).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=5)

        ttk.Label(frame, text="抖动范围(像素):").grid(row=3, column=2, sticky=tk.W, pady=5, padx=(10, 0))
        self.entry_mouse_range = ttk.Entry(frame, width=10)
        self.entry_mouse_range.grid(row=3, column=3, sticky=tk.W, pady=5)

        ttk.Label(frame, text="启动热键:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.entry_hotkey_start = ttk.Entry(frame, width=10)
        self.entry_hotkey_start.grid(row=4, column=1, sticky=tk.W, pady=5)

        ttk.Label(frame, text="停止热键:").grid(row=4, column=2, sticky=tk.W, pady=5, padx=(10, 0))
        self.entry_hotkey_stop = ttk.Entry(frame, width=10)
        self.entry_hotkey_stop.grid(row=4, column=3, sticky=tk.W, pady=5)

        ttk.Label(frame, text="退出热键:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.entry_hotkey_exit = ttk.Entry(frame, width=10)
        self.entry_hotkey_exit.grid(row=5, column=1, sticky=tk.W, pady=5)

        ttk.Label(frame, text="自动停止(分钟,0=不限制):").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.entry_auto_stop = ttk.Entry(frame, width=10)
        self.entry_auto_stop.grid(row=6, column=1, sticky=tk.W, pady=5)

        self.var_log = tk.BooleanVar()
        ttk.Checkbutton(frame, text="保存日志到文件", variable=self.var_log).grid(row=7, column=0, columnspan=2, sticky=tk.W, pady=5)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=8, column=0, columnspan=4, pady=15)

        self.btn_start = ttk.Button(btn_frame, text="启动 (F9)", command=self._start)
        self.btn_start.pack(side=tk.LEFT, padx=5)

        self.btn_stop = ttk.Button(btn_frame, text="停止 (F10)", command=self._stop)
        self.btn_stop.pack(side=tk.LEFT, padx=5)

        self.btn_save = ttk.Button(btn_frame, text="保存配置", command=self._save_config)
        self.btn_save.pack(side=tk.LEFT, padx=5)

        self.btn_minimize = ttk.Button(btn_frame, text="最小化到托盘", command=self._minimize_to_tray)
        self.btn_minimize.pack(side=tk.LEFT, padx=5)

        self.lbl_status = ttk.Label(frame, text="状态: 已停止", foreground="gray")
        self.lbl_status.grid(row=9, column=0, columnspan=4, sticky=tk.W, pady=5)

        ttk.Label(frame, text="运行日志:").grid(row=10, column=0, sticky=tk.W, pady=5)
        self.log_text = tk.Text(frame, height=12, state=tk.DISABLED)
        self.log_text.grid(row=11, column=0, columnspan=4, sticky=tk.NSEW)
        scrollbar = ttk.Scrollbar(frame, command=self.log_text.yview)
        scrollbar.grid(row=11, column=4, sticky=tk.NS)
        self.log_text.config(yscrollcommand=scrollbar.set)

        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)
        frame.rowconfigure(11, weight=1)

    def _apply_config(self):
        self.entry_key.insert(0, CFG.get("key", "i"))
        combo_keys = [k.lower() for k in CFG.get("combo_keys", [])]
        self.var_ctrl.set("ctrl" in combo_keys)
        self.var_shift.set("shift" in combo_keys)
        self.var_alt.set("alt" in combo_keys)
        self.entry_interval.insert(0, str(CFG.get("interval", 7.0)))
        self.entry_jitter.insert(0, str(CFG.get("jitter", 1.0)))
        self.entry_press_min.insert(0, str(CFG.get("press_duration_min", 0.05)))
        self.entry_press_max.insert(0, str(CFG.get("press_duration_max", 0.25)))
        self.var_mouse.set(CFG.get("mouse_jitter_enabled", True))
        self.entry_mouse_range.insert(0, str(CFG.get("mouse_jitter_range", 8)))
        self.entry_hotkey_start.insert(0, CFG.get("hotkey_start", "f9"))
        self.entry_hotkey_stop.insert(0, CFG.get("hotkey_stop", "f10"))
        self.entry_hotkey_exit.insert(0, CFG.get("hotkey_exit", "f12"))
        self.entry_auto_stop.insert(0, str(CFG.get("auto_stop_minutes", 0)))
        self.var_log.set(CFG.get("log_to_file", True))

    def _read_config_from_ui(self):
        try:
            interval = float(self.entry_interval.get())
            jitter = float(self.entry_jitter.get())
            press_min = float(self.entry_press_min.get())
            press_max = float(self.entry_press_max.get())
            mouse_range = int(self.entry_mouse_range.get())
            auto_stop = int(self.entry_auto_stop.get())
        except ValueError:
            raise ValueError("请输入有效的数字")

        key = self.entry_key.get().strip().lower()
        if not key:
            raise ValueError("按键不能为空")

        combo_keys = []
        if self.var_ctrl.get():
            combo_keys.append("ctrl")
        if self.var_shift.get():
            combo_keys.append("shift")
        if self.var_alt.get():
            combo_keys.append("alt")

        return {
            "key": key,
            "combo_keys": combo_keys,
            "interval": interval,
            "jitter": jitter,
            "press_duration_min": press_min,
            "press_duration_max": press_max,
            "mouse_jitter_enabled": self.var_mouse.get(),
            "mouse_jitter_range": mouse_range,
            "hotkey_start": self.entry_hotkey_start.get().strip().lower(),
            "hotkey_stop": self.entry_hotkey_stop.get().strip().lower(),
            "hotkey_exit": self.entry_hotkey_exit.get().strip().lower(),
            "auto_stop_minutes": auto_stop,
            "log_to_file": self.var_log.get(),
            "log_file": CFG.get("log_file", "auto_key_i.log"),
        }

    def _save_config(self):
        try:
            new_cfg = self._read_config_from_ui()
            global CFG
            CFG = new_cfg
            path = os.path.join(app_base_dir(), "config.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(CFG, f, ensure_ascii=False, indent=2)
            logger.info("配置已保存")
            messagebox.showinfo("保存成功", "配置已保存到 config.json")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def _start(self):
        auto.start()

    def _stop(self):
        auto.stop()

    def _update_status(self):
        if auto.running:
            self.lbl_status.config(text="状态: 运行中", foreground="green")
        else:
            self.lbl_status.config(text="状态: 已停止", foreground="gray")

    def _add_log_handler(self):
        handler = QueueHandler(self.log_queue)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(handler)

    def _poll_log(self):
        while not self.log_queue.empty():
            try:
                msg = self.log_queue.get_nowait()
                self.log_text.config(state=tk.NORMAL)
                self.log_text.insert(tk.END, msg + "\n")
                self.log_text.see(tk.END)
                self.log_text.config(state=tk.DISABLED)
            except Exception:
                pass
        self.root.after(200, self._poll_log)

    def _poll_status(self):
        self._update_status()
        self.root.after(200, self._poll_status)

    def _minimize_to_tray(self):
        self.root.withdraw()

    def _show_window(self):
        self.root.after(0, self.root.deiconify)

    def _on_close(self):
        self.root.withdraw()

    def _exit_app(self):
        auto.stop()
        if tray_icon:
            tray_icon.stop()
        self.root.after(0, self.root.destroy)

    def _start_tray(self):
        threading.Thread(target=self._run_tray, daemon=True).start()

    def _run_tray(self):
        global tray_icon
        menu = pystray.Menu(
            pystray.MenuItem("显示窗口", lambda icon, item: self._show_window()),
            pystray.MenuItem("启动", lambda icon, item: auto.start()),
            pystray.MenuItem("停止", lambda icon, item: auto.stop()),
            pystray.MenuItem("退出", lambda icon, item: self._exit_app()),
        )
        tray_icon = pystray.Icon("AutoKeyI", create_icon_image(), "自动按键工具", menu)
        tray_icon.run()


def on_press(key):
    try:
        start_key = parse_key(CFG.get("hotkey_start", "f9"))
        stop_key = parse_key(CFG.get("hotkey_stop", "f10"))
        exit_key = parse_key(CFG.get("hotkey_exit", "f12"))

        if key == start_key:
            auto.start()
        elif key == stop_key:
            auto.stop()
        elif key == exit_key:
            logger.info("热键退出程序")
            auto.stop()
            if tray_icon:
                tray_icon.stop()
            return False
    except Exception as e:
        logger.error(f"热键处理异常: {e}")


def listen_hotkeys():
    with Listener(on_press=on_press) as listener:
        listener.join()


def main():
    threading.Thread(target=listen_hotkeys, daemon=True).start()

    root = tk.Tk()
    app = AppUI(root)
    root.mainloop()
    logger.info("程序已退出")


if __name__ == "__main__":
    main()
