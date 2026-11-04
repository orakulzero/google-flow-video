# Teamwork Project Prompt — Draft

> Status: Ready for launch — awaiting user approval
> Goal: Craft prompt → get user approval → delegate to `teamwork_preview` (or execute directly)
> Requested team: Small, focused team (single self-contained completion of `src/flow_bridge.py` + simple general-science demo render)

This is a single self-contained fix; keep it small and focused. Complete the remaining `REQ-001`, `REQ-002`, and `REQ-004` refinements in `src/flow_bridge.py` (`REQ-003` and `REQ-005` are already passing), render a clean, self-contained 3-scene 720p HD educational video demo on a simple general-science topic (**«Затухающие колебания маятника и физика резонанса»** / Damped Harmonic Pendulum & Resonance Physics) into `output/simple_flow_demo/`, and issue the ISO 9001:2015 (`v2.0.0`) quality certificate.

Working directory: e:\ANTIGRAVITY\flow_video_testbench
Integrity mode: development

## Requirements

### R1. Zero Truncation & Native Localization in Educational Video Compositor (`REQ-001`)
All scene titles, phase badges, focus pills, schematic callouts, scientific plot titles/legends, and Mayer CTML key-point cards in `FlowEducationalCompositor` (`src/flow_bridge.py`) must render without mid-word string truncation and must be 100% localized into Russian when `language="ru"` (and English when `language="en"`).

### R2. Aspect-Preserving Schematic Zoom & Distinct Multi-Scene Veo 3.1 Viewports (`REQ-002`)
The bottom-left engineering diagram viewport must use aspect-preserving `LANCZOS` smart zoom/crop around each scene's active `focus_bbox` with dynamically sized label pills rather than squishing full A4 sheets. The top-left Cloud Flow Veo 3.1 3D viewport must provide visually distinct camera crops and HUD telemetry across all scenes.

### R3. Collision-Free Scientific Plot Typography & Complete Mathematical Annotations (`REQ-003`)
All 4 procedural scientific plot modes (`hardware_topology`, `biquad_zplane`, `frequency_response`, `dma_timing`) must render with zero curve-over-text collisions, explicit axis labels, unit-circle zeros and poles, full-width impulse response `h[n]` envelopes from `t=0s`, and separated label/progress-bar tracks in the SRAM DMA timing view.

### R4. Dual-Stream Engineering Subtitles vs. Phonetic TTS & Orphan-Free Page Layout (`REQ-004`)
Visual subtitles (`narration_text`, `.srt`, `.vtt`) must display crisp engineering numbers and symbols while `tts_narration_text` feeds phonetic Russian to the locked female narrator (`voice_y0joebp3bwta`). Subtitle pages must be horizontally centered and balanced so no page ever contains fewer than 4 words.

### R5. Frame-Boundary Clamping & Glyph Cleanliness in Hybrid and Diff-Tour Engines (`REQ-005`)
In `src/flow_cli.py` (`draw_hardware_exploded_frame_at_t`), the hardware blocks must remain strictly inside the `1280x720` canvas (`x in [24, 1256]`) from `t=0.0s` onward. In `src/flow_diff_tour.py`, all step titles and badges must be free of raw `\u2014` em-dash tofu boxes.

### R6. Simple General-Science Educational Video Demo (`output/simple_flow_demo/`)
Create `scripts/render_simple_flow_demo.py` and render a 3-scene 720p HD educational video on a simple general-science topic outside the DSP coursework (**«Затухающие колебания маятника и физика резонанса»**, `language="ru"`, `voice_persona="voice_y0joebp3bwta"`), saving `output/simple_flow_demo/simple_flow_demo.mp4`, `.srt`, `.vtt`, and a 3×2 frame `contact_sheet.png`.

## Verification Resources

- Existing pytest verification suites (`C:\Python314\python.exe -m pytest`):
  - `tests/test_flow_studio.py`
  - `tests/test_github_repo_adaptations.py`
  - `tests/test_interactive_course.py`
  - `tests/test_flow_m5_m9_pipeline.py`
- ISO 9001:2015 / Agile V CLI (`C:\Python314\python.exe -m iso9000_agentops.cli --workspace .`) with frozen baseline `BL-20261027-L2`.

## Acceptance Criteria

### Programmatic & Visual Quality Gates
- [ ] `C:\Python314\python.exe -m pytest tests/test_flow_studio.py tests/test_github_repo_adaptations.py tests/test_interactive_course.py tests/test_flow_m5_m9_pipeline.py` passes 100% (`63/63 passed`), including `test_req_001` through `test_req_005`.
- [ ] Zero literal Cyrillic characters (`[\u0400-\u04FF]`) and zero personal/workspace path tokens across all `src/*.py` and `tests/*.py`.
- [ ] `output/simple_flow_demo/simple_flow_demo.mp4` (`> 50 KB`, valid `ftyp` ISO-BMFF container) and `output/simple_flow_demo/contact_sheet.png` are generated and verified free of text truncation or plot overlaps.
- [ ] `C:\Python314\python.exe -m iso9000_agentops.cli --workspace . certify --reqs REQ-001,REQ-002,REQ-003,REQ-004,REQ-005 --src src --tests tests` issues `status: "CERTIFIED"` in `.supergraph/quality_certificate.json`.

---
*Next: when approved → delegate via `invoke_subagent` (`teamwork_preview`) or execute directly*
