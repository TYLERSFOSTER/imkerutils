from pathlib import Path

# resolve project root assuming this file lives in imkerutils/paths.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# internal generated files
GENERATED_ROOT = PROJECT_ROOT / "imkerutils" / "_generated"

# top-level outputs
OUTPUT_ROOT = PROJECT_ROOT / "outputs"

# subdirectories
GENERATED_TILES = GENERATED_ROOT / "tiles"
GENERATED_CACHE = GENERATED_ROOT / "cache"

OUTPUT_IMAGES = OUTPUT_ROOT / "images"
OUTPUT_TILES = OUTPUT_ROOT / "tiles"


def ensure_dirs():
    dirs = [
        GENERATED_ROOT,
        GENERATED_TILES,
        GENERATED_CACHE,
        OUTPUT_ROOT,
        OUTPUT_IMAGES,
        OUTPUT_TILES,
    ]

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

ensure_dirs()
