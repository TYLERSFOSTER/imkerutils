#!/usr/bin/env python3
import argparse
from .core import paste_tile

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("tile")
    ap.add_argument("output")
    ap.add_argument("--x", type=int, required=True)
    ap.add_argument("--y", type=int, required=True)
    ap.add_argument("--corner", default="tl")
    args = ap.parse_args()

    pos = paste_tile(args.base, args.tile, args.output, x=args.x, y=args.y, corner=args.corner)
    print(f"Saved: {args.output}")
    print(f"Pasted at top-left: {pos}")

if __name__ == "__main__":
    main()
