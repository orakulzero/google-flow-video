# Google Flow & Veo 3.1 Educational Video Studio — Testbench

Standalone testbench for evaluating **Google Flow (`labs.google/fx/tools/flow` / `veo_3_1_t2v_fast_audio`)** and **Gemini 3.8 Studio Voice Design (`gemini-3.8-flash-tts` / `gemini-3.8-flash-lite-tts`)** before publishing `v1.1.0` to `orakulzero/gemini_local_ui`.

## Voice Engine Architecture (Unified Female Studio Narrator)

1. **Tier 1 — Gemini 3.8 Studio Voice Design (`/v1beta/voices` + `/v1beta/interactions`)**:
   - **Russian Female Lecturer (`voice_y0joebp3bwta`)**: Custom-designed native Russian warm mezzo-soprano science communicator across all scenes.
   - **English Female Lecturer (`Sulafat`)**: Curated Gemini 3.8 warm studio female voice across all scenes.
   - **Prosody & Emphasis**: Phrases wrapped in `*...*` are converted to uppercase vocal stress cues with natural `<short pause>` breathing breaks at clause boundaries (`:` and `—`).
   - **Persistent Disk Cache (`.tts_cache/`)**: Every synthesized studio WAV is cached by SHA-256 hash so repeated runs are instantaneous and consume zero API quota.
2. **Tier 2 — Microsoft Edge Female Neural TTS via Local Proxy (`127.0.0.1:7890`)**:
   - High-availability female fallback (`ru-RU-SvetlanaNeural`, `en-US-EmmaMultilingualNeural`) with automatic retry and acronym transliteration.

## Quick Start

1. Open [`index.html`](file:///e:/ANTIGRAVITY/flow_video_testbench/index.html) in your browser or double-click [`start_testbench.cmd`](file:///e:/ANTIGRAVITY/flow_video_testbench/start_testbench.cmd).
2. Generated lessons:
   - **Russian Lesson (4 scenes, Female Mezzo `voice_y0joebp3bwta`)**: [`output/lesson_01_ru_transformer_mla/lesson_full_720p.mp4`](file:///e:/ANTIGRAVITY/flow_video_testbench/output/lesson_01_ru_transformer_mla/lesson_full_720p.mp4)
   - **English Lesson (3 scenes, Female `Sulafat`)**: [`output/lesson_02_en_quantum_bell/lesson_full_720p.mp4`](file:///e:/ANTIGRAVITY/flow_video_testbench/output/lesson_02_en_quantum_bell/lesson_full_720p.mp4)
3. Generate a custom topic:
   ```powershell
   python flow_testbench_runner.py --topic "Квантовая криптография и протокол BB84" --lang ru --scenes 4
   ```
