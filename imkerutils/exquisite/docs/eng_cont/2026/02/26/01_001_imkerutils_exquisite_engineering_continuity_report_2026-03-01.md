# imkerutils.exquisite — Engineering Continuity Report (Session Log)

**Date:** 2026-03-01 (America/New_York)  
**Author:** ChatGPT (embedded engineering consultant)  
**Project:** `imkerutils/exquisite/`  
**Scope of this report:** A detailed continuity write-up of the work, decisions, refactors, breakages, and architectural shifts discussed in this session. This is intentionally exhaustive so you can re-enter the codebase later and understand *exactly* what changed and why.

---

## 0. Executive summary (what changed architecturally)

Across this session, we changed the project’s conceptual model in **three** big ways:

1. **API-side “tile generation” is now treated as the primary truth**, and we moved away from a complicated “prompting + multi-candidate scoring” loop.  
   - You explicitly asked to remove “best-of-three” candidate selection and “just use the first thing we get.”
   - This is a major architectural simplification: *pipeline correctness* becomes more about **correct input packing** (band/tile/mask semantics) than about post-hoc ranking.

2. **We re-evaluated (and partially redefined) the tile gluing contract**:  
   - Original contract: **OVERLAP=256**, crop/paste a **768px** patch from the 1024 tile, and grow the canvas by **ADVANCE=512** each step.
   - New direction you requested: **“paste the whole API output directly, without trimming.”**
   - That implies **OVERLAP must be 512**, so the “patch” becomes the full 1024 tile and the paste origin becomes `w - 512` (x_ltr) rather than `w - 256`.

3. **We moved from “hard seam” assumptions to “soft seam” expectations**:  
   - You observed: “I’m still seeing a hard edge in gluing… it should look more like a fade when details mismatch.”
   - This leads to a structural requirement: overlap regions should be blended (feathered), and/or model-side mask semantics should be used to force continuity.

These changes are “architectural facts” because they affect:
- data contracts (what band is, what overlap is),
- invariants (canvas growth and seam behavior),
- UI expectations (visible new content each step),
- and the API request format (mask semantics and size).

---

## 1. The original pipeline mental model (before this session)

### 1.1 Tile geometry and growth
The project is built around repeated extension steps that generate a **1024×1024** tile and then splice part of it into a growing canvas.

Core constants historically used:

- `TILE_PX = 1024`
- `HALF_PX = 512`
- `BAND_PX = 512` (conditioning strip thickness)
- `OVERLAP_PX = 256` (how much existing canvas is overwritten)
- `ADVANCE_PX = 512` (how much canvas grows per step)
- patch thickness along extension axis: `PATCH_PX = OVERLAP_PX + ADVANCE_PX = 768`

### 1.2 “White diagram contract” (legacy)
The legacy gluing contract was:

- Extract conditioning band (512px) at the frontier of the existing canvas.
- Ask the model for a 1024 tile that includes both conditioning + novel content.
- Crop out a patch of width 768 from the returned tile:
  - `start = HALF_PX - OVERLAP_PX = 256`
  - `end = HALF_PX + ADVANCE_PX = 1024`
- Paste that patch onto the canvas at position:
  - for x_ltr: `paste_x = w - OVERLAP_PX` (i.e., `w - 256`)
- The canvas grows by `ADVANCE_PX = 512` each step.

This contract makes the overlap seam deterministic:
- 256px of the patch overwrites the last 256px of the prior canvas, and
- 512px extends beyond the previous frontier.

### 1.3 Best-of-three (multi-candidate scoring)
There was a “best-of-N” candidate selection strategy:
- Make multiple API calls (3 by default in many versions).
- Score candidates using edge-based metrics on seam-adjacent strips.
- Select best tile, then glue.

You already had a sophisticated scoring function:
- Extract seam-adjacent generated strip.
- Convert to edge map.
- Weight by proximity to seam.
- Compute weighted MSE.

This served two goals:
- maximize continuity (reduce seams),
- reduce catastrophic “wrong prompt” drift.

---

## 2. Why we questioned the prompting architecture

You provided evidence that:
- A *simple prompt in the UI* with the same tile input gave much better continuity than your package prompt scaffolding.
- This suggested the “overly complicated prompting” approach was counterproductive and likely causing model confusion.

