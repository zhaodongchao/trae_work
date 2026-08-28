import os
import sys

from PIL import Image, ImageDraw, ImageFont


def create_icon_ico():
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    images = []
    for size in sizes:
        image = Image.new("RGB", size, color=(30, 120, 220))
        dc = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("arial.ttf", size[0] // 2)
        except Exception:
            font = ImageFont.load_default()
        dc.text((size[0] // 2, size[1] // 2), "I", font=font, fill="white", anchor="mm")
        images.append(image)
    images[0].save("icon.ico", format="ICO", sizes=sizes, append_images=images[1:])
    print("已生成 icon.ico")


def main():
    create_icon_ico()

    import PyInstaller.__main__

    args = [
        "auto_key_i.py",
        "--onefile",
        "--noconsole",
        "--name", "AutoKeyI",
        "--add-data", "config.json;.",
        "--icon", "icon.ico",
        "--clean",
    ]
    PyInstaller.__main__.run(args)
    print("打包完成，可执行文件位于 dist/AutoKeyI.exe")


if __name__ == "__main__":
    main()
