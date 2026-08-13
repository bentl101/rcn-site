#!/usr/bin/env python3
"""Build optimized raster assets from source images and SVG brand masters."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "assets" / "images"
PURPLE = "#321551"
RED = "#D51F35"
GOLD = "#A37A2B"
CREAM = "#FFF9EF"
GEORGIA = "/System/Library/Fonts/Supplemental/Georgia.ttf"
ARIAL = "/System/Library/Fonts/Supplemental/Arial.ttf"
ARIAL_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def webp(name: str, width: int, quality: int = 84) -> None:
    source = IMAGES / f"{name}.png"
    target = IMAGES / f"{name}.webp"
    with Image.open(source) as image:
        image = image.convert("RGB")
        if image.width > width:
            height = round(image.height * width / image.width)
            image = image.resize((width, height), Image.Resampling.LANCZOS)
        image.save(target, "WEBP", quality=quality, method=6)


def scaled_points(points: list[tuple[int, int]], scale: float) -> list[tuple[int, int]]:
    return [(round(x * scale), round(y * scale)) for x, y in points]


def draw_coach(draw: ImageDraw.ImageDraw, scale: float, offset: tuple[int, int] = (0, 0)) -> None:
    """Draw the recognizable DCT coach motif used by both logo lockups."""
    ox, oy = offset

    def pts(values: list[tuple[int, int]]) -> list[tuple[int, int]]:
        return [(round(x * scale) + ox, round(y * scale) + oy) for x, y in values]

    width = max(6, round(12 * scale))
    draw.line(
        pts([(398, 89), (318, 84), (238, 90), (173, 108), (131, 139), (120, 171),
             (127, 205), (150, 231), (184, 244), (256, 247), (271, 281),
             (438, 281), (452, 246), (505, 242), (545, 221), (569, 187),
             (565, 149), (544, 120), (499, 101), (438, 91), (398, 89)]),
        fill=PURPLE,
        width=width,
        joint="curve",
    )
    for x in (305, 419):
        box = [
            round((x - 29) * scale) + ox,
            round(252 * scale) + oy,
            round((x + 29) * scale) + ox,
            round(310 * scale) + oy,
        ]
        draw.ellipse(box, fill="#FFFFFF", outline=PURPLE, width=max(4, round(9 * scale)))
    draw.line(pts([(152, 201), (215, 205), (241, 233)]), fill=PURPLE, width=max(4, round(8 * scale)))
    draw.line(pts([(191, 136), (483, 129), (521, 143), (501, 181), (170, 183), (191, 136)]),
              fill=PURPLE, width=max(4, round(8 * scale)), joint="curve")


def build_horizontal_logo() -> None:
    canvas = Image.new("RGBA", (2400, 780), (255, 255, 255, 0))
    draw = ImageDraw.Draw(canvas)
    draw_coach(draw, 1.5, (300, 0))
    draw.rounded_rectangle((138, 352, 2262, 598), radius=18, fill="#FFFDF8", outline=PURPLE, width=14)
    title = ImageFont.truetype(GEORGIA, 182)
    subtitle = ImageFont.truetype(ARIAL_BOLD, 58)
    draw.text((1200, 490), "Discount", font=title, fill=PURPLE, anchor="mm")
    label_box = (738, 624, 1662, 744)
    draw.rounded_rectangle(label_box, radius=60, fill="#FFFFFF", outline=RED, width=7)
    draw.text((1200, 684), "C O A C H   T O U R S", font=subtitle, fill=RED, anchor="mm")
    canvas.save(IMAGES / "dct-logo-horizontal.png", optimize=True)


def build_square_logo() -> None:
    canvas = Image.new("RGBA", (2048, 2048), CREAM)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((36, 36, 2012, 2012), radius=200, outline=PURPLE, width=30)
    draw.ellipse((374, 145, 1674, 1445), outline=GOLD, width=22)
    draw_coach(draw, 2.15, (165, 60))
    title = ImageFont.truetype(GEORGIA, 248)
    subtitle = ImageFont.truetype(ARIAL_BOLD, 80)
    draw.text((1024, 1452), "Discount", font=title, fill=PURPLE, anchor="mm")
    draw.rounded_rectangle((360, 1650, 1688, 1832), radius=91, fill="#FFFFFF", outline=RED, width=12)
    draw.text((1024, 1742), "C O A C H   T O U R S", font=subtitle, fill=RED, anchor="mm")
    canvas.save(IMAGES / "dct-logo-square.png", optimize=True)


for asset, size in {
    "hero-coach-rockies": 2000,
    "trafalgar-guests": 1200,
    "globus-alps": 1200,
    "cosmos-highlands": 1200,
    "insight-lake-como": 1200,
}.items():
    webp(asset, size)

build_horizontal_logo()
build_square_logo()

print("Built optimized WebP photography and high-resolution PNG logo exports.")