**Resulting conclusion:**  
Prompt engineering complexity is not automatically a win. Correctness might come primarily from:
- correct image packing (band placement),
- correct mask semantics (what is frozen vs editable),
- correct seam blending.

---

## 3. Mask semantics: the “freeze → free” gradient concept

### 3.1 What you wanted conceptually
You described a masking strategy:

- We cut a **512px band at the frontier**.
- When asking the model for a 1024×1024 extension:
  - The mask should act on the **conditioning half** (width 512) such that:
    - near the *inner boundary* (opposite the frontier), pixels are “fixed”
    - toward the *frontier boundary*, pixels become more “free”
- When you said “noise,” you clarified:
  - you meant “free” as in diffusion sampling is allowed to treat it like noise / unconstrained.

### 3.2 The key question: what size mask is passed?
You asked:
- If we request a 1024×1024 output tile, is the mask:
  - 1024×1024 aligned with the entire tile?
  - or only a 512×1024 band?

**Engineering conclusion (pragmatic):**  
For APIs that accept a mask, it typically must match the full output image size (i.e., 1024×1024), because it is a per-pixel gate over the whole sampling space.  
So in practice:
- We build a 1024×1024 **reference image** (where the conditioning band is placed into the appropriate half),
- and a 1024×1024 **mask** that indicates editability (or “strength”) per pixel.

### 3.3 What was wrong with the previous diagram (the failed alignment)
You objected strongly to a previous image/diagram because it failed the core geometric contract:

- It did not reflect that only a **512px frontier band** is conditioning-relevant.
- It implied “noise” or “free” in a region that was not the correct location relative to the frontier.
- It blurred the distinction between:
  - the *existing canvas interior*, which should remain unchanged, and
  - the *frontier overlap region*, which should be editable/negotiated,
  - the *new region*, which should be fully generated.

In other words: the diagram confused **coordinate frames**:
- canvas space vs tile space,
- conditioning band space vs output tile space.

---

## 4. Convention A vs Convention B: the “ground truth connection” problem

You asked for “connection to ground truth” and whether “Convention A vs Convention B actually work correctly on the GPT end.”

While the original conversation included the naming, the essential distinction was:

- **Convention A** (legacy-ish): Treat the overlap + advance contract as a post-processing splice and enforce conditioning with hard identity checks.
- **Convention B** (the direction you pushed): Treat the model as producing a full coherent tile where conditioning is placed in the correct half, and seam consistency is achieved primarily by:
  - correct packing,
  - correct masking / editability gradient,
  - and optionally blending in overlap.

Your decision: **refactor to apply Convention B.**

---

## 5. Codebase tour: what files mattered in this session

You provided full contents of key files:

### 5.1 `imkerutils/exquisite/geometry/tile_mode.py`
Defines:
- constants: TILE_PX, HALF_PX, BAND_PX, OVERLAP_PX, ADVANCE_PX
- extraction of conditioning band from canvas
- split tile into conditioning half + new half
- `_tile_patch_for_overlap_glue` (defines what portion of tile is pasted)
- `glue` (defines where patch is pasted into output canvas)
- expected next canvas size

This file is the **single source of truth** for geometry contracts.

### 5.2 `imkerutils/exquisite/pipeline/session.py`
Defines:
- session lifecycle: create/open
- step execution:
  - mock generation (local deterministic)
  - real generation (API client)
- candidate scoring (in earlier versions)
- optional seam feathering `_glue_with_feather`
- persistence layout of step artifacts

This file is the **pipeline** and artifact recorder.

### 5.3 `imkerutils/exquisite/geometry/reference_tile.py`
Defines (as discussed in-session):
- how to build a 1024×1024 reference tile from a 512px band
- how to build a mask image with 0..255 semantics
- includes `KEEP_PX = HALF_PX - OVERLAP_PX`
- `_set_keep_alpha(...)` historically used alpha=128 for “keep region”

This file is the **mask+reference generator** and is central to Convention B.

---

## 6. The “remove best-of-three” refactor

### 6.1 You requested
> “remove the part of the pipeline where 3 API calls are compared. I just want to use the first thing we get.”

