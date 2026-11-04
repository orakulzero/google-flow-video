# -*- coding: utf-8 -*-
"""
Almanac Editorial Daylight (1280x720 @ 24 fps) Zero-Jitter Mathematical & Geometric
Animation Engine for the 16-Chapter Machine Learning (`MOiAD`) Video Course.
"""

from __future__ import annotations

import io
import math
from typing import Any, Dict, List, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Hallmark v2.0.0 Almanac Daylight Palette (RGB)
COL_PAPER = (246, 248, 251)
COL_SHEET = (255, 255, 255)
COL_INK = (24, 33, 47)
COL_INK_2 = (62, 76, 99)
COL_MUTED = (74, 88, 110)
COL_RULE = (218, 226, 237)
COL_RULE_STRONG = (186, 199, 218)
COL_COBALT = (37, 99, 235)
COL_COBALT_WASH = (238, 244, 255)
COL_EMERALD = (5, 150, 105)
COL_EMERALD_WASH = (236, 253, 245)
COL_AMBER = (217, 119, 6)
COL_AMBER_WASH = (255, 251, 235)
COL_ROSE = (225, 29, 72)
COL_ROSE_WASH = (255, 241, 242)


def load_moiad_fonts() -> Dict[str, ImageFont.FreeTypeFont]:
    """Load crisp Windows TrueType fonts for the 1280x720 HD canvas."""
    res: Dict[str, Any] = {}
    specs = [
        ("hdr_b", "C:/Windows/Fonts/segoeuib.ttf", 16),
        ("hdr_m", "C:/Windows/Fonts/segoeuib.ttf", 14),
        ("hdr_s", "C:/Windows/Fonts/segoeui.ttf", 13),
        ("pill_b", "C:/Windows/Fonts/segoeuib.ttf", 12),
        ("pill_s", "C:/Windows/Fonts/segoeuib.ttf", 11),
        ("pill_10", "C:/Windows/Fonts/segoeuib.ttf", 10),
        ("pill_95", "C:/Windows/Fonts/segoeuib.ttf", 9.5),
        ("card_t", "C:/Windows/Fonts/segoeuib.ttf", 14),
        ("eq_b", "C:/Windows/Fonts/consolab.ttf", 13),
        ("body", "C:/Windows/Fonts/segoeui.ttf", 13),
        ("body_s", "C:/Windows/Fonts/segoeui.ttf", 12),
        ("mono_b", "C:/Windows/Fonts/consolab.ttf", 13),
        ("sub_r", "C:/Windows/Fonts/segoeui.ttf", 18),
        ("sub_b", "C:/Windows/Fonts/segoeuib.ttf", 18),
    ]
    for key, fpath, sz in specs:
        try:
            res[key] = ImageFont.truetype(fpath, sz)
        except Exception:
            res[key] = ImageFont.load_default()
    return res


_WRAP_CACHE: Dict[Tuple[str, int, int], List[str]] = {}
_WIDTH_CACHE: Dict[Tuple[str, int], int] = {}
_PHASE_CHROME_CACHE: Dict[Tuple[str, int], Image.Image] = {}
_DYNAMIC_FONT_CACHE: Dict[Tuple[str, float], ImageFont.FreeTypeFont] = {}


def _get_dynamic_font(path: str, size: float) -> ImageFont.FreeTypeFont:
    key = (path, size)
    f = _DYNAMIC_FONT_CACHE.get(key)
    if f is None:
        try:
            f = ImageFont.truetype(path, size)
        except Exception:
            f = ImageFont.load_default()
        _DYNAMIC_FONT_CACHE[key] = f
    return f


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: Any) -> int:
    key = (text, id(font))
    w = _WIDTH_CACHE.get(key)
    if w is None:
        tb = draw.textbbox((0, 0), text, font=font)
        w = int(tb[2] - tb[0])
        _WIDTH_CACHE[key] = w
    return w


def _fit_single_line(
    draw: ImageDraw.ImageDraw, text: str, font_primary: Any, font_fallback: Any, max_w: int
) -> Tuple[str, Any]:
    """Ensure a single-line title or header fits within `max_w` without mid-word clipping.
    Supports a list/tuple of fallback fonts or automatic stepping down to 10pt/9.5pt.
    """
    if _text_width(draw, text, font_primary) <= max_w:
        return text, font_primary

    fallbacks = list(font_fallback) if isinstance(font_fallback, (list, tuple)) else [font_fallback]
    for fb in fallbacks:
        if _text_width(draw, text, fb) <= max_w:
            return text, fb

    last_fnt = fallbacks[-1]
    fnt_path = getattr(last_fnt, "path", None)
    if fnt_path:
        for extra_sz in (10.0, 9.5, 9.0, 8.5, 8.0):
            extra_fnt = _get_dynamic_font(fnt_path, extra_sz)
            if _text_width(draw, text, extra_fnt) <= max_w:
                return text, extra_fnt
            last_fnt = extra_fnt

    words = text.split()
    cur = ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if _text_width(draw, cand, last_fnt) <= max_w:
            cur = cand
        else:
            break
    if not cur:
        for k in range(len(text), 0, -1):
            cand = text[:k].rstrip(" :,;-–—") + "…"
            if _text_width(draw, cand, last_fnt) <= max_w:
                cur = cand
                break
        if not cur:
            cur = text[:1]
    else:
        cur = cur.rstrip(":,;-–—")
    return cur, last_fnt


# Typographic trailing prepositions and conjunctions that must not dangle at line ends
_DANGLING_WORDS = {
    "\u0438", "\u0430", "\u0432", "\u0441", "\u043a", "\u0443", "\u043e", "\u043d\u0430",
    "\u043f\u043e", "\u0438\u0437", "\u0437\u0430", "\u043e\u0442", "\u0434\u043e",
    "\u043f\u0440\u0438", "\u0434\u043b\u044f", "\u0438\u043b\u0438", "\u0447\u0442\u043e",
    "\u043a\u0430\u043a", "\u043d\u043e", "\u043f\u043e\u0434", "\u043d\u0430\u0434",
    "\u0431\u0435\u0437", "\u043f\u0440\u043e", "\u043d\u0435", "\u043d\u0438",
    "\u0436\u0435", "\u0431\u044b", "\u043b\u0438", "\u0442\u043e", "\u0432\u043e",
    "\u0441\u043e", "\u043a\u043e", "\u043e\u0431", "\u043e\u0431\u043e",
    "\u043f\u043e\u0447\u0435\u043c\u0443", "\u0434\u0430\u043b\u0435\u043a\u043e",
    "\u043e\u0447\u0435\u043d\u044c", "\u043f\u043e\u0447\u0442\u0438", "\u0442\u043e\u043b\u044c\u043a\u043e",
    "a", "an", "the", "of", "in", "to", "for", "and", "or", "with", "at", "by", "on",
    "=", "+", "-", "\u2014", "\u2013",
}


def _wrap_lines(draw: ImageDraw.ImageDraw, text: str, font: Any, max_w: int) -> List[str]:
    key = (text, id(font), max_w)
    cached = _WRAP_CACHE.get(key)
    if cached is not None:
        return cached
    words = text.split()
    if not words:
        return []
    lines: List[str] = []
    idx = 0
    while idx < len(words):
        cur_words = [words[idx]]
        idx += 1
        while idx < len(words):
            cand = " ".join(cur_words + [words[idx]])
            if _text_width(draw, cand, font) <= max_w:
                cur_words.append(words[idx])
                idx += 1
            else:
                break
        # Migrate trailing dangling prepositions/conjunctions to next line
        if idx < len(words):
            while len(cur_words) > 1 and cur_words[-1].lower().rstrip(",;:.!?-—–") in _DANGLING_WORDS:
                cur_words.pop()
                idx -= 1
        lines.append(" ".join(cur_words))
    _WRAP_CACHE[key] = lines
    return lines


