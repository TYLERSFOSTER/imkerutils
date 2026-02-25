# Exquisite Seam/Overlap Incident Report — “How We Got Stuck and What Not To Do Again”
**Project:** `imkerutils.exquisite`  
**Date:** 2026-02-25  

> You’re right to be frustrated. This thread devolved into “patch math thrash” without establishing hard observability. This is a blunt postmortem: what went wrong in the debugging approach, what an engineer should do instead, and concrete better ideas to get seam match-up working.

---

## Executive summary

We burned cycles arguing about **256 vs 512 vs 768** and shuffling crop windows while **not proving** (with artifacts) which of these was true:

1. **Generator tile seam region is wrong** (high probability).
2. **We are pasting the wrong region of the tile** (possible).
3. **Band identity is enforced into the wrong place** (possible).
4. **We are scoring the wrong strip** and selecting a bad candidate (possible).
5. **We are looking at the wrong boundary** (step boundary vs seam boundary) (very possible).

Engineering failure: we did **geometry-by-chat** instead of geometry-by-evidence.

---

## The contract we were trying to implement

- `TILE_PX = 1024`
- `BAND_PX = 512` extracted from the canvas frontier (conditioning input)
- model returns a full **1024×1024 tile**
- net growth per step: `ADVANCE_PX = 512`
- overwrite overlap: `OVERLAP_PX = 256`
- paste payload: `PATCH_PX = OVERLAP_PX + ADVANCE_PX = 768`

So the pasted patch straddles the seam: **256 px** from the conditioning side + **512 px** new.

This contract is coherent.

---

## Immediate failure we caused

### The “name 'a' is not defined” crash
A debug print referenced `a`/`b` inside `glue()` even though those variables only existed inside `_tile_patch_for_overlap_glue()`.

**Bad engineering pattern:** debug prints that can crash.  
**Fix:** only print variables in scope, or print from inside the function where they exist.

This crash didn’t just waste time; it destroyed trust and momentum.

---

## The deeper failure: no observability

### Missing invariant checks
The seam dispute (“panes at 512 not 256”) should have been settled immediately by saving and inspecting:

- `conditioning_band.png`
- `tile_full.png`
- `tile_patch.png` (what glue actually pastes)
- `canvas_before.png`
- `canvas_after.png`

And then drawing ONE vertical line at the paste boundary.

Instead, we debated from screenshots and mental models.

### Multiple slice points, treated as one
There are *at least* these slicing/cropping locations:

1. `extract_conditioning_band()` — slices canvas to produce the 512 band.
2. `post_enforce_band_identity` paste — overwrites part of the tile with the band.
3. `split_tile()` — defines what “conditioning half” means for identity checks.
4. `_tile_patch_for_overlap_glue()` — defines the actual 768 patch.
5. `glue()` — chooses paste coordinates into the output canvas.
6. `_extract_scoring_strips()` — slices strips for scoring candidate tiles.
7. `_overlap_crops_for_blend()` — slices overlap for feather blending.

Failure mode: change one crop window while other crop windows encode old assumptions → silent disagreement between enforcement, scoring, and glue.

---

## Likely root causes of “still no good”

Given the code shown in `session.py`, the patch crop and paste coordinates are internally consistent **if** the tile is constructed in the assumed coordinate frame. What remains high-probability:

### 1) Generator alignment mismatch
Even with post-enforcement, you might be enforcing the band into the wrong region for the mode, *relative to how the model interprets conditioning*.

Symptom: identity checks pass because you paste the band in, but the **generated pixels adjacent to seam** are incoherent.

### 2) Scoring selects the wrong candidate
If the score strip doesn’t correspond to what will be pasted / what determines visible continuity, you can “optimize the wrong thing” and lock in bad seams.

### 3) You are visually diagnosing the wrong boundary
The “pane” you see could be:
- the boundary between steps (every 512),
- the internal half split (512),
- or a real seam artifact.

Without an overlay showing paste bounds, you can’t disambiguate.

---

## Better ideas (high ROI, low thrash)

### Make paste bounds visible (debug overlay)
Add a debug mode that draws 1px bright lines on:
- seam location in `tile_full`
- start/end of `tile_patch`
- paste origin in `canvas_after`

Then you stop guessing.

### Save *every* intermediate crop as a step artifact
For each step, write:
- `band.png`
- `tile_full.png`
- `tile_patch.png`
- `score_canvas_strip.png`
- `score_tile_strip.png`
- `blend_canvas_ov.png`
- `blend_tile_ov.png`
- `canvas_after.png`

Cheap, deterministic, ends arguments.

### Centralize seam-frame math in one function
Create a single function returning all boxes/origins:
- band box on canvas
- band box on tile (post-enforce)
- cond-half box (identity)
- score strip box
- overlap blend box
- patch box
- patch paste origin on output

Everything uses those boxes. No duplicated 256/512 arithmetic.

### Feather blending may be creating “pane haze”
For line art, alpha feather can look like a pane. Consider:
- no feather (first), or
- gradient-domain / 1D derivative blending only inside overlap.

### Improve scoring for line art
FIND_EDGES + MSE is crude for Darrow-like texture. Better:
- Sobel-like gradient correlation,
- normalized cross-correlation near seam,
- Laplacian energy match, weighted toward seam.

---

## What an engineer should not do (and we did)

- Do not “reason from desired outcome” instead of localizing where the defect first appears.
- Do not change constants while leaving enforcement/scoring/blending using old assumptions.
- Do not introduce debug prints that crash.
- Do not rewrite whole files repeatedly; make minimal diffs and re-run.

---

## Correct workflow for the next engineer

1. Reproduce on ONE step.
2. Instrument: save all intermediates + overlay boundaries.
3. Locate where the pane first appears (`tile_full` vs `tile_patch` vs `canvas_after`).
4. Fix only that stage.
5. Add regression tests for crop boxes and paste positions.

---

## Mea culpa (what I did wrong here)

- I let this drift into parameter thrash without demanding the minimal artifact set.
- I increased code surface area before making the pipeline observable.
- I caused a scoping crash in debug output.
- I didn’t force a disciplined “find the stage that injects the defect” loop.

That’s not acceptable production engineering behavior.

---

## Checklist

- [ ] Save: band, tile_full, tile_patch, canvas_before, canvas_after
- [ ] Overlay seam + patch bounds
- [ ] Verify band paste region per mode
- [ ] Verify score strip equals “what matters”
- [ ] Verify patch crop window matches paste payload
- [ ] Add regression tests for all crop boxes

**End.**
