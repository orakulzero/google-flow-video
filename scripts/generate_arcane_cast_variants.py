"""Generate Arcane (Fortiche) style character concept sheets in Google Flow via Nano Banana Pro."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

PROJECT_ID = "7d9a2a67-9cd2-4a79-932e-717d2e29257f"
OUT_DIR = Path("output/ttd_arcane_characters")
BRAIN_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")

ARCANE_BASE = (
    "Character concept turnaround sheet in the hand-painted brushwork style of Fortiche Production Arcane: "
    "visible dynamic oil and gouache brushstrokes on skin and fabric, heavy impasto texture, bold expressive "
    "ink outlines blended with 3D volumetric chiaroscuro rim lighting, neutral parchment concept art background, "
    "showing close-up face portrait, 3/4 expression view, and full-body front/side turnaround. "
    "No text, no labels, no typography, no callout words."
)

CHARACTER_SPECS = [
    (
        "ash_arcane_v2.jpg",
        "Ash Everblack — Var 2 (Battlefield Tyrant / Dragon Eye)",
        f"{ARCANE_BASE} Subject: Commander Ash Everblack in battle mode, young dark-fantasy prince with rain-soaked "
        "disheveled jet-black hair, glowing golden dragon-slit eyes with dark insomnia rings, burn scars on his neck "
        "and bandaged hands, wearing a heavy black-and-gold imperial commander greatcoat with a dark fur mantle, "
        "holding a brass spyglass and glowing cyan mana crystal.",
    ),
    (
        "lucas_arcane_v1.jpg",
        "Lucas MacGregor — Var 1 (Golden SSR Vanguard Knight)",
        f"{ARCANE_BASE} Subject: Lucas MacGregor, tall broad-shouldered SSR-rank vanguard knight in his early twenties, "
        "tousled golden-blonde hair, warm yet resolute blue eyes, strong jawline with a thin cheek scar, wearing heavy "
        "polished silver-steel full plate armor with gold trim and a flowing royal-blue cape, carrying a massive "
        "iron tower shield and knightly broadsword.",
    ),
    (
        "lucas_arcane_v2.jpg",
        "Lucas MacGregor — Var 2 (Battle-Scarred Frontline Shield)",
        f"{ARCANE_BASE} Subject: Lucas MacGregor in grim frontline combat gear, muscular blonde knight with windswept "
        "golden hair, fierce protective expression, wearing dented weather-beaten gunmetal plate armor scorched by "
        "fire and rain, tattered azure cloak, resting a heavy steel greatsword on his shoulder.",
    ),
    (
        "damien_arcane_v1.jpg",
        "Damien — Var 1 (All-Seeing Eye Arcane Sniper)",
        f"{ARCANE_BASE} Subject: Damien, slender young marksman in his late teens with messy chestnut-brown hair, "
        "wearing a brass steampunk optical monocle lens over one eye, his irises glowing luminous pure white from "
        "his All-Seeing Eye skill, dressed in a worn brown leather sniper vest and long coat, holding the long-barreled "
        "black-and-gold arcane rifle Black Queen.",
    ),
    (
        "damien_arcane_v2.jpg",
        "Damien — Var 2 (Hooded Watchtower Sharpshooter)",
        f"{ARCANE_BASE} Subject: Damien in watchtower scout attire, youthful sharpshooter with tousled brown hair and "
        "intense amber-brown eyes, brass sniper goggles resting on his forehead, dark forest-green hooded cloak over "
        "a bandolier of glowing blue mana cartridges, holding a masterwork long-range hextech sniper musket.",
    ),
    (
        "evangeline_arcane_v1.jpg",
        "Evangeline Cross — Var 1 (Crimson Bastion Heavy Tank)",
        f"{ARCANE_BASE} Subject: Evangeline Cross, petite fierce teenage noblewoman knight with vibrant crimson-pink "
        "hair tied in twin tails, defiant confident smirk and bright ruby eyes, encased in oversized heavy silver-and-crimson "
        "fortress plate armor of House Cross, wielding a colossal steel knight lance and heavy heraldic tower shield.",
    ),
    (
        "evangeline_arcane_v2.jpg",
        "Evangeline Cross — Var 2 (Valkyrie Lance Heiress)",
        f"{ARCANE_BASE} Subject: Evangeline Cross in ornate noble battle armor, young fierce knight heiress with flowing "
        "rose-crimson hair and sharp aristocratic features, wearing intricate gothic silver-and-red plate armor with "
        "a white fur shoulder cape, holding a glowing ruby-tipped cavalry lance.",
    ),
    (
        "jupiter_arcane_v1.jpg",
        "Jupiter — Var 1 (Veteran One-Eyed Lightning Mercenary)",
        f"{ARCANE_BASE} Subject: Jupiter the Lightning Bolt, rugged charismatic 55-year-old female mercenary veteran "
        "with spiky ash-white hair, a black leather eyepatch over her left eye, weathered facial scars, a smirk with "
        "an unlit cigar, wearing a scorched dark leather trench coat with brass arcane coils and crackling blue "
        "lightning arcs around her gauntlets.",
    ),
    (
        "lily_arcane_v1.jpg",
        "Lily — Var 1 (Exhausted Red-Haired Alchemist & Fire Mage)",
        f"{ARCANE_BASE} Subject: Lily, young female fire mage and chief alchemist engineer with fiery red hair tied "
        "in a messy bun with stray locks, exhausted green eyes with heavy dark circles behind round brass spectacles, "
        "wearing a soot-stained leather alchemist apron over a dark crimson mage robe, holding a glowing amber fire "
        "mana core and rolled fortress blueprints.",
    ),
]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_dir = OUT_DIR / "raw_batch"
    raw_dir.mkdir(parents=True, exist_ok=True)

    pending = [(fname, label, prompt) for fname, label, prompt in CHARACTER_SPECS if not (OUT_DIR / fname).is_file()]
    if pending:
        prompts_file = OUT_DIR / "prompts_batch.txt"
        prompts_file.write_text("\n".join(p[2] for p in pending) + "\n", encoding="utf-8")

        env = os.environ.copy()
        env["GFLOW_CLI_BROWSER_PROXY"] = "http://127.0.0.1:7890"
        env["HTTPS_PROXY"] = "http://127.0.0.1:7890"
        env["HTTP_PROXY"] = "http://127.0.0.1:7890"
        env["GFLOW_CLI_FLOW_HOST"] = "flow.google.com"
        env["GFLOW_CLI_AGENT_CONFIRM"] = "never"
        env["GFLOW_CLI_BROWSER_WINDOW_POSITION"] = "-30000,-30000"
        env["GFLOW_CLI_UPDATE_CHECK"] = "0"

        for idx, (fname, label, prompt) in enumerate(pending, 1):
            target = OUT_DIR / fname
            print(f"[{idx}/{len(pending)}] Generating {fname} ({label})...", flush=True)
            cmd = [
                sys.executable,
                "-u",
                "-m",
                "gflow_cli",
                "image",
                "t2i",
                prompt,
                "--model",
                "nano-pro",
                "--aspect",
                "16:9",
                "--project",
                PROJECT_ID,
                "-o",
                str(target),
                "--json",
            ]
            proc = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
            print(f"  -> rc={proc.returncode} exists={target.is_file()}", flush=True)
            if proc.returncode != 0:
                print(proc.stdout[-600:], proc.stderr[-600:], flush=True)

    print("Building master Arcane character contact sheet...", flush=True)
    all_items = [
        ("ash_arcane_v1.jpg", "Ash Everblack — Var 1 ( Aristocrat Commander )"),
        *[(f, lbl) for f, lbl, _ in CHARACTER_SPECS],
    ]
    cols, rows = 2, 5
    cell_w, cell_h = 688, 410
    sheet = Image.new("RGB", (cols * cell_w + 30, rows * cell_h + 80), (14, 16, 22))
    draw = ImageDraw.Draw(sheet)
    try:
        title_font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 24)
        lbl_font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 16)
    except Exception:
        title_font = ImageFont.load_default()
        lbl_font = ImageFont.load_default()

    draw.text((20, 18), "TYRANT OF THE TOWER DEFENSE GAME — ARCANE (FORTICHE) CHARACTER SHEETS (GOOGLE FLOW NANO BANANA PRO)", fill=(235, 195, 110), font=title_font)

    for i, (fname, label) in enumerate(all_items):
        p = OUT_DIR / fname
        r_idx, c_idx = divmod(i, cols)
        x0 = 10 + c_idx * (cell_w + 10)
        y0 = 65 + r_idx * cell_h
        if p.is_file():
            im = Image.open(p).convert("RGB").resize((cell_w, 368), Image.Resampling.LANCZOS)
            sheet.paste(im, (x0, y0))
            shutil.copy2(p, BRAIN_DIR / fname)
        draw.rectangle([x0, y0 + 368, x0 + cell_w, y0 + 398], fill=(26, 30, 42))
        draw.text((x0 + 10, y0 + 374), f"{i + 1:02d}. {label}", fill=(240, 240, 245), font=lbl_font)

    sheet_path = OUT_DIR / "arcane_cast_contact_sheet.png"
    sheet.save(sheet_path)
    shutil.copy2(sheet_path, BRAIN_DIR / "arcane_cast_contact_sheet.png")
    print(f"Saved contact sheet to {sheet_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
