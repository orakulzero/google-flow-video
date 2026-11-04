# Opening Bootstrap Prompt (Copy & Paste into New Antigravity Session in `e:\ANTIGRAVITY\flow_video_testbench`)

```markdown
Ты работаешь в изолированной лаборатории `e:\ANTIGRAVITY\flow_video_testbench` (разработка и тестирование **Google Flow & Veo 3.1 Educational Video Studio** — модуль M27 для `gemini_local_ui`).
Корневая архитектурная сессия: [Root Architecture Session](conversation://a6e93033-0846-422c-a4e2-dfc7274efe0d).

Перед началом работы:
1. Прочитай `AGENTS.md`, `.agents/rules/root-session-reporting.md`, `flow_testbench_runner.py` и `src/flow_bridge.py`.
2. Запусти базовую проверку `pytest tests/test_flow_studio.py -v`, чтобы убедиться, что стенд зелёный.

Текущие инварианты, которые нельзя ломать:
- **Только женский голос диктора** во всех сценах (мужские голоса отключены):
  - Для русского языка (`ru`): кастомный студийный голос Gemini 3.8 Voice Design `voice_y0joebp3bwta` (Warm Mezzo-Soprano Science Lecturer), резерв `Sulafat`, оффлайн-резерв `ru-RU-SvetlanaNeural`.
  - Для английского языка (`en`): студийный женский голос `Sulafat` (`gemini-3.8-flash-lite-tts` / `gemini-3.8-flash-tts`), резерв `Kore`, оффлайн-резерв `en-US-EmmaMultilingualNeural`.
- Запросы к Gemini 3.8 TTS идут с заголовком `Api-Revision: 2026-05-20` через локальный прокси `http://127.0.0.1:7890` (`_detect_local_proxy()`), ключ `GEMINI_API_KEY` подтягивается из окружения или `HKCU\Environment`.
- Все сгенерированные WAV проходят проверку `_is_valid_speech_wav()` (`длительность >= 2.8s`, `RMS >= 350`) и кэшируются по SHA-256 в `.tts_cache/`.

Правило отчётности в корневую сессию (`a6e93033-0846-422c-a4e2-dfc7274efe0d`):
После каждого завершённого шага или доработки обязательно выполняй:
1) `pytest tests/test_flow_studio.py -v`
2) `python scripts/sync_with_gemini_local_ui.py --push` (если менялись `src/flow_bridge.py` или `src/flow_api.py`)
3) Отправку отчёта в корневую сессию:
   `python scripts/report_to_root_session.py --status "VERIFIED" --summary "<краткий итог>" --change "<что изменено>" --tests "pytest passed"`

Подтверди готовность стенда и жди моих указаний по доработке инструмента.
```
