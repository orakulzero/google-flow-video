# Episode 1 Fortiche Arcane 4.00-Second Vertical Slice ("Tyrant of the Tower Defense Game" — Knight Lucas Portrait)

* **Author:** Orakul Grey & PHANTOM END
* **Date:** 2026-11-03

## Overview

This feature builds a single-scene 4.00-second (`96` frames at `24.0` fps, `1280x720`) animated vertical slice for Episode 1 of *Tyrant of the Tower Defense Game* in the hand-painted Fortiche *Arcane* visual style, starting with the close-up portrait of Knight Lucas (`output/canonical_arcane_concepts/knight_lucas_portrait.png`).

Earlier 8-second `Veo 3.1` clips suffered from mid-clip camera drift, premature weapon discharges, and anatomy hallucinations because the model had to invent 5 to 6 seconds of filler motion. Our benchmark on real *Arcane* shots (`Vi` and `Jinx`) proved that `Gemini Omni 1.1 Flash` (internal Google Flow model ID `abra`), when driven in 2-frame Start + End Interpolation mode (`generate_video_with_interpolation`) at the minimum 4.00-second duration, locks both endpoints (`frame 0` and `frame 95`) and keeps the camera static.

To apply this 4.00-second interpolation workflow to Knight Lucas (`c03_knight_lucas_portrait`), the pipeline normalizes the starting frame (`first_frame.png`) to `1280x720`, generates a companion end frame (`last_frame.png`) where Lucas shifts from grim exhaustion to a defiant battle cry under intensifying crimson-amber fortress fire, composites the active foreground onto the static background of `first_frame.png` via a soft ROI alpha mask, verifies alignment with a lightweight pre-flight check, and dispatches the pair to `Gemini Omni 1.1 Flash` (`abra`) via Google Flow.

## Analysis

Six parallel Goldfish reviewers (`egm-design`, `egm-codebase-details`, `egm-zoom-out`, `egm-comprehension`, `egm-implementation-readiness`, `egm-structural`) audited this concept against the codebase. All blocking risks have been resolved into concrete engineering requirements:

1. **Resolution Normalization Without Mutating Canonical Assets (`1376x768 -> 1280x720`)**:
   `output/canonical_arcane_concepts/knight_lucas_portrait.png` is `1376x768` (`86:48`) and locked by `tests/test_flow_studio.py` (`test_m2_canonical_arcane_concept_arts_presence_and_geometry`). Modifying it in place would break the test suite, while feeding `1376x768` or `1344x768` into `veo_style_pipeline.py` would cause a `~10` px aspect shift and bypass the shape-equal endpoint MAE gate (`if frm.shape == gt_s.shape`).
   * **Resolution**: Keep `output/canonical_arcane_concepts/knight_lucas_portrait.png` read-only. Stage `veo_arcane_style/dataset/pairs/pair_ttd_ep01_lucas_001/first_frame.png` by applying a symmetric `10` px horizontal center-crop (`1376x768 -> 1366x768`) followed by Lanczos resize to exact `1280x720` *before* generating `last_frame.png`.

