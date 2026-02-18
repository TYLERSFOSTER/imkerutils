# imkerutils
Image processing utilities.
# imkerutils

**Image processing infrastructure for large‑scale, tile‑based, and
model‑integrated workflows.**

imkerutils is a Python package designed to provide deterministic,
composable, and scalable image processing primitives, especially for
workflows involving:

-   Diffusion models
-   Vision transformers (ViT)
-   Large language model (LLM)‑driven image manipulation
-   Tile‑based gigapixel image pipelines
-   Seam‑preserving edits and recomposition
-   Structured image generation and reconstruction

It is built to serve as foundational infrastructure for high‑resolution
and arbitrarily large image processing systems.

------------------------------------------------------------------------

## Design principles

imkerutils is built around the following core principles:

### Deterministic pixel operations

All core operations preserve exact pixel identity unless explicitly
modified.

This enables:

-   Seamless tiling
-   Boundary‑preserving editing
-   Exact recomposition
-   Cryptographic reproducibility

### Tile‑native architecture

All image processing can be expressed in terms of fixed‑size tiles
(default: 1024×1024), enabling:

-   Arbitrary image sizes
-   Parallel processing
-   Distributed pipelines
-   Incremental modification

### Explicit data locality

Generated data is separated into:

    imkerutils/_generated/
    outputs/

This ensures:

-   clean source trees
-   reproducible pipelines
-   explicit artifact tracking

### Model‑compatible workflows

imkerutils is designed to integrate cleanly with:

-   diffusion models
-   segmentation models
-   ViTs
-   multimodal LLM pipelines

------------------------------------------------------------------------

## Installation

### Development install

Clone repository:

``` bash
git clone git@github.com:TYLERSFOSTER/imkerutils
cd imkerutils
```

Create environment:

``` bash
python -m venv .venv
source .venv/bin/activate
```

Install editable:

``` bash
pip install -e .
```

------------------------------------------------------------------------

## Quick start

### Extract a tile

``` bash
extract-tile input.png --x 0 --y 0
```

Output:

    outputs/tiles/input__tl__0_0.png

### Paste a tile

``` bash
paste-tile base.png tile.png --x 0 --y 0
```

Output:

    outputs/images/base__patched.png

These operations preserve exact pixel identity outside the modified
region.

------------------------------------------------------------------------

## Python API

``` python
from imkerutils.tiling import extract_tile, paste_tile

extract_tile(
    "input.png",
    "tile.png",
    x=0,
    y=0,
)

paste_tile(
    "base.png",
    "tile.png",
    "output.png",
    x=0,
    y=0,
)
```

------------------------------------------------------------------------

## Project structure

    imkerutils/
    │
    ├── imkerutils/
    │   ├── tiling/
    │   ├── paths.py
    │   └── _generated/
    │
    ├── outputs/
    │
    ├── tests/
    │
    └── pyproject.toml

------------------------------------------------------------------------

## Generated data model

imkerutils enforces strict separation of concerns:

    imkerutils/_generated/

Intermediate artifacts:

-   tiles
-   masks
-   caches

```{=html}
<!-- -->
```
    outputs/

Final outputs:

-   stitched images
-   processed results
-   exported data

------------------------------------------------------------------------

## Example workflow

    image → tiles → model → modified tiles → recomposition → output

This allows arbitrary image sizes without loss of fidelity.

------------------------------------------------------------------------

## Roadmap

Planned modules:

    imkerutils.tiling
    imkerutils.stitching
    imkerutils.segmentation
    imkerutils.diffusion
    imkerutils.io
    imkerutils.transforms
    imkerutils.workspace

------------------------------------------------------------------------

## Guarantees

imkerutils guarantees:

-   Exact pixel preservation unless explicitly modified
-   Deterministic transformations
-   Explicit artifact management
-   Scalable architecture

------------------------------------------------------------------------

## License

MIT License

------------------------------------------------------------------------

## Author

Tyler Foster

------------------------------------------------------------------------

## Status

Active development.

Production‑oriented design.

API stability improving rapidly.
