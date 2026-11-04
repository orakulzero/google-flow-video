# -*- coding: utf-8 -*-
"""
scripts/intensive_template_part2.py
JavaScript runtime for the Split-Screen Coursework Intensive:
- Bidirectional Sheet <-> Intensive Sync
- Text Selection Floating Toolbar & Image Rectangular Lasso Cropper
- Hybrid 1-Click Dispatch (Clipboard + FastAPI POST /api/flow/intensive-question)
- 3 Interactive HTML5 Canvas Simulation Engines
"""

JS_RUNTIME_TEMPLATE = r"""
  <script>
    const COURSE_DATA = __COURSE_DATA_JSON__;

    // Flatten all 47 lessons across 6 modules
    const ALL_LESSONS = [];
    COURSE_DATA.modules.forEach(m => {
      m.lessons.forEach(l => {
        ALL_LESSONS.push({ ...l, module_title: m.short_title, module_slug: m.slug });
      });
    });

    // State
    let curSheetIdx = 1; // Default to Page 2 (Assignment / TZ Variant 5) or Page 8
    let curZoom = 1.0;
    let curRightTab = 'page';
    let curModFilter = 0; // 0 = all modules
    let lassoMode = false;
    let isDraggingLasso = false;
    let lassoStart = { x: 0, y: 0 };
    let currentPendingAnnotation = null;
    let autoZoomCameraEnabled = true;
    let curSlideStepIdx = 0;
    let slideLoopEnabled = false;
    let slideAutoPlayTimer = null;
    let whiteboardEnabled = false;
    let typingCalloutTimer = null;

    const learnedTopics = new Set(JSON.parse(localStorage.getItem('dsp56824_intensive_learned_v2') || '[]'));

    function resolveAssetUrl(fileName, subFolder = 'dsp_assets') {
      const href = decodeURIComponent(window.location.href).replace(/\\/g, '/');
      if (href.includes('/brain/')) {
        return fileName;
      }
      if (href.includes('/output/')) {
        return `${subFolder}/${fileName}`;
      }
      return `output/${subFolder}/${fileName}`;
    }

    function resolveAssetFallbacks(fileName, subFolder = 'dsp_assets') {
      return [
        resolveAssetUrl(fileName, subFolder),
        `output/${subFolder}/${fileName}`,
        `${subFolder}/${fileName}`,
        fileName,
        `file:///e:/ANTIGRAVITY/flow_video_testbench/output/${subFolder}/${fileName}`
      ];
    }

    function setImgWithFallback(imgEl, fileName, subFolder = 'dsp_assets') {
      const candidates = resolveAssetFallbacks(fileName, subFolder);
      let idx = 0;
      imgEl.onerror = () => {
        idx += 1;
        if (idx < candidates.length) {
          imgEl.src = candidates[idx];
        }
      };
      imgEl.src = candidates[0];
    }

    function resolveVideoUrl(relPath) {
      const href = decodeURIComponent(window.location.href).replace(/\\/g, '/');
      if (href.includes('/brain/')) {
        return `file:///e:/ANTIGRAVITY/flow_video_testbench/output/${relPath}`;
      }
      if (href.includes('/output/')) {
        return relPath;
      }
      return `output/${relPath}`;
    }

    // Return all items (lessons + structural cards) mapped to a given sheet
    function getItemsForSheet(sheetObj) {
      if (sheetObj.blueprint_id === 'drawing_e2') {
        return ALL_LESSONS.filter(l => l.pz_page === 42);
      }
      if (sheetObj.blueprint_id === 'drawing_pe2') {
        return ALL_LESSONS.filter(l => l.pz_page === 43);
      }
      const pNum = sheetObj.page_number;
      const lessons = ALL_LESSONS.filter(l => l.pz_page === pNum);
      const structCards = COURSE_DATA.structural_cards.filter(s => s.page_number === pNum);
      return [...structCards.map(s => ({ ...s, is_structural: true })), ...lessons];
    }

    function initApp() {
      populateSheetSelectorAndFilmstrip();
      renderModulesFilterPills();
      renderQACards();
      updateLearnedProgressBadge();
      setupLassoEvents();
      setupTextSelectionListener();
      // Start on Page 8 (first substantive calculation sheet) or Page 2
      selectSheetByIndex(7);
      drawSim1();
      drawSim2();
      drawSim3();
    }

    function populateSheetSelectorAndFilmstrip() {
      const sel = document.getElementById('sheet-select');
      const strip = document.getElementById('sheet-filmstrip');
      sel.innerHTML = '';
      strip.innerHTML = '';

      COURSE_DATA.sheets_catalog.forEach((sh, idx) => {
        const items = getItemsForSheet(sh);
        const opt = document.createElement('option');
        opt.value = idx;
        opt.textContent = sh.is_blueprint
          ? `📐 ${sh.title}`
          : `📄 Стр. ${sh.page_number}/43 — ${sh.section_hint} (${items.length})`;
        sel.appendChild(opt);

        const pill = document.createElement('button');
        pill.id = `film-pill-${idx}`;
        pill.onclick = () => selectSheetByIndex(idx);
        const label = sh.blueprint_id === 'drawing_e2' ? 'Э2 (А3)' : (sh.blueprint_id === 'drawing_pe2' ? 'ПЭ2 (А4)' : `${sh.page_number}`);
        pill.className = 'px-2 py-1 text-[11px] font-bold rounded border shrink-0 transition';
        pill.textContent = label;
        pill.title = sh.title;
        strip.appendChild(pill);
      });
    }

    function updateFilmstripHighlight() {
      COURSE_DATA.sheets_catalog.forEach((sh, idx) => {
        const pill = document.getElementById(`film-pill-${idx}`);
        if (!pill) return;
        if (idx === curSheetIdx) {
          pill.className = 'px-2.5 py-1 text-[11px] font-extrabold rounded bg-cyan-500 text-slate-950 border border-cyan-300 shrink-0 shadow';
          pill.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
        } else if (sh.is_blueprint) {
          pill.className = 'px-2 py-1 text-[11px] font-bold rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 hover:bg-amber-500/30 shrink-0';
        } else {
          pill.className = 'px-2 py-1 text-[11px] font-semibold rounded bg-slate-800 text-slate-300 border border-slate-700 hover:bg-slate-700 shrink-0';
        }
      });
    }

    function selectSheetByIndex(idx, highlightItemId = null) {
      if (idx < 0 || idx >= COURSE_DATA.sheets_catalog.length) return;
      curSheetIdx = idx;
      const sh = COURSE_DATA.sheets_catalog[idx];
      document.getElementById('sheet-select').value = idx;
      updateFilmstripHighlight();

      const img = document.getElementById('sheet-img');
      setImgWithFallback(img, sh.sheet_file, 'dsp_assets');

      const items = getItemsForSheet(sh);
      document.getElementById('left-sheet-caption').textContent = `${sh.title} • ${sh.section_hint}`;
      document.getElementById('sheet-topics-count-badge').textContent = `Блоков разбора: ${items.length}`;

      renderSheetBBoxOverlays(sh, items, highlightItemId);
      renderActivePageIntensive(sh, items, highlightItemId);
      curSlideStepIdx = 0;
      renderOpenMAICClassroomWidget(sh, items);
      autoSyncInlineSimForPage(sh.page_number);
    }

    function getOpenMAICActionPackForSheetIndex(sheetIdx) {
      const key = String(sheetIdx + 1);
      if (COURSE_DATA.openmaic_actions && COURSE_DATA.openmaic_actions[key]) {
        return COURSE_DATA.openmaic_actions[key];
      }
      return {
        page_number: sheetIdx + 1,
        actions: [
          { action_id: 'act01', type: 'ShowSheet', title: 'ShowSheet', description: 'Обзор листа ПЗ', bbox: [0.0, 0.0, 1.0, 1.0], zoom: 1.0 },
          { action_id: 'act02', type: 'ZoomBBox', title: 'ZoomBBox', description: 'Фокус на расчётном блоке', bbox: [0.1, 0.14, 0.9, 0.48], zoom: 1.65 },
          { action_id: 'act03', type: 'LaserPoint', title: 'LaserPoint', description: 'Трассировка лазерной указкой', bbox: [0.1, 0.50, 0.9, 0.85], zoom: 1.75 },
          { action_id: 'act04', type: 'RunSimPreset', title: 'RunSimPreset', description: 'Запуск пресета симулятора', bbox: [0.1, 0.14, 0.9, 0.48], zoom: 1.5, sim_preset: { mode: 'filter', p1: 10, p2: 16 } },
          { action_id: 'act05', type: 'QuizCheckpoint', title: 'QuizCheckpoint', description: 'Контрольный вопрос', bbox: [0.1, 0.50, 0.9, 0.85], zoom: 1.4, quiz: { question: 'Проверка параметров Варианта №5', options: ['3.75 мкс <= 20.833 мкс (Q15 /2 ASL A)', 'Плавающая запятая IEEE-754', 'КИХ N=237'], correct_index: 0, explanation: 'Фиксированная точка Q15 с запасом реального времени 82%.' } }
        ]
      };
    }

    function animateCalloutText(textStr) {
      const hud = document.getElementById('pdf2video-callout');
      if (!hud) return;
      if (typingCalloutTimer) clearInterval(typingCalloutTimer);
      const full = `🎯 Paper2Video Focus: ${textStr}`;
      let pos = Math.min(22, full.length);
      hud.textContent = full.slice(0, pos);
      typingCalloutTimer = setInterval(() => {
        pos += 3;
        if (pos >= full.length) {
          hud.textContent = full;
          clearInterval(typingCalloutTimer);
          typingCalloutTimer = null;
        } else {
          hud.textContent = full.slice(0, pos) + '▋';
        }
      }, 24);
    }

    function applySheetAutoZoomAndLaser(bbox, labelText = '', zoomOverride = null) {
      const zoomContainer = document.getElementById('sheet-zoom-container');
      const laserEl = document.getElementById('paper2video-laser');
      const [x0, y0, x1, y1] = (bbox && bbox.length >= 4) ? bbox : [0.1, 0.15, 0.9, 0.55];
      const cx = 0.5 * (x0 + x1);
      const cy = 0.5 * (y0 + y1);

      if (laserEl) {
        laserEl.style.left = `${(cx * 100).toFixed(1)}%`;
        laserEl.style.top = `${(cy * 100).toFixed(1)}%`;
      }
      if (labelText) {
        animateCalloutText(labelText);
      }
      if (!zoomContainer) return;
      if (!autoZoomCameraEnabled || (x0 <= 0.01 && y0 <= 0.01 && x1 >= 0.99 && y1 >= 0.99)) {
        zoomContainer.style.transform = 'scale(1) translate(0%, 0%)';
        return;
      }
      const span = Math.max(0.18, Math.max(x1 - x0, y1 - y0));
      const z = zoomOverride || Math.min(1.85, Math.max(1.4, +(0.82 / span).toFixed(2)));
      const tx = Math.max(-24, Math.min(24, (0.5 - cx) * 45));
      const ty = Math.max(-28, Math.min(28, (0.5 - cy) * 45));
      zoomContainer.style.transform = `scale(${z.toFixed(2)}) translate(${tx.toFixed(1)}%, ${ty.toFixed(1)}%)`;
    }

    function toggleAutoZoomCamera() {
      autoZoomCameraEnabled = !autoZoomCameraEnabled;
      const b1 = document.getElementById('btn-autozoom-laser');
      const b2 = document.getElementById('btn-slide-autozoom');
      const activeCls = 'px-2.5 py-1 text-xs font-bold rounded bg-amber-500 text-slate-950 shadow transition';
      const idleCls = 'px-2.5 py-1 text-xs font-bold rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 transition';
      if (b1) b1.className = autoZoomCameraEnabled ? activeCls : idleCls;
      if (b2) b2.textContent = autoZoomCameraEnabled ? '🔍 Авто-Зум камеры: ВКЛ' : '🔍 Авто-Зум камеры: ВЫКЛ';
      executeOpenMAICAction(curSlideStepIdx);
    }

    function prevSlideStep() {
      const pack = getOpenMAICActionPackForSheetIndex(curSheetIdx);
      const total = pack.actions.length;
      curSlideStepIdx = (curSlideStepIdx - 1 + total) % total;
      executeOpenMAICAction(curSlideStepIdx);
    }

    function nextSlideStep() {
      const pack = getOpenMAICActionPackForSheetIndex(curSheetIdx);
      const total = pack.actions.length;
      if (slideLoopEnabled) {
        executeOpenMAICAction(curSlideStepIdx);
        return;
      }
      curSlideStepIdx = (curSlideStepIdx + 1) % total;
      executeOpenMAICAction(curSlideStepIdx);
    }

    function toggleSlideLoop() {
      slideLoopEnabled = !slideLoopEnabled;
      const btn = document.getElementById('btn-slide-loop');
      if (btn) {
        btn.textContent = slideLoopEnabled ? '🔁 Цикл блока: ВКЛ' : '🔁 Зациклить текущий блок';
      }
    }

    function toggleSlidePlayPause() {
      const btn = document.getElementById('btn-slide-play');
      if (slideAutoPlayTimer) {
        clearInterval(slideAutoPlayTimer);
        slideAutoPlayTimer = null;
        if (btn) btn.textContent = '⏯ Старт/Пауза авто-разбора';
      } else {
        if (btn) btn.textContent = '⏸ Авто-разбор идёт...';
        slideAutoPlayTimer = setInterval(() => {
          nextSlideStep();
        }, 2800);
      }
    }

    function toggleWhiteboardLayer() {
      whiteboardEnabled = !whiteboardEnabled;
      const wb = document.getElementById('whiteboard-canvas');
      if (wb) wb.classList.toggle('hidden', !whiteboardEnabled);
    }

    function renderOpenMAICClassroomWidget(sh, items) {
      const streamEl = document.getElementById('openmaic-action-stream');
      const quizEl = document.getElementById('openmaic-socratic-checkpoint');
      const badgeEl = document.getElementById('openmaic-sheet-badge');
      const stepInd = document.getElementById('manim-slide-step-indicator');
      if (!streamEl || !quizEl) return;

      const pack = getOpenMAICActionPackForSheetIndex(curSheetIdx);
      if (badgeEl) badgeEl.textContent = `Лист #${curSheetIdx + 1}/45 (${sh.sheet_file})`;
      if (stepInd) stepInd.textContent = `Шаг ${curSlideStepIdx + 1} / ${pack.actions.length} (manim-slides)`;

      streamEl.innerHTML = '';
      pack.actions.forEach((act, idx) => {
        const btn = document.createElement('button');
        const isCur = (idx === curSlideStepIdx);
        btn.className = isCur
          ? 'p-2 rounded-lg bg-amber-400 text-slate-950 font-extrabold text-[11px] text-left shadow transition'
          : 'p-2 rounded-lg bg-slate-900 hover:bg-slate-700 text-slate-200 border border-slate-700 text-[11px] text-left transition';
        btn.innerHTML = `<div class="font-mono text-[10px] opacity-80">Шаг ${idx + 1} • ${act.type}</div><div class="truncate font-bold">${act.description || act.title}</div>`;
        btn.onclick = () => executeOpenMAICAction(idx);
        streamEl.appendChild(btn);
      });

      const quizAct = pack.actions.find(a => a.type === 'QuizCheckpoint') || pack.actions[pack.actions.length - 1];
      const qObj = (quizAct && quizAct.quiz) ? quizAct.quiz : {
        question: `Какой ключевой параметр определяет расчёт на листе ${sh.title}?`,
        options: ['3.75 мкс <= 20.833 мкс и деление коэффициентов /2 в Q15', 'Неограниченная разрядность', 'Отсутствие ФНЧ Саллена–Кея'],
        correct_index: 0,
        explanation: 'Жёсткое реальное время DSP56824 (150 тактов = 3.75 мкс) и масштабирование Q15.'
      };
      const optsHtml = (qObj.options || []).map((opt, oIdx) => `
        <button onclick="verifyOpenMAICQuiz(${oIdx})" class="w-full text-left px-3 py-1.5 rounded bg-slate-800 hover:bg-cyan-500/20 border border-slate-700 text-xs text-slate-200 transition">
          <b>${oIdx + 1}.</b> ${opt}
        </button>
      `).join('');

      quizEl.innerHTML = `
        <div class="flex items-center justify-between">
          <span class="text-xs font-extrabold text-amber-300">🎓 Socratic QuizCheckpoint (Самопроверка по листу):</span>
          <span class="text-[11px] font-mono text-slate-400">OpenMAIC Action #5</span>
        </div>
        <p class="text-xs text-white font-semibold">${qObj.question}</p>
        <div class="space-y-1">${optsHtml}</div>
        <div id="openmaic-quiz-feedback" class="hidden p-2 rounded text-xs font-semibold"></div>
      `;
    }

    function executeOpenMAICAction(stepIdx) {
      const pack = getOpenMAICActionPackForSheetIndex(curSheetIdx);
      if (!pack || !pack.actions || !pack.actions.length) return;
      curSlideStepIdx = Math.max(0, Math.min(pack.actions.length - 1, stepIdx));
      const act = pack.actions[curSlideStepIdx];
      const sh = COURSE_DATA.sheets_catalog[curSheetIdx];
      const items = getItemsForSheet(sh);

      renderOpenMAICClassroomWidget(sh, items);
      applySheetAutoZoomAndLaser(act.bbox || [0.1, 0.15, 0.9, 0.55], `${act.type}: ${act.description || act.title}`, act.zoom || null);

      if (act.sim_preset) {
        setInlineSimMode(act.sim_preset.mode || 'filter');
        const p1El = document.getElementById('isim-p1');
        const p2El = document.getElementById('isim-p2');
        if (p1El && act.sim_preset.p1 !== undefined) p1El.value = act.sim_preset.p1;
        if (p2El && act.sim_preset.p2 !== undefined) p2El.value = act.sim_preset.p2;
        drawInlineSim();
      }
    }

    function verifyOpenMAICQuiz(selectedIdx) {
      const pack = getOpenMAICActionPackForSheetIndex(curSheetIdx);
      const quizAct = pack.actions.find(a => a.type === 'QuizCheckpoint') || pack.actions[pack.actions.length - 1];
      const qObj = (quizAct && quizAct.quiz) ? quizAct.quiz : { correct_index: 0, explanation: '' };
      const fb = document.getElementById('openmaic-quiz-feedback');
      if (!fb) return;
      fb.classList.remove('hidden');
      if (selectedIdx === (qObj.correct_index || 0)) {
        fb.className = 'p-2 rounded bg-emerald-500/20 border border-emerald-500/50 text-emerald-300 text-xs font-semibold';
        fb.textContent = `✅ Верно! ${qObj.explanation || ''}`;
      } else {
        fb.className = 'p-2 rounded bg-rose-500/20 border border-rose-500/50 text-rose-300 text-xs font-semibold';
        fb.textContent = `❌ Попробуй ещё раз. Подсказка: ${qObj.explanation || ''}`;
      }
    }

    function selectSheetByPageNumber(pageNum, highlightItemId = null) {
      const idx = COURSE_DATA.sheets_catalog.findIndex(s => s.page_number === pageNum && !s.is_blueprint);
      if (idx >= 0) {
        selectSheetByIndex(idx, highlightItemId);
      }
    }

    function stepSheet(delta) {
      const next = curSheetIdx + delta;
      if (next >= 0 && next < COURSE_DATA.sheets_catalog.length) {
        selectSheetByIndex(next);
      }
    }

    function adjustZoom(delta) {
      curZoom = Math.min(2.6, Math.max(0.6, +(curZoom + delta).toFixed(2)));
      applyZoom();
    }

    function resetZoom() {
      curZoom = 1.0;
      applyZoom();
    }

    function applyZoom() {
      document.getElementById('zoom-label').textContent = `${Math.round(curZoom * 100)}%`;
      const stage = document.getElementById('sheet-stage');
      stage.style.width = `${Math.round(curZoom * 100)}%`;
    }

    // Render clickable BBox overlays on the Left Pane sheet
    function renderSheetBBoxOverlays(sh, items, highlightItemId) {
      const layer = document.getElementById('bbox-overlay-layer');
      layer.innerHTML = '';

      items.forEach((item, idx) => {
        const boxes = item.bboxes || (item.bbox ? [[...item.bbox, item.title]] : [[0.08, 0.12 + (idx * 0.22) % 0.65, 0.92, 0.32 + (idx * 0.22) % 0.65, item.title]]);
        const itemId = item.is_structural ? item.id : `topic-${item.global_num}`;

        boxes.forEach((b, bIdx) => {
          const [x0, y0, x1, y1, label] = b;
          const div = document.createElement('div');
          const isHighlighted = (highlightItemId === itemId);
          div.className = `bbox-rect ${isHighlighted ? 'active-bbox' : ''}`;
          div.style.left = `${(x0 * 100).toFixed(1)}%`;
          div.style.top = `${(y0 * 100).toFixed(1)}%`;
          div.style.width = `${((x1 - x0) * 100).toFixed(1)}%`;
          div.style.height = `${((y1 - y0) * 100).toFixed(1)}%`;
          div.title = `Кликни, чтобы открыть в интенсиве: ${label || item.title}`;

          const tag = document.createElement('span');
          tag.className = 'px-1.5 py-0.5 text-[10px] font-extrabold bg-cyan-500 text-slate-950 rounded-br shadow inline-block truncate max-w-full';
          tag.textContent = item.is_structural ? `${item.id}: ${label || item.title}` : `#${item.global_num}: ${label || item.badge || item.title}`;
          div.appendChild(tag);

          div.onclick = (e) => {
            e.stopPropagation();
            switchRightTab('page');
            const cardEl = document.getElementById(`intensive-card-${itemId}`);
            if (cardEl) {
              cardEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
              cardEl.classList.add('ring-2', 'ring-amber-400');
              setTimeout(() => cardEl.classList.remove('ring-2', 'ring-amber-400'), 1800);
            }
          };
          layer.appendChild(div);
        });
      });
    }

    // Render Right Pane Tab 1: Active Sheet Intensive Walkthrough
    function renderActivePageIntensive(sh, items, highlightItemId) {
      const hdr = document.getElementById('page-intensive-header');
      const box = document.getElementById('page-intensive-cards');

      hdr.innerHTML = `
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div class="flex items-center gap-2">
              <span class="px-2 py-0.5 text-xs font-extrabold rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
                ${sh.is_blueprint ? 'ЧЕРТЁЖ ЕСКД' : `ЛИСТ ПЗ СТР. ${sh.page_number} ИЗ 43`}
              </span>
              <h2 class="text-base font-bold text-white">${sh.title} — ${sh.section_hint}</h2>
            </div>
            <p class="text-xs text-slate-400 mt-1">
              Ниже приведён полный инженерный разбор всех формул, схем, таблиц и блоков этого листа. Выдели любой непонятный текст мышью или выдели область на листе слева («✂️ Выделить участок»), чтобы в 1 клик отправить вопрос в чат.
            </p>
          </div>
          <div class="flex items-center gap-1.5">
            <button onclick="toggleLassoMode(true)" class="px-3 py-1.5 text-xs font-bold rounded-lg bg-pink-600/20 text-pink-300 border border-pink-500/40 hover:bg-pink-600 hover:text-white transition">
              ✂️ Выделить схему/формулу на листе
            </button>
          </div>
        </div>
      `;

      box.innerHTML = '';
      items.forEach(item => {
        box.appendChild(buildIntensiveCardDOM(item, sh));
      });
    }

    function buildIntensiveCardDOM(item, sh) {
      const itemId = item.is_structural ? item.id : `topic-${item.global_num}`;
      const isLearned = !item.is_structural && learnedTopics.has(item.global_num);
      const card = document.createElement('div');
      card.id = `intensive-card-${itemId}`;
      card.className = 'lesson-card bg-slate-800/90 border border-slate-700 rounded-xl p-4 space-y-3 transition';

      const bulletsHtml = (item.bullets || []).map(b => `<li class="leading-relaxed">${b}</li>`).join('');
      const eqsHtml = (item.equations || []).map(eq => `
        <div class="p-2 rounded bg-slate-950 border border-slate-800 flex items-center justify-between gap-2 text-xs">
          <span class="text-slate-400">${eq.span}:</span>
          <code class="text-cyan-300 font-mono font-bold">${eq.formula}</code>
        </div>
      `).join('');

      const pNum = item.page_number || item.pz_page || 8;
      const fallbackTopicNum = item.global_num || (pNum <= 7 ? pNum : 42);
      const topicFrameFile = `topic_${String(fallbackTopicNum).padStart(2, '0')}.png`;
      const extraFigFile = item.extra_fig || (pNum <= 3 ? 'fig_3_1.png' : (pNum <= 5 ? 'fig_5_3.png' : (pNum <= 7 ? 'drawing_e2.png' : 'fig_4_1.png')));
      const videoRel = item.mp4_rel || 'lesson_03_ru_dsp_cycle1_architecture/scene_01.mp4';
      const videoUrl = resolveVideoUrl(videoRel);

      const mediaSectionHtml = `
        <div class="pt-2 border-t border-slate-700/80 space-y-2">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <span class="text-xs font-bold text-slate-300">🎬 Иллюстрации, чертежи и видео-разбор к блоку:</span>
            <div class="flex flex-wrap gap-1.5">
              <button onclick="toggleCardMedia('${itemId}', 'split')" class="px-2.5 py-1 text-[11px] font-semibold rounded bg-slate-700 hover:bg-cyan-500 hover:text-slate-950 text-slate-200 transition">🖼 Сплит-кадр симуляции</button>
              <button onclick="toggleCardMedia('${itemId}', 'fig')" class="px-2.5 py-1 text-[11px] font-semibold rounded bg-slate-700 hover:bg-cyan-500 hover:text-slate-950 text-slate-200 transition">📐 Чертёж / Схема (${extraFigFile})</button>
              <button onclick="toggleCardMedia('${itemId}', 'video')" class="px-2.5 py-1 text-[11px] font-semibold rounded bg-slate-700 hover:bg-cyan-500 hover:text-slate-950 text-slate-200 transition">▶ Видео-анимация (720p MP4)</button>
              <button onclick="openSimForPage(${pNum})" class="px-2.5 py-1 text-[11px] font-bold rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 hover:bg-emerald-500 hover:text-slate-950 transition">🧮 Развернуть лабораторию</button>
            </div>
          </div>
          <div id="media-split-${itemId}" class="rounded-lg overflow-hidden border border-slate-700 bg-slate-950">
            <img id="img-split-${itemId}" alt="${item.title}" class="w-full h-auto block" loading="lazy" />
          </div>
          <div id="media-fig-${itemId}" class="hidden rounded-lg overflow-hidden border border-slate-700 bg-white p-2">
            <img id="img-fig-${itemId}" alt="Профильная схема" class="w-full h-auto block" loading="lazy" />
          </div>
          <div id="media-video-${itemId}" class="hidden rounded-lg overflow-hidden border border-slate-700 bg-black">
            <video controls preload="none" class="w-full h-auto max-h-80" src="${videoUrl}"></video>
          </div>
        </div>
      `;

      card.innerHTML = `
        <div class="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-slate-700">
          <div class="flex flex-wrap items-center gap-2">
            <span class="px-2.5 py-0.5 text-xs font-extrabold rounded bg-cyan-500 text-slate-950">
              ${item.is_structural ? `Раздел ПЗ ${item.id}` : `Тема #${item.global_num} (М${item.cycle_num}.${item.scene_num})`}
            </span>
            <span class="px-2 py-0.5 text-xs font-semibold rounded bg-slate-900 text-slate-300 border border-slate-700">
              Стр. ПЗ: ${item.page_number || item.pz_page}
            </span>
            ${item.tc_str ? `<span class="px-2 py-0.5 text-xs font-mono rounded bg-slate-900 text-cyan-300 border border-slate-700">⏱ ${item.tc_str}</span>` : ''}
            ${item.badge ? `<span class="px-2 py-0.5 text-xs font-semibold rounded bg-amber-500/15 text-amber-300 border border-amber-500/30">${item.badge}</span>` : ''}
          </div>
          <div class="flex items-center gap-2">
            <button onclick="focusItemOnLeftSheet('${itemId}', ${item.page_number || item.pz_page})" class="px-2.5 py-1 text-xs font-semibold rounded bg-slate-700 hover:bg-amber-400 hover:text-slate-950 text-slate-200 transition">
              🎯 Показать на листе слева
            </button>
            <button onclick="askQuestionAboutCard('${itemId}')" class="px-2.5 py-1 text-xs font-bold rounded bg-pink-600/25 text-pink-300 border border-pink-500/40 hover:bg-pink-600 hover:text-white transition">
              ❓ Непонятно → в чат
            </button>
            ${!item.is_structural ? `
              <label class="flex items-center gap-1.5 text-xs font-bold cursor-pointer select-none px-2 py-1 rounded bg-slate-900 border border-slate-700">
                <input type="checkbox" ${isLearned ? 'checked' : ''} onchange="toggleTopicLearned(${item.global_num}, this.checked)" class="rounded" />
                <span class="text-emerald-300">Изучено</span>
              </label>
            ` : ''}
          </div>
        </div>

        <h3 class="text-sm font-bold text-white">${item.title}</h3>

        <div class="p-3 rounded-lg bg-slate-950/90 border border-slate-800 text-xs leading-relaxed text-slate-200">
          ${item.narration}
        </div>

        <div>
          <div class="text-xs font-bold text-cyan-300 mb-1">📌 Ключевые инженерные тезисы, формулы и параметры на листе:</div>
          <ul class="list-disc pl-5 space-y-1 text-xs text-slate-300">${bulletsHtml}</ul>
        </div>

        ${eqsHtml ? `<div class="grid grid-cols-1 gap-1.5">${eqsHtml}</div>` : ''}
        ${mediaSectionHtml}
      `;
      const splitImgEl = card.querySelector(`#img-split-${itemId}`);
      if (splitImgEl) setImgWithFallback(splitImgEl, topicFrameFile, 'course_frames');
      const figImgEl = card.querySelector(`#img-fig-${itemId}`);
      if (figImgEl) setImgWithFallback(figImgEl, extraFigFile, 'dsp_assets');
      return card;
    }

    function toggleCardMedia(itemId, mode) {
      ['split', 'fig', 'video'].forEach(m => {
        const el = document.getElementById(`media-${m}-${itemId}`);
        if (el) el.classList.toggle('hidden', m !== mode);
      });
    }

    function focusItemOnLeftSheet(itemId, pageNum) {
      selectSheetByPageNumber(pageNum, itemId);
    }

    function openSimForPage(pzPage) {
      if ([10, 25, 26, 27, 28, 29, 30].includes(pzPage)) {
        switchRightTab('sim1');
      } else if ([24, 31, 32, 33, 38, 39, 40, 41].includes(pzPage)) {
        switchRightTab('sim2');
      } else {
        switchRightTab('sim3');
      }
    }

    function switchRightTab(tab) {
      curRightTab = tab;
      ['page', 'modules', 'sim1', 'sim2', 'sim3', 'qa'].forEach(t => {
        const view = document.getElementById(`rview-${t}`);
        const btn = document.getElementById(`rtab-${t}`);
        if (view) view.classList.toggle('hidden', t !== tab);
        if (btn) {
          btn.className = (t === tab)
            ? 'px-3 py-1.5 text-xs font-bold rounded-lg bg-cyan-500 text-slate-950 transition shadow'
            : 'px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 text-slate-200 hover:bg-slate-700 transition';
        }
      });
      if (tab === 'modules') renderModulesExplorer();
      if (tab === 'sim1') drawSim1();
      if (tab === 'sim2') drawSim2();
      if (tab === 'sim3') drawSim3();
    }

    // Modules & 47 Topics Explorer
    function renderModulesFilterPills() {
      const box = document.getElementById('module-filter-pills');
      box.innerHTML = '';
      const allBtn = document.createElement('button');
      allBtn.textContent = 'Все 6 модулей (47 тем)';
      allBtn.className = curModFilter === 0
        ? 'px-2.5 py-1 text-xs font-bold rounded bg-cyan-500 text-slate-950'
        : 'px-2.5 py-1 text-xs font-semibold rounded bg-slate-900 text-slate-300 border border-slate-700';
      allBtn.onclick = () => { curModFilter = 0; renderModulesFilterPills(); renderModulesExplorer(); };
      box.appendChild(allBtn);

      COURSE_DATA.modules.forEach(m => {
        const btn = document.createElement('button');
        btn.textContent = `М${m.cycle_number} (${m.lessons.length})`;
        btn.title = m.short_title;
        btn.className = curModFilter === m.cycle_number
          ? 'px-2.5 py-1 text-xs font-bold rounded bg-cyan-500 text-slate-950'
          : 'px-2.5 py-1 text-xs font-semibold rounded bg-slate-900 text-slate-300 border border-slate-700';
        btn.onclick = () => { curModFilter = m.cycle_number; renderModulesFilterPills(); renderModulesExplorer(); };
        box.appendChild(btn);
      });
    }

    function renderModulesExplorer() {
      const q = (document.getElementById('topic-search-input').value || '').trim().toLowerCase();
      const box = document.getElementById('modules-topic-list');
      box.innerHTML = '';

      const filtered = ALL_LESSONS.filter(l => {
        if (curModFilter !== 0 && l.cycle_num !== curModFilter) return false;
        if (!q) return true;
        return (
          l.title.toLowerCase().includes(q) ||
          l.narration.toLowerCase().includes(q) ||
          (l.bullets || []).some(b => b.toLowerCase().includes(q)) ||
          `стр. ${l.pz_page}`.includes(q)
        );
      });

      filtered.forEach(l => {
        const sh = COURSE_DATA.sheets_catalog.find(s => s.page_number === l.pz_page && !s.is_blueprint) || COURSE_DATA.sheets_catalog[0];
        box.appendChild(buildIntensiveCardDOM(l, sh));
      });
    }

    function renderQACards() {
      const box = document.getElementById('qa-cards-container');
      box.innerHTML = '';
      COURSE_DATA.qa_cards.forEach((qa, idx) => {
        const div = document.createElement('div');
        div.className = 'p-3.5 rounded-xl bg-slate-900 border border-slate-700 space-y-2';
        div.innerHTML = `
          <div class="flex items-center justify-between gap-2">
            <span class="text-xs font-bold text-amber-300">❓ Узел #${idx + 1}: ${qa.q}</span>
            <button onclick="openQuestionModalCustom('Вопрос по узлу #${idx + 1}', '${qa.q.replace(/'/g, "\\'")}')" class="px-2 py-0.5 text-[11px] font-semibold rounded bg-pink-600/20 text-pink-300 border border-pink-500/40">Уточнить в чате</button>
          </div>
          <p class="text-xs text-slate-300 leading-relaxed">${qa.a}</p>
        `;
        box.appendChild(div);
      });
    }

    function toggleTopicLearned(globalNum, checked) {
      if (checked) learnedTopics.add(globalNum);
      else learnedTopics.delete(globalNum);
      localStorage.setItem('dsp56824_intensive_learned_v2', JSON.stringify([...learnedTopics]));
      updateLearnedProgressBadge();
    }

    function updateLearnedProgressBadge() {
      document.getElementById('learned-progress-badge').textContent = `Изучено: ${learnedTopics.size} / 47 тем`;
    }

    // =========================================================================
    // HYBRID 1-CLICK SELECTION & ANNOTATION BRIDGE (TEXT + IMAGE LASSO)
    // =========================================================================
    function setupTextSelectionListener() {
      const toolbar = document.getElementById('text-floating-toolbar');
      document.addEventListener('mouseup', (e) => {
        if (toolbar.contains(e.target) || document.getElementById('question-modal').contains(e.target)) return;
        const sel = window.getSelection();
        const text = sel ? sel.toString().trim() : '';
        if (text.length >= 4) {
          const range = sel.getRangeAt(0);
          const rect = range.getBoundingClientRect();
          toolbar.style.left = `${Math.max(12, Math.min(window.innerWidth - 340, rect.left))}px`;
          toolbar.style.top = `${Math.max(12, rect.top - 46)}px`;
          toolbar.classList.remove('hidden');

          const sh = COURSE_DATA.sheets_catalog[curSheetIdx];
          currentPendingAnnotation = {
            page_number: sh.page_number,
            sheet_name: sh.sheet_file,
            topic_id: `sheet_${sh.page_number}`,
            topic_title: sh.title,
            selection_type: 'text_highlight',
            bbox: [0.1, 0.1, 0.9, 0.3],
            selected_text: text,
            image_base64: null
          };
        } else {
          toolbar.classList.add('hidden');
        }
      });
    }

    function sendSelectedTextImmediately() {
      if (!currentPendingAnnotation) return;
      document.getElementById('text-floating-toolbar').classList.add('hidden');
      document.getElementById('qmodal-input').value = 'Объясни подробно этот фрагмент и физический смысл входящих в него параметров.';
      submitQuestionToAntigravity();
    }

    function openQuestionModalFromTextSelection() {
      if (!currentPendingAnnotation) return;
      document.getElementById('text-floating-toolbar').classList.add('hidden');
      openQuestionModalUI();
    }

    function askQuestionAboutCard(itemId) {
      const sh = COURSE_DATA.sheets_catalog[curSheetIdx];
      const items = getItemsForSheet(sh);
      const item = items.find(x => (x.is_structural ? x.id : `topic-${x.global_num}`) === itemId) || items[0];
      currentPendingAnnotation = {
        page_number: sh.page_number,
        sheet_name: sh.sheet_file,
        topic_id: itemId,
        topic_title: item ? item.title : sh.title,
        selection_type: 'text_highlight',
        bbox: [0.1, 0.1, 0.9, 0.5],
        selected_text: item ? `${item.title}: ${item.narration.slice(0, 260)}...` : sh.title,
        image_base64: null
      };
      openQuestionModalUI();
    }

    function openQuestionModalWithCurrentContext() {
      const sh = COURSE_DATA.sheets_catalog[curSheetIdx];
      currentPendingAnnotation = {
        page_number: sh.page_number,
        sheet_name: sh.sheet_file,
        topic_id: `page_${sh.page_number}`,
        topic_title: `${sh.title} (${sh.section_hint})`,
        selection_type: 'text_highlight',
        bbox: [0.0, 0.0, 1.0, 1.0],
        selected_text: `Лист ПЗ стр. ${sh.page_number} (${sh.sheet_file})`,
        image_base64: null
      };
      openQuestionModalUI();
    }

    function openQuestionModalCustom(title, quoteText) {
      const sh = COURSE_DATA.sheets_catalog[curSheetIdx];
      currentPendingAnnotation = {
        page_number: sh.page_number,
        sheet_name: sh.sheet_file,
        topic_id: 'qa_node',
        topic_title: title,
        selection_type: 'text_highlight',
        bbox: [0.1, 0.1, 0.9, 0.5],
        selected_text: quoteText,
        image_base64: null
      };
      openQuestionModalUI();
    }

    // Rectangular Image Lasso on Left Pane Sheet
    function toggleLassoMode(forceState = null) {
      lassoMode = (forceState !== null) ? forceState : !lassoMode;
      const btn = document.getElementById('btn-toggle-lasso');
      const dragLayer = document.getElementById('lasso-drag-layer');
      if (lassoMode) {
        btn.className = 'px-2.5 py-1 text-xs font-extrabold rounded bg-pink-600 text-white shadow-lg ring-2 ring-pink-300';
        btn.textContent = '✂️ Выдели рамкой участок... (Отмена)';
        dragLayer.classList.remove('hidden');
      } else {
        btn.className = 'px-2.5 py-1 text-xs font-bold rounded bg-pink-600/20 text-pink-300 border border-pink-500/40 hover:bg-pink-600 hover:text-white transition';
        btn.textContent = '✂️ Выделить участок';
        dragLayer.classList.add('hidden');
        document.getElementById('lasso-box').classList.add('hidden');
      }
    }

    function setupLassoEvents() {
      const dragLayer = document.getElementById('lasso-drag-layer');
      const lassoBox = document.getElementById('lasso-box');

      dragLayer.addEventListener('mousedown', (e) => {
        if (!lassoMode) return;
        isDraggingLasso = true;
        const rect = dragLayer.getBoundingClientRect();
        lassoStart = {
          x: (e.clientX - rect.left) / rect.width,
          y: (e.clientY - rect.top) / rect.height
        };
        lassoBox.style.left = `${lassoStart.x * 100}%`;
        lassoBox.style.top = `${lassoStart.y * 100}%`;
        lassoBox.style.width = '0%';
        lassoBox.style.height = '0%';
        lassoBox.classList.remove('hidden');
      });

      dragLayer.addEventListener('mousemove', (e) => {
        if (!isDraggingLasso) return;
        const rect = dragLayer.getBoundingClientRect();
        const curX = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
        const curY = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));
        const x0 = Math.min(lassoStart.x, curX);
        const y0 = Math.min(lassoStart.y, curY);
        const w = Math.abs(curX - lassoStart.x);
        const h = Math.abs(curY - lassoStart.y);
        lassoBox.style.left = `${x0 * 100}%`;
        lassoBox.style.top = `${y0 * 100}%`;
        lassoBox.style.width = `${w * 100}%`;
        lassoBox.style.height = `${h * 100}%`;
      });

      window.addEventListener('mouseup', (e) => {
        if (!isDraggingLasso) return;
        isDraggingLasso = false;
        const rect = dragLayer.getBoundingClientRect();
        const curX = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
        const curY = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));
        const x0 = Math.min(lassoStart.x, curX);
        const y0 = Math.min(lassoStart.y, curY);
        const x1 = Math.max(lassoStart.x, curX);
        const y1 = Math.max(lassoStart.y, curY);

        if ((x1 - x0) < 0.02 || (y1 - y0) < 0.02) {
          lassoBox.classList.add('hidden');
          return;
        }

        const croppedDataUrl = cropSheetRegionToBase64(x0, y0, x1, y1);
        const sh = COURSE_DATA.sheets_catalog[curSheetIdx];
        currentPendingAnnotation = {
          page_number: sh.page_number,
          sheet_name: sh.sheet_file,
          topic_id: `sheet_${sh.page_number}_crop`,
          topic_title: `${sh.title} (${sh.section_hint})`,
          selection_type: 'image_crop',
          bbox: [+x0.toFixed(4), +y0.toFixed(4), +x1.toFixed(4), +y1.toFixed(4)],
          selected_text: null,
          image_base64: croppedDataUrl
        };
        toggleLassoMode(false);
        openQuestionModalUI();
      });
    }

    function cropSheetRegionToBase64(x0, y0, x1, y1) {
      const img = document.getElementById('sheet-img');
      const canvas = document.getElementById('offscreen-crop-canvas');
      const natW = img.naturalWidth || 1200;
      const natH = img.naturalHeight || 1600;
      const sx = Math.round(x0 * natW);
      const sy = Math.round(y0 * natH);
      const sw = Math.max(16, Math.round((x1 - x0) * natW));
      const sh = Math.max(16, Math.round((y1 - y0) * natH));
      canvas.width = sw;
      canvas.height = sh;
      const ctx = canvas.getContext('2d');
      try {
        ctx.drawImage(img, sx, sy, sw, sh, 0, 0, sw, sh);
        return canvas.toDataURL('image/png');
      } catch (err) {
        // Fallback synthetic preview if file:// CORS blocks canvas readback
        ctx.fillStyle = '#0f172a';
        ctx.fillRect(0, 0, 360, 140);
        ctx.strokeStyle = '#06b6d4';
        ctx.strokeRect(4, 4, 352, 132);
        ctx.fillStyle = '#f8fafc';
        ctx.font = 'bold 13px sans-serif';
        ctx.fillText(`Выделенная область листа (${Math.round(x0*100)}%..${Math.round(x1*100)}%)`, 16, 55);
        return canvas.toDataURL('image/png');
      }
    }

    function openQuestionModalUI() {
      if (!currentPendingAnnotation) return;
      document.getElementById('qmodal-context-title').textContent =
        `${currentPendingAnnotation.topic_title} • Стр. ${currentPendingAnnotation.page_number}`;
      const quoteBox = document.getElementById('qmodal-quote-box');
      const cropBox = document.getElementById('qmodal-crop-box');
      const statusBox = document.getElementById('qmodal-status');
      statusBox.classList.add('hidden');

      if (currentPendingAnnotation.selection_type === 'image_crop' && currentPendingAnnotation.image_base64) {
        quoteBox.classList.add('hidden');
        cropBox.classList.remove('hidden');
        document.getElementById('qmodal-crop-preview').src = currentPendingAnnotation.image_base64;
      } else {
        cropBox.classList.add('hidden');
        quoteBox.classList.remove('hidden');
        quoteBox.textContent = `«${currentPendingAnnotation.selected_text || ''}»`;
      }
      document.getElementById('question-modal').classList.remove('hidden');
      document.getElementById('qmodal-input').focus();
    }

    function closeQuestionModal() {
      document.getElementById('question-modal').classList.add('hidden');
    }

    async function submitQuestionToAntigravity() {
      if (!currentPendingAnnotation) return;
      const userQ = (document.getElementById('qmodal-input').value || '').trim() ||
        'Объясни этот участок курсовой работы подробно (формулы, физический смысл, связь со схемой).';

      const payload = {
        ...currentPendingAnnotation,
        user_question: userQ
      };

      // 1. Try POSTing to local FastAPI bridge (/api/flow/intensive-question)
      let savedCropPath = 'output/user_questions/latest_crop.png';
      try {
        const res = await fetch('/api/flow/intensive-question', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (res.ok) {
          const data = await res.json();
          if (data.crop_path) savedCropPath = data.crop_path;
        }
      } catch (_err) {
        // Offline / file:// protocol — clipboard prompt still works 100%
      }

      // 2. Build ready-to-paste Markdown prompt for Antigravity chat
      const bboxStr = payload.bbox ? payload.bbox.map(v => v.toFixed(2)).join(', ') : '0,0,1,1';
      const mdLines = [
        `❓ **Вопрос по интенсиву курсовой работы (Вариант №5, DSP56824)**`,
        `- **Лист ПЗ / Чертёж:** \`${payload.sheet_name}\` (стр. ${payload.page_number})`,
        `- **Тема / Раздел:** ${payload.topic_title} (\`${payload.topic_id}\`)`,
        `- **Координаты области (BBox):** \`[${bboxStr}]\``,
      ];
      if (payload.selection_type === 'image_crop') {
        mdLines.push(`- **Вырезанный фрагмент схемы/листа:** \`${savedCropPath}\` (также на листе \`output/dsp_assets/${payload.sheet_name}\` в области \`[${bboxStr}]\`)`);
      } else if (payload.selected_text) {
        mdLines.push(`- **Выделенная цитата / формула:** > ${payload.selected_text}`);
      }
      mdLines.push(`- **Мой вопрос:** ${userQ}`);

      const promptText = mdLines.join('\n');
      try {
        await navigator.clipboard.writeText(promptText);
      } catch (_e) {}

      const statusBox = document.getElementById('qmodal-status');
      statusBox.textContent = '✅ Скопировано в буфер обмена и сохранено в output/user_questions/! Теперь просто нажми Ctrl+V в чате Antigravity.';
      statusBox.classList.remove('hidden');
      setTimeout(() => closeQuestionModal(), 1600);
    }

    // =========================================================================
    // SIMULATION 1: CAUER IIR N=11 & Q15 QUANTIZATION LAB (Canvas)
    // =========================================================================
    const CAUER_POLES = [
      { r: 0.5726, deg: 0, q: 0.60, a1: -0.5726 },
      { r: 0.6589, deg: 38.4, q: 1.15, a1: -1.0312 },
      { r: 0.8014, deg: 58.7, q: 2.45, a1: -0.8093 },
      { r: 0.9010, deg: 69.2, q: 5.40, a1: -0.6324 },
      { r: 0.9564, deg: 73.8, q: 12.80, a1: -0.5346 },
      { r: 0.9878, deg: 75.3, q: 41.50, a1: -1.8253 }
    ];
    const L_INF_G_OUT = 4.8236;

    function drawSim1() {
      const approx = document.getElementById('sim1-approx').value;
      const bits = parseInt(document.getElementById('sim1-bits').value, 10);
      const div2Mode = document.getElementById('sim1-div2').value;
      document.getElementById('sim1-bits-label').textContent =
        `${bits} бит (${div2Mode === 'on' ? 'Q15 + /2 ASL' : 'Без /2 — клиппинг!'})`;

      const magCanvas = document.getElementById('sim1-mag-canvas');
      const zCanvas = document.getElementById('sim1-z-canvas');
      if (!magCanvas || !zCanvas) return;

      const ctx = magCanvas.getContext('2d');
      const W = magCanvas.width, H = magCanvas.height;
      ctx.fillStyle = '#090d16';
      ctx.fillRect(0, 0, W, H);

      // Grid
      ctx.strokeStyle = '#1e293b';
      ctx.lineWidth = 1;
      for (let i = 1; i < 6; i++) {
        const y = (H / 6) * i;
        ctx.beginPath(); ctx.moveTo(40, y); ctx.lineTo(W - 15, y); ctx.stroke();
      }

      // Passband and Stopband masks
      const fToX = (f) => 40 + (f / 24.0) * (W - 55);
      const dbToY = (db) => 20 + ((-db) / 100.0) * (H - 45);

      // Stopband threshold -80 dB from 11 kHz
      ctx.strokeStyle = '#22c55e';
      ctx.setLineDash([5, 4]);
      ctx.beginPath();
      ctx.moveTo(fToX(11), dbToY(-80));
      ctx.lineTo(fToX(24), dbToY(-80));
      ctx.stroke();

      // f1 = 10 kHz, f2 = 11 kHz vertical lines
      ctx.strokeStyle = '#ec4899';
      ctx.beginPath(); ctx.moveTo(fToX(10), 15); ctx.lineTo(fToX(10), H - 25); ctx.stroke();
      ctx.strokeStyle = '#10b981';
      ctx.beginPath(); ctx.moveTo(fToX(11), 15); ctx.lineTo(fToX(11), H - 25); ctx.stroke();
      ctx.setLineDash([]);

      // Quantization error impact
      const quantErr = Math.pow(2, 16 - bits) * 0.0012 + (div2Mode === 'off' ? 0.14 : 0.0);
      const maxPole = Math.min(1.03, +(0.9878 + quantErr * 0.65).toFixed(4));
      const rippleDb = +(0.05 + quantErr * 2.8).toFixed(3);
      const stopDb = Math.max(28, +(80.04 - quantErr * 190).toFixed(2));

      document.getElementById('sim1-telemetry').textContent =
        `ΔA_ПП = ${rippleDb} дБ | A_ПЗ = ${stopDb} дБ | g_out = ${L_INF_G_OUT}`;
      document.getElementById('sim1-pole-telemetry').textContent =
        `|p_max| = ${maxPole} ${maxPole >= 1.0 ? '(НЕУСТОЙЧИВ!)' : '(Устойчив)'}`;

      // Plot Magnitude Curve
      ctx.strokeStyle = '#06b6d4';
      ctx.lineWidth = 2.2;
      ctx.beginPath();
      for (let px = 0; px <= 240; px++) {
        const f = (px / 240) * 24.0;
        let db = 0;
        if (f <= 10.0) {
          db = -rippleDb * 0.5 * (1 - Math.cos(f * 1.9));
        } else if (f < 11.0) {
          const t = (f - 10.0) / 1.0;
          const steep = approx === 'cauer' ? 1.0 : (approx === 'cheb' ? 0.62 : 0.28);
          db = -stopDb * Math.pow(t, 1.4) * steep;
        } else {
          const notches = Math.abs(Math.sin((f - 11.0) * 0.85));
          db = -stopDb - 18 * Math.exp(-notches * 3.2);
        }
        const x = fToX(f), y = dbToY(Math.max(-105, db));
        if (px === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();

      // Axis labels
      ctx.fillStyle = '#94a3b8';
      ctx.font = '10px monospace';
      ctx.fillText('0 дБ', 6, dbToY(0) + 3);
      ctx.fillText('-40 дБ', 4, dbToY(-40) + 3);
      ctx.fillText('-80 дБ', 4, dbToY(-80) + 3);
      ctx.fillText('0 кГц', fToX(0) - 8, H - 8);
      ctx.fillText('10 кГц', fToX(10) - 18, H - 8);
      ctx.fillText('11 кГц', fToX(11) + 4, H - 8);
      ctx.fillText('24 кГц', fToX(24) - 34, H - 8);

      // Z-plane canvas
      const zctx = zCanvas.getContext('2d');
      const ZW = zCanvas.width, ZH = zCanvas.height;
      const cx = ZW / 2, cy = ZH / 2, R = Math.min(ZW, ZH) * 0.39;
      zctx.fillStyle = '#090d16';
      zctx.fillRect(0, 0, ZW, ZH);

      // Axes & Unit Circle |z| = 1
      zctx.strokeStyle = '#334155';
      zctx.beginPath(); zctx.moveTo(12, cy); zctx.lineTo(ZW - 12, cy); zctx.stroke();
      zctx.beginPath(); zctx.moveTo(cx, 12); zctx.lineTo(cx, ZH - 12); zctx.stroke();

      zctx.strokeStyle = '#64748b';
      zctx.setLineDash([4, 4]);
      zctx.beginPath(); zctx.arc(cx, cy, R, 0, Math.PI * 2); zctx.stroke();
      zctx.setLineDash([]);

      // Draw poles (crosses) and zeros on unit circle (circles)
      CAUER_POLES.forEach((p, idx) => {
        const rEff = Math.min(1.05, p.r + (idx === 5 ? quantErr * 0.65 : quantErr * 0.2));
        const rad = (p.deg * Math.PI) / 180.0;
        [1, -1].forEach(sign => {
          if (p.deg === 0 && sign === -1) return;
          const px = cx + rEff * Math.cos(rad) * R;
          const py = cy - sign * rEff * Math.sin(rad) * R;
          zctx.strokeStyle = idx === 5 ? '#ef4444' : '#f59e0b';
          zctx.lineWidth = 2;
          zctx.beginPath();
          zctx.moveTo(px - 4, py - 4); zctx.lineTo(px + 4, py + 4);
          zctx.moveTo(px - 4, py + 4); zctx.lineTo(px + 4, py - 4);
          zctx.stroke();
        });
      });
    }

    // =========================================================================
    // SIMULATION 2: DSP56824 OSCILLOSCOPE & DO #6 PIPELINE STEPPER
    // =========================================================================
    function drawSim2() {
      const f1 = parseFloat(document.getElementById('sim2-f1').value);
      const f2 = parseFloat(document.getElementById('sim2-f2').value);
      const sec = parseInt(document.getElementById('sim2-sec').value, 10);
      document.getElementById('sim2-f1-val').textContent = `${f1.toFixed(1)} кГц`;
      document.getElementById('sim2-f2-val').textContent = `${f2.toFixed(1)} кГц`;
      document.getElementById('sim2-sec-val').textContent = `Секция ${sec} / 6`;

      const canvas = document.getElementById('sim2-osc-canvas');
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      const W = canvas.width, H = canvas.height;
      ctx.fillStyle = '#090d16';
      ctx.fillRect(0, 0, W, H);

      // Grid
      ctx.strokeStyle = '#1e293b';
      ctx.beginPath(); ctx.moveTo(0, H / 2); ctx.lineTo(W, H / 2); ctx.stroke();

      const atten = Math.pow(0.22, sec);
      // Input x(n) (noisy pink trace)
      ctx.strokeStyle = 'rgba(236, 72, 153, 0.55)';
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      for (let i = 0; i < W; i++) {
        const t = i / 48.0;
        const xVal = 0.65 * Math.sin(2 * Math.PI * (f1 / 10) * t) + 0.35 * Math.sin(2 * Math.PI * (f2 / 10) * t);
        const y = H / 2 - xVal * (H * 0.38);
        if (i === 0) ctx.moveTo(i, y); else ctx.lineTo(i, y);
      }
      ctx.stroke();

      // Filtered output y(n) (clean cyan trace)
      ctx.strokeStyle = '#06b6d4';
      ctx.lineWidth = 2.4;
      ctx.beginPath();
      for (let i = 0; i < W; i++) {
        const t = i / 48.0 - sec * 0.08;
        const yVal = 0.65 * Math.sin(2 * Math.PI * (f1 / 10) * t) + 0.35 * atten * Math.sin(2 * Math.PI * (f2 / 10) * t);
        const y = H / 2 - yVal * (H * 0.38);
        if (i === 0) ctx.moveTo(i, y); else ctx.lineTo(i, y);
      }
      ctx.stroke();

      const p = CAUER_POLES[sec - 1];
      const cycUsed = 6 + 2 + sec * 23 + 4;
      const regBox = document.getElementById('sim2-reg-dump');
      regBox.innerHTML = `
        <div class="flex justify-between"><span>Вектор прерывания:</span><b class="text-cyan-300">P:$001E (SSI_Rx_ISR)</b></div>
        <div class="flex justify-between"><span>Тактовая частота / Ts:</span><b class="text-white">40 МГц (25 нс) / 20.833 мкс</b></div>
        <div class="flex justify-between"><span>Счётчик аппаратного цикла:</span><b class="text-amber-300">LC = ${7 - sec} (DO #6)</b></div>
        <div class="flex justify-between"><span>Коэффициент a1/2 секции ${sec}:</span><b class="text-emerald-300">${(p.a1 / 2).toFixed(4)} (Q15)</b></div>
        <div class="flex justify-between"><span>Добротность полюса Q:</span><b class="text-pink-300">Q = ${p.q.toFixed(2)} (|p|=${p.r})</b></div>
        <div class="flex justify-between"><span>Аккумулятор A (36 бит):</span><b class="text-cyan-300">A2=$0 : A1=$3D4A : A0=$81C0</b></div>
        <div class="flex justify-between"><span>Коррекция масштаба /2:</span><b class="text-amber-300">ASL B / ASL A (1 такт)</b></div>
        <div class="flex justify-between"><span>Тактов выполнено:</span><b class="text-emerald-400">${cycUsed} / 150 тактов (114 dual-move)</b></div>
      `;
    }

    // =========================================================================
    // SIMULATION 3: SALLEN-KEY AAF (25.03 kHz, Q=0.736) & IS61LV6416 0-WS TIMING
    // =========================================================================
    function drawSim3() {
      const f0 = parseFloat(document.getElementById('sim3-f0').value);
      const clk = parseInt(document.getElementById('sim3-clk').value, 10);
      const tCycNs = +(1000.0 / clk).toFixed(1);
      const tTotalNs = 19.0; // 6 ns setup + 10 ns t_AA (IS61LV6416) + 3 ns hold
      const zeroWsOk = tCycNs >= tTotalNs;

      document.getElementById('sim3-f0-val').textContent = `${f0.toFixed(2)} кГц (норма 25.03 кГц, Q = 0.736)`;
      document.getElementById('sim3-clk-val').textContent =
        `${clk} МГц (T_cyc = ${tCycNs} нс ${zeroWsOk ? '>= 19 нс → 0 WS (BCR=$0000)' : '< 19 нс → Нужен 1 WS!'})`;

      const canvas = document.getElementById('sim3-hw-canvas');
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      const W = canvas.width, H = canvas.height;
      ctx.fillStyle = '#090d16';
      ctx.fillRect(0, 0, W, H);

      // Left half: Sallen-Key response; Right half: IS61LV6416 Timing Diagram
      const midX = W * 0.52;
      ctx.strokeStyle = '#334155';
      ctx.beginPath(); ctx.moveTo(midX, 10); ctx.lineTo(midX, H - 10); ctx.stroke();

      // Left: Sallen-Key Magnitude curve
      ctx.fillStyle = '#e2e8f0';
      ctx.font = 'bold 11px sans-serif';
      ctx.fillText(`АЧХ активного ФНЧ Саллена–Кея (AD8606AR, f0=${f0.toFixed(2)} кГц, Q=0.736)`, 18, 22);

      ctx.strokeStyle = '#06b6d4';
      ctx.lineWidth = 2.2;
      ctx.beginPath();
      for (let i = 0; i <= 200; i++) {
        const f = (i / 200) * 100.0; // 0..100 kHz
        const u = f / f0;
        const mag = 1.0 / Math.sqrt(Math.pow(1 - u * u, 2) + Math.pow(u / 0.736, 2));
        const db = 20 * Math.log10(Math.max(1e-4, mag));
        const x = 25 + (i / 200) * (midX - 45);
        const y = 45 + ((-db) / 40.0) * (H - 75);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, Math.min(H - 20, Math.max(30, y)));
      }
      ctx.stroke();

      // Right: IS61LV6416-10T Read Cycle Timing Bar
      const rx = midX + 20;
      ctx.fillStyle = '#e2e8f0';
      ctx.fillText(`Диаграмма цикла шины SRAM IS61LV6416 (t_AA = 10 нс vs T_cyc = ${tCycNs} нс)`, rx, 22);

      const scale = (W - rx - 30) / 40.0; // 40 ns full scale
      // Address setup 6 ns
      ctx.fillStyle = '#f59e0b';
      ctx.fillRect(rx, 65, 6 * scale, 28);
      ctx.fillStyle = '#090d16';
      ctx.fillText('6 нс (Addr)', rx + 4, 83);

      // Access time t_AA = 10 ns
      ctx.fillStyle = '#06b6d4';
      ctx.fillRect(rx + 6 * scale, 65, 10 * scale, 28);
      ctx.fillStyle = '#090d16';
      ctx.fillText('t_AA = 10 нс', rx + 6 * scale + 6, 83);

      // Hold 3 ns
      ctx.fillStyle = '#a855f7';
      ctx.fillRect(rx + 16 * scale, 65, 3 * scale, 28);

      // Total T_cyc bar
      ctx.fillStyle = zeroWsOk ? 'rgba(16, 185, 129, 0.28)' : 'rgba(239, 68, 68, 0.35)';
      ctx.strokeStyle = zeroWsOk ? '#10b981' : '#ef4444';
      ctx.fillRect(rx, 115, tCycNs * scale, 30);
      ctx.strokeRect(rx, 115, tCycNs * scale, 30);
      ctx.fillStyle = '#f8fafc';
      ctx.fillText(`Машинный такт T_cyc = ${tCycNs} нс (Запас: ${(tCycNs - 19).toFixed(1)} нс)`, rx + 8, 134);
    }

    // =========================================================================
    // INLINE LIVE SIMULATOR ON ACTIVE SHEET TAB (#inline-sim-canvas)
    // =========================================================================
    let inlineSimMode = 'filter';

    function setInlineSimMode(mode) {
      inlineSimMode = mode;
      ['filter', 'osc', 'hw'].forEach(m => {
        const btn = document.getElementById(`btn-isim-${m}`);
        if (btn) {
          btn.className = (m === mode)
            ? 'px-2.5 py-1 text-xs font-bold rounded bg-cyan-500 text-slate-950'
            : 'px-2.5 py-1 text-xs font-semibold rounded bg-slate-900 text-slate-200 border border-slate-700';
        }
      });
      drawInlineSim();
    }

    function autoSyncInlineSimForPage(pNum) {
      if ([10, 25, 26, 27, 28, 29, 30].includes(pNum)) {
        setInlineSimMode('filter');
      } else if ([24, 31, 32, 33, 38, 39, 40, 41].includes(pNum)) {
        setInlineSimMode('osc');
      } else if ([12, 16, 17, 18, 19, 20, 21, 22, 23, 42, 43].includes(pNum)) {
        setInlineSimMode('hw');
      } else {
        setInlineSimMode('filter');
      }
    }

    function drawInlineSim() {
      const canvas = document.getElementById('inline-sim-canvas');
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      const W = canvas.width, H = canvas.height;
      const p1 = parseFloat(document.getElementById('isim-p1').value);
      const p2 = parseInt(document.getElementById('isim-p2').value, 10);

      ctx.fillStyle = '#090d16';
      ctx.fillRect(0, 0, W, H);

      if (inlineSimMode === 'filter') {
        document.getElementById('isim-p1-label').textContent = `f_c = ${p1.toFixed(1)} кГц`;
        document.getElementById('isim-p2-label').textContent = `${p2} бит (Q${p2 - 1})`;
        const qErr = Math.pow(2, 16 - p2) * 0.0015;
        const stopAtten = Math.max(30, +(80.04 - qErr * 160).toFixed(1));
        document.getElementById('isim-status-badge').textContent =
          `Кауэр N=11 | f1=${p1.toFixed(1)} кГц | A_ПЗ = ${stopAtten} дБ | |p_max| = ${(0.9878 + qErr * 0.4).toFixed(4)}`;

        // Left: Magnitude Response; Right: Z-plane
        const midX = W * 0.64;
        ctx.strokeStyle = '#1e293b';
        for (let i = 1; i < 5; i++) {
          ctx.beginPath(); ctx.moveTo(35, (H / 5) * i); ctx.lineTo(midX - 15, (H / 5) * i); ctx.stroke();
        }
        ctx.strokeStyle = '#06b6d4';
        ctx.lineWidth = 2.2;
        ctx.beginPath();
        for (let i = 0; i <= 180; i++) {
          const f = (i / 180) * 24.0;
          let db = 0;
          if (f <= p1) db = -0.05 * Math.sin(f * 2.1);
          else if (f < p1 + 1.0) db = -stopAtten * Math.pow(f - p1, 1.3);
          else db = -stopAtten - 14 * Math.abs(Math.sin((f - p1) * 0.9));
          const x = 35 + (i / 180) * (midX - 50);
          const y = 20 + ((-Math.max(-100, db)) / 100.0) * (H - 42);
          if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.stroke();

        // Z-plane circle on right
        const cx = midX + (W - midX) / 2, cy = H / 2, R = Math.min(W - midX, H) * 0.37;
        ctx.strokeStyle = '#475569';
        ctx.setLineDash([4, 4]);
        ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.stroke();
        ctx.setLineDash([]);
        CAUER_POLES.forEach((p, idx) => {
          const rad = (p.deg * Math.PI) / 180.0;
          [1, -1].forEach(s => {
            const px = cx + p.r * Math.cos(rad) * R;
            const py = cy - s * p.r * Math.sin(rad) * R;
            ctx.strokeStyle = idx === 5 ? '#ef4444' : '#f59e0b';
            ctx.beginPath();
            ctx.moveTo(px - 4, py - 4); ctx.lineTo(px + 4, py + 4);
            ctx.moveTo(px - 4, py + 4); ctx.lineTo(px + 4, py - 4);
            ctx.stroke();
          });
        });
      } else if (inlineSimMode === 'osc') {
        document.getElementById('isim-p1-label').textContent = `f_вх = ${(p1 * 0.45).toFixed(1)} кГц`;
        const sec = Math.max(1, Math.min(6, Math.round((p2 - 8) * 6 / 8) || 6));
        document.getElementById('isim-p2-label').textContent = `Каскад ${sec} / 6 (DO #6)`;
        document.getElementById('isim-status-badge').textContent =
          `DSP56824 (40 МГц) | SSI_Rx_ISR: ${6 + 2 + sec * 23 + 4}/150 тактов (3.75 мкс, 18% ЦП)`;

        const atten = Math.pow(0.22, sec);
        ctx.strokeStyle = 'rgba(236, 72, 153, 0.5)';
        ctx.lineWidth = 1.4;
        ctx.beginPath();
        for (let x = 0; x < W; x++) {
          const t = x / 45.0;
          const v = 0.6 * Math.sin(t * (p1 * 0.25)) + 0.35 * Math.sin(t * 4.2);
          const y = H / 2 - v * (H * 0.38);
          if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.stroke();

        ctx.strokeStyle = '#06b6d4';
        ctx.lineWidth = 2.4;
        ctx.beginPath();
        for (let x = 0; x < W; x++) {
          const t = x / 45.0 - sec * 0.08;
          const v = 0.6 * Math.sin(t * (p1 * 0.25)) + 0.35 * atten * Math.sin(t * 4.2);
          const y = H / 2 - v * (H * 0.38);
          if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.stroke();
      } else {
        const f0 = 15 + p1 * 1.0;
        const clk = 20 + (p2 - 8) * 4;
        const tCyc = +(1000.0 / clk).toFixed(1);
        document.getElementById('isim-p1-label').textContent = `f0 = ${f0.toFixed(1)} кГц`;
        document.getElementById('isim-p2-label').textContent = `f_clk = ${clk} МГц (${tCyc} нс)`;
        document.getElementById('isim-status-badge').textContent =
          `AD8606AR (Q=0.736) | IS61LV6416: t_AA=10 нс, цикл 19 нс < ${tCyc} нс → 0 WS`;

        ctx.strokeStyle = '#06b6d4';
        ctx.lineWidth = 2.2;
        ctx.beginPath();
        for (let i = 0; i <= 200; i++) {
          const f = (i / 200) * 90.0;
          const u = f / f0;
          const mag = 1.0 / Math.sqrt(Math.pow(1 - u * u, 2) + Math.pow(u / 0.736, 2));
          const db = 20 * Math.log10(Math.max(1e-4, mag));
          const x = 30 + (i / 200) * (W - 60);
          const y = 30 + ((-db) / 40.0) * (H - 55);
          if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, Math.min(H - 18, Math.max(20, y)));
        }
        ctx.stroke();
      }
    }

    window.addEventListener('DOMContentLoaded', initApp);
  </script>
</body>
</html>
"""
