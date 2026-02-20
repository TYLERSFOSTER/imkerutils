# Exquisite Subproject --- Master Binding Checklist Closure (Authoritative)

**Date:** 2026-02-20 (America/New_York)

This document closes all remaining `[ ]` bindings for v1 and provides
the exact authority text that must be appended to:

    imkerutils/exquisite/docs/eng_cont/2026/02/20/imkerutils_exquisite_engineer_notes.md

This document is itself authoritative once appended.

------------------------------------------------------------------------

# Authority Binding --- Target Canvas Size Policy

``` text
TARGET_CANVAS_SIZE_POLICY = OPENAI_IMAGE_SIZE_ENUM
```

Contract:

-   Target canvas sizes for v1 MUST be exactly the OpenAI-supported size
    enum for GPT image models.
-   Therefore:

``` text
ALLOWED_CANVAS_SIZES = {
  "1024x1024",
  "1536x1024",
  "1024x1536"
}
```

Implication:

-   SESSION_START_CANVAS_SIZE MUST be "1024x1024".
-   Any extension MUST land exactly on one of the allowed sizes.

Violation:

``` text
UNSUPPORTED_TARGET_CANVAS_SIZE → reject_step + preserve_canvas_authority
```

------------------------------------------------------------------------

# Authority Binding --- Step Target Size Rule

``` text
STEP_TARGET_SIZE_RULE = FULL_TARGET_DIMENSIONS
```

Contract:

``` text
requested GPT size == expected next canvas size
returned image size == expected next canvas size
```

No resizing or cropping permitted.

------------------------------------------------------------------------

# Authority Binding --- Dimension Invariant Check

``` text
DIMENSION_INVARIANT_CHECK =
(actual_width_px, actual_height_px) ==
(expected_width_px, expected_height_px)
```

Dimensions MUST be read from Pillow IMAGE_HEADER authority.

Violation:

``` text
REJECTED_DIMENSION_INVARIANT_VIOLATION
```

------------------------------------------------------------------------

# Authority Binding --- GPT Endpoint Authority

``` text
GPT_ENDPOINT_AUTHORITY = POST https://api.openai.com/v1/images/edits
```

This endpoint MUST be used for extension generation.

------------------------------------------------------------------------

# Authority Binding --- GPT Auth Authority

``` text
GPT_AUTH_AUTHORITY = ENV:OPENAI_API_KEY
```

Authorization source:

``` text
Authorization: Bearer $OPENAI_API_KEY
```

------------------------------------------------------------------------

# Authority Binding --- GPT Model Authority

``` text
GPT_MODEL_AUTHORITY = gpt-image-1.5
```

------------------------------------------------------------------------

# Authority Binding --- GPT Request Schema Authority

``` text
GPT_REQUEST_SCHEMA_AUTHORITY = images.edits multipart/form-data
```

Authoritative fields:

``` text
model
image[]
prompt
size
output_format = png
n = 1
optional: mask, quality, moderation, stream
```

------------------------------------------------------------------------

# Authority Binding --- GPT Response Schema Authority

``` text
GPT_RESPONSE_SCHEMA_AUTHORITY = ImagesResponse
```

Image decode referent:

``` text
data[0].b64_json
```

------------------------------------------------------------------------

# Authority Binding --- GPT Timeout and Retry

``` text
GPT_TIMEOUT_S = 120
GPT_RETRY_POLICY = exponential_backoff
GPT_RATE_LIMIT_BEHAVIOR = exponential_backoff_then_fail
```

Retry allowed only for transient errors.

------------------------------------------------------------------------

# Authority Binding --- GPT Error Classification

``` text
GPT_ERROR_CLASSIFICATION = {
  APITransientError,
  APIPermanentError,
  SafetyRefusal,
  DecodeError,
  DimensionMismatch
}
```

------------------------------------------------------------------------

# Authority Binding --- GPT Image Decode Authority

``` text
GPT_IMAGE_RETURN_FORMAT = png
GPT_IMAGE_DECODE_AUTHORITY = PIL.Image.open(BytesIO(decoded_bytes))
```

Conversion authority:

``` text
img.convert("RGB")
```

------------------------------------------------------------------------

# Authority Binding --- GPT Dimension Mismatch Behavior

``` text
GPT_DIMENSION_MISMATCH_BEHAVIOR = reject_step
```

------------------------------------------------------------------------

# Authority Binding --- Seam Alignment Contract

``` text
SEAM_ALIGNMENT_CONTRACT = AXIS_DEPENDENT_OFFSETS
```

Coordinates defined explicitly per axis direction.

Violation:

``` text
SEAM_ALIGNMENT_VIOLATION
```

------------------------------------------------------------------------

# Authority Binding --- Blend Ramp Space

``` text
BLEND_RAMP_SPACE = linear_rgb_uint8
```

Deterministic integer math blending.

------------------------------------------------------------------------

# Authority Binding --- Atomic Write Strategy

``` text
ATOMIC_WRITE_STRATEGY = tempfile_plus_os_replace
```

Write order authority:

``` text
STEP_DIR_WRITE_ORDER   = write artifacts first
CANVAS_WRITE_ORDER     = tmp → os.replace → canvas_latest.png
STATE_WRITE_ORDER      = tmp → os.replace → session_state.json
COMMIT_MARKER_FILENAME = committed.ok
```

Partial commit detection:

``` text
PARTIAL_COMMIT_DETECTION =
if missing committed.ok → RECOVERY_REQUIRED
```

------------------------------------------------------------------------

# Authority Binding --- Recovery Decision Rules

``` text
RECOVERY_PRECEDENCE = CANVAS > STATE > STEPS
RECOVERY_MISMATCH_POLICY = RECOVERY_REQUIRED
ROLLBACK_POLICY = to_last_valid_committed_step
```

------------------------------------------------------------------------

# Authority Binding --- Prompt Hash Authority

``` text
PROMPT_HASH = sha256(prompt.txt)
PROMPT_REDACTION_POLICY = none
```

------------------------------------------------------------------------

# Authority Binding --- Step Metadata Authority

``` text
HASH_ALGO = sha256
```

Authoritative metadata fields:

``` text
session_id
step_index
timestamp_utc
extend_direction
extension_length_px
overlap_px
band_thickness_px
blend_mode
expected_width_px
expected_height_px
model
endpoint
timeout_s
retry_policy
prompt_sha256
input_band_sha256
generator_output_sha256
canvas_before_sha256
canvas_after_sha256
output_format
size
usage
provider_request_id
status
```

Hash timing authority:

``` text
CANVAS_HASH_POLICY           = before + after commit
INPUT_BAND_HASH_POLICY       = immediately after extraction
GENERATOR_OUTPUT_HASH_POLICY = immediately after decode
```

------------------------------------------------------------------------

# Final Status

All bindings required for v1 are now AUTHORITATIVELY DEFINED.

Next authorized phase:

``` text
BEGIN PIPELINE IMPLEMENTATION
```

------------------------------------------------------------------------

END OF DOCUMENT
