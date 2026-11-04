# Original User Request

## 2026-10-23T18:09:23Z

Комплексная модернизация программной видеостудии Google Flow & Veo 3.1 Educational Video Studio (модуль M27 для `gemini_local_ui`) под защиту курсовой работы по ЦОС (Вариант №5, Motorola DSP56824, каф. ИТРС, ПГТУ) с увеличением хронометража до 30+ минут, точным таймингом подсветки субтитров (word-level alignment), единым тембром диктора, аутентичными англоязычными терминами в субтитрах и актуализацией по материалам сессии `ЦОС 3`.

Working directory: e:\ANTIGRAVITY\flow_video_testbench
Integrity mode: development

## Requirements

### R1. Точный тайминг подсветки слов в субтитрах (Word-Level Timing Alignment)
- Исключить аппроксимацию тайминга слов по равномерному делению символов строки.
- Внедрить точное вычисление временных границ каждого слова (startMs / endMs) по аналогии с Remotion @remotion/captions (TikTokPage) и ShortGPT, используя временные метки фонем/слов из синтезатора речи (WordBoundary) либо интегратор речевой активности (VAD / RMS envelope integration с фиксацией пауз <short pause>).
- Активное слово должно подсвечиваться янтарно-золотым цветом строго в момент его физического звучания диктором.

### R2. Актуализация материалов слайд-шоу и чертежей по сессии «ЦОС 3»
- Синхронизировать графику, расчетные параметры и формулировки с финальным состоянием сессии ЦОС 3 (525e6c9d-6a46-4eb4-a036-15eb0bd427b4):
  - Пояснительная записка: 43 страницы (Стр. 6–41 со штампами Формы 2/2а, Приложения Б и В).
  - Параметры дискретизации: f_д = 48 кГц, T_s = 20,833 мкс, тактовая частота ядра 40,000 МГц, частота кодека MCLK 12,288 МГц, SCLK 3,072 МГц.
  - Архитектура и схемотехника: Motorola DSP56824 (DA1), кодек AD73322 (DA2), SRAM IS61LV6416 (DA3, 10–12 нс), ФНЧ Саллена–Кея на AD8606AR (DA4, DA5, f_0 = 25,03 кГц, Q = 0,736), супервизор MAX706S (DA6), стабилизатор AMS1117-3.3 (DA7), МК индикации MC68HC908GP32 (DD1).
  - Графика MATLAB: Рис. 5.2 — плашка «ФИЛЬТР УСТОЙЧИВ» строго в левом верхнем углу вне |z|=1 (зазор >45 px); Рис. 5.3 — f_1 = 10 кГц малиновый штрихпунктир, f_2 = 11 кГц зеленый штрихпунктир; серая линия 0 dB исключена из легенды.
  - Таблица 6.1: столбец 3 отцентрирован, запятая 0,1;.
  - Заключение: п. 3 — ФНЧ Саллена-Кея, наработка на отказ 1,034 * 10^6 ч, Delta T ~ 4,2 °C; п. 4 — чертежи Э2 А3 и ПЭ2 А4 (КОМПАС-3D v22, KiCad 8.0).

### R3. Строго единый персонаж диктора во всех сценах
- Исключить любые переключения тембров между сценами и циклами (включая несанкционированные переключения на Sulafat / SvetlanaNeural).
- Закрепить единый студийный тембр: Gemini 3.8 Voice Design voice_y0joebp3bwta (Warm Mezzo-Soprano Academic Lecturer) с кэшированием в .tts_cache/ и строгим контролем валидности (_is_valid_speech_wav: длительность >= 2,8 с, RMS >= 350).

### R4. Аутентичное написание иностранных терминов и микросхем в субтитрах
- Разделить поток синтеза речи (TTS) и визуальный поток субтитров:
  - В субтитрах и карточках тезисов иностранные названия компонентов и терминов отображаются на языке оригинала: Motorola DSP56824, AD73322, IS61LV6416, MAX706S, AD8606AR, AMS1117-3.3, MC68HC908GP32, WH1602B, Direct Form II, Q15, SSI_Rx_ISR, SRAM, MAC, ALU, AGU, PLL, MIPS, KiCad 8.0, MATLAB, L_infinity.
  - Фонетическая развертка (format_dsp_phonetics_ru: Ди-Эс-Пи пятьдесят шесть восемьсот...) подается исключительно на вход TTS-движка и никогда не попадает в субтитры.

### R5. Полная орфоэпическая разметка ударений (Stress Accents)
- Проставить знак + перед ударными гласными во всех технических терминах, числительных и падежных формах (например, спрос+или, спроектир+овано, дискретиз+ации, эллипт+ический, подавл+ение, перес+ылки, нулев+ое, коэффиц+иент, отсч+ёт, разр+ядной), чтобы полностью исключить ошибки ударения при генерации звука.

### R6. Масштабирование хронометража до 30+ минут с глубокой проработкой и визуализациями
- Расширить структуру до 30+ минутного полномасштабного доклада:
  - Введение и регламент защиты (2–3 мин): цели, задачи, структура комплекта, соответствие ГОСТ/ЕСКД.
  - Раздел 1 — Архитектура процессора Motorola DSP56824 и математика конвейера (6–8 мин): ядро DSP56800, Гарвардская структура, параллельные пересылки dual-move, MAC 16x16 в 36-битный аккумулятор, блок генерации адресов AGU с кольцевыми буферами.
  - Раздел 2 — Аппаратная схема, интерфейс SSI/SPORT и аналоговая обвязка (6–8 мин): временные диаграммы кодека AD73322, расчет ФНЧ Саллена–Кея на ОУ AD8606, расчет надежности MTBF и теплового режима, обзор чертежей Э2 А3 и ПЭ2 А4.
  - Раздел 3 — Синтез эллиптического БИХ-фильтра N=12 и моделирование в MATLAB (6–8 мин): билинейное Z-преобразование, Direct Form II, масштабирование по L_infinity-норме, квантование коэффициентов в сетку Q15, анализ нулей и полюсов (Рис. 5.2), АЧХ (Рис. 5.3) и спектрограмм (Рис. 5.5).
  - Раздел 4 — Прошивка ассемблера, оптимизация по тактам и доказательство реального времени (6–8 мин): вектор P:$001E, обработчик прерывания SSI_Rx_ISR, кольцевой буфер состояний, формула времени вычисления t_calc = 3,75 мкс, запас 82% ядра.
  - Заключение и ответы на типовые вопросы комиссии ГЭК (4–6 мин).