### 6.2 What that changes architecturally
- Pipeline becomes **single-sample**:
  - no more multi-candidate scoring,
  - no more candidate directories and score JSONs (or they become trivial).
- Debugging becomes:
  - easier: one tile per step, fewer files,
  - riskier: you lose resilience to occasional bad outputs.

### 6.3 Minimum pipeline behavior after this change
Per step, always persist:
- `prompt.txt`
- `conditioning_band.png`
- `canvas_before.png`
- `tile_full.png`
- `new_half.png`
- `canvas_after.png`
- `committed.ok` or `rejected.err`

This keeps continuity artifacts even without scoring.

---

## 7. Feathering (`feather_px`): what it does

You asked:
> “Tell me what this parameter does: `feather_px: int = 0`”

### 7.1 What feathering does
In `session.py`, `_glue_with_feather(...)`:

- If `feather_px <= 0`, it calls `glue(...)` directly: **hard seam**.
- If `feather_px > 0`, it blends the overlap region using a linear ramp mask:
  - builds a grayscale ramp from 0 → 255 across `feather_px`,
  - composites `tile_overlap` over `canvas_overlap` using that mask,
  - pastes the blended overlap into the tile,
  - then calls `glue(canvas, tile2, mode)`.

### 7.2 Why you still saw a hard edge
If `feather_px` is:
- left at 0 (default), seam is hard.
- set too small relative to overlap width, seam may still look abrupt.

This matters even more if we shift to **OVERLAP=512** (full conditioning overlap):
- you likely want feathering across a large portion of the overlap,
- or even across *the full overlap* if you want the seam to behave like a dissolve.

---

## 8. “Glue at 0 not 256” and “paste the whole output” — the big geometry change

You stated:

- “Want to glue in at 0 in new piece, not 256… Full glue in when feather is set to 0”
- “I’m saying just glue the whole API output directly in where it goes, without trimming”

### 8.1 Why this is incompatible with OVERLAP=256
With `OVERLAP_PX=256`, `_tile_patch_for_overlap_glue` necessarily trims:
- `a = 512 - 256 = 256`
- patch is `tile[256:1024]`

So if you want **no trimming**, `a` must become 0.

### 8.2 The cleanest contract that implements “no trimming”
Set:
- `OVERLAP_PX = 512` (full conditioning overlap),
- keep `ADVANCE_PX = 512`.

Then:
- `a = 512 - 512 = 0`
- `b = 512 + 512 = 1024`
- patch width becomes 1024 (full tile).

**Glue position becomes:**
- x_ltr: paste at `w - OVERLAP_PX = w - 512`
- so the conditioning half overlaps exactly with the canvas frontier band.

This produces the interpretation:
- left half of tile = conditioning half aligned to frontier band,
- right half = novel extension region.

### 8.3 Architectural consequences
This is not a small tweak. It changes:
- global constants and assumptions across the project
- keep-region computations (`KEEP_PX = HALF_PX - OVERLAP_PX`)
  - with OVERLAP=512, KEEP_PX becomes 0, which breaks “keep-only 256” logic
- any enforcement code that assumes overlap is 256
- any mask generation code that assumes a 256px hard keep area

So moving to OVERLAP=512 forces a re-design of:
- keep/identity enforcement (likely becomes *whole conditioning half*),
- mask alpha ramps,
- reference_tile.py logic.

---

## 9. The “alpha must persist through glue” concept (and why it got messy)

You asked:
> “When the new image is glued back in, glue it back in with the same alpha, so that pixels are actually new according to mask.”

This request implies:
- the model output should contain an alpha channel (or mask-derived alpha),
- and the canvas should be composited using that alpha, not hard pasted.

### 9.1 Why this is tricky in the current architecture
Right now:
- canvas is stored as RGB PNGs (no alpha),
- tiles are converted to RGB,
- glue uses `out.paste(patch, ...)` which is an overwrite paste without transparency.

So to “preserve alpha” you would need:
- tile outputs to be RGBA (or at least an alpha mask available),
- the canvas to become RGBA consistently,
- glue to use alpha compositing (e.g., `Image.alpha_composite` or `paste(..., mask=alpha)`).

