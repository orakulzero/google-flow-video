# E2E Test Infra: Motorola DSP56824 Coursework Interactive Intensive

## Test Philosophy
- Requirement-driven, opaque-box and grey-box verification.
- Enforces ISO 9001:2015 Agile V quality gates.
- Strict invariant checks: 0 literal Cyrillic characters in `src/*.py` and `tests/*.py` (`\u04...` escapes only), 0 personal credentials or tokens.

## Feature Inventory & Test Mapping
| # | Feature | Requirement | Test Suite & Gate |
|---|---------|-------------|-------------------|
| 1 | 43-Page + E2/PE2 Left Pane Viewer | R1 | Gate 1: Asset Completeness (300 DPI, dimensions >= 2400 px) |
| 2 | 100% Page Coverage & Structural Cards | R1 | Gate 2: 100% Page Mapping (0 dead pages across 1..43, E2, PE2) |
| 3 | Bidirectional Sync Engine | R1 | Gate 2: DOM & CourseSyncEngine events |
| 4 | Cauer IIR N=11 & Q15 Quantization Lab | R2 | Gate 3: Mathematical & Simulation Invariants (poles, gains, Q15) |
| 5 | DSP56824 Oscilloscope & DO #6 Stepper | R2 | Gate 3: Pipeline Timing (150 cycles = 3.75 µs, 18% CPU load) |
| 6 | Analog Sallen-Key & 0-WS Simulator | R2 | Gate 3: Analog & SRAM Timing (f0 = 25.03 kHz, 10 ns < 25 ns) |
| 7 | Embedded Video Player & Flashcards | R2 | Gate 2: Media & Flashcard DOM presence (12 cards, localStorage) |
| 8 | Floating Text Selection Toolbar | R3 | Gate 2: DOM presence of text question action bar |
| 9 | Rectangular/Lasso Image Crop Tool | R3 | Gate 2: DOM presence of image lasso selection canvas |
| 10 | Hybrid 1-Click Dispatch Bridge | R3 | Gate 4: API Endpoint round-trip & Clipboard payload format |
| 11 | FastAPI Question Bridge Endpoint | R3 | Gate 4: POST /api/flow/intensive-question JSON & PNG persistence |
| 12 | REQ-004 Code Cleanliness Audit | Cleanliness | Gate 5: 0 literal Cyrillic in *.py, 0 personal tokens |
| 13 | Operational Sync Compatibility | Sync | Gate 6: Synchronization verification with gemini_local_ui |

## Test Architecture
- Test Runner: `python -m pytest tests/test_interactive_course.py tests/test_flow_studio.py tests/test_flow_m3_m5_verification.py -v`
- Pass/Fail Semantics: 100% pass (0 failures, 0 skips on critical paths).
- Test File Location: `tests/test_interactive_course.py`
