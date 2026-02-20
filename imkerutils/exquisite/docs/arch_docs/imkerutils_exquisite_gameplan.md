# imkerutils.exquisite — Gameplan (Extreme Detail)
**Date:** 2026-02-20 (America/New_York)  
**Role contract:** Human Project Owner ↔ LLM Consultant Engineer (Prime Directive in force)

This is a **design-first, contract-first** gameplan for building `imkerutils/exquisite/` as a small pipeline that produces an unfolding “exquisite corpse” image by repeatedly extending an image in a chosen direction using GPT image generation.

No code is committed by this document. It is a **build sequence** + **contracts** + **invariants** that keep the project hermetic and debuggable.

---

## 0. Definitions (shared vocabulary)

### Canvas
The evolving “master image” that grows over time.

### Step
One extension operation: extract a band from the canvas, call the image model, validate, composite, persist.

### Direction
Which side we extend: `right | left | up | down`.

### Band types
- **Context band**: pixels we provide to the model as *visual context* (usually the region adjacent to the seam).
- **Immutable band**: pixels that must remain identical after a step (e.g., a border or overlap zone).
- **Generation band**: the new pixels the model produces (the extension).

### Overlap (seam context)
A strip of width `overlap_px` near the seam that is included from the existing canvas so the generated portion can align and avoid visible stitching.

---

## 1. Non-negotiable invariants (v1)
These are **engineering physics** for v1; everything else is a feature.

### I1 — Exact output size
After each step, the new canvas dimensions are exactly predictable:
- extend right/left: `(N, M + L)`
- extend up/down: `(N + L, M)`
(where `N`=height, `M`=width, `L`=extension length in pixels)

### I2 — Immutable region preservation
We define an immutable region `B` (e.g., k-pixel border all around the canvas, or a seam-adjacent band), and enforce:
- For all pixels `(x,y) ∈ B`: `canvas_after[x,y] == canvas_before[x,y]`

How we enforce can be:
- **Pre-mask** (preferred if tooling supports masks) OR
- **Post-restore** (always possible): replace immutable pixels in output with original pixels.

### I3 — Hermetic artifacts
No behavior depends on ambient variables across caller boundaries:
- No `Path.cwd()` semantics leaking into outputs
- No output paths “guessed”
- A run writes to a declared root directory under a declared session ID

### I4 — Validation gate before composite
No step is committed unless validation passes:
- dimensions correct
- immutable region identical
- image decodes and matches expected mode/channels

If validation fails, the pipeline must:
- keep the previous canvas as authoritative
- write a failure report artifact
- present the failure to the UI without mutating the session state

### I5 — Reproducibility record
For each step we record:
- model name/version
- prompt payload (including templates and constraints)
- parameters (seed, temperature, size, overlap_px, immutable_px)
- hashes of input/output images

---

## 2. Submodule responsibilities (what lives where)

This section maps the proposed directory structure to responsibilities. The point is to prevent **leaky abstractions**.

### `api/` — GPT image API boundary
**Purpose:** translate an internal request object into an API call and return a typed response.

- **Inputs (contract):** `ImageGenRequest` (image bytes, optional mask bytes, prompt, size, model, params)
- **Outputs (contract):** `ImageGenResponse` (image bytes, safety info, usage/cost info, raw provider metadata)
- **No geometry:** API must not “know” about right/left/up/down; it only knows “here is an image + prompt + (optional) mask”.

### `geometry/` — pure image math
**Purpose:** deterministic pixel region selection and compositing.

- `extract_band.py`: compute region(s) for context/overlap
- `mask.py`: compute immutable masks as explicit pixel sets or binary images
- `composite.py`: paste the new generated band onto the old canvas
- `dimensions.py`: all coordinate transforms, sign conventions, asserts

This layer must be testable with **no network**.

### `prompt/` — deterministic prompt building
**Purpose:** produce a prompt payload that is **stable** and debuggable.

- `constraints.py`: boundary preservation clauses, style locks, negative constraints
- `templates.py`: reusable fragments
- `builder.py`: one function that builds the final prompt from:
  - user text
  - direction & extension geometry
  - invariant constraints

This layer should also record the final prompt used verbatim into step metadata.

