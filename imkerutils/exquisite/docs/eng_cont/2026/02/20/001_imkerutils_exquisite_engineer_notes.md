# imkerutils.exquisite — Engineer Notes (Running Authority Log)
**Purpose:** This document is the authoritative running engineering log for session authority binding, invariant declarations, and geometry contracts.

This file is append-only. New authority bindings and invariant decisions must be added, never rewritten silently.

---

## Authority Binding — Primary Invariant

```text
PRIMARY_INVARIANT = DIMENSION_INVARIANT
```

Formal definition:

For every pipeline step k, extending canvas C_k by L pixels in direction D:

```
shape(C_{k+1}) = expected_shape(shape(C_k), D, L)
```

Expected shape rules:

If D = right or left:

```
height_next = height_current
width_next  = width_current + L
```

If D = up or down:

```
height_next = height_current + L
width_next  = width_current
```

Commit gate rule:

```
actual_shape == expected_shape
```

Otherwise:

```
STEP_STATUS = REJECTED_DIMENSION_INVARIANT_VIOLATION
CANVAS_AUTHORITY = PRESERVE_PREVIOUS
```

This invariant is the authoritative correctness gate for v1.

---

## Authority Binding — Session Parameter Contract

```text
SESSION_AUTHORITY_PARAMETERS =
{
  session_id: UUID,
  session_root: absolute_path,

  initial_canvas_path: absolute_path,
  canvas_height_px: int,
  canvas_width_px: int,

  extend_direction: {right,left,up,down},
  extension_length_px: int,

  PRIMARY_INVARIANT: DIMENSION_INVARIANT
}
```

Authority rules:

- These parameters define the authoritative session state.
- extend_direction is a session-level authority parameter.
- extend_direction determines geometry transform sign conventions.
- extension_length_px defines dimension delta per step.
- canvas dimensions must evolve strictly according to DIMENSION_INVARIANT.

These parameters must be recorded in session metadata.

---

## Authority Graph (Derived)

Authority chain:

```
SESSION_AUTHORITY_PARAMETERS
        ↓
geometry.dimensions
        ↓
pipeline.invariants
        ↓
pipeline.session commit gate
        ↓
state.session_state authoritative canvas
```

No pipeline step may bypass this chain.

---

## Failure Classes — Dimension Invariant Violations

Authoritative failure conditions:

- Model returns incorrect output size
- Composite introduces coordinate error
- Direction transform error
- Decode alters dimensions
- Crop/mask alters dimensions

Failure response:

```
reject_step()
preserve_canvas_authority()
record_failure_artifact()
```

---

## Append Protocol

All future authority bindings, invariant decisions, geometry conventions, and artifact contracts must be appended below this line.

---


## Authority Binding — Artifact Root (Session Artifact Authority)

```text
ARTIFACT_ROOT = /home/foster/imkerutils/imkerutils/_generated/exquisite
```

Contract:

- All session artifacts MUST be created under ARTIFACT_ROOT.
- No subsystem (UI, pipeline, tests, API client) may read/write canvas authority outside ARTIFACT_ROOT.
- Session root is:

```text
SESSION_ROOT = ARTIFACT_ROOT/<session_id>/
```

Authoritative canvas referent:

```text
CANVAS_AUTHORITY = SESSION_ROOT/canvas_latest.png
```

Violation class:

- ARTIFACT_AUTHORITY_SPLIT_BRAIN (multiple roots or competing canvas_latest referents)

---


## Authority Binding — Session ID Scheme

```text
SESSION_ID_SCHEME = uuid4
```

Contract:

- Each session_id MUST be generated using RFC 4122 UUID version 4.
- Session root directory is:

```text
SESSION_ROOT = ARTIFACT_ROOT/<session_id>/
```

Example:

```text
/home/foster/imkerutils/imkerutils/_generated/exquisite/550e8400-e29b-41d4-a716-446655440000/
```

Authority properties:

