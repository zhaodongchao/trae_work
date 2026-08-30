# -*- coding: utf-8 -*-
"""
Windows 系统垃圾清理工具 - PyInstaller 打包脚本
运行后将在 dist/ 目录生成 SystemClear.exe
"""

import os
import sys
import shutil


def create_icon_ico():
    """生成一个简单的图标文件（如果 Pillow 可用）。"""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("未安装 Pillow，跳过自定义图标生成，将使用 PyInstaller 默认图标。")
        return None

    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    images = []
    for size in sizes:
        image = Image.new("RGB", size, color=(0, 120, 212))
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("arial.ttf", size[0] // 2)
        except Exception:
            font = ImageFont.load_default()
        draw.text((size[0] // 2, size[1] // 2), "C", font=font, fill="white", anchor="mm")
        images.append(image)

    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
    images[0].save(icon_path, format="ICO", sizes=sizes, append_images=images[1:])
    print(f"图标已生成: {icon_path}")
    return icon_path


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)

    # 清理旧构建
    for folder in ("build", "dist"):
        if os.path.isdir(folder):
            shutil.rmtree(folder)
            print(f"已清理旧目录: {folder}")

    # 检查 PyInstaller
    try:
        import PyInstaller.__main__
    except ImportError:
        print("错误：未安装 PyInstaller，请先执行：pip install pyinstaller")
        sys.exit(1)

    icon_path = create_icon_ico()
    script_path = os.path.join(base_dir, "system_clear.py")

    args = [
        script_path,
        "--onefile",
        "--noconsole",
        "--name", "SystemClear",
        "--clean",
        "--noconfirm",
    ]
    if icon_path and os.path.exists(icon_path):
        args.extend(["--icon", icon_path])

    print("开始打包...")
    PyInstaller.__main__.run(args)
    print("打包完成，可执行文件位于 dist/SystemClear.exe")


if __name__ == "__main__":
    main()