### `state/` — session state + contracts
**Purpose:** define the canonical session record and artifact contracts.

- `session_state.py`: in-memory representation of “where we are”
- `metadata.py`: JSON-serializable structures (run header + per-step records)
- `contracts.py`: named artifacts and their canonical paths

### `pipeline/` — orchestration engine
**Purpose:** step machine and validation gating.

- `step.py`: step input/output dataclasses (one step == one transaction)
- `invariants.py`: dimension checks, immutable checks, decode checks
- `artifacts.py`: resolves canonical paths using the contract + session root
- `session.py`: the state machine (but does not do UI; provides events)

### `io/` — file/format correctness
**Purpose:** ensure images are loaded/saved consistently.

- `image_io.py`: load/save; enforce color mode conventions
- `atomic_write.py`: write artifacts atomically (tmp + rename)
- `formats.py`: explicit format/mode decisions (RGB vs RGBA, PNG vs JPG)

### `ui/` — browser UI boundary
**Purpose:** user interaction, live updates, and invoking pipeline steps.

- `server.py`: HTTP server + routes
- `websocket.py`: push step events to client
- `dto.py`: strict data transfer objects (no raw internal structures)

### `config/` and `logging/`
**Purpose:** explicit config schema + structured events.

- `schema.py`: define configuration (session root, model, overlap_px, immutable_px)
- `defaults.py`: a single place for v1 defaults
- `events.py`: event types emitted by pipeline (StepStarted, StepSucceeded, StepFailed)
- `usage.py`: cost accounting, budgets, estimates

### `tests/`
**Purpose:** hermetic tests for geometry/invariants/pipeline logic with mocked API.

---

## 3. The v1 pipeline transaction (single step)
This is the core loop. **One step is a transaction**: either it commits or it doesn’t.

### Inputs to a step
- `canvas` (current master image)
- `direction` (right/left/up/down)
- `extension_px = L`
- `overlap_px` (context band width)
- `immutable_policy` (what pixels must be preserved)
- `user_prompt` (human text)
- `model params` (model name, seed, temperature, output size)

### Step procedure (conceptual)
1. **Derive geometry plan**
   - compute `context_region` (includes overlap)
   - compute expected output dimensions
   - compute immutable mask/band definition

2. **Construct prompt payload**
   - combine user text + constraints + direction context
   - ensure deterministic ordering and formatting

3. **Prepare API request**
   - choose which image is sent:
     - minimal: send only context region
     - or: send full canvas with mask
   - choose whether to supply a mask
   - encode images

4. **Call API**
   - capture raw provider metadata and usage
   - handle transient errors/retries (without corrupting state)

5. **Decode API image output**
   - verify decodes and has expected channel mode

6. **Validate invariants**
   - dimension check
   - immutable region check (either because model honored mask or via post-restore verification)
   - seam/overlap identity check if we require it

7. **Composite**
   - paste generated band onto canvas
   - (optional) post-restore immutable region

8. **Persist artifacts**
   - write step output image
   - write step metadata JSON
   - write a “latest.png” symlink or copy (contracted)

9. **Emit events**
   - UI receives: started → succeeded/failed with paths + thumbnails

If any validation fails: **no commit**; we write failure artifacts and keep state unchanged.

---

## 4. Artifact contracts (v1)
We explicitly name the files and where they live. This prevents “where did it write?” drift.

### Session root
A single directory chosen at session start, e.g.:
- `imkerutils/_generated/exquisite/<session_id>/`

All artifacts are under this root.

### Canonical artifacts
- `session.json` — run header (immutable-ish) + pointer to steps
- `canvas_latest.png` — latest committed canvas
- `steps/0001/`
  - `input_canvas.png` (or a hash reference)
  - `context.png`
  - `mask.png` (if used)
  - `api_output.png`
  - `output_canvas.png`
  - `step.json`
  - `validation.json`
  - `failure.txt` (only on failure)

### Naming
- Step numbers are zero-padded for lexical order.
- Every artifact path is computed from `session_root` + step index; never from CWD.

---

## 5. UI contract (v1)
The UI is a thin layer that:
- shows the evolving canvas
- provides a text box for user prompt
- provides controls for direction, L, overlap, immutable policy
- shows progress states and failure reasons

