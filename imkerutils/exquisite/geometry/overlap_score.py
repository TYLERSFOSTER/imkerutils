# imkerutils/exquisite/geometry/overlap_score.py
from __future__ import annotations

import numpy as np
from PIL import Image

from imkerutils.exquisite.geometry.tile_mode import (
    ExtendMode, TILE_PX, HALF_PX, OVERLAP_PX
)

def _to_gray_f32(img: Image.Image) -> np.ndarray:
    g = img.convert("L")
    a = np.asarray(g, dtype=np.float32) / 255.0
    return a

def _sobel_mag(gray: np.ndarray) -> np.ndarray:
    # gray: (H, W)
    # simple Sobel
    kx = np.array([[-1, 0, 1],
                   [-2, 0, 2],
                   [-1, 0, 1]], dtype=np.float32)
    ky = np.array([[-1, -2, -1],
                   [ 0,  0,  0],
                   [ 1,  2,  1]], dtype=np.float32)

    # pad
    p = np.pad(gray, ((1, 1), (1, 1)), mode="edge")
    H, W = gray.shape
    gx = np.zeros((H, W), dtype=np.float32)
    gy = np.zeros((H, W), dtype=np.float32)

    # conv (small and fast enough for 1024x256)
    for y in range(H):
        for x in range(W):
            window = p[y:y+3, x:x+3]
            gx[y, x] = float(np.sum(window * kx))
            gy[y, x] = float(np.sum(window * ky))

    return np.sqrt(gx * gx + gy * gy)

def _edge_weight(mask_shape: tuple[int, int], mode: ExtendMode) -> np.ndarray:
    # weights emphasize pixels closest to the seam boundary
    H, W = mask_shape
    if mode in ("x_ltr", "x_rtl"):
        # seam at left edge of generated strip for x_ltr; right edge for x_rtl strip choice.
        # Here we always score a strip that borders the seam, so weight highest near the seam edge.
        # We'll weight columns: col 0 is closest to seam for x_ltr; col W-1 is closest for x_rtl.
        w = np.linspace(1.0, 0.2, W, dtype=np.float32)  # drop off across strip
        if mode == "x_rtl":
            w = w[::-1].copy()
        return np.tile(w[None, :], (H, 1))
    else:
        w = np.linspace(1.0, 0.2, H, dtype=np.float32)
        if mode == "y_btt":
            w = w[::-1].copy()
        return np.tile(w[:, None], (1, W))

def extract_scoring_strips(canvas: Image.Image, tile: Image.Image, mode: ExtendMode) -> tuple[Image.Image, Image.Image]:
    canvas = canvas.convert("RGB")
    tile = tile.convert("RGB")
    w, h = canvas.size

    if mode in ("x_ltr", "x_rtl"):
        if h != TILE_PX: raise ValueError("canvas height must be TILE_PX")
        if mode == "x_ltr":
            canvas_strip = canvas.crop((w - OVERLAP_PX, 0, w, TILE_PX))
            tile_strip   = tile.crop((HALF_PX, 0, HALF_PX + OVERLAP_PX, TILE_PX))   # GENERATED side
        else:
            canvas_strip = canvas.crop((0, 0, OVERLAP_PX, TILE_PX))
            tile_strip   = tile.crop((HALF_PX - OVERLAP_PX, 0, HALF_PX, TILE_PX))   # GENERATED side
        return canvas_strip, tile_strip

    if mode in ("y_ttb", "y_btt"):
        if w != TILE_PX: raise ValueError("canvas width must be TILE_PX")
        if mode == "y_ttb":
            canvas_strip = canvas.crop((0, h - OVERLAP_PX, TILE_PX, h))
            tile_strip   = tile.crop((0, HALF_PX, TILE_PX, HALF_PX + OVERLAP_PX))   # GENERATED side
        else:
            canvas_strip = canvas.crop((0, 0, TILE_PX, OVERLAP_PX))
            tile_strip   = tile.crop((0, HALF_PX - OVERLAP_PX, TILE_PX, HALF_PX))   # GENERATED side
        return canvas_strip, tile_strip

    raise ValueError(mode)

def score_tile_sobel_corr(canvas: Image.Image, tile: Image.Image, mode: ExtendMode) -> float:
    c_strip, t_strip = extract_scoring_strips(canvas, tile, mode)

    c = _to_gray_f32(c_strip)
    t = _to_gray_f32(t_strip)

    c_edges = _sobel_mag(c)
    t_edges = _sobel_mag(t)

    w = _edge_weight(c_edges.shape, mode)

    # weighted correlation (cosine similarity)
    c_vec = (c_edges * w).ravel()
    t_vec = (t_edges * w).ravel()

    denom = float(np.linalg.norm(c_vec) * np.linalg.norm(t_vec))
    if denom == 0.0:
        return 0.0
    return float(np.dot(c_vec, t_vec) / denom)