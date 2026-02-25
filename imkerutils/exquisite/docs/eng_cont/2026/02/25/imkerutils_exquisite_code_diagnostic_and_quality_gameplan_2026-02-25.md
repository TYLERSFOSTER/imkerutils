# imkerutils.exquisite — Ground-Truth Diagnostic (Code-Level) + Quality Improvement Gameplan
**Date:** 2026-02-25 (America/New_York)  
**Scope:** Based on the exact code you pasted: `reference_tile.py`, `api/openai_client.py`, `pipeline/session.py`, `geometry/overlap_score.py`, plus the current `tile_mode.py` contract you previously provided.

This is **not** a “high-level theory” doc. It’s a **concrete, file-by-file reality alignment**: what is correct, what is likely wrong, and what factors in the repo *today* can explain seam quality issues or instability.

---

## 0. Current ground-truth contract (as implemented)
From `tile_mode.py` (your pasted version):

- `TILE_PX = 1024`
- `BAND_PX = 512` extracted from canvas frontier.
- Overlap/advance contract:
  - `OVERLAP_PX = 256`
  - `ADVANCE_PX = 256`
  - glue uses **patch** `tile[256:768]` (or y-analog) pasted at `(w - 256)` (or shifted variants), so:
    - last **256px of existing canvas** are overwritten
    - **256px new** are appended
    - net growth = +256

**Critical derived fact:** there are *two* perceptual “seam boundaries”:
1. **Interior/overlap boundary** at output x = `w0 - 256` (old interior meets overwritten overlap).
2. **Overlap/new boundary** at output x = `w0` (overlap meets truly new pixels).

For the overlap/advance model, the seam you usually care about is **(2)**: the model must continue structure from old frontier into the new region.

---

## 1. Diagnostic: `geometry/reference_tile.py` (reference tile + mask)
### 1.1 Mask polarity appears correct
You document:

- `alpha=255` => preserve (NOT edited)
- `alpha=0` => editable (regenerated)

And in `build_reference_tile_and_mask()` you:
- start fully opaque (`alpha=255`)
- carve editable half to `alpha=0` via `_set_alpha_rect(...)`

This matches the “transparent == editable” convention historically used by OpenAI edits/inpainting.

### 1.2 Placement conventions align with `split_tile()` and post-enforcement
For each mode:

- `x_ltr`: conditioning band pasted at x=0 (left half), editable is right half
- `x_rtl`: conditioning band pasted at x=512 (right half), editable is left half
- `y_ttb`: conditioning band pasted at y=0 (top half), editable bottom half
- `y_btt`: conditioning band pasted at y=512 (bottom half), editable top half

This matches both:
- `tile_mode.split_tile()`
- `OpenAITileGeneratorClient._post_enforce_conditioning_half()`

So **orientation** is consistent.

### 1.3 Potential bug / footgun: `_set_alpha_rect` uses an odd “paste merged RGBA” pattern
Current code ends with:

```py
mask_rgba.paste(Image.merge("RGBA", (r, g, b, a)))
```

That *replaces the entire image* (at (0,0)) with a new merged RGBA.

It “works” because:
- r,g,b are unchanged
- a has your modifications
- same size as mask

But it’s easy to misread and is fragile.

**Recommended fix (behavior-identical, clearer):**
```py
mask_rgba.putalpha(a)
```

This is not likely the cause of seam mismatch, but it’s a “repo factor” for correctness clarity.

### 1.4 Seam cue + scaffold are correctly quarantined (good)
- `continuation_cue` draws only inside conditioning half.
- Conditioning half is overwritten post-gen by the original band.
So cues do not pollute the final canvas. Good.

---

## 2. Diagnostic: `api/openai_client.py` (real OpenAI generation)
### 2.1 The pipeline is genuinely image-conditioned now (good)
You build `ref + mask` and call `images.edits(...)` with both. That’s the correct *architectural* move.

