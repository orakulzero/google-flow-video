"""Download official manhwa frames, character portraits, and BGM from Fandom Wiki & AniList."""

from __future__ import annotations

from pathlib import Path
import urllib.request

from PIL import Image, ImageDraw, ImageFont

REF_DIR = Path("output/ttd_arcane_characters/manga_refs")
BRAIN_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")

MANHWA_ASSETS = [
    # Ash Everblack
    ("ash_manhwa_cover.jpg", "https://static.wikia.nocookie.net/i-became-the-tyrant-of-the-defense-tower-game/images/0/0d/Ash_Cover.jpg/revision/latest?cb=20240726172404"),
    ("ash_manhwa_portrait.jpg", "https://s4.anilist.co/file/anilistcdn/character/large/b318977-OEYu0Omcl1Cr.jpg"),
    ("ash_lucas_meet.png", "https://static.wikia.nocookie.net/i-became-the-tyrant-of-the-defense-tower-game/images/3/3c/Ash_Lucas_First_Meet.png/revision/latest?cb=20240726181634"),
    # Lucas MacGregor
    ("lucas_manhwa_intro.png", "https://static.wikia.nocookie.net/i-became-the-tyrant-of-the-defense-tower-game/images/5/58/Lucas_Intro.png/revision/latest?cb=20240726153842"),
    ("lucas_manhwa_portrait.jpg", "https://s4.anilist.co/file/anilistcdn/character/large/b319130-6xlSkF8Cwn2s.jpg"),
    ("lucas_manhwa_smile.png", "https://static.wikia.nocookie.net/i-became-the-tyrant-of-the-defense-tower-game/images/c/ca/Lucas_smile.png/revision/latest?cb=20240727155545"),
    # Damien
    ("damien_manhwa_action.png", "https://static.wikia.nocookie.net/i-became-the-tyrant-of-the-defense-tower-game/images/0/04/Damian_Action.png/revision/latest?cb=20240726225223"),
    ("damien_manhwa_eye.png", "https://static.wikia.nocookie.net/i-became-the-tyrant-of-the-defense-tower-game/images/c/c5/Thousand-Mile_Eye.png/revision/latest?cb=20240726152252"),
    ("damien_black_queen_gun.png", "https://static.wikia.nocookie.net/i-became-the-tyrant-of-the-defense-tower-game/images/f/f1/Black_Queen_Gun.png/revision/latest?cb=20240726195351"),
    # Evangeline Cross
    ("evangeline_manhwa_armor.png", "https://static.wikia.nocookie.net/i-became-the-tyrant-of-the-defense-tower-game/images/d/d3/Eva_L%2BS_OG.png/revision/latest?cb=20240726174045"),
    ("evangeline_manhwa_portrait.jpg", "https://s4.anilist.co/file/anilistcdn/character/large/b319131-kEOTBHTIsiBu.jpg"),
    ("evangeline_manhwa_future.png", "https://static.wikia.nocookie.net/i-became-the-tyrant-of-the-defense-tower-game/images/6/63/Eva_Future.png/revision/latest?cb=20240726161707"),
    # Jupiter
    ("jupiter_manhwa.png", "https://static.wikia.nocookie.net/i-became-the-tyrant-of-the-defense-tower-game/images/6/68/Jupiter.png/revision/latest?cb=20240726173735"),
    ("jupiter_junior_manhwa.png", "https://static.wikia.nocookie.net/i-became-the-tyrant-of-the-defense-tower-game/images/3/3c/Jupiter_junior_intro.png/revision/latest?cb=20240728023701"),
    # Lily & Eider & Stage 1 Boss
    ("lily_manhwa_1.png", "https://static.wikia.nocookie.net/i-became-the-tyrant-of-the-defense-tower-game/images/2/23/Lily1.png/revision/latest?cb=20240726040808"),
    ("lily_manhwa_portrait.jpg", "https://s4.anilist.co/file/anilistcdn/character/large/b318979-Y1rYk4rScrTh.jpg"),
    ("eider_manhwa.png", "https://static.wikia.nocookie.net/i-became-the-tyrant-of-the-defense-tower-game/images/2/2b/Eider.png/revision/latest?cb=20240726154650"),
    ("stage1_manhwa.png", "https://static.wikia.nocookie.net/i-became-the-tyrant-of-the-defense-tower-game/images/5/58/Stage_1.png/revision/latest?cb=20240727143642"),
    ("black_spider_queen_manhwa.png", "https://static.wikia.nocookie.net/i-became-the-tyrant-of-the-defense-tower-game/images/f/f9/Black_Spider_Queen.png/revision/latest?cb=20240726205808"),
]


