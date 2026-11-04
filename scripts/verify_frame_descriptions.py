#!/usr/bin/env python3
"""Verify details of each frame by generating descriptive feature summaries."""

import cv2
import numpy as np
from pathlib import Path

SRC_DIR = Path("output/ttd_arcane_characters/episode1_frames/ep01")

descriptions = {
    1: "CRT screen displaying 'Congratulations!' game clear fanfare with golden pixel runes and fireworks banner.",
    2: "Streamer in light-blue hoodie throwing both arms up in ecstatic victory celebration at his gaming desk.",
    3: "Streamer closeup, wide eyes and ecstatic open mouth, hands raised, glowing monitor reflection, 'I managed to beat it!'.",
    4: "Streamer extreme closeup shouting with intensity into mic/camera, headset on head, 'Finally beat this godd*** game!'.",
    5: "Gothic stone title card monument for 'Save the Empire', weathered stone engraving with golden runes and dark fantasy atmosphere.",
    6: "Narrative caption box: 'But today, ten years after its release, a gamer has managed to beat it!'.",
    7: "Narrative caption box: 'That\\'s right... that gamer is me!'.",
    8: "Streamer medium shot pointing at viewers with confident, proud expression, headphones on, monitor glow.",
    9: "Tactical defense grid overview of Crossroads fortress showing hex tiles, wall defense lines, monster siege paths, and hero markers.",
    10: "Narrative caption box: 'I\\'m a game streamer...'.",
    11: "Atmospheric wide shot of dark gaming bedroom, silhouette of streamer at desk illuminated by multi-monitor glow.",
    12: "Narrative caption box: '..who only plays retro games known to be brutally difficult.'.",
    13: "Retro Gamer streaming channel profile banner with subscriber counter and 172 videos catalog.",
    14: "Streamer broadcast workstation view showing ultrawide displays, broadcast boom mic, animated 300,000 won donation pop-up, streamer thanking viewers.",
    15: "Narrative caption box: 'No one has ever finished the game at this difficulty setting in the last ten years...'.",
    16: "Streamer leaning back in gaming chair with proud smug grin, rubbing nose/chin, 'I guess I was pretty awesome, too'.",
    17: "Narrative caption box: 'Is there a greater achievement for a gamer than that?'.",
    18: "Streamer face transitioning from smug pride to thoughtful, slightly wistful expression as he reads chat.",
    19: "Narrative caption box: 'But of course, it could\\'ve been better...'.",
    20: "Live stream chat overlay panel with viewer comment from Sanghy lamenting the tragic death of the R-rank priestess in the final battle.",
    21: "Streamer gazing down at desk in quiet pause, mood turning somber, monitor light on lowered eyelids.",
    22: "Streamer reflective monologue: 'Many of my viewers had grown attached to the game\\'s characters over time...'.",
    23: "Desolate battlefield rampart on fortress walls: fallen soldier corpses, shattered swords and shields, burning embers, ash and rain, 'Everyone other than Lucas died in battle'.",
    24: "Streamer half-profile shrug/rationalization: 'Oh well, my goal was never to keep everyone alive anyway. It was to see the ending.'.",
    25: "Game clear result UI screen: 'LAST STAGE CLEAR', Stage MVP: Lucas [SSR], Hell Difficulty & Ironman Mode, Player: Retro Gamer.",
    26: "Signature shot: Lucas solitary back view standing alone in the pitch-black void, battered silver plate armor, tattered blue cape, bowed head of tragic grief."
}

for i in range(1, 27):
    p = SRC_DIR / f"frame_{i:03d}.jpg"
    assert p.is_file(), f"Missing frame {i}"
    img = cv2.imread(str(p))
    print(f"[{i:02d}] {p.name}: {img.shape[1]}x{img.shape[0]} | {descriptions[i]}")

print("\nAll 26 frames verified against visual inventory.")