### 2.2 Major repo factor: model name drift / confusion in docs
- Code uses `MODEL_DEFAULT = "gpt-image-1"`
- Your earlier doc snippet showed `gpt-image-1.5`

If the doc and code disagree, you will get:
- inconsistent quality expectations
- inconsistent behavior changes when someone “fixes the doc” or “fixes the code”

**Action:** bind `GPT_MODEL_AUTHORITY` to exactly what code uses in the currently-running environment.

### 2.3 Missing explicit output format/quality knobs
You do:
```py
size="1024x1024"
```
but do not set:
- output format (png vs webp)
- quality setting (if available via the model)

This may affect micro-artifacts at seams (compression, antialiasing).

**Action:** add explicit output format = PNG if supported (because you do byte-level invariants and edge-based scoring).

### 2.4 Hard post-enforcement is correct for invariants, but it changes what “seam” means
You overwrite the entire conditioning half after generation:
- good for strict invariants
- but it means the model can’t “heal” any misalignment *by slightly altering conditioning pixels*.

This is fine, but it implies you should score the **generated-side strip** adjacent to the seam (see §3), not the overwritten overlap strip.

---

## 3. Diagnostic: `pipeline/session.py` (the big one)
### 3.1 **Immediate breaking factor:** `execute_step_real` imports numpy
You saw:
> `No module named 'numpy'`

And here it is:
```py
import numpy as np
```

So the “real step” path is **non-hermetic** w.r.t. dependencies: it assumes numpy exists, but your venv doesn’t have it installed (or it was removed).

This is a **hard stop** for real quality iteration because it prevents running the real pipeline at all.

**Fix options:**
- A) Add numpy as an explicit dependency for `exquisite` (fastest).
- B) Remove numpy dependency from real path and reuse the PIL-based scoring pipeline you already wrote for mock path.
- C) Keep numpy optional with a fallback scorer.

Given your stated “hermetic / contract-first” ethos, **B or C** is more aligned.

### 3.2 Candidate scoring: mock path and real path are scoring *different things*
- `execute_step_mock` uses `_overlap_crops_for_scoring()` which (for x_ltr/y_ttb) ends up comparing **tile’s conditioning-side overlap region** (`tile[256..512]`) with canvas overlap.
- But after post-enforcement, that region is **guaranteed** to match extremely well, so the score can become nearly meaningless.

Meanwhile `execute_step_real` intentionally scores:
- canvas frontier strip vs **generated strip adjacent to seam** (`tile[512..768]` for x_ltr).

That is the correct objective for overlap/advance: “does the new region continue what the frontier suggests?”

**Repo factor:** you may think “scoring works” because mock looks stable, but real scoring (and real seam behavior) is different.

**Action:** unify scoring so both mock and real score the same semantic seam: **generated-side strip adjacent to seam**.

### 3.3 `geometry/overlap_score.py` matches the *real* semantic scoring (good)
Your standalone `overlap_score.py` implements:
- canvas frontier overlap strip vs tile generated-side strip adjacent to seam
- weighted Sobel correlation (cosine similarity)

That aligns with the *real path* logic, not the mock path logic.

**Action:** make `execute_step_mock` use `overlap_score.score_tile_sobel_corr(...)` (or the same strip extraction), and delete/retire `_overlap_crops_for_scoring()` to avoid divergence.

### 3.4 Feather blending: there are two implementations with different semantics
- Mock path: `_glue_with_feather()` blends inside the overlap window by modifying the tile then calling glue().
- Real path: `_glue_with_feather()` blends *after glue* across the “seam boundary” between old and new.

Both can be reasonable, but they are not equivalent, and they target different boundaries.

Given the overlap/advance design, the boundary you typically want to hide is **at `w0`** (overlap/new boundary), because that’s where the model’s continuation begins.

**Action:** pick one feather policy and bind it:
- either “blend at overlap/new boundary (x=w0)”
- or “blend inside overlap window”
Then implement exactly one.

---

