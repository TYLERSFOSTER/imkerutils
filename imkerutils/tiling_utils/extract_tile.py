#!/usr/bin/env python3
import argparse
from .core import extract_tile

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--x", type=int, required=True)
    ap.add_argument("--y", type=int, required=True)
    ap.add_argument("--corner", default="tl")
    args = ap.parse_args()

    rect = extract_tile(args.input, args.output, x=args.x, y=args.y, corner=args.corner)
    print(f"Saved tile: {args.output}")
    print(f"Rect: {rect} (right/bottom are exclusive)")

if __name__ == "__main__":
    main()
