# Project: Tyrant of the Tower Defense Game — Episode 1 Pilot Keyframes & Flow Clips Autonomous Generation

## Architecture
- **Canonical Lore & World Atlas Engine (`M1`)**:
  - `docs/ttd_universe_lore_bible.md`: Authoritative narrative context of Stage 50 Final Wave (Tae-Seok 1056th attempt, Hell Ironman), Lucas's survival mechanics (*Man of Steel*, *Strike of Will*, *Step of Tenacity*), battle aftermath and transition, Prince Ash's profile and immediate Stage 0 Tutorial crisis.
  - `docs/ttd_world_locations_atlas.md`: Crossroads Forward Fortress (30m basalt curtain wall, kill-zone moat, gatehouse, command spire, dungeon), Black Fog (300m boundary, supernatural miasma), New Terra Imperial Capital, Sunken Lake Kingdom (Sleepless Princess), Evergreen Elven forest, Shadow Squad convict outcasts.
- **Visual Style, Character Model Sheets & Storyboard Matrix (`M2`)**:
  - `docs/ttd_ep01_pilot_bible.md` and `docs/ttd_ep01_shot_matrix.json`: Codified 4-shot Climax Sequence (`SHOT CL-01` to `SHOT CL-04`) and 12 pilot episode scenes.
  - Master Knight Lucas character specification: 3/4 Medium Close-Up to Close-Up angle (Yaw 30 deg, Pitch +10 deg, Dutch tilt 12 deg, 15% push-in over 4s), clenched-jaw to roaring command ("CHARGE!"), anatomically grounded steel-gray eyes with torchlight reflections, strictly zero magic sparks on eyes, armor, or blade. Blurred silhouettes of 3 charging vanguard spearmen in deep background bokeh.
  - Canonical 16:9 golden background plates (`output/canonical_plates/`): `bg_crossroads_ramparts_night.png`, `bg_cathedral_boss_arena.png`, `bg_streamer_room_night.png`.
  - Updated `src/flow_prompt_library.py` with refined Fortiche Arcane + Manhwa + Anime prompts.
- **Google Flow Keyframe & Video Generation Pipeline (`M3`)**:
  - Canonical 1280x720 16:9 keyframes for Episode 1 pilot scenes via Google Flow (`AgentOnlyComposer` + `GEM_PIX_2`) and workspace generation tooling.
  - Genuine Google Flow / Veo 3.1 / Gemini Omni 1.1 Flash video cuts using `generate_video_with_interpolation` (`Mode.I2V`) and reference conditioning.
  - Native audio and studio Russian female narration (`voice_y0joebp3bwta`) preserved.
- **Visual Review, Background Drift Remediation & Contact Sheet Assembly (`M4`)**:
  - Multi-agent visual review of each generated frame/cut.
  - Programmatic spark/laser Laplacian exclusion audit and background drift SSIM audit ($\text{SSIM}_{\text{bg}} \ge 0.85$, $\text{MAE}_{\text{bg}} \le 6.0$).
  - Inpainting/regeneration of drifted background frames using Gaussian ROI alpha compositing onto canonical background plates.
  - Master Visual Comparison Contact Sheet (`output/ttd_ep01_master_contact_sheet.png`) and manifest.
- **Dual Verification Suite & Autonomous Brain Mirroring (`M5`)**:
  - Automated Pytest suite (`tests/test_ttd_ep01_pilot_delivery.py`) validating media parameters (1280x720, 24fps CFR, H.264, FastStart, audio RMS, zero mock contamination, zero Cyrillic in code).
  - Mirror all deliverables with `ttd_ep01_` prefixes into persistent brain storage `C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f` with cryptographically verified bit-for-bit SHA-256 parity.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Universe Lore Bible Codification | Stage 50 final wave, Lee Tae-Seok 1056th run, Hell Ironman permadeath, Lucas sole survivor mechanics | M1 | Survey Lore |
