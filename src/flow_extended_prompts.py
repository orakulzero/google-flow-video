"""Continuation prompts for Episode 1 Extended Director's Cut (26 clips, 104.0s).

Each continuation clip (01b..12b, 02c, 04c) starts from the exact final frame of the
preceding clip using generate_video_with_first_frame and explicitly enforces
'Continuous, unbroken single shot, no scene cuts' per Gemini Omni 1.1 Flash guidelines.
100% English-only source hygiene, <= 180 lines.
"""
from __future__ import annotations

PREFIX = (
    "Use generate_video_with_first_frame with model_display_name='Omni 1.1 Flash', "
    "aspect_ratio='16:9', duration='4s', and the attached image as start_image_media_id. "
    "Prompt: Continuous, unbroken single shot, no scene cuts. "
    "Hand-painted 2.5D dark fantasy animation style of Fortiche Arcane with visible impasto brushwork. "
)

# Maps clip_id -> (source_clip_for_last_frame, prompt)
EXTENDED_CLIP_SPECS: dict[str, tuple[str, str]] = {
    "01b": (
        "ttd_ep01_shot_01_clip_720p.mp4",
        PREFIX + (
            "Continuing the slow camera push-in past the exhausted dark-haired gamer's shoulder "
            "toward the glowing dual monitors in the dark night study. His fingers fly across the "
            "mechanical keyboard at extreme speed as tactical damage logs and siege alerts scroll "
            "across the cyan screen while rain streaks down the window blinds."
        ),
    ),
    "02b": (
        "ttd_ep01_shot_02_clip_720p.mp4",
        PREFIX + (
            "Continuing the crane camera glide across the rain-lashed stone flagstones of the "
            "shattered fortress ramparts during a lightning storm. Rain splashes over a cracked "
            "silver-gold paladin shield and a broken wooden crossbow lying in the shallow puddles "
            "while iron braziers smoke in the wind and dark mist churns beyond the battlements."
        ),
    ),
    "02c": (
        "ttd_ep01_shot_02b_clip_720p.mp4",
        PREFIX + (
            "Continuing the camera pan up toward the breached basalt parapet as a massive dark "
            "armored siege monstrosity crawls out of the swirling black fog over the ruined wall. "
            "Heavy rain and lightning illuminate its jagged obsidian plates while burning embers "
            "fly across the wet stone ramparts."
        ),
    ),
    "03b": (
        "ttd_ep01_shot_03_clip_720p.mp4",
        PREFIX + (
            "Continuing the low-angle 3/4 medium shot of the blond vanguard knight on the wet "
            "stone ramparts. He plants his heavy steel greave firmly into the flooded gravel, "
            "shifts his notched broadsword into a high two-handed guard, and turns his scarred "
            "face to rally the three spearmen behind him. Natural human eyes, zero glowing eyes, zero sparks."
        ),
    ),
    "04b": (
        "ttd_ep01_shot_04_clip_720p.mp4",
        PREFIX + (
            "Continuing directly from the blond knight's battle roar as he lunges forward in an "
            "explosive vanguard sprint through the pouring rain with the three spearmen charging "
            "behind him. He swings his heavy high-carbon broadsword in a powerful two-handed "
            "diagonal cleave through the rain. Natural steel, zero glowing eyes, zero sparks."
        ),
    ),
    "04c": (
        "ttd_ep01_shot_04b_clip_720p.mp4",
        PREFIX + (
            "Continuing as the camera settles behind the blond knight's broad armored shoulders "
            "in the pouring rain. The defeated dark monster dissolves into drifting black ash "
            "while the exhausted knight lowers his notched broadsword tip to the wet stone floor, "
            "standing completely alone in the dark mist with his head bowed in silent grief. Zero sparks."
        ),
    ),
    "05b": (
        "ttd_ep01_shot_05_clip_720p.mp4",
        PREFIX + (
            "Continuing the over-the-shoulder shot in the dimly lit room as the exhausted gamer "
            "slowly raises one trembling hand toward the glowing monitor displaying the solitary "
            "knight. The golden and cyan light of the computer screen intensifies and ripples "
            "outward like a luminous whirlpool, enveloping his silhouette."
        ),
    ),
    "06b": (
        "ttd_ep01_shot_06_clip_720p.mp4",
        PREFIX + (
            "Continuing from the hand clenching the crimson velvet sheets as the camera tilts up "
            " smoothly. The pale black-haired young nobleman bolts upright on the medieval four-poster "
            "bed in the cold stone chamber, gasping for air and pressing a trembling hand to his "
            "temple as warm fireplace embers flicker across the flagstones."
        ),
    ),
    "07b": (
        "ttd_ep01_shot_07_clip_720p.mp4",
        PREFIX + (
            "Continuing the slow push-in toward the cracked silvered wall mirror in the candlelit "
            "stone chamber. The pale black-haired commander in his dark officer greatcoat raises "
            "his hand with its black obsidian ring to touch his cheek, and his sharp amber-gold "
            "eyes narrow with cold tactical resolve in the fractured reflection."
        ),
    ),
    "08b": (
        "ttd_ep01_shot_08_clip_720p.mp4",
        PREFIX + (
            "Continuing the reverse over-the-shoulder shot in the torchlit stone corridor. The "
            "dark-haired commander steps closer and places a firm hand on the young blond knight's "
            "steel pauldron. The blond knight uncrosses his arms and stiffens in startled surprise "
            "at the commander's intense gaze. Natural human eyes, zero glowing eyes, zero sparks."
        ),
    ),
    "09b": (
        "ttd_ep01_shot_09_clip_720p.mp4",
        PREFIX + (
            "Continuing from the macro close-up of the commander's amber-gold eye as the camera "
            "smoothly pulls back slightly. The translucent cyan tactical status lines shimmer and "
            "fade in his corneal reflection as urgent orange torchlight flares across his pale "
            "face and a low vibration shakes the dust in the stone corridor."
        ),
    ),
    "10b": (
        "ttd_ep01_shot_10_clip_720p.mp4",
        PREFIX + (
            "Continuing the wide establishing sweep along the monumental dark basalt fortress "
            "walls at stormy twilight. Iron pitch cauldrons flare up with bright orange flames "
            "along the battlements while dark multi-limbed shadow creatures surge out of the "
            "churning black fog across the outer ditch toward the lower ramparts."
        ),
    ),
    "11b": (
        "ttd_ep01_shot_11_clip_720p.mp4",
        PREFIX + (
            "Continuing the 12-degree Dutch-tilt tracking shot on the rain-swept stone ramparts "
            "as the blond vanguard knight reaches the narrow stone gatehouse archway. While "
            "panicked soldiers retreat behind him, he plants his boots wide in the wet mud and "
            "raises his heavy broadsword to hold the choke point alone. Zero glowing eyes, zero sparks."
        ),
    ),
    "12b": (
        "ttd_ep01_shot_12_clip_720p.mp4",
        PREFIX + (
            "Continuing the low-angle heroic two-shot at the fortress gatehouse in the storm. "
            "As the black-haired commander slashes his arm forward in command from the parapet "
            "above, the blond knight braces his massive iron-rimmed oak tower shield against a "
            "violent impact of rainwater and dark claws in the archway, holding the line immovable. Zero sparks."
        ),
    ),
}