### UI states
- Idle (ready)
- Running step (spinner/progress)
- Step succeeded (canvas updates)
- Step failed (canvas unchanged, show failure report, allow retry)

### UI → pipeline boundary
A single call:
- `pipeline.run_step(user_prompt, direction, extension_px, ...)`

And the pipeline emits structured events that the UI subscribes to.

---

## 6. Parameter defaults (sane v1)
These are initial guesses; we’ll revise after first real runs.

- `direction = right`
- `extension_px L = 512` (or 256 for speed)
- `overlap_px = 64` (enough seam context without huge payload)
- `immutable_px border = 0` by default (or 5 if tiling is required)
- `format = PNG` (lossless for invariant checks)
- `mode = RGB` unless alpha is needed

---

## 7. Failure taxonomy (how we stay sane)
We classify failures so UI and logs are consistent.

- `APITransientError` (timeout, 5xx)
- `APIPermanentError` (auth, invalid request)
- `SafetyRefusal` (model refusal)
- `DecodeError` (returned bytes not an image)
- `DimensionMismatch`
- `ImmutableViolation`
- `CompositeError` (unexpected geometry)
- `ArtifactWriteError`

Each failure writes:
- `failure.txt` human-readable
- `validation.json` machine-readable
- preserves raw API metadata when safe

---

## 8. Testing plan (v1, hermetic)
We do not need network for most tests.

### Geometry tests
- For each direction:
  - extraction region math is correct
  - composite places band in correct location
  - output dimensions are correct

### Invariant tests
- If immutable region is post-restored, verify exact identity after restore.
- Border identity test: hash the border pixels.

### Pipeline tests
- Mock API returns a known synthetic image; verify pipeline commits and artifacts are created.
- Mock API returns wrong dimensions; verify pipeline rejects and does not mutate state.

---

## 9. Build sequence (what we do first, second, third)
This is the recommended order because it keeps reality anchored.

### Phase A — Contracts & invariants (no API)
1. Define session root + artifact contracts.
2. Implement geometry: extract + composite.
3. Implement invariant checks and failure reports.
4. Build tiny CLI-free harness inside tests to run one “fake step” with mock outputs.

**Exit criterion:** a local step using a fake generated band can extend the canvas and pass validations.

### Phase B — API boundary (still no UI)
5. Implement `api/client` with a mockable interface and explicit errors.
6. Wire pipeline to call API (with mock in tests).

**Exit criterion:** pipeline can run with API mocked, and swapping in real client only changes config.

### Phase C — Minimal UI
7. Minimal browser UI that displays `canvas_latest.png` and sends prompts.
8. Websocket events for step status.

**Exit criterion:** you can type prompt → see step run → see canvas update.

### Phase D — Quality & features
9. Masking policies, seam strategies, style locks, budgets, caching, etc.

---

## 10. Design decisions we must make explicitly (before coding)
These are “choose one” knobs that affect everything downstream.

1. **Do we send full canvas or only context region to the model?**
   - Full canvas: easier to reason about, but heavy payload and may introduce accidental changes.
   - Context-only: cheaper and safer, but composite must be exact and seam-safe.

2. **Do we enforce immutable region via mask or post-restore?**
   - Mask: ideal if supported and reliable.
   - Post-restore: always works but can create hard seams if immutable overlaps with generated area.

3. **What is the seam strategy?**
   - Hard seam at boundary
   - Overlap + blend band (requires controlled blending)
   - Overlap + immutable band (requires model to match overlap)

4. **What is v1’s single most important invariant?**
   - Border identity? Seam invisibility? Reproducibility? Cost control?

We will pick these under human direction, one decision at a time.

---

## 11. Current state (as of this doc)
- Directory skeleton for `imkerutils/exquisite/` has been planned and created with `__init__.py` stubs (no code yet).
- Next work should start at **Phase A**: artifact contracts + geometry + invariants **without** API and without UI.

---

## 12. Operating protocol reminders (Prime Directive alignment)
- One action per turn.
- Multiple hypotheses allowed, but only one executed action.
- No reality claims without artifacts/logs/tests shown.
- No unnamed referents: every change names the exact file and target symbol.

---

**End.**
