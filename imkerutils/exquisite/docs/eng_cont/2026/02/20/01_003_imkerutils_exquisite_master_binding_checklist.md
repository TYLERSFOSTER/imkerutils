# Exquisite Subproject — Master Binding Checklist (Authoritative)
**Date:** 2026-02-20 (America/New_York)

Purpose: This is the **single authoritative list** of *every binding* required for v1.
- When a line is marked **[x]**, that binding is complete (bound in `engineer_notes.md`).
- When a line is **[ ]**, it is not yet bound and **must not drift** into “implied”.

Source of truth for “done”: `imkerutils_exquisite_engineer_notes.md`.

---

## A. Session Authority Bindings (Filesystem + Identity)

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

---

## B. Geometry + Direction Bindings

- [x] `EXTEND_DIRECTION` is a **session parameter** (user sets at session start)
- [x] `STEP_INPUT_BAND_CONTRACT = AXIS_DEPENDENT`
- [x] `BAND_THICKNESS_PARAM = band_thickness_px`
- [x] `OVERLAP_AUTHORITY = SESSION_PARAMETER`
- [ ] `OVERLAP_PX = <integer>`  ← not yet bound (value missing)
- [ ] `EXTENSION_LENGTH_PX = <integer>`  ← not yet bound (value missing)
- [ ] `BAND_THICKNESS_PX = <integer>`  ← not yet bound (value missing)
- [ ] `TARGET_CANVAS_SIZE_POLICY = <rule>`  ← not yet bound (see section D)

---

## C. Generation Authority Bindings (GPT)

- [x] `EXTENSION_SOURCE = GPT_IMAGE_API`
- [x] `GENERATION_SIZE_POLICY = FULL_TARGET_DIMENSIONS`

### C1. GPT Client Contract (Interface + Failure Semantics)
- [x] `GPT_CLIENT_INTERFACE = ACCEPTED` (signature + guarantees)
- [ ] `GPT_ENDPOINT_AUTHORITY = <official endpoint name>`
- [ ] `GPT_AUTH_AUTHORITY = <how API key is sourced>`
- [ ] `GPT_MODEL_AUTHORITY = <model identifier>`
- [ ] `GPT_REQUEST_SCHEMA_AUTHORITY = <exact request fields>`
- [ ] `GPT_RESPONSE_SCHEMA_AUTHORITY = <exact response fields>`
- [ ] `GPT_TIMEOUT_S = <integer>`
- [ ] `GPT_RETRY_POLICY = <none|fixed|backoff>`
- [ ] `GPT_ERROR_CLASSIFICATION = <list>`
- [ ] `GPT_RATE_LIMIT_BEHAVIOR = <policy>`
- [ ] `GPT_IMAGE_RETURN_FORMAT = <png|...>` (must be consistent with PNG_RGB pipeline)
- [ ] `GPT_IMAGE_DECODE_AUTHORITY = PIL.Image.open(BytesIO(...))` (explicitly bind decode path)
- [ ] `GPT_DIMENSION_MISMATCH_BEHAVIOR = reject_step` (explicitly bind)

---

## D. Step Target Dimensions Contract (Dimension Invariant Projection)

This binds **how expected dimensions evolve** per step (the “prediction” side).

- [ ] `TARGET_DIMENSION_CONTRACT = AXIS_DEPENDENT_APPEND`
  - If extend_direction ∈ {right,left}: `W_next = W + extension_length_px`, `H_next = H`
  - If extend_direction ∈ {up,down}: `H_next = H + extension_length_px`, `W_next = W`

- [ ] `ALLOWED_CANVAS_SIZES = <set>`
  - Example: `{1024x512, 1024x1024, 1024x1536, ...}` (must be enumerated for v1)

- [ ] `SESSION_START_CANVAS_SIZE = <WxH>` (must match initial canvas header)
- [ ] `STEP_TARGET_SIZE_RULE = FULL_TARGET_DIMENSIONS` (restate coupling to GPT output)
- [ ] `DIMENSION_INVARIANT_CHECK = (actual_from_IMAGE_HEADER == expected_from_SESSION_STATE)`

---

## E. Composite / Seam Authority Bindings

- [x] `EXTENSION_PLACEMENT = OVERLAP_AND_BLEND`
- [x] `BLEND_MODE ∈ {blend, replace}` (session/user option)
- [x] `OVERLAP_AND_BLEND_CONTRACT` (deterministic linear ramp, channel-wise RGB, round+clamp)

### E1. Composite Geometry Contracts
- [ ] `SEAM_ALIGNMENT_CONTRACT = <rule>`
  - Defines exact pixel coordinates of overlap region on both sides for each direction.

- [ ] `BLEND_RAMP_SPACE = <linear_rgb|gamma_corrected>` (must bind; current notes assume linear in uint8 math)

---

## F. Commit Gate + Atomicity Bindings

- [x] `COMMIT_GATE = DIMENSION_AND_ARTIFACT_ATOMIC`

### F1. Atomic Write Strategy (must be bound)
- [ ] `ATOMIC_WRITE_STRATEGY = <tempfile+rename|...>`
- [ ] `CANVAS_WRITE_ORDER = <order>`
- [ ] `STATE_WRITE_ORDER = <order>`
- [ ] `STEP_DIR_WRITE_ORDER = <order>`
- [ ] `PARTIAL_COMMIT_DETECTION = <rule>`

---

## G. Recovery / Reconstruction Bindings

- [x] `RECOVERY_MODE = RECONSTRUCT_FROM_ARTIFACT_ROOT`

### G1. Recovery Decision Rules (must be bound)
- [ ] `RECOVERY_PRECEDENCE = CANVAS > STATE > STEPS` (explicitly bind)
- [ ] `RECOVERY_MISMATCH_POLICY = RECOVERY_REQUIRED` (explicitly bind)
- [ ] `ROLLBACK_POLICY = <none|to_last_valid_step>`

---

## H. Prompt Authority Bindings

- [x] `PROMPT_AUTHORITY_CONTRACT = ACCEPTED`

### H1. Prompt Storage Schema (must be bound)
- [ ] `PROMPT_FILENAME = prompt.txt`
- [ ] `PROMPT_TEXT_AUTHORITY = prompt.txt` (explicitly bind)
- [ ] `PROMPT_HASH = <sha256|...>`
- [ ] `PROMPT_REDACTION_POLICY = <none|...>`

---

## I. Step Executor Bindings

- [x] `STEP_EXECUTOR_CONTRACT = ACCEPTED`

### I1. Step Metadata Schema (must be bound)
- [ ] `STEP_METADATA_FILENAME = step_metadata.json`
- [ ] `STEP_METADATA_FIELDS = <list>` (must enumerate)
- [ ] `HASH_ALGO = <sha256|...>`
- [ ] `CANVAS_HASH_POLICY = <when computed>`
- [ ] `INPUT_BAND_HASH_POLICY = <when computed>`
- [ ] `GENERATOR_OUTPUT_HASH_POLICY = <when computed>`

---

## J. UI Bindings (Deferred)

- [ ] UI contract (explicitly deferred by design)
  - `UI_BACKEND = <...>`
  - `UI_SESSION_DISCOVERY = <...>`
  - `UI_CANVAS_REFRESH_POLICY = <...>`
  - `UI_PROMPT_SUBMIT_POLICY = <...>`

---

# Status Summary

- Bound (done): items marked **[x]**
- Remaining (must bind): items marked **[ ]**

This checklist is authoritative. No new “requirements” may appear outside this file; if discovered, they must be added here first.
