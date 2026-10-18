"""由 assets/icon_source.png（生圖原稿）產生 App icon。

做法：裁成正方形 → 縮到 1024 → 套圓角 → 輸出 assets/icon.png 與多尺寸 assets/icon.ico。
更換圖案時，只要換掉 assets/icon_source.png 再執行：python tools/make_icon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SIZE, RADIUS = 1024, 190
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def main():
    src = Image.open(ASSETS / "icon_source.png").convert("RGB")
    side = min(src.size)
    left, top = (src.width - side) // 2, (src.height - side) // 2
    img = src.crop((left, top, left + side, top + side)).resize((SIZE, SIZE), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (SIZE * 2, SIZE * 2), 0)  # 2 倍繪製再縮小，圓角邊緣較平滑
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, SIZE * 2 - 1, SIZE * 2 - 1), radius=RADIUS * 2, fill=255)
    img.putalpha(mask.resize((SIZE, SIZE), Image.LANCZOS))
    img.save(ASSETS / "icon.png")
    img.save(ASSETS / "icon.ico", sizes=[(n, n) for n in ICO_SIZES])
    print("已輸出 icon.png、icon.ico")


if __name__ == "__main__":
    main()
