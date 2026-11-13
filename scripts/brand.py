"""Draw the Wyoming Silero brand images from one description of the mark.

    uv run --no-project --with pillow python -I scripts/brand.py --font <Onest TTF>

``--font`` is the Onest variable TTF (https://github.com/google/fonts/tree/main/ofl/onest), used
for the wordmark. The mark is our own (a sound wave with a stress mark over its crest), not the
Silero logo. Writes:

- ``assets/brand/mark.svg``                 vector source of the mark
- ``assets/brand/logo.png``, ``dark_logo.png``  logos for the README (light and dark themes)
- ``addon/icon.png``, ``addon/logo.png``    the app in the app store
- ``assets/brand/social-preview.png``       GitHub social preview (upload by hand)

Images are PNG, transparent, without empty margins (as home-assistant/brands asks).
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
NAME = "Wyoming Silero"

TEAL = "#2BB8A6"
VIOLET = "#9C7BF0"
AMBER = "#E9A23B"
INK_LIGHT = "#1D2330"  # wordmark on light backgrounds
INK_DARK = "#E4E7EC"  # wordmark on dark backgrounds
INK_ANY = "#6B7484"  # wordmark that reads on both (the app store has no dark variant)
CANVAS = "#1B1F26"

# Geometry in a unit square (the same numbers go into the SVG).
# A spoken wave with a stress mark over its main crest: Silero v5_6_ru puts stresses itself.
WAVE_X = (0.08, 0.92)  # where the wave starts and ends
WAVE_Y = 0.60  # its rest line
WAVE_A = 0.22  # the height of the main crest
WAVE_PERIODS = 2.5  # the main crest in the middle, smaller ones fading out
WAVE_W = 0.07
DOT_R = 0.07  # violet dot at the start: the text the voice comes from
ACCENT = ((0.485, 0.27), (0.565, 0.15))  # the stress mark, an acute accent
ACCENT_W = 0.075


def wave_points(n: int = 160) -> list[tuple[float, float]]:
    """The wave in unit coordinates: a sine under a sine envelope, flat at both ends."""
    x0, x1 = WAVE_X
    points = []
    for i in range(n + 1):
        t = i / n
        envelope = math.sin(math.pi * t)
        y = WAVE_Y - WAVE_A * envelope * math.cos(2 * math.pi * WAVE_PERIODS * (t - 0.5))
        points.append((x0 + (x1 - x0) * t, y))
    return points


def _round_line(d: ImageDraw.ImageDraw, a: tuple[float, float], b: tuple[float, float],
                width: float, color: str) -> None:  # fmt: skip
    d.line([a, b], fill=color, width=round(width))
    for x, y in (a, b):
        d.ellipse([x - width / 2, y - width / 2, x + width / 2, y + width / 2], fill=color)


def mark(size: int) -> Image.Image:
    """The mark, trimmed to its content and centred in a transparent square of ``size``."""
    s = 2048
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = WAVE_W * s
    points = [(x * s, y * s) for x, y in wave_points()]
    d.line(points, fill=TEAL, width=round(w), joint="curve")
    for x, y in points:  # smooth round joints and caps
        d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=TEAL)
    (ax, ay), (bx, by) = ACCENT
    _round_line(d, (ax * s, ay * s), (bx * s, by * s), ACCENT_W * s, AMBER)
    x, y, r = WAVE_X[0] * s, WAVE_Y * s, DOT_R * s
    d.ellipse([x - r, y - r, x + r, y + r], fill=VIOLET)
    trimmed = img.crop(img.getbbox())
    side = max(trimmed.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(trimmed, ((side - trimmed.width) // 2, (side - trimmed.height) // 2))
    return square.resize((size, size), Image.Resampling.LANCZOS)


def mark_svg() -> str:
    """The same mark as SVG (units of 1/1000)."""
    k = 1000
    points = wave_points(60)
    path = "M" + " L".join(f"{x * k:.1f} {y * k:.1f}" for x, y in points)
    (ax, ay), (bx, by) = ACCENT
    ys = [y for _, y in points]
    pad = max(WAVE_W, ACCENT_W, 2 * DOT_R) / 2
    vb_left = (WAVE_X[0] - DOT_R) * k
    vb_right = (WAVE_X[1] + WAVE_W / 2) * k
    vb_top = (min(by, min(ys)) - pad) * k
    vb_bottom = (max(ys) + pad) * k
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb_left:g} {vb_top:g} {vb_right - vb_left:g} {vb_bottom - vb_top:g}">
<title>{NAME}</title>
<path d="{path}" fill="none" stroke="{TEAL}" stroke-width="{WAVE_W * k:g}" stroke-linecap="round" stroke-linejoin="round" />
<path d="M{ax * k:g} {ay * k:g} L{bx * k:g} {by * k:g}" stroke="{AMBER}" stroke-width="{ACCENT_W * k:g}" stroke-linecap="round" />
<circle cx="{WAVE_X[0] * k:g}" cy="{WAVE_Y * k:g}" r="{DOT_R * k:g}" fill="{VIOLET}" />
</svg>
"""  # noqa: E501


