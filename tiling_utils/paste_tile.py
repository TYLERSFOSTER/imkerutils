#!/usr/bin/env python3
# paste_tile.py
import argparse
from PIL import Image

TILE = 1024

def top_left_from_corner(x: int, y: int, corner: str):
    corner = corner.lower()
    if corner == "tl":
        return x, y
    if corner == "tr":
        return x - (TILE - 1), y
    if corner == "bl":
        return x, y - (TILE - 1)
    if corner == "br":
        return x - (TILE - 1), y - (TILE - 1)
    raise ValueError("corner must be one of: tl, tr, bl, br")

def main():
    ap = argparse.ArgumentParser(description="Replace a 1024×1024 region of an image with a given tile.")
    ap.add_argument("base", help="Base JPG/PNG path (the image to modify)")
    ap.add_argument("tile", help="Tile image path (must be exactly 1024×1024)")
    ap.add_argument("output", help="Output image path")
    ap.add_argument("--x", type=int, required=True, help="Corner pixel x (0-based)")
    ap.add_argument("--y", type=int, required=True, help="Corner pixel y (0-based)")
    ap.add_argument("--corner", default="tl", help="Which corner is (x,y): tl|tr|bl|br (default tl)")
    args = ap.parse_args()

    base = Image.open(args.base)
    tile = Image.open(args.tile)

    bw, bh = base.size
    tw, th = tile.size
    if (tw, th) != (TILE, TILE):
        raise SystemExit(f"Tile must be exactly {TILE}×{TILE}, got {tw}×{th}")

    left, top = top_left_from_corner(args.x, args.y, args.corner)
    right, bottom = left + TILE, top + TILE

    if left < 0 or top < 0 or right > bw or bottom > bh:
        raise SystemExit(
            f"Paste out of bounds.\n"
            f"Base size: {bw}×{bh}\n"
            f"Paste rect: left={left}, top={top}, right={right}, bottom={bottom}"
        )

    # Ensure same mode to avoid implicit conversions
    if tile.mode != base.mode:
        tile = tile.convert(base.mode)

    base.paste(tile, (left, top))  # exact paste, no blending, no resampling
    base.save(args.output)
    print(f"Saved: {args.output}")
    print(f"Pasted at top-left: ({left}, {top})")

if __name__ == "__main__":
    main()