- Globally unique without coordination.
- No dependence on ambient time, locale, or host clock.
- Safe across concurrent UI, CLI, and test execution.

Violation class:

- SESSION_ID_COLLISION (should never occur under uuid4 generation)

---


## Authority Binding — Canvas Image Format

```text
CANVAS_FORMAT = PNG_RGB
```

Contract:

- Authoritative canvas encoding MUST be PNG.
- Authoritative color mode MUST be RGB (3 channels).
- Pixel structure is:

```text
[R, G, B]
```

- Alpha channel MUST NOT exist in authoritative canvas artifacts.
- All generated images MUST be converted to RGB before invariant validation and composite.

Authoritative canvas referent:

```text
CANVAS_AUTHORITY = SESSION_ROOT/canvas_latest.png
COLOR_MODE = RGB
CHANNEL_COUNT = 3
```

Violation classes:

- CANVAS_FORMAT_VIOLATION
- CANVAS_COLOR_MODE_VIOLATION
- CANVAS_CHANNEL_COUNT_VIOLATION

Failure response:

```
reject_step()
preserve_canvas_authority()
record_failure_artifact()
```

---


## Authority Binding — Pixel Coordinate Origin

```text
PIXEL_ORIGIN = TOP_LEFT
```

Contract:

- Pixel coordinate (0,0) is located at the top-left corner of the image.
- X coordinate increases to the right.
- Y coordinate increases downward.

Coordinate system:

```text
(0,0) --------> +X
  |
  |
  v
 +Y
```

Authoritative dimension interpretation:

```text
height_px = max_y + 1
width_px  = max_x + 1
```

Composite and geometry operations MUST use this coordinate system.

Violation classes:

- PIXEL_ORIGIN_MISMATCH
- COMPOSITE_COORDINATE_VIOLATION

Failure response:

```
reject_step()
preserve_canvas_authority()
record_failure_artifact()
```

---


## Authority Binding — Image Backend

```text
IMAGE_BACKEND = PILLOW
```

Contract:

- All authoritative image decode, encode, geometry, and composite operations MUST use Pillow.
- Authoritative image object type:

```text
PIL.Image.Image
```

- Authoritative color interpretation:

```text
mode = "RGB"
channel_order = R, G, B
```

- Authoritative dimension interpretation:

```text
image.size = (width_px, height_px)
origin = TOP_LEFT
```

Backend authority chain:

```text
PIL.Image.open()
    ↓
geometry operations
    ↓
composite operations
    ↓
PIL.Image.save()
```

Violation classes:

- IMAGE_BACKEND_SPLIT_BRAIN (multiple image libraries used)
- COLOR_CHANNEL_ORDER_VIOLATION
- IMAGE_OBJECT_AUTHORITY_VIOLATION

Failure response:

```
reject_step()
preserve_canvas_authority()
record_failure_artifact()
```

---


## Authority Binding — Dimension Authority

```text
DIMENSION_AUTHORITY = IMAGE_HEADER
```

Contract:

- Authoritative dimensions MUST be read from the image header via Pillow.
- Authoritative dimension referent:

```text
width_px, height_px = PIL.Image.open(CANVAS_AUTHORITY).size
```

- Session state dimensions are advisory expectations only.
- Dimension invariant validation MUST compare:

```text
expected_dimensions (from session parameters)
vs
actual_dimensions (from IMAGE_HEADER authority)
```

Authority chain:

```text
CANVAS_AUTHORITY file
    ↓
PIL.Image.open()
    ↓
IMAGE_HEADER
    ↓
DIMENSION_AUTHORITY
```

Violation classes:

- DIMENSION_AUTHORITY_SPLIT_BRAIN
- IMAGE_HEADER_DIMENSION_VIOLATION
- SESSION_STATE_DIMENSION_DRIFT

Failure response:

```
reject_step()
preserve_canvas_authority()
record_failure_artifact()
```

---


## Authority Binding — Canvas Filename Convention

```text
CANVAS_FILENAME = canvas_latest.png
```

Contract:

