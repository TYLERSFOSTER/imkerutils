# imkerutils.exquisite — Phase A: Start Building (No UI, No Real GPT Yet)
**Date:** 2026-02-20 (America/New_York)  
**Status:** *Authorized build start for Phase A (hermetic geometry + artifacts + invariants, with mocked generator)*

This document defines the **exact files** and **function signatures** to implement first, in order, to get a working
“band → square → glue” pipeline **without any network calls**.

It assumes the elemental v1 mode:

- `TILE_PX = 1024` (square side)
- `EXTENSION_PX = 512`
- **Axis+direction mode:** `x_axis_left_to_right`
- Each step:
  1) crop **rightmost** `1024×512` band from canvas  
  2) “generate” a `1024×1024` tile whose **left half equals the band**  
  3) take the **right half** (`1024×512`) and append to the canvas width

------------------------------------------------------------------------

## 0. Repository / artifact constants (already bound)
- `ARTIFACT_ROOT = /home/foster/imkerutils/imkerutils/_generated/exquisite`
- `SESSION_ID_SCHEME = uuid4`
- `CANVAS_FILENAME = canvas_latest.png`
- `SESSION_STATE_FILENAME = session_state.json`
- `STEP_DIR_FORMAT = steps/%04d`
- `IMAGE_BACKEND = PILLOW`
- `CANVAS_FORMAT = PNG_RGB`
- `DIMENSION_AUTHORITY = IMAGE_HEADER`
- `PIXEL_ORIGIN = TOP_LEFT`
- `PRIMARY_INVARIANT = DIMENSION_INVARIANT`

------------------------------------------------------------------------

## 1. Minimal module surface (Phase A)

### 1.1 `imkerutils/exquisite/session.py`
**Purpose:** create a new session directory and seed `canvas_latest.png` + `session_state.json` + step 0000.

```python
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import UUID

ExtendMode = Literal["x_axis_left_to_right"]  # Phase A only

@dataclass(frozen=True)
class SessionPaths:
    session_root: Path
    canvas_path: Path          # canvas_latest.png
    state_path: Path           # session_state.json
    steps_root: Path           # session_root/steps/

def create_session(
    *,
    initial_canvas_path: Path,
    extend_mode: ExtendMode,
    tile_px: int = 1024,
    extension_px: int = 512,
    band_thickness_px: int = 512,
) -> SessionPaths:
    ...
```

**Phase A rules:**
- Validate `initial_canvas_path` decodes to `RGB` and is exactly `1024×1024` (reject otherwise).
- Copy/convert and write authoritative `canvas_latest.png` into session root.
- Initialize `session_state.json` with expected dims and step index 0.
- Create `steps/0000/` and persist `input_canvas.png` (snapshot) + `step_metadata.json` (minimal).

---

### 1.2 `imkerutils/exquisite/canvas.py`
**Purpose:** load the authoritative canvas and enforce mode/format invariants.

```python
from pathlib import Path
from PIL import Image

def load_canvas(*, canvas_path: Path) -> Image.Image:
    """Load via Pillow. Return RGB. Dimensions from IMAGE_HEADER are authoritative."""
    ...
```

---

### 1.3 `imkerutils/exquisite/band.py`
**Purpose:** crop the conditioning band for the current step.

```python
from typing import Literal
from PIL import Image

ExtendMode = Literal["x_axis_left_to_right"]

def extract_input_band(
    *,
    canvas: Image.Image,
    extend_mode: ExtendMode,
    band_thickness_px: int,
) -> Image.Image:
    """Phase A only: returns rightmost (H×band_thickness_px) band."""
    ...
```

**Phase A cropping rule (`x_axis_left_to_right`):**
- If `canvas.size == (W, H)`, band bbox is `(W - band_thickness_px, 0, W, H)`.

---

### 1.4 `imkerutils/exquisite/mock_generator.py`
**Purpose:** deterministic “fake GPT” that returns a full `1024×1024` tile.

```python
from dataclasses import dataclass
from typing import Literal
from PIL import Image

ExtendMode = Literal["x_axis_left_to_right"]

@dataclass(frozen=True)
class MockGenConfig:
    tile_px: int = 1024
    extension_px: int = 512

def generate_tile_mock(
    *,
    input_band: Image.Image,          # 1024×512
    extend_mode: ExtendMode,
    user_prompt: str,
    cfg: MockGenConfig = MockGenConfig(),
) -> Image.Image:
    """Return a 1024×1024 RGB tile with left half == input_band, right half synthetic."""
    ...
```

**Determinism rule:**
- Synthetic right half must be a deterministic function of:
  - `sha256(input_band_bytes + user_prompt.encode())`
