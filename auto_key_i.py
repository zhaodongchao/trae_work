import time
import random
import threading
import logging
import sys
from pynput.keyboard import Controller, Listener, Key
from pynput.mouse import Controller as MouseController


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("AutoKeyI")


class AutoKeyI:
    def __init__(self):
        self.running = False
        self.thread = None
        self.keyboard = Controller()
        self.mouse = MouseController()
        self.lock = threading.Lock()
        self.interval = 7.0
        self.jitter = 1.0
        self.stop_event = threading.Event()

    def start(self):
        with self.lock:
            if self.running:
                logger.info("已经在运行中")
                return
            self.running = True
            self.stop_event.clear()
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()
            logger.info("已启动，约每 6~8 秒随机按一次 I 键（F10 停止）")

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
        try:
            dx = random.randint(-8, 8)
            dy = random.randint(-8, 8)
            self.mouse.move(dx, dy)
            time.sleep(random.uniform(0.03, 0.12))
            self.mouse.move(-dx, -dy)
        except Exception as e:
            logger.debug(f"鼠标抖动失败: {e}")

    def _loop(self):
        while not self.stop_event.is_set():
            # 随机按键时长 0.05 ~ 0.25 秒
            press_duration = random.uniform(0.05, 0.25)
            self.keyboard.press("i")
            time.sleep(press_duration)
            self.keyboard.release("i")
            logger.info("已按下 I 键，持续 %.3f 秒", press_duration)

            # 每次按键后随机轻微移动鼠标，模拟真人操作
            self._jitter_mouse()

            # 随机间隔 6.0 ~ 8.0 秒，避免固定节奏
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
    print("自动按 I 工具")
    print("=" * 55)
    print("F9  : 启动")
    print("F10 : 停止")
    print("F12 : 退出")
    print("=" * 55)

    with Listener(on_press=on_press) as listener:
        listener.join()

    logger.info("程序已退出")
