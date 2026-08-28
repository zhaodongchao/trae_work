import json
import os
import sys
import time
import random
import threading
import logging
from datetime import datetime

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
            self.keyboard.press(key)
            time.sleep(press_duration)
            self.keyboard.release(key)
            logger.info(f"已按下 {key.upper()} 键，持续 {press_duration:.3f} 秒")

            self._jitter_mouse()

            sleep_time = interval + random.uniform(-jitter, jitter)
            if self.stop_event.wait(max(0.5, sleep_time)):
                break


auto = AutoKey()
tray_icon = None


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


def start_action(icon, item):
    auto.start()


def stop_action(icon, item):
    auto.stop()


def exit_action(icon, item):
    logger.info("通过托盘退出")
    auto.stop()
    icon.stop()


def setup_tray(icon):
    icon.visible = True
    threading.Thread(target=listen_hotkeys, daemon=True).start()


def listen_hotkeys():
    with Listener(on_press=on_press) as listener:
        listener.join()


def main():
    global tray_icon
    menu = pystray.Menu(
        pystray.MenuItem("启动 (F9)", start_action),
        pystray.MenuItem("停止 (F10)", stop_action),
        pystray.MenuItem("退出 (F12)", exit_action),
    )
    tray_icon = pystray.Icon("AutoKeyI", create_icon_image(), "自动按 I 工具", menu)
    tray_icon.run(setup=setup_tray)


if __name__ == "__main__":
    main()