- The authoritative canvas referent MUST be:

```text
CANVAS_AUTHORITY = SESSION_ROOT/canvas_latest.png
```

- This file is the single source of truth for the current session canvas.
- All geometry, invariant validation, UI display, and composite operations MUST read from and write to this file.

Step history rule:

- Historical steps MUST NOT redefine canvas authority.
- Historical step artifacts MUST be stored under:

```text
SESSION_ROOT/steps/<step_index>/
```

but the authoritative current canvas remains:

```text
SESSION_ROOT/canvas_latest.png
```

Authority chain:

```text
SESSION_ROOT/
    canvas_latest.png      ← authoritative referent
    steps/
        0001/
        0002/
        ...
```

Violation classes:

- CANVAS_AUTHORITY_SPLIT_BRAIN
- MULTIPLE_CANVAS_AUTHORITY_REFERENTS
- STEP_AUTHORITY_OVERRIDE_VIOLATION

Failure response:

```
reject_step()
preserve_canvas_authority()
record_failure_artifact()
```

---


## Authority Binding — Step Index Origin

```text
STEP_INDEX_ORIGIN = 0
```

Contract:

- Step indices MUST begin at 0.
- Step 0 corresponds to the initial authoritative canvas state.
- Step index increases monotonically by exactly +1 per committed extension step.

Step index interpretation:

```text
step_index = 0 → initial canvas authority
step_index = 1 → first extension
step_index = 2 → second extension
...
```

Authoritative step artifact path:

```text
SESSION_ROOT/steps/<step_index>/
```

Example:

```text
SESSION_ROOT/
    canvas_latest.png
    steps/
        0/
        1/
        2/
```

Invariant relation:

```text
canvas_latest.png reflects step_index = max(existing steps)
```

Violation classes:

- STEP_INDEX_DRIFT
- STEP_INDEX_COLLISION
- STEP_INDEX_NON_MONOTONIC
- STEP_AUTHORITY_MISMATCH

Failure response:

```
reject_step()
preserve_canvas_authority()
record_failure_artifact()
```

---


## Authority Binding — Extension Generation Source

```text
EXTENSION_SOURCE = GPT_IMAGE_API
```

Contract:

- The authoritative generator of extension pixels MUST be the GPT Image API.
- No local generator, procedural generator, or alternate model may produce authoritative extension bands.

Authoritative generation chain:

```text
prompt
    +
authoritative edge region
    ↓
GPT Image API
    ↓
generated extension band (PNG_RGB)
    ↓
composite into CANVAS_AUTHORITY
```

Reproducibility requirement:

Each step MUST record:

```text
generator = GPT_IMAGE_API
prompt = <exact prompt string>
input_edge_region_hash = <hash>
output_band_hash = <hash>
```

Violation classes:

- GENERATOR_AUTHORITY_SPLIT_BRAIN
- NON_AUTHORITATIVE_GENERATOR_USAGE
- GENERATION_SOURCE_DRIFT

Failure response:

```
reject_step()
preserve_canvas_authority()
record_failure_artifact()
```

---


## Authority Binding — Extension Placement and Blend Contract

```text
EXTENSION_PLACEMENT = OVERLAP_AND_BLEND
```

Formal composite contract:

Given:

- Authoritative canvas C with shape (H, W)
- extend_direction D ∈ {right,left,up,down}
- extension_length_px = L
- overlap_px = O, where 0 < O ≤ L
- Generated patch P contains:

    P_overlap: overlap band of thickness O aligned with canvas seam
    P_new: extension band of thickness L aligned beyond seam

Composite authority rule:

1. Dimension invariant MUST hold:

```text
shape(C_next) = expected_shape(shape(C), D, L)
```

2. Non-overlap old region authority:

```text
C_next_old = C_old   (bit-identical preservation)
```

3. Non-overlap new region authority:

```text
C_next_new = P_new   (direct assignment)
```

4. Overlap region composite authority:

Blend mode parameter:

