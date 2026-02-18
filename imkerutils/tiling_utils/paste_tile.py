#!/usr/bin/env python3
import argparse
from pathlib import Path

from .core import paste_tile
from imkerutils.paths import ensure_dirs, OUTPUT_IMAGES


def main():
    ensure_dirs()

    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("tile")
    ap.add_argument("output", nargs="?", default=None)  # <- optional
    ap.add_argument("--x", type=int, required=True)
    ap.add_argument("--y", type=int, required=True)
    ap.add_argument("--corner", default="tl")
    args = ap.parse_args()

    if args.output is None:
        base_stem = Path(args.base).stem
        args.output = str(OUTPUT_IMAGES / f"{base_stem}__patched.png")

    pos = paste_tile(args.base, args.tile, args.output, x=args.x, y=args.y, corner=args.corner)
    print(f"Saved: {args.output}")
    print(f"Pasted at top-left: {pos}")


if __name__ == "__main__":
    main()