ORDERED_EPISODE_CLIPS: list[str] = [
    # Act I: The 1,000th Hell-Difficulty Run & The Last Survivor in the Throne Hall (104.0s)
    "ttd_ep01_shot_01_clip_720p.mp4",
    "ttd_ep01_shot_02_clip_720p.mp4",
    "ttd_ep01_shot_03_clip_720p.mp4",
    "ttd_ep01_shot_04_clip_720p.mp4",
    "ttd_ep01_shot_04b_clip_720p.mp4",
    "ttd_ep01_shot_03b_clip_720p.mp4",
    "ttd_ep01_shot_04c_clip_720p.mp4",
    "ttd_ep01_shot_04d_clip_720p.mp4",
    "ttd_ep01_shot_01b_clip_720p.mp4",
    "ttd_ep01_shot_01c_clip_720p.mp4",
    "ttd_ep01_shot_02b_clip_720p.mp4",
    "ttd_ep01_shot_02c_clip_720p.mp4",
    "ttd_ep01_shot_05_clip_720p.mp4",
    "ttd_ep01_shot_05b_clip_720p.mp4",
    # Act II: Transmigration into Prince Ash Everblack & Assembling the Guard Party (36.0s)
    "ttd_ep01_shot_06_clip_720p.mp4",
    "ttd_ep01_shot_07_clip_720p.mp4",
    "ttd_ep01_shot_08_clip_720p.mp4",
    "ttd_ep01_shot_09_clip_720p.mp4",
    "ttd_ep01_shot_07b_clip_720p.mp4",
    "ttd_ep01_shot_08b_clip_720p.mp4",
    # Act III: Stage 0 Tutorial Siege - Black Spider Legion & Ancient Mana Cannon (62.0s)
    "ttd_ep01_shot_10_clip_720p.mp4",
    "ttd_ep01_shot_09b_clip_720p.mp4",
    "ttd_ep01_shot_10b_clip_720p.mp4",
    "ttd_ep01_shot_11_clip_720p.mp4",
    "ttd_ep01_shot_12_clip_720p.mp4",
    "ttd_ep01_shot_11b_clip_720p.mp4",
    "ttd_ep01_shot_12b_clip_720p.mp4",
    "ttd_ep01_shot_12c_clip_720p.mp4",
]
