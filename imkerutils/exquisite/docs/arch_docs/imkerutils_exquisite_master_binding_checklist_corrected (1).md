# Exquisite Subproject — Master Binding Checklist (CORRECTED FOR TILE MODE)
**Date:** 2026-02-20 (America/New_York)

This checklist corrects a prior misunderstanding: **v1 is tile-based**.

> v1 generator contract is **NOT** “expand arbitrary (N, M) to (N, M+L)” in one API call.  
> v1 generator contract is: **take a fixed-size band and produce a fixed-size square tile**; then the pipeline glues the new region onto an arbitrarily wide (or tall) canvas.

Therefore:
- The GPT model only ever returns a **1024×1024** tile in v1.
- The *canvas* can grow unbounded (by repeated appends), but the *generator output size* does not.

This document is intended to be appended to the authoritative engineer notes / checklist.

------------------------------------------------------------------------

## A. Session Authority Bindings (Filesystem + Identity) — unchanged
- [x] `PRIMARY_INVARIANT = DIMENSION_INVARIANT`
- [x] `ARTIFACT_ROOT = /home/foster/imkerutils/imkerutils/_generated/exquisite`
- [x] `SESSION_ID_SCHEME = uuid4`
- [x] `PIXEL_ORIGIN = TOP_LEFT`
- [x] `CANVAS_FORMAT = PNG_RGB`
- [x] `IMAGE_BACKEND = PILLOW`
- [x] `DIMENSION_AUTHORITY = IMAGE_HEADER`
- [x] `CANVAS_FILENAME = canvas_latest.png`
- [x] `SESSION_STATE_FILENAME = session_state.json`
- [x] `STEP_INDEX_ORIGIN = 0`
- [x] `STEP_DIR_FORMAT = steps/%04d`
- [x] `STEP_RESULT_AUTHORITY = STEP_DIR_ARTIFACTS`

------------------------------------------------------------------------

## B. Tile Mode Bindings (NEW — replaces “allowed canvas sizes” confusion)
- [x] `GENERATOR_TILE_PX = 1024`
- [x] `EXTENSION_PX = 512`
- [x] `BAND_THICKNESS_PX = 512`
- [x] `EXTEND_MODE = x_axis_left_to_right` *(Phase A only; more modes later)*

**Meaning (x-axis, left→right):**
- Each step adds **512 pixels** to the **right** of the master canvas.
- Conditioning band is the **rightmost 1024×512** band of the canvas.
- Generator output is a **1024×1024** tile with a fixed placement convention (below).

------------------------------------------------------------------------

## C. Generator IO Contract (CORRECTED)
### C0. Generator size policy (CORRECTED)
- [x] `GENERATION_SIZE_POLICY = FIXED_TILE_1024`

Contract:
- Every generation request MUST ask for:
  - `size = 1024×1024`
- Every generator response MUST be exactly:
  - `tile.size == (1024, 1024)`

### C1. Band placement convention inside the tile (CRITICAL)
- [x] `BAND_PLACEMENT_IN_TILE = LEFT_HALF_FOR_X_LTR`

Contract (x-axis left→right):
- `tile[:, 0:512]` is the **conditioning band** (must match input band if enforcement is enabled)
- `tile[:, 512:1024]` is the **newly generated region**

This convention is what makes “axis+direction” sufficient.

------------------------------------------------------------------------

## D. Canvas growth contract (CORRECTED)
### D1. Canvas dimension projection (v1)
- [x] `TARGET_DIMENSION_CONTRACT = CANVAS_APPEND_BY_EXTENSION_PX`

For `x_axis_left_to_right`:
- `H_next = H_current`
- `W_next = W_current + EXTENSION_PX`

### D2. “Allowed canvas sizes” (REMOVED for v1)
- [x] `ALLOWED_CANVAS_SIZES = UNBOUNDED_MULTIPLE_OF_EXTENSION_PX`

Contract:
- Canvas width may grow without enum restriction.
- The only constraint is that width increases by exactly `EXTENSION_PX` per committed step.

(If later we need power-of-two or UI constraints, they must be added as a *new* binding explicitly.)

------------------------------------------------------------------------

## E. Composite / Glue Contract (CORRECTED)
- [x] `COMPOSITE_POLICY = APPEND_TILE_NEW_REGION_TO_CANVAS`

For `x_axis_left_to_right`:
1. `new_pixels = tile[:, 512:1024]`
2. `canvas_next = concat(canvas_current, new_pixels) along width`

Optional seam policy (v1 simplification):
- [ ] `SEAM_BLEND_POLICY = none|linear` *(defer; not required for Phase A mock tests)*

------------------------------------------------------------------------

## F. Primary invariant (DIMENSION) — clarified for tile mode
- [x] `DIMENSION_INVARIANT_CHECK` uses **Pillow header** on:
  - `tile_out` (must be 1024×1024)
  - `canvas_next` (must be W+512 by H)

There is no axis confusion when stated explicitly:
- Pillow returns `(width, height)` and we compare against expected `(expected_w, expected_h)`.

------------------------------------------------------------------------

## G. Commit gate + atomicity (still required)
- [x] `ATOMIC_WRITE_STRATEGY = tempfile_plus_os_replace`
- [x] `COMMIT_MARKER_FILENAME = committed.ok`
- [x] `PARTIAL_COMMIT_DETECTION = missing committed.ok → RECOVERY_REQUIRED`

------------------------------------------------------------------------

## H. GPT Client bindings (Deferred until after Phase A)
This is intentionally postponed until the hermetic pipeline exists.

- [ ] `GPT_ENDPOINT_AUTHORITY = <bind when integrating real API>`
- [ ] `GPT_AUTH_AUTHORITY = <bind when integrating real API>`
- [ ] `GPT_MODEL_AUTHORITY = <bind when integrating real API>`
- [ ] `GPT_REQUEST_SCHEMA_AUTHORITY = <bind when integrating real API>`
- [ ] `GPT_RESPONSE_SCHEMA_AUTHORITY = <bind when integrating real API>`
- [ ] `GPT_TIMEOUT_S = <bind when integrating real API>`
- [ ] `GPT_RETRY_POLICY = <bind when integrating real API>`

------------------------------------------------------------------------

# Status Summary (CORRECTED)
- v1 is now consistently specified as **fixed tile generation + canvas append**.
- All “OpenAI size enum constrains canvas” language is removed as a category error for v1.
- Next authorized phase remains:
```text
BEGIN PIPELINE IMPLEMENTATION (Phase A: mock generator, no network)
```

END.