def main() -> int:
    import subprocess

    REF_DIR.mkdir(parents=True, exist_ok=True)
    for fname, url in MANHWA_ASSETS:
        out_p = REF_DIR / fname
        clean_url = url.split("/revision/latest")[0]
        if not out_p.is_file() or out_p.stat().st_size < 500:
            subprocess.run(["curl.exe", "-sL", clean_url, "-o", str(out_p)], timeout=20, check=True)
        im = Image.open(out_p).convert("RGB")
        clean_p = REF_DIR / (out_p.stem + ".jpg")
        im.save(clean_p, quality=95)
        print(f"Downloaded {clean_p.name}: {im.size[0]}x{im.size[1]} ({clean_p.stat().st_size // 1024} KB)", flush=True)

    # Also download the 2 official Naver Webtoon BGM tracks from the Fandom Wiki
    bgm_tracks = [
        (
            "bgm_ep21_victory_banquet.ogg",
            "https://static.wikia.nocookie.net/i-became-the-tyrant-of-the-defense-tower-game/images/4/46/%E3%80%90%EB%84%A4%EC%9D%B4%EB%B2%84_%EC%9B%B9%ED%88%B0_%E2%80%98%EB%94%94%ED%8E%9C%EC%8A%A4_%EA%B2%8C%EC%9E%84%EC%9D%98_%ED%8F%AD%EA%B5%B0%EC%9D%B4_%EB%90%98%EC%97%88%EB%8B%A4%E2%80%99_21%ED%99%94_BGM%E3%80%91_MZ_-_%EC%8A%B9%EB%A6%AC_%EC%97%B0%ED%9A%8C",
        ),
        (
            "bgm_ep96_one_step_to_hell.ogg",
            "https://static.wikia.nocookie.net/i-became-the-tyrant-of-the-defense-tower-game/images/e/e9/%E3%80%90%EB%84%A4%EC%9D%B4%EB%B2%84_%EC%9B%B9%ED%88%B0_%E2%80%98%EB%94%94%ED%8E%9C%EC%8A%A4_%EA%B2%8C%EC%9E%84%EC%9D%98_%ED%8F%AD%EA%B5%B0%EC%9D%B4_%EB%90%98%EC%97%88%EB%8B%A4%E2%80%99_96%ED%99%94_BGM%E3%80%91_MZ_-_%EC%A7%80%EC%98%A5%EA%B9%8C%EC%A7%80_%ED%95%9C_%EA%B1%B8%EC%9D%8C",
        ),
    ]
    for bname, burl in bgm_tracks:
        bp = REF_DIR / bname
        if not bp.is_file() or bp.stat().st_size < 1000:
            subprocess.run(["curl.exe", "-sL", burl, "-o", str(bp)], timeout=30, check=False)
        if bp.is_file():
            print(f"Downloaded BGM {bp.name}: {bp.stat().st_size // 1024} KB", flush=True)

    # Build a visual reference sheet of the original manhwa frames
    grid_items = [
        ("ash_manhwa_cover.jpg", "Ash (Manhwa Cover)"),
        ("ash_manhwa_portrait.jpg", "Ash (Manhwa Portrait)"),
        ("lucas_manhwa_intro.jpg", "Lucas (Manhwa Intro)"),
        ("lucas_manhwa_portrait.jpg", "Lucas (Manhwa Portrait)"),
        ("damien_manhwa_action.jpg", "Damien (Manhwa Action)"),
        ("damien_manhwa_eye.jpg", "Damien (Thousand-Mile Eye)"),
        ("evangeline_manhwa_armor.jpg", "Evangeline (Lance & Shield)"),
        ("evangeline_manhwa_portrait.jpg", "Evangeline (Portrait)"),
        ("jupiter_manhwa.jpg", "Jupiter (Manhwa Frame)"),
        ("lily_manhwa_1.jpg", "Lily (Manhwa Frame)"),
        ("eider_manhwa.jpg", "Eider (Manhwa Frame)"),
        ("black_spider_queen_manhwa.jpg", "Stage 1 Boss: Black Spider Queen"),
    ]
    cols, rows = 4, 3
    cw, ch = 340, 380
    sheet = Image.new("RGB", (cols * cw + 20, rows * ch + 60), (18, 20, 28))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 15)
    except Exception:
        font = ImageFont.load_default()
    draw.text((15, 15), "ORIGINAL MANHWA FRAMES — TYRANT OF THE TOWER DEFENSE GAME", fill=(240, 200, 110), font=font)
    for idx, (fn, label) in enumerate(grid_items):
        r_i, c_i = divmod(idx, cols)
        x0 = 10 + c_i * cw
        y0 = 50 + r_i * ch
        p = REF_DIR / fn
        if p.is_file():
            im = Image.open(p).convert("RGB")
            im.thumbnail((cw - 12, ch - 42), Image.Resampling.LANCZOS)
            ox = x0 + (cw - im.width) // 2
            oy = y0 + (ch - 40 - im.height) // 2
            sheet.paste(im, (ox, oy))
        draw.text((x0 + 8, y0 + ch - 30), label, fill=(235, 235, 245), font=font)
    sheet_path = REF_DIR / "manhwa_original_frames_grid.jpg"
    sheet.save(sheet_path, quality=92)
    (BRAIN_DIR / "manhwa_original_frames_grid.jpg").write_bytes(sheet_path.read_bytes())
    print("Saved manhwa_original_frames_grid.jpg", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
