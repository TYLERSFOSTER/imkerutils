# EXQUISITE ENGINEERING CONTINUITY REPORT

**Timestamp:** 2026-02-24 21:58:03\
**Project:** imkerutils.exquisite\
**Phase:** Overlap-Advance Refactor + Seam Quality Strategy

------------------------------------------------------------------------

# 1. Executive Summary

This report documents:

-   The transition from append-only 512px growth to 256px
    overlap/advance growth
-   The refactor of tile_mode glue semantics
-   The required changes to session pipeline
-   The UI behavioral changes (left-anchored growth + overflow feed)
-   The invariant model now governing seam geometry
-   The next high-ROI seam matching improvement plan

This document is authoritative for the current architecture.

------------------------------------------------------------------------

# 2. Geometry Contract Evolution

## 2.1 Previous Model (Append-Only)

-   Extract 512px frontier band
-   Generate 1024×1024 tile
-   Split 512/512
-   Append 512 new pixels
-   No overlap
-   Canvas growth: +512 per step

Problems observed:

-   Visible seam discontinuities
-   Hard resets in structure
-   Lower structural coherence
-   "Panel" feeling instead of continuous surface

------------------------------------------------------------------------

## 2.2 New Model (Overlap/Advance Contract)

Constants:

-   TILE_PX = 1024
-   HALF_PX = 512
-   BAND_PX = 512
-   OVERLAP_PX = 256
-   ADVANCE_PX = 256

### Behavior

Each step:

1.  Extract 512px frontier band

2.  Generate full 1024×1024 tile

3.  Conditioning half is enforced

4.  Glue using overlap operator:

    -   Overwrite last 256px of canvas
    -   Append 256px beyond frontier
    -   Net growth: +256

### Key Architectural Shift

Glue now consumes FULL TILE, not new_half.

Because overlap region requires conditioning-side pixels.

This fixes structural discontinuity at seam.

------------------------------------------------------------------------

# 3. tile_mode.py Refactor

## 3.1 Changes

-   Introduced OVERLAP_PX = 256
-   ADVANCE_PX = 256
-   expected_next_canvas_size now advances by 256
-   glue(canvas, tile, mode) replaces old glue(canvas, new_half, mode)
-   Introduced seam patch crop centered at 512 boundary: 256 → 768
    window

This patch: - 256px from conditioning side - 256px from generated side

Guarantees correct overlap semantics.

------------------------------------------------------------------------

# 4. session.py Refactor

## 4.1 Glue Update

Old: canvas_next = glue(canvas, new_half, mode)

New: canvas_next = glue(canvas, tile, mode)

## 4.2 Invariants Preserved

-   Conditioning identity enforcement
-   Dimension invariants
-   Disk atomic commit order
-   Step directory artifact capture
-   session_state.json authority update

## 4.3 Authority Model

Authority always flows:

1.  Write step artifacts
2.  Atomically replace canvas_latest.png
3.  Update session_state.json
4.  Write committed.ok marker LAST

This prevents half-committed state corruption.

------------------------------------------------------------------------

# 5. UI Behavior Evolution

## 5.1 Scaling

-   Canvas scales to fill viewport height
-   Prompt UI anchored bottom
-   No centering

## 5.2 Growth Model

-   Image initially left-aligned
-   As width \< viewport: pure concatenation
-   Once width \> viewport: right edge becomes live edge user scrolls
    left to see history

Simulates "feed until margin then push left".

------------------------------------------------------------------------

# 6. Seam Quality Problem

Observed issues:

-   Structural drift
-   Line misalignment
-   Scale inconsistencies
-   Overlap artifacts

Overlap contract improves baseline continuity but does not guarantee
structural coherence.

We now implement selection + scoring.

------------------------------------------------------------------------

# 7. Next High-ROI Upgrade Plan

## Strategy Summary

For each step:

1.  Generate 3 candidate tiles
2.  Score overlap region using edge-weighted similarity
3.  Select best candidate
4.  Optionally feather blend last 32px
5.  Commit

------------------------------------------------------------------------

# 8. Candidate Generation Strategy

Instead of:

    tile = generate_tile(...)

We will:

    candidates = [generate_tile(...) for _ in range(3)]

No architectural change to session authority model required.

Only selection logic inserted before glue.

------------------------------------------------------------------------

# 9. Overlap Scoring Plan

Overlap region:

-   Width = 256px
-   Compare against canvas frontier

### Scoring Options

Primary: - Edge-weighted SSIM

Alternative: - Sobel gradient correlation

Edge weighting: - Higher weight near seam boundary - Lower weight deeper
into overlap

Score definition:

    score = Σ w(x) * similarity_metric(x)

Choose candidate with max score.

------------------------------------------------------------------------

# 10. Feather Blend Plan (Optional)

After selecting best candidate:

Blend last 32px of overlap using linear ramp:

    alpha(x) = x / 32

Preserves continuity while hiding micro-artifacts.

Blend applied only inside overlap region.

Conditioning half invariant remains hard-enforced.

------------------------------------------------------------------------

# 11. Failure Modes Addressed

This strategy directly improves:

-   Line continuation accuracy
-   Pipe/tube continuation
-   Edge alignment
-   Structural coherence

It does NOT rely on model compliance alone.

It enforces geometric consistency post-generation.

------------------------------------------------------------------------

# 12. Future Extensions

Potential later upgrades:

-   Orientation histogram scoring
-   Multi-scale seam analysis
-   Two-pass structure/detail generation
-   Adaptive overlap thickness
-   Automatic seam diagnostics logging

------------------------------------------------------------------------

# 13. Current System State

-   Overlap contract active
-   Glue operator corrected
-   UI feed model working
-   Session authority stable
-   Seam scoring not yet implemented

System stable and ready for scoring integration.

------------------------------------------------------------------------

# 14. Conclusion

We have:

-   Shifted from naive append model
-   Implemented mathematically coherent overlap contract
-   Preserved authority invariants
-   Achieved better visual continuity
-   Designed next upgrade path for seam scoring

This document supersedes earlier continuity report.