2. **ROI-Masked Static Background Lock (`first_frame.png -> last_frame.png`)**:
   Full-canvas image editing re-synthesizes every background pixel, shifting background fortress battlements and rain streaks by 2 to 6 pixels. When `Gemini Omni 1.1 Flash` interpolates between two frames whose backgrounds differ slightly, it interprets the background shift as a camera zoom or pan.
   * **Resolution**: Generate `last_frame_raw.png` from `first_frame.png` (`1280x720`), normalize to `1280x720`, and blend the active foreground subject (Lucas's head, expression, dented steel pauldrons, and rising ember/fire glow) onto the static background pixel buffer of `first_frame.png` using a feathered foreground mask $M(x,y) \in [0, 1]$. This guarantees static background stability (`MAE_bg <= 6.0`) on pass #1.

3. **Google Flow Ingredient Ordering & `reuse_top2=False` Enforcement**:
   In `veo_arcane_style/scripts/run_omni_flow_clips.py`, `main()` previously set `reuse_top2=(idx == 0)`, skipping local file uploads and attaching stale Vi/Jinx library frames. In addition, `attach_frame_human` swallowed `maseQ` upload timeouts without verifying `flow-image-ingredient-chip` count.
   * **Resolution**: Default `reuse_top2=False`, verify HTTP 200 on the `maseQ` upload RPC, assert `flow-image-ingredient-chip` count increments `0 -> 1 -> 2` before submitting the prompt, and resolve the browser profile path dynamically via `LOCALAPPDATA` / `Path.home()`.

4. **Lightweight Pre-Flight & Post-Flight Telemetry (`YAGNI`)**:
   * **Pre-Flight Pair Gate**: Assert exact `(1280, 720)` RGB PNG dimensions, static background perimeter `MAE_bg <= 6.0`, and active foreground ROI `8.0 <= MAE_roi <= 55.0` (ensuring visible action and lighting progression without scene replacement).
   * **Post-Flight Video Gate**: Assert `1280x720`, `24.0` fps, `96` frames (`4.00s`), `ftyp -> moov -> mdat` FastStart layout, start/end endpoint lock (`MAE_start <= 18.0`, `MAE_end <= 22.0`), and continuous frame-to-frame motion (no mid-clip scene cuts), accompanied by an 8-frame temporal filmstrip.

## Goals vs. Non-Goals

* **In-Scope Goals:**
  * Stage the Knight Lucas close-up pair (`first_frame.png` and ROI-masked `last_frame.png`) at exact `1280x720` under `veo_arcane_style/dataset/pairs/pair_ttd_ep01_lucas_001/`.
  * Harden `veo_arcane_style/scripts/run_omni_flow_clips.py` (dynamic profile path, `reuse_top2=False`, chip count assertion `0 -> 1 -> 2`, generic `--recover <idx>`).
  * Render `veo_arcane_style/output/omni_clip_03_lucas_interpolation_720p.mp4` (`4.00s`, `96` frames at `24.0` fps, `1280x720`, H.264 + AAC + FastStart) via `Gemini Omni 1.1 Flash` (`abra`) in `generate_video_with_interpolation` mode.
  * Verify endpoint MAE lock and render an 8-frame visual comparison filmstrip (`omni_lucas_interpolation_filmstrip.png`).
* **Out-of-Scope Non-Goals:**
  * Re-rendering all 16 micro-shots of the 69.83-second Episode 1 master sequence before this single-scene vertical slice is evaluated.
  * Adding PyTorch/LPIPS or local 3D/WebGL dependencies.
  * Modifying `output/canonical_arcane_concepts/*.png` or locked test suites in `tests/`.

## Alternatives Weighed

* **8.00-Second `Veo 3.1` First & Last Frame Interpolation (`Rejected`)**: Empirically tested; 8 seconds (`192` frames) causes mid-clip camera drift and hallucinated extra actions.
* **4.00-Second `Omni 1.1 Flash` 6-Frame Reference-to-Video (`Rejected for Exact Cut Continuity`)**: Empirically tested; treats reference images as loose style ingredients and changes camera framing instead of pixel-locking frame `0` and frame `95`.
* **Unmasked Full-Frame Image-to-Image for `last_frame.png` (`Rejected`)**: Causes 2 to 6 pixel background drift that `Omni 1.1 Flash` interprets as camera zoom.

## Key Decisions & Staging for Next Steps

1. **Target Scene Locked**: `output/canonical_arcane_concepts/knight_lucas_portrait.png` (`c03_knight_lucas_portrait`) — close-up of Knight Lucas in dented steel plate armor under rain and flying embers.
2. **4.00-Second Micro-Action Beat Locked**: Locked static close-up camera; Lucas raises his chin slightly and clenches/opens his jaw in a fierce battle stance while warm golden-orange fortress fire and flying embers intensify across his wet steel armor and scarred cheek (`ROI alpha blend` keeps the dark stormy fortress background 100% static).
3. **Ready for Formal Design (`/egm-draft`) or Direct Implementation**: All architectural blockers raised by the 6 Goldfish reviewers are resolved.