def _configure_ax(ax: Any, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_facecolor("#FFFFFF")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("#64748B")
        ax.spines[sp].set_linewidth(1.3)
    ax.grid(True, linestyle="--", linewidth=0.8, color="#E2E8F0", alpha=0.9)
    ax.set_title(title, fontsize=10.0, fontweight="bold", color="#0F172A", pad=8)
    ax.set_xlabel(xlabel, fontsize=9.2, fontweight="semibold", color="#334155")
    ax.set_ylabel(ylabel, fontsize=9.0, fontweight="semibold", color="#334155", labelpad=2.0)
    ax.tick_params(colors="#334155", labelsize=8.5, width=1.1, length=3.0, pad=2.0)


def _populate_backdrop_pr1_pr2(mode: str, ax1: Any, ax2: Any) -> None:
    """Draw static coordinate reference geometry for Parts I & II (PR1 & PR2)."""
    rng = np.random.default_rng(42)
    if mode == "stevens_scales":
        _configure_ax(ax1, "Ловушка Label Encoding (1, 2, 3)", "Код локации ЦОД", "Задержка (мс)")
        ax1.set_xlim(0.4, 3.6)
        ax1.set_ylim(10, 95)
        ax1.set_xticks([1, 2, 3], ["1: СПб", "2: МСК", "3: Франкф."])
        for c_i, ym, col in [(1, 72, "#E11D48"), (2, 28, "#2563EB"), (3, 46, "#059669")]:
            ax1.scatter(c_i + rng.normal(0, 0.06, 18), ym + rng.normal(0, 6, 18), s=22, color=col, alpha=0.75)
        _configure_ax(ax2, "Ортогональный базис One-Hot (0/1)", "Ось e1 (DC-SPb)", "Ось e2 (DC-Moscow)")
        ax2.set_xlim(-0.15, 1.25)
        ax2.set_ylim(-0.15, 1.25)
        ax2.scatter([1, 0, 0], [0, 1, 0], s=95, color=["#E11D48", "#2563EB", "#059669"], zorder=5)
        ax2.annotate("DC-SPb (1,0,0)", (0.68, 0.08), fontsize=8.8, fontweight="bold", color="#E11D48")
        ax2.annotate("DC-MSK (0,1,0)", (0.06, 1.03), fontsize=8.8, fontweight="bold", color="#2563EB")
        ax2.annotate("DC-FRA (0,0,1)", (0.06, 0.12), fontsize=8.8, fontweight="bold", color="#059669")

    elif mode == "outlier_masking":
        _configure_ax(ax1, "Маскировка 3 сигма vs забор IQR", "Значение метрики / задержки", "Плотность ядер")
        x = np.linspace(0, 120, 300)
        y = np.exp(-0.5 * ((x - 22.0) / 8.5) ** 2)
        ax1.plot(x, y, color="#2563EB", lw=2.0, label="\u042f\u0434\u0440\u043e \u043f\u0430\u0440\u043a\u0430 (\u043c\u0435\u0434. 20.6)")
        ax1.fill_between(x, 0, y, color="#DBEAFE", alpha=0.6)
        ax1.axvline(48.0, color="#059669", lw=2.2, ls="-", label="\u0417\u0430\u0431\u043e\u0440 IQR (Q3+1.5*IQR)")
        ax1.set_xlim(0, 120)
        ax1.set_ylim(0, 1.18)
        ax1.legend(loc="upper left", fontsize=6.6, frameon=True, handlelength=1.2, handletextpad=0.4, borderpad=0.3, framealpha=0.92)
        _configure_ax(ax2, "Винзоризация 1%–99% (хвост задержек)", "Индекс сервера (ранжир.)", "Задержка (мс)")
        idx = np.linspace(1, 1000, 120)
        raw_lat = 20.58 + 18.0 * np.exp((idx - 650) / 140.0)
        clamped = np.clip(raw_lat, 6.39, 180.0)
        ax2.plot(idx, raw_lat, color="#E11D48", lw=1.6, ls="--", label="Сырой хвост (до 1999.8 мс)")
        ax2.plot(idx, clamped, color="#059669", lw=2.2, label="После Winsorize [1%..99%]")
        ax2.set_xlim(0, 1000)
        ax2.set_ylim(0, 260)
        ax2.legend(loc="upper left", fontsize=7.2)

    elif mode == "missing_mechanisms":
        _configure_ax(ax1, "Восстановление 35 пропусков RAM", "Шаг времени t (часы)", "Утилизация RAM (%)")
        t = np.linspace(0, 48, 96)
        clean = 55.0 + 18.0 * np.sin(2 * np.pi * t / 24.0) + 5.0 * np.cos(2 * np.pi * t / 12.0)
        ax1.plot(t, clean, color="#CBD5E1", lw=1.5, ls=":", label="Истинный профиль")
        mean_line = np.where((t > 14) & (t < 26), 55.0, clean)
        ax1.plot(t, mean_line, color="#E11D48", lw=1.6, ls="--", label="Подстановка среднего (полка)")
        ax1.axvspan(14, 26, color="#FEF3C7", alpha=0.55, label="Зона пропуска NaN")
        ax1.set_xlim(0, 48)
        ax1.set_ylim(20, 92)
        ax1.legend(loc="lower left", fontsize=7.0)
        _configure_ax(ax2, "Структура пропусков ПР1 по столбцам", "Признак датасета ЦОД", "Число пропусков NaN")
        cols = ["CPU", "ЦОД", "RAM", "Отклик", "Статус"]
        vals = [40, 39, 35, 30, 27]
        ax2.bar(cols, vals, color=["#2563EB", "#059669", "#D97706", "#6366F1", "#E11D48"], width=0.55)
        ax2.set_ylim(0, 48)

    elif mode == "mahalanobis_pca":
        _configure_ax(ax1, "Эллипс Махаланобиса vs евклидов круг", "Загрузка CPU (%)", "Загрузка RAM (%)")
        u_pts = rng.normal(45.5, 14.0, 140)
        v_pts = 0.82 * u_pts + rng.normal(8.0, 6.5, 140)
        ax1.scatter(u_pts, v_pts, s=16, color="#3B82F6", alpha=0.55, label="Штатные узлы ЦОД")
        ax1.scatter([78, 24], [20, 82], s=58, color="#E11D48", zorder=6, label="Скрытые аномалии")
        ang = np.linspace(0, 2 * np.pi, 120)
        ax1.plot(45.5 + 26 * np.cos(ang), 45.5 + 26 * np.sin(ang), color="#94A3B8", ls="--", lw=1.4, label="Евклидов круг")
        el_x = 45.5 + 28.0 * np.cos(ang) - 9.0 * np.sin(ang)
        el_y = 45.5 + 23.0 * np.cos(ang) + 9.0 * np.sin(ang)
        ax1.plot(el_x, el_y, color="#059669", lw=2.0, label="Эллипс Махаланобиса")
        ax1.set_xlim(5, 98)
        ax1.set_ylim(5, 98)
        ax1.set_aspect("equal", adjustable="box")
        ax1.legend(loc="upper left", fontsize=6.8)
        _configure_ax(ax2, "Аномалии и нагрузка по филиалам ЦОД", "Филиал ЦОД", "Критичные узлы / Аномалии")
        dcs = ["SPb", "MSK", "AMS", "FRA"]
        crit = [13, 11, 9, 8]
        ax2.bar(dcs, crit, color=["#E11D48", "#D97706", "#2563EB", "#059669"], width=0.52)
        ax2.set_ylim(0, 16)
    elif mode == "weibull_hazard":
        _configure_ax(ax1, "Плотность f(x) = |x(p0-x)sin(p1*x)| / C", "Аргумент x в [0, 4]", "Плотность p(x)")
        x = np.linspace(0, 4, 240)
        f1 = np.abs(x * (1.0 - x) * np.sin(1.0 * x)) / 4.786
        f2 = np.abs(x * (-1.0 - x) * np.sin(np.pi * x)) / 7.112
        ax1.plot(x, f1, color="#2563EB", lw=2.2, label="Набор 1: p0=1, p1=1 (C=4.786)")
        ax1.fill_between(x, 0, f1, color="#DBEAFE", alpha=0.45)
        ax1.plot(x, f2, color="#059669", lw=1.8, ls="--", label="Набор 2: p0=-1, p1=pi (C=7.112)")
        ax1.set_xlim(0, 4)
        ax1.set_ylim(0, 0.85)
        ax1.legend(loc="upper left", fontsize=7.0)
        _configure_ax(ax2, "Метод обратных функций X = F^-1(U)", "Квантиль x", "Накопленная вер. F(x)")
        cdf = np.cumsum(f1)
        cdf = cdf / cdf[-1]
        ax2.plot(x, cdf, color="#2563EB", lw=2.3, label="Кумулятивная F(x)")
        ax2.set_xlim(0, 4)
        ax2.set_ylim(0, 1.05)
        ax2.legend(loc="lower right", fontsize=7.2)

    elif mode == "goodness_of_fit":
        _configure_ax(ax1, "Гистограмма N=1000 и N(5, 1.2^2)", "Значение X", "Плотность / Частота")
        xg = np.linspace(1.2, 8.8, 200)
        yg = (1.0 / (1.2 * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((xg - 5.0) / 1.2) ** 2)
        bins = np.linspace(1.6, 8.4, 15)
        bc = 0.5 * (bins[:-1] + bins[1:])
        bh = (1.0 / (1.2 * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((bc - 5.0) / 1.2) ** 2) * rng.uniform(0.93, 1.07, len(bc))
        ax1.bar(bc, bh, width=0.42, color="#DBEAFE", edgecolor="#3B82F6", label="Выборка N=1000")
        ax1.errorbar(bc, bh, yerr=0.025, fmt="none", ecolor="#1E293B", capsize=2)
        ax1.plot(xg, yg, color="#E11D48", lw=2.2, label="Теор. N(5, 1.2^2)")
        ax1.set_xlim(1.2, 8.8)
        ax1.set_ylim(0, 0.42)
        ax1.legend(loc="upper left", fontsize=7.0, framealpha=0.92)
        _configure_ax(ax2, "Квантильный график QQ-plot (W=0.998)", "Теоретические квантили", "Выборочные квантили")
        q_th = np.linspace(-2.6, 2.6, 45)
        q_em = 5.0 + 1.2 * q_th + rng.normal(0, 0.05, 45)
        ax2.plot([-2.8, 2.8], [5.0 - 1.2 * 2.8, 5.0 + 1.2 * 2.8], color="#E11D48", lw=1.8, ls="--", label="Биссектриса H0")
        ax2.scatter(q_th, q_em, s=20, color="#2563EB", alpha=0.85, label="Квантили (p > 0.12)")
        ax2.set_xlim(-2.8, 2.8)
        ax2.set_ylim(1.5, 8.5)
        ax2.legend(loc="upper left", fontsize=8.4, framealpha=0.92)

    elif mode == "clt_monte_carlo":
        _configure_ax(ax1, "Свертка плотностей ЦПТ: к Гауссу", "Выборочное среднее X_bar_N", "Плотность")
        x = np.linspace(0, 1, 250)
        ax1.plot(x, np.ones_like(x), color="#94A3B8", lw=1.5, ls="--", label="N=1: плоское U(0,1)")
        tri = 2.0 * (0.5 - np.abs(x - 0.5)) * 2.0
        ax1.plot(x, tri, color="#D97706", lw=1.7, label="N=2: треугольник")
        g30 = (1.0 / (0.0527 * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x - 0.5) / 0.0527) ** 2)
        ax1.plot(x, g30, color="#2563EB", lw=2.2, label="N=30..100: купол ЦПТ")
        ax1.set_xlim(0, 1)
        ax1.set_ylim(0, 8.8)
        ax1.legend(loc="upper right", fontsize=8.4, framealpha=0.92)
        _configure_ax(ax2, "Закон 1/sqrt(N): убывание ошибки SE", "Объем выборки N", "Ошибка SE = sigma/sqrt(N)")
        n_arr = np.linspace(1, 100, 150)
        se_arr = 0.2887 / np.sqrt(n_arr)
        ax2.plot(n_arr, se_arr, color="#059669", lw=2.3, label="SE(N) = 0.2887 / sqrt(N)")
        ax2.scatter([1, 5, 10, 30, 100], [0.2887 / math.sqrt(k) for k in (1, 5, 10, 30, 100)], color="#E11D48", s=32, zorder=5)
        ax2.set_xlim(0, 105)
        ax2.set_ylim(0, 0.32)
        ax2.legend(loc="upper right", fontsize=8.4, framealpha=0.92)

    elif mode == "vif_gls":
        _configure_ax(ax1, "Мультиколлинеарность VIF (< 5 норма)", "Признак телеком-тракта", "Фактор VIF")
        f_names = ["Трафик", "Сессии", "Задержка"]
        vifs = [1.505, 1.494, 1.141]
        ax1.bar(f_names, vifs, color=["#2563EB", "#059669", "#D97706"], width=0.48)
        ax1.axhline(5.0, color="#E11D48", lw=1.6, ls="--", label="Критический порог VIF = 5")
        ax1.set_ylim(0, 6.0)
        ax1.legend(loc="upper right", fontsize=8.4, framealpha=0.92)
        _configure_ax(ax2, "Регрессии: OLS vs WLS vs GLS Айткена", "Предиктор x", "Отклик y")
        xp = np.linspace(0.5, 9.5, 12)
        yp = 0.925 * xp + 0.30 + np.array([-0.1, 0.15, -0.2, 0.1, 0.05, -0.15, 0.2, -0.1, 0.35, 0.55, 0.72, 0.85])
        err = np.array([0.2, 0.2, 0.25, 0.2, 0.25, 0.3, 0.3, 0.35, 0.75, 0.95, 1.15, 1.35])
        ax2.errorbar(xp, yp, yerr=err, fmt="o", color="#475569", markersize=4, capsize=2, label="Замеры с ковар. шумом")
        ax2.plot(xp, 0.9600 * xp + 0.1800, color="#E11D48", lw=1.8, ls="--", label="OLS (a=0.9600)")
        ax2.plot(xp, 0.9542 * xp + 0.2047, color="#D97706", lw=1.8, ls="-.", label="WLS (a=0.9542)")
        ax2.plot(xp, 0.9250 * xp + 0.3000, color="#059669", lw=2.3, label="GLS Айткена (a=0.9250)")
        ax2.set_xlim(0, 10)
        ax2.set_ylim(0, 11.5)
        ax2.legend(loc="upper left", fontsize=8.2, framealpha=0.92)


def _populate_backdrop_pr3_pr4(mode: str, ax1: Any, ax2: Any) -> None:
    """Draw static coordinate reference geometry for Parts III & IV (PR3 & PR4)."""
    rng = np.random.default_rng(42)
    if mode == "churn_cost_threshold":
        _configure_ax(ax1, "Плотности Stay (78.6%) и Churn (21.4%)", "Вероятность оттока p_hat", "Плотность")
        p = np.linspace(0, 1, 240)
        d0 = np.exp(-0.5 * ((p - 0.18) / 0.13) ** 2) * 0.786
        d1 = np.exp(-0.5 * ((p - 0.56) / 0.18) ** 2) * 0.45
        ax1.plot(p, d0, color="#2563EB", lw=2.0, label="Лояльные (786 абон.)")
        ax1.fill_between(p, 0, d0, color="#DBEAFE", alpha=0.45)
        ax1.plot(p, d1, color="#E11D48", lw=2.0, label="Отток 21.4% (214 абон.)")
        ax1.fill_between(p, 0, d1, color="#FFE4E6", alpha=0.55)
        ax1.axvline(0.50, color="#94A3B8", ls="--", lw=1.5, label="Наивный порог 0.50")
        ax1.axvline(0.25, color="#059669", ls="-", lw=2.2, label="Оптимум бизнеса tau*=0.25")
        ax1.set_xlim(0, 1)
        ax1.set_ylim(0, 0.92)
        ax1.legend(loc="upper right", fontsize=7.0)
        _configure_ax(ax2, "Компромисс Recall и бизнес-затрат", "Порог решения tau", "Метрика / Норм. затраты")
        rec = 1.0 / (1.0 + np.exp((p - 0.36) / 0.11))
        cost = 0.38 + 0.58 * (p - 0.25) ** 2 / 0.32 + 0.12 * np.maximum(0, 0.25 - p) * 3.0
        ax2.plot(p, rec, color="#059669", lw=2.2, label="Полнота Recall (76.7% при 0.25)")
        ax2.plot(p, cost, color="#E11D48", lw=2.0, ls="--", label="Суммарные потери оператора")
        ax2.set_xlim(0, 1)
        ax2.set_ylim(0, 1.08)
        ax2.legend(loc="upper left", fontsize=7.0)

    elif mode == "svm_rbf_trees":
        _configure_ax(ax1, "Границы: LogReg, Дерево и RBF SVC", "Стаж tenure_months (норм.)", "Платеж monthly_charges")
        x0 = rng.normal(0.62, 0.18, 80)
        y0 = rng.normal(0.42, 0.18, 80)
        x1 = rng.normal(0.28, 0.16, 45)
        y1 = rng.normal(0.72, 0.15, 45)
        ax1.scatter(x0, y0, s=18, color="#2563EB", alpha=0.65, label="Stay (0)")
        ax1.scatter(x1, y1, s=24, color="#E11D48", alpha=0.80, label="Churn (1)")
        xg = np.linspace(0, 1, 100)
        ax1.plot(xg, 0.22 + 0.72 * xg, color="#059669", lw=2.0, label="LogReg (Acc=0.790)")
        ax1.step([0, 0.42, 0.42, 1.0], [0.55, 0.55, 0.82, 0.82], color="#D97706", lw=1.8, ls="--", label="RandomForest")
        ang_r = np.linspace(0, 2 * np.pi, 100)
        ax1.plot(0.28 + 0.20 * np.cos(ang_r), 0.72 + 0.18 * np.sin(ang_r), color="#E11D48", lw=1.7, ls=":", label="RBF SVC ядро")
        ax1.set_xlim(0, 1)
        ax1.set_ylim(0, 1)
        ax1.legend(loc="lower left", fontsize=6.2, frameon=True, framealpha=0.92)
        _configure_ax(ax2, "ROC-кривые 6 классификаторов ПР3", "Доля ложных тревог (FPR)", "Полнота (TPR / Recall)")
        fpr = np.linspace(0, 1, 120)
        ax2.plot(fpr, fpr, color="#94A3B8", ls=":", lw=1.3)
        ax2.plot(fpr, fpr ** 0.36, color="#2563EB", lw=2.2, label="LogReg / RF (AUC=0.75)")
        ax2.plot(fpr, fpr ** 0.44, color="#059669", lw=1.9, label="GaussianNB (Recall=51.2%)")
        ax2.plot(fpr, fpr ** 0.52, color="#D97706", lw=1.6, ls="--", label="SVC RBF / KNN")
        ax2.set_xlim(0, 1)
        ax2.set_ylim(0, 1.02)
        ax2.legend(loc="lower right", fontsize=8.4, framealpha=0.92)

    elif mode == "kmeans_vs_dbscan":
        _configure_ax(ax1, "Сегментация k-Means (k=4, s=0.412)", "Стаж абонента (норм.)", "Ежемесячный чек (норм.)")
        centers = [(0.22, 0.25, "#2563EB", "Базовые"), (0.76, 0.32, "#059669", "Стабильные"), (0.78, 0.78, "#D97706", "Премиум"), (0.22, 0.78, "#E11D48", "Группа риска")]
        for cx, cy, col, lbl in centers:
            ax1.scatter(cx + rng.normal(0, 0.08, 30), cy + rng.normal(0, 0.08, 30), s=18, color=col, alpha=0.65, label=lbl)
        ax1.axvline(0.50, color="#94A3B8", ls="--", lw=1.2)
        ax1.axhline(0.54, color="#94A3B8", ls="--", lw=1.2)
        ax1.set_xlim(0, 1)
        ax1.set_ylim(0, 1.05)
        ax1.legend(loc="upper center", ncol=2, fontsize=7.8, framealpha=0.92)
        _configure_ax(ax2, "Оптимум кластеров: Локоть и Силуэт", "Число кластеров k", "Коэффициент силуэта s(k)")
        ks = [2, 3, 4, 5, 6, 7]
        sil = [0.335, 0.378, 0.412, 0.364, 0.328, 0.295]
        ax2.plot(ks, sil, marker="o", color="#059669", lw=2.3, label="Silhouette (макс. 0.412 при k=4)")
        ax2.axvline(4, color="#E11D48", ls="--", lw=1.6, label="Оптимум k* = 4")
        ax2.set_xlim(1.6, 7.4)
        ax2.set_ylim(0.25, 0.46)
        ax2.legend(loc="upper right", fontsize=8.4, framealpha=0.92)

    elif mode == "lift_ablation":
        _configure_ax(ax1, "Абляция: падение F1 при удалении", "Исключенный признак", "Изменение Delta F1")
        feats = ["minutes", "tenure", "charges", "support", "gb_used"]
        drops = [-0.075, -0.066, -0.052, -0.038, -0.024]
        ax1.bar(feats, drops, color=["#E11D48", "#D97706", "#2563EB", "#6366F1", "#059669"], width=0.52)
        ax1.axhline(0, color="#475569", lw=1.0)
        ax1.set_ylim(-0.09, 0.01)
        _configure_ax(ax2, "Кумулятивная кривая захвата (Gain/Lift)", "Доля охваченной базы (%)", "Перехваченный отток (%)")
        pct = np.linspace(0, 100, 100)
        gain = 100.0 * (1.0 - (1.0 - pct / 100.0) ** 2.9)
        ax2.plot(pct, pct, color="#94A3B8", ls="--", lw=1.4, label="Случайный обзвон (Lift=1.0)")
        ax2.plot(pct, gain, color="#059669", lw=2.4, label="Ранжирование модели (Lift=2.75x)")
        ax2.axvline(20, color="#2563EB", ls=":", lw=1.6, label="Топ-20% базы -> 55% оттока")
        ax2.set_xlim(0, 100)
        ax2.set_ylim(0, 105)
        ax2.legend(loc="lower right", fontsize=8.4, framealpha=0.92)
    elif mode == "time_arrow_leakage":
        _configure_ax(ax1, "Разбиение по времени 80/20 (730 сут.)", "Сутки наблюдения (1..730)", "Трафик (Мбит/с)")
        days = np.linspace(1, 730, 240)
        trf = 3400 + 1.65 * days + 420 * np.sin(2 * np.pi * days / 30.0)
        ax1.plot(days[:192], trf[:192], color="#2563EB", lw=1.9, label="Train 80% (584 сут.)")
        ax1.plot(days[191:], trf[191:], color="#059669", lw=2.1, label="Test 20% (146 сут.)")
        ax1.axvline(584, color="#E11D48", lw=2.0, ls="--", label="Барьер причинности t=584")
        ax1.set_xlim(0, 740)
        ax1.set_ylim(2600, 5600)
        ax1.legend(loc="upper left", fontsize=7.0)
        _configure_ax(ax2, "Каскад 5 окон TimeSeriesSplit", "Горизонт времени (%)", "Номер фолда (1..5)")
        for f_i in range(1, 6):
            tr_end = 15 + f_i * 13
            ax2.barh(f_i, tr_end, left=0, height=0.52, color="#3B82F6", alpha=0.85, label="Train" if f_i == 1 else "")
            ax2.barh(f_i, 13, left=tr_end, height=0.52, color="#059669", alpha=0.90, label="Test" if f_i == 1 else "")
        ax2.set_xlim(0, 100)
        ax2.set_ylim(0.3, 5.8)
        ax2.legend(loc="lower right", fontsize=7.2)

    elif mode == "acf_fourier_circle":
        _configure_ax(ax1, "АКФ: пики 24 ч (сутки) и 168 ч (неделя)", "Лаг сдвига tau (часы)", "Коэффициент АКФ r(tau)")
        lags = np.arange(0, 192, 4)
        acf = np.exp(-lags / 240.0) * (0.55 * np.cos(2 * np.pi * lags / 24.0) + 0.45)
        acf[0] = 1.0
        ax1.stem(lags, acf, linefmt="#2563EB", markerfmt="o", basefmt="#94A3B8")
        ax1.axvline(24, color="#059669", ls="--", lw=1.5, label="Суточный пик (24 ч)")
        ax1.axvline(168, color="#D97706", ls="--", lw=1.5, label="Недельный пик (168 ч)")
        ax1.set_xlim(-4, 192)
        ax1.set_ylim(-0.15, 1.12)
        ax1.legend(loc="upper right", fontsize=7.0)
        _configure_ax(ax2, "Свертка часов 0..23 в круг (sin, cos)", "cos(2*pi*t / 24)", "sin(2*pi*t / 24)")
        ang = np.linspace(0, 2 * np.pi, 160)
        ax2.plot(np.cos(ang), np.sin(ang), color="#2563EB", lw=2.0)
        for hr, lbl in [(0, "00:00"), (6, "06:00"), (12, "12:00"), (18, "18:00"), (23, "23:00")]:
            a_h = 2 * np.pi * hr / 24.0
            ax2.scatter([math.cos(a_h)], [math.sin(a_h)], color="#E11D48" if hr in (0, 23) else "#059669", s=38, zorder=5)
            ax2.annotate(lbl, (math.cos(a_h) * 0.78 - 0.14, math.sin(a_h) * 0.78), fontsize=7.5, fontweight="bold")
        ax2.set_xlim(-1.25, 1.25)
        ax2.set_ylim(-1.25, 1.25)

    elif mode == "lasso_diamond_ridge":
        _configure_ax(ax1, "Геометрия L1 (ромб) vs L2 (круг)", "Вес шума beta_1", "Вес лага beta_2")
        ax1.axhline(0, color="#94A3B8", lw=1.0)
        ax1.axvline(0, color="#94A3B8", lw=1.0)
        # L1 diamond
        ax1.plot([0, 0.55, 0, -0.55, 0], [0.55, 0, -0.55, 0, 0.55], color="#059669", lw=2.2, label="Ромб L1 Lasso (beta_1=0)")
        ax1.fill([0, 0.55, 0, -0.55], [0.55, 0, -0.55, 0], color="#D1FAE5", alpha=0.5)
        # L2 circle
        ang = np.linspace(0, 2 * np.pi, 120)
        ax1.plot(0.42 * np.cos(ang), 0.42 * np.sin(ang), color="#2563EB", ls="--", lw=1.6, label="Круг L2 Ridge")
        ax1.scatter([0.45], [0.85], color="#E11D48", s=40, zorder=6, label="Минимум OLS")
        ax1.scatter([0.0], [0.55], color="#059669", s=52, zorder=7, label="Касание на оси (0, 0.55)")
        ax1.set_xlim(-0.85, 0.95)
        ax1.set_ylim(-0.65, 1.15)
        ax1.legend(loc="lower left", fontsize=6.6)
        _configure_ax(ax2, "Отбор признаков Lasso (3 шума -> 0)", "Признак модели трафика", "Абс. вес |beta_j|")
        p_names = ["lag_1h", "lag_24h", "lag_168h", "roll_24", "noise_1", "noise_2"]
        w_vals = [0.48, 0.31, 0.24, 0.16, 0.0, 0.0]
        ax2.bar(p_names, w_vals, color=["#2563EB", "#2563EB", "#059669", "#D97706", "#CBD5E1", "#CBD5E1"], width=0.52)
        ax2.set_ylim(0, 0.56)

    elif mode == "sarimax_fan_chart":
        _configure_ax(ax1, "Прогноз трафика и 95% веер коридора", "Горизонт прогноза h (часы)", "Трафик (Мбит/с)")
        h = np.linspace(0, 72, 144)
        pred = 4200 + 950 * np.sin(2 * np.pi * h / 24.0) + 220 * np.cos(2 * np.pi * h / 12.0)
        fan = 1.96 * 95.0 * np.sqrt(np.maximum(0.0, (h - 24.0) / 6.0))
        ax1.plot(h, pred, color="#2563EB", lw=2.1, label="Прогноз (R^2 = 0.9117)")
        ax1.fill_between(h[48:], (pred - fan)[48:], (pred + fan)[48:], color="#DBEAFE", alpha=0.65, label="95% коридор +-1.96*s*sqrt(h)")
        ax1.axhline(5650, color="#E11D48", ls="--", lw=1.7, label="Порог емкости SLA")
        ax1.axvline(24, color="#475569", ls=":", lw=1.3)
        ax1.set_xlim(0, 72)
        ax1.set_ylim(2600, 6200)
        ax1.legend(loc="upper left", fontsize=6.5, frameon=True, framealpha=0.92)
        _configure_ax(ax2, "Диагностика невязок e_t (белый шум)", "Час тестовой выборки", "Ошибка e_t (Мбит/с)")
        th = np.linspace(1, 100, 90)
        res_e = rng.normal(0, 185.0, 90)
        ax2.scatter(th, res_e, s=16, color="#2563EB", alpha=0.75)
        ax2.axhline(0, color="#1E293B", lw=1.2)
        ax2.axhline(360, color="#059669", ls="--", lw=1.4, label="Коридор +-2*sigma")
        ax2.axhline(-360, color="#059669", ls="--", lw=1.4)
        ax2.set_xlim(0, 102)
        ax2.set_ylim(-620, 620)
        ax2.legend(loc="upper right", fontsize=8.4, framealpha=0.92)


def build_moiad_stage_backdrop(ch_spec: Dict[str, Any]) -> np.ndarray:
    """
    Pre-render the 864x540 dual-panel Matplotlib scientific coordinate stage
    once per chapter at 2x resolution (`0.0 px` frame-to-frame jitter).
    """
    mode = ch_spec["mode"]
    fig = plt.figure(figsize=(8.64, 5.40), dpi=200, facecolor="#FFFFFF")
    gs = fig.add_gridspec(1, 2, left=0.075, right=0.975, top=0.88, bottom=0.12, wspace=0.22)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])

    if mode in ("stevens_scales", "outlier_masking", "missing_mechanisms", "mahalanobis_pca", "weibull_hazard", "goodness_of_fit", "clt_monte_carlo", "vif_gls"):
        _populate_backdrop_pr1_pr2(mode, ax1, ax2)
    else:
        _populate_backdrop_pr3_pr4(mode, ax1, ax2)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="#FFFFFF")
    plt.close(fig)
    buf.seek(0)
    stage_img = Image.open(buf).convert("RGB").resize((864, 540), Image.Resampling.LANCZOS)
    return np.asarray(stage_img, dtype=np.uint8)