| 2 | World Locations Atlas Codification | Crossroads 30m basalt walls, Black Fog 300m boundary, New Terra, Sunken Lake Kingdom, Evergreen, Shadow Squad | M1 | Survey Lore |
| 3 | Knight Lucas Master Character & Facial Model Sheet | 3/4 low angle, weathered tan skin, left cheek claw scar, natural steel-gray irises, zero glowing eye sparks | M2 | Survey Visual |
| 4 | Knight Lucas Armor & Weapon Metallurgy Specs | Battered blackened gothic plate, acid gouges, frayed navy tabard, heavy notched Oakeshott bastard sword, zero blade glow | M2 | Survey Visual |
| 5 | Episode 1 4-Shot Climax Sequence Storyboard | CL-01 Establishing Step, CL-02 Command Roar (3/4 CU), CL-03 Kinetic Charge Cut, CL-04 Solitary Back in Dark Void | M2 | Survey Visual |
| 6 | Canonical Golden Background Plates Staging | 16:9 plates for Crossroads Ramparts, Cathedral Boss Arena, Streamer Room | M2 | Survey Pipeline |
| 7 | Flow Lexical Prompt Formula Tuning | 6-stage Fortiche Arcane prompt tuning with negative constraints against arcade sparks and plastic 3D | M2 | Survey Pipeline |
| 8 | Google Flow Pilot Keyframe Generation | 12 verified 720p 16:9 pilot keyframes via Flow GEM_PIX_2 / workspace generator | M3 | Survey Pipeline |
| 9 | Genuine Veo 3.1 / Omni Flash Video Generation | Live Patchright generation with First+Last frame interpolation and reference conditioning | M3 | Survey Pipeline |
| 10 | Background Drift Suppression & Soft ROI Inpainting | Gaussian ROI alpha masking ($\sigma=28$ px, $\text{MAE}_{\text{bg}} \le 6.0$, $\text{SSIM}_{\text{bg}} \ge 0.85$) | M4 | Survey Pipeline |
| 11 | Spark & Laser Laplacian Exclusion Audit | Programmatic detection banning V>245, S>120 and sharp Laplacian eye/armor spikes | M4 | Survey Pipeline |
| 12 | Master Visual Comparison Contact Sheet | Multi-card contact sheet (Canon Ref, Start Frame, Mid Frame, End Frame, Difference Heatmap) | M4 | Survey Pipeline |
| 13 | Automated Pilot Delivery Test Suite | Pytest suite enforcing 1280x720, 24fps CFR, H.264 FastStart, audio RMS, zero mock contamination | M5 | Survey Pipeline |
| 14 | Prefixed Cryptographic Brain Mirroring | Mirroring all ttd_ep01 deliverables to brain store 94dd6a04-... with SHA-256 parity manifest | M5 | Survey Pipeline |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Canonical Universe Lore Bible & World Locations Atlas | Features 1, 2 | none | DONE |
| M2 | Episode 1 Storyboard, Character Model Sheets & Combat Shot Design | Features 3, 4, 5, 6, 7 | M1 | DONE |
| M3 | Google Flow Keyframe & Video Generation | Features 8, 9 | M2 | DONE |
| M4 | Visual Quality Review, Background Drift Inpainting & Contact Sheet | Features 10, 11, 12 | M3 | DONE |
| M5 | Dual Verification Suite & Autonomous Brain Mirroring | Features 13, 14 | M4 | DONE |

## Interface Contracts
### M1 ↔ M2 (Lore & Atlas ↔ Visual Storyboard)
- Input: `docs/ttd_universe_lore_bible.md` and `docs/ttd_world_locations_atlas.md`.
- Output: `docs/ttd_ep01_pilot_bible.md`, `docs/ttd_ep01_shot_matrix.json`, updated `src/flow_prompt_library.py`.
- Invariants: All visual prompts must reference canonical lore tokens (`basalt_stone`, `obsidian_iron`, `Crossroads`, `Black Fog 300m`).

### M2 ↔ M3 (Shot Prompts & Golden Plates ↔ Flow Keyframe Generation)
- Input: Refined shot matrix, golden background plates (`output/canonical_plates/*.png`), and staged Lucas pair.
- Output: `output/ttd_ep01_flow_keyframes/` (12 verified 720p 16:9 keyframes), `output/ttd_ep01_flow_videos/*.mp4`.
- Invariants: Exact 1280x720 resolution, H.264 CFR 24fps, FastStart box structure, native audio preserved.

### M3 ↔ M4 (Generated Assets ↔ Visual Review & Inpainting)
- Input: Generated keyframes and video cuts.
- Output: Drift-corrected frames, `output/ttd_ep01_master_contact_sheet.png`, `output/ttd_ep01_manifest.json`.
- Invariants: $\text{SSIM}_{\text{bg}} \ge 0.85$, $\text{MAE}_{\text{bg}} \le 6.0$, Laplacian spark count $\le 4$ in face/eye ROI.

### M4 ↔ M5 (Deliverables ↔ Verification Suite & Brain Mirroring)
- Input: All verified media deliverables and manifest.
- Output: 100% passing tests in `tests/test_ttd_ep01_pilot_delivery.py`, bit-for-bit mirror in brain store `94dd6a04-54e7-4e8c-9551-224cace4f85f`.
- Invariants: Zero mock contamination, zero Cyrillic characters in `.py` source/tests, 100% SHA-256 parity.

## Code Layout
- `docs/ttd_universe_lore_bible.md`: Comprehensive universe lore bible.
- `docs/ttd_world_locations_atlas.md`: Canonical world locations atlas.
- `docs/ttd_ep01_pilot_bible.md`: Episode 1 pilot production bible.
- `docs/ttd_ep01_shot_matrix.json`: Episode 1 shot-by-shot specification matrix.
- `src/flow_prompt_library.py`: Fortiche Arcane + Manhwa + Anime prompt definitions.
- `src/ttd_lore_bible.py`: Programmatic lore tokens and character/environment profiles.
- `output/canonical_plates/`: Golden 16:9 background plates.
- `output/ttd_ep01_flow_keyframes/`: Generated 1280x720 pilot keyframes.
- `output/ttd_ep01_flow_videos/`: Generated 720p MP4 clips.
- `scripts/verify_ep01_cinematic_delivery.py`: Media container validator.
- `tests/test_ttd_ep01_pilot_delivery.py`: Pytest verification suite.
