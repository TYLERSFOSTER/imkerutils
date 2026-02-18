# HARD Boundary-Constrained Image Editing Prompt Specification

## Purpose

This document defines a precise specification for **boundary-constrained
interior image modification**, ensuring that image edits preserve exact
boundary compatibility for seamless tiling and recomposition.

This specification must be followed exactly.

------------------------------------------------------------------------

## Input

You are given an image:

-   Resolution: **1024 × 1024 pixels**
-   Color space: RGB (assume 8-bit per channel unless otherwise stated)

Define:

-   Domain:\
    I : {0,...,1023} × {0,...,1023} → RGB

-   Boundary thickness:\
    b = 5 pixels

Define the boundary region:

B = { (x,y) \| x \< 5 OR x ≥ 1019 OR y \< 5 OR y ≥ 1019 }

Define the editable interior region:

Ω = { (x,y) \| 5 ≤ x ≤ 1018, 5 ≤ y ≤ 1018 }

------------------------------------------------------------------------

## Required output

Produce an output image:

I'

with resolution:

1024 × 1024 pixels

such that:

------------------------------------------------------------------------

## HARD constraint (non-negotiable)

For ALL boundary pixels:

I'(x,y) = I(x,y)

EXACTLY.

This means:

-   No color change
-   No smoothing
-   No resampling
-   No recompression artifacts
-   No reinterpretation
-   No regeneration

The pixel values must be bit-identical.

------------------------------------------------------------------------

## Editable region

For pixels in the interior region:

(x,y) ∈ Ω

you may modify content according to the requested edit.

However:

-   The boundary itself must remain unchanged.
-   Interior modifications must be visually continuous with the
    boundary.

------------------------------------------------------------------------

## Seamlessness requirement

The output must satisfy:

-   No visible seams at the boundary
-   No discontinuities in edges crossing the boundary
-   No abrupt color or texture transitions at the boundary

Interior modifications must condition on boundary context.

------------------------------------------------------------------------

## Explicit operational instruction

Treat the boundary region as:

READ-ONLY MEMORY

Interior region is:

WRITE-ALLOWED

Boundary region must be copied verbatim from input to output.

------------------------------------------------------------------------

## Explicit anti-patterns (DO NOT DO)

The following are forbidden:

-   Regenerating the entire image
-   Modifying the boundary even slightly
-   Applying filters to the entire image
-   Recompressing the image in a way that alters boundary pixels
-   Cropping or resizing the image
-   Changing image resolution

------------------------------------------------------------------------

## Correct conceptual model

Correct mental model:

Output image = Copy(input image) Modify only pixels strictly inside the
boundary region Leave boundary untouched

Equivalent to:

output = input.copy() output\[5:1019, 5:1019\] = modified_interior

------------------------------------------------------------------------

## Intended use

This constraint exists so that the modified image can be:

-   Seamlessly tiled with neighboring tiles
-   Reinserted into a larger parent image
-   Used in deterministic tiled diffusion pipelines
-   Used in gigapixel image processing workflows

------------------------------------------------------------------------

## Summary (single-sentence instruction)

Modify ONLY pixels strictly inside the 5-pixel boundary while leaving
ALL boundary pixels EXACTLY unchanged.
