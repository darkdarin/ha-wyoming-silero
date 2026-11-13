"""Draw the Wyoming Silero brand images from one description of the mark.

    uv run --no-project --with pillow python -I scripts/brand.py --font <Onest TTF>

``--font`` is the Onest variable TTF (https://github.com/google/fonts/tree/main/ofl/onest), used
for the wordmark. The mark is our own (a speech bubble with five sound bars, one per voice), not
the Silero logo. Writes:

- ``assets/brand/mark.svg``                 vector source of the mark
- ``assets/brand/logo.png``, ``dark_logo.png``  logos for the README (light and dark themes)
- ``addon/icon.png``, ``addon/logo.png``    the app in the app store
- ``assets/brand/social-preview.png``       GitHub social preview (upload by hand)

Images are PNG, transparent, without empty margins (as home-assistant/brands asks).
"""

from __future__ import annotations

import argparse
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

# Geometry in a unit square (the same numbers go into the SVG)
BUBBLE = (0.08, 0.10, 0.92, 0.74)  # left, top, right, bottom of the stroke's centre line
BUBBLE_R = 0.17  # corner radius
BUBBLE_W = 0.075  # stroke width
TAIL = ((0.22, 0.70), (0.17, 0.93), (0.45, 0.70))  # filled
BAR_Y = 0.42  # centre line of the sound bars
BAR_W = 0.075
BARS = (  # x, height, colour
    (0.27, 0.10, VIOLET),
    (0.385, 0.24, VIOLET),
    (0.50, 0.34, AMBER),
    (0.615, 0.24, VIOLET),
    (0.73, 0.10, VIOLET),
)


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
    left, top, right, bottom = (v * s for v in BUBBLE)
    w = BUBBLE_W * s
    d.polygon([(x * s, y * s) for x, y in TAIL], fill=TEAL)
    d.rounded_rectangle(
        [left - w / 2, top - w / 2, right + w / 2, bottom + w / 2],
        radius=(BUBBLE_R * s) + w / 2,
        outline=TEAL,
        width=round(w),
    )
    for x, h, color in BARS:
        _round_line(d, (x * s, (BAR_Y - h / 2) * s), (x * s, (BAR_Y + h / 2) * s), BAR_W * s, color)
    trimmed = img.crop(img.getbbox())
    side = max(trimmed.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(trimmed, ((side - trimmed.width) // 2, (side - trimmed.height) // 2))
    return square.resize((size, size), Image.Resampling.LANCZOS)


def mark_svg() -> str:
    """The same mark as SVG (units of 1/1000)."""
    k = 1000
    left, top, right, bottom = (v * k for v in BUBBLE)
    w = BUBBLE_W * k
    tail = " ".join(f"{x * k:g},{y * k:g}" for x, y in TAIL)
    bars = "\n".join(
        f'  <path d="M{x * k:g} {(BAR_Y - h / 2) * k:g} V{(BAR_Y + h / 2) * k:g}" stroke="{c}" />'
        for x, h, c in BARS
    )
    vb_left, vb_top = left - w / 2, top - w / 2
    vb_right, vb_bottom = right + w / 2, max(bottom + w / 2, max(y for _, y in TAIL) * k)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb_left:g} {vb_top:g} {vb_right - vb_left:g} {vb_bottom - vb_top:g}">
<title>{NAME}</title>
<polygon points="{tail}" fill="{TEAL}" />
<rect x="{left:g}" y="{top:g}" width="{right - left:g}" height="{bottom - top:g}" rx="{BUBBLE_R * k:g}" fill="none" stroke="{TEAL}" stroke-width="{w:g}" />
<g stroke-width="{BAR_W * k:g}" stroke-linecap="round">
{bars}
</g>
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
