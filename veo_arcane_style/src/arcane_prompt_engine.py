"""Arcane Prompt Engine with Fortiche 6-Stage Lexical Tuning.

Constructs reference conditioning and image-to-video / reference-to-video
prompts tailored for Google Veo 3.1 and Gemini Omni Flash.
"""

from __future__ import annotations

from typing import Dict, List, Optional


class ArcanePromptEngine:
    """Fortiche Production Arcane 2.5D lexical prompt synthesis engine."""

    # Stage 1: Aspect Ratio Prefix
    ASPECT_PREFIX = "Make me a video in a 16:9 aspect ratio: "

    # Stage 2: Core Style Anchor
    STYLE_ANCHOR = "Hand-painted Fortiche Production Arcane 2.5D animation style. "

    # Stage 3: Visual Texture & Brushwork
    TEXTURE_BRUSHWORK = (
        "Visible textured digital brushwork, tactile gouache and oil impasto strokes, "
        "matte painted concept art background, graphic novel depth with sharp illustrated line-art accents. "
    )

    # Stage 4: Chiaroscuro & Lighting Template
    LIGHTING_TEMPLATE = (
        "Extreme chiaroscuro contrast, dramatic dual-tone rim lighting ({palette}), "
        "volumetric atmospheric haze, and glowing particle embers. "
    )

    # Stage 5: Camera Direction
    CAMERA_DIRECTION = (
        "Cinematic sweeping camera tracking along the action vector, "
        "shallow depth of field with soft background bokeh. "
    )

    # Stage 6: Negative Constraint Block
    NEGATIVE_CONSTRAINTS = (
        "Strictly avoid photorealism, avoid live-action defects, avoid 3D plastic CG sheen, "
        "avoid uncanny valley wax skin, avoid flat cartoon shading, avoid speech bubbles, "
        "avoid text overlays, avoid watermarks, avoid frame judder, avoid distorted hands."
    )

    # Mood to Palette Canonical Mapping
    MOOD_PALETTE_MAP: Dict[str, str] = {
        "combat": "magenta_cyan_chiaroscuro",
        "action": "magenta_cyan_chiaroscuro",
        "duel": "magenta_cyan_chiaroscuro",
        "piltover": "gilded_hextech_amber",
        "golden_hour": "gilded_hextech_amber",
        "steampunk": "gilded_hextech_amber",
        "hextech": "gilded_hextech_amber",
        "zaun": "toxic_chemtech_green",
        "chemtech": "toxic_chemtech_green",
        "underworld": "desaturated_underworld_slate",
        "noir": "desaturated_underworld_slate",
        "somber": "desaturated_underworld_slate",
        "subdued": "desaturated_underworld_slate",
        "twilight": "cobalt_neon_twilight",
        "ambient": "cobalt_neon_twilight",
    }

    DEFAULT_PALETTE = "magenta_cyan_chiaroscuro"

    def __init__(self, default_palette: Optional[str] = None) -> None:
        if default_palette:
            self.default_palette = default_palette
        else:
            self.default_palette = self.DEFAULT_PALETTE

    def get_palette_for_mood(self, mood: str) -> str:
        """Map emotional or atmospheric mood to a Fortiche lighting palette."""
        clean_mood = (mood or "").strip().lower().replace("-", "_").replace(" ", "_")
        return self.MOOD_PALETTE_MAP.get(clean_mood, self.default_palette)

    def format_lighting(self, palette: Optional[str] = None) -> str:
        """Format Stage 4 lighting block with specified palette name."""
        clean_palette = palette.strip() if palette and palette.strip() else self.default_palette
        return self.LIGHTING_TEMPLATE.format(palette=clean_palette)

    def build_i2v_prompt(
        self,
        action_description: str = "",
        character: str = "",
        palette: str = "magenta_cyan_chiaroscuro",
        mood: str = "combat",
    ) -> str:
        """Build 6-stage Fortiche prompt for Image-to-Video (I2V) conditioning."""
        effective_palette = palette.strip() if palette and palette.strip() else self.get_palette_for_mood(mood)
        lighting_block = self.format_lighting(effective_palette)

        action_clean = (action_description or "").strip()
        if action_clean.endswith("."):
            action_clean = action_clean[:-1].strip()
        char_clean = (character or "").strip()

        if char_clean and action_clean:
            action_block = f"Featuring {char_clean}, {action_clean}. "
        elif char_clean:
            action_block = f"Featuring {char_clean}. "
        elif action_clean:
            action_block = f"{action_clean}. "
        else:
            action_block = ""

        parts = [
            self.ASPECT_PREFIX,
            self.STYLE_ANCHOR,
            action_block,
            self.TEXTURE_BRUSHWORK,
            lighting_block,
            self.CAMERA_DIRECTION,
            self.NEGATIVE_CONSTRAINTS,
        ]
        return "".join(parts)

    def build_r2v_prompt(
        self,
        scene_description: str = "",
        style_tags: Optional[List[str]] = None,
        palette: Optional[str] = None,
    ) -> str:
        """Build 6-stage Fortiche prompt for Reference-to-Video (R2V) style conditioning."""
        effective_palette = palette.strip() if palette and palette.strip() else self.default_palette
        lighting_block = self.format_lighting(effective_palette)

        desc_clean = (scene_description or "").strip()
        if desc_clean and not desc_clean.endswith("."):
            desc_clean += "."

        tags_block = ""
        if style_tags:
            valid_tags = [t.strip() for t in style_tags if t and t.strip()]
            if valid_tags:
                tags_block = f"Visual elements: {', '.join(valid_tags)}. "

        parts = [
            self.ASPECT_PREFIX,
            self.STYLE_ANCHOR,
            f"{desc_clean} " if desc_clean else "",
            tags_block,
            self.TEXTURE_BRUSHWORK,
            lighting_block,
            self.CAMERA_DIRECTION,
            self.NEGATIVE_CONSTRAINTS,
        ]
        return "".join(parts)
