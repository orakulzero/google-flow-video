# -*- coding: utf-8 -*-
"""
scripts/intensive_template_part1.py
HTML/CSS layout and synchronization engine for the Split-Screen Coursework Intensive
(Left: 43 Coursework Pages + E2/PE2 Blueprints with BBox & Image Lasso;
 Right: Intensive Walkthrough, Embedded Video/Diagrams, Floating Text Selection & 1-Click Chat Bridge).
"""

HTML_HEAD_AND_BODY = r"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Интенсив по курсовой работе: Цифровой аудиофильтр на Motorola DSP56824 (Вариант №5)</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    :root {
      --bg-main: #0b1120;
      --bg-panel: #111827;
      --bg-card: #1e293b;
      --border-col: #334155;
      --accent: #06b6d4;
      --accent-amber: #f59e0b;
    }
    body {
      background: var(--bg-main);
      color: #f1f5f9;
      font-family: 'Inter', system-ui, -apple-system, sans-serif;
      overflow: hidden;
      height: 100vh;
    }
    ::-webkit-scrollbar { width: 7px; height: 7px; }
    ::-webkit-scrollbar-track { background: #0f172a; }
    ::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #475569; }
    .bbox-rect {
      position: absolute;
      border: 2px solid rgba(6, 182, 212, 0.85);
      background: rgba(6, 182, 212, 0.14);
      border-radius: 4px;
      cursor: pointer;
      transition: all 0.18s ease;
    }
    .bbox-rect:hover, .bbox-rect.active-bbox {
      border-color: #f59e0b;
      background: rgba(245, 158, 11, 0.24);
      box-shadow: 0 0 14px rgba(245, 158, 11, 0.55);
      z-index: 20;
    }
    .lasso-selection-box {
      position: absolute;
      border: 2px dashed #ec4899;
      background: rgba(236, 72, 153, 0.18);
      pointer-events: none;
      z-index: 35;
    }
    #sheet-zoom-container {
      transition: transform 0.55s cubic-bezier(0.25, 0.1, 0.25, 1.0);
      transform-origin: center center;
      will-change: transform;
    }
    #paper2video-laser {
      position: absolute;
      width: 18px;
      height: 18px;
      margin-left: -9px;
      margin-top: -9px;
      border-radius: 9999px;
      background: radial-gradient(circle, #ffffff 15%, #ef4444 55%, rgba(239, 68, 68, 0) 100%);
      box-shadow: 0 0 16px 5px rgba(239, 68, 68, 0.85), 0 0 28px 10px rgba(245, 158, 11, 0.55);
      pointer-events: none;
      z-index: 28;
      transition: left 0.42s cubic-bezier(0.22, 1, 0.36, 1), top 0.42s cubic-bezier(0.22, 1, 0.36, 1);
    }
  </style>
