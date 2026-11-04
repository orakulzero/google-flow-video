# Google Flow & Veo 3.1 Educational Video Studio — Standalone Lab (`flow_video_testbench`)

Parent Session: [Root Architecture Session](conversation://a6e93033-0846-422c-a4e2-dfc7274efe0d)

## Directory Layout
- `flow_testbench_runner.py` — End-to-end 720p HD educational video generator, Gemini 3.8 Studio TTS voiceover engine (`voice_y0joebp3bwta` / `Sulafat`), matplotlib scientific animation renderer, and HTML5 interactive player builder.
- `src/flow_bridge.py` — Standalone Google Flow (`labs.google/fx/tools/flow`) & Veo 3.1 (`aisandbox-pa.googleapis.com`) client, storyboard synthesizer, and WebVTT/SRT/MP4 builder.
- `src/flow_api.py` — FastAPI `/api/flow/*` router.
- `tests/test_flow_studio.py` — Standalone `pytest` verification suite.
- `scripts/report_to_root_session.py` — Sends structured JSONL + Markdown status reports back to [Root Architecture Session](conversation://a6e93033-0846-422c-a4e2-dfc7274efe0d).
- `scripts/sync_with_gemini_local_ui.py` — Bidirectional sync (`--push` / `--pull`) between this standalone testbench and `gemini_local_ui`.
- `.tts_cache/` — Persistent SHA-256 disk cache of verified Gemini 3.8 Studio TTS WAV files.
- `output/` — Rendered 720p MP4 lessons (`lesson_01_ru_transformer_mla`, `lesson_02_en_quantum_bell`), `.vtt`/`.srt` subtitles, and `output/index.html`.

## Operational Rules
1. Follow `.agents/rules/root-session-reporting.md` at all times.
2. Keep female-only studio narration (`voice_y0joebp3bwta` for RU, `Sulafat` for EN).
3. Run `pytest tests/test_flow_studio.py -v` and `python scripts/report_to_root_session.py ...` at the end of every milestone.
