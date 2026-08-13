#!/usr/bin/env python3
"""Build optimized photographic assets. Logo PNGs come from SVG via Sharp."""

from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "assets" / "images"


def webp(name: str, width: int, quality: int = 84) -> None:
    source = IMAGES / f"{name}.png"
    target = IMAGES / f"{name}.webp"
    with Image.open(source) as image:
        image = image.convert("RGB")
        if image.width > width:
            height = round(image.height * width / image.width)
            image = image.resize((width, height), Image.Resampling.LANCZOS)
        image.save(target, "WEBP", quality=quality, method=6)


for asset, size in {
    "hero-coach-rockies": 2000,
    "trafalgar-guests": 1200,
    "globus-alps": 1200,
    "cosmos-highlands": 1200,
    "insight-lake-como": 1200,
}.items():
    webp(asset, size)

print("Built optimized WebP photography. Run render_logo.cjs for logo PNGs.")
