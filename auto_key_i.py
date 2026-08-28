import time
import random
import threading
import logging
import sys
import ctypes
import psutil
from pynput.keyboard import Controller, Listener, Key


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("AutoKeyI")


user32 = ctypes.windll.user32


def get_foreground_window_title():
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


# 游戏识别配置，可根据实际情况调整
GAME_PROCESS_NAMES = ["WhereWindsMeet.exe", "燕云十六声.exe", "wwm.exe"]
GAME_WINDOW_KEYWORDS = ["燕云十六声", "Where Winds Meet", "WWM"]


def is_game_running():
    for proc in psutil.process_iter(["name"]):
        try:
            name = proc.info["name"]
            if name and any(p.lower() == name.lower() for p in GAME_PROCESS_NAMES):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def is_game_focused():
    title = get_foreground_window_title()
    return any(kw in title for kw in GAME_WINDOW_KEYWORDS)


class AutoKeyI:
    def __init__(self):
        self.running = False
        self.thread = None
        self.keyboard = Controller()
        self.lock = threading.Lock()
        self.interval = 7.0
        self.jitter = 0.5
        self.stop_event = threading.Event()

    def start(self):
        with self.lock:
            if self.running:
                logger.info("已经在运行中")
                return
            if not is_game_running():
                logger.warning("未检测到《燕云十六声》游戏进程，请先启动游戏")
                return
            self.running = True
            self.stop_event.clear()
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()
            logger.info("已启动，约每 7 秒按一次 I 键（F10 停止）")

    def stop(self):
        with self.lock:
            if not self.running:
                return
            self.running = False
            self.stop_event.set()
            if self.thread:
                self.thread.join(timeout=2)
            logger.info("已停止")

    def _loop(self):
        while not self.stop_event.is_set():
            if not is_game_running():
                logger.warning("游戏进程已消失，自动停止")
                self.stop()
                break

            if not is_game_focused():
                logger.info("游戏窗口未激活，跳过本次按键")
                if self.stop_event.wait(1):
                    break
                continue

            # 模拟真实按键，按下与释放之间加入随机小延迟
            self.keyboard.press("i")
            time.sleep(random.uniform(0.05, 0.15))
            self.keyboard.release("i")
            logger.info("已按下 I 键")

            # 随机间隔 6.5 ~ 7.5 秒，降低被判定为机械操作的风险
            sleep_time = self.interval + random.uniform(-self.jitter, self.jitter)
            if self.stop_event.wait(sleep_time):
                break


auto = AutoKeyI()


def on_press(key):
    try:
        if key == Key.f9:
            auto.start()
        elif key == Key.f10:
            auto.stop()
        elif key == Key.f12:
            logger.info("F12 被按下，正在退出程序")
            auto.stop()
            return False
    except Exception as e:
        logger.error(f"热键处理异常: {e}")


if __name__ == "__main__":
    print("=" * 55)
    print("《燕云十六声》自动按 I 工具")
    print("=" * 55)
    print("F9  : 启动")
    print("F10 : 停止")
    print("F12 : 退出")
    print("=" * 55)

    with Listener(on_press=on_press) as listener:
        listener.join()

    logger.info("程序已退出")
