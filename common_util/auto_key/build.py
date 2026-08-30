import os
import sys

from PIL import Image, ImageDraw, ImageFont


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


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
    icon_path = os.path.join(BASE_DIR, "icon.ico")
    images[0].save(icon_path, format="ICO", sizes=sizes, append_images=images[1:])
    print(f"已生成 {icon_path}")


def main():
    os.chdir(BASE_DIR)

    try:
        import PyInstaller.__main__
    except ImportError as e:
        print(f"缺少 PyInstaller：{e}")
        print('请先安装依赖：python -m pip install -r requirements.txt')
        sys.exit(1)

    create_icon_ico()

    script = os.path.join(BASE_DIR, "auto_key_i.py")
    icon = os.path.join(BASE_DIR, "icon.ico")
    config_add = f"config.json{os.pathsep}."

    args = [
        script,
        "--onefile",
        "--noconsole",
        "--name", "AutoKeyI",
        "--add-data", config_add,
        "--icon", icon,
        "--clean",
    ]
    PyInstaller.__main__.run(args)
    print("打包完成，可执行文件位于 dist/AutoKeyI.exe")


if __name__ == "__main__":
    main()