```text
BLEND_MODE ∈ {blend, replace}
```

If:

```text
BLEND_MODE = replace
```

Then:

```text
C_next_overlap = P_overlap
```

If:

```text
BLEND_MODE = blend
```

Then deterministic linear ramp blend MUST be applied:

For each overlap pixel index t ∈ [0, O−1]:

```text
alpha(t) = t / (O − 1)
```

Composite rule:

```text
C_next_overlap =
    round(
        (1 − alpha(t)) * C_overlap
        +
        alpha(t) * P_overlap
    )
```

Applied independently to each RGB channel.

5. Alpha channel MUST NOT exist (CANVAS_FORMAT = PNG_RGB).

Authority guarantees:

- Old non-overlap region: immutable authority preservation.
- New non-overlap region: generator authority.
- Overlap region: deterministic composite authority.

Violation classes:

- EXTENSION_PLACEMENT_AUTHORITY_VIOLATION
- OVERLAP_REGION_GEOMETRY_VIOLATION
- BLEND_DETERMINISM_VIOLATION
- NON_IMMUTABLE_REGION_MODIFICATION

Failure response:

```
reject_step()
preserve_canvas_authority()
record_failure_artifact()
```

---


## Authority Binding — Overlap Thickness Authority

```text
OVERLAP_AUTHORITY = SESSION_PARAMETER
```

Contract:

- overlap_px (O) MUST be defined as a session authority parameter.
- overlap_px MUST remain constant for the lifetime of the session unless explicitly changed via a session mutation event.

Authoritative definition:

```text
overlap_px ∈ ℕ
0 < overlap_px ≤ extension_length_px
```

Generator constraint:

- The GPT_IMAGE_API MUST produce extension patches that include exactly overlap_px of overlap region.

Composite authority chain:

```text
SESSION_AUTHORITY_PARAMETERS.overlap_px
    ↓
geometry.extract_edge_region()
    ↓
GPT_IMAGE_API generation contract
    ↓
composite.overlap_and_blend()
```

Violation classes:

- OVERLAP_AUTHORITY_DRIFT
- GENERATOR_OVERLAP_MISMATCH
- COMPOSITE_OVERLAP_INCONSISTENCY

Failure response:

```
reject_step()
preserve_canvas_authority()
record_failure_artifact()
```

---


## Authority Binding — Generation Size Policy

```text
GENERATION_SIZE_POLICY = FULL_TARGET_DIMENSIONS
```

Contract:

- The GPT_IMAGE_API MUST be invoked to generate the full target image size for the step.
- The generator output MUST have dimensions equal to the next-step expected dimensions (per DIMENSION_INVARIANT).

Example (right-extend):

Input edge band extracted from current canvas:

```text
H = 1024
M = 512
```

Target generator output:

```text
H = 1024
W = 1024
L = 512
```

Authority rule:

```text
generated_image.size == expected_next_canvas_size
```

Composite is then performed by extracting overlap/new regions from the full generated image and applying EXTENSION_PLACEMENT policy.

Violation classes:

- GENERATION_SIZE_POLICY_VIOLATION
- GENERATOR_DIMENSION_MISMATCH
- UNSUPPORTED_GENERATION_DIMENSIONS

Failure response:

```
reject_step()
preserve_canvas_authority()
record_failure_artifact()
```

---


## Authority Binding — Step Input Band Contract (Axis-Dependent)

```text
STEP_INPUT_BAND_CONTRACT = AXIS_DEPENDENT
```

Formal definition:

Let:

```text
H, W = authoritative canvas dimensions (from IMAGE_HEADER)
D = extend_direction ∈ {right,left,up,down}
B = band_thickness_px (session authority parameter)
```

Then authoritative input band dimensions are:

```text
if D ∈ {right,left}:

    band_height_px = H
    band_width_px  = B

if D ∈ {up,down}:

    band_height_px = B
    band_width_px  = W
```

Band extraction authority rule:

