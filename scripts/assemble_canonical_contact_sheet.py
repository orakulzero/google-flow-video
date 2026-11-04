"""Assemble canonical Arcane concept arts into a high-resolution master contact sheet.

Unites all Milestone 2 (Requirement R2) canonical concept arts for Episode 1 intro:
- Streamer Ash (Turnaround & Desk)
- Vanguard Knight Lucas (Portrait, Turnaround & Solitary Back)
- Environments & Props (Streamer Room, PC Desk Closeup, 'Save the Empire' Game Screen, Stream Overlay)

Outputs:
  output/canonical_arcane_concepts/master_contact_sheet.png
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys
from typing import Sequence

from PIL import Image, ImageDraw, ImageFont

CANONICAL_DIR = Path("output/canonical_arcane_concepts")
BRAIN_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")

DEFAULT_CARDS: list[tuple[str, str]] = [
    ("streamer_ash_turnaround.png", "01. Streamer Ash — Character Turnaround & Roaring Triumph"),
    ("streamer_ash_desk.png", "02. Streamer Ash at Rectangular Desk — Dual Monitors (0 Rear Monitors)"),
    ("knight_lucas_portrait.png", "03. Lucas via PC Monitor — In-Game RPG Sprite & Round Buckler"),
    ("knight_lucas_turnaround.png", "04. Lucas Turnaround — Round Buckler Shield (Blue Boss) & Broadsword"),
    ("knight_lucas_solitary_back.png", "05. Lucas Solitary Back — Boss Hall & Princess Corpse Fading to Void"),
    ("streamer_room_environment.png", "06. Streamer Bedroom — Rectangular Desk & 'Save the Empire' Clear"),
    ("streamer_pc_desk_closeup.png", "07. Rectangular Desk Closeup — Straight Dual Monitors & 3-Ring RGB PC"),
    ("game_save_the_empire_screen.png", "08. 'Save the Empire' — Official Box Art & Throne Hall Clear UI"),
    ("stream_overlay_chat_donation.png", "09. Stream Broadcast UI — Live Chat, Facecam & Foxy 300,000 KRW Alert"),
]


def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        try:
            return ImageFont.truetype("arialbd.ttf", size)
        except Exception:
            return ImageFont.load_default()


def assemble_canonical_contact_sheet(
    image_cards: Sequence[tuple[Path, str]],
    output_path: Path,
    title: str = "CANONICAL ARCANE CONCEPT ARTS & REFERENCE PACK (EPISODE 1 R2)",
    subtitle: str = "Fortiche Production Arcane Style • High-Res Reference Bench • Native 1376x768 (16:9)",
    cols: int = 3,
    cell_w: int = 688,
    cell_h: int = 410,
) -> Path:
    """Renders a high-resolution grid contact sheet from canonical concept art images."""
    if not image_cards:
        raise ValueError("Cannot assemble contact sheet: image_cards list is empty.")

    rows = (len(image_cards) + cols - 1) // cols
    margin_x = 24
    margin_top = 110
    margin_bottom = 30
    gap = 16

    total_w = margin_x * 2 + cols * cell_w + (cols - 1) * gap
    total_h = margin_top + rows * cell_h + (rows - 1) * gap + margin_bottom

    # Dark matte charcoal canvas #0E1016
    sheet = Image.new("RGB", (total_w, total_h), (14, 16, 22))
    draw = ImageDraw.Draw(sheet)

    # Fonts
    font_title = _load_font("C:/Windows/Fonts/arialbd.ttf", 26)
    font_sub = _load_font("C:/Windows/Fonts/arial.ttf", 14)
    font_badge = _load_font("C:/Windows/Fonts/arialbd.ttf", 13)
    font_tag = _load_font("C:/Windows/Fonts/arialbd.ttf", 12)

    # Outer decorative subtle border
    draw.rectangle([6, 6, total_w - 7, total_h - 7], outline=(34, 41, 58), width=2)

    # Header section
    draw.text((margin_x, 24), title, fill=(240, 198, 105), font=font_title)  # Gold #F0C669
    draw.text((margin_x, 62), subtitle, fill=(155, 163, 184), font=font_sub)  # Slate #9BA3B8

    # Quality badge on right
    tag_text = "CANONICAL VERIFIED (R2)"
    tag_w = 180
    tag_h = 28
    tag_x = total_w - margin_x - tag_w
    tag_y = 28
    draw.rectangle([tag_x, tag_y, tag_x + tag_w, tag_y + tag_h], fill=(22, 45, 34), outline=(78, 186, 136), width=1)
    draw.text((tag_x + 14, tag_y + 6), tag_text, fill=(78, 186, 136), font=font_tag)

    # Header dividing rule
    draw.line([(margin_x, 92), (total_w - margin_x, 92)], fill=(42, 50, 69), width=1)

    badge_h = 32
    img_area_h = cell_h - badge_h

    for idx, (img_path, label) in enumerate(image_cards):
        r, c = divmod(idx, cols)
        x0 = margin_x + c * (cell_w + gap)
        y0 = margin_top + r * (cell_h + gap)
        x1 = x0 + cell_w
        y1 = y0 + cell_h

        # Card container with border
        draw.rectangle([x0, y0, x1, y1], fill=(18, 21, 30), outline=(42, 50, 69), width=1)

        # Card header badge bar
        draw.rectangle([x0, y0, x1, y0 + badge_h], fill=(28, 32, 46))
        draw.text((x0 + 12, y0 + 8), label, fill=(240, 240, 248), font=font_badge)

        # Image render
        if img_path.is_file():
            try:
                with Image.open(img_path) as src_im:
                    im = src_im.convert("RGB")
                    im.thumbnail((cell_w - 6, img_area_h - 6), Image.Resampling.LANCZOS)
                    paste_x = x0 + (cell_w - im.width) // 2
                    paste_y = y0 + badge_h + (img_area_h - im.height) // 2
                    sheet.paste(im, (paste_x, paste_y))
            except Exception as exc:
                err_msg = f"Failed to load image: {exc}"
                draw.text((x0 + 16, y0 + badge_h + 30), err_msg, fill=(230, 80, 80), font=font_sub)
        else:
            draw.text(
                (x0 + 16, y0 + badge_h + 30),
                f"Missing file: {img_path.name}",
                fill=(230, 80, 80),
                font=font_sub,
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, "PNG")
    print(f"Master contact sheet assembled successfully -> {output_path} ({total_w}x{total_h}, {output_path.stat().st_size} bytes)")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble canonical Arcane concept arts contact sheet.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=CANONICAL_DIR,
        help="Directory containing canonical concept art PNGs",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=CANONICAL_DIR / "master_contact_sheet.png",
        help="Output path for master contact sheet PNG",
    )
    parser.add_argument(
        "--brain-dir",
        type=Path,
        default=BRAIN_DIR,
        help="Optional destination brain directory for persistent embedding",
    )
    parser.add_argument("--cols", type=int, default=3, help="Grid columns (default: 3)")
    args = parser.parse_args()

    cards: list[tuple[Path, str]] = []
    for filename, label in DEFAULT_CARDS:
        card_p = args.input_dir / filename
        cards.append((card_p, label))

    out_file = assemble_canonical_contact_sheet(
        image_cards=cards,
        output_path=args.output,
        cols=args.cols,
    )

    if args.brain_dir and args.brain_dir.is_dir():
        brain_target = args.brain_dir / args.output.name
        shutil.copy2(out_file, brain_target)
        print(f"Copied master contact sheet to brain store -> {brain_target}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
