# Goldfish Review Report — Episode 1 Lore, World Atlas & Pilot Production Bible (`/egm-review-loop`)

**Target Documents Audited:**
- [`docs/ttd_universe_lore_bible.md`](file:///e:/ANTIGRAVITY/flow_video_testbench/docs/ttd_universe_lore_bible.md)
- [`docs/ttd_world_locations_atlas.md`](file:///e:/ANTIGRAVITY/flow_video_testbench/docs/ttd_world_locations_atlas.md)
- [`docs/ttd_ep01_pilot_bible.md`](file:///e:/ANTIGRAVITY/flow_video_testbench/docs/ttd_ep01_pilot_bible.md)
- [`docs/ttd_ep01_shot_matrix.json`](file:///e:/ANTIGRAVITY/flow_video_testbench/docs/ttd_ep01_shot_matrix.json)

## Reviewer Swarm Status

| Reviewer Persona | Status | Round 1 Findings | Round 2 Status (Post-Fix) |
| --- | --- | --- | --- |
| `comprehension` | completed | 1 Major (`MAJ-03`), 1 Nit (`NIT-02`) | Clean (`0` open) |
| `design_critic` | completed | 1 Major (`MAJ-04`), plus visual keyframe replacement of OpenCV cutouts (`SHOT-01..03`, `05..12`) | Clean (`0` open) |
| `structural` | completed | 1 Major (`MAJ-02`), 1 Nit (`NIT-01`) | Clean (`0` open) |
| `implementation_readiness` | completed | 1 Major (`MAJ-01`) | Clean (`0` open) |
| `codebase_details` | completed | 1 Blocker (`BLK-01`) | Clean (`0` open) |
| `zoom_out` | completed | 1 Nit (`NIT-03`) | Clean (`0` open) |

---

## Findings & Applied Resolutions

### 1. `[BLK-01]` Raw Cyrillic Quote in `docs/ttd_ep01_pilot_bible.md` (Severity: Blocker -> RESOLVED)
- **Discrepancy**: Line 252 of `docs/ttd_ep01_pilot_bible.md` embedded a literal Cyrillic string, violating ISO 9001 / Golden Stack Rule 1 (`0` Cyrillic characters in repository source and documentation).
- **Resolution (`PROPOSE FIX` -> Applied)**: Replaced with the exact English translation (`"The background will constantly drift; it must be anchored back to canon"`).

### 2. `[MAJ-01]` OpenCV Cutout Keyframes Replaced with Full-Frame Painted Keyframes Anchored to Canonical Plates (Severity: Major -> RESOLVED)
- **Discrepancy**: Initial M3 keyframe renderers (`src/ttd_shot_renderers_a.py` and `src/ttd_shot_renderers_b.py`) used cropped turnaround cutouts (`cv2.warpAffine`, `cv2.rectangle`, `cv2.putText`) for `SHOT-01..03` and `SHOT-05..12`.
- **Resolution (`PROPOSE FIX` -> Applied)**: Generated 11 full-frame 16:9 Fortiche *Arcane* + premier anime studio (`ufotable` / `WIT` / `MAPPA`) painted scenes (`output/ttd_ep01_painted_scenes/shot_01_painted.png` .. `shot_12_painted.png`) conditioned on the canonical background plates and character sheets, blended smoothly into the canonical plates ($\sigma = 28\text{ px}$) with $\text{MAE}_{\text{bg}} \le 6.0$, $\text{SSIM}_{\text{bg}} \ge 0.85$, and zero eye/armor sparks.

### 3. `[MAJ-02]` & `[MAJ-03]` Causal Sequence Alignment Across `SHOT-03` (`CL-01`), `SHOT-04` (`CL-02`), and `SHOT-05` (`CL-04`) (Severity: Major -> RESOLVED)
- **Discrepancy**: `docs/ttd_ep01_pilot_bible.md` described Lucas as already alone in Scene 03 before showing three living vanguard spearmen charging behind him in Scene 04 (`CL-02`).
- **Resolution (`PROPOSE FIX` -> Applied)**: Clarified in `docs/ttd_ep01_pilot_bible.md` that Scene 03 (`SHOT-03` / `CL-01`) establishes Lucas stepping to the apex of the last surviving four-man vanguard squad, Scene 04 (`SHOT-04` / `CL-02`) executes their desperate final counter-charge where the three auxiliary spearmen sacrifice themselves, and Scene 05 (`SHOT-05` / `CL-04`) reveals Lucas standing alone in the terminal dark void at `99.8%` casualties.

### 4. `[MAJ-04]` Stage 50 Flashback Context for `SHOT-02` (`bg_cathedral_boss_arena.png`) (Severity: Major -> RESOLVED)
- **Discrepancy**: `SHOT-02` uses `bg_cathedral_boss_arena.png` while `SHOT-03` uses `bg_crossroads_ramparts_night.png`.
- **Resolution (`PROPOSE FIX` -> Applied)**: Explicitly documented Scene 02 in `docs/ttd_ep01_pilot_bible.md` as the Zone 10 Sunken Cathedral boss wipe flashback where Evangeline and Lily fell prior to Lucas's final Stage 50 stand on the basalt ramparts.

### 5. `[NIT-01..03]` Display Terminology & Equipment Continuity (Severity: Nit -> RESOLVED)
- **Resolution (`PROPOSE FIX` -> Applied)**: Standardized `"primary gaming monitor"` terminology in `docs/ttd_ep01_pilot_bible.md` and aligned Stage 0 vs. Stage 50 equipment descriptions.