- Внедрить заставки тем, плавные переходы (xfade), динамические схемы потоков данных (dataflow animation) и пошаговые визуализации для каждого термина.

## Acceptance Criteria

### Функциональные критерии
- [ ] Суммарный хронометраж итогового мастер-ролика lesson_full_720p.mp4 составляет не менее 30 минут (1800+ секунд).
- [ ] Во всех сценах используется строго один голос диктора: voice_y0joebp3bwta (Gemini 3.8 Studio Warm Mezzo), без выпадения в другие голоса.
- [ ] В субтитрах иностранные обозначения (DSP56824, AD73322, IS61LV6416, Direct Form II, Q15, MAX706S и др.) отображаются на латинице в оригинальном написании.
- [ ] Подсветка слов в субтитрах синхронизирована с фактическим звучанием диктора с расхождением не более +-150 мс.
- [ ] В тексте для TTS все технические термины и сложные слова размечены ударениями +.
- [ ] Все графические иллюстрации соответствуют последней версии сессии ЦОС 3 (Рис. 5.2 с плашкой вне единичного круга, Рис. 5.3 с корректной легендой, чертежи Э2 А3 и ПЭ2 А4).

### Инженерно-технические критерии
- [ ] Все 13+ тестов python -m pytest tests/test_flow_studio.py -v проходят со статусом PASS.
- [ ] Программный рендеринг работает в режиме Zero-Disk In-Memory Pipe без создания гигабайтных файлов frames.rgb.
- [ ] Интерактивный двухрежимный пульт output/dsp_defense_index.html и студийный index.html обновлены и поддерживают 30-минутный ролик с оглавлением по главам и таймкодам.


## 2026-10-24T09:27:02Z