</head>
<body class="flex flex-col h-screen select-text">

  <!-- TOP HEADER BAR -->
  <header class="h-14 bg-slate-900 border-b border-slate-700 px-4 flex items-center justify-between shrink-0 z-30">
    <div class="flex items-center gap-3">
      <span class="px-2.5 py-1 text-xs font-extrabold rounded bg-cyan-500 text-slate-950 tracking-wide">ПГТУ.466225.001 ПЗ • ВАРИАНТ №5</span>
      <div>
        <h1 class="text-sm font-bold text-white leading-tight">Интенсив по курсовой работе: Цифровой аудиофильтр на Motorola DSP56824 (40 МГц, БИХ Кауэра N=11)</h1>
        <p class="text-[11px] text-slate-400">Слева: 43 листа ПЗ + чертежи Э2/ПЭ2 с выделением областей • Справа: полный разбор, 3 живые симуляции и отправка вопросов в чат в 1 клик</p>
      </div>
    </div>

    <div class="flex items-center gap-2">
      <!-- Bidirectional Sync Indicator -->
      <span id="sync-status-pill" class="px-2.5 py-1 text-xs font-semibold rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
        🔗 Стр. ПЗ ↔ Интенсив синхронизированы
      </span>
      <span id="learned-progress-badge" class="px-2.5 py-1 text-xs font-bold rounded bg-slate-800 text-cyan-300 border border-slate-700">
        Изучено: 0 / 47 тем
      </span>
      <button onclick="openQuestionModalWithCurrentContext()" class="px-3 py-1.5 text-xs font-bold rounded-lg bg-pink-600 hover:bg-pink-500 text-white shadow transition flex items-center gap-1.5">
        <span>❓ Задать вопрос по листу в чат</span>
      </button>
    </div>
  </header>

  <!-- MAIN SPLIT-SCREEN WORKSPACE -->
  <main class="flex-1 grid grid-cols-12 overflow-hidden">

    <!-- =================================================================== -->
    <!-- LEFT PANE (5 cols): COURSEWORK SHEETS (1..43) + BLUEPRINTS (E2, PE2) -->
    <!-- =================================================================== -->
    <section id="left-pane" class="col-span-5 bg-slate-950 border-r border-slate-700 flex flex-col h-full overflow-hidden">
      <!-- Sheet Toolbar -->
      <div class="p-2.5 bg-slate-900/90 border-b border-slate-800 flex flex-wrap items-center justify-between gap-2 shrink-0">
        <div class="flex items-center gap-1.5">
          <button onclick="stepSheet(-1)" title="Предыдущий лист ПЗ" class="px-2 py-1 text-xs font-bold rounded bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700">◀</button>
          <select id="sheet-select" onchange="selectSheetByIndex(parseInt(this.value, 10))" class="px-2.5 py-1 text-xs font-semibold rounded bg-slate-800 text-white border border-slate-600 focus:outline-none max-w-[230px]"></select>
          <button onclick="stepSheet(1)" title="Следующий лист ПЗ" class="px-2 py-1 text-xs font-bold rounded bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700">▶</button>
        </div>

        <div class="flex items-center gap-1.5">
          <button onclick="adjustZoom(-0.2)" class="px-2 py-1 text-xs font-bold rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700" title="Уменьшить">−</button>
          <span id="zoom-label" class="text-xs font-mono text-slate-300 w-12 text-center">100%</span>
          <button onclick="adjustZoom(0.2)" class="px-2 py-1 text-xs font-bold rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700" title="Увеличить">+</button>
          <button onclick="resetZoom()" class="px-2 py-1 text-xs font-semibold rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700" title="По ширине">Сброс</button>
          <button id="btn-autozoom-laser" onclick="toggleAutoZoomCamera()" class="px-2.5 py-1 text-xs font-bold rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 hover:bg-amber-500 hover:text-slate-950 transition" title="Авто-Зум + Лазерная указка Paper2Video">
            🔍 Авто-Зум + Лазерная указка Paper2Video
          </button>
          <button id="btn-toggle-lasso" onclick="toggleLassoMode()" class="px-2.5 py-1 text-xs font-bold rounded bg-pink-600/20 text-pink-300 border border-pink-500/40 hover:bg-pink-600 hover:text-white transition">
            ✂️ Выделить участок
          </button>
        </div>
      </div>

      <!-- manim-slides Step-by-Step Deck Controller Bar -->
      <div id="manim-slides-controller" class="px-2.5 py-1.5 bg-slate-900 border-b border-slate-800 flex flex-wrap items-center justify-between gap-1.5 shrink-0">
        <div class="flex flex-wrap items-center gap-1">
          <button onclick="prevSlideStep()" class="px-2 py-1 text-[11px] font-bold rounded bg-slate-800 hover:bg-cyan-500 hover:text-slate-950 text-slate-200 border border-slate-700 transition">⏮ Пред. шаг</button>
          <button id="btn-slide-play" onclick="toggleSlidePlayPause()" class="px-2.5 py-1 text-[11px] font-bold rounded bg-cyan-500/20 hover:bg-cyan-500 hover:text-slate-950 text-cyan-300 border border-cyan-500/40 transition">⏯ Старт/Пауза авто-разбора</button>
          <button id="btn-slide-loop" onclick="toggleSlideLoop()" class="px-2 py-1 text-[11px] font-semibold rounded bg-slate-800 hover:bg-amber-500 hover:text-slate-950 text-slate-300 border border-slate-700 transition">🔁 Зациклить текущий блок</button>
          <button onclick="nextSlideStep()" class="px-2 py-1 text-[11px] font-bold rounded bg-slate-800 hover:bg-cyan-500 hover:text-slate-950 text-slate-200 border border-slate-700 transition">⏭ След. шаг</button>
          <button id="btn-slide-autozoom" onclick="toggleAutoZoomCamera()" class="px-2 py-1 text-[11px] font-semibold rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 transition">🔍 Авто-Зум камеры</button>
          <button id="btn-slide-whiteboard" onclick="toggleWhiteboardLayer()" class="px-2 py-1 text-[11px] font-semibold rounded bg-slate-800 hover:bg-emerald-500 hover:text-slate-950 text-slate-300 border border-slate-700 transition">✏️ Доска/Аннотации</button>
        </div>
        <span id="manim-slide-step-indicator" class="text-[11px] font-mono text-cyan-300">Шаг 1 / 5 (manim-slides)</span>
      </div>

      <!-- Lasso / Sheet Helper Banner -->
      <div id="lasso-hint-bar" class="px-3 py-1 bg-slate-900 border-b border-slate-800 flex items-center justify-between text-[11px] text-slate-400 shrink-0">
        <span id="left-sheet-caption">Лист ПЗ • кликни по подсвеченному блоку или включи «✂️ Выделить участок» для отправки скриншота в чат</span>
        <span id="sheet-topics-count-badge" class="text-cyan-400 font-semibold"></span>
      </div>

      <!-- Sheet Viewport with Image, Clickable BBoxes, Paper2Video Laser & Rectangular Lasso -->
      <div id="sheet-viewport" class="flex-1 overflow-auto relative flex justify-center items-start p-3 bg-slate-950 select-none">
        <div id="sheet-zoom-container" class="w-full flex justify-center items-start">
          <div id="sheet-stage" class="relative inline-block shadow-2xl border border-slate-700 bg-white origin-top transition-transform duration-150" style="width: 100%;">
            <img id="sheet-img" src="" alt="Лист курсовой работы" class="w-full h-auto block select-none pointer-events-none" />
            <!-- Interactive BBox Overlays -->
            <div id="bbox-overlay-layer" class="absolute inset-0"></div>
            <!-- Paper2Video Grounded Laser Pointer -->
            <div id="paper2video-laser" style="left: 50%; top: 30%;"></div>
            <!-- OpenMAIC Interactive Whiteboard Canvas Layer -->
            <canvas id="whiteboard-canvas" width="900" height="1270" class="absolute inset-0 w-full h-full hidden cursor-pen z-25"></canvas>
            <!-- Active Lasso Selection Layer -->
            <div id="lasso-drag-layer" class="absolute inset-0 hidden cursor-crosshair z-30">
              <div id="lasso-box" class="lasso-selection-box hidden"></div>
            </div>
          </div>
        </div>
        <!-- pdf2video Glassmorphic Typing Callout HUD -->
        <div id="pdf2video-callout" class="fixed bottom-14 left-4 max-w-[38%] px-3 py-1.5 rounded-lg bg-slate-900/90 backdrop-blur-md border border-amber-400/50 text-xs font-mono text-amber-300 shadow-xl z-30 pointer-events-none">
          🎯 Paper2Video Focus: Выберите блок или шаг разбора...
        </div>
      </div>

      <!-- Bottom Quick-Jump Filmstrip (1..43 + E2 + PE2) -->
      <div class="p-2 bg-slate-900 border-t border-slate-800 shrink-0">
        <div class="flex items-center gap-1 overflow-x-auto pb-1" id="sheet-filmstrip"></div>
      </div>
    </section>

    <!-- =================================================================== -->
    <!-- RIGHT PANE (7 cols): INTENSIVE WALKTHROUGH, SIMULATIONS & TOOLS     -->
    <!-- =================================================================== -->
    <section id="right-pane" class="col-span-7 bg-slate-900 flex flex-col h-full overflow-hidden">

      <!-- Right Pane Navigation Tabs -->
      <div class="p-2.5 bg-slate-900 border-b border-slate-800 flex flex-wrap items-center justify-between gap-2 shrink-0">
        <div class="flex flex-wrap items-center gap-1">
          <button id="rtab-page" onclick="switchRightTab('page')" class="px-3 py-1.5 text-xs font-bold rounded-lg bg-cyan-500 text-slate-950 transition">
            📄 Разбор активного листа
          </button>
          <button id="rtab-modules" onclick="switchRightTab('modules')" class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 text-slate-200 hover:bg-slate-700 transition">
            📘 Все 47 тем (6 модулей)
          </button>
          <button id="rtab-sim1" onclick="switchRightTab('sim1')" class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 text-slate-200 hover:bg-slate-700 transition">
            📈 Симулятор 1: БИХ N=11 & Q15
          </button>
          <button id="rtab-sim2" onclick="switchRightTab('sim2')" class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 text-slate-200 hover:bg-slate-700 transition">
            🌊 Симулятор 2: Конвейер DSP & Осциллограф
          </button>
          <button id="rtab-sim3" onclick="switchRightTab('sim3')" class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 text-slate-200 hover:bg-slate-700 transition">
            🔌 Симулятор 3: ФНЧ Саллена–Кея & 0-WS
          </button>
          <button id="rtab-qa" onclick="switchRightTab('qa')" class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 text-slate-200 hover:bg-slate-700 transition">
            ⚡ 8 ключевых узлов
          </button>
        </div>
      </div>

      <!-- TAB 1: ACTIVE SHEET WALKTHROUGH (Explains everything on the currently selected Left-Pane sheet) -->
      <div id="rview-page" class="flex-1 overflow-y-auto p-4 space-y-4">
        <div id="page-intensive-header" class="bg-slate-800/90 border border-slate-700 rounded-xl p-4"></div>
        <!-- OpenMAIC Classroom Action Stream & Socratic Checkpoint Widget -->
        <div id="openmaic-classroom-widget" class="bg-slate-800/95 border border-amber-500/40 rounded-xl p-4 space-y-3">
          <div class="flex flex-wrap items-center justify-between gap-2 border-b border-slate-700 pb-2">
            <div class="flex items-center gap-2">
              <span class="px-2 py-0.5 text-[11px] font-extrabold rounded bg-amber-400 text-slate-950">THU-MAIC / OpenMAIC + manim-slides</span>
              <h3 class="text-xs font-bold text-white">Сценарий интерактивного разбора листа (ShowSheet → ZoomBBox → LaserPoint → RunSimPreset → QuizCheckpoint)</h3>
            </div>
            <span id="openmaic-sheet-badge" class="text-[11px] font-mono text-amber-300">Лист #8</span>
          </div>
          <div id="openmaic-action-stream" class="grid grid-cols-5 gap-1.5"></div>
          <div id="openmaic-socratic-checkpoint" class="bg-slate-900/95 border border-slate-700 rounded-lg p-3 space-y-2"></div>
        </div>
        <div id="page-intensive-cards" class="space-y-4"></div>
        <!-- Inline Live Interactive Simulator on the Active Sheet Tab -->
        <div id="page-inline-sim-card" class="bg-slate-800/95 border-2 border-cyan-500/40 rounded-xl p-4 space-y-3">
          <div class="flex flex-wrap items-center justify-between gap-2 border-b border-slate-700 pb-2">
            <div>
              <span class="px-2 py-0.5 text-[11px] font-extrabold rounded bg-cyan-500 text-slate-950">ИНТЕРАКТИВНЫЙ СТЕНД РАЗДЕЛА</span>
              <h3 id="inline-sim-title" class="text-sm font-bold text-white mt-1">Живая симуляция тракта ЦОС и параметров фильтра (Вариант №5)</h3>
            </div>
            <div class="flex flex-wrap gap-1.5">
              <button onclick="setInlineSimMode('filter')" id="btn-isim-filter" class="px-2.5 py-1 text-xs font-bold rounded bg-cyan-500 text-slate-950">📈 АЧХ & Полюса Q15</button>
              <button onclick="setInlineSimMode('osc')" id="btn-isim-osc" class="px-2.5 py-1 text-xs font-semibold rounded bg-slate-900 text-slate-200 border border-slate-700">🌊 Осциллограф & DO #6</button>
              <button onclick="setInlineSimMode('hw')" id="btn-isim-hw" class="px-2.5 py-1 text-xs font-semibold rounded bg-slate-900 text-slate-200 border border-slate-700">🔌 ФНЧ Саллена–Кея & 0-WS</button>
            </div>
          </div>
          <div class="grid grid-cols-3 gap-2 bg-slate-900 p-2.5 rounded-lg border border-slate-700 text-xs">
            <div>
              <div class="flex justify-between text-slate-400 mb-1"><span>Параметр 1 (Частота / Порядок):</span><b id="isim-p1-label" class="text-cyan-300">10.0 кГц</b></div>
              <input id="isim-p1" type="range" min="1" max="20" step="0.5" value="10" oninput="drawInlineSim()" class="w-full" />
            </div>
            <div>
              <div class="flex justify-between text-slate-400 mb-1"><span>Параметр 2 (Разрядность / Секция):</span><b id="isim-p2-label" class="text-amber-300">16 бит (Q15)</b></div>
              <input id="isim-p2" type="range" min="8" max="16" step="1" value="16" oninput="drawInlineSim()" class="w-full" />
            </div>
            <div class="flex flex-col justify-center">
              <span id="isim-status-badge" class="text-[11px] font-mono text-emerald-400">ΔA_ПП = 0.05 дБ | A_ПЗ = 80.04 дБ | |p_max| = 0.9878</span>
            </div>
          </div>
          <canvas id="inline-sim-canvas" width="760" height="240" class="w-full h-auto rounded-lg bg-slate-950 border border-slate-700"></canvas>
        </div>
      </div>

      <!-- TAB 2: ALL 6 MODULES & 47 TOPICS EXPLORER -->
      <div id="rview-modules" class="flex-1 overflow-y-auto p-4 hidden space-y-3">
        <div class="flex flex-wrap items-center justify-between gap-2 bg-slate-800/80 p-3 rounded-xl border border-slate-700">
          <div class="flex flex-wrap gap-1.5" id="module-filter-pills"></div>
          <input id="topic-search-input" type="text" placeholder="Поиск по формулам, микросхемам, регистрам (Q15, SSI, AD73322)..." oninput="renderModulesExplorer()" class="px-3 py-1.5 text-xs rounded-lg bg-slate-900 text-white border border-slate-600 w-72 focus:outline-none" />
        </div>
        <div id="modules-topic-list" class="space-y-3"></div>
      </div>

      <!-- TAB 3: SIMULATION 1 — CAUER IIR N=11 & Q15 LAB -->
      <div id="rview-sim1" class="flex-1 overflow-y-auto p-4 hidden space-y-3">
        <div class="bg-slate-800 border border-slate-700 rounded-xl p-4">
          <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
            <div>
              <h2 class="text-sm font-bold text-cyan-300">📈 Лаборатория 1: Эллиптический БИХ-фильтр Кауэра N=11, Z-плоскость и квантование Q15 (стр. 10, 25–30 ПЗ)</h2>
              <p class="text-xs text-slate-400">Крутизна среза 10..11 кГц (Fs=48 кГц), 6 биквадратных секций Direct Form II, |p_max| = 0.9878, секция 6: a1 = -1.8253, L_infinity масштаб g_out = 4.8236</p>
            </div>
            <button onclick="selectSheetByPageNumber(28)" class="px-2.5 py-1 text-xs font-semibold rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 hover:bg-cyan-500 hover:text-slate-950">
              📄 Открыть стр. 28 ПЗ слева
            </button>
          </div>

          <!-- Controls -->
          <div class="grid grid-cols-3 gap-3 mb-3 bg-slate-900/90 p-3 rounded-lg border border-slate-700 text-xs">
            <div>
              <label class="text-slate-400 block mb-1">Тип аппроксимации фильтра:</label>
              <select id="sim1-approx" onchange="drawSim1()" class="w-full px-2 py-1 rounded bg-slate-800 text-white border border-slate-600">
                <option value="cauer">Кауэр (эллиптический) N = 11 (6 секций, 30 MAC)</option>
                <option value="cheb">Чебышев I рода N = 25 (13 секций, 65 MAC)</option>
                <option value="butt">Баттерворт N = 109 (55 секций, 275 MAC)</option>
                <option value="fir">КИХ с окном Кайзера N = 237 (237 MAC)</option>
              </select>
            </div>
            <div>
              <div class="flex justify-between text-slate-400 mb-1">
                <span>Разрядность коэффициентов DSP:</span>
                <b id="sim1-bits-label" class="text-cyan-300">16 бит (Q15 + /2 ASL)</b>
              </div>
              <input id="sim1-bits" type="range" min="8" max="16" step="1" value="16" oninput="drawSim1()" class="w-full" />
            </div>
            <div>
              <label class="text-slate-400 block mb-1">Масштабирование коэффициентов /2 (ASL A):</label>
              <select id="sim1-div2" onchange="drawSim1()" class="w-full px-2 py-1 rounded bg-slate-800 text-white border border-slate-600">
                <option value="on">ВКЛ: Хранение a1/2 в Q15 + сдвиг ASL A (Норма)</option>
                <option value="off">ВЫКЛ: Прямая запись в Q15 (Насыщение a1=-1.8253 до -1.0!)</option>
              </select>
            </div>
          </div>

          <!-- Canvases: Left = Magnitude Response |H(f)| + Zoom, Right = Z-plane -->
          <div class="grid grid-cols-12 gap-3">
            <div class="col-span-7 bg-slate-950 border border-slate-700 rounded-lg p-2">
              <div class="text-[11px] font-semibold text-slate-300 mb-1 flex justify-between">
                <span>АЧХ |H(e^{jω})|, дБ (0..24 кГц) + Врезка пульсаций 0..10 кГц (≤ 0,1 дБ)</span>
                <span id="sim1-telemetry" class="text-emerald-400 font-mono">ΔA_ПП = 0.05 дБ | A_ПЗ = 80.04 дБ</span>
              </div>
              <canvas id="sim1-mag-canvas" width="520" height="290" class="w-full h-auto rounded bg-slate-950"></canvas>
            </div>
            <div class="col-span-5 bg-slate-950 border border-slate-700 rounded-lg p-2">
              <div class="text-[11px] font-semibold text-slate-300 mb-1 flex justify-between">
                <span>Комплексная z-плоскость (|z| = 1)</span>
                <span id="sim1-pole-telemetry" class="text-amber-300 font-mono">|p_max| = 0.9878</span>
              </div>
              <canvas id="sim1-z-canvas" width="340" height="290" class="w-full h-auto rounded bg-slate-950"></canvas>
            </div>
          </div>
        </div>
      </div>

      <!-- TAB 4: SIMULATION 2 — DSP56824 REAL-TIME OSCILLOSCOPE & DO #6 PIPELINE STEPPER -->
      <div id="rview-sim2" class="flex-1 overflow-y-auto p-4 hidden space-y-3">
        <div class="bg-slate-800 border border-slate-700 rounded-xl p-4">
          <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
            <div>
              <h2 class="text-sm font-bold text-cyan-300">🌊 Лаборатория 2: Осциллограф и конвейер SSI_Rx_ISR процессора DSP56824 (стр. 24, 31–33, 38–41 ПЗ)</h2>
              <p class="text-xs text-slate-400">Тактовая частота 40 МГц (T_cyc = 25 нс), период Fs=48 кГц (Ts = 20.833 мкс = 833.3 такта), цикл DO #6 за 150 тактов (3.75 мкс, 18.0% ЦП; с dual-move 114 / 102 такта)</p>
            </div>
            <button onclick="selectSheetByPageNumber(32)" class="px-2.5 py-1 text-xs font-semibold rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 hover:bg-cyan-500 hover:text-slate-950">
              📄 Открыть стр. 32 ПЗ слева
            </button>
          </div>

          <div class="grid grid-cols-3 gap-3 mb-3 bg-slate-900/90 p-3 rounded-lg border border-slate-700 text-xs">
            <div>
              <div class="flex justify-between text-slate-400 mb-1">
                <span>Полезный тон f1 (полоса пропускания):</span>
                <b id="sim2-f1-val" class="text-cyan-300">2.5 кГц</b>
              </div>
              <input id="sim2-f1" type="range" min="0.5" max="9.5" step="0.5" value="2.5" oninput="drawSim2()" class="w-full" />
            </div>
            <div>
              <div class="flex justify-between text-slate-400 mb-1">
                <span>Частота помехи f2 (полоса задерживания):</span>
                <b id="sim2-f2-val" class="text-pink-400">14.5 кГц</b>
              </div>
              <input id="sim2-f2" type="range" min="11.0" max="22.0" step="0.5" value="14.5" oninput="drawSim2()" class="w-full" />
            </div>
            <div>
              <div class="flex justify-between text-slate-400 mb-1">
                <span>Шаг итерации аппаратного цикла DO #6:</span>
                <b id="sim2-sec-val" class="text-amber-300">Секция 6 / 6</b>
              </div>
              <input id="sim2-sec" type="range" min="1" max="6" step="1" value="6" oninput="drawSim2()" class="w-full" />
            </div>
          </div>

          <div class="grid grid-cols-12 gap-3">
            <div class="col-span-7 bg-slate-950 border border-slate-700 rounded-lg p-2">
              <div class="text-[11px] font-semibold text-slate-300 mb-1 flex justify-between">
                <span>Двухлучевой осциллограф: Вход x(n) (с помехой) vs Выход y(n) после БИХ</span>
                <span class="text-cyan-400 font-mono">Подавление помехи > 80 дБ</span>
              </div>
              <canvas id="sim2-osc-canvas" width="520" height="270" class="w-full h-auto rounded bg-slate-950"></canvas>
            </div>
            <div class="col-span-5 bg-slate-950 border border-slate-700 rounded-lg p-3 text-xs space-y-2">
              <div class="font-bold text-amber-300 border-b border-slate-800 pb-1">Состояние регистров ALU DSP56824 (36 бит)</div>
              <div id="sim2-reg-dump" class="space-y-1.5 font-mono text-[11px]"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- TAB 5: SIMULATION 3 — SALLEN-KEY AAF/SMF & IS61LV6416 0-WS TIMING -->
      <div id="rview-sim3" class="flex-1 overflow-y-auto p-4 hidden space-y-3">
        <div class="bg-slate-800 border border-slate-700 rounded-xl p-4">
          <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
            <div>
              <h2 class="text-sm font-bold text-cyan-300">🔌 Лаборатория 3: Активный ФНЧ Саллена–Кея (AD8606AR, f0=25.03 кГц, Q=0.736) и тайминги ОЗУ IS61LV6416 (0 WS)</h2>
              <p class="text-xs text-slate-400">Подавление зеркальных частот вокруг 3,072 МГц (64×Fs кодека AD73322) и цикл чтения ОЗУ t_AA = 10 нс &lt; T_cyc = 25 нс (BCR = $0000)</p>
            </div>
            <div class="flex gap-1.5">
              <button onclick="selectSheetByPageNumber(18)" class="px-2.5 py-1 text-xs font-semibold rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">Стр. 18 (ОЗУ 10 нс)</button>
              <button onclick="selectSheetByPageNumber(19)" class="px-2.5 py-1 text-xs font-semibold rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">Стр. 19 (Саллен–Кей)</button>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-3 mb-3 bg-slate-900/90 p-3 rounded-lg border border-slate-700 text-xs">
            <div>
              <div class="flex justify-between text-slate-400 mb-1">
                <span>Частота среза ФНЧ Саллена–Кея f0 (норма 25.03 кГц):</span>
                <b id="sim3-f0-val" class="text-cyan-300">25.03 кГц (Q = 0.736)</b>
              </div>
              <input id="sim3-f0" type="range" min="15" max="40" step="0.5" value="25.0" oninput="drawSim3()" class="w-full" />
            </div>
            <div>
              <div class="flex justify-between text-slate-400 mb-1">
                <span>Тактовая частота шины DSP56824 (проверка Wait States IS61LV6416):</span>
                <b id="sim3-clk-val" class="text-emerald-300">40 МГц (T_cyc = 25.0 нс &gt; 19 нс → 0 WS)</b>
              </div>
              <input id="sim3-clk" type="range" min="20" max="60" step="2" value="40" oninput="drawSim3()" class="w-full" />
            </div>
          </div>

          <canvas id="sim3-hw-canvas" width="860" height="290" class="w-full h-auto rounded bg-slate-950 border border-slate-700"></canvas>
        </div>
      </div>

      <!-- TAB 6: 8 KEY ENGINEERING NODES FLASHCARDS -->
      <div id="rview-qa" class="flex-1 overflow-y-auto p-4 hidden space-y-3">
        <div class="bg-slate-800 border border-slate-700 rounded-xl p-4">
          <h2 class="text-sm font-bold text-cyan-300 mb-1">⚡ 8 фундаментальных инженерных узлов курсовой работы («Почему спроектировано именно так?»)</h2>
          <p class="text-xs text-slate-400 mb-3">Кликни по любой карточке, чтобы раскрыть точное расчётное обоснование или выделить фрагмент для вопроса в чат</p>
          <div id="qa-cards-container" class="grid grid-cols-1 gap-3"></div>
        </div>
      </div>

    </section>
  </main>

  <!-- ===================================================================== -->
  <!-- FLOATING TEXT SELECTION TOOLBAR (#text-floating-toolbar)              -->
  <!-- ===================================================================== -->
  <div id="text-floating-toolbar" class="fixed hidden z-50 bg-slate-900 border-2 border-pink-500 rounded-xl shadow-2xl p-2 flex items-center gap-2">
    <span class="text-xs font-bold text-pink-300 px-1">Выделен фрагмент:</span>
    <button onclick="sendSelectedTextImmediately()" class="px-2.5 py-1 text-xs font-bold rounded-lg bg-pink-600 hover:bg-pink-500 text-white transition">
      🚀 В чат (1 клик)
    </button>
    <button onclick="openQuestionModalFromTextSelection()" class="px-2.5 py-1 text-xs font-semibold rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-600">
      ✏️ Добавить комментарий...
    </button>
  </div>

  <!-- ===================================================================== -->
  <!-- 1-CLICK QUESTION & IMAGE CROP MODAL (#question-modal)                 -->
  <!-- ===================================================================== -->
  <div id="question-modal" class="fixed inset-0 bg-black/75 hidden z-50 flex items-center justify-center p-4">
    <div class="bg-slate-900 border-2 border-cyan-500/60 rounded-2xl max-w-xl w-full p-5 shadow-2xl space-y-3">
      <div class="flex items-center justify-between border-b border-slate-800 pb-2.5">
        <div class="flex items-center gap-2">
          <span class="px-2 py-0.5 text-xs font-bold rounded bg-pink-600 text-white">МОСТ В ЧАТ ANTIGRAVITY</span>
          <h3 class="text-sm font-bold text-white" id="qmodal-context-title">Отправка выделенного фрагмента</h3>
        </div>
        <button onclick="closeQuestionModal()" class="text-slate-400 hover:text-white text-sm font-bold px-2">✕</button>
      </div>

      <!-- Selected Text or Cropped Image Preview -->
      <div id="qmodal-quote-box" class="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-300 italic max-h-32 overflow-y-auto hidden"></div>
      <div id="qmodal-crop-box" class="p-2 rounded-lg bg-slate-950 border border-slate-800 flex flex-col items-center hidden">
        <span class="text-[11px] text-slate-400 mb-1">Вырезанный участок листа ПЗ / чертежа (будет сохранён в output/user_questions/latest_crop.png):</span>
        <img id="qmodal-crop-preview" src="" alt="Cropped region" class="max-h-48 rounded border border-slate-700" />
      </div>

      <div>
        <label class="text-xs font-semibold text-slate-300 block mb-1">Что именно непонятно или что нужно разобрать подробнее?</label>
        <textarea id="qmodal-input" rows="3" class="w-full px-3 py-2 text-xs rounded-lg bg-slate-950 text-white border border-slate-700 focus:border-cyan-400 focus:outline-none" placeholder="Например: Объясни на пальцах, откуда здесь берётся эта формула и как связаны выводы микросхемы..."></textarea>
      </div>

      <div id="qmodal-status" class="text-xs font-semibold text-emerald-400 hidden"></div>

      <div class="flex items-center justify-between pt-2 border-t border-slate-800">
        <span class="text-[11px] text-slate-400">Промпт копируется в буфер (Ctrl+V в чат) + сохраняется в `output/user_questions/`</span>
        <div class="flex items-center gap-2">
          <button onclick="closeQuestionModal()" class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700">Отмена</button>
          <button onclick="submitQuestionToAntigravity()" class="px-4 py-1.5 text-xs font-bold rounded-lg bg-gradient-to-r from-pink-600 to-cyan-500 text-white shadow-lg hover:opacity-95">
            🚀 Скопировать и отправить в чат (1 клик)
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- Offscreen Canvas for High-DPI Sheet Cropping -->
  <canvas id="offscreen-crop-canvas" class="hidden"></canvas>
"""