### 9.2 What we *actually* have today
Instead of alpha-preserving glue, we currently have:
- optional feathering in overlap using a ramp mask,
- hard paste otherwise.

So the current system can create fades **only in the overlap** (client-side), not “pixel is new according to model mask” globally.

### 9.3 Going-forward design choice
You need to decide whether:
- (A) you want the canvas to remain RGB and do all seam smoothing client-side, or
- (B) you want an RGBA canvas and treat the model mask as authoritative for compositing.

Option B is a bigger refactor but aligns with your “mask means newness” desire.

---

## 10. Operational issues encountered (and what they mean)

### 10.1 `OSError: [Errno 48] Address already in use`
You got:

```
OSError: [Errno 48] Address already in use
```

This is unrelated to geometry. It means:
- your UI server is already bound to the requested port (often 8000),
- or another process occupies the port.

Fixes:
- kill the process using that port (e.g., `lsof -i :8000` then `kill PID`)
- or run the UI on a different port.

This error does **not** mean the tile pipeline is broken; it just blocks the server from starting.

### 10.2 “No new tile even appears”
You reported that UI runs but visually there is no new tile.

Common causes in this architecture:
- `execute_step_*` is rejecting silently (status "rejected") and the UI isn’t surfacing that prominently.
- identity enforcement / post-enforcement causes the resulting tile to effectively paste the old band back (so visually unchanged).
- glue paste region is wrong (e.g., paste_x miscomputed) so new region is overwritten by old canvas or pasted off-frame.
- the UI is not reloading the updated `canvas_after.png` (caching issue).

**Immediate debugging action:**  
Inspect the step directory:
- is `committed.ok` present?
- what does `canvas_after.png` look like compared to `canvas_before.png`?
- is there a `rejected.err` or warning file?

---

## 11. What script to change for seam behavior (your “hard edge” complaint)

The seam behavior is controlled by:
- `imkerutils/exquisite/pipeline/session.py` → `_glue_with_feather(...)` (client-side blending)
- `imkerutils/exquisite/geometry/tile_mode.py` → `glue(...)` and `_tile_patch_for_overlap_glue(...)` (geometry paste region)
- `imkerutils/exquisite/geometry/reference_tile.py` (mask / alpha intent if you use it)

If you want a fade, the *first* lever is:
- increase `feather_px` from 0 to something meaningful.

If you want no trimming, the lever is:
- change overlap contract to 512 and patch to full tile.

---

## 12. Going-forward roadmap (what must happen next)

This is the “what now” section: what engineering tasks are implied by the decisions above.

### 12.1 Decide the canonical geometry contract
You must choose:

- **Contract 1 (Legacy / 256 overlap):**
  - OVERLAP=256, ADVANCE=512, patch=768 crop.
  - Works with existing keep logic and “KEEP_PX=256” semantics.
  - Harder to ensure continuity because tile is not pasted fully.

- **Contract 2 (Requested / full tile paste):**
  - OVERLAP=512, ADVANCE=512, patch=1024 (no trim).
  - Directly matches “paste full API output.”
  - Breaks any code that assumes KEEP_PX>0 (keep-only enforcement, reference_tile keep alpha).
  - Requires updating:
    - `reference_tile.py` mask logic,
    - enforcement logic in session/step,
    - any scoring strip calculations if you reintroduce them.

Given your explicit request, the direction is **Contract 2**.

### 12.2 Rebuild mask semantics to match Contract 2
For Contract 2, you likely want:

- Entire conditioning half overlaps the frontier band (512px).
- Mask across the conditioning half should be a **gradient**:
  - inner side: fixed (255)
  - toward seam: more editable (down to 0 or some floor)
- New half is fully editable (0) if the mask is “0=editable”.

But you also said:
> “Let’s assume values between 255 and 0 have meaning and proceed like that.”

So you want a *continuous* control signal.

**This requires:**
- A precise definition of what “mask intensity” means in the chosen API:
  - 255 = keep or 255 = edit? (APIs differ!)
- A consistent mapping to whatever the model expects.

### 12.3 Decide whether to keep post-enforcement
Your current pipeline includes `_post_enforce_keep_into_tile` which pastes only a 256px keep region.

Under Contract 2:
- KEEP_PX becomes 0 if you define KEEP_PX as HALF-OVERLAP.
- That code becomes nonsensical.

