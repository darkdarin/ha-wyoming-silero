"""Assemble Wyoming Silero as a local app folder that Home Assistant builds by itself.

    uv run --no-project python -I scripts/build_addon.py      # -> dist/addon/wyoming_silero/

Copy the resulting ``wyoming_silero`` folder into ``/addons`` on the Home Assistant machine (Samba
or SSH app), then Settings → Apps → App Store → ⋮ → Check for updates; "Wyoming Silero" appears
under "Local apps". The Supervisor builds the image on that machine from the bundled sources.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SLUG = "wyoming_silero"
# The root README stays out: the app folder has its own README for the app store, and it also
# satisfies pyproject's "readme" during the image build.
SOURCES = ["Dockerfile", ".dockerignore", "pyproject.toml", "uv.lock", "LICENSE", "src"]


def build(out: Path) -> Path:
    target = out / SLUG
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(ROOT / "addon", target)
    config = target / "config.yaml"  # without "image:" the Supervisor builds the bundled Dockerfile
    config.write_text(
        "".join(
            line
            for line in config.read_text().splitlines(keepends=True)
            if not line.startswith("image:")
        )
    )
    for name in SOURCES:
        src = ROOT / name
        if src.is_dir():
            shutil.copytree(src, target / name, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(src, target / name)
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "dist" / "addon")
    target = build(parser.parse_args().out)
    print(f"app folder: {target}")


if __name__ == "__main__":
    main()
