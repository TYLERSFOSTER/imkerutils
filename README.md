# imkerutils

**Image processing infrastructure for large‑scale, tile‑based,
model‑integrated workflows.**

imkerutils is a Python package providing deterministic, composable, and
scalable image processing primitives for high‑resolution and arbitrarily
large image systems.

It now includes **Exquisite**, an image‑conditioned, tile‑native
directional extension engine built on top of the core tiling
architecture.

------------------------------------------------------------------------

# Core Focus

imkerutils is designed for:

-   Diffusion model pipelines
-   Vision transformers (ViT)
-   Multimodal LLM‑driven image manipulation
-   Tile‑based gigapixel image processing
-   Seam‑preserving edits and recomposition
-   Structured image generation and reconstruction
-   Deterministic image extension workflows

------------------------------------------------------------------------

# Design Principles

## Deterministic Pixel Operations

All core operations preserve exact pixel identity unless explicitly
modified.

This enables:

-   Seamless tiling
-   Boundary‑preserving editing
-   Exact recomposition
-   Cryptographic reproducibility
-   Verifiable seam invariants

## Tile‑Native Architecture

All processing is expressed in fixed‑size tiles (default: 1024×1024).

This enables:

-   Arbitrary image dimensions
-   Incremental growth
-   Distributed execution
-   Model‑compatible patch conditioning
-   Memory‑bounded processing

## Explicit Data Locality

Generated data is separated into:

    imkerutils/_generated/
    outputs/

This ensures:

-   Clean source trees
-   Deterministic artifact management
-   Explicit step tracking
-   Reproducible experiments

## Model‑Conditioned Workflows

imkerutils integrates cleanly with:

-   Diffusion models
-   Segmentation models
-   Vision transformers
-   Multimodal LLM pipelines
-   Image inpainting APIs

The architecture explicitly supports masked, image‑conditioned
generation.

------------------------------------------------------------------------

# New: Exquisite --- Directional Image Extension Engine

Exquisite is a tile‑native application layer inside imkerutils that
enables:

-   Incremental image growth
-   Directional extension (RIGHT / LEFT / UP / DOWN)
-   Seam‑aware inpainting
-   Conditioning‑band enforcement
-   Deterministic canvas growth

It operates by:

1.  Extracting a 512px conditioning band from the canvas
2.  Constructing a 1024×1024 reference tile
3.  Creating an RGBA mask where only the new region is editable
4.  Calling an image‑conditioned generator (e.g., OpenAI images.edits)
5.  Enforcing conditioning band identity post‑generation
6.  Splitting and gluing new content into the growing canvas

The seam is physically possible because the model sees the real pixels
it must extend.

Exquisite is not a generic art tool --- it is a deterministic,
model‑integrated image extension system built for scalable workflows.

------------------------------------------------------------------------

# Installation

## Development Install

``` bash
git clone git@github.com:TYLERSFOSTER/imkerutils
cd imkerutils

python -m venv .venv
source .venv/bin/activate

pip install -e .
```

------------------------------------------------------------------------

# Quick Start (Core Tiling)

## Extract a tile

``` bash
extract-tile input.png --x 0 --y 0
```

## Paste a tile

``` bash
paste-tile base.png tile.png --x 0 --y 0
```

These operations preserve exact pixel identity outside modified regions.

------------------------------------------------------------------------

# Quick Start (Exquisite)

Run the directional extension UI:

``` bash
python -m imkerutils.exquisite.ui path/to/1024x1024_image.png
```

Then use the browser interface to:

-   Enter a prompt
-   Extend the canvas directionally
-   Grow the image incrementally

The system enforces: - Fixed tile size (1024×1024 per generation) -
512px conditioning band - Deterministic canvas dimension growth -
Post‑generation conditioning identity

------------------------------------------------------------------------

# Python API (Core)

``` python
from imkerutils.tiling import extract_tile, paste_tile

extract_tile("input.png", "tile.png", x=0, y=0)
paste_tile("base.png", "tile.png", "output.png", x=0, y=0)
```

------------------------------------------------------------------------

# Project Structure (Current Ground Truth)

    imkerutils/
    │
    ├── imkerutils/
    │   ├── tiling/
    │   ├── exquisite/
    │   │   ├── api/
    │   │   ├── geometry/
    │   │   ├── pipeline/
    │   │   ├── prompt/
    │   │   ├── state/
    │   │   └── ui/
    │   ├── paths.py
    │   └── _generated/
    │
    ├── outputs/
    ├── tests/
    └── pyproject.toml

------------------------------------------------------------------------

# Generated Data Model

Intermediate artifacts:

    imkerutils/_generated/

Contains:

-   tiles
-   masks
-   session state
-   step artifacts
-   deterministic prompt hashes

Final outputs:

    outputs/

Contains:

-   stitched images
-   final canvases
-   processed exports

------------------------------------------------------------------------

# Example Workflow

    image
     → extract band
     → build reference tile
     → mask editable region
     → model edit
     → enforce band identity
     → split tile
     → glue canvas
     → grow image

------------------------------------------------------------------------

# Roadmap

Planned expansion:

-   Seam blending strategies
-   Quality control tuning hooks
-   Prompt versioning registry
-   Multi‑direction batch growth
-   Distributed tile generation
-   Deterministic cost accounting
-   Model‑agnostic generator interface

------------------------------------------------------------------------

# Guarantees

imkerutils guarantees:

-   Exact pixel preservation unless explicitly modified
-   Deterministic geometric transforms
-   Explicit artifact separation
-   Tile‑native scalability
-   Conditioning‑band invariants (Exquisite)

------------------------------------------------------------------------

# License

MIT License

------------------------------------------------------------------------

# Author

Tyler Foster

------------------------------------------------------------------------

# Status

Active development.

Architecture stable. Application layer (Exquisite) maturing rapidly.