```text
right: extract columns [W − B, W − 1]
left:  extract columns [0, B − 1]

down:  extract rows [H − B, H − 1]
up:    extract rows [0, B − 1]
```

Band referent authority:

```text
STEP_INPUT_BAND = extract_from(CANVAS_AUTHORITY, D, B)
```

Generator conditioning contract:

```text
GPT_IMAGE_API MUST receive STEP_INPUT_BAND as conditioning input
```

Authority guarantees:

- Band extraction semantics are unambiguous.
- Axis orientation authority is preserved.
- Generator conditioning authority matches composite seam authority.

Violation classes:

- STEP_INPUT_BAND_AUTHORITY_VIOLATION
- BAND_EXTRACTION_AXIS_MISMATCH
- GENERATOR_CONDITIONING_DRIFT

Failure response:

```
reject_step()
preserve_canvas_authority()
record_failure_artifact()
```

---


## Authority Binding — Band Thickness Parameter Name

```text
BAND_THICKNESS_PARAM = band_thickness_px
```

Contract:

- The authoritative session parameter controlling input band extraction thickness MUST be named:

```text
band_thickness_px
```

Authoritative usage:

```text
STEP_INPUT_BAND = extract_from(CANVAS_AUTHORITY, extend_direction, band_thickness_px)
```

This parameter defines:

- conditioning region thickness for GPT_IMAGE_API
- overlap and blend seam geometry
- composite seam authority alignment

Violation classes:

- BAND_THICKNESS_PARAM_NAME_MISMATCH
- BAND_THICKNESS_AUTHORITY_DRIFT

---


## Authority Binding — Session State File Contract

```text
SESSION_STATE_FILENAME = session_state.json
```

Contract:

- The authoritative session metadata referent MUST be:

```text
SESSION_STATE_AUTHORITY = SESSION_ROOT/session_state.json
```

This file MUST contain the authoritative session state necessary for reconstruction and invariant validation.

Authoritative fields:

```text
session_id: UUID
canvas_width_px_expected: int
canvas_height_px_expected: int
extend_direction: {right,left,up,down}
extension_length_px: int
band_thickness_px: int
overlap_px: int
step_index_current: int
generator: GPT_IMAGE_API
generation_size_policy: FULL_TARGET_DIMENSIONS
canvas_filename: canvas_latest.png
image_backend: PILLOW
pixel_origin: TOP_LEFT
canvas_format: PNG_RGB
dimension_authority: IMAGE_HEADER
```

Authority chain:

```text
SESSION_STATE_AUTHORITY
    ↓
expected geometry and invariant expectations
    ↓
validated against IMAGE_HEADER (DIMENSION_AUTHORITY)
    ↓
composite commit gate
```

Violation classes:

- SESSION_STATE_AUTHORITY_MISSING
- SESSION_STATE_DRIFT
- SESSION_STATE_CANVAS_MISMATCH
- SESSION_RECONSTRUCTION_FAILURE

Failure response:

```
halt_session()
preserve_canvas_authority()
require_state_reconstruction()
```

---


## Authority Binding — Step Directory Naming Convention

```text
STEP_DIR_FORMAT = steps/%04d
```

Contract:

- Authoritative step artifact directory MUST follow zero-padded 4-digit format.

Authoritative directory referent:

```text
STEP_DIR(step_index) =
    SESSION_ROOT/steps/%04d/ % step_index
```

Examples:

```text
SESSION_ROOT/steps/0000/
SESSION_ROOT/steps/0001/
SESSION_ROOT/steps/0002/
```

Authority guarantees:

- Lexicographic ordering equals numeric ordering.
- Step reconstruction is deterministic.
- Step authority uniqueness is preserved.

Violation classes:

- STEP_DIR_FORMAT_VIOLATION
- STEP_DIR_AUTHORITY_SPLIT_BRAIN
- STEP_ORDER_RECONSTRUCTION_FAILURE

Failure response:

```
halt_session()
require_authority_reconstruction()
```

---


## Authority Binding — Commit Gate Contract

