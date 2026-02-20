# IMPLEMENTATION_READINESS_CHECKLIST (authoritative) — STATUS

Legend:
  [x] Bound as contract in engineer_notes (design/authority decided)
  [ ] Not yet bound / not yet created

Before writing pipeline code, the following modules and contracts MUST exist:

---

## 1. SESSION CREATION AUTHORITY
**File:** `exquisite/session.py`

**Required capability:**
```
create_session(initial_canvas_path, extend_direction, extension_length_px, band_thickness_px, overlap_px)
```

**Must produce:**
```
SESSION_ROOT/
    canvas_latest.png
    session_state.json
    steps/0000/
```

**Status:** [x]  
Contracts bound:
- ARTIFACT_ROOT
- SESSION_ID_SCHEME = uuid4
- CANVAS_FILENAME = canvas_latest.png
- SESSION_STATE_FILENAME = session_state.json
- STEP_DIR_FORMAT = %04d
- STEP_INDEX_ORIGIN = 0

---

## 2. CANVAS AUTHORITY LOADER
**File:** `exquisite/canvas.py`

**Required capability:**
```
load_canvas() → PIL.Image
```

**Authority rule:**
```
Dimensions must be read from IMAGE_HEADER only.
```

**Status:** [x]  
Contracts bound:
- IMAGE_BACKEND = PILLOW
- DIMENSION_AUTHORITY = IMAGE_HEADER
- CANVAS_FORMAT = PNG_RGB
- PIXEL_ORIGIN = TOP_LEFT

---

## 3. STEP INPUT BAND EXTRACTOR
**File:** `exquisite/band.py`

**Required capability:**
```
extract_band(canvas, extend_direction, band_thickness_px)
```

**Status:** [x]  
Contracts bound:
- STEP_INPUT_BAND_CONTRACT = AXIS_DEPENDENT
- BAND_THICKNESS_PARAM = band_thickness_px

---

## 4. GENERATION REQUEST BUILDER
**File:** `exquisite/generator.py`

**Required capability:**
Construct GPT_IMAGE_API request with:

- STEP_INPUT_BAND
- prompt
- GENERATION_SIZE_POLICY = FULL_TARGET_DIMENSIONS

**Status:** [x]  
Contracts bound:
- EXTENSION_SOURCE = GPT_IMAGE_API
- GENERATION_SIZE_POLICY = FULL_TARGET_DIMENSIONS

---

## 5. GENERATOR RESPONSE VALIDATOR
**File:** `exquisite/generator.py`

**Required capability:**
Verify returned image dimensions match expected authoritative dimensions.

**Status:** [x]  
Contracts bound:
- PRIMARY_INVARIANT = DIMENSION_INVARIANT
- DIMENSION_AUTHORITY = IMAGE_HEADER

---

## 6. COMPOSITE ENGINE
**File:** `exquisite/composite.py`

**Required capability:**
Composite extension into canvas using:

- EXTENSION_PLACEMENT
- BLEND_MODE
- OVERLAP_AUTHORITY

**Status:** [x]  
Contracts bound:
- EXTENSION_PLACEMENT = OVERLAP_AND_BLEND
- OVERLAP_AUTHORITY = SESSION_PARAMETER

---

## 7. COMMIT GATE IMPLEMENTATION
**File:** `exquisite/commit.py`

**Required capability:**
Atomic update of:

```
canvas_latest.png
session_state.json
steps/%04d/
```

**Status:** [x]  
Contracts bound:
- COMMIT_GATE = DIMENSION_AND_ARTIFACT_ATOMIC
- STEP_RESULT_AUTHORITY = STEP_DIR_ARTIFACTS

---

## 8. SESSION STATE AUTHORITY WRITER
**File:** `exquisite/session_state.py`

**Required capability:**
Deterministically update:

```
session_state.json
```

**Status:** [x]  
Contracts bound:
- SESSION_STATE_FILENAME = session_state.json
- AUTHORITATIVE_SESSION_STATE_FIELDS defined

---

## 9. SESSION RECOVERY ENGINE
**File:** `exquisite/recovery.py`

**Required capability:**
Reconstruct session solely from artifact root.

**Status:** [x]  
Contracts bound:
- RECOVERY_MODE = RECONSTRUCT_FROM_ARTIFACT_ROOT
- STEP_RESULT_AUTHORITY = STEP_DIR_ARTIFACTS

---

## 10. INVARIANT VALIDATION ENGINE
**File:** `exquisite/invariants.py`

**Required capability:**
Enforce:

- DIMENSION_INVARIANT
- artifact authority invariants
- commit atomicity invariants

**Status:** [x]  
Contracts bound:
- PRIMARY_INVARIANT = DIMENSION_INVARIANT
- DIMENSION_AUTHORITY = IMAGE_HEADER
- COMMIT_GATE atomic invariant
- ARTIFACT_ROOT authority invariant

---

## 11. GPT IMAGE API AUTHORITY CLIENT
**File:** `exquisite/gpt_client.py`

**Required capability:**
```
call GPT_IMAGE_API deterministically
return PIL.Image authority object
```

**Status:** [ ]  
Not yet bound:

- Exact API interface schema
- Authentication contract
- Request construction authority
- Response validation contract
- Error authority semantics

---

## 12. PROMPT AUTHORITY CONTRACT
**File:** `exquisite/prompt.py`

**Required capability:**
```
construct authoritative prompt string
persist prompt in steps/%04d/
```

**Status:** [x]  
Contracts bound:

- PROMPT_AUTHORITY_CONTRACT = ACCEPTED
- Prompt must be persisted in STEP_RESULT_AUTHORITY directory
- Prompt text is authoritative reconstruction source

---

## 13. SESSION STEP EXECUTOR
**File:** `exquisite/step.py`

**Required capability:**
Execute authoritative step sequence:

```
extract band
generate extension
validate invariant
composite
commit atomically
```

**Status:** [x]  
Contracts bound:

- STEP_EXECUTOR_CONTRACT = ACCEPTED
- COMMIT_GATE authority enforced
- STEP_RESULT_AUTHORITY enforced

---

## 14. UI CONTRACT (later phase)
**File:** `exquisite/ui/`

**Required capability:**
```
display CANVAS_AUTHORITY
submit prompt
invoke STEP_EXECUTOR
```

**Status:** [ ]  
Explicitly deferred.

---

# GLOBAL READINESS SUMMARY

Fully bound modules/contracts: **11 / 14**  
Remaining blockers:

- GPT_IMAGE_API_AUTHORITY_CLIENT
- UI_CONTRACT (deferred by design)

System is now ready to begin pipeline implementation once GPT client authority is bound.

END CHECKLIST
