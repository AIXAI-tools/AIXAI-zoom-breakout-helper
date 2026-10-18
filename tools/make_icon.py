"""產生 App icon（金藍雙色光流匯聚 + 分成 5 間的視窗）。

與 AIXAI 系列（DLA、VPN）同一視覺語言：深色星空底、左金右藍、中央光點，
下方放各工具自己的主題圖。執行：python tools/make_icon.py
輸出：assets/icon.png（預覽）、assets/icon.ico（多尺寸，供視窗與 exe 使用）
"""
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

S = 1024
SS = 2  # 超取樣倍率，縮小後邊緣較平滑
OUT = Path(__file__).resolve().parent.parent / "assets"
GOLD, BLUE, WHITE = (255, 190, 70), (60, 180, 255), (255, 250, 235)


def bezier(p0, p1, p2, p3, n=120):
    pts = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
        pts.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
                    a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return pts


def lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def background(size):
    g = Image.radial_gradient("L").resize((size, size))
    bg = ImageOps.colorize(ImageOps.invert(g), black=(2, 4, 12), white=(12, 28, 64))
    d = ImageDraw.Draw(bg)
    rnd = random.Random(7)
    for _ in range(140):
        x, y, r = rnd.randrange(size), rnd.randrange(size), rnd.choice((1, 1, 2, 3))
        v = rnd.randrange(110, 230)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(v, v, min(255, v + 25)))
    return bg


def main():
    k = SS
    W = S * k
    s = lambda v: v * k  # noqa: E731  座標換算到超取樣尺寸
    layer = Image.new("RGB", (W, W), (0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = s(512), s(330)  # 匯聚光點

    # 光流：左金右藍，多股細線匯聚到中央光點
    rnd = random.Random(3)
    for side, color in ((-1, GOLD), (1, BLUE)):
        for i in range(26):
            spread = (i - 13) * 11
            start = (cx + side * s(520), s(120) + s(spread * 2.2))
            c1 = (cx + side * s(330), s(60) + s(spread * 1.2))
            c2 = (cx + side * s(150), cy - s(80) + s(spread * 0.4))
            pts = bezier(start, c1, c2, (cx, cy))
            fade = 1 - abs(i - 13) / 16
            col = tuple(int(c * (0.35 + 0.65 * fade)) for c in color)
            d.line(pts, fill=col, width=max(1, int(s(2) + rnd.random() * s(3) * fade)))

    # 光點下方的光束
    d.line([(cx, cy), (cx, s(470))], fill=(150, 210, 255), width=s(6))

    # 外框（大視窗）
    fx0, fy0, fx1, fy1 = s(140), s(480), s(884), s(940)
    d.rounded_rectangle((fx0, fy0, fx1, fy1), radius=s(46), outline=(110, 200, 255), width=s(10))
    d.line([(fx0 + s(30), fy0 + s(48)), (fx1 - s(30), fy0 + s(48))], fill=(70, 130, 200), width=s(5))
    for i, x in enumerate((fx0 + s(40), fx0 + s(66), fx0 + s(92))):  # 標題列的三個小點
        d.ellipse((x - s(7), fy0 + s(24) - s(7) + s(0), x + s(7), fy0 + s(24) + s(7)),
                  fill=lerp(GOLD, BLUE, i / 2))

    # 5 個房間：3 + 2，顏色由左金漸變到右藍；每間下方一條「名稱標籤」
    rw, rh, gap = s(190), s(138), s(34)
    rows = [(s(555), 3), (s(745), 2)]
    area_x0, area_x1 = fx0 + s(40), fx1 - s(40)
    for y, n in rows:
        total = n * rw + (n - 1) * gap
        x0 = (area_x0 + area_x1 - total) // 2
        for j in range(n):
            x = x0 + j * (rw + gap)
            t = (x + rw / 2 - area_x0) / (area_x1 - area_x0)
            col = lerp(GOLD, BLUE, t)
            d.rounded_rectangle((x, y, x + rw, y + rh), radius=s(22), fill=tuple(int(c * 0.16) for c in col),
                                outline=col, width=s(8))
            d.rounded_rectangle((x + s(34), y + rh - s(42), x + rw - s(34), y + rh - s(24)),
                                radius=s(9), fill=lerp(col, WHITE, 0.25))

    # 中央光點（放最後，蓋在光流交會處）
    for r, a in ((s(110), 0.10), (s(64), 0.22), (s(36), 0.5), (s(15), 1.0)):
        spark = Image.new("RGB", (W, W), (0, 0, 0))
        ImageDraw.Draw(spark).ellipse((cx - r, cy - r, cx + r, cy + r), fill=tuple(int(c * a) for c in WHITE))
        layer = ImageChops.add(layer, spark.filter(ImageFilter.GaussianBlur(s(8))) if r > s(30) else spark.filter(ImageFilter.GaussianBlur(s(2))))

    glow = layer.filter(ImageFilter.GaussianBlur(s(16)))
    glow2 = layer.filter(ImageFilter.GaussianBlur(s(40)))
    dim = lambda im, v: ImageChops.multiply(im, Image.new("RGB", (W, W), (v,) * 3))  # noqa: E731  壓低光暈強度
    art = ImageChops.add(ImageChops.add(layer, dim(glow, 150)), dim(glow2, 80))
    art = art.resize((S, S), Image.LANCZOS)
    final = ImageChops.add(background(S), art)

    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, S - 1, S - 1), radius=190, fill=255)
    final = final.convert("RGBA")
    final.putalpha(mask)

    OUT.mkdir(exist_ok=True)
    final.save(OUT / "icon.png")
    final.save(OUT / "icon.ico", sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])
    print("已輸出", OUT / "icon.png", OUT / "icon.ico")


if __name__ == "__main__":
    main()