```text
COMMIT_GATE = DIMENSION_AND_ARTIFACT_ATOMIC
```

Formal definition:

A step becomes authoritative if and only if all required authority artifacts are successfully written and consistent.

Authoritative commit conditions:

```text
1. Generator returns image
2. Generated image dimensions == expected dimensions (DIMENSION_INVARIANT)
3. Composite completes successfully
4. CANVAS_AUTHORITY (canvas_latest.png) is written successfully
5. SESSION_STATE_AUTHORITY (session_state.json) is written successfully
6. STEP_DIR(step_index) exists and contains step artifacts
```

Atomicity rule:

```text
Authority transition MUST be atomic.

Either:

    all authority artifacts advance to step N

or:

    authority remains at step N−1
```

Forbidden partial state example:

```text
canvas_latest.png reflects step N
session_state.json reflects step N−1
steps directory reflects step N−1
```

Authority chain:

```text
generator output
    ↓
composite validation
    ↓
commit gate validation
    ↓
atomic authority transition
```

Violation classes:

- PARTIAL_COMMIT_AUTHORITY_SPLIT_BRAIN
- SESSION_STATE_CANVAS_MISMATCH
- STEP_DIR_CANVAS_MISMATCH

Failure response:

```
reject_step()
preserve_authoritative_state()
require_commit_recovery()
```

---


## Authority Binding — Recovery Mode Contract

```text
RECOVERY_MODE = RECONSTRUCT_FROM_ARTIFACT_ROOT
```

Contract:

On session open or restart, authoritative state MUST be reconstructed from ARTIFACT_ROOT.

Authoritative recovery chain:

```text
SESSION_ROOT/
    canvas_latest.png        ← primary authority referent
    session_state.json       ← metadata authority (validated against canvas)
    steps/                   ← advisory reconstruction history
```

Recovery procedure:

1. Load CANVAS_AUTHORITY:

```text
canvas_width_px, canvas_height_px = IMAGE_HEADER authority
```

2. Load SESSION_STATE_AUTHORITY:

```text
validate expected dimensions against IMAGE_HEADER
```

3. Determine authoritative step index:

```text
step_index_current = max valid STEP_DIR consistent with canvas + state
```

4. If any inconsistency exists:

```text
SESSION_STATUS = RECOVERY_REQUIRED
GENERATION_FORBIDDEN = TRUE
```

5. Session must be repaired or rolled back before generation resumes.

Authority precedence order:

```text
CANVAS_AUTHORITY
    >
SESSION_STATE_AUTHORITY
    >
STEP_DIR history
```

Violation classes:

- SESSION_RECOVERY_FAILURE
- CANVAS_STATE_METADATA_MISMATCH
- STEP_HISTORY_INCONSISTENCY

Failure response:

```
enter_recovery_mode()
block_generation()
require_authority_reconstruction()
```

---


## Authority Binding — GPT Client Interface Contract

```text
GPT_CLIENT_INTERFACE = ACCEPTED
```

Authoritative file:

```text
exquisite/gpt_client.py
```

Authoritative function signature:

```python
generate_extension(
    *,
    step_input_band: PIL.Image,
    extend_direction: Literal["right","left","up","down"],
    target_canvas_width_px: int,
    target_canvas_height_px: int,
    prompt: str,
    session_id: UUID,
    step_index: int,
) -> PIL.Image
```

Authoritative guarantees:

```text
1. Return value MUST be PIL.Image (IMAGE_BACKEND authority)
2. Return image dimensions MUST equal:

   (target_canvas_width_px, target_canvas_height_px)

3. Returned image MUST be full target canvas dimensions
   (GENERATION_SIZE_POLICY = FULL_TARGET_DIMENSIONS)

4. No implicit resizing allowed after receipt
5. No implicit cropping allowed after receipt
6. No implicit color conversion allowed after receipt
```

Authoritative persistence requirements:

```text
steps/%04d/
    generator_input_band.png
    generator_output_full.png
    prompt.txt
```

