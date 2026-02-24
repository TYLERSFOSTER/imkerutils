from __future__ import annotations

import sys
from pathlib import Path

from imkerutils.exquisite.ui.server import run_server


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m imkerutils.exquisite.ui <initial_canvas.png>")
        sys.exit(1)

    initial = Path(sys.argv[1])
    if not initial.exists():
        print("Initial canvas not found.")
        sys.exit(1)

    run_server(initial)


if __name__ == "__main__":
    main()