- (So test outputs are stable.)

---

### 1.5 `imkerutils/exquisite/composite.py`
**Purpose:** append the generated new pixels to the master canvas.

```python
from typing import Literal
from PIL import Image

ExtendMode = Literal["x_axis_left_to_right"]

def append_generated_region(
    *,
    canvas: Image.Image,
    generated_tile: Image.Image,  # 1024×1024
    extend_mode: ExtendMode,
    extension_px: int,
) -> Image.Image:
    """Phase A only: take right half of tile and append to canvas width."""
    ...
```

**Phase A glue rule (`x_axis_left_to_right`):**
- `new_pixels = generated_tile.crop((tile_px - extension_px, 0, tile_px, tile_px))`
- `canvas_next = new Image (W + extension_px, H)` with `canvas` pasted at x=0 and `new_pixels` pasted at x=W.

---

### 1.6 `imkerutils/exquisite/invariants.py`
**Purpose:** validate the primary invariant + minimal correctness gates.

```python
from dataclasses import dataclass
from PIL import Image

@dataclass(frozen=True)
class DimensionExpectation:
    expected_w: int
    expected_h: int

def expected_next_dimensions(
    *,
    current_w: int,
    current_h: int,
    extension_px: int,
    extend_mode: str,
) -> DimensionExpectation:
    ...

def check_dimension_invariant(
    *,
    image: Image.Image,
    expected: DimensionExpectation,
) -> None:
    """Raise DimensionMismatch on failure."""
    ...
```

**Phase A checks:**
- `generated_tile` must be exactly `(1024, 1024)`
- `canvas_next` must be exactly `(current_w + 512, 1024)`

---

### 1.7 `imkerutils/exquisite/atomic_write.py`
**Purpose:** tempfile + `os.replace` atomic writes.

```python
from pathlib import Path

def atomic_write_bytes(*, path: Path, data: bytes) -> None:
    ...

def atomic_write_image_png_rgb(*, path: Path, pil_img) -> None:
    ...
```

---

### 1.8 `imkerutils/exquisite/state.py`
**Purpose:** canonical session state representation + JSON (minimal in Phase A).

```python
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

ExtendMode = Literal["x_axis_left_to_right"]

@dataclass
class SessionState:
    session_id: str
    extend_mode: ExtendMode
    tile_px: int
    extension_px: int
    band_thickness_px: int
    step_index_current: int
    canvas_width_px_expected: int
    canvas_height_px_expected: int
```

---

### 1.9 `imkerutils/exquisite/step.py`
**Purpose:** the step transaction (with mock generator).

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

@dataclass(frozen=True)
class StepResult:
    status: Literal["committed", "rejected"]
    step_index: int
    canvas_path: Path

def execute_step_mock(
    *,
    session_root: Path,
    user_prompt: str,
) -> StepResult:
    """Loads state+canvas, extracts band, generates mock tile, validates, composites, commits."""
    ...
```

**Persistence (Phase A):**
Write to `steps/%04d/`:
- `input_band.png`
- `generator_output_full.png`
- `prompt.txt`
- `output_canvas.png` (snapshot)
- `step_metadata.json`
- `committed.ok` (commit marker)

Then atomically update:
- `canvas_latest.png`
- `session_state.json`

------------------------------------------------------------------------

## 2. Exact build order (Phase A)
1. `atomic_write.py` (atomic primitives)
2. `canvas.py` (RGB loader)
3. `session.py` (create session)
4. `band.py` (crop band)
5. `mock_generator.py` (deterministic tile)
6. `composite.py` (append glue)
7. `invariants.py` (dimension checks)
8. `state.py` (session_state JSON)
9. `step.py` (execute_step_mock orchestration)
10. `tests/` (below)

------------------------------------------------------------------------

## 3. Tests (Phase A)
Create `imkerutils/exquisite/tests/`:

### 3.1 `test_phaseA_two_steps.py`
- Make a synthetic `1024×1024` seed canvas (RGB).
- `create_session(...)`
- Run `execute_step_mock(...)` twice.
- Assert:
  - After 1 step: canvas is `1024×1536`
  - After 2 steps: canvas is `1024×2048`
  - `steps/0001/committed.ok` exists and similarly for 0002
  - `canvas_latest.png` exists and matches expected dimensions via Pillow header

------------------------------------------------------------------------

## 4. Exit criterion for Phase A
**We are allowed to move to real GPT API only when:**
- Phase A tests pass locally and deterministically.
- Artifacts are created exactly under `ARTIFACT_ROOT/<session_id>/...`
- Dimension invariant never fails in the mock path.
- Commit is atomic (no partial state) as indicated by `committed.ok` + `os.replace` usage.

END.
