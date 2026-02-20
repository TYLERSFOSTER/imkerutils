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

