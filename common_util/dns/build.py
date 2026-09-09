# -*- coding: utf-8 -*-
"""
DNS 缓存清理工具 - PyInstaller 打包脚本
运行后将在 dist/ 目录生成 DnsFlush.exe
"""

import os
import sys
import shutil


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def create_icon_ico():
    """生成一个简单的图标文件（如果 Pillow 可用）。"""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("未安装 Pillow，将使用 PyInstaller 默认图标。")
        return None

    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    images = []
    for size in sizes:
        image = Image.new("RGB", size, color=(52, 152, 219))
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("arial.ttf", size[0] // 2)
        except Exception:
            font = ImageFont.load_default()
        draw.text(
            (size[0] // 2, size[1] // 2), "D",
            font=font, fill="white", anchor="mm",
        )
        images.append(image)

    icon_path = os.path.join(BASE_DIR, "icon.ico")
    images[0].save(icon_path, format="ICO", sizes=sizes, append_images=images[1:])
    print(f"图标已生成: {icon_path}")
    return icon_path


def main():
    os.chdir(BASE_DIR)

    # 清理旧构建
    for folder in ("build", "dist"):
        if os.path.isdir(folder):
            shutil.rmtree(folder)
            print(f"已清理旧目录: {folder}")

    try:
        import PyInstaller.__main__
    except ImportError as e:
        print(f"缺少 PyInstaller：{e}")
        print('请先安装依赖：python -m pip install -r requirements.txt')
        sys.exit(1)

    icon_path = create_icon_ico()
    script = os.path.join(BASE_DIR, "dns_flush.py")

    args = [
        script,
        "--onefile",
        "--noconsole",
        "--name", "DnsFlush",
        "--clean",
        "--noconfirm",
    ]
    if icon_path and os.path.exists(icon_path):
        args.extend(["--icon", icon_path])

    print("开始打包...")
    PyInstaller.__main__.run(args)
    print("打包完成，可执行文件位于 dist/DnsFlush.exe")


if __name__ == "__main__":
    main()