So you need to re-spec:
- either “post-enforce the entire conditioning half (512px)”
- or disable post-enforce and rely on mask + model to maintain conditioning.

Given your goal (“continuously extends”), disabling enforcement initially is often the best way to see real model behavior.

### 12.4 UI diagnostics: make rejections obvious
Your frustration “it’s not producing anything new” suggests the UI needs:

- a visible “last step status: committed/rejected”
- display of `rejected.err` if present
- an always-on link to `canvas_before.png` and `canvas_after.png`
- maybe a “diff viewer” or blink comparator

This will prevent silent failure loops.

### 12.5 Testing plan: ground truth checks
To “connect to ground truth,” do tests where you know expected geometry:

1. Start with a simple synthetic image (gridlines, rulers, colored bands).
2. Run one step.
3. Verify that in output canvas:
   - the overlap region aligns exactly where expected,
   - the new region appears exactly where expected.

If Contract 2 is in place:
- seam alignment should be exactly at the 512 boundary.

---

## 13. Files and invariants checklist (for future you)

### 13.1 Invariants that must always hold
- Tile generated by model is always 1024×1024.
- Conditioning band extracted from canvas is always 512px thick on the growth axis.
- Canvas grows by exactly 512px per step on the growth axis.
- After committing, `canvas_after.png` replaces `state.canvas_path`.

### 13.2 Step artifact layout expectations
For each step directory:
- `prompt.txt`
- `conditioning_band.png`
- `canvas_before.png`
- `tile_full.png`
- `new_half.png`
- `canvas_after.png`
- `committed.ok` OR `rejected.err`

If any are missing, pipeline is not behaving as expected.

---

## 14. Summary of “what you asked for” vs “what the code currently does”

### 14.1 You asked for:
- mask-based conditioning with a gradient from fixed→free across the 512 conditioning width
- no best-of-three
- no trimming: paste the full tile output into the canvas
- seams should fade when there’s mismatch, not hard-cut

### 14.2 Current code (as pasted) does:
- best-of-three removed in your latest `session.py` snippet (single sample)
- seam feathering exists but only applies if `feather_px > 0`
- trimming is still present because `tile_mode.py` is still `OVERLAP=256` and patch is 768
- keep-only enforcement still pastes 256px, not 512px
- alpha semantics from `reference_tile.py` are not composited into the canvas

So: the “no trimming” request is not satisfied until the geometry constants and glue contract are changed.

---

## 15. Immediate next changes I recommend (in order)

1. **Pick Contract 2 and implement it consistently**:
   - set OVERLAP=512
   - patch becomes full tile (no trimming)
   - update glue paste coordinates accordingly

2. **Update `reference_tile.py` for Contract 2**:
   - replace KEEP-only 256 logic with a proper gradient ramp across 512
   - ensure mask matches tile size (1024×1024)
   - decide consistent meaning of mask values (0..255)

3. **Temporarily disable post-enforcement**:
   - to observe actual model continuity behavior without your code rewriting pixels

4. **Set feathering aggressively during debug**:
   - e.g., `feather_px = 512` to force a visible dissolve across the whole overlap

5. **Improve UI error surfacing**:
   - show commit/reject status
   - show reason file

---

## 16. Appendix: the most important “gotchas” we tripped over

- **Mask meaning is not universal.** You insisted “assume 0..255 has meaning.” Yes—but the polarity (keep vs edit) must match the API.
- **Overlaps and “keep” logic are tightly coupled.** If you change overlap, keep logic and mask logic must change too.
- **Hard seam is expected when feather_px=0.** If you want fade, set feather_px > 0.
- **Port-in-use errors are operational, not architectural.** Don’t conflate them with pipeline breakage.
- **Silent rejections create the experience of “nothing is happening.”** Always check step artifacts.

---

## 17. Closing note

You are not crazy to want “ground truth” here. This pipeline is fundamentally an exercise in **coordinate-frame correctness**:
- where the band lives,
- where the tile lives,
- where the seam lives,
- and what the mask means.

Once the geometry contract is correct and the UI exposes step success/failure clearly, you’ll be able to iterate on mask/prompt semantics with much less pain.