def font(path: Path, size: int, weight: int = 640) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(path), size)
    f.set_variation_by_axes([weight])
    return f


def logo(height: int, ink: str, font_path: Path) -> Image.Image:
    """Mark and wordmark side by side, trimmed: the short side is ``height``."""
    scale = 4
    h = height * scale
    m = mark(h)
    f = font(font_path, int(h * 0.56))
    box = f.getbbox(NAME)
    gap = int(h * 0.22)
    canvas = Image.new("RGBA", (h + gap + box[2] + h, h), (0, 0, 0, 0))
    canvas.paste(m, (0, 0), m)
    d = ImageDraw.Draw(canvas)
    d.text((h + gap, (h - (box[3] + box[1])) // 2), NAME, font=f, fill=ink)
    trimmed = canvas.crop(canvas.getbbox())
    width = round(trimmed.width * height / trimmed.height)
    return trimmed.resize((width, height), Image.Resampling.LANCZOS)


def fit(img: Image.Image, width: int, height: int) -> Image.Image:
    """Scale ``img`` into a ``width``x``height`` transparent box (the app logo has a fixed box)."""
    img = img.copy()
    img.thumbnail((width, height), Image.Resampling.LANCZOS)
    box = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    box.paste(img, ((width - img.width) // 2, (height - img.height) // 2), img)
    return box


def social(font_path: Path) -> Image.Image:
    img = Image.new("RGB", (1280, 640), CANVAS)
    m = mark(280)
    img.paste(m, (110, 180), m)
    d = ImageDraw.Draw(img)
    d.text((450, 200), "Wyoming", font=font(font_path, 104), fill=INK_DARK)
    d.text((450, 310), "Silero", font=font(font_path, 104), fill=INK_DARK)
    tagline = font(font_path, 36, 420)
    d.text((454, 450), "Local Russian text-to-speech for", font=tagline, fill="#8A93A3")
    d.text((454, 496), "Home Assistant Assist, no cloud", font=tagline, fill="#8A93A3")
    return img


def save(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, optimize=True)
    print(f"{path.relative_to(ROOT)}  {img.width}x{img.height}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--font", type=Path, required=True, help="Onest variable TTF")
    font_path = parser.parse_args().font

    assets = ROOT / "assets" / "brand"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "mark.svg").write_text(mark_svg())
    print("assets/brand/mark.svg")

    save(logo(128, INK_LIGHT, font_path), assets / "logo.png")
    save(logo(128, INK_DARK, font_path), assets / "dark_logo.png")

    save(mark(128), ROOT / "addon" / "icon.png")
    save(fit(logo(200, INK_ANY, font_path), 250, 100), ROOT / "addon" / "logo.png")

    save(social(font_path), assets / "social-preview.png")


if __name__ == "__main__":
    main()
