"""
src/flow_stream_overlays.py
High-performance programmatic Manga/Webtoon stream chat and donation overlay engine.
Features:
- High-DPI Pillow RGBA vector renderer with rounded frames and speech bubbles.
- Multi-font hierarchy (Segoe UI Bold, Impact, Comic Sans Bold, Malgun Gothic Bold for KRW/Hangul).
- Manga-style scrolling chat column strictly clamped to [960, 180, 1250, 580].
- Luxury Golden Donation Banner ("FOXY 300,000 KRW") at [840, 40, 1240, 165] with pulsing gold frame.
- Strict boundary clamp: all elements Y <= 580 to preserve bottom subtitle clearance [600, 720].
- Terminal void dissolve: smooth alpha fade-out to 0.0 for t >= 59.84s.
- 100% English-only source code and comments (0 literal Cyrillic characters).
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Canvas and layout boundaries
CANVAS_WIDTH: int = 1280
CANVAS_HEIGHT: int = 720
CHAT_X_MIN: int = 960
CHAT_Y_MIN: int = 180
CHAT_X_MAX: int = 1250
CHAT_Y_MAX: int = 580  # Hard ceiling: subtitle clearance starts at Y=600

DONATION_X_MIN: int = 840
DONATION_Y_MIN: int = 40
DONATION_X_MAX: int = 1240
DONATION_Y_MAX: int = 165

DONATION_START_T: float = 29.92
DONATION_END_T: float = 39.92
TERMINAL_VOID_START_T: float = 59.84
TERMINAL_VOID_FADE_DUR: float = 1.66


@dataclass(frozen=True)
class ChatMessage:
    msg_id: str
    t_start: float
    t_end: float
    username: str
    role: str  # "vip", "mod", "sub", "viewer", "system"
    badge_color: Tuple[int, int, int]
    text: str
    is_bubble: bool = False
    bubble_style: str = "normal"  # "normal", "shout", "golden"


# Curated chronological manga stream chat events synchronized with episode action beats
CHAT_TIMELINE: List[ChatMessage] = [
    # Beat 1: Wide Arena Boss Clash (0.00 - 9.96s)
    ChatMessage("m01", 0.8, 6.0, "TowerClimber", "sub", (70, 130, 240), "HE'S FIGHTING FLOOR 100 BOSS?!"),
    ChatMessage("m02", 2.0, 7.5, "MangaKing99", "viewer", (180, 180, 180), "Floor 100 has never been cleared!"),
    ChatMessage("m03", 3.8, 9.5, "DefenseGod", "mod", (40, 200, 120), "Look at SSR Lucas positioning! POG", is_bubble=True, bubble_style="shout"),
    ChatMessage("m04", 5.5, 11.0, "Gamer_Kai", "viewer", (160, 160, 160), "Is this real or a mod??"),
    # Beat 2: Low-Angle Shield Block & Sparks Parry (9.96 - 19.96s)
    ChatMessage("m05", 10.2, 16.0, "IronWall", "vip", (255, 180, 40), "PARRY INCOMING!! WATCH THE SHIELD!"),
    ChatMessage("m06", 11.8, 17.5, "BlondeKnightSimp", "sub", (220, 80, 160), "LUCAS BRACED THE BUCKLER!!"),
    ChatMessage("m07", 13.5, 19.2, "MangaFan_RU", "viewer", (170, 170, 210), "THE SPARK PARTICLES ARE INSANE!"),
    ChatMessage("m08", 15.0, 21.0, "DefenseGod", "mod", (40, 200, 120), "Counter-slash ready! CLEAVE HIM!"),
    # Beat 3: Decisive Final Strike to CLEAR! Fanfare (19.96 - 29.92s)
    ChatMessage("m09", 20.0, 26.5, "Floor100Wait", "sub", (70, 130, 240), "BROADSWORD CLEAVE CONNECTED!!", is_bubble=True, bubble_style="shout"),
    ChatMessage("m10", 21.5, 27.5, "NightRaid", "vip", (255, 180, 40), "HE SLICED RIGHT THROUGH!"),
    ChatMessage("m11", 23.2, 29.2, "TowerClimber", "sub", (70, 130, 240), "WAIT... IS THE BOSS DISSOLVING?!"),
    ChatMessage("m12", 25.0, 30.0, "MOD_Alpha", "mod", (40, 200, 120), "CLEAR! CLEAR! CONGRATULATIONS!!"),
    # Beat 4: Rectangular Desk Dual Monitors & Stream Setup (29.92 - 39.92s)
    ChatMessage("m13", 30.2, 38.0, "Foxy_VIP", "vip", (255, 215, 0), "[DONATION] 300,000 KRW SENT!!", is_bubble=True, bubble_style="golden"),
    ChatMessage("m14", 31.0, 37.5, "GamerGirl_Yuna", "sub", (220, 80, 160), "FIRST IN THE WORLD TO CLEAR FLOOR 100!"),
    ChatMessage("m15", 32.5, 38.8, "DefenseGod", "mod", (40, 200, 120), "GOAT STREAMER CONFIRMED!! \U0001f3c6"),
    ChatMessage("m16", 34.0, 39.5, "AshArmy", "viewer", (180, 180, 180), "Buy yourself the best steak Ash!"),
    # Beat 5: Strategy Map to Streamer Remorse (39.92 - 49.88s)
    ChatMessage("m17", 40.5, 47.0, "LoreMaster", "sub", (130, 140, 250), "Wait... look at the casualty list..."),
    ChatMessage("m18", 42.0, 48.2, "SadBoi_99", "viewer", (170, 170, 170), "Did the priestess survive?"),
    ChatMessage("m19", 43.8, 49.5, "MangaKing99", "viewer", (180, 180, 180), "Zero HP on entire party except Lucas..."),
    ChatMessage("m20", 45.5, 51.0, "SilentKnight", "sub", (200, 90, 90), "He sacrificed everyone for the win..."),
    # Beat 6: Broadcast Workstation to Ramparts (49.88 - 59.84s)
    ChatMessage("m21", 50.2, 57.0, "TowerClimber", "sub", (100, 100, 150), "...at what cost?"),
    ChatMessage("m22", 52.0, 58.5, "Foxy_VIP", "vip", (200, 180, 80), "Lucas is standing alone in the ruins..."),
    ChatMessage("m23", 54.0, 59.5, "DefenseGod", "mod", (100, 140, 120), "Chat slow down... look at his back..."),
    ChatMessage("m24", 56.0, 59.84, "AshArmy", "viewer", (120, 120, 120), "..."),
    # Beat 7: Terminal Void (59.84 - 69.83s) -> ALL DISSOLVED TO ZERO ALPHA
]


@dataclass(frozen=True)
class FloatingPopup:
    popup_id: str
    t_start: float
    t_end: float
    username: str
    text: str
    box_xy: Tuple[int, int, int, int]  # (x0, y0, x1, y1) in [40..480, 60..520]
    badge_color: Tuple[int, int, int]
    style: str = "manga_box"  # "manga_box", "shout", "golden"


# Staggered floating manga comment boxes across left canvas [40..480, 60..520]
FLOATING_POPUPS: List[FloatingPopup] = [
    # Beat 1: Wide Arena Boss Clash (0.00 - 9.96s)
    FloatingPopup("fp01", 2.5, 6.5, "RaidLeader_K", "Colossal shadow aura is wiping vanguard!!", (45, 90, 365, 134), (220, 60, 60), "shout"),
    FloatingPopup("fp02", 5.5, 9.2, "SteelVanguard", "Tank hold aggro! Watch the abyssal claw!", (60, 220, 385, 264), (70, 130, 240), "manga_box"),
    # Beat 2: Low-Angle Shield Block & Sparks Parry (9.96 - 19.96s)
    FloatingPopup("fp03", 10.5, 15.0, "AegisMaster", "ROUND SHIELD PARRY!! LOOK AT SPARKS!", (50, 120, 375, 164), (255, 180, 40), "shout"),
    FloatingPopup("fp04", 14.5, 19.0, "BladeWatcher", "Lucas absorbed the shockwave! Counter ready!", (70, 320, 395, 364), (40, 200, 120), "manga_box"),
    # Beat 3: Decisive Final Strike to CLEAR! Fanfare (19.96 - 29.92s)
    FloatingPopup("fp05", 20.5, 25.5, "BossHunter99", "CRITICAL CORE PIERCE!! BOSS SHATTERS!", (45, 80, 370, 124), (255, 90, 110), "shout"),
    FloatingPopup("fp06", 24.5, 29.2, "EmpireHerald", "GOLDEN MANA BURST! CLEAR CONFIRMED!!", (60, 260, 390, 304), (255, 215, 0), "golden"),
    # Beat 4: Rectangular Desk Dual Monitors & Stream Setup (29.92 - 39.92s)
    FloatingPopup("fp07", 31.0, 36.5, "Foxy_Donator", "300,000 KRW FOR GREATEST DEFENSE!", (50, 140, 410, 184), (255, 215, 0), "golden"),
    FloatingPopup("fp08", 34.5, 39.2, "PC_Modder", "Dual monitors glowing like sacred relics! GG!", (65, 380, 400, 424), (180, 100, 240), "manga_box"),
    # Beat 5: Strategy Map to Streamer Remorse (39.92 - 49.88s)
    FloatingPopup("fp09", 42.0, 47.5, "LoreSeeker", "Only Lucas survived?! Where is the priestess?!", (55, 160, 395, 204), (100, 150, 240), "manga_box"),
    # Beat 6: Broadcast Workstation to Ramparts (49.88 - 59.84s)
    FloatingPopup("fp10", 51.0, 57.0, "SilentObserver", "Standing alone amidst the shattered throne...", (60, 240, 405, 284), (150, 150, 170), "manga_box"),
]



class FontManager:
    """Loads and caches required Windows fonts with reliable fallbacks."""

    def __init__(self) -> None:
        self._fonts: Dict[Tuple[str, int], ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}
        self.font_dir = Path("C:/Windows/Fonts")

    def get_font(self, font_name: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        key = (font_name.lower(), size)
        if key in self._fonts:
            return self._fonts[key]

        font_path = self.font_dir / font_name
        loaded: ImageFont.FreeTypeFont | ImageFont.ImageFont
        if font_path.is_file():
            try:
                loaded = ImageFont.truetype(str(font_path), size=size)
            except Exception:
                loaded = ImageFont.load_default()
        else:
            # Fallback mapping
            fallbacks = ["arialbd.ttf", "arial.ttf", "segoeui.ttf"]
            loaded = ImageFont.load_default()
            for fb in fallbacks:
                fb_p = self.font_dir / fb
                if fb_p.is_file():
                    try:
                        loaded = ImageFont.truetype(str(fb_p), size=size)
                        break
                    except Exception:
                        continue
        self._fonts[key] = loaded
        return loaded


def draw_rounded_rectangle(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int, int, int],
    radius: int,
    fill: Optional[Tuple[int, int, int, int]] = None,
    outline: Optional[Tuple[int, int, int, int]] = None,
    width: int = 1,
) -> None:
    """Draw a smooth anti-aliased rounded rectangle with explicit RGBA fill and outline."""
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill, outline=outline, width=width)


def draw_golden_gradient_frame(
    img: Image.Image,
    xy: Tuple[int, int, int, int],
    radius: int = 10,
    pulse_phase: float = 0.0,
    alpha_scale: float = 1.0,
) -> None:
    """Draw a luxury metallic golden gradient container with pulsing border for donations."""
    x0, y0, x1, y1 = xy
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0 or alpha_scale <= 0.0:
        return

    # Background gradient: dark amber/obsidian to rich gold-brown
    bg_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(bg_overlay)
    base_alpha = int(220 * alpha_scale)

    for i in range(h):
        ratio = i / float(h)
        # Gradient from deep dark mahogany/black (25, 20, 15) to warm dark gold (65, 45, 15)
        r = int(22 + 45 * ratio)
        g = int(18 + 32 * ratio)
        b = int(12 + 10 * ratio)
        bg_draw.line([(0, i), (w, i)], fill=(r, g, b, base_alpha))

    # Mask to rounded rect
    mask = Image.new("L", (w, h), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([0, 0, w, h], radius=radius, fill=255)

    img.paste(bg_overlay, (x0, y0), mask)

    # Pulsing golden multi-tier border
    draw = ImageDraw.Draw(img)
    pulse_val = 0.5 + 0.5 * math.sin(pulse_phase)
    gold_outer_alpha = int((140 + 100 * pulse_val) * alpha_scale)
    gold_inner_alpha = int((200 + 55 * pulse_val) * alpha_scale)

    # Outer glow line
    draw.rounded_rectangle(
        [x0 - 1, y0 - 1, x1 + 1, y1 + 1],
        radius=radius + 1,
        outline=(255, 200, 50, int(gold_outer_alpha * 0.5)),
        width=1,
    )
    # Main golden border
    draw.rounded_rectangle(
        [x0, y0, x1, y1],
        radius=radius,
        outline=(255, 215, 0, gold_inner_alpha),
        width=2,
    )
    # Inner specular highlight
    draw.rounded_rectangle(
        [x0 + 2, y0 + 2, x1 - 2, y1 - 2],
        radius=max(1, radius - 2),
        outline=(255, 245, 180, int(80 * alpha_scale)),
        width=1,
    )


def draw_speech_bubble(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int, int, int],
    radius: int = 8,
    fill: Tuple[int, int, int, int] = (255, 255, 255, 230),
    outline: Tuple[int, int, int, int] = (20, 20, 30, 255),
    tail_side: str = "left",
    is_shout: bool = False,
) -> None:
    """Draw a comic/webtoon speech bubble with manga outline and directional indicator."""
    x0, y0, x1, y1 = xy
    if is_shout:
        # Action shout bubble with high-energy outline
        draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill, outline=outline, width=2)
        # Accent spikes/notches on edges
        mid_y = (y0 + y1) // 2
        draw.polygon([(x0 - 5, mid_y), (x0, mid_y - 6), (x0, mid_y + 6)], fill=fill, outline=outline)
    else:
        # Smooth rounded speech bubble
        draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill, outline=outline, width=1)
        if tail_side == "left":
            tail_y = min(y1 - 6, y0 + 14)
            draw.polygon([(x0 - 6, tail_y + 6), (x0, tail_y), (x0, tail_y + 8)], fill=fill, outline=outline)


def render_donation_banner(
    img: Image.Image,
    font_mgr: FontManager,
    t: float,
    alpha_scale: float = 1.0,
) -> None:
    """Render the luxury golden FOXY 300,000 KRW donation alert banner."""
    if t < DONATION_START_T or t > DONATION_END_T or alpha_scale <= 0.0:
        return

    # In/out animations: slide-in from top, slide-out
    rel_t = t - DONATION_START_T
    dur = DONATION_END_T - DONATION_START_T
    in_dur = 0.5
    out_dur = 0.5

    banner_alpha = alpha_scale
    y_offset = 0.0

    if rel_t < in_dur:
        progress = rel_t / in_dur
        # Smooth ease-out quad
        ease = 1.0 - (1.0 - progress) ** 2
        y_offset = -60.0 * (1.0 - ease)
        banner_alpha *= ease
    elif rel_t > (dur - out_dur):
        progress = (DONATION_END_T - t) / out_dur
        ease = progress ** 2
        y_offset = -60.0 * (1.0 - ease)
        banner_alpha *= ease

    curr_y0 = int(DONATION_Y_MIN + y_offset)
    curr_y1 = int(DONATION_Y_MAX + y_offset)
    if curr_y1 <= 0 or curr_y0 >= CANVAS_HEIGHT:
        return

    # Draw luxury gradient background with pulsing border
    pulse_phase = 2.0 * math.pi * 1.5 * t
    draw_golden_gradient_frame(
        img,
        (DONATION_X_MIN, curr_y0, DONATION_X_MAX, curr_y1),
        radius=12,
        pulse_phase=pulse_phase,
        alpha_scale=banner_alpha,
    )

    draw = ImageDraw.Draw(img)
    text_alpha = int(255 * banner_alpha)

    # Fonts
    font_title = font_mgr.get_font("impact.ttf", 20)
    font_krw = font_mgr.get_font("malgunbd.ttf", 22)
    font_msg = font_mgr.get_font("segoeuib.ttf", 13)
    font_badge = font_mgr.get_font("segoeuib.ttf", 11)

    # Top header bar: [DONATION] pill badge + "FOXY" + "300,000 KRW" (\u20a9 300,000)
    badge_x = DONATION_X_MIN + 16
    badge_y = curr_y0 + 14
    draw_rounded_rectangle(
        draw,
        (badge_x, badge_y, badge_x + 85, badge_y + 20),
        radius=4,
        fill=(255, 215, 0, int(220 * banner_alpha)),
        outline=(255, 255, 255, text_alpha),
        width=1,
    )
    draw.text((badge_x + 6, badge_y + 3), "DONATION", font=font_badge, fill=(20, 20, 20, text_alpha))

    # Username: FOXY
    user_x = badge_x + 95
    draw.text((user_x, curr_y0 + 12), "FOXY", font=font_title, fill=(255, 255, 255, text_alpha))

    # Amount: 300,000 KRW with Korean Won sign (\u20a9)
    amt_str = "\u20a9 300,000 KRW"
    draw.text((DONATION_X_MAX - 165, curr_y0 + 11), amt_str, font=font_krw, fill=(255, 225, 60, text_alpha))

    # Separator line
    line_y = curr_y0 + 44
    draw.line(
        [(DONATION_X_MIN + 16, line_y), (DONATION_X_MAX - 16, line_y)],
        fill=(255, 215, 0, int(100 * banner_alpha)),
        width=1,
    )

    # Donation message
    msg_y = curr_y0 + 54
    line1 = "Congrats on clearing floor 100 Tyrant!"
    line2 = "Buy yourself some meat tonight!"
    draw.text((DONATION_X_MIN + 18, msg_y), line1, font=font_msg, fill=(245, 245, 245, text_alpha))
    draw.text((DONATION_X_MIN + 18, msg_y + 20), line2, font=font_msg, fill=(255, 220, 120, text_alpha))


def render_chat_column(
    img: Image.Image,
    font_mgr: FontManager,
    t: float,
    alpha_scale: float = 1.0,
) -> None:
    """Render the semi-transparent manga stream chat HUD column clamped strictly to [960, 180, 1250, 580]."""
    if alpha_scale <= 0.0:
        return

    # Background container for chat
    col_w = CHAT_X_MAX - CHAT_X_MIN
    col_h = CHAT_Y_MAX - CHAT_Y_MIN

    chat_bg = Image.new("RGBA", (col_w, col_h), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(chat_bg)

    # Dark translucent manga panel background
    panel_alpha = int(165 * alpha_scale)
    bg_draw.rounded_rectangle(
        [0, 0, col_w, col_h],
        radius=10,
        fill=(12, 14, 22, panel_alpha),
        outline=(60, 75, 110, int(180 * alpha_scale)),
        width=1,
    )

    # Top header bar: "LIVE STREAM CHAT" with pulsating red dot
    font_header = font_mgr.get_font("segoeuib.ttf", 11)
    font_user = font_mgr.get_font("segoeuib.ttf", 11)
    font_body = font_mgr.get_font("segoeuib.ttf", 11)
    font_bubble = font_mgr.get_font("comicbd.ttf", 11)

    pulse = 0.5 + 0.5 * math.sin(t * 3.0)
    red_alpha = int((180 + 75 * pulse) * alpha_scale)
    bg_draw.ellipse([14, 11, 20, 17], fill=(255, 60, 60, red_alpha))
    bg_draw.text((26, 8), "LIVE CHAT \u2022 EPISODE 1 CLIMAX", font=font_header, fill=(200, 215, 240, int(220 * alpha_scale)))

    # Header separator line
    bg_draw.line([(8, 26), (col_w - 8, 26)], fill=(50, 65, 95, int(150 * alpha_scale)), width=1)

    # Select active messages at timestamp t
    active_msgs = [m for m in CHAT_TIMELINE if m.t_start <= t <= m.t_end]
    # Display the most recent active messages (up to 4)
    display_msgs = active_msgs[-4:] if len(active_msgs) > 4 else active_msgs

    # Stack messages from top to bottom inside the chat column
    curr_rel_y = 34
    max_rel_y = col_h - 10  # Ensure rel_y + msg_h <= col_h

    for m in display_msgs:
        # Age-based fade in
        age = t - m.t_start
        msg_alpha = alpha_scale
        if age < 0.35:
            msg_alpha *= (age / 0.35)
        # Fade out before disappearing
        time_left = m.t_end - t
        if time_left < 0.5:
            msg_alpha *= max(0.0, time_left / 0.5)

        m_alpha_int = int(255 * msg_alpha)
        if m_alpha_int <= 0:
            continue

        if m.is_bubble:
            # Manga styled speech bubble
            bubble_h = 38
            if curr_rel_y + bubble_h > max_rel_y:
                break
            b_x0, b_y0 = 10, curr_rel_y
            b_x1, b_y1 = col_w - 10, curr_rel_y + bubble_h

            if m.bubble_style == "golden":
                b_fill = (60, 50, 20, int(230 * msg_alpha))
                b_line = (255, 215, 0, int(240 * msg_alpha))
                text_col = (255, 235, 140, m_alpha_int)
            elif m.bubble_style == "shout":
                b_fill = (45, 20, 30, int(230 * msg_alpha))
                b_line = (255, 90, 110, int(240 * msg_alpha))
                text_col = (255, 220, 230, m_alpha_int)
            else:
                b_fill = (25, 30, 45, int(220 * msg_alpha))
                b_line = (90, 130, 220, int(220 * msg_alpha))
                text_col = (240, 245, 255, m_alpha_int)

            draw_speech_bubble(bg_draw, (b_x0, b_y0, b_x1, b_y1), radius=6, fill=b_fill, outline=b_line, is_shout=(m.bubble_style == "shout"))
            # User header inside bubble
            bg_draw.text((b_x0 + 8, b_y0 + 4), f"{m.username}:", font=font_user, fill=m.badge_color + (m_alpha_int,))
            bg_draw.text((b_x0 + 8, b_y0 + 19), m.text, font=font_bubble, fill=text_col)
            curr_rel_y += bubble_h + 8
        else:
            # Regular chat item with colored badge
            msg_h = 32
            if curr_rel_y + msg_h > max_rel_y:
                break
            # Badge pill
            badge_w = 42 if m.role == "vip" else (38 if m.role == "mod" else 32)
            bg_draw.rounded_rectangle(
                [12, curr_rel_y + 1, 12 + badge_w, curr_rel_y + 15],
                radius=3,
                fill=m.badge_color + (int(190 * msg_alpha),),
            )
            bg_draw.text((15, curr_rel_y + 2), m.role.upper(), font=font_user, fill=(255, 255, 255, m_alpha_int))
            # Username
            user_x = 12 + badge_w + 6
            bg_draw.text((user_x, curr_rel_y + 1), m.username, font=font_user, fill=(230, 235, 245, m_alpha_int))
            # Text body
            bg_draw.text((14, curr_rel_y + 16), m.text, font=font_body, fill=(200, 210, 225, m_alpha_int))
            curr_rel_y += msg_h + 6

    # Paste chat panel onto master canvas
    img.paste(chat_bg, (CHAT_X_MIN, CHAT_Y_MIN), chat_bg)


def render_floating_popups(
    img: Image.Image,
    font_mgr: FontManager,
    t: float,
    alpha_scale: float = 1.0,
) -> None:
    """Render staggered floating manga comment boxes across [40..480, 60..520]."""
    if alpha_scale <= 0.0:
        return

    active_popups = [p for p in FLOATING_POPUPS if p.t_start <= t <= p.t_end]
    if not active_popups:
        return

    draw = ImageDraw.Draw(img)
    font_user = font_mgr.get_font("segoeuib.ttf", 10)
    font_text = font_mgr.get_font("comicbd.ttf", 10)

    for p in active_popups:
        age = t - p.t_start
        p_alpha = alpha_scale
        if age < 0.35:
            p_alpha *= (age / 0.35)
        time_left = p.t_end - t
        if time_left < 0.4:
            p_alpha *= max(0.0, time_left / 0.4)

        alpha_int = int(255 * p_alpha)
        if alpha_int <= 0:
            continue

        x0, y0, x1, y1 = p.box_xy
        y1 = min(y1, 580)
        if y1 <= y0:
            continue

        if p.style == "golden":
            fill_bg = (40, 32, 12, int(220 * p_alpha))
            line_col = (255, 215, 0, int(240 * p_alpha))
            txt_col = (255, 235, 140, alpha_int)
        elif p.style == "shout":
            fill_bg = (38, 16, 22, int(220 * p_alpha))
            line_col = (255, 80, 100, int(240 * p_alpha))
            txt_col = (255, 220, 225, alpha_int)
        else:
            fill_bg = (16, 20, 32, int(210 * p_alpha))
            line_col = (70, 100, 180, int(220 * p_alpha))
            txt_col = (230, 240, 255, alpha_int)

        draw_speech_bubble(draw, (x0, y0, x1, y1), radius=6, fill=fill_bg, outline=line_col, is_shout=(p.style == "shout"))
        badge_pill_w = 28
        draw.rounded_rectangle([x0 + 6, y0 + 4, x0 + 6 + badge_pill_w, y0 + 17], radius=2, fill=p.badge_color + (int(200 * p_alpha),))
        draw.text((x0 + 8, y0 + 5), "CHAT", font=font_user, fill=(255, 255, 255, alpha_int))
        draw.text((x0 + 6 + badge_pill_w + 6, y0 + 4), f"{p.username}:", font=font_user, fill=p.badge_color + (alpha_int,))
        draw.text((x0 + 8, y0 + 20), p.text, font=font_text, fill=txt_col)


def render_monitor_typo_patch(
    img: Image.Image,
    font_mgr: FontManager,
    t: float,
    alpha_scale: float = 1.0,
) -> None:
    """
    Render clean sub-banner 'CONGRATULATIONS!' over [270, 336, 468, 366] in Beat 4
    to fix Veo misspelled sub-caption on the left monitor.
    """
    if t < 29.92 or t > 39.92 or alpha_scale <= 0.0:
        return

    draw = ImageDraw.Draw(img)
    x0, y0, x1, y1 = 270, 336, 468, 366
    fill_col = (14, 12, 10, int(250 * alpha_scale))
    line_col = (255, 215, 0, int(220 * alpha_scale))
    draw.rounded_rectangle([x0, y0, x1, y1], radius=3, fill=fill_col, outline=line_col, width=1)

    font_congrat = font_mgr.get_font("segoeuib.ttf", 13)
    txt = "CONGRATULATIONS!"
    bbox = font_congrat.getbbox(txt)
    txt_w = bbox[2] - bbox[0]
    txt_h = bbox[3] - bbox[1]
    tx = x0 + (x1 - x0 - txt_w) // 2
    ty = y0 + (y1 - y0 - txt_h) // 2 - 1
    draw.text((tx, ty), txt, font=font_congrat, fill=(255, 225, 75, int(255 * alpha_scale)))


class MangaStreamOverlayEngine:

    """High-performance 2D Manga/Webtoon stream overlay engine for Episode 1."""

    def __init__(self, width: int = CANVAS_WIDTH, height: int = CANVAS_HEIGHT) -> None:
        self.width = width
        self.height = height
        self.font_mgr = FontManager()

    def get_alpha_scale(self, t: float) -> float:
        """Compute global alpha multiplier enforcing smooth terminal void dissolve."""
        if t < TERMINAL_VOID_START_T:
            return 1.0
        elapsed = t - TERMINAL_VOID_START_T
        if elapsed >= TERMINAL_VOID_FADE_DUR:
            return 0.0
        # Smooth cosine or linear fade-out to 0.0
        return max(0.0, 0.5 * (1.0 + math.cos(math.pi * (elapsed / TERMINAL_VOID_FADE_DUR))))

    def render_overlay_frame(self, t: float) -> Image.Image:
        """Render a single standalone 1280x720 RGBA overlay frame for timestamp t."""
        alpha_scale = self.get_alpha_scale(t)
        frame = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))

        if alpha_scale <= 0.0:
            return frame

        # Render donation banner if active
        if DONATION_START_T - 0.5 <= t <= DONATION_END_T + 0.5:
            render_donation_banner(frame, self.font_mgr, t, alpha_scale=alpha_scale)

        # Render manga chat column
        render_chat_column(frame, self.font_mgr, t, alpha_scale=alpha_scale)

        # Render floating manga popups across left canvas
        render_floating_popups(frame, self.font_mgr, t, alpha_scale=alpha_scale)

        # Render monitor typo patch during Beat 4 (CLEAR! CONGRATULATIONS!)
        if 29.92 <= t <= 39.92:
            render_monitor_typo_patch(frame, self.font_mgr, t, alpha_scale=alpha_scale)

        # Hard invariant clamp: ensure zero alpha in subtitle clearance zone Y in [600, 720]
        # Any drawing at Y > 580 is strictly zeroed out
        arr = np.array(frame)
        if np.any(arr[581:, :, 3] > 0):
            arr[581:, :, 3] = 0
            frame = Image.fromarray(arr, mode="RGBA")

        return frame

    def composite_frame(self, base_img: Image.Image, t: float) -> Image.Image:
        """Composite dynamic overlay onto base frame using accelerated alpha composition."""
        alpha_scale = self.get_alpha_scale(t)
        if alpha_scale <= 0.0:
            return base_img.convert("RGB")

        overlay = self.render_overlay_frame(t)
        base_rgba = base_img.convert("RGBA") if base_img.mode != "RGBA" else base_img
        composited = Image.alpha_composite(base_rgba, overlay)
        return composited.convert("RGB")


def verify_overlay_bounds(overlay_img: Image.Image) -> Dict[str, Any]:
    """Verify that all non-zero pixels in overlay satisfy strict Y <= 580 boundary clamp."""
    arr = np.array(overlay_img)
    alpha = arr[:, :, 3]
    y_indices, x_indices = np.where(alpha > 0)
    if len(y_indices) == 0:
        return {"empty": True, "max_y": 0, "violations": 0, "valid": True}

    max_y = int(np.max(y_indices))
    min_y = int(np.min(y_indices))
    violations = int(np.sum(y_indices > 580))
    return {
        "empty": False,
        "min_y": min_y,
        "max_y": max_y,
        "violations": violations,
        "valid": violations == 0,
    }