Build a strict, non-slideshow programmatic educational animation pipeline (3Blue1Brown / ManimGX / Motion Canvas paradigm based on Mayer's Cognitive Theory of Multimedia Learning) in `e:\ANTIGRAVITY\flow_video_testbench` that produces a substantive 20–30 minute engineering lecture with continuous visual state morphing, camera focus/zoom transitions, progressive disclosure of formulas/schematics/plots, and cloud-synthesized single-speaker Russian female narration.

Working directory: e:\ANTIGRAVITY\flow_video_testbench
Integrity mode: development

## Requirements

### R1. Strict Programmatic Engineering Animation (Zero Slideshow / Zero Decorative Clutter)
Replace static bullet-point slides and decorative background HUD clutter with continuous, state-driven programmatic animations following Mayer's CTML principles (Progressive Disclosure, Signaling, Spatial & Temporal Contiguity, Modality):
- Strip all decorative non-informative chrome (remove permanent ESKD border stamps, random entropy badges, and static bullet lists).
- Every scene must animate actual engineering causality: live signal waveforms transforming as they pass through filter stages, step-by-step equation derivation where active terms highlight in sync with speech, Z-plane pole-zero positions dynamically shaping the magnitude/phase response curve, camera zoom-ins onto active hardware bus transfers (`DSP56824` / `STM32H743` <-> `SRAM IS61LV6416`), and line-by-line assembly/C execution tracing with live register/accumulator state updates.
- On-screen text must be limited to mathematical expressions, component labels, numerical parameters, and concise 2–4 word callouts (plus bottom subtitle track preserving Latin technical acronyms).

### R2. Long-Form (20–30 Minute) Multi-Chapter Pedagogical Structure
Construct a cohesive 20–30 minute lecture structured into clear thematic chapters with smooth animated chapter transitions, term definitions cards, and deep mathematical/hardware walkthroughs (covering technical specification, hardware architecture, analog anti-aliasing filter, IIR filter synthesis, Q15 fixed-point quantization effects, real-time assembly pipeline, and verification metrics) sourced from the verified coursework specification.

### R3. Cloud-Native Single-Speaker Russian Female Voiceover & Word-Level Sync
Synthesize all narration in the cloud using a unified female lecturer voice (Gemini 3.8 Studio TTS `voice_y0joebp3bwta` with automatic failover to Gemini Ultra Web Session TTS `XqA3Ic`, cached in `.tts_cache/`, and optional Flow/Veo chapter intros) with verified Russian stress accents and phonetic expansion of chip/bus acronyms. Drive every visual reveal, formula term highlight, and camera pan/zoom from exact spoken word/phrase timestamps (`[span]` synchronization).

## Acceptance Criteria

### Animation Quality & Cognitive Clarity
- [ ] Zero static bullet-list slides and zero decorative filler HUD badges: 100% of scenes contain progressive multi-step visual transformations (minimum 4 distinct visual state transitions per 30 seconds of animation, verified via `build_contact_sheet` frame-delta and layout diagnostics).
- [ ] `manimgx` / layout diagnostics report `clean == True` (zero overlapping equations/labels, zero cutoffs, zero unreadable tiny text).
- [ ] On-screen labels (excluding subtitles) never exceed 6 words per label, enforcing Mayer's Modality Principle.

### Duration, Audio & Synchronization
- [ ] Assembled lecture duration is at least 20 minutes (or configurable full-depth run >= 1,200 seconds across all chapters) at 1280x720 HD, 30 fps H.264 + 48 kHz AAC.
- [ ] 100% cloud-generated Russian female narration (`voice_y0joebp3bwta` / Ultra Web TTS) with zero local sine-wave/formant fallback and verified vocal RMS energy.
- [ ] All automated pytest verification suites pass (`0` Cyrillic and `0` personal path tokens in `src/` and `tests/`).


## 2026-10-25T06:11:55Z

Build a **Split-Screen Live Sync** educational video pipeline for defending the Motorola DSP56824 coursework (Variant №5, Dept. of ITRS, PSTU) and **re-render all actual `.mp4` video files on disk** (`output/lesson_03..07/lesson_full_720p.mp4` and per-scene `.mp4` clips) plus the interactive defense workstation (`output/dsp_defense_index.html` and `dsp_defense_index.html`). Every spoken concept in the 53-scene (32m01s / 1,921s) Russian female narration (`voice_y0joebp3bwta`) must drive both panels in real time:
1. **Left Viewport (43-Page 300 DPI Coursework & Blueprint Inspector)**: rasterizes all **43 pages** of the final verified coursework PDF (`E:\STUDY_NEW_GEN\ЦОС\coursework\release_final\Пояснительная_записка_ЦОС_Иванов.pdf`, dated `22.10.2026`) and the updated `22.10.2026` ESKD drawings (`ПГТУ.466225.001_Э2.pdf`, `ПГТУ.466225.001_ПЭ2.pdf`) + MATLAB/algorithm figures (`fig_3_1_canonical.png`, `fig_4_1_large.png`, `fig_5_1_cropped.png`, `fig_5_2_clean.png`, `fig_5_3_clean.png`, `fig_5_5_clean.png`) at **300 DPI**. Pages advance sequentially from Page 1 to Page 43 across the 53 scenes, and within each scene a word-synchronized camera (`closed_form_spring`) smoothly pans and zooms onto the exact paragraph, formula `(1.1)..(6.5)`, table row (`Таблица 2.1`, `5.1`, `6.1`), assembly routine (`Приложение А`, pp. 38–41), or schematic node (`Э2` p. 42, `ПЭ2` p. 43) being spoken, framed by a glowing callout highlight box.
2. **Right Viewport (Word-Synchronized Multi-Concept Dynamic Process Animation)**: switches across **3–5 distinct concept cues per scene** triggered by the spoken word timestamps (`words[i].start_ms`), dynamically animating the exact chip, signal, formula, filter stage, or assembly instruction being discussed right now.

Working directory: .
Integrity mode: development

## Reference Material & Authoritative Inputs
- **Final Coursework Master PDF (43 pages, `22.10.2026 15:02:31`)**: `E:\STUDY_NEW_GEN\ЦОС\coursework\release_final\Пояснительная_записка_ЦОС_Иванов.pdf`
  - Pages 1–2: Title Page & Technical Assignment (Variant №5)
  - Page 3: Bilingual Abstract (43 pages, 7 figures, 2 ESKD drawings, 3 tables, $T_s = 20.833\ \mu\text{s}$)
  - Pages 4–5: Table of Contents (41 synchronized entries)
  - Pages 6–7: Introduction (Sheet 1 Form 2 stamp + Sheet 2)
  - Pages 8–10: Section 1 — Technical Specification Analysis & Formulas (1.1)–(1.7)
  - Pages 11–15: Section 2 — Processor Selection, Table 2.1 (`DSP56824` vs `TMS320C54x` vs `ADSP-218x`), Harvard 6-bus matrix, Dual-Access X-RAM
  - Pages 16–20: Section 3 — Block Diagram (Fig. 3.1), Sallen-Key LPF ($f_0=25.03\text{ kHz}, Q=0.736$), Reliability ($\text{MTBF}=1.034\cdot 10^6\text{ h}$) & Thermal ($\Delta T=4.2\ ^\circ\text{C}, P_{\text{DA7}}=322\text{ mW}, P_\Sigma=947.5\text{ mW}$)
  - Pages 21–24: Section 4 — Functional Circuit, SSI/SPI interfaces, Algorithm Flowchart (Fig. 4.1)
  - Pages 25–30: Section 5 — Elliptic IIR Filter $N=11$ (6 biquads DF-II, Fig. 5.1, Table 5.1 Q15 & $L_\infty$ scaling $g_1..g_6, g_{\text{out}}=4.8236$, Fig. 5.2 Z-plane $|p_{\max}|=0.9878$, Fig. 5.3 Bode/Phase/Group Delay, Fig. 5.5 float64 vs Q15)
  - Pages 31–34: Section 6 — Firmware Development, 23-instruction `DO #6` loop, 8-register LIFO stack, Real-time load ($114..150$ cycles / $130$ cycles with LIFO $= 3.25\ \mu\text{s} < 20.833\ \mu\text{s}$), Table 6.1
  - Page 35: Conclusion
  - Pages 36–37: Bibliography (23 GOST 7.0.5-2008 sources)
  - Pages 38–41: Appendix A — Full Assembly Listing `motorola_iir_dsp56824.asm` (up to `END`)
  - Page 42: Appendix B — Functional Schematic `ПГТУ.466225.001 Э2` (A3 Landscape, `22.10.2026`)
  - Page 43: Appendix C — Parts List `ПГТУ.466225.001 ПЭ2` (A4 Portrait, 30 rows with `VD1/VD3/W1/XP3`, `22.10.2026`)
- **Standalone Latest Drawings & Figures (`22.10.2026`)**:
  - `E:\STUDY_NEW_GEN\ЦОС\coursework\drawings\ПГТУ.466225.001_Э2.pdf`
  - `E:\STUDY_NEW_GEN\ЦОС\coursework\drawings\ПГТУ.466225.001_ПЭ2.pdf`
  - `E:\STUDY_NEW_GEN\ЦОС\pipeline\assets\fig_3_1_canonical.png`, `fig_4_1_large.png`, `fig_5_1_cropped.png`, `fig_5_2_clean.png`, `fig_5_3_clean.png`, `fig_5_5_clean.png`

---

## Requirements

### R1. 300 DPI Rasterization of All 43 Coursework Pages & Updated 22.10.2026 Drawings
- Replace all outdated (`02.10.2026`) PNGs in `output/dsp_assets/`.
- Rasterize all **43 pages** (`pz_page_01.png` .. `pz_page_43.png`) from `E:\STUDY_NEW_GEN\ЦОС\coursework\release_final\Пояснительная_записка_ЦОС_Иванов.pdf` (`22.10.2026`) and rasterize `drawing_e2.png` and `drawing_pe2.png` directly from `ПГТУ.466225.001_Э2.pdf` and `ПГТУ.466225.001_ПЭ2.pdf` (`22.10.2026`) at **300 DPI** (`zoom = 300.0 / 72.0` via PyMuPDF `fitz`), plus copy the `22.10.2026` `fig_3_1..5_5` assets.
- Map all 53 storyboard scenes in `src/dsp_defense_cycles.py` sequentially across pages `1..43` of the coursework (with sub-scene focus bounding boxes `[rx0, ry0, rx1, ry1]` per spoken concept cue).

### R2. Split-Screen Live Sync Architecture (Left 43-Page Zooming Inspector + Right Multi-Concept Process Animation)
- Redesign frame rendering (`1280x720`) into a balanced **Split-Screen Live Sync** layout above the kinetic subtitle bar (`y = 604..702`):
  - **Left Panel (`x = 24..584, y = 66..594`)**: renders the active 300 DPI coursework page (`pz_page_01..43`) or blueprint (`drawing_e2` / `drawing_pe2`), smoothly panning and zooming (`closed_form_spring`, `zoom = 1.0 -> 1.6..2.6`) from the full sheet onto the exact bounding box of the currently spoken paragraph, formula, table row, assembly block, or IC symbol, highlighted with a glowing cyan/amber focus frame and concise badge (`Стр. X/43 • <узел>`).
  - **Right Panel (`x = 596..1256, y = 66..594`)**: executes a **multi-concept scenario (3–5 visual cues per scene)** synchronized to the spoken word timestamps (`words[i].start_ms`):
    - **(a) Hardware / IC Node Cues** (`DSP56824`, `AD73322AR`, `IS61LV6416`, `AD8606AR`, `MAX706S`, `MC68HC908GP32`, `WH1602B`, `ZQ1/ZQ2`): renders an interactive pinout/circuit card of that specific IC and animates its live signals (6-bus Harvard transfers, 4-wire `SSI` frames `SCLK/SDFS`, 0-WS SRAM $19\text{ ns} < 25\text{ ns}$ timing diagram, Sallen-Key $25.03\text{ kHz}$ analog filtering, `/RESET` supervisor threshold $2.93\text{ V}$, SPI & HD44780 LCD updates).
    - **(b) Mathematical / Formula / Plot Cues** (ТЗ frequency mask, Table 2.1 comparison, reliability $\text{MTBF}=1.034\cdot 10^6\text{ h}$ & thermal $\Delta T=4.2\ ^\circ\text{C}$, bilinear transform, Direct Form II delay buffer, Table 5.1 Q15 halving & $L_\infty$ scaling $g_1..g_6$, Z-plane poles/zeros $|p_{\max}|=0.9878$, Bode/Phase/Group Delay, `float64 vs Q15`): animates step-by-step formula derivation with `[span]` term highlighting and live evolving plots/waveforms.
    - **(c) Firmware / Assembly Cues** (`ORG P:$001E`, Vector 15 `SSI_Rx_ISR`, 8-register LIFO stack, `DO #6` 23-instruction biquad loop, `MPY/MAC`, `ASL B / ASL A`, real-time cycle meter $114..150$ cycles vs $20.833\ \mu\text{s}$): animates line-by-line opcode stepping and live register/36-bit accumulator (`A2:A1:A0`) transitions.

### R3. Full Disk Re-Render of All MP4 Videos & Updated Interactive Workstation
- Actually re-render and overwrite the `.mp4` video files on disk in `output/`:
  - Section videos: `output/lesson_03_ru_dsp_cycle1_architecture/lesson_full_720p.mp4` .. `output/lesson_06_ru_dsp_cycle4_firmware_realtime/lesson_full_720p.mp4` (and all 6 chapter directories / per-scene `.mp4` files referenced by `dsp_defense_index.html`), plus the full master video `output/lesson_07_ru_dsp_defense_master/lesson_full_720p.mp4` using the cached Russian female voiceover (`voice_y0joebp3bwta` in `.tts_cache/`).
- Update `output/dsp_defense_index.html` and `dsp_defense_index.html` so the interactive workstation includes a **43-Page Coursework & ESKD Gallery / Lightbox** (`Стр. 1..43 ПЗ + Э2 + ПЭ2 + Рис. 3.1..5.5`) synchronized with playback timecodes.
- Maintain `0` literal Cyrillic characters (`[\u0400-\u04FF]`) and `0` personal/workspace path tokens across all `src/*.py` and `tests/*.py` (use `\u04...` Unicode escapes in Python strings where Russian UI text is needed).

---

## Acceptance Criteria

### Asset Freshness & 43-Page Coverage
- [ ] `output/dsp_assets/` contains all 43 rasterized pages (`pz_page_01.png` .. `pz_page_43.png`) from the `22.10.2026` PDF (`Пояснительная_записка_ЦОС_Иванов.pdf`) and fresh 300 DPI `drawing_e2.png` + `drawing_pe2.png` from the `22.10.2026` drawing PDFs (verified by image dimensions $\ge 2400\text{ px}$ on long edge and file timestamps/hashes).
- [ ] All 43 pages (`1..43`) are referenced across the 53 scenes in `DSP_DEFENSE_CYCLES`.

### Split-Screen Live Sync & Intra-Scene Visual Dynamics
- [ ] Every scene in `DSP_DEFENSE_CYCLES` defines `pz_page` (`1..43`) and 3–5 word-synchronized `concept_cues` (each specifying `start_ratio`/`end_ratio`, `focus_bbox` on the left coursework page, `concept_type`, `concept_target`, `formula_or_label`, and `animation_mode` on the right).
- [ ] Sampling rendered frames at 4 distinct timestamps ($t = 15\%, 40\%, 65\%, 90\%$) within any scene proves **both** the Left Panel (`x = 24..584`, zoomed coursework page + moving focus highlight) and the Right Panel (`x = 596..1256`, multi-concept process animation) exhibit significant pixel change ($\text{mean\_abs\_diff} > 4.0$ in both left and right halves — zero static frozen panels).

### Re-Rendered MP4 Files on Disk & Cleanliness Gate
- [ ] The `.mp4` files on disk (`output/lesson_03..07/lesson_full_720p.mp4` and scene `.mp4`s) are freshly generated during this run, non-empty, valid H.264+AAC streams, and frame extraction via `imageio_ffmpeg` from the actual `.mp4` on disk confirms the Split-Screen Live Sync layout is present in the video files themselves.
- [ ] All `pytest` suites pass (`100%` green) and `src/*.py` + `tests/*.py` contain `0` literal Cyrillic characters and `0` personal tokens.


## 2026-10-25T15:38:16Z

Transform the Motorola DSP56824 digital audio filter coursework video and interactive HTML workstation (`flow_video_testbench`) from a formal commission defense simulation into a pure, zero-fluff 47-scene engineering deep-dive (`1705 s` / `28:25`) designed for the author's complete technical mastery of every calculation, schematic node, MATLAB filter equation, and assembly routine.

Working directory: e:/ANTIGRAVITY/flow_video_testbench
Integrity mode: development

## Verification Resources
- Existing test suites: `tests/test_flow_m3_m5_verification.py` and `tests/test_flow_studio.py`
- Re-render pipeline: `scripts/re_render_defense_mp4s.py`
- Storyboard & workstation generator: `src/dsp_defense_cycles.py`
- Persistent TTS cache: `.tts_cache/` (40 unchanged technical scenes already cached with `voice_y0joebp3bwta`; 7 rewritten scenes to be synthesized and cached)

## Requirements

### R1. Remove Purely Bureaucratic & Duplicate Scenes (53 -> 47 Pure Engineering Scenes)
Remove the 6 purely administrative/formal/duplicate scenes from `DSP_DEFENSE_CYCLES` in `src/dsp_defense_cycles.py`:
- `cycle1_sc01` (Title page greeting to state examination commission & GOST page-count recitation)
- `cycle5_sc01` (Bureaucratic recitation of ESKD document code `ПГТУ.466225.001`)
- `cycle5_sc04` (Normocontrol pass recitation)
- `cycle5_sc08` (GOST stamp height `40 мм` / `15 мм` and table border clearance `29,97 мм` normocontrol recitation)
- `cycle6_sc02` (Redundant duplicate of `cycle2_sc10` MTBF & thermal calculation)
- `cycle6_sc05` (Recitation of 43 pages, Form 2a stamps, and handover to supervisor Dedov A. N.)

Update `DSP_SCENE_PZ_PAGES` and `DSP_SCENE_CONCEPT_CUES` accordingly so that all **47 retained scenes** (`7 + 10 + 10 + 9 + 5 + 6 = 47` scenes, total duration `1705 s` / `28:25`) map to substantive engineering pages of the Explanatory Note (`стр. 8..35, 38..43`) with zero references to title pages, table of contents (`стр. 4`), or bibliography (`стр. 36..37`).

### R2. Rewrite the 7 Remaining Scenes Containing Formal/Commission/Normocontrol Phrasing into Direct Engineering Explanations
Rewrite the titles, `narration_text`, `tts_narration_text`, `telemetry_badge`, `highlight_box`, `on_screen_bullets`, `pz_page`, and `concept_cues` of the 7 scenes that previously contained formal/commission/normocontrol phrasing:
1. `cycle5_sc05` (`стр. 42`, Drawing `Э2`): Replace `"В соответствии с замечанием нормоконтроля..."` with direct hardware engineering explanation of why pins 39/40 (`/LB`, `/UB`) of `IS61LV6416` (`DA3`) are tied to `DGND` for full 16-bit word access on `D0..D15` and how differential analog lines of `AD73322` (`DA2`) are isolated.
2. `cycle6_sc01` (`стр. 34`, `Таблица 6.1`): Remove the Word-formatting remark `"Третий столбец отцентрирован с запятой ноль, один"`, replacing it with how the 8 specification parameters of Variant 5 interact as a closed engineering budget.
3. `cycle6_sc03` (`стр. 27`, Section 5.3): Reframe from `"Отвечая на вопросы комиссии ГЭК..."` into **"Ключевой узел №1–2: Почему выбран эллиптический БИХ N=11 вместо КИХ N≈237 и как каноническая форма Direct Form II экономит 50% ОЗУ"**.
4. `cycle6_sc04` (`стр. 35`, Conclusion): Remove `"В заключение доклада... Доклад окончен, спасибо за внимание, готова ответить на вопросы комиссии!"`, reframing into **"Сквозная архитектура тракта: как связаны аналоговая часть, математика Кауэра N=11 и конвейер DSP56824"**.
5. `cycle6_sc06` (re-map `pz_page` from `4` to `28`, `Таблица 5.1` & `Рис. 5.2`): Reframe from `"Третий и четвёртый вопросы..."` into **"Ключевой узел №3–4: Зачем коэффициенты поделены пополам (Q15 + сдвиг ASL) и как норма L_infinity защищает от переполнения"**.
6. `cycle6_sc07` (re-map `pz_page` from `36` to `33`, Section 6.4 Real-Time Balance): Reframe from `"Пятый и шестой вопросы..."` into **"Ключевой узел №5–6: Доказательство жёсткого реального времени (3,75 мкс из 20,833 мкс) и работа памяти IS61LV6416 без тактов ожидания (0 Wait States)"**.
7. `cycle6_sc08` (re-map `pz_page` from `37` to `22`, Section 3.3 `SSI` Interface): Reframe from `"Седьмой и восьмой вопросы..."` into **"Ключевой узел №7–8: Роль аналоговых фильтров Саллена–Кея (25,03 кГц) и тактовая синхронизация шины SSI от кодека AD73322 в режиме Master"**.

### R3. Refactor the Interactive HTML Workstation (`dsp_defense_index.html`) for Personal Engineering Study
Update `generate_dsp_defense_player_html` in `src/dsp_defense_cycles.py` (and regenerate both `output/dsp_defense_index.html` and `dsp_defense_index.html`):
- Replace all commission/defense headings (`Пульт защиты курсовой работы перед комиссией ГЭК`, `Шпаргалка ответов на вопросы комиссии ГЭК`, `Ораторский телесуфлёр докладчика`) with personal engineering study headings:
  - Header: **«Интерактивный инженерный разбор курсовой работы: Цифровой аудиофильтр на Motorola DSP56824 (Вариант №5)»**
  - Mode 1: **«🔊 Режим 1: Видеоразбор со звуком (voice_y0joebp3bwta)»**
  - Mode 2: **«🧭 Режим 2: Пошаговый инженерный разбор (Конспект + Схемы 300 DPI + Ключевые узлы)»**
  - Bottom cards: **«⚡ Ключевые инженерные решения и "почему устроено именно так" (8 базовых узлов проекта)»**

### R4. Synthesize Audio for the 7 Rewritten Scenes, Re-Render MP4s, and Update Tests
- Synthesize Russian female studio voiceover (`voice_y0joebp3bwta`) for the 7 rewritten scenes into `.tts_cache/` while reusing the 40 already-cached studio WAVs for the 40 unchanged technical scenes.
- Re-render all 47 scene MP4s (reusing unchanged scene MP4s where scene number/audio match, and re-rendering modified scenes/numbering), re-mux all 6 chapter `lesson_full_720p.mp4` files, and assemble the full 47-scene Master Engineering Deep-Dive Video (`output/lesson_07_ru_dsp_defense_master/lesson_full_720p.mp4`, `1705 s` / `28:25`).
- Update `tests/test_flow_m3_m5_verification.py` and `tests/test_flow_studio.py` to verify the 47-scene engineering deep-dive invariants and zero bureaucratic/commission tokens.

## Acceptance Criteria

### Bureaucratic & Commission Cleanliness
- [ ] Zero occurrences of `комисс`, `ГЭК`, `Уважаемые члены`, `Доклад окончен`, `спасибо за внимание`, `нормоконтрол`, `штамп`, `запятой ноль` across all 47 scene titles, `narration_text`, `tts_narration_text`, `on_screen_bullets`, and `dsp_defense_index.html`.
- [ ] Zero scenes mapped to non-technical pages (`pz_page` not in `{1, 3, 4, 6, 7, 36, 37}`).

### Media & Test Suite Verification
- [ ] All 47 scenes have valid studio WAVs (`> 200 KB`) in `.tts_cache/` matching their exact SHA-256 key (`v3|ru|voice_y0joebp3bwta|<formatted>`).
- [ ] Master video `output/lesson_07_ru_dsp_defense_master/lesson_full_720p.mp4` has duration `1705.0 ± 1.0 s` (`28:25`) and size `> 550 MB`, matching the HTML chapter timecodes (`00:00`, `04:13`, `10:14`, `16:16`, `21:37`, `24:49`) to the second.
- [ ] `python -m pytest tests/test_flow_m3_m5_verification.py tests/test_flow_studio.py -v` passes 100% with zero `[\u0400-\u04FF]` in `src/*.py` and `tests/*.py`.


## 2026-10-26T08:44:42Z

Build a comprehensive interactive HTML coursework intensive ("Интенсив по курсовой работе: Цифровой аудиофильтр на Motorola DSP56824, Вариант №5") with a synchronized split-screen layout: all 43 coursework pages (`стр. 1..43`) and GOST blueprints (`Э2`, `ПЭ2`) on the left pane, and a deep, element-by-element engineering walkthrough with live interactive simulations, embedded video segments, and self-check flashcards on the right pane, plus a hybrid 1-click text and image-lasso selection bridge for sending questions directly into the Antigravity chat.

Working directory: `e:\ANTIGRAVITY\flow_video_testbench`
Integrity mode: `development`

## Verification Resources

- Existing coursework page renders (`43` pages + blueprints + MATLAB figures): `output/dsp_assets/pz_page_01.png` .. `pz_page_43.png`, `drawing_e2.png`, `drawing_pe2.png`, `fig_3_1.png`, `fig_4_1.png`, `fig_5_1.png`, `fig_5_2.png`, `fig_5_3.png`, `fig_5_5.png` (and mirrored in `output/course_frames/`).
- Existing 47-scene storyboard, page mappings, bounding boxes, equations, and 8 Q&A cards: `src/dsp_defense_cycles.py`.
- Existing rendered 720p HD scene MP4s (`scene_01.mp4` ..) across `output/lesson_03_ru_dsp_cycle1_architecture` .. `output/lesson_08_ru_dsp_cycle6_conclusion_faq` and master video `output/lesson_07_ru_dsp_defense_master/lesson_full_720p.mp4`.
- Existing FastAPI router & test suite: `src/flow_api.py`, `tests/test_flow_studio.py`, `tests/test_flow_m3_m5_verification.py`.

## Requirements

### R1. Bidirectional Split-Screen Synchronization (Left: Coursework Sheets & Blueprints ↔ Right: Engineering Intensive)
Create a standalone, responsive split-screen HTML application (`dsp_interactive_course.html` at the workspace root and `output/dsp_interactive_course.html`) where:
- **Left Pane (Coursework Sheet & Blueprint Viewer)**: Displays the high-resolution coursework pages (`стр. 1..43`, `pz_page_01.png..pz_page_43.png`) and GOST drawings (`Э2`, `ПЭ2`), with page selector/filmstrip, zoom/pan controls, and interactive highlighted bounding-box overlays (`pdf_bbox`) corresponding to the formulas, tables, schematics, and code blocks on that sheet.
- **Right Pane (Engineering Intensive)**: Displays the complete engineering breakdown of everything on the currently active sheet/topic.
- **Bidirectional Binding**:
  1. Navigating to any page (`стр. 1..43`, `Э2`, `ПЭ2`) or clicking a highlighted block on the left pane automatically scrolls/switches the right pane to the corresponding intensive lesson(s) and block explanation.
  2. Navigating by module/topic (`Модули 1..6`, `Темы #1..#47`) or clicking any formula/paragraph/card on the right pane automatically switches the left pane to the exact coursework page (`pz_page`) and highlights/zooms the target bounding box (`pdf_bbox`).
  3. Even structural pages (`стр. 1..7, 36..37`) must have concise contextual explanations in the intensive so that all 43 pages + `Э2` + `ПЭ2` have 100% coverage without dead pages.

### R2. Maximum-Depth Intensive Content, Live Interactive Simulations & Embedded Media (Right Pane)
For every page and topic, the right pane must provide a complete, self-sufficient learning experience ("без воды", pure engineering substance):
- **Block-by-Block Page Walkthrough**: Detailed explanation of every formula, parameter, circuit node, register, assembly instruction, and table on the active sheet, with physical meaning and numerical derivations for Variant 5 (`DSP56824` at `40 МГц`, `AD73322AR` at `Fs = 48 кГц`, elliptic Cauer IIR `N = 11` with `6` Direct Form II biquads, `IS61LV6416` `10 нс` `0 WS`, `AD8606AR` Sallen-Key LPF `25.03 кГц`, `MAX706S`, `MTBF = 1.034×10⁶ ч`).
- **Interactive HTML5 Canvas Simulations** (contextualized to the relevant pages and accessible from a dedicated Simulation Drawer/Tabs):
  1. **Cauer IIR `N=11` Filter & `Q15` Quantization Lab (`стр. 10, 25..30`)**: Live magnitude response $|H(e^{j\omega})|$ (0..24 kHz) with passband ripple zoom (`0..10 кГц`, $\Delta A \le 0.1\text{ дБ}$) and stopband mask ($\ge 11\text{ кГц}$, $\ge 80\text{ дБ}$), interactive $z$-plane pole-zero plot ($|p_{\max}| = 0.9878$), comparison toggle (`Cauer N=11` vs `Chebyshev N=25` vs `Butterworth N=109` vs `FIR N=237`), and live bit-depth / `/2` (`ASL A`) scaling slider.
  2. **DSP56824 Real-Time Oscilloscope & `SSI_Rx_ISR` Pipeline Stepper (`стр. 24, 31..33, 38..41`)**: Live dual-trace time/FFT oscilloscope ($x(n)$ vs filtered $y(n)$) + cycle-accurate stepper for the 150-cycle (`3.75 мкс`, `18%` CPU load) `DO #6` biquad loop, 36-bit accumulator `A2:A1:A0`, `MAC`, `ASL A`, and `RND A`.
  3. **Analog Sallen-Key AAF/SMF, `AD73322` $\Sigma\Delta$ & `IS61LV6416` 0-WS Timing Simulator (`стр. 12..23, 42, 43`)**: Interactive anti-aliasing frequency sweep, `SSI` frame sync timing diagram, and `0 Wait States` (`10 нс < 25 нс`) bus timing diagram.
- **Embedded Video & Self-Check**: Synchronized 720p video player for the active topic (`scene_XX.mp4` / master video timecode) and interactive self-check flashcards with progress tracking (`localStorage`).

### R3. Hybrid 1-Click Selection & Annotation Bridge to Antigravity Chat (Text Highlight + Image Lasso)
Provide built-in annotation tools so the user can mark anything unclear on either pane and send it to the chat in one click:
- **Text Selection Tool**: Selecting any text, formula, or code in the right pane pops up a floating action bar (`"❓ Непонятно — отправить в чат"` + optional quick note input).
- **Image Rectangular/Lasso Selection Tool (Left Pane & Diagrams)**: A toggleable `"✂️ Выделить область на листе"` mode on the coursework page/blueprint viewer allowing the user to drag a selection box over any part of a formula, schematic (`Э2`), table (`ПЭ2`), or plot, rendering a cropped PNG data URL of that exact region.
- **Hybrid 1-Click Dispatch (`"🚀 Отправить в чат Antigravity"`)**:
  1. **Clipboard**: Immediately copies a structured, ready-to-paste Markdown prompt into the system clipboard (containing page number `стр. X`, topic ID, coordinates/bbox, quoted text or cropped image file path, and the user's question/note) so the user can press `Ctrl+V` in chat.
  2. **Local Disk / FastAPI Bridge**: Simultaneously POSTs the annotation payload (including the base64 cropped PNG image when an image region is selected) to a FastAPI endpoint (`POST /api/flow/intensive-question` in `src/flow_api.py`, with automatic fallback saving `.json` + `.png` via File System Access / download into `output/user_questions/latest_question.json` and `output/user_questions/latest_crop.png`) so the agent in chat can immediately read the exact cropped image and metadata on disk.

### R4. ISO 9001:2015 Agile V Quality Gate & Sync (`/iso9000-agentops`)
- Maintain strict verification hygiene: add comprehensive programmatic tests in `tests/test_flow_studio.py` (or a dedicated test module) verifying 100% 43-page + `Э2`/`ПЭ2` mapping coverage, bidirectional sync data structures, interactive simulation engines, and the `/api/flow/intensive-question` bridge endpoint.
- Sync updated artifacts via `python scripts/sync_with_gemini_local_ui.py --push` and report milestone status via `python scripts/report_to_root_session.py`.

## Acceptance Criteria

### Bidirectional Page ↔ Intensive Coverage
- [ ] All 43 coursework pages (`pz_page_01.png` .. `pz_page_43.png`) plus `drawing_e2.png` (`Э2`) and `drawing_pe2.png` (`ПЭ2`) are selectable in the left pane and mapped to structured explanations in the right pane (0 unmapped/empty pages).
- [ ] All 47 engineering topics across the 6 modules are selectable in the right pane and automatically navigate the left pane to the corresponding `pz_page` and highlight its `pdf_bbox`.

### Interactive Simulations & Media
- [ ] All 3 interactive HTML5 Canvas simulations (Cauer `N=11` / `Q15` $z$-plane & frequency response, `DSP56824` `DO #6` pipeline & oscilloscope, and Sallen-Key / `SSI` / `0-WS` hardware timing) render dynamically and respond to user controls.
- [ ] Each topic card includes embedded video playback (`scene_XX.mp4`), high-resolution schematic/plot views, and self-check flashcards.

### 1-Click Text & Image-Lasso Question Bridge
- [ ] Dragging a selection box on the left pane crops the selected region of the coursework page/blueprint onto an offscreen canvas and generates a valid PNG preview.
- [ ] Clicking `"Отправить в чат"` copies a structured Markdown reference to the clipboard AND persists/POSTs the question metadata + cropped PNG via `POST /api/flow/intensive-question` into `output/user_questions/latest_question.json` and `output/user_questions/latest_crop.png`.

### Programmatic Verification (`/iso9000-agentops`)
- [ ] `pytest` suite passes 100% (`0` failures), including programmatic checks of `dsp_interactive_course.html`, all 43+2 page mappings, simulation scripts, and FastAPI question-bridge round-trip tests.

## 2026-10-27T10:24:08Z

Adapt the four highest-value architectural mechanisms from the top open-source educational video lecture repositories (`showlab/Paper2Video`, `THU-MAIC/OpenMAIC`, `jeertmans/manim-slides`, `ManimCommunity/manim-voiceover`, `motion-canvas/motion-canvas`, `remotion-dev/remotion`, `DangJin/pdf2video`, `sekika/slidemovie`) into the `flow_video_testbench` educational video studio — spanning both the Python MP4 generation pipeline (`src/flow_bridge.py`, `flow_testbench_runner.py`, `src/flow_api.py`) and the synchronized split-screen coursework workstation (`dsp_interactive_course.html` and `output/dsp_interactive_course.html`).

Working directory: e:/ANTIGRAVITY/flow_video_testbench
Integrity mode: development

## Reference Repositories & Selected Adaptations

1. `ManimCommunity/manim-voiceover` (322 stars) + `motion-canvas/motion-canvas` (19.5k stars) -> Bookmark-Driven Audio-Visual Sync (`<bookmark mark="..."/>` & Named Time Events).
2. `showlab/Paper2Video` (2.39k stars) + `DangJin/pdf2video` (393 stars) -> Cursor Grounding (animated laser pointer) & Smooth Auto-Zoom Camera (`1.0x -> 1.8x` Cubic-Bezier pan/zoom into active PDF `pz_bbox` regions) + typing-effect glassmorphic callout HUDs.
3. `THU-MAIC/OpenMAIC` (41.6k stars) + `jeertmans/manim-slides` (970 stars) -> Structured Classroom Action Script (`ShowSheet`, `ZoomBBox`, `LaserPoint`, `DrawWhiteboard`, `RunSimPreset`, `QuizCheckpoint`) & Step-by-Step Slide State Machine (`Prev Step / Play-Pause / Loop Cue / Next Step`).
4. `remotion-dev/remotion` (68.0k stars) + `sekika/slidemovie` -> Deterministic Frame-Pure Rendering & Incremental SHA-256 Scene Cache (`.scene_cache/`).

## Requirements

### R1. Bookmark-Driven Audio-Visual Sync & Time Events (`src/flow_bridge.py`, `flow_testbench_runner.py`)
Implement a bookmark & time-event synchronization engine that parses inline `<bookmark mark="id"/>` markers in narration scripts, strips them cleanly before TTS synthesis and subtitle rendering (so zero raw `<bookmark>` tags ever appear in `.vtt`/`.srt` or spoken audio), and resolves each bookmark to an exact millisecond and frame offset `[0, total_frames]` aligned with the acoustic syllable/word timeline. Allow `concept_cues` and `pz_bbox` focus transitions to bind directly to bookmark IDs or relative time fractions.

### R2. Cursor Grounding & Auto-Zoom Camera on Coursework Sheets (`flow_testbench_runner.py`, `dsp_interactive_course.html`)
Implement a `CursorGroundingEngine` and smooth camera pan-and-zoom transform (`1.0x` full-page view smoothly easing via Cubic-Bezier to `1.4x-1.85x` centered on the active `pz_bbox` region, with safe boundary clamping inside `[0, W] x [0, H]`) in both:
- the left PDF panel of the 720p split-screen MP4 compositor (`flow_testbench_runner.py`), including a rendered laser-pointer dot/trail and a typing-effect callout bar at the bottom of the sheet; and
- the left interactive sheet viewer of `dsp_interactive_course.html` (and `output/dsp_interactive_course.html`), with an interactive toggle (`🔍 Авто-Зум + Лазерная указка Paper2Video`) that smoothly pans/zooms the coursework sheet (`pz_page_01..43.png`, `drawing_e2.png`, `drawing_pe2.png`) and animates a laser pointer + floating formula callout card over the active bounding box.

### R3. OpenMAIC Classroom Action Engine & Manim-Slides Step Controller (`dsp_interactive_course.html`, `src/flow_api.py`)
Upgrade `dsp_interactive_course.html` (and sync to `output/dsp_interactive_course.html`) with:
- A `manim-slides` Step-by-Step Deck Controller bar (`⏮ Пред. шаг`, `⏯ Старт/Пауза авто-разбора`, `🔁 Зациклить текущий блок`, `⏭ След. шаг`, `🔍 Авто-Зум камеры`, `✏️ Доска/Аннотации`) that steps through every coursework page's `concept_cues` and bounding boxes sequentially;
- An `OpenMAIC` Action Stream & Socratic Checkpoint widget per sheet: structured action steps (`ShowSheet` -> `ZoomBBox` -> `LaserPoint` -> `RunSimPreset` -> `QuizCheckpoint`) where clicking any action step immediately focuses the PDF region, sets the inline simulator (`#inline-sim-canvas`) parameters to that step's preset, and provides a 1-click interactive self-check question with instant answer verification for defense preparation;
- A FastAPI endpoint `GET /api/flow/lecture-actions/{page_num}` in `src/flow_api.py` returning the structured `OpenMAIC` action script and `manim-slides` segment metadata for any sheet `1..45`.

### R4. Incremental Content-Addressable Scene Cache (`flow_testbench_runner.py`, `src/flow_bridge.py`)
Implement a content-addressable scene cache (`.scene_cache/`) modeled on `remotion` and `slidemovie` that computes a deterministic SHA-256 digest of `(scene_id, narration_text, pz_page, pz_bbox, concept_cues, visual_type, tts_wav_sha256, renderer_version)`. When a scene's digest matches an existing verified segment in `.scene_cache/`, reuse the cached segment without re-running frame synthesis; expose cache hit/miss telemetry in the build report.

## Verification Resources

- Existing test suites that MUST remain 100% green:
  - `python -m pytest tests/test_flow_studio.py -v`
  - `python -m pytest tests/test_interactive_course.py -v`
- Existing codebase files:
  - `e:/ANTIGRAVITY/flow_video_testbench/src/flow_bridge.py`
  - `e:/ANTIGRAVITY/flow_video_testbench/flow_testbench_runner.py`
  - `e:/ANTIGRAVITY/flow_video_testbench/src/flow_api.py`
  - `e:/ANTIGRAVITY/flow_video_testbench/dsp_interactive_course.html`
- Note: Keep `src/flow_bridge.py`, `src/flow_api.py`, and `flow_testbench_runner.py` compliant with `test_gate5_req004_zero_cyrillic_and_zero_personal_tokens_in_code` (if `test_interactive_course.py` checks `src/` or specific files for English-only source, verify how `test_gate5_req004_zero_cyrillic_and_zero_personal_tokens_in_code` works before editing).

## Acceptance Criteria

### 1. Bookmark & Time-Event Synchronization (R1)
- [ ] `parse_voiceover_bookmarks(text)` extracts ordered bookmark IDs and word-index ratios in `[0.0, 1.0]` while returning clean narration text with zero `<bookmark.../>` artifacts.
- [ ] `resolve_bookmark_timestamps(bookmarks, total_duration_sec, acoustic_segments)` maps every bookmark monotonically (`0.0 <= t_1 <= t_2 <= ... <= total_duration_sec`).

### 2. Cursor Grounding & Auto-Zoom Camera (R2)
- [ ] `CursorGroundingEngine` computes smooth Cubic-Bezier `(x, y, zoom)` camera and laser-pointer states for any frame `f` in `[0, total_frames]`, strictly clamped within source image dimensions.
- [ ] Rendered split-screen frames with Auto-Zoom + Cursor Grounding exhibit non-zero intra-scene pixel variance on the left PDF panel as the camera zooms and pans across `pz_bbox` regions.
- [ ] `dsp_interactive_course.html` includes working Auto-Zoom transform (`#sheet-zoom-container` / CSS transform), animated laser pointer overlay (`#paper2video-laser`), and typing callout HUD (`#pdf2video-callout`).

### 3. OpenMAIC Action Script & Manim-Slides Step Controller (R3)
- [ ] `dsp_interactive_course.html` and `output/dsp_interactive_course.html` are byte-identical and contain the `manim-slides` step controller (`prevSlideStep()`, `toggleSlideLoop()`, `nextSlideStep()`, `toggleAutoZoomCamera()`) and `OpenMAIC` interactive Socratic checkpoint cards for all 45 sheets.
- [ ] `GET /api/flow/lecture-actions/{page_num}` in `src/flow_api.py` returns HTTP 200 with valid JSON action sequences (`ShowSheet`, `ZoomBBox`, `LaserPoint`, `RunSimPreset`, `QuizCheckpoint`) for sheets `1..45`.

### 4. Incremental Scene Cache & Full Regression Suite (R4)
- [ ] `SceneRenderCache` computes deterministic SHA-256 keys, stores/retrieves MP4 scene segments in `.scene_cache/`, and achieves a cache hit on second invocation with identical inputs.
- [ ] Dedicated test suite `tests/test_github_repo_adaptations.py` (covering R1, R2, R3, R4) and all existing suites (`tests/test_flow_studio.py`, `tests/test_interactive_course.py`) pass 100% (`0 failed`), and all source files pass the English-only source / zero-secret gate.