## 4. Primary contributing factors to seam mismatch (given current code)
Assuming your geometry glue is correct, the most plausible present contributors are:

1. **The model simply fails to continue lines cleanly across the seam** even when it sees context.
   - This is expected behavior; the fix is selection/scoring + prompt conditioning + sometimes scaffold.

2. **Scoring divergence (mock vs real) makes iteration deceptive.**
   - You might be “optimizing” a metric that doesn’t predict visible seam quality in the real pipeline.

3. **Dependency instability (numpy missing) blocks real iteration**, forcing you back to mock behavior.

4. **Missing explicit output format/quality** may introduce micro artifacts that your edge score punishes unpredictably.

---

## 5. Gameplan: sequential + parallel tracks
### 5.1 Sequential track (do in this order)
#### S1 — Unblock real runs (dependency reality)
- Either add numpy to deps OR remove numpy usage in `execute_step_real`.
- Success criterion: `execute_step_real` runs in your venv without manual pip installs.

#### S2 — Bind one scoring authority (single metric, single strip semantics)
- Define “scoring strip” once:
  - canvas: last 256px frontier
  - tile: generated strip adjacent to seam
- Use the same scorer for both mock and real.
- Persist:
  - `canvas_strip.png`
  - `tile_strip.png`
  - `score.json` with metric + parameters
- Success criterion: “best candidate” selection is explainable with artifacts.

#### S3 — Candidate generation (n=3) + selection becomes default
- Make `num_candidates=3` default in real path (already present as arg).
- Success criterion: visible seam improves statistically over repeated steps.

#### S4 — One feather policy, measured
- Pick *one* feather strategy, start with `feather_px=0` baseline.
- Add A/B artifacts per step: before/after feather.
- Success criterion: feather improves seam without blurring structure.

#### S5 — Prompt + scaffold knobs (controlled experiments)
- Try scaffold_fill ON for a few steps.
- Try a slightly stronger “continue exact linework” clause.
- Success criterion: improved edge continuation without style drift.

---

### 5.2 Parallel track A — Instrumentation (fast, low risk)
Add per-step artifacts that make debugging trivial:

- `ref_tile.png`
- `mask.png`
- `tile_out_raw.png` (pre post-enforce, if available)
- `tile_out_enforced.png`
- `canvas_strip.png`, `tile_strip.png` (the scored ones)
- `score_metric.json` (metric name + params)
- `prompt_full.txt` (the expanded prompt)
- `model_response_meta.json` (if safe)

This lets you answer “why did it choose candidate 2?” instantly.

### 5.3 Parallel track B — Metric improvements (still cheap)
You already have two metrics:
- negative weighted MSE on Sobel magnitude
- weighted cosine correlation of Sobel magnitude

Run both, store both, pick best by one primary metric but log both.  
Later you can learn which correlates with human judgment.

### 5.4 Parallel track C — Model-side knobs
If the API supports it for `gpt-image-1`:
- set `output_format="png"`
- set quality/high detail (if parameter exists)
- set prompt to “do not rescale; do not change stroke thickness; continue edges”

---

## 6. Minimal authoritative “next commit” checklist
If you want the shortest path to better seams **without redesign**:

1. **Fix numpy reality** (dependency or remove).
2. **Unify scoring semantics** (score generated strip adjacent to seam everywhere).
3. **Make 3-candidate selection default** in real path.
4. Add **strip artifacts** to every step.
5. Bind **one feather policy** (off by default, measured).

---

## 7. Concrete “gotchas” to keep in mind
- Scoring the preserved overlap region is mostly pointless once post-enforcement exists.
- If you change `OVERLAP_PX` or `ADVANCE_PX`, you must update:
  - tile_mode patch crop
  - scoring strip extraction
  - feather boundary logic
- If you ever change where the conditioning band is pasted in the reference tile, you must update:
  - `split_tile`
  - post-enforcement
  - scoring strip extraction

---

**End.**
