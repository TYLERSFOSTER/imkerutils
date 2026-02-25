# imkerutils/exquisite/ui/__main__.py
from __future__ import annotations

import argparse
from pathlib import Path

from imkerutils.exquisite.ui.server import run_server


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m imkerutils.exquisite.ui")
    p.add_argument("initial_canvas", type=str, help="Path to initial 1024x1024 image (PNG recommended).")
    p.add_argument("--mode", type=str, default="x_ltr", choices=["x_ltr", "x_rtl", "y_ttb", "y_btt"])
    p.add_argument("--host", type=str, default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()

    initial = Path(args.initial_canvas).expanduser().resolve()
    if not initial.exists():
        raise SystemExit("Initial canvas not found.")

    run_server(initial_canvas=initial, mode=args.mode, host=args.host, port=args.port)


if __name__ == "__main__":
    main()