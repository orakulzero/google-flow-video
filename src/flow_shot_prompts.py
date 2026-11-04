"""Prompt dictionary for Google Flow Omni 1.1 Flash 12-shot Episode 1 video generation.

Enforces 100% English-only source hygiene and <= 180 lines chunking.
"""
from __future__ import annotations

PREFIX = (
    "Use generate_video_with_first_frame with model_display_name='Omni 1.1 Flash', "
    "aspect_ratio='16:9', duration='4s', and the attached image as start_image_media_id. Prompt: "
)

SHOT_PROMPTS: dict[int, str] = {
    1: PREFIX + (
        "Hand-painted 2.5D animation style of Fortiche Arcane with visible impasto brushwork and "
        "dual-tone cyan-amber chiaroscuro lighting. Slow 5% camera push-in inside the dimly lit night "
        "study as the focused dark-haired gamer types rapidly on his mechanical keyboard in front of "
        "dual glowing monitors while rain streaks roll down the window glass behind the blinds. "
        "The room walls and desk background remain locked and stable."
    ),
    2: PREFIX + (
        "Hand-painted 2.5D dark fantasy animation style with visible impasto brushwork and physical "
        "storm lighting. Slow crane camera descent over the rain-swept stone battlements of the "
        "ancient dark basalt fortress during a nocturnal thunderstorm. Heavy rain splashes across "
        "wet flagstones and weathered shields while iron braziers flicker in the wind and distant "
        "lightning illuminates the dark mist on the horizon. Fortress architecture remains stable."
    ),
    3: PREFIX + (
        "Hand-painted 2.5D dark fantasy animation style with visible impasto brushwork and warm "
        "torchlight against cool slate rain. Low-angle 3/4 medium close-up of the blond vanguard "
        "knight standing firm on the wet stone ramparts in weathered dark steel plate armor, gripping "
        "his notched broadsword at guard. Rain and wind whip through his dirty-blonde hair and navy "
        "tabard as he breathes heavily. Natural human eyes, zero glowing eyes, zero sparks."
    ),
    5: PREFIX + (
        "Hand-painted 2.5D animation style of Fortiche Arcane with high-contrast cyan monitor glow "
        "and deep shadows. Over-the-shoulder medium shot of the exhausted gamer at his computer desk "
        "as the dual monitors display the glowing golden STAGE 50 CLEAR victory screen. His shoulders "
        "sink in quiet exhaustion and he lowers his head toward the mechanical keyboard as the monitor "
        "light pulses softly across the dim room."
    ),
    6: PREFIX + (
        "Hand-painted 2.5D dark fantasy animation style with tactile gouache brushwork and warm "
        "fireplace ember lighting. Low-angle close-up of a pale aristocratic hand clenching coarse "
        "crimson velvet bedsheets above cold stone flagstones in a medieval keep bedchamber. Warm "
        "amber light from fireplace embers flickers across the stone floor and drifting dust motes "
        "as the fingers tighten and rise slightly upon awakening."
    ),
    7: PREFIX + (
        "Hand-painted 2.5D dark fantasy animation style of Fortiche Arcane with sculpted facial "
        "planes and warm candlelight. Eye-level medium shot with a slow 8% push-in as the young "
        "black-haired commander in a high-collared charcoal-black officer greatcoat with gold "
        "embroidery stares into a cracked silvered wall mirror. His sharp amber-gold eyes narrow "
        "in realization as his reflection shifts subtly across the fractured mirror glass."
    ),
    8: PREFIX + (
        "Hand-painted 2.5D dark fantasy animation style with flickering orange wall-torch lighting "
        "against stone masonry. Reverse over-the-shoulder dialogue framing looking past the "
        "dark-haired commander's greatcoat collar at the young blond knight standing guard in the "
        "stone corridor with arms crossed and broadsword at his hip. The blond knight shifts his "
        "weight slightly with a guarded stoic expression. Zero glowing eyes, zero sparks."
    ),
    9: PREFIX + (
        "Hand-painted 2.5D animation style in macro extreme close-up on the commander's amber-gold "
        "eye. Subtle pupil constriction and a gentle blink as translucent cyan tactical status "
        "brackets shimmer softly in the corneal reflection. High chiaroscuro detail on dark "
        "eyelashes and pale temple in warm torchlight."
    ),
    10: PREFIX + (
        "Hand-painted 2.5D dark fantasy establishing panorama with Ufotable atmospheric lighting. "
        "Extreme wide 18mm shot of the monumental dark basalt fortress walls at stormy twilight. "
        "Iron braziers roar with billowing smoke along the battlements while the churning wall of "
        "dark mist rolls forward across the outer plain and dark chitinous shadow-creatures surge "
        "toward the lower ramparts. The stone fortress architecture remains locked and stable."
    ),
    11: PREFIX + (
        "Hand-painted 2.5D dark fantasy kinetic tracking shot with a 12-degree Dutch tilt on the "
        "rain-swept stone ramparts. The blond vanguard knight in weathered dark steel plate armor "
        "strides forward with resolute determination, gripping his heavy broadsword in his gauntlets "
        "while garrison soldiers hurry past in the background and torch flames whip in the storm "
        "wind. Natural human eyes, zero glowing eyes, zero sparks on armor or blade."
    ),
    12: PREFIX + (
        "Hand-painted 2.5D dark fantasy heroic low-angle two-shot at the fortress gatehouse in a "
        "night storm. On the stone parapet above, the black-haired commander in his dark officer "
        "greatcoat points forward in an authoritative battle command against the storm sky. Below "
        "him in the archway, the blond vanguard knight braces his massive iron-rimmed oak tower "
        "shield into the wet flagstones and holds his broadsword ready. Zero glowing eyes, zero sparks."
    ),
}