class _DirectRgbaDraw:
    """Fast RGBA overlay drawer mapping 2x virtual stage coordinates directly onto 1x RGB stage."""

    def __init__(self, img: Image.Image) -> None:
        self._d = ImageDraw.Draw(img, "RGBA")

    def rounded_rectangle(
        self, xy: List[int], radius: int = 8, fill: Any = None, outline: Any = None, width: int = 1
    ) -> None:
        self._d.rounded_rectangle(
            [int(c // 2) for c in xy],
            radius=max(1, int(radius // 2)),
            fill=fill,
            outline=outline,
            width=max(1, int(round(width / 2.0))),
        )

    def line(self, xy: List[int], fill: Any = None, width: int = 1) -> None:
        self._d.line([int(c // 2) for c in xy], fill=fill, width=max(1, int(round(width / 2.0))))

    def ellipse(self, xy: List[int], fill: Any = None, outline: Any = None, width: int = 1) -> None:
        self._d.ellipse(
            [int(c // 2) for c in xy],
            fill=fill,
            outline=outline,
            width=max(1, int(round(width / 2.0))),
        )


_W_X_ARR = np.linspace(0.0, 4.0, 240)
_W_F1_ARR = np.abs(_W_X_ARR * (1.0 - _W_X_ARR) * np.sin(_W_X_ARR)) / 4.786
_W_CDF_ARR = np.cumsum(_W_F1_ARR)
_W_CDF_ARR = _W_CDF_ARR / _W_CDF_ARR[-1]


def _draw_stage_overlay_2x(
    stage_img: Image.Image,
    mode: str,
    u: float,
    u_switch: float = 0.50,
) -> Image.Image:
    """
    Draw crisp RGBA dynamic mathematical geometry on top of
    the pre-rendered `864x540` coordinate stage for continuous 24-fps motion.
    `u_switch` defines the normalized transition point between Panel 1 (left) and Panel 2 (right).
    """
    out = stage_img.copy()
    d = _DirectRgbaDraw(out)

    # Panel 1 plot box: x in [65..405], y in [65..474]; Panel 2 plot box: x in [488..838], y in [65..474]
    p1_box = [4 * 2, 14 * 2, 425 * 2, 524 * 2]
    p2_box = [434 * 2, 14 * 2, 858 * 2, 524 * 2]
    is_left = u < u_switch
    active_box = p1_box if is_left else p2_box
    inactive_box = p2_box if is_left else p1_box
    act_col = (37, 99, 235, 225) if is_left else (5, 150, 105, 225)

    # Soft dim on inactive panel + glowing rounded spotlight border on active panel
    d.rounded_rectangle(inactive_box, radius=18, fill=(246, 248, 251, 52), outline=(203, 213, 225, 140), width=2)
    d.rounded_rectangle(
        [active_box[0] - 4, active_box[1] - 4, active_box[2] + 4, active_box[3] + 4],
        radius=20,
        outline=(act_col[0], act_col[1], act_col[2], 70),
        width=8,
    )
    d.rounded_rectangle(active_box, radius=18, outline=act_col, width=4)

    # Smooth local progress inside Panel 1 (u1) and Panel 2 (u2) scaled dynamically to u_switch
    span1 = max(0.01, u_switch * 1.04)
    u1 = min(1.0, max(0.0, u / span1))

    lead2 = min(0.06, u_switch * 0.12)
    start2 = max(0.0, u_switch - lead2)
    span2 = max(0.01, 1.0 - start2)
    u2 = min(1.0, max(0.0, (u - start2) / span2))

    # Panel 1 & 2 plot coordinate helpers: x_norm, y_norm in [0, 1] -> 2x pixel coords
    def p1_xy(xn: float, yn: float) -> Tuple[int, int]:
        px = int((64.8 + xn * 350.3) * 2.0)
        py = int((475.2 - yn * 410.4) * 2.0)
        return px, py

    def p2_xy(xn: float, yn: float) -> Tuple[int, int]:
        px = int((492.1 + xn * 350.3) * 2.0)
        py = int((475.2 - yn * 410.4) * 2.0)
        return px, py

    def draw_curve_dot(pt: Tuple[int, int], base_y: int, col: Tuple[int, int, int]) -> None:
        """Curve-following point with projection stem to `base_y` (strictly for 1D functions y=f(x))."""
        x_p, y_p = pt
        d.line([x_p, base_y, x_p, y_p], fill=(col[0], col[1], col[2], 145), width=3)
        d.ellipse([x_p - 14, y_p - 14, x_p + 14, y_p + 14], fill=(col[0], col[1], col[2], 65))
        d.ellipse([x_p - 8, y_p - 8, x_p + 8, y_p + 8], fill=(col[0], col[1], col[2], 255), outline=(255, 255, 255, 255), width=3)

    def draw_point_ring(pt: Tuple[int, int], col: Tuple[int, int, int], r_out: int = 18) -> None:
        """2D target ring highlight without vertical stem (for scatter, basis, cluster, and circle plots)."""
        x_p, y_p = pt
        d.ellipse([x_p - r_out, y_p - r_out, x_p + r_out, y_p + r_out], fill=(col[0], col[1], col[2], 50), outline=(col[0], col[1], col[2], 210), width=3)
        d.ellipse([x_p - 8, y_p - 8, x_p + 8, y_p + 8], fill=(col[0], col[1], col[2], 255), outline=(255, 255, 255, 255), width=3)

    def draw_bar_box(
        p_fn: Any, x_c: float, y_bot: float, y_top: float, half_w: float, col: Tuple[int, int, int]
    ) -> None:
        """Crisp rounded highlight box around an active vertical bar (no vertical drop stem)."""
        p_tl = p_fn(max(0.01, x_c - half_w), min(0.98, max(y_bot, y_top) + 0.02))
        p_br = p_fn(min(0.99, x_c + half_w), max(0.0, min(y_bot, y_top)))
        d.rounded_rectangle(
            [p_tl[0] - 4, p_tl[1] - 4, p_br[0] + 4, p_br[1] + 4],
            radius=10,
            fill=(col[0], col[1], col[2], 42),
            outline=(col[0], col[1], col[2], 235),
            width=4,
        )

    by = int(475 * 2)

    if mode == "stevens_scales":
        # Tilting false regression line on Label Encoding (Panel 1) + orthogonal One-Hot basis target rings (Panel 2)
        p_a = p1_xy((1.0 - 0.4) / 3.2, (72.0 - 10.0) / 85.0)
        p_b = p1_xy((3.0 - 0.4) / 3.2, (58.0 - 16.0 * u1 - 10.0) / 85.0)
        d.line([p_a[0], p_a[1], p_b[0], p_b[1]], fill=(225, 29, 72, 230), width=5)
        draw_point_ring(p1_xy((2.0 - 0.4) / 3.2, (28.0 - 10.0) / 85.0), COL_COBALT, r_out=20)
        # Orthogonal basis axes from (0,0) to (1,0) and (0,1)
        o_pt = p2_xy(0.15 / 1.40, 0.15 / 1.40)
        e1_pt = p2_xy((1.0 + 0.15) / 1.40, 0.15 / 1.40)
        e2_pt = p2_xy(0.15 / 1.40, (1.0 + 0.15) / 1.40)
        d.line([o_pt[0], o_pt[1], e1_pt[0], e1_pt[1]], fill=(225, 29, 72, 210), width=4)
        d.line([o_pt[0], o_pt[1], e2_pt[0], e2_pt[1]], fill=(37, 99, 235, 210), width=4)
        b_pts = [(e1_pt, COL_ROSE), (e2_pt, COL_COBALT), (o_pt, COL_EMERALD)]
        act_b, act_c = b_pts[min(2, int(u2 * 3.0))]
        draw_point_ring(act_b, act_c, r_out=22)

    elif mode == "outlier_masking":
        # Sliding 3-sigma threshold rightward as outlier grows vs locked IQR fence
        x_3s = 0.44 + 0.44 * u1
        pt_top = p1_xy(x_3s, 0.94)
        pt_bot = p1_xy(x_3s, 0.0)
        d.line([pt_top[0], pt_top[1], pt_bot[0], pt_bot[1]], fill=(225, 29, 72, 235), width=5)
        draw_point_ring(p1_xy(x_3s, 0.50), COL_ROSE, r_out=16)
        # Exact Winsorized curve point: idx = u2 * 1000, clamped = min(180, 20.58 + 18*exp((idx-650)/140))
        idx_v = u2 * 1000.0
        clamped_v = min(180.0, 20.58 + 18.0 * math.exp((idx_v - 650.0) / 140.0))
        draw_curve_dot(p2_xy(u2, clamped_v / 260.0), by, COL_EMERALD)

    elif mode == "missing_mechanisms":
        # Panel 1: Exact curve dot active during Left phase
        if is_left:
            t_v = u1 * 48.0
            clean_v = 55.0 + 18.0 * math.sin(2.0 * math.pi * t_v / 24.0) + 5.0 * math.cos(2.0 * math.pi * t_v / 12.0)
            draw_curve_dot(p1_xy(u1, (clean_v - 20.0) / 72.0), by, COL_COBALT)

        # Panel 2: Highlight box active ONLY when Right panel is genuine focus
        if not is_left:
            b_idx = min(4, int(u2 * 5.0))
            # Exact Matplotlib 5-bar categorical positions (error < 0.02 px)
            bx_c = 0.1004 + b_idx * 0.1998
            half_w = 0.0549
            bh_n = [40 / 48.0, 39 / 48.0, 35 / 48.0, 30 / 48.0, 27 / 48.0][b_idx]
            draw_bar_box(p2_xy, bx_c, 0.0, bh_n, half_w, COL_EMERALD)

    elif mode == "mahalanobis_pca":
        # Scanning target ring along tilted Mahalanobis ellipse + anomaly target rings (Panel 1) + bar callout (Panel 2)
        ang = 2.0 * math.pi * u1
        ex = (45.5 + 28.0 * math.cos(ang) - 9.0 * math.sin(ang) - 5.0) / 93.0
        ey = (45.5 + 23.0 * math.cos(ang) + 9.0 * math.sin(ang) - 5.0) / 93.0
        draw_point_ring(p1_xy(ex, ey), COL_EMERALD, r_out=16)
        draw_point_ring(p1_xy((78.0 - 5.0) / 93.0, (20.0 - 5.0) / 93.0), COL_ROSE, r_out=20)
        draw_point_ring(p1_xy((24.0 - 5.0) / 93.0, (82.0 - 5.0) / 93.0), COL_ROSE, r_out=20)
        b_i = min(3, int(u2 * 4.0))
        draw_bar_box(p2_xy, 0.15 + b_i * 0.233, 0.0, [13 / 16.0, 11 / 16.0, 9 / 16.0, 8 / 16.0][b_i], 0.075, COL_ROSE)

    elif mode == "weibull_hazard":
        # Exact PDF curve dot (Panel 1) + Exact Inverse CDF PPF reflection ray (Panel 2)
        xv = u1 * 4.0
        fv = abs(xv * (1.0 - xv) * math.sin(xv)) / 4.786 / 0.85
        draw_curve_dot(p1_xy(u1, min(0.95, fv)), by, COL_COBALT)
        u_q = 0.06 + 0.88 * u2
        x_q_val = float(np.interp(u_q, _W_CDF_ARR, _W_X_ARR))
        xq_norm = x_q_val / 4.0
        yq_norm = u_q / 1.05
        p_y = p2_xy(0.0, yq_norm)
        p_c = p2_xy(xq_norm, yq_norm)
        p_x = p2_xy(xq_norm, 0.0)
        d.line([p_y[0], p_y[1], p_c[0], p_c[1]], fill=(217, 119, 6, 235), width=4)
        d.line([p_c[0], p_c[1], p_x[0], p_x[1]], fill=(5, 150, 105, 235), width=4)
        draw_point_ring(p_c, COL_EMERALD, r_out=16)

    elif mode == "goodness_of_fit":
        # Exact Gaussian bell curve N(5, 1.2^2) on xlim(1.2, 8.8), ylim(0, 0.42) + QQ-plot bisector
        x_val = 1.2 + u1 * 7.6
        yg_val = (1.0 / (1.2 * math.sqrt(2.0 * math.pi))) * math.exp(-0.5 * ((x_val - 5.0) / 1.2) ** 2)
        draw_curve_dot(p1_xy(u1, yg_val / 0.42), by, COL_ROSE)
        q_v = -2.5 + 5.0 * u2
        draw_point_ring(p2_xy((q_v + 2.8) / 5.6, (5.0 + 1.2 * q_v - 1.5) / 7.0), COL_COBALT, r_out=18)

    elif mode == "clt_monte_carlo":
        # Exact CLT Gaussian bell curve (N=30..100) + 1/sqrt(N) decay dot
        x_c = 0.25 + 0.50 * u1
        g_val = (1.0 / (0.0527 * math.sqrt(2.0 * math.pi))) * math.exp(-0.5 * ((x_c - 0.5) / 0.0527) ** 2)
        draw_curve_dot(p1_xy(x_c, min(0.95, g_val / 8.8)), by, COL_COBALT)
        n_val = 1.0 + 99.0 * u2
        se_norm = (0.2887 / math.sqrt(n_val)) / 0.32
        draw_curve_dot(p2_xy(n_val / 105.0, se_norm), by, COL_EMERALD)

    elif mode == "vif_gls":
        b_i = min(2, int(u1 * 3.0))
        draw_bar_box(p1_xy, 0.139 + b_i * 0.361, 0.0, [1.505 / 6.0, 1.494 / 6.0, 1.141 / 6.0][b_i], 0.094, COL_COBALT)
        x_v = 0.5 + 9.0 * u2
        y_gls = 0.9250 * x_v + 0.3000
        draw_curve_dot(p2_xy(x_v / 10.0, y_gls / 11.5), by, COL_EMERALD)

    elif mode == "churn_cost_threshold":
        # Threshold tau sweeping leftward from 0.50 to 0.25
        tau = 0.50 - 0.25 * u1
        t_top = p1_xy(tau, 0.94)
        t_bot = p1_xy(tau, 0.0)
        d.line([t_top[0], t_top[1], t_bot[0], t_bot[1]], fill=(5, 150, 105, 240), width=5)
        d1_v = math.exp(-0.5 * ((tau - 0.56) / 0.18) ** 2) * 0.45 / 0.92
        draw_point_ring(p1_xy(tau, d1_v), COL_EMERALD, r_out=18)
        tau2 = 0.50 - 0.25 * u2
        rec_y = (1.0 / (1.0 + math.exp((tau2 - 0.36) / 0.11))) / 1.08
        cost_y = (0.38 + 0.58 * ((tau2 - 0.25) ** 2) / 0.32 + 0.12 * max(0.0, 0.25 - tau2) * 3.0) / 1.08
        draw_curve_dot(p2_xy(tau2, rec_y), by, COL_EMERALD)
        draw_point_ring(p2_xy(tau2, cost_y), COL_ROSE, r_out=16)

    elif mode == "svm_rbf_trees":
        ang_r = 2.0 * math.pi * u1
        rx = 0.28 + 0.20 * math.cos(ang_r)
        ry = 0.72 + 0.18 * math.sin(ang_r)
        draw_point_ring(p1_xy(rx, ry), COL_ROSE, r_out=18)
        fpr_v = 0.04 + 0.90 * u2
        draw_curve_dot(p2_xy(fpr_v, (fpr_v ** 0.36) / 1.02), by, COL_COBALT)

    elif mode == "kmeans_vs_dbscan":
        # All 4 cluster centroids migrating smoothly without 1D vertical stems + exact Silhouette curve dot
        targets = [
            (0.22, 0.25, COL_COBALT),
            (0.76, 0.32, COL_EMERALD),
            (0.78, 0.78, COL_AMBER),
            (0.22, 0.78, COL_ROSE),
        ]
        for tx, ty, tcol in targets:
            cx = 0.50 + (tx - 0.50) * u1
            cy = (0.52 + (ty - 0.52) * u1) / 1.05
            draw_point_ring(p1_xy(cx, cy), tcol, r_out=18)
        k_val = 2.0 + 5.0 * u2
        ks_arr = np.array([2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
        sil_arr = np.array([0.335, 0.378, 0.412, 0.364, 0.328, 0.295])
        s_val = float(np.interp(k_val, ks_arr, sil_arr))
        draw_curve_dot(p2_xy((k_val - 1.6) / 5.8, (s_val - 0.25) / 0.21), by, COL_EMERALD)

    elif mode == "lift_ablation":
        b_i = min(4, int(u1 * 5.0))
        drops_n = [(-0.075 + 0.09) / 0.10, (-0.066 + 0.09) / 0.10, (-0.052 + 0.09) / 0.10, (-0.038 + 0.09) / 0.10, (-0.024 + 0.09) / 0.10]
        draw_bar_box(p1_xy, 0.100 + b_i * 0.200, drops_n[b_i], 0.90, 0.058, COL_ROSE)
        gain_y = (100.0 * (1.0 - (1.0 - u2) ** 2.9)) / 105.0
        draw_curve_dot(p2_xy(u2, gain_y), by, COL_EMERALD)

    elif mode == "time_arrow_leakage":
        d_val = 1.0 + 729.0 * u1
        trf_v = 3400.0 + 1.65 * d_val + 420.0 * math.sin(2.0 * math.pi * d_val / 30.0)
        draw_curve_dot(p1_xy(d_val / 740.0, (trf_v - 2600.0) / 3000.0), by, COL_COBALT if u1 < 0.80 else COL_EMERALD)
        f_idx = min(4, int(u2 * 5.0)) + 1
        tr_end = (15.0 + f_idx * 13.0 + 13.0) / 100.0
        yc_f = (f_idx - 0.3) / 5.5
        p_tl = p2_xy(0.01, min(0.98, yc_f + 0.055))
        p_br = p2_xy(tr_end, max(0.02, yc_f - 0.055))
        d.rounded_rectangle([p_tl[0], p_tl[1], p_br[0], p_br[1]], radius=10, fill=(5, 150, 105, 40), outline=(5, 150, 105, 235), width=4)

    elif mode == "acf_fourier_circle":
        lag_v = u1 * 184.0
        acf_v = math.exp(-lag_v / 240.0) * (0.55 * math.cos(2.0 * math.pi * lag_v / 24.0) + 0.45)
        draw_curve_dot(p1_xy((lag_v + 4.0) / 196.0, (acf_v + 0.15) / 1.27), int((475.2 - (0.15 / 1.27) * 410.4) * 2.0), COL_COBALT)
        # Rotating clock hand on equal-aspect unit circle (xlim/ylim [-1.35, 1.35] inside 350.3x410.4 box)
        ang = 2.0 * math.pi * u2
        c_o = p2_xy(0.50, 0.50)
        c_p = p2_xy(0.50 + 0.3704 * math.cos(ang), 0.50 + 0.3161 * math.sin(ang))
        d.line([c_o[0], c_o[1], c_p[0], c_p[1]], fill=(225, 29, 72, 235), width=5)
        draw_point_ring(c_p, COL_ROSE, r_out=18)

    elif mode == "lasso_diamond_ridge":
        # Expanding MSE contour ellipse centered at OLS (0.45, 0.85) tangent to L1 vertex (0, 0.55)
        c_ols = p1_xy((0.45 + 0.85) / 1.80, (0.85 + 0.65) / 1.80)
        rx_px = int((0.250 * max(0.18, u1)) * 340.0 * 2.0)
        ry_px = int((0.167 * max(0.18, u1)) * 410.0 * 2.0)
        d.ellipse(
            [c_ols[0] - rx_px, c_ols[1] - ry_px, c_ols[0] + rx_px, c_ols[1] + ry_px],
            outline=(225, 29, 72, 215),
            width=4,
        )
        draw_point_ring(p1_xy(0.85 / 1.80, 1.20 / 1.80), COL_EMERALD, r_out=20)
        b_i = min(5, int(u2 * 6.0))
        bh_l = [0.48 / 0.56, 0.31 / 0.56, 0.24 / 0.56, 0.16 / 0.56, 0.04, 0.04][b_i]
        draw_bar_box(p2_xy, 0.11 + b_i * 0.156, 0.0, bh_l, 0.055, COL_COBALT)

    elif mode == "sarimax_fan_chart":
        h_v = 72.0 * u1
        pred_v = 4200.0 + 950.0 * math.sin(2.0 * math.pi * h_v / 24.0) + 220.0 * math.cos(2.0 * math.pi * h_v / 12.0)
        draw_curve_dot(p1_xy(u1, (pred_v - 2600.0) / 3600.0), by, COL_COBALT)
        y_res = 0.50 + 0.22 * math.sin(2.0 * math.pi * u2 * 5.0)
        draw_curve_dot(p2_xy(0.04 + 0.92 * u2, y_res), int((475.0 - 0.50 * 410.0) * 2.0), COL_EMERALD)

    return out


_LATEX_FORMULA_CACHE: Dict[Any, Image.Image] = {}


def render_latex_to_slot(
    expr: str, max_w: int = 332, max_h: int = 38, color: str = "#18212F"
) -> Image.Image:
    """Render LaTeX expression via matplotlib.mathtext at 200 DPI with anti-aliasing into max_w x max_h slot."""
    cache_key = (expr, max_w, max_h, color)
    cached = _LATEX_FORMULA_CACHE.get(cache_key)
    if cached is not None:
        return cached

    if not expr or not isinstance(expr, str) or not expr.strip() or max_w <= 0 or max_h <= 0:
        blank = Image.new("RGBA", (max(1, max_w), max(1, max_h)), (0, 0, 0, 0))
        _LATEX_FORMULA_CACHE[cache_key] = blank
        if (max_w, max_h, color) == (332, 38, "#18212F") and expr:
            _LATEX_FORMULA_CACHE[expr] = blank
        return blank

    tex_expr = expr if (expr.startswith("$") and expr.endswith("$")) else f"${expr}$"
    dpi = 200
    fig = None
    try:
        fig = plt.figure(dpi=dpi)
        fig.patch.set_alpha(0.0)
        t_obj = fig.text(0.5, 0.5, tex_expr, fontsize=10.0, color=color, va="center", ha="center")
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        bbox = t_obj.get_window_extent(renderer)

        pad = 2
        w_in = max(0.5, (bbox.width + pad * 2) / dpi)
        h_in = max(0.2, (bbox.height + pad * 2) / dpi)
        fig.set_size_inches(w_in, h_in)
        t_obj.set_position((0.5, 0.5))

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi, transparent=True, bbox_inches="tight", pad_inches=0.01)
        buf.seek(0)
        raw_img = Image.open(buf).convert("RGBA")
    except Exception:
        blank = Image.new("RGBA", (max(1, max_w), max(1, max_h)), (0, 0, 0, 0))
        _LATEX_FORMULA_CACHE[cache_key] = blank
        if (max_w, max_h, color) == (332, 38, "#18212F") and expr:
            _LATEX_FORMULA_CACHE[expr] = blank
        return blank
    finally:
        if fig is not None:
            plt.close(fig)

    target_w = raw_img.width / 2.0
    target_h = raw_img.height / 2.0
    scale = min(1.0, max_w / max(1.0, target_w), max_h / max(1.0, target_h))
    final_w = max(1, int(round(target_w * scale)))
    final_h = max(1, int(round(target_h * scale)))

    out_img = raw_img.resize((final_w, final_h), Image.Resampling.LANCZOS)
    _LATEX_FORMULA_CACHE[cache_key] = out_img
    if (max_w, max_h, color) == (332, 38, "#18212F"):
        _LATEX_FORMULA_CACHE[expr] = out_img
    return out_img


def _render_frozen_gauges(
    draw: ImageDraw.ImageDraw, gauges: List[Dict[str, Any]], u: float, fonts: Dict[str, Any]
) -> None:
    """Render Card 2 gauges with freeze support for pinned invariants and physical contraction for decreasing metrics."""
    gy = 266
    col_map = {
        "blue": (COL_COBALT, COL_COBALT_WASH),
        "emerald": (COL_EMERALD, COL_EMERALD_WASH),
        "amber": (COL_AMBER, COL_AMBER_WASH),
        "rose": (COL_ROSE, COL_ROSE_WASH),
    }
    for g in gauges[:3]:
        v0, v1 = float(g.get("v0", 0.0)), float(g.get("v1", 0.0))
        is_pinned = bool(g.get("pinned", False)) or abs(v1 - v0) < 1e-6
        fg_c, bg_c = col_map.get(g.get("color", "blue"), (COL_COBALT, COL_COBALT_WASH))
        unit = g.get("unit", "")
        label = g.get("label", "")

        if is_pinned:
            val = v0
            val_str = f"{val:.3f} {unit}" if abs(val) < 2.0 and val != int(val) else f"{val:.1f} {unit}"
            badge_txt = "[ИНВАРИАНТ]" if "инвариант" in label.lower() else "[ФИКС]"
            vw = _text_width(draw, val_str, fonts["mono_b"])
            bw = _text_width(draw, badge_txt, fonts["pill_s"])
            draw.text((1246 - vw, gy), val_str, fill=fg_c, font=fonts["mono_b"])
            badge_x1 = 1246 - vw - 6
            badge_x0 = badge_x1 - bw - 8
            draw.rounded_rectangle([badge_x0, gy, badge_x1, gy + 17], radius=3, fill=bg_c, outline=fg_c, width=1)
            draw.text((badge_x0 + 4, gy + 1), badge_txt, fill=fg_c, font=fonts["pill_s"])

            pinned_ratio = float(g.get("pinned_ratio", 0.65))
            fill_w = max(14, int(332 * pinned_ratio))
            draw.rounded_rectangle([914, gy + 20, 1246, gy + 30], radius=4, fill=bg_c, outline=COL_RULE, width=1)
            draw.rounded_rectangle([914, gy + 20, 914 + fill_w, gy + 30], radius=4, fill=fg_c)
        else:
            val = v0 + (v1 - v0) * u
            val_str = f"{val:.3f} {unit}" if abs(v1) < 2.0 and v1 != int(v1) else f"{val:.1f} {unit}"
            vw = _text_width(draw, val_str, fonts["mono_b"])
            draw.text((1246 - vw, gy), val_str, fill=fg_c, font=fonts["mono_b"])
            draw.rounded_rectangle([914, gy + 20, 1246, gy + 30], radius=4, fill=bg_c, outline=COL_RULE, width=1)
            if v1 < v0:
                frac = max(0.0, min(1.0, (val - v1) / max(1e-9, (v0 - v1))))
                fill_w = max(14, int(332 * (0.12 + 0.88 * frac)))
            else:
                frac = max(0.0, min(1.0, (val - v0) / max(1e-9, (v1 - v0))))
                fill_w = max(14, int(332 * (0.18 + 0.82 * frac)))
            draw.rounded_rectangle([914, gy + 20, 914 + fill_w, gy + 30], radius=4, fill=fg_c)
        gy += 52


def _render_metric_table(
    draw: ImageDraw.ImageDraw, info_block: Dict[str, Any], u: float, fonts: Dict[str, Any]
) -> None:
    """Render 3-4 row metric comparison table with header, values, deltas, and KPI banner."""
    headers = info_block.get("headers", ["Метрика", "До", "После", "Эффект"])
    rows = info_block.get("rows", [])
    n_cols = max(1, len(headers))
    n_rows = min(4, len(rows))
    if n_rows == 0:
        return

    if n_cols == 4:
        col_w = [118, 70, 72, 72]
    elif n_cols == 5:
        col_w = [96, 58, 56, 58, 64]
    else:
        first_w = max(80, 332 - 60 * (n_cols - 1))
        rem_w = (332 - first_w) // max(1, n_cols - 1)
        col_w = [first_w] + [rem_w] * (n_cols - 1)

    draw.rounded_rectangle([914, 264, 1246, 282], radius=3, fill=COL_COBALT_WASH, outline=COL_RULE, width=1)
    cx = 918
    for c_i, h_txt in enumerate(headers[:n_cols]):
        cw = col_w[c_i]
        ht, hf = _fit_single_line(draw, str(h_txt), fonts["pill_10"], [fonts["pill_95"]], cw - 6)
        draw.text((cx, 267), ht, fill=COL_COBALT, font=hf)
        cx += cw

    summary_kpi = info_block.get("summary_kpi")
    bot_y = 402 if summary_kpi else 424
    avail_h = bot_y - 286
    row_h = avail_h // n_rows

    for r_i, row in enumerate(rows[:n_rows]):
        ry0 = 286 + r_i * row_h
        ry1 = ry0 + row_h - 2
        bg = COL_PAPER if (r_i % 2 == 1) else COL_SHEET
        draw.rounded_rectangle([914, ry0, 1246, ry1], radius=3, fill=bg, outline=COL_RULE, width=1)

        if isinstance(row, dict):
            cell_vals = [row.get("metric", ""), row.get("before", ""), row.get("after", ""), row.get("delta", "")]
        elif isinstance(row, (list, tuple)):
            cell_vals = [str(x) for x in row]
        else:
            cell_vals = [str(row)]

        cx = 918
        for c_i in range(n_cols):
            cw = col_w[c_i]
            val_str = cell_vals[c_i] if c_i < len(cell_vals) else ""
            txt_color = COL_INK
            if c_i == n_cols - 1 or c_i >= 2:
                if any(k in val_str for k in ("[OK]", "Норма", "ФИКС", "ИНВАРИАНТ", "0.0%", "BLUE", "Честно")):
                    txt_color = COL_EMERALD
                elif any(k in val_str for k in ("КРИТИЧ", "Ложно", "Смещен", "РИСК")):
                    txt_color = COL_ROSE
                elif "-" in val_str and "%" in val_str:
                    txt_color = COL_EMERALD
                elif val_str.startswith("-"):
                    txt_color = COL_ROSE

            ct, cf = _fit_single_line(draw, val_str, fonts["pill_s"], [fonts["pill_10"], fonts["pill_95"]], cw - 6)
            draw.text((cx, ry0 + max(2, (row_h - 18) // 2)), ct, fill=txt_color, font=cf)
            cx += cw

    if summary_kpi:
        draw.rounded_rectangle([914, 404, 1246, 426], radius=4, fill=COL_COBALT_WASH, outline=COL_COBALT, width=1)
        kt, kf = _fit_single_line(draw, str(summary_kpi), fonts["pill_10"], [fonts["pill_95"]], 320)
        draw.text((920, 408), kt, fill=COL_COBALT, font=kf)


def _render_confusion_matrix(
    draw: ImageDraw.ImageDraw, info_block: Dict[str, Any], u: float, fonts: Dict[str, Any]
) -> None:
    """Render dynamic 2x2 confusion matrix with threshold sweep tau(u), live cell counts, and cost metrics."""
    tau0 = float(info_block.get("threshold_start", 0.50))
    tau1 = float(info_block.get("threshold_end", 0.25))
    tau = tau0 + (tau1 - tau0) * u

    ms = info_block.get("matrix_start", {"tp": 40, "fn": 174, "fp": 22, "tn": 764})
    me = info_block.get("matrix_end", {"tp": 164, "fn": 50, "fp": 98, "tn": 688})

    tp = int(round(ms["tp"] + (me["tp"] - ms["tp"]) * u))
    fn = int(round(ms["fn"] + (me["fn"] - ms["fn"]) * u))
    fp = int(round(ms["fp"] + (me["fp"] - ms["fp"]) * u))
    tn = int(round(ms["tn"] + (me["tn"] - ms["tn"]) * u))

    tot_pos = max(1, tp + fn)
    recall = (tp / tot_pos) * 100.0
    cost = int(round(412 - (412 - 168) * u))

    draw.rounded_rectangle([914, 264, 1246, 284], radius=4, fill=COL_COBALT_WASH, outline=COL_COBALT, width=1)
    status_str = f"Порог \u03c4* = {tau:.2f}  \u00b7  Recall = {recall:.1f}%  \u00b7  Потери: {cost} тыс. р."
    st, sf = _fit_single_line(draw, status_str, fonts["pill_b"], [fonts["pill_s"], fonts["pill_10"]], 320)
    draw.text((922, 267), st, fill=COL_COBALT, font=sf)

    lbl_w = 52
    cell_w = (332 - lbl_w - 6) // 2
    x_c1 = 914 + lbl_w + 2
    x_c2 = x_c1 + cell_w + 4

    draw.text((x_c1 + 4, 288), "Предск: 1 (Отток)", fill=COL_INK_2, font=fonts["pill_95"])
    draw.text((x_c2 + 4, 288), "Предск: 0 (Норма)", fill=COL_INK_2, font=fonts["pill_95"])

    draw.text((916, 318), "Факт: 1", fill=COL_INK, font=fonts["pill_b"])
    draw.rounded_rectangle([x_c1, 302, x_c1 + cell_w, 348], radius=4, fill=COL_EMERALD_WASH, outline=COL_EMERALD, width=2)
    draw.text((x_c1 + 8, 306), f"TP = {tp}", fill=COL_EMERALD, font=fonts["mono_b"])
    draw.text((x_c1 + 8, 328), f"Пойман отток ({recall:.0f}%)", fill=COL_INK_2, font=fonts["pill_95"])

    draw.rounded_rectangle([x_c2, 302, x_c2 + cell_w, 348], radius=4, fill=COL_ROSE_WASH, outline=COL_ROSE, width=1)
    draw.text((x_c2 + 8, 306), f"FN = {fn}", fill=COL_ROSE, font=fonts["mono_b"])
    draw.text((x_c2 + 8, 328), "Пропущен (\u00d76 штраф)", fill=COL_INK_2, font=fonts["pill_95"])

    draw.text((916, 368), "Факт: 0", fill=COL_INK, font=fonts["pill_b"])
    draw.rounded_rectangle([x_c1, 352, x_c1 + cell_w, 398], radius=4, fill=COL_AMBER_WASH, outline=COL_AMBER, width=1)
    draw.text((x_c1 + 8, 356), f"FP = {fp}", fill=COL_AMBER, font=fonts["mono_b"])
    draw.text((x_c1 + 8, 378), "Ложная тревога (\u00d71)", fill=COL_INK_2, font=fonts["pill_95"])

    draw.rounded_rectangle([x_c2, 352, x_c2 + cell_w, 398], radius=4, fill=COL_PAPER, outline=COL_RULE, width=1)
    draw.text((x_c2 + 8, 356), f"TN = {tn}", fill=COL_INK, font=fonts["mono_b"])
    draw.text((x_c2 + 8, 378), "Верно удержан", fill=COL_INK_2, font=fonts["pill_95"])

    draw.rounded_rectangle([914, 404, 1246, 426], radius=4, fill=COL_EMERALD_WASH, outline=COL_EMERALD, width=1)
    summary_txt = str(info_block.get("summary", "Байесовский порог \u03c4* = 0.25 сокращает потери на 244 тыс. р.")).replace("\u20bd", "р.")
    sm_t, sm_f = _fit_single_line(draw, summary_txt, fonts["pill_10"], [fonts["pill_95"]], 320)
    draw.text((920, 408), sm_t, fill=COL_EMERALD, font=sm_f)


def _render_flowchart(
    draw: ImageDraw.ImageDraw, info_block: Dict[str, Any], phase_idx: Optional[int], u: float, fonts: Dict[str, Any]
) -> None:
    """Render 4-step pipeline flowchart with active step pulse tied to phase/narration."""
    steps = info_block.get("steps", [])
    n_steps = min(4, len(steps))
    if n_steps == 0:
        return

    act_idx = min(n_steps - 1, phase_idx if phase_idx is not None else int(u * n_steps))
    step_h = 34
    gap = (162 - n_steps * step_h) // max(1, n_steps - 1)

    for s_i, st in enumerate(steps[:n_steps]):
        sy0 = 264 + s_i * (step_h + gap)
        sy1 = sy0 + step_h
        is_act = (s_i == act_idx)
        is_done = (s_i < act_idx)

        bg = COL_COBALT_WASH if is_act else (COL_EMERALD_WASH if is_done else COL_PAPER)
        bd = COL_COBALT if is_act else (COL_EMERALD if is_done else COL_RULE)
        fg = COL_COBALT if is_act else (COL_EMERALD if is_done else COL_INK)
        bw_sz = 2 if is_act else 1

        draw.rounded_rectangle([914, sy0, 1246, sy1], radius=5, fill=bg, outline=bd, width=bw_sz)

        num_str = f"0{s_i + 1}"
        draw.rounded_rectangle([920, sy0 + 6, 954, sy1 - 6], radius=3, fill=bd)
        draw.text((937, sy0 + 17), num_str, fill=COL_SHEET, font=fonts["pill_95"], anchor="mm")

        st_name = st.get("name", "")
        st_det = st.get("detail", "")
        badge = st.get("badge", "")

        badge_w = _text_width(draw, badge, fonts["pill_95"]) + 12 if badge else 0
        text_avail_w = 1246 - (962 + badge_w + 12)

        nt, nf = _fit_single_line(draw, f"{st_name}: {st_det}", fonts["pill_b"] if is_act else fonts["pill_s"], [fonts["pill_10"], fonts["pill_95"]], text_avail_w)
        draw.text((962, sy0 + 17), nt, fill=fg, font=nf, anchor="lm")

        if badge:
            bx1 = 1240
            bx0 = bx1 - badge_w
            draw.rounded_rectangle([bx0, sy0 + 6, bx1, sy1 - 6], radius=3, fill=COL_SHEET, outline=bd, width=1)
            draw.text(((bx0 + bx1) // 2, sy0 + 17), badge, fill=bd, font=fonts["pill_95"], anchor="mm")


def _render_theorem_card(
    draw: ImageDraw.ImageDraw, info_block: Dict[str, Any], u: float, fonts: Dict[str, Any]
) -> None:
    """Render formal theorem card with TeX formula, condition badge, and mini convergence/comparison table."""
    thm_name = info_block.get("theorem_name", "Теорема")
    formula_tex = info_block.get("formula_latex", "")
    cond_txt = info_block.get("condition") or info_block.get("takeaway", "")

    badge_w = _text_width(draw, "[ТЕОРЕМА]", fonts["pill_b"]) + 10
    draw.rounded_rectangle([914, 264, 914 + badge_w, 284], radius=3, fill=COL_COBALT, outline=COL_COBALT)
    draw.text((914 + badge_w // 2, 274), "[ТЕОРЕМА]", fill=COL_SHEET, font=fonts["pill_b"], anchor="mm")

    tt_avail = 1246 - (922 + badge_w)
    tt, tf = _fit_single_line(draw, thm_name, fonts["pill_b"], [fonts["pill_s"], fonts["pill_10"]], tt_avail)
    draw.text((922 + badge_w, 274), tt, fill=COL_INK, font=tf, anchor="lm")

    draw.rounded_rectangle([914, 288, 1246, 320], radius=4, fill=COL_COBALT_WASH, outline=COL_RULE, width=1)
    if formula_tex:
        try:
            eq_img = render_latex_to_slot(formula_tex, max_w=320, max_h=28, color="#18212F")
            if eq_img is not None and eq_img.width > 1 and eq_img.height > 1 and eq_img.getbbox() is not None:
                fx = 914 + (332 - eq_img.width) // 2
                fy = 288 + (32 - eq_img.height) // 2
                if hasattr(draw, "_image"):
                    draw._image.paste(eq_img, (fx, fy), mask=eq_img)
        except Exception:
            pass

    if cond_txt:
        ct, cf = _fit_single_line(draw, cond_txt, fonts["body_s"], [fonts["pill_10"], fonts["pill_95"]], 330)
        draw.text((916, 325), ct, fill=COL_INK_2, font=cf)

    conv_rows = info_block.get("convergence_rows")
    comp_table = info_block.get("comparison_table")

    if conv_rows:
        n_r = min(4, len(conv_rows))
        r_h = (426 - 344) // max(1, n_r)
        active_r = min(n_r - 1, int(u * n_r))
        for r_i, cr in enumerate(conv_rows[:n_r]):
            ry0 = 344 + r_i * r_h
            ry1 = ry0 + r_h - 2
            is_cur = (r_i == active_r)
            bg = COL_COBALT_WASH if is_cur else (COL_PAPER if r_i % 2 == 1 else COL_SHEET)
            bd = COL_COBALT if is_cur else COL_RULE
            draw.rounded_rectangle([914, ry0, 1246, ry1], radius=3, fill=bg, outline=bd, width=1)

            n_str = cr.get("n", "")
            se_str = f"SE = {cr.get('se', '')}"
            sh_str = cr.get("shape", "")
            draw.text((920, ry0 + max(1, (r_h - 16) // 2)), n_str, fill=COL_COBALT if is_cur else COL_INK, font=fonts["pill_b"])
            draw.text((980, ry0 + max(1, (r_h - 16) // 2)), se_str, fill=COL_EMERALD if is_cur else COL_INK_2, font=fonts["mono_b"])
            st, sf = _fit_single_line(draw, sh_str, fonts["pill_s"], [fonts["pill_10"], fonts["pill_95"]], 1246 - 1070)
            draw.text((1070, ry0 + max(1, (r_h - 16) // 2)), st, fill=COL_INK, font=sf)
    elif comp_table:
        n_r = min(3, len(comp_table))
        r_h = (426 - 344) // max(1, n_r)
        for r_i, row in enumerate(comp_table[:n_r]):
            ry0 = 344 + r_i * r_h
            ry1 = ry0 + r_h - 2
            is_blue = ("BLUE" in str(row)) or (r_i == n_r - 1)
            bg = COL_EMERALD_WASH if is_blue else (COL_PAPER if r_i % 2 == 1 else COL_SHEET)
            bd = COL_EMERALD if is_blue else COL_RULE
            draw.rounded_rectangle([914, ry0, 1246, ry1], radius=3, fill=bg, outline=bd, width=1)

            col_w = [90, 70, 78, 86]
            cx = 918
            for c_i, cell in enumerate(row[:4]):
                cw = col_w[c_i]
                fg = COL_EMERALD if is_blue else COL_INK
                ct, cf = _fit_single_line(draw, str(cell), fonts["pill_s"], [fonts["pill_10"], fonts["pill_95"]], cw - 4)
                draw.text((cx, ry0 + max(1, (r_h - 16) // 2)), ct, fill=fg, font=cf)
                cx += cw


def _render_feature_table(
    draw: ImageDraw.ImageDraw, info_block: Dict[str, Any], u: float, fonts: Dict[str, Any]
) -> None:
    """Render 4-row feature attribute table with headers, scales, encoding, and footnote."""
    headers = info_block.get("headers", ["Признак", "Шкала", "Кодирование", "Законность"])
    rows = info_block.get("rows", [])
    n_cols = max(1, len(headers))
    n_rows = min(4, len(rows))
    if n_rows == 0:
        return

    col_w = [90, 74, 86, 78] if n_cols == 4 else [332 // n_cols] * n_cols

    draw.rounded_rectangle([914, 264, 1246, 282], radius=3, fill=COL_COBALT_WASH, outline=COL_RULE, width=1)
    cx = 918
    for c_i, h in enumerate(headers[:n_cols]):
        cw = col_w[c_i]
        ht, hf = _fit_single_line(draw, str(h), fonts["pill_10"], [fonts["pill_95"]], cw - 4)
        draw.text((cx, 267), ht, fill=COL_COBALT, font=hf)
        cx += cw

    row_h = (398 - 286) // n_rows
    for r_i, r in enumerate(rows[:n_rows]):
        ry0 = 286 + r_i * row_h
        ry1 = ry0 + row_h - 2
        bg = COL_PAPER if r_i % 2 == 1 else COL_SHEET
        draw.rounded_rectangle([914, ry0, 1246, ry1], radius=3, fill=bg, outline=COL_RULE, width=1)

        cell_vals = [str(x) for x in r] if isinstance(r, (list, tuple)) else [str(r)]
        cx = 918
        for c_i in range(n_cols):
            cw = col_w[c_i]
            v_str = cell_vals[c_i] if c_i < len(cell_vals) else ""
            fg = COL_INK
            if any(k in v_str for k in ("One-Hot", "Complete", "[OK]", "Без потерь", "Мин-Макс")):
                fg = COL_EMERALD
            elif any(k in v_str for k in ("КРИТИЧ", "MAR", "Missing")):
                fg = COL_ROSE if "КРИТИЧ" in v_str else COL_AMBER
            elif any(k in v_str for k in ("Ранги", "Единичная")):
                fg = COL_COBALT

            ct, cf = _fit_single_line(draw, v_str, fonts["pill_s"], [fonts["pill_10"], fonts["pill_95"]], cw - 4)
            draw.text((cx, ry0 + max(1, (row_h - 16) // 2)), ct, fill=fg, font=cf)
            cx += cw

    footnote = info_block.get("footnote", "")
    if footnote:
        draw.rounded_rectangle([914, 402, 1246, 426], radius=4, fill=COL_COBALT_WASH, outline=COL_COBALT, width=1)
        ft, ff = _fit_single_line(draw, footnote, fonts["pill_10"], [fonts["pill_95"]], 320)
        draw.text((920, 406), ft, fill=COL_COBALT, font=ff)


def _render_importance_bars(
    draw: ImageDraw.ImageDraw, info_block: Dict[str, Any], u: float, fonts: Dict[str, Any]
) -> None:
    """Render horizontal feature importance bar chart with drop-column dF1 and cumulative Lift banner."""
    subtitle = info_block.get("subtitle", "Падение метрики F1 при удалении признака:")
    st, sf = _fit_single_line(draw, subtitle, fonts["pill_s"], [fonts["pill_10"], fonts["pill_95"]], 330)
    draw.text((916, 264), st, fill=COL_INK_2, font=sf)

    bars = info_block.get("bars", [])
    n_bars = min(5, len(bars))
    col_map = {
        "rose": COL_ROSE,
        "amber": COL_AMBER,
        "blue": COL_COBALT,
        "emerald": COL_EMERALD,
    }

    by = 282
    for b_i, b in enumerate(bars[:n_bars]):
        b_name = b.get("name", f"feat_{b_i}")
        val = float(b.get("val", -0.05))
        val_str = b.get("val_str", f"{val:.3f}")
        c_name = b.get("color", "blue")
        fg = col_map.get(c_name, COL_COBALT)

        lt, lf = _fit_single_line(draw, b_name, fonts["pill_10"], [fonts["pill_95"]], 96)
        draw.text((914, by + 1), lt, fill=COL_INK, font=lf)

        track_w = 140
        draw.rounded_rectangle([1016, by + 4, 1016 + track_w, by + 13], radius=3, fill=COL_PAPER, outline=COL_RULE, width=1)

        ratio = min(1.0, abs(val) / 0.08)
        dyn_ratio = ratio * (0.20 + 0.80 * u)
        fill_w = max(6, int(track_w * dyn_ratio))
        draw.rounded_rectangle([1016, by + 4, 1016 + fill_w, by + 13], radius=3, fill=fg)

        draw.text((1164, by + 1), val_str, fill=fg, font=fonts["mono_b"])
        by += 23

    kpi_badge = info_block.get("kpi_badge", "Охват топ-20% базы перехватывает 55% оттока (Lift = 2.75x)")
    draw.rounded_rectangle([914, 402, 1246, 426], radius=4, fill=COL_EMERALD_WASH, outline=COL_EMERALD, width=1)
    kt, kf = _fit_single_line(draw, kpi_badge, fonts["pill_10"], [fonts["pill_95"]], 320)
    draw.text((920, 406), kt, fill=COL_EMERALD, font=kf)


def _get_phase_chrome_template(ch_spec: Dict[str, Any], phase_idx: int, fonts: Dict[str, Any]) -> Image.Image:
    cache_key = (ch_spec["ch_id"], phase_idx)
    tpl = _PHASE_CHROME_CACHE.get(cache_key)
    if tpl is not None:
        return tpl
    tpl = Image.new("RGB", (1280, 720), COL_PAPER)
    draw = ImageDraw.Draw(tpl)

    # 1. Top Slim Header Bar (height: 50px) — dynamically size chapter badge & 4 phase pills with generous padding
    draw.rectangle([0, 0, 1280, 50], fill=COL_SHEET)
    draw.line([0, 50, 1280, 50], fill=COL_RULE, width=1)
    badge_lbl = f"\u0413\u043b\u0430\u0432\u0430 {ch_spec['ch_num']} \u00b7 \u041c\u041e\u0438\u0410\u0414"
    badge_tw = _text_width(draw, badge_lbl, fonts["pill_b"])
    badge_x0 = 20
    badge_x1 = badge_x0 + badge_tw + 28
    draw.rounded_rectangle([badge_x0, 10, badge_x1, 40], radius=6, fill=COL_COBALT_WASH, outline=COL_COBALT, width=1)
    draw.text(((badge_x0 + badge_x1) // 2, 25), badge_lbl, fill=COL_COBALT, font=fonts["pill_b"], anchor="mm")

    pill_specs: List[Tuple[str, int, bool, bool]] = []
    for p_i, ph in enumerate(ch_spec["phases"]):
        lbl = f"{ph['num']} {ph['title'].split()[0]}"
        pw = max(96, _text_width(draw, lbl, fonts["pill_s"]) + 24)
        pill_specs.append((lbl, pw, p_i == phase_idx, p_i < phase_idx))

    total_pills_w = sum(pw for _, pw, _, _ in pill_specs) + 6 * (len(pill_specs) - 1)
    pills_start_x = 1260 - total_pills_w
    px_cursor = pills_start_x
    for lbl, pw, is_act, is_done in pill_specs:
        bg = COL_COBALT_WASH if is_act else (COL_EMERALD_WASH if is_done else COL_PAPER)
        bd = COL_COBALT if is_act else (COL_EMERALD if is_done else COL_RULE)
        fg = COL_COBALT if is_act else (COL_EMERALD if is_done else COL_MUTED)
        draw.rounded_rectangle([px_cursor, 10, px_cursor + pw, 40], radius=6, fill=bg, outline=bd, width=2 if is_act else 1)
        draw.text((px_cursor + pw // 2, 25), lbl, fill=fg, font=fonts["pill_s"], anchor="mm")
        px_cursor += pw + 6

    title_x0 = badge_x1 + 16
    max_title_w = pills_start_x - title_x0 - 16
    hdr_txt, hdr_fnt = _fit_single_line(draw, ch_spec["title"], fonts["hdr_b"], [fonts["hdr_m"], fonts["card_t"], fonts["pill_b"]], max_title_w)
    draw.text((title_x0, 25), hdr_txt, fill=COL_INK, font=hdr_fnt, anchor="lm")

    # Stage border + Right Telemetry & Formula Rail static cards
    draw.rounded_rectangle([19, 59, 885, 601], radius=10, fill=COL_SHEET, outline=COL_RULE_STRONG, width=1)
    draw.rounded_rectangle([900, 60, 1260, 216], radius=8, fill=COL_SHEET, outline=COL_RULE_STRONG, width=1)
    draw.rounded_rectangle([900, 60, 1260, 92], radius=8, fill=COL_COBALT_WASH, outline=COL_RULE_STRONG, width=1)
    f_hdr_txt, f_hdr_fnt = _fit_single_line(draw, f"01 · {ch_spec['formula_title']}", fonts["pill_b"], [fonts["pill_s"], fonts["pill_10"], fonts["pill_95"]], 332)
    draw.text((914, 68), f_hdr_txt, fill=COL_COBALT, font=f_hdr_fnt)
    formula_expr = ch_spec.get("formula_latex") or ch_spec.get("formula_str", "")
    ey = 98
    rendered_latex = False
    if formula_expr and (formula_expr.startswith("$") or "\\" in formula_expr):
        try:
            eq_img = render_latex_to_slot(formula_expr, max_w=332, max_h=38, color="#18212F")
            if eq_img is not None and eq_img.width > 1 and eq_img.height > 1 and eq_img.getbbox() is not None:
                tpl.paste(eq_img, (914, ey), mask=eq_img)
                ey += eq_img.height + 6
                rendered_latex = True
        except Exception:
            rendered_latex = False

    if not rendered_latex:
        raw_formula = ch_spec.get("formula_str") or formula_expr
        eq_lines = _wrap_lines(draw, raw_formula, fonts["eq_b"], 332)
        for el in eq_lines[:2]:
            draw.text((914, ey), el, fill=COL_INK, font=fonts["eq_b"])
            ey += 20
    desc_lines = _wrap_lines(draw, ch_spec["formula_desc"], fonts["body_s"], 332)
    for dl in desc_lines[:3]:
        draw.text((914, ey + 4), dl, fill=COL_INK_2, font=fonts["body_s"])
        ey += 17

    draw.rounded_rectangle([900, 228, 1260, 434], radius=8, fill=COL_SHEET, outline=COL_RULE_STRONG, width=1)
    info_block = ch_spec.get("info_block")
    card2_title = f"02 · {info_block['title']}" if (info_block and info_block.get("title")) else "02 · Живая телеметрия модели"
    c2_txt, c2_fnt = _fit_single_line(draw, card2_title, fonts["card_t"], [fonts["pill_b"], fonts["pill_s"]], 332)
    draw.text((914, 238), c2_txt, fill=COL_INK, font=c2_fnt)
    if not info_block:
        gy = 266
        for g in ch_spec.get("gauges", [])[:3]:
            v0, v1 = float(g.get("v0", 0.0)), float(g.get("v1", 0.0))
            is_pinned = bool(g.get("pinned", False)) or abs(v1 - v0) < 1e-6
            vw0 = _text_width(draw, f"{v0:.3f} {g['unit']}" if abs(v1) < 2.0 and v1 != int(v1) else f"{v0:.1f} {g['unit']}", fonts["mono_b"])
            vw1 = _text_width(draw, f"{v1:.3f} {g['unit']}" if abs(v1) < 2.0 and v1 != int(v1) else f"{v1:.1f} {g['unit']}", fonts["mono_b"])
            max_vw = max(vw0, vw1)
            if is_pinned:
                badge_lbl = "[ИНВАРИАНТ]" if "инвариант" in g.get("label", "").lower() else "[ФИКС]"
                max_vw += _text_width(draw, badge_lbl, fonts["pill_s"]) + 14
            max_label_w = 1246 - max_vw - 16 - 914
            lbl_txt, lbl_fnt = _fit_single_line(draw, g["label"], fonts["body_s"], [fonts["pill_s"], fonts["pill_10"], fonts["pill_95"]], max_label_w)
            draw.text((914, gy), lbl_txt, fill=COL_INK_2, font=lbl_fnt)
            gy += 52

    act_ph = ch_spec["phases"][phase_idx]
    draw.rounded_rectangle([900, 446, 1260, 600], radius=8, fill=COL_SHEET, outline=COL_COBALT, width=2)
    draw.rounded_rectangle([900, 446, 1260, 478], radius=8, fill=COL_COBALT_WASH, outline=COL_COBALT, width=1)
    p_hdr_txt, p_hdr_fnt = _fit_single_line(draw, f"\u0417\u0432\u0435\u043d\u043e {act_ph['num']} · {act_ph['title']}", fonts["pill_b"], [fonts["pill_s"], fonts["pill_10"], fonts["pill_95"]], 332)
    draw.text((914, 454), p_hdr_txt, fill=COL_COBALT, font=p_hdr_fnt)
    p_lines = _wrap_lines(draw, act_ph["desc"], fonts["body"], 332)
    py = 488
    for pl in p_lines[:4]:
        draw.text((914, py), pl, fill=COL_INK, font=fonts["body"])
        py += 20
    draw.rounded_rectangle([914, 578, 1246, 588], radius=4, fill=COL_PAPER, outline=COL_RULE, width=1)

    draw.rounded_rectangle([20, 612, 1260, 706], radius=8, fill=COL_SHEET, outline=COL_RULE_STRONG, width=1)
    draw.rounded_rectangle([20, 612, 26, 706], radius=3, fill=COL_COBALT)

    _PHASE_CHROME_CACHE[cache_key] = tpl
    return tpl


def _partition_subtitle_page_words(
    draw: ImageDraw.ImageDraw, words: List[Any], font: Any, max_w: int = 1040
) -> Tuple[List[Any], List[Any]]:
    """Partition subtitle page words into 1 line (if <= 860px) or 2 balanced lines avoiding danglings."""
    if not words:
        return [], []
    if len(words) == 1:
        return [words[0]], []

    word_texts = [
        getattr(w, "word", "") if hasattr(w, "word") else (w.get("word", "") if isinstance(w, dict) else str(w))
        for w in words
    ]
    n = len(words)
    space_w = 14
    word_widths = [_text_width(draw, wt, font) for wt in word_texts]
    total_w = sum(word_widths) + space_w * max(0, n - 1)
    if total_w <= 620 and n <= 6:
        return words, []

    best_k = None
    best_score = float("-inf")

    for k in range(1, n):
        l0_w = sum(word_widths[:k]) + space_w * max(0, k - 1)
        l1_w = sum(word_widths[k:]) + space_w * max(0, n - k - 1)
        if l0_w > max_w or l1_w > max_w:
            continue

        last_w0 = word_texts[k - 1].lower().rstrip(",;:.!?-—–")
        dangling_pen = -1000.0 if last_w0 in _DANGLING_WORDS else 0.0

        clause_bonus = 0.0
        raw_last_w0 = word_texts[k - 1]
        ratio0 = l0_w / max(1.0, float(l0_w + l1_w))
        if 0.32 <= ratio0 <= 0.68:
            if raw_last_w0.endswith((".", "!", "?")):
                clause_bonus += 80.0
            elif raw_last_w0.endswith((";", ":", "\u2014", "\u2013")):
                clause_bonus += 60.0
            elif raw_last_w0.endswith(","):
                clause_bonus += 40.0

        balance_pen = -abs(l0_w - l1_w) / 3.5
        count_pen = -abs(k - (n - k)) * 6.0

        score = dangling_pen + clause_bonus + balance_pen + count_pen
        if score > best_score:
            best_score = score
            best_k = k

    if best_k is None:
        best_k = max(1, n // 2)

    return words[:best_k], words[best_k:]


def render_moiad_chapter_frame(
    backdrop_arr: np.ndarray,
    ch_spec: Dict[str, Any],
    flow_sc: Any,
    u_prog: float,
    fonts: Dict[str, Any],
    sentence_boundaries: Optional[List[float]] = None,
) -> Image.Image:
    """
    Composite a single 1280x720 HD Almanac Editorial Daylight frame at `u_prog` in `[0, 1]`.
    If `sentence_boundaries = [tau_0, tau_1, tau_2, tau_3, total_dur]` is supplied,
    the active phase and panel spotlight are locked frame-accurately to narration speech.
    """
    u = float(min(1.0, max(0.0, u_prog)))

    # Discover sentence_boundaries from metadata if not explicitly supplied
    if sentence_boundaries is None:
        sentence_boundaries = getattr(flow_sc, "sentence_boundaries", None)
        if sentence_boundaries is None and hasattr(flow_sc, "captions"):
            sentence_boundaries = getattr(flow_sc.captions, "sentence_boundaries", None)
        if sentence_boundaries is None and isinstance(ch_spec, dict):
            sentence_boundaries = ch_spec.get("sentence_boundaries")

    if sentence_boundaries and len(sentence_boundaries) >= 5:
        sb = [float(x) for x in sentence_boundaries]
        tau_0, tau_1, tau_2, tau_3 = sb[0], sb[1], sb[2], sb[3]
        total_dur = max(0.01, sb[4])
        t_curr = u * total_dur

        if t_curr < tau_1:
            phase_idx = 0
            t_k, t_next = tau_0, tau_1
        elif t_curr < tau_2:
            phase_idx = 1
            t_k, t_next = tau_1, tau_2
        elif t_curr < tau_3:
            phase_idx = 2
            t_k, t_next = tau_2, tau_3
        else:
            phase_idx = 3
            t_k, t_next = tau_3, total_dur

        phase_local = min(1.0, max(0.0, (t_curr - t_k) / max(0.01, t_next - t_k)))

        # Dynamic spotlight switch: Left panel when t_curr < tau_2, Right panel when t_curr >= tau_2
        tau_switch = sb[5] if len(sb) >= 6 else tau_2
        u_switch = min(0.95, max(0.05, tau_switch / total_dur))
    else:
        phase_idx = min(3, int(u * 4.0))
        phase_local = min(1.0, max(0.0, (u - phase_idx * 0.25) / 0.25))
        u_switch = 0.50

    canvas = _get_phase_chrome_template(ch_spec, phase_idx, fonts).copy()
    draw = ImageDraw.Draw(canvas)

    # 2. Left Mathematical Animation Stage (x: 20..884, y: 60..600 -> 864x540)
    stage_base = Image.fromarray(backdrop_arr, mode="RGB")
    stage_anim = _draw_stage_overlay_2x(stage_base, ch_spec["mode"], u, u_switch=u_switch)
    canvas.paste(stage_anim, (20, 60))

    # 3. Dynamic Gauges or Modular Card 2 Info Block
    info_block = ch_spec.get("info_block")
    if info_block:
        b_type = info_block.get("type")
        if b_type == "metric_table":
            _render_metric_table(draw, info_block, u, fonts)
        elif b_type == "confusion_matrix":
            _render_confusion_matrix(draw, info_block, u, fonts)
        elif b_type == "flowchart":
            _render_flowchart(draw, info_block, phase_idx, u, fonts)
        elif b_type == "theorem_card":
            _render_theorem_card(draw, info_block, u, fonts)
        elif b_type == "feature_table":
            _render_feature_table(draw, info_block, u, fonts)
        elif b_type == "importance_bars":
            _render_importance_bars(draw, info_block, u, fonts)
        else:
            _render_frozen_gauges(draw, ch_spec.get("gauges", []), u, fonts)
    else:
        _render_frozen_gauges(draw, ch_spec.get("gauges", []), u, fonts)

    draw.rounded_rectangle([914, 578, 914 + max(10, int(332 * phase_local)), 588], radius=4, fill=COL_COBALT)

    # 4. Word-level synced subtitles
    dur_sec = float(getattr(flow_sc, "duration_sec", 0.0) or 0.0)
    captions = getattr(flow_sc, "captions", None)
    if dur_sec <= 0.0 and captions and getattr(captions, "duration_ms", 0):
        dur_sec = float(captions.duration_ms) / 1000.0
    if dur_sec <= 0.0:
        dur_sec = 16.0
    t_sec = u * dur_sec

    def _get_sec(obj: Any, key_sec: str, key_ms: str) -> Optional[float]:
        if hasattr(obj, key_sec):
            val = getattr(obj, key_sec)
            if val is not None:
                return float(val)
        if hasattr(obj, key_ms):
            val = getattr(obj, key_ms)
            if val is not None:
                return float(val) / 1000.0
        if isinstance(obj, dict):
            if key_sec in obj and obj[key_sec] is not None:
                return float(obj[key_sec])
            if key_ms in obj and obj[key_ms] is not None:
                return float(obj[key_ms]) / 1000.0
        return None

    pages = getattr(captions, "pages", None) or (captions.get("pages") if isinstance(captions, dict) else None) or []
    all_words = (
        getattr(captions, "all_words", None)
        or getattr(captions, "words", None)
        or (captions.get("all_words") or captions.get("words") if isinstance(captions, dict) else None)
        or []
    )

    active_page = None
    if pages:
        for p_i, p in enumerate(pages):
            p_s = _get_sec(p, "start_sec", "start_ms")
            p_e = _get_sec(p, "end_sec", "end_ms")
            if p_s is None or p_e is None:
                continue
            next_p_s = None
            if p_i + 1 < len(pages):
                next_p_s = _get_sec(pages[p_i + 1], "start_sec", "start_ms")
            page_hold_end = next_p_s if next_p_s is not None else (p_e + 0.8)
            if p_s <= t_sec < page_hold_end:
                active_page = p
                break
        if active_page is None:
            first_p_s = _get_sec(pages[0], "start_sec", "start_ms")
            if first_p_s is not None and t_sec < first_p_s:
                active_page = pages[0]
            else:
                active_page = pages[-1]

    page_words = []
    if active_page:
        page_words = getattr(active_page, "words", None) or (active_page.get("words") if isinstance(active_page, dict) else None) or []
    elif all_words:
        act_idx = 0
        for w_i, wt in enumerate(all_words):
            ws = _get_sec(wt, "start_sec", "start_ms") or 0.0
            if ws <= t_sec:
                act_idx = w_i
        chunk_sz = 9
        chunk_start = (act_idx // chunk_sz) * chunk_sz
        page_words = all_words[chunk_start : chunk_start + chunk_sz]

    if page_words:
        active_word_obj = None
        for wt in page_words:
            ws = _get_sec(wt, "start_sec", "start_ms")
            we = _get_sec(wt, "end_sec", "end_ms")
            if ws is not None and we is not None:
                if ws <= t_sec <= we + 0.08:
                    active_word_obj = wt
                    break
                elif ws <= t_sec:
                    active_word_obj = wt
        if active_word_obj is None:
            active_word_obj = page_words[0]

        line0_words, line1_words = _partition_subtitle_page_words(draw, page_words, fonts["sub_r"], 1040)
        rendered_lines = [(line0_words, 643)] if not line1_words else [(line0_words, 626), (line1_words, 660)]
        ww_space = 14

        for line_words, cy in rendered_lines:
            if not line_words:
                continue
            w_txts = [
                getattr(wt, "word", "") if hasattr(wt, "word") else (wt.get("word", "") if isinstance(wt, dict) else str(wt))
                for wt in line_words
            ]
            w_widths = [_text_width(draw, wt_s, fonts["sub_r"]) for wt_s in w_txts]
            line_total_w = sum(w_widths) + ww_space * max(0, len(line_words) - 1)
            cx_start = max(42, 590 - line_total_w // 2)

            # Precalculate layout positions and active states
            word_slots = []
            cur_x = cx_start
            for wt, w_txt, ww_word in zip(line_words, w_txts, w_widths):
                is_active = (wt is active_word_obj) or (
                    hasattr(wt, "word_index") and hasattr(active_word_obj, "word_index")
                    and wt.word_index == active_word_obj.word_index
                )
                act_w = _text_width(draw, w_txt, fonts["sub_b"]) if is_active else ww_word
                pad_l = min(4 + max(0, (act_w - ww_word) // 2), 6)
                pad_r = min(4 + max(0, act_w - ww_word - (act_w - ww_word) // 2), 6)
                word_slots.append((wt, w_txt, ww_word, cur_x, is_active, act_w, pad_l, pad_r))
                cur_x += ww_word + ww_space

            # Pass 1: Render active background badge pill (fill never occludes adjacent text)
            for _, _, ww_word, cur_x, is_active, act_w, pad_l, pad_r in word_slots:
                if is_active:
                    draw.rounded_rectangle(
                        [cur_x - pad_l, cy - 2, cur_x + ww_word + pad_r, cy + 26],
                        radius=5,
                        fill=COL_COBALT_WASH,
                        outline=COL_COBALT,
                        width=1,
                    )

            # Pass 2: Render word texts on top (active in bold cobalt, others in regular ink)
            for _, w_txt, ww_word, cur_x, is_active, act_w, _, _ in word_slots:
                if is_active:
                    text_x = cur_x - (act_w - ww_word) // 2
                    draw.text((text_x, cy), w_txt, fill=COL_COBALT, font=fonts["sub_b"])
                else:
                    draw.text((cur_x, cy), w_txt, fill=COL_INK, font=fonts["sub_r"])
    else:
        sub_lines = _wrap_lines(draw, ch_spec["narration"], fonts["sub_r"], 1040)
        act_fb = sub_lines if len(sub_lines) <= 2 else [sub_lines[i : i + 2] for i in range(0, len(sub_lines), 2)][min((len(sub_lines) - 1) // 2, max(0, int(u * ((len(sub_lines) + 1) // 2))))]
        for s_i, sl in enumerate(act_fb):
            sl_w = _text_width(draw, sl, fonts["sub_r"])
            cx_fb = max(42, 590 - sl_w // 2)
            cy_fb = 643 if len(act_fb) == 1 else (626 + s_i * 34)
            draw.text((cx_fb, cy_fb), sl, fill=COL_INK, font=fonts["sub_r"])

    # Right-side animated voiceover equalizer bars inside subtitle box
    for b_i in range(10):
        bh = int(8 + 22 * abs(math.sin(u * 26.0 + b_i * 0.7)))
        bx = 1152 + b_i * 9
        ym = 659
        draw.rounded_rectangle([bx, ym - bh // 2, bx + 5, ym + bh // 2], radius=2, fill=COL_COBALT if b_i % 2 == 0 else COL_EMERALD)

    return canvas