Failure behavior:

```text
If generation fails → NO commit allowed
If returned dimensions mismatch → invariant violation → reject step
```

Violation classes:

- GENERATOR_DIMENSION_VIOLATION
- GENERATOR_AUTHORITY_VIOLATION
- GENERATOR_OUTPUT_MISSING

---


## Authority Binding — Prompt Authority Contract

```text
PROMPT_AUTHORITY_CONTRACT = ACCEPTED
```

Authoritative file:

```text
exquisite/prompt.py
```

Authoritative function signature:

```python
build_prompt(
    *,
    user_prompt: str,
    extend_direction: Literal["right","left","up","down"],
    band_thickness_px: int,
    extension_length_px: int,
    step_index: int,
) -> str
```

Authoritative persistence requirement:

```text
steps/%04d/
    prompt.txt   ← exact string sent to GPT_IMAGE_API
```

Authority rule:

```text
prompt.txt is the single authoritative referent of generator intent.
No regeneration of prompt is allowed from memory or recomputation.
```

Violation classes:

- PROMPT_AUTHORITY_DRIFT
- PROMPT_REGENERATION_FORBIDDEN
- PROMPT_MISSING

---


## Authority Binding — Step Executor Contract

```text
STEP_EXECUTOR_CONTRACT = ACCEPTED
```

Authoritative file:

```text
exquisite/step.py
```

Authoritative interface:

```python
execute_step(
    *,
    session_id: UUID,
    step_index: int,
    user_prompt: str,
    blend_mode: Literal["blend", "replace"],
) -> StepResult
```

Authoritative behavior sequence:

```text
1. Load CANVAS_AUTHORITY (canvas_latest.png) via IMAGE_HEADER authority
2. Extract STEP_INPUT_BAND using STEP_INPUT_BAND_CONTRACT (axis-dependent)
3. Build authoritative prompt via PROMPT_AUTHORITY_CONTRACT
4. Persist prompt.txt in STEP_DIR
5. Call GPT_CLIENT_INTERFACE to generate full target extension
6. Persist generator_input_band.png and generator_output_full.png
7. Validate DIMENSION_INVARIANT against IMAGE_HEADER authority
8. Composite extension into canvas using EXTENSION_PLACEMENT and blend_mode
9. Invoke COMMIT_GATE (DIMENSION_AND_ARTIFACT_ATOMIC)
10. Update SESSION_STATE_AUTHORITY
11. Return StepResult reflecting authoritative outcome
```

Authoritative StepResult contract:

```python
class StepResult:
    status: Literal["committed", "rejected", "recovery_required"]
    step_index: int
    canvas_path: Path
```

Failure behavior:

```text
If invariant violation → reject step → preserve previous authority
If commit gate failure → reject step → preserve previous authority
If recovery required → block generation until recovery resolves
```

Violation classes:

- STEP_EXECUTION_AUTHORITY_VIOLATION
- STEP_COMMIT_FAILURE
- STEP_INVARIANT_FAILURE

---


## Authority Binding — Step Result Authority Contract

```text
STEP_RESULT_AUTHORITY = STEP_DIR_ARTIFACTS
```

Authoritative referent:

```text
SESSION_ROOT/steps/%04d/
```

This directory is the single authoritative record of each step.

Authoritative contents:

```text
prompt.txt
generator_input_band.png
generator_output_full.png
canvas_after_commit.png (optional snapshot)
step_metadata.json (optional)
```

Authority rule:

```text
STEP RESULT AUTHORITY exists exclusively in filesystem artifacts.

Memory, logs, UI state, or transient runtime structures are NOT authoritative.
```

Reconstruction rule:

```text
Authoritative step index = max valid STEP_DIR consistent with:

    canvas_latest.png
    session_state.json
```

Violation classes:

- STEP_RESULT_AUTHORITY_DRIFT
- STEP_DIR_MISSING
- STEP_RESULT_RECONSTRUCTION_FAILURE

---

