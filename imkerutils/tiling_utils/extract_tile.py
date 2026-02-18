#!/usr/bin/env python3
import argparse
from pathlib import Path

from .core import extract_tile
from imkerutils.paths import ensure_dirs, OUTPUT_TILES


def main():
    ensure_dirs()

    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output", nargs="?", default=None)  # <- optional
    ap.add_argument("--x", type=int, required=True)
    ap.add_argument("--y", type=int, required=True)
    ap.add_argument("--corner", default="tl")
    args = ap.parse_args()

    if args.output is None:
        stem = Path(args.input).stem
        args.output = str(OUTPUT_TILES / f"{stem}__{args.corner}__{args.x}_{args.y}.png")

    rect = extract_tile(args.input, args.output, x=args.x, y=args.y, corner=args.corner)
    print(f"Saved tile: {args.output}")
    print(f"Rect: {rect} (right/bottom are exclusive)")


if __name__ == "__main__":
    main()
