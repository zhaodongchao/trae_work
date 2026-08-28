import time
import random
import threading
import logging
import sys
from pynput.keyboard import Controller, Listener, Key


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
        self.lock = threading.Lock()
        self.interval = 7.0
        self.jitter = 0.5
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
    print("自动按 I 工具")
    print("=" * 55)
    print("F9  : 启动")
    print("F10 : 停止")
    print("F12 : 退出")
    print("=" * 55)

    with Listener(on_press=on_press) as listener:
        listener.join()

    logger.info("程序已退出")
