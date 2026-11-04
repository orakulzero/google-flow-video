"""
src/ttd_storyboard.py
Tyrant of the Tower Defense Game - Flow Storyboard Templates & Prompt Generator Pipeline.

Provides reusable storyboard templates, multimodal prompt compilers, and FlowStoryboard
serialization/validation for Google Flow and Veo 3.1.

Zero literal Cyrillic rule: all localized Russian strings use unicode escapes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type, Union

from src.flow_bridge import (
    FlowEducationalProject,
    FlowScene,
    FlowStoryboard,
    sanitize_cloud_veo_narration,
)
from src.ttd_lore_bible import (
    COLOR_PALETTE,
    CROSSROADS_FORTRESS,
    TTD_MASTER_NEGATIVE_PROMPT,
    get_character_anchor,
    get_color_token,
    get_environment,
    get_environment_anchor,
    get_master_negative_prompt,
    get_monster_anchor,
)

# ==============================================================================
# Presets: Layer 1 Cinematography & Camera Movement
# ==============================================================================
CAMERA_SLOW_PUSH_IN: str = "slow push-in, steady locked camera, zero camera shake"
CAMERA_ORBITAL_PAN: str = "orbital 180-degree tracking pan, smooth gimbal rotation"
CAMERA_MACRO_TRACKING: str = "macro tracking shot with shallow depth of field, optical rack focus"
CAMERA_CRANE_TOP_DOWN: str = "crane top-down reveal from fortress battlements descending to kill-zone moat"
CAMERA_DOLLY_LATERAL: str = "dolly lateral slide tracking the defensive rampart line at chest height"
CAMERA_LOW_ANGLE_HEROIC: str = "low-angle heroic upward tilt emphasizing fortress masonry and defender mass"
CAMERA_EXTREME_MACRO_ARROW: str = (
    "extreme macro tracking shot locked onto bodkin arrow shaft cutting through raindrops"
)

# ==============================================================================
# Presets: Layer 2 Volumetric Lighting & Chromatics
# ==============================================================================
LIGHTING_ROARING_TORCHLIGHT: str = (
    "volumetric lighting, roaring iron pitch braziers casting flickering warm amber torchlight "
    "and drifting embers across rain-slick stone"
)
LIGHTING_BLOOD_MOON_VOLUMETRIC: str = (
    "high-contrast chiaroscuro, eerie blood-red moon volumetric rim illumination slicing through dark storm clouds"
)
LIGHTING_ARCANE_CYAN_DISPATCH: str = (
    "high-intensity arcane cyan dispatch glow radiating from mana signaling crystals casting sharp specular highlights"
)
LIGHTING_WITCH_FIRE_CHIAROSCURO: str = (
    "dramatic chiaroscuro contrast with corrupted violet witch-fire and necrotic purple shadows radiating from abyssal cores"
)
LIGHTING_STORMY_TEMPEST: str = (
    "strobe-like distant lightning flashes illuminating torrential driving rain against cyclopean dark basalt walls"
)

# ==============================================================================
# Presets: Layer 5 Motion Dynamics
# ==============================================================================
MOTION_TORRENTIAL_RAIN: str = (
    "driving torrential rain streaks slashing across the lens, rain droplets splashing violently off polished steel and basalt stone"
)
MOTION_SHIELD_COLLISION: str = (
    "massive iron tower shield slamming into wet stone, absorbing violent diving monster impact in explosive showers of orange sparks"
)
MOTION_SLOW_MOTION_ARROW: str = (
    "extreme slow-motion bodkin arrow flight, aerodynamic vapor spiral, razor point cutting cleanly through suspended raindrops"
)
MOTION_GARGOYLE_DIVE: str = (
    "black-scaled gargoyles dive-bombing at terminal velocity from storm clouds, razor talons scraping stone crenellations"
)
MOTION_SOUL_FIRE_CLEAVE: str = (
    "jagged two-handed executioner greatsword cleaving stone rampart in a shower of pulverized granite and dark crimson flames"
)

# ==============================================================================
# Presets: Layer 6 Audio Pacing, SFX & Ambience
# ==============================================================================
SFX_BATTLE_STORM: str = (
    "Deafening thunderclaps, clashing iron tower shields, roaring pitch brazier crackle, "
    "howling wind through crenellations, shrieking gargoyles"
)
SFX_COMMAND_DISPATCH: str = (
    "Resonant mana crystal chime, low-frequency arcane hum, rain drumming steadily on iron plate armor, "
    "firm boot steps on wet stone"
)
SFX_SNIPER_RELEASE: str = (
    "Tense bowstring draw creak, sudden concussive arrow release whoosh, whistling bodkin flight cutting through wind"
)
SFX_BOSS_COLLISION: str = (
    "Crushing armored footsteps shaking masonry, dragging two-handed greatsword sparking violently on stone, "
    "demonic furnace roar"
)
AMBIENT_CROSSROADS_STORM: str = (
    "Nocturnal tempest howling over volcanic bluffs, driving torrential rain on granite, "
    "distant demonic war horns reverberating from the Black Fog"
)

# ==============================================================================
# 6-Layer Configuration Dataclass
# ==============================================================================
@dataclass
class Prompt6LayerConfig:
    """Configuration container for the 6-layer TTD multimodal prompt generator."""
    # Layer 1: Cinematography & Camera Direction
    camera_motion: str = CAMERA_SLOW_PUSH_IN
    camera_framing: str = "steady locked camera, zero camera shake"
    focal_depth: str = "shallow cinematic depth of field, sharp edge focus"

    # Layer 2: Volumetric Lighting & Chromatics
    lighting_model: str = LIGHTING_ROARING_TORCHLIGHT
    color_tokens: List[str] = field(default_factory=list)

    # Layer 3: Environmental Context & Weather
    environment_id: str = "crossroads_fortress"
    environment_zone: Optional[str] = None
    weather_override: Optional[str] = None

    # Layer 4: Character & Monster Anchors
    characters: List[str] = field(default_factory=list)
    character_phases: Dict[str, str] = field(default_factory=dict)
    monsters: List[str] = field(default_factory=list)

    # Layer 5: Motion Dynamics & Action Directives
    action: str = ""
    motion_dynamics: str = MOTION_TORRENTIAL_RAIN
    timecoded_actions: List[Dict[str, str]] = field(default_factory=list)
    composition_and_style: str = (
        "cinematic dark fantasy anime aesthetic, 8k resolution, photoreal anime detail, dynamic chiaroscuro"
    )

    # Layer 6: Audio Pacing & Native Veo 3.1 Narration
    narration_text: str = ""
    voice_persona: str = "voice_y0joebp3bwta"
    voice_style: str = "grim authoritative Russian commander"
    sound_effects: str = SFX_BATTLE_STORM
    ambient_audio: str = AMBIENT_CROSSROADS_STORM

    # Calibrated Negative Prompt
    negative_prompt: str = ""

    def __post_init__(self) -> None:
        if not self.negative_prompt:
            self.negative_prompt = get_master_negative_prompt()


# ==============================================================================
# Prompt Generator Functions (6-Layer Architecture)
# ==============================================================================

def build_6layer_visual_prompt(config: Prompt6LayerConfig) -> str:
    """
    Construct a 100% Google Flow & Veo 3.1 compliant visual prompt by synthesizing
    all 5 visual layers into a continuous unbroken cinematic shot.
    """
    parts: List[str] = []

    # Layer 1: Camera Direction & Framing
    cam_motion = (config.camera_motion or "slow push-in").strip().rstrip(".")
    cam_framing = (config.camera_framing or "steady locked camera").strip().rstrip(".")
    parts.append(f"In a single continuous unbroken cinematic shot, {cam_motion}, {cam_framing}.")

    # Layer 2: Environmental Setting & Atmosphere
    env_anchor = get_environment_anchor(config.environment_id or "crossroads_fortress")
    parts.append(env_anchor)

    if config.environment_zone:
        env_spec = get_environment(config.environment_id or "crossroads_fortress")
        if hasattr(env_spec, "strategic_zones") and config.environment_zone in env_spec.strategic_zones:
            zone_desc = env_spec.strategic_zones[config.environment_zone]
            parts.append(f"Location Zone: {zone_desc}.")

    # Layer 3: Character & Monster Visual Anchors
    if config.characters:
        for char_id in config.characters:
            phase = config.character_phases.get(char_id)
            parts.append(get_character_anchor(char_id, phase))

    if config.monsters:
        for monster_id in config.monsters:
            parts.append(get_monster_anchor(monster_id))

    # Layer 4: Action & Motion Dynamics
    action_clean = (config.action or "").strip().rstrip(".")
    motion_clean = (config.motion_dynamics or "").strip().rstrip(".")
    action_parts: List[str] = []
    if action_clean:
        action_parts.append(action_clean)
    if motion_clean:
        action_parts.append(motion_clean)

    if config.timecoded_actions:
        tc_parts = [
            f"[{d.get('window', '0-2s')}] {d.get('action', '')}"
            for d in config.timecoded_actions
            if isinstance(d, dict) and d.get("action")
        ]
        if tc_parts:
            action_parts.append("Timeline: " + " ".join(tc_parts))

    if action_parts:
        parts.append(". ".join(action_parts) + ".")

    # Layer 5: Volumetric Lighting & Chromatics
    light_clean = (config.lighting_model or "").strip().rstrip(".")
    if config.color_tokens:
        palette_details: List[str] = []
        for ctok in config.color_tokens:
            try:
                ct = get_color_token(ctok)
                palette_details.append(f"{ct.name} ({ct.description})")
            except KeyError:
                pass
        if palette_details:
            light_clean += f", color highlights: {'; '.join(palette_details)}"

    if light_clean:
        parts.append(light_clean + ".")

    # Final Style Directive
    style_clean = (config.composition_and_style or "").strip().rstrip(".")
    if style_clean:
        parts.append(style_clean + ".")

    return " ".join(p for p in parts if p)


def build_veo31_native_audio_prompt(
    config: Prompt6LayerConfig,
    visual_prompt: Optional[str] = None,
) -> str:
    """
    Construct a Veo 3.1 native audio prompt combining visual cues, quoted spoken
    dialogue with persona delivery style, sound effects, and ambient noise.
    """
    vis = (visual_prompt or build_6layer_visual_prompt(config)).strip().rstrip(".")
    clean_speech = sanitize_cloud_veo_narration(config.narration_text)
    persona = (config.voice_persona or "voice_y0joebp3bwta").strip()
    style = (config.voice_style or "grim authoritative Russian commander").strip()
    sfx = (config.sound_effects or "").strip().rstrip(".")
    ambient = (config.ambient_audio or "").strip().rstrip(".")

    audio_parts = [f"{vis}."]
    if clean_speech:
        audio_parts.append(f'Narrator ({persona}, {style}): "{clean_speech}"')
    if sfx:
        audio_parts.append(f"SFX: {sfx}.")
    if ambient:
        audio_parts.append(f"Ambient noise: {ambient}.")

    return " ".join(audio_parts)


def build_ttd_flow_prompt(
    config: Prompt6LayerConfig,
) -> Tuple[str, str, str]:
    """
    Synthesize complete Google Flow & Veo 3.1 prompt triplet:
    Returns (visual_prompt, native_audio_prompt, master_negative_prompt).
    """
    visual_p = build_6layer_visual_prompt(config)
    audio_p = build_veo31_native_audio_prompt(config, visual_prompt=visual_p)
    neg_p = config.negative_prompt or get_master_negative_prompt()
    return visual_p, audio_p, neg_p


def create_ttd_flow_scene(
    config: Prompt6LayerConfig,
    scene_id: str,
    scene_number: int,
    title: str,
    duration_sec: float = 5.0,
    on_screen_bullets: Optional[List[str]] = None,
    learning_objective: Optional[str] = None,
    formula_expression: Optional[str] = None,
) -> FlowScene:
    """
    Create a fully validated and schema-compliant FlowScene object using the 6-layer prompt generator.
    """
    visual_p, audio_p, _ = build_ttd_flow_prompt(config)
    return FlowScene(
        scene_id=scene_id,
        scene_number=scene_number,
        title=title,
        narration_text=config.narration_text,
        visual_prompt=visual_p,
        duration_sec=duration_sec,
        camera_motion=config.camera_motion,
        on_screen_bullets=on_screen_bullets or [],
        status="pending",
        voice_persona=config.voice_persona,
        voice_style=config.voice_style,
        native_veo_audio=True,
        veo_audio_prompt=audio_p,
        tts_narration_text=config.narration_text,
        timecoded_directives=config.timecoded_actions,
        learning_objective=learning_objective,
        formula_expression=formula_expression,
    )


# ==============================================================================
# Base Storyboard Template
# ==============================================================================

@dataclass
class TTDStoryboardTemplate:
    """Base class for all Tyrant of the Tower Defense storyboard templates."""
    template_id: str = "base_template"
    template_name: str = "Base Template"
    description: str = "Base storyboard template"
    scene_archetype: str = "base"
    default_duration_sec: float = 5.0
    default_camera_motion: str = CAMERA_SLOW_PUSH_IN
    default_voice_persona: str = "voice_y0joebp3bwta"
    default_voice_style: str = "grim authoritative Russian commander"
    default_pedagogical_phase: str = "Hook & Core Phenomenon"

    def build_scene(
        self,
        scene_id: str,
        scene_number: int,
        language: str = "ru",
        duration_sec: Optional[float] = None,
        camera_motion: Optional[str] = None,
        voice_persona: Optional[str] = None,
        voice_style: Optional[str] = None,
        custom_action: Optional[str] = None,
        custom_narration: Optional[str] = None,
        custom_tts_narration: Optional[str] = None,
        **kwargs: Any,
    ) -> FlowScene:
        """Construct a fully populated, valid FlowScene instance."""
        raise NotImplementedError


# ==============================================================================
# Template 1: Fortress Atmosphere & Black Fog
# ==============================================================================

class FortressAtmosphereTemplate(TTDStoryboardTemplate):
    """Panoramic atmospheric reveal of Crossroads Citadel under storm and Black Fog."""

    def __init__(
        self,
        template_id: str = "fortress_atmosphere",
        template_name: str = "Crossroads Fortress Atmosphere & Black Fog",
        description: str = "Panoramic establishing view of Crossroads Fortress ramparts facing the Black Fog",
        scene_archetype: str = "panoramic_establishing",
        default_duration_sec: float = 7.5,
        default_camera_motion: str = "wide panoramic crane reveal from parapets down to the killing fields",
        default_voice_persona: str = "voice_y0joebp3bwta",
        default_voice_style: str = "grim atmospheric narrator with heavy ominous undertones",
        default_pedagogical_phase: str = "Hook & Core Phenomenon",
    ) -> None:
        super().__init__(
            template_id=template_id,
            template_name=template_name,
            description=description,
            scene_archetype=scene_archetype,
            default_duration_sec=default_duration_sec,
            default_camera_motion=default_camera_motion,
            default_voice_persona=default_voice_persona,
            default_voice_style=default_voice_style,
            default_pedagogical_phase=default_pedagogical_phase,
        )

    def build_scene(
        self,
        scene_id: str,
        scene_number: int,
        language: str = "ru",
        duration_sec: Optional[float] = None,
        camera_motion: Optional[str] = None,
        voice_persona: Optional[str] = None,
        voice_style: Optional[str] = None,
        custom_action: Optional[str] = None,
        custom_narration: Optional[str] = None,
        custom_tts_narration: Optional[str] = None,
        **kwargs: Any,
    ) -> FlowScene:
        cam_motion = camera_motion or self.default_camera_motion
        dur = duration_sec if duration_sec is not None else self.default_duration_sec
        persona = voice_persona or self.default_voice_persona
        v_style = voice_style or self.default_voice_style

        # Russian titles and text encoded via unicode escapes (0 literal Cyrillic)
        title = "\u041a\u0440\u0435\u043f\u043e\u0441\u0442\u044c \u041f\u0435\u0440\u0435\u043a\u0440\u0451\u0441\u0442\u043e\u043a: \u041f\u0440\u043e\u0431\u0443\u0436\u0434\u0435\u043d\u0438\u0435 \u0427\u0451\u0440\u043d\u043e\u0433\u043e \u0422\u0443\u043c\u0430\u043d\u0430"
        narration = custom_narration or (
            "\u042e\u0436\u043d\u044b\u0439 \u0440\u0443\u0431\u0435\u0436 \u0418\u043c\u043f\u0435\u0440\u0438\u0438. "
            "\u041a\u0440\u0435\u043f\u043e\u0441\u0442\u044c \u041f\u0435\u0440\u0435\u043a\u0440\u0451\u0441\u0442\u043e\u043a \u0432\u0441\u0442\u0440\u0435\u0447\u0430\u0435\u0442 \u043f\u0435\u0440\u0432\u0443\u044e \u0432\u043e\u043b\u043d\u0443 "
            "\u0438\u0437 \u0427\u0451\u0440\u043d\u043e\u0433\u043e \u0422\u0443\u043c\u0430\u043d\u0430. "
            "\u0417\u0434\u0435\u0441\u044c \u043d\u0435\u0442 \u043f\u043e\u0434\u043a\u0440\u0435\u043f\u043b\u0435\u043d\u0438\u0439 \u0438 \u043f\u0440\u0430\u0432\u0430 \u043d\u0430 \u043e\u0448\u0438\u0431\u043a\u0443."
        )
        tts_narration = custom_tts_narration or (
            "\u042e+\u0436\u043d\u044b\u0439 \u0440\u0443\u0431+\u0435\u0436 \u0418\u043c\u043f+\u0435\u0440\u0438\u0438. <short pause> "
            "\u041a\u0440+\u0435\u043f\u043e\u0441\u0442\u044c \u041f\u0435\u0440\u0435\u043a\u0440+\u0451\u0441\u0442\u043e\u043a \u0432\u0441\u0442\u0440\u0435\u0447+\u0430\u0435\u0442 \u043f+\u0435\u0440\u0432\u0443\u044e \u0432\u043e\u043b\u043d+\u0443 "
            "\u0438\u0437 \u0427+\u0451\u0440\u043d\u043e\u0433\u043e \u0422\u0443\u043c+\u0430\u043d\u0430. <short pause> "
            "*\u0417\u0434\u0435\u0441\u044c \u043d\u0435\u0442 \u043f\u043e\u0434\u043a\u0440\u0435\u043f\u043b+\u0435\u043d\u0438\u0439 \u0438 \u043f\u0440+\u0430\u0432\u0430 \u043d\u0430 \u043e\u0448+\u0438\u0431\u043a\u0443.*"
        )

        timecoded = [
            {"window": "0-2s", "action": "Crane camera descends through dark storm clouds revealing 30-meter wet granite walls and roaring braziers."},
            {"window": "2-5s", "action": "Camera tilts downward over the notched parapets to reveal the scorched moat and caltrop ditches."},
            {"window": "5-8s", "action": "Sudden lightning flash exposes the supernatural wall of Black Fog 300 meters out, establishing extreme peril."},
        ]

        bullets = [
            "\u042e\u0436\u043d\u044b\u0439 \u0440\u0443\u0431\u0435\u0436: \u041a\u0440\u0435\u043f\u043e\u0441\u0442\u044c \u041f\u0435\u0440\u0435\u043a\u0440\u0451\u0441\u0442\u043e\u043a",
            "\u0417\u0430\u043a\u043e\u043d \u043f\u0435\u0440\u043c\u0430\u0434\u0435\u0437\u0430: \u043d\u043e\u043b\u044c \u043f\u043e\u0434\u043a\u0440\u0435\u043f\u043b\u0435\u043d\u0438\u0439",
            "\u041f\u0435\u0440\u0432\u0430\u044f \u0432\u043e\u043b\u043d\u0430: \u043f\u0440\u043e\u0440\u044b\u0432 \u0427\u0451\u0440\u043d\u043e\u0433\u043e \u0422\u0443\u043c\u0430\u043d\u0430",
        ]

        cfg = Prompt6LayerConfig(
            camera_motion=cam_motion,
            camera_framing="steady locked camera, zero camera shake",
            lighting_model=LIGHTING_BLOOD_MOON_VOLUMETRIC,
            color_tokens=["pitch_amber", "arterial_crimson", "midnight_storm"],
            environment_id="crossroads_fortress",
            environment_zone="battlements",
            action=custom_action or "Driving storm rain sweeps across the granite battlements of Crossroads Fortress as distant lightning illuminates the bottomless moat facing the creeping Black Fog.",
            motion_dynamics=MOTION_TORRENTIAL_RAIN,
            timecoded_actions=timecoded,
            composition_and_style="cinematic dark fantasy anime aesthetic, 8k resolution, photoreal anime detail, dynamic chiaroscuro",
            narration_text=narration,
            voice_persona=persona,
            voice_style=v_style,
            sound_effects="Distant rolling thunder, freezing wind whistling through iron crenellations, torrential rain splashing on wet basalt stone, crackling iron braziers",
            ambient_audio="Low-frequency ominous hum of the supernatural Black Fog miasma over volcanic bluffs",
        )

        visual_p, audio_p, _ = build_ttd_flow_prompt(cfg)

        return FlowScene(
            scene_id=scene_id,
            scene_number=scene_number,
            title=title,
            narration_text=narration,
            visual_prompt=visual_p,
            duration_sec=dur,
            camera_motion=cam_motion,
            on_screen_bullets=bullets,
            status="pending",
            voice_persona=persona,
            voice_style=v_style,
            native_veo_audio=True,
            veo_audio_prompt=audio_p,
            tts_narration_text=tts_narration,
            pedagogical_phase=self.default_pedagogical_phase,
            timecoded_directives=timecoded,
            learning_objective="Establish the dark fantasy permadeath setting of Crossroads Fortress under assault from the Black Fog",
        )


# ==============================================================================
# Template 2: Tactical Command & Attrition Grid
# ==============================================================================

class TacticalCommandTemplate(TTDStoryboardTemplate):
    """Prince Ash Bornhater calculating defense vectors and commanding the garrison."""

    def __init__(
        self,
        template_id: str = "tactical_command",
        template_name: str = "Prince Ash Tactical Command & Defense Grid",
        description: str = "Prince Ash calculating attrition vectors and commanding the garrison with baton and crystal",
        scene_archetype: str = "tactical_command_calculation",
        default_duration_sec: float = 7.0,
        default_camera_motion: str = CAMERA_SLOW_PUSH_IN,
        default_voice_persona: str = "voice_y0joebp3bwta",
        default_voice_style: str = "grim authoritative Russian commander",
        default_pedagogical_phase: str = "Concept Core & Mechanism",
    ) -> None:
        super().__init__(
            template_id=template_id,
            template_name=template_name,
            description=description,
            scene_archetype=scene_archetype,
            default_duration_sec=default_duration_sec,
            default_camera_motion=default_camera_motion,
            default_voice_persona=default_voice_persona,
            default_voice_style=default_voice_style,
            default_pedagogical_phase=default_pedagogical_phase,
        )

    def build_scene(
        self,
        scene_id: str,
        scene_number: int,
        language: str = "ru",
        duration_sec: Optional[float] = None,
        camera_motion: Optional[str] = None,
        voice_persona: Optional[str] = None,
        voice_style: Optional[str] = None,
        custom_action: Optional[str] = None,
        custom_narration: Optional[str] = None,
        custom_tts_narration: Optional[str] = None,
        **kwargs: Any,
    ) -> FlowScene:
        cam_motion = camera_motion or self.default_camera_motion
        dur = duration_sec if duration_sec is not None else self.default_duration_sec
        persona = voice_persona or self.default_voice_persona
        v_style = voice_style or self.default_voice_style

        title = "\u041f\u0440\u0438\u043d\u0446 \u042d\u0448: \u0420\u0430\u0441\u0447\u0451\u0442 \u0441\u0435\u0442\u043a\u0438 \u043e\u0431\u043e\u0440\u043e\u043d\u044b"
        narration = custom_narration or (
            "\u041f\u0440\u0438\u043d\u0446 \u042d\u0448 \u043e\u0446\u0435\u043d\u0438\u0432\u0430\u0435\u0442 \u0432\u0435\u043a\u0442\u043e\u0440\u044b \u0430\u0442\u0430\u043a\u0438. "
            "\u0412 \u0440\u0435\u0436\u0438\u043c\u0435 \u0410\u0434\u0430 \u043f\u0430\u043d\u0438\u043a\u0430 \u0440\u0430\u0432\u043d\u0430 \u0441\u043c\u0435\u0440\u0442\u0438. "
            "\u041a\u0430\u0436\u0434\u0430\u044f \u0441\u0442\u0440\u0435\u043b\u0430 \u0438 \u043a\u0430\u0436\u0434\u044b\u0439 \u0449\u0438\u0442 \u0432\u043f\u0438\u0441\u0430\u043d\u044b \u0432 \u0443\u0440\u0430\u0432\u043d\u0435\u043d\u0438\u0435 \u0432\u044b\u0436\u0438\u0432\u0430\u043d\u0438\u044f."
        )
        tts_narration = custom_tts_narration or (
            "\u041f\u0440\u0438\u043d\u0446 \u042d\u0448 \u043e\u0446\u0435\u043d+\u0438\u0432\u0430\u0435\u0442 \u0432+\u0435\u043a\u0442\u043e\u0440\u044b \u0430\u0442+\u0430\u043a\u0438. <short pause> "
            "\u0412 \u0440\u0435\u0436+\u0438\u043c\u0435 \u0410\u0434\u0430 \u043f+\u0430\u043d\u0438\u043a\u0430 \u0440\u0430\u0432\u043d+\u0430 \u0441\u043c+\u0435\u0440\u0442\u0438. <short pause> "
            "*\u041a\u0430\u0436\u0434\u0430\u044f \u0441\u0442\u0440\u0435\u043b+\u0430, \u043a\u0430\u0436\u0434\u044b\u0439 \u0449\u0438\u0442 \u0438 \u043a\u0430\u0436\u0434\u0430\u044f \u0436\u0438\u0437\u043d\u044c \u0432\u043f+\u0438\u0441\u0430\u043d\u044b \u0432 \u0443\u0440\u0430\u0432\u043d+\u0435\u043d\u0438\u0435 \u0432\u044b\u0436\u0438\u0432+\u0430\u043d\u0438\u044f.*"
        )

        timecoded = [
            {"window": "0-2s", "action": "Tight push-in frames Ash's unyielding profile, rain dripping from his black hair across sharp cheekbones."},
            {"window": "2-5s", "action": "Ash lifts the commander baton toward the outer killing fields; cyan telemetry lines faintly illuminate the parapet."},
            {"window": "5-7s", "action": "Amber eye glint flares under torchlight as he speaks decisive orders with calm authority."},
        ]

        bullets = [
            "\u0422\u0430\u043a\u0442\u0438\u043a\u0430 \u0440\u0435\u0436\u0438\u043c\u0430 \u0410\u0434\u0430: \u0445\u043e\u043b\u043e\u0434\u043d\u044b\u0439 \u0440\u0430\u0441\u0447\u0451\u0442",
            "\u0416\u0435\u0441\u0442\u043a\u0430\u044f \u0434\u0438\u0441\u0446\u0438\u043f\u043b\u0438\u043d\u0430: \u043f\u0440\u0435\u0434\u043e\u0442\u0432\u0440\u0430\u0449\u0435\u043d\u0438\u0435 \u043f\u0430\u043d\u0438\u043a\u0438",
            "\u042d\u043a\u043e\u043d\u043e\u043c\u0438\u043a\u0430 \u0431\u043e\u0435\u043f\u0440\u0438\u043f\u0430\u0441\u043e\u0432 \u0438 \u0436\u0438\u0437\u043d\u0435\u0439",
        ]

        cfg = Prompt6LayerConfig(
            camera_motion=cam_motion,
            camera_framing="steady locked camera, zero camera shake",
            lighting_model=LIGHTING_ARCANE_CYAN_DISPATCH,
            color_tokens=["arcane_cyan", "pitch_amber", "obsidian_black"],
            environment_id="crossroads_fortress",
            environment_zone="commanders_spire",
            characters=["ash_bornhater"],
            action=custom_action or "Prince Ash Bornhater raises his polished steel tactical commander baton pointing across the killing fields as the azure dispatch crystal on his chest pulses with arcane light.",
            motion_dynamics=MOTION_TORRENTIAL_RAIN,
            timecoded_actions=timecoded,
            composition_and_style="cinematic dark fantasy anime aesthetic, 8k resolution, photoreal anime detail, dynamic chiaroscuro",
            narration_text=narration,
            voice_persona=persona,
            voice_style=v_style,
            sound_effects="Crisp metallic click of commander baton against iron parapet stone, subtle high-pitch hum of the mana crystal, distant garrison war horn echoing through rain",
            ambient_audio="Rain drumming heavily on wet woolen officer greatcoat and granite battlements",
        )

        visual_p, audio_p, _ = build_ttd_flow_prompt(cfg)

        return FlowScene(
            scene_id=scene_id,
            scene_number=scene_number,
            title=title,
            narration_text=narration,
            visual_prompt=visual_p,
            duration_sec=dur,
            camera_motion=cam_motion,
            on_screen_bullets=bullets,
            status="pending",
            voice_persona=persona,
            voice_style=v_style,
            native_veo_audio=True,
            veo_audio_prompt=audio_p,
            tts_narration_text=tts_narration,
            pedagogical_phase=self.default_pedagogical_phase,
            timecoded_directives=timecoded,
            learning_objective="Demonstrate tactical commanding, attrition modeling, and psychological discipline under crisis",
        )


# ==============================================================================
# Template 3: Knight Lucas Vanguard Defense
# ==============================================================================

class VanguardDefenseTemplate(TTDStoryboardTemplate):
    """Knight Lucas absorbing violent monster strikes with his heavy spiked tower shield."""

    def __init__(
        self,
        template_id: str = "vanguard_defense",
        template_name: str = "Knight Lucas Vanguard Defense & Shield Wall",
        description: str = "Knight Lucas planting his massive tower shield against diving gargoyles",
        scene_archetype: str = "heroic_vanguard_defense",
        default_duration_sec: float = 7.0,
        default_camera_motion: str = "low-angle heroic dolly slide, heavy physical impact",
        default_voice_persona: str = "voice_y0joebp3bwta",
        default_voice_style: str = "deep resonant loyal warrior",
        default_pedagogical_phase: str = "Physical Dynamics & Defense",
    ) -> None:
        super().__init__(
            template_id=template_id,
            template_name=template_name,
            description=description,
            scene_archetype=scene_archetype,
            default_duration_sec=default_duration_sec,
            default_camera_motion=default_camera_motion,
            default_voice_persona=default_voice_persona,
            default_voice_style=default_voice_style,
            default_pedagogical_phase=default_pedagogical_phase,
        )

    def build_scene(
        self,
        scene_id: str,
        scene_number: int,
        language: str = "ru",
        duration_sec: Optional[float] = None,
        camera_motion: Optional[str] = None,
        voice_persona: Optional[str] = None,
        voice_style: Optional[str] = None,
        custom_action: Optional[str] = None,
        custom_narration: Optional[str] = None,
        custom_tts_narration: Optional[str] = None,
        **kwargs: Any,
    ) -> FlowScene:
        cam_motion = camera_motion or self.default_camera_motion
        dur = duration_sec if duration_sec is not None else self.default_duration_sec
        persona = voice_persona or self.default_voice_persona
        v_style = voice_style or self.default_voice_style

        title = "\u0420\u044b\u0446\u0430\u0440\u044c \u041b\u0443\u043a\u0430\u0441: \u041d\u0435\u0441\u043e\u043a\u0440\u0443\u0448\u0438\u043c\u044b\u0439 \u0436\u0435\u043b\u0435\u0437\u043d\u044b\u0439 \u0431\u0430\u0441\u0442\u0438\u043e\u043d"
        narration = custom_narration or (
            "\u0420\u044b\u0446\u0430\u0440\u044c \u041b\u0443\u043a\u0430\u0441 \u0432\u0440\u0443\u0431\u0430\u0435\u0442 \u0442\u044f\u0436\u0451\u043b\u044b\u0439 \u0440\u043e\u0441\u0442\u043e\u0432\u043e\u0439 \u0449\u0438\u0442 \u0432 \u043a\u0430\u043c\u0435\u043d\u044c. "
            "\u0423\u0434\u0430\u0440 \u043f\u0438\u043a\u0438\u0440\u0443\u044e\u0449\u0435\u0439 \u0442\u0432\u0430\u0440\u0438 \u0432\u044b\u0441\u0435\u043a\u0430\u0435\u0442 \u0441\u043d\u043e\u043f \u0438\u0441\u043a\u0440. "
            "\u041f\u043e\u043a\u0430 \u0441\u0442\u043e\u0438\u0442 \u041b\u0443\u043a\u0430\u0441 \u2014 \u043b\u0438\u043d\u0438\u044f \u043e\u0431\u043e\u0440\u043e\u043d\u044b \u0434\u0435\u0440\u0436\u0438\u0442\u0441\u044f."
        )
        tts_narration = custom_tts_narration or (
            "\u0420\u044b\u0446\u0430\u0440\u044c \u041b+\u0443\u043a\u0430\u0441 \u0432\u0440\u0443\u0431+\u0430\u0435\u0442 \u0442\u044f\u0436+\u0451\u043b\u044b\u0439 \u0440\u043e\u0441\u0442\u043e\u0432+\u043e\u0439 \u0449\u0438\u0442 \u0432 \u043a+\u0430\u043c\u0435\u043d\u044c. <short pause> "
            "\u0423\u0434+\u0430\u0440 \u043f\u0438\u043a\u0438\u0440\u0443\u044e\u0449\u0435\u0439 \u0442\u0432+\u0430\u0440\u0438 \u0432\u044b\u0441\u0435\u043a+\u0430\u0435\u0442 \u0441\u043d\u043e\u043f \u0438\u0441\u043a\u0440. <short pause> "
            "*\u041f\u043e\u043a+\u0430 \u0441\u0442\u043e+\u0438\u0442 \u041b+\u0443\u043a\u0430\u0441 \u2014 \u043b+\u0438\u043d\u0438\u044f \u043e\u0431\u043e\u0440+\u043e\u043d\u044b \u0434+\u0435\u0440\u0436\u0438\u0442\u0441\u044f.*"
        )

        timecoded = [
            {"window": "0-2s", "action": "Low-angle camera slides toward Lucas as he drops into a rigid crouch, ramming the tower shield into the parapet."},
            {"window": "2-5s", "action": "Diving gargoyle smashes into the shield face; sparks erupt violently into the torrential downpour."},
            {"window": "5-7s", "action": "Lucas thrusts the heavy shield forward, staggering the beast, and draws his broadsword for a lethal counter."},
        ]

        bullets = [
            "\u0410\u0432\u0430\u043d\u0433\u0430\u0440\u0434: \u0440\u044b\u0446\u0430\u0440\u044c \u041b\u0443\u043a\u0430\u0441",
            "\u041f\u043e\u0433\u043b\u043e\u0449\u0435\u043d\u0438\u0435 \u0443\u0434\u0430\u0440\u0430: \u0440\u043e\u0441\u0442\u043e\u0432\u043e\u0439 \u0449\u0438\u0442-\u043f\u0430\u0432\u0435\u0437\u0430",
            "\u0423\u0434\u0435\u0440\u0436\u0430\u043d\u0438\u0435 \u0431\u0440\u0435\u0448\u0438 \u043d\u0430 \u043a\u0440\u0435\u043f\u043e\u0441\u0442\u043d\u043e\u0439 \u0441\u0442\u0435\u043d\u0435",
        ]

        cfg = Prompt6LayerConfig(
            camera_motion=cam_motion,
            camera_framing="heavy physical impact, low angle heroic tracking",
            lighting_model=LIGHTING_ROARING_TORCHLIGHT,
            color_tokens=["pitch_amber", "weathered_iron", "obsidian_black"],
            environment_id="crossroads_fortress",
            environment_zone="battlements",
            characters=["knight_lucas"],
            monsters=["black_scaled_gargoyle"],
            action=custom_action or "Knight Lucas plants the bottom spike of his massive tower shield into the stone pavement, absorbing the massive kinetic strike of the diving gargoyle; sparks and stone splinters burst into the rain.",
            motion_dynamics=MOTION_SHIELD_COLLISION,
            timecoded_actions=timecoded,
            composition_and_style="cinematic dark fantasy anime aesthetic, 8k resolution, photoreal anime detail, dynamic chiaroscuro",
            narration_text=narration,
            voice_persona=persona,
            voice_style=v_style,
            sound_effects="Explosive metallic impact of beast talons slamming into heavy iron plate, razor talons screeching across steel throwing sparks, deep warrior battle grunt, heavy broadsword slicing through air",
            ambient_audio="Driving rainstorm, shouting defenders, and crackling brazier fires",
        )

        visual_p, audio_p, _ = build_ttd_flow_prompt(cfg)

        return FlowScene(
            scene_id=scene_id,
            scene_number=scene_number,
            title=title,
            narration_text=narration,
            visual_prompt=visual_p,
            duration_sec=dur,
            camera_motion=cam_motion,
            on_screen_bullets=bullets,
            status="pending",
            voice_persona=persona,
            voice_style=v_style,
            native_veo_audio=True,
            veo_audio_prompt=audio_p,
            tts_narration_text=tts_narration,
            pedagogical_phase=self.default_pedagogical_phase,
            timecoded_directives=timecoded,
            learning_objective="Examine heroic vanguard kinetic impact absorption and frontline stability under siege",
        )


# ==============================================================================
# Template 4: Archer Lily Precision Awakening
# ==============================================================================

class SniperAwakeningTemplate(TTDStoryboardTemplate):
    """Archer Lily achieving cold awakened focus with recurve horn bow and bodkin arrow."""

    def __init__(
        self,
        template_id: str = "sniper_awakening",
        template_name: str = "Archer Lily Precision Awakening",
        description: str = "Archer Lily overcoming fear and awakening sniper precision with horn bow and bodkin arrow",
        scene_archetype: str = "precision_sniper_awakening",
        default_duration_sec: float = 7.5,
        default_camera_motion: str = "extreme macro tracking shot along arrow shaft, rack focus",
        default_voice_persona: str = "voice_y0joebp3bwta",
        default_voice_style: str = "intense focused young marksman",
        default_pedagogical_phase: str = "Precision Mechanics & Overcoming Crisis",
    ) -> None:
        super().__init__(
            template_id=template_id,
            template_name=template_name,
            description=description,
            scene_archetype=scene_archetype,
            default_duration_sec=default_duration_sec,
            default_camera_motion=default_camera_motion,
            default_voice_persona=default_voice_persona,
            default_voice_style=default_voice_style,
            default_pedagogical_phase=default_pedagogical_phase,
        )

    def build_scene(
        self,
        scene_id: str,
        scene_number: int,
        language: str = "ru",
        duration_sec: Optional[float] = None,
        camera_motion: Optional[str] = None,
        voice_persona: Optional[str] = None,
        voice_style: Optional[str] = None,
        custom_action: Optional[str] = None,
        custom_narration: Optional[str] = None,
        custom_tts_narration: Optional[str] = None,
        **kwargs: Any,
    ) -> FlowScene:
        cam_motion = camera_motion or self.default_camera_motion
        dur = duration_sec if duration_sec is not None else self.default_duration_sec
        persona = voice_persona or self.default_voice_persona
        v_style = voice_style or self.default_voice_style

        title = "\u041b\u0443\u0447\u043d\u0438\u0446\u0430 \u041b\u0438\u043b\u0438: \u041f\u0440\u043e\u0431\u0443\u0436\u0434\u0435\u043d\u0438\u0435 \u0441\u043d\u0430\u0439\u043f\u0435\u0440\u0441\u043a\u043e\u0439 \u0442\u043e\u0447\u043d\u043e\u0441\u0442\u0438"
        narration = custom_narration or (
            "\u0421\u0442\u0440\u0430\u0445 \u043e\u0442\u0441\u0442\u0443\u043f\u0430\u0435\u0442 \u043f\u0435\u0440\u0435\u0434 \u043f\u0440\u0438\u043a\u0430\u0437\u043e\u043c \u043a\u043e\u043c\u0430\u043d\u0434\u0438\u0440\u0430. "
            "\u0414\u0440\u043e\u0436\u044c \u0432 \u0440\u0443\u043a\u0430\u0445 \u041b\u0438\u043b\u0438 \u0441\u043c\u0435\u043d\u044f\u0435\u0442\u0441\u044f \u043b\u0435\u0434\u044f\u043d\u044b\u043c \u0441\u043f\u043e\u043a\u043e\u0439\u0441\u0442\u0432\u0438\u0435\u043c. "
            "\u041d\u0430\u0442\u044f\u043d\u0443\u0442\u0430\u044f \u0442\u0435\u0442\u0438\u0432\u0430, \u0437\u0430\u0434\u0435\u0440\u0436\u043a\u0430 \u0434\u044b\u0445\u0430\u043d\u0438\u044f \u2014 \u0432\u044b\u0441\u0442\u0440\u0435\u043b \u0442\u043e\u0447\u043d\u043e \u0432 \u0443\u044f\u0437\u0432\u0438\u043c\u043e\u0435 \u0441\u043e\u0447\u043b\u0435\u043d\u0435\u043d\u0438\u0435."
        )
        tts_narration = custom_tts_narration or (
            "\u0421\u0442\u0440\u0430\u0445 \u043e\u0442\u0441\u0442\u0443\u043f+\u0430\u0435\u0442 \u043f+\u0435\u0440\u0435\u0434 \u043f\u0440\u0438\u043a+\u0430\u0437\u043e\u043c \u043a\u043e\u043c\u0430\u043d\u0434+\u0438\u0440\u0430. <short pause> "
            "\u0414\u0440\u043e\u0436\u044c \u0432 \u0440\u0443\u043a+\u0430\u0445 \u041b+\u0438\u043b\u0438 \u0441\u043c\u0435\u043d+\u044f\u0435\u0442\u0441\u044f \u043b\u0435\u0434\u044f\u043d+\u044b\u043c \u0441\u043f\u043e\u043a+\u043e\u0439\u0441\u0442\u0432\u0438\u0435\u043c. <short pause> "
            "*\u041d\u0430\u0442+\u044f\u043d\u0443\u0442\u0430\u044f \u0442\u0435\u0442\u0438\u0432+\u0430, \u0437\u0430\u0434+\u0435\u0440\u0436\u043a\u0430 \u0434\u044b\u0445+\u0430\u043d\u0438\u044f \u2014 \u0432\u044b\u0441\u0442\u0440\u0435\u043b \u0442+\u043e\u0447\u043d\u043e \u0432 \u0443\u044f\u0437\u0432+\u0438\u043c\u043e\u0435 \u0441\u043e\u0447\u043b\u0435\u043d+\u0435\u043d\u0438\u0435.*"
        )

        timecoded = [
            {"window": "0-2s", "action": "Close-up on trembling fingers gripping the bowstring; Ash's firm hand grounds her shoulder as trembling vanishes."},
            {"window": "2-5s", "action": "Camera rack-focuses from Lily's narrowed predator amber eyes down the grooved shaft of the bodkin arrow."},
            {"window": "5-8s", "action": "Taut release of the bowstring; camera tracks the whistling projectile exploding forward with azure vapor trail."},
        ]

        bullets = [
            "\u041f\u0441\u0438\u0445\u043e\u043b\u043e\u0433\u0438\u0447\u0435\u0441\u043a\u043e\u0435 \u043f\u0440\u043e\u0431\u0443\u0436\u0434\u0435\u043d\u0438\u0435: \u0441\u043d\u0430\u0439\u043f\u0435\u0440 \u041b\u0438\u043b\u0438",
            "\u041c\u0430\u0433\u0438\u0447\u0435\u0441\u043a\u0430\u044f \u043a\u043e\u043d\u0446\u0435\u043d\u0442\u0440\u0430\u0446\u0438\u044f: \u0441\u0442\u0440\u0435\u043b\u0430-\u0431\u043e\u0434\u043a\u0438\u043d",
            "\u041f\u0440\u0438\u0446\u0435\u043b\u0438\u0432\u0430\u043d\u0438\u0435 \u0432 \u0443\u044f\u0437\u0432\u0438\u043c\u043e\u0435 \u0441\u043e\u0447\u043b\u0435\u043d\u0435\u043d\u0438\u0435",
        ]

        cfg = Prompt6LayerConfig(
            camera_motion=cam_motion,
            camera_framing="rack focus, extreme macro tracking shot along arrow shaft",
            focal_depth="sub-millimeter optical focus on steel bodkin point, cinematic shallow depth of field",
            lighting_model=LIGHTING_BLOOD_MOON_VOLUMETRIC,
            color_tokens=["arcane_cyan", "arterial_crimson", "obsidian_black"],
            environment_id="crossroads_fortress",
            environment_zone="battlements",
            characters=["archer_lily"],
            character_phases={"archer_lily": "sniper"},
            action=custom_action or "Archer Lily in awakened sniper phase holds her breath, drawing her masterwork recurve horn bow to full tension as azure mana gathers on the black steel bodkin arrow point aimed directly forward.",
            motion_dynamics=MOTION_SLOW_MOTION_ARROW,
            timecoded_actions=timecoded,
            composition_and_style="cinematic dark fantasy anime aesthetic, 8k resolution, photoreal anime detail, dynamic chiaroscuro",
            narration_text=narration,
            voice_persona=persona,
            voice_style=v_style,
            sound_effects="Tense bowstring draw creak, sudden concussive arrow release whoosh, whistling bodkin flight cutting through wind",
            ambient_audio="Distant battlefield chaos suppressed into hyper-focused auditory tunnel, soft rain patter",
        )

        visual_p, audio_p, _ = build_ttd_flow_prompt(cfg)

        return FlowScene(
            scene_id=scene_id,
            scene_number=scene_number,
            title=title,
            narration_text=narration,
            visual_prompt=visual_p,
            duration_sec=dur,
            camera_motion=cam_motion,
            on_screen_bullets=bullets,
            status="pending",
            voice_persona=persona,
            voice_style=v_style,
            native_veo_audio=True,
            veo_audio_prompt=audio_p,
            tts_narration_text=tts_narration,
            pedagogical_phase=self.default_pedagogical_phase,
            timecoded_directives=timecoded,
            learning_objective="Highlight psychological mastery, fear suppression, and precision ballistics under pressure",
        )


# ==============================================================================
# Template 5: Boss Showdown & Tactical Trinity
# ==============================================================================

class BossShowdownTemplate(TTDStoryboardTemplate):
    """Climax engagement against Stage 1 Boss Cursed Living Armor Vanguard via Tactical Trinity."""

    def __init__(
        self,
        template_id: str = "boss_showdown",
        template_name: str = "Stage 1 Boss Showdown: Tactical Trinity",
        description: str = "Tactical Trinity synergy engagement against Cursed Living Armor Vanguard",
        scene_archetype: str = "tactical_trinity_climax",
        default_duration_sec: float = 8.5,
        default_camera_motion: str = "dynamic 360-degree orbital combat tracking shot, climax impact",
        default_voice_persona: str = "voice_y0joebp3bwta",
        default_voice_style: str = "grim authoritative Russian commander",
        default_pedagogical_phase: str = "Climax Synthesis & Synergistic Resolution",
    ) -> None:
        super().__init__(
            template_id=template_id,
            template_name=template_name,
            description=description,
            scene_archetype=scene_archetype,
            default_duration_sec=default_duration_sec,
            default_camera_motion=default_camera_motion,
            default_voice_persona=default_voice_persona,
            default_voice_style=default_voice_style,
            default_pedagogical_phase=default_pedagogical_phase,
        )

    def build_scene(
        self,
        scene_id: str,
        scene_number: int,
        language: str = "ru",
        duration_sec: Optional[float] = None,
        camera_motion: Optional[str] = None,
        voice_persona: Optional[str] = None,
        voice_style: Optional[str] = None,
        custom_action: Optional[str] = None,
        custom_narration: Optional[str] = None,
        custom_tts_narration: Optional[str] = None,
        **kwargs: Any,
    ) -> FlowScene:
        cam_motion = camera_motion or self.default_camera_motion
        dur = duration_sec if duration_sec is not None else self.default_duration_sec
        persona = voice_persona or self.default_voice_persona
        v_style = voice_style or self.default_voice_style

        title = "\u041a\u0443\u043b\u044c\u043c\u0438\u043d\u0430\u0446\u0438\u044f: \u0422\u0430\u043a\u0442\u0438\u0447\u0435\u0441\u043a\u043e\u0435 \u0442\u0440\u043e\u0435\u0434\u0438\u043d\u0441\u0442\u0432\u043e \u043f\u0440\u043e\u0442\u0438\u0432 \u0416\u0438\u0432\u043e\u0433\u043e \u0414\u043e\u0441\u043f\u0435\u0445\u0430"
        narration = custom_narration or (
            "\u041f\u0435\u0440\u0432\u044b\u0439 \u0431\u043e\u0441\u0441 \u2014 \u041f\u0440\u043e\u043a\u043b\u044f\u0442\u044b\u0439 \u0416\u0438\u0432\u043e\u0439 \u0414\u043e\u0441\u043f\u0435\u0445. "
            "\u041b\u0443\u043a\u0430\u0441 \u043f\u0440\u0438\u043d\u0438\u043c\u0430\u0435\u0442 \u0441\u043e\u043a\u0440\u0443\u0448\u0438\u0442\u0435\u043b\u044c\u043d\u044b\u0439 \u0443\u0434\u0430\u0440 \u043a\u043b\u0438\u043d\u043a\u0430. "
            "\u042d\u0448 \u0432\u0441\u043a\u0440\u044b\u0432\u0430\u0435\u0442 \u0443\u044f\u0437\u0432\u0438\u043c\u043e\u0435 \u044f\u0434\u0440\u043e \u0434\u0443\u0448\u0438, \u0430 \u041b\u0438\u043b\u0438 \u043d\u0430\u043d\u043e\u0441\u0438\u0442 \u0441\u043c\u0435\u0440\u0442\u0435\u043b\u044c\u043d\u044b\u0439 \u0432\u044b\u0441\u0442\u0440\u0435\u043b. "
            "\u042d\u0442\u043e \u2014 \u0422\u0430\u043a\u0442\u0438\u0447\u0435\u0441\u043a\u043e\u0435 \u0422\u0440\u043e\u0435\u0434\u0438\u043d\u0441\u0442\u0432\u043e \u041f\u0435\u0440\u0435\u043a\u0440\u0451\u0441\u0442\u043a\u0430."
        )
        tts_narration = custom_tts_narration or (
            "\u041f+\u0435\u0440\u0432\u044b\u0439 \u0431\u043e\u0441\u0441 \u2014 \u041f\u0440\u043e\u043a\u043b+\u044f\u0442\u044b\u0439 \u0416\u0438\u0432+\u043e\u0439 \u0414\u043e\u0441\u043f+\u0435\u0445. <short pause> "
            "\u041b+\u0443\u043a\u0430\u0441 \u043f\u0440\u0438\u043d\u0438\u043c+\u0430\u0435\u0442 \u0441\u043e\u043a\u0440\u0443\u0448+\u0438\u0442\u0435\u043b\u044c\u043d\u044b\u0439 \u0443\u0434+\u0430\u0440 \u043a\u043b\u0438\u043d\u043a+\u0430. <short pause> "
            "\u042d\u0448 \u0432\u0441\u043a\u0440\u044b\u0432+\u0430\u0435\u0442 \u0443\u044f\u0437\u0432+\u0438\u043c\u043e\u0435 \u044f\u0434\u0440+\u043e \u0434\u0443\u0448+\u0438, \u0430 \u041b+\u0438\u043b\u0438 \u043d\u0430\u043d+\u043e\u0441\u0438\u0442 \u0441\u043c\u0435\u0440\u0442+\u0435\u043b\u044c\u043d\u044b\u0439 \u0432\u044b\u0441\u0442\u0440\u0435\u043b. <short pause> "
            "*\u042d\u0442\u043e \u2014 \u0422\u0430\u043a\u0442\u0438\u0447\u0435\u0441\u043a\u043e\u0435 \u0422\u0440\u043e\u0435\u0434\u0438\u043d\u0441\u0442\u0432\u043e \u041f\u0435\u0440\u0435\u043a\u0440+\u0451\u0441\u0442\u043a\u0430.*"
        )

        timecoded = [
            {"window": "0-3s", "action": "Boss raises colossal jagged executioner greatsword overhead; Lucas braces under the shield as blade impacts in an explosion of sparks."},
            {"window": "3-6s", "action": "Ash shouts and aims the azure crystal; the joint seam on the boss armpit flares with unstable red soul-fire."},
            {"window": "6-9s", "action": "Lily's bodkin arrow hits dead center; the soul-core detonates into violet embers as the armor collapses to stone."},
        ]

        bullets = [
            "\u0422\u0430\u043a\u0442\u0438\u0447\u0435\u0441\u043a\u043e\u0435 \u0422\u0440\u043e\u0435\u0434\u0438\u043d\u0441\u0442\u0432\u043e: \u0441\u0438\u043d\u0435\u0440\u0433\u0438\u044f \u043a\u043b\u0430\u0441\u0441\u043e\u0432",
            "\u042d\u0442\u0430\u043f 1: \u041b\u0443\u043a\u0430\u0441 \u043f\u0430\u0440\u0438\u0440\u0443\u0435\u0442 -> \u042d\u0442\u0430\u043f 2: \u042d\u0448 \u0432\u0441\u043a\u0440\u044b\u0432\u0430\u0435\u0442",
            "\u042d\u0442\u0430\u043f 3: \u041b\u0438\u043b\u0438 \u0443\u043d\u0438\u0447\u0442\u043e\u0436\u0430\u0435\u0442 \u044f\u0434\u0440\u043e \u0434\u0443\u0448\u0438",
        ]

        cfg = Prompt6LayerConfig(
            camera_motion=cam_motion,
            camera_framing="360-degree rotational tracking, climax cinematic composition",
            lighting_model=LIGHTING_WITCH_FIRE_CHIAROSCURO,
            color_tokens=["witch_fire_violet", "arterial_crimson", "arcane_cyan", "weathered_iron"],
            environment_id="crossroads_fortress",
            environment_zone="gatehouse",
            characters=["knight_lucas", "ash_bornhater", "archer_lily"],
            character_phases={"archer_lily": "sniper"},
            monsters=["living_armor_vanguard"],
            action=custom_action or "The colossal boss Cursed Living Armor Vanguard swings its jagged executioner greatsword into Knight Lucas's braced tower shield in a cataclysm of sparks; Prince Ash directs the strike with his pulsing crystal; Archer Lily releases a bodkin arrow straight into the exposed crimson soul-core.",
            motion_dynamics=MOTION_SOUL_FIRE_CLEAVE,
            timecoded_actions=timecoded,
            composition_and_style="cinematic dark fantasy anime masterpiece, 8k resolution, photoreal anime detail, dynamic chiaroscuro",
            narration_text=narration,
            voice_persona=persona,
            voice_style=v_style,
            sound_effects="Colossal thunderous metallic shockwave as boss greatsword slams into tower shield, crisp sonic crack of supersonic whistling bodkin arrow, explosive shattering of the cursed soul-core into crackling energy shards",
            ambient_audio="Roaring storm wind and victorious battle cries echoing through the fortress ramparts",
        )

        visual_p, audio_p, _ = build_ttd_flow_prompt(cfg)

        return FlowScene(
            scene_id=scene_id,
            scene_number=scene_number,
            title=title,
            narration_text=narration,
            visual_prompt=visual_p,
            duration_sec=dur,
            camera_motion=cam_motion,
            on_screen_bullets=bullets,
            status="pending",
            voice_persona=persona,
            voice_style=v_style,
            native_veo_audio=True,
            veo_audio_prompt=audio_p,
            tts_narration_text=tts_narration,
            pedagogical_phase=self.default_pedagogical_phase,
            timecoded_directives=timecoded,
            learning_objective="Synthesize the Tactical Trinity tripartite class mechanics in defeating a high-tier stage boss",
        )


# ==============================================================================
# Template Registry & Discovery
# ==============================================================================

TEMPLATE_REGISTRY: Dict[str, TTDStoryboardTemplate] = {
    "fortress_atmosphere": FortressAtmosphereTemplate(),
    "tactical_command": TacticalCommandTemplate(),
    "vanguard_defense": VanguardDefenseTemplate(),
    "sniper_awakening": SniperAwakeningTemplate(),
    "boss_showdown": BossShowdownTemplate(),
}


def get_storyboard_template(template_id: str) -> TTDStoryboardTemplate:
    """Retrieve storyboard template singleton by slug or fuzzy identifier."""
    norm = template_id.strip().lower().replace("-", "_")
    if norm in TEMPLATE_REGISTRY:
        return TEMPLATE_REGISTRY[norm]
    for key, tmpl in TEMPLATE_REGISTRY.items():
        if norm in key or key in norm:
            return tmpl
    raise KeyError(f"Unknown storyboard template_id: {template_id}")


# ==============================================================================
# Pilot Storyboard Factory
# ==============================================================================

def build_ttd_pilot_storyboard(
    project_id: str = "flow_ttd_pilot_crossroads",
    language: str = "ru",
    include_boss: bool = True,
) -> FlowStoryboard:
    """
    Construct the complete end-to-end pilot storyboard for the Crossroads
    Prologue / First Wave Defense using the 5 core storyboard templates.
    Total duration: 37.5 seconds across 5 dramatic scenes.
    """
    scenes: List[FlowScene] = []

    # Scene 1: Prologue / Fortress Atmosphere (7.5s)
    sc1 = TEMPLATE_REGISTRY["fortress_atmosphere"].build_scene(
        scene_id="sc_crossroads_01_prologue",
        scene_number=1,
        language=language,
        duration_sec=7.5,
    )
    scenes.append(sc1)

    # Scene 2: Tactical Command / Prince Ash (7.0s)
    sc2 = TEMPLATE_REGISTRY["tactical_command"].build_scene(
        scene_id="sc_crossroads_02_command",
        scene_number=2,
        language=language,
        duration_sec=7.0,
    )
    scenes.append(sc2)

    # Scene 3: Vanguard Defense / Knight Lucas (7.0s)
    sc3 = TEMPLATE_REGISTRY["vanguard_defense"].build_scene(
        scene_id="sc_crossroads_03_vanguard",
        scene_number=3,
        language=language,
        duration_sec=7.0,
    )
    scenes.append(sc3)

    # Scene 4: Sniper Awakening / Archer Lily (7.5s)
    sc4 = TEMPLATE_REGISTRY["sniper_awakening"].build_scene(
        scene_id="sc_crossroads_04_sniper",
        scene_number=4,
        language=language,
        duration_sec=7.5,
    )
    scenes.append(sc4)

    # Scene 5: Boss Showdown / Living Armor Vanguard (8.5s)
    if include_boss:
        sc5 = TEMPLATE_REGISTRY["boss_showdown"].build_scene(
            scene_id="sc_crossroads_05_boss",
            scene_number=5,
            language=language,
            duration_sec=8.5,
        )
        scenes.append(sc5)

    topic = "\u0422\u0438\u0440\u0430\u043d \u0432 \u043e\u0431\u043e\u0440\u043e\u043d\u0438\u0442\u0435\u043b\u044c\u043d\u043e\u0439 \u0438\u0433\u0440\u0435: \u041f\u0435\u0440\u0435\u043a\u0440\u0451\u0441\u0442\u043e\u043a \u2014 \u041f\u0435\u0440\u0432\u0430\u044f \u0432\u043e\u043b\u043d\u0430"

    return FlowStoryboard(
        project_id=project_id,
        topic=topic,
        language=language,
        target_audience="intermediate",
        aspect_ratio="16:9",
        model_key="veo_3_1_t2v_fast",
        scenes=scenes,
        status="storyboard_ready",
    )


# ==============================================================================
# Serialization & Validation
# ==============================================================================

AUTHORIZED_VOICE_PERSONAS: set[str] = {
    "voice_y0joebp3bwta",
    "Sulafat",
    "Kore",
}


def export_storyboard_to_json(
    storyboard: FlowStoryboard,
    path: Optional[Union[str, Path]] = None,
    indent: int = 2,
) -> str:
    """
    Export a FlowStoryboard instance to an ISO-compliant, Unicode-safe JSON string
    and optionally write to disk.
    """
    payload = storyboard.to_dict()
    json_str = json.dumps(payload, indent=indent, ensure_ascii=True)
    if path is not None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json_str, encoding="utf-8")
    return json_str


def load_storyboard_from_json(
    json_str_or_path: Union[str, Path],
) -> FlowStoryboard:
    """
    Load and reconstruct a FlowStoryboard instance from a JSON string or file path.

    Raises:
        FileNotFoundError: If the input represents a file path that does not exist on disk,
                           or is an unresolvable string that cannot be decoded as JSON.
        ValueError: If the JSON payload root is not a dictionary or contains malformed JSON.
    """
    if isinstance(json_str_or_path, (Path, os.PathLike)):
        p = Path(json_str_or_path)
        if not p.is_file():
            raise FileNotFoundError(f"Storyboard JSON file not found: {json_str_or_path}")
        content = p.read_text(encoding="utf-8")
    else:
        raw = str(json_str_or_path).strip()
        is_json_literal = (
            (raw.startswith("{") and raw.endswith("}"))
            or (raw.startswith("[") and raw.endswith("]"))
        )
        has_path_marker = (
            raw.lower().endswith(".json")
            or "/" in raw
            or "\\" in raw
        )
        p = Path(raw)
        if not is_json_literal and (has_path_marker or p.is_file()):
            if not p.is_file():
                raise FileNotFoundError(f"Storyboard JSON file not found: {raw}")
            content = p.read_text(encoding="utf-8")
        elif p.is_file():
            content = p.read_text(encoding="utf-8")
        else:
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, ValueError) as err:
                raise FileNotFoundError(f"Storyboard JSON file not found: {raw}") from err
            else:
                if not isinstance(data, dict):
                    raise ValueError(
                        f"Invalid storyboard JSON: root element must be a dictionary, got {type(data).__name__}"
                    )
                return FlowStoryboard.from_dict(data)

    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError) as err:
        raise ValueError(f"Malformed JSON content in storyboard file: {err}") from err

    if not isinstance(data, dict):
        raise ValueError(
            f"Invalid storyboard JSON: root element must be a dictionary, got {type(data).__name__}"
        )

    return FlowStoryboard.from_dict(data)


def validate_storyboard(
    storyboard: FlowStoryboard,
    raise_on_error: bool = False,
) -> bool:
    """
    Verify structural validity of a FlowStoryboard and its scenes:
    - storyboard is a valid FlowStoryboard or FlowEducationalProject instance
    - project_id and topic are non-empty strings
    - target_audience (if present) is a non-empty string
    - scenes list contains at least 1 FlowScene
    - each scene has non-empty scene_id, title, narration_text, visual_prompt,
      camera_motion, and voice_persona
    - duration_sec > 0.0 for every scene
    - voice_persona is in the authorized set {"voice_y0joebp3bwta", "Sulafat", "Kore"}

    Parameters:
        storyboard: The FlowStoryboard instance to validate.
        raise_on_error: If True, raises ValueError with a descriptive diagnostic
                        message on validation failure. If False, returns False.

    Returns:
        True if the storyboard passes all validation checks, False otherwise
        (when raise_on_error is False).

    Raises:
        ValueError: When validation fails and raise_on_error is True.
    """
    def _fail(msg: str) -> bool:
        if raise_on_error:
            raise ValueError(msg)
        return False

    if not isinstance(storyboard, (FlowEducationalProject, FlowStoryboard)):
        return _fail(
            f"Invalid storyboard type: expected FlowStoryboard or FlowEducationalProject, "
            f"got {type(storyboard).__name__}"
        )

    if not getattr(storyboard, "project_id", None) or not str(storyboard.project_id).strip():
        return _fail("Storyboard project_id must be a non-empty string")

    if not getattr(storyboard, "topic", None) or not str(storyboard.topic).strip():
        return _fail("Storyboard topic must be a non-empty string")

    if hasattr(storyboard, "target_audience") and (
        not storyboard.target_audience or not str(storyboard.target_audience).strip()
    ):
        return _fail("Storyboard target_audience must be a non-empty string")

    if not hasattr(storyboard, "scenes") or not isinstance(storyboard.scenes, list):
        return _fail(
            f"Storyboard scenes must be a list, got {type(getattr(storyboard, 'scenes', None)).__name__}"
        )

    if len(storyboard.scenes) == 0:
        return _fail("Storyboard scenes list must contain at least 1 FlowScene")

    for idx, sc in enumerate(storyboard.scenes):
        if not isinstance(sc, FlowScene):
            return _fail(
                f"Scene at index {idx} must be a FlowScene instance, got {type(sc).__name__}"
            )

        scene_ref = (
            f"'{sc.scene_id}' (scene #{getattr(sc, 'scene_number', idx + 1)})"
            if getattr(sc, "scene_id", None) and str(sc.scene_id).strip()
            else f"at index {idx}"
        )

        if not getattr(sc, "scene_id", None) or not str(sc.scene_id).strip():
            return _fail(f"Scene at index {idx} has missing or empty scene_id")

        if not getattr(sc, "title", None) or not str(sc.title).strip():
            return _fail(f"Scene {scene_ref} has missing or empty title")

        if not getattr(sc, "narration_text", None) or not str(sc.narration_text).strip():
            return _fail(f"Scene {scene_ref} has missing or empty narration_text")

        if not getattr(sc, "visual_prompt", None) or not str(sc.visual_prompt).strip():
            return _fail(f"Scene {scene_ref} has missing or empty visual_prompt")

        if (
            sc.duration_sec is None
            or not isinstance(sc.duration_sec, (int, float))
            or sc.duration_sec <= 0.0
        ):
            return _fail(
                f"Scene {scene_ref} has invalid duration_sec={sc.duration_sec} (must be a positive number > 0.0)"
            )

        if not getattr(sc, "camera_motion", None) or not str(sc.camera_motion).strip():
            return _fail(f"Scene {scene_ref} has missing or empty camera_motion")

        persona = str(getattr(sc, "voice_persona", "") or "").strip()
        if not persona:
            return _fail(f"Scene {scene_ref} has missing or empty voice_persona")

        if persona not in AUTHORIZED_VOICE_PERSONAS:
            auth_str = ", ".join(f"'{p}'" for p in sorted(AUTHORIZED_VOICE_PERSONAS))
            return _fail(
                f"Scene {scene_ref} has unauthorized voice_persona '{sc.voice_persona}'. "
                f"Authorized voice personas are: {auth_str}"
            )

    return True


# ==============================================================================
# Stage 0 / 3-Act Episode Manifest Schema & Validator (Chapters 001-010)
# ==============================================================================

CHARACTER_VOICE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "ASH": {"voice_id": "Alnilam", "gender": "M", "pitch_semitones": 0.0, "role": "3rd Prince Ash Everblack"},
    "LUCAS": {"voice_id": "Orus", "gender": "M", "pitch_semitones": -1.0, "role": "Knight Lucas MacGregor"},
    "LILY": {"voice_id": "Aoede", "gender": "F", "pitch_semitones": 0.0, "role": "Fire Mage Lily"},
    "DAMIEN": {"voice_id": "Fenrir", "gender": "M", "pitch_semitones": 1.5, "role": "Healer Priest Damien"},
    "KEN": {"voice_id": "Charon", "gender": "M", "pitch_semitones": -2.0, "role": "Shield Knight Ken"},
    "EIDER": {"voice_id": "Puck", "gender": "M", "pitch_semitones": 0.5, "role": "Director Eider"},
    "FOXY": {"voice_id": "Kore", "gender": "F", "pitch_semitones": 1.0, "role": "Stream Viewer Foxy"},
}

STAGE0_AUTHORIZED_VOICE_IDS: set[str] = {
    v["voice_id"] for v in CHARACTER_VOICE_REGISTRY.values()
} | AUTHORIZED_VOICE_PERSONAS


@dataclass
class DialogueTurn:
    turn_index: int
    speaker_id: str
    voice_id: str
    raw_bookmarked_text: str
    window_start_sec: float
    window_end_sec: float
    emotion_cue: str = "determined"

    @property
    def text_ru_with_bookmarks(self) -> str:
        return self.raw_bookmarked_text

    @property
    def style_prompt(self) -> str:
        return self.emotion_cue

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_index": self.turn_index,
            "speaker_id": self.speaker_id,
            "voice_id": self.voice_id,
            "raw_bookmarked_text": self.raw_bookmarked_text,
            "text_ru_with_bookmarks": self.raw_bookmarked_text,
            "window_start_sec": self.window_start_sec,
            "window_end_sec": self.window_end_sec,
            "emotion_cue": self.emotion_cue,
            "style_prompt": self.emotion_cue,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DialogueTurn":
        spk = str(data.get("speaker_id", "ASH")).upper()
        default_vid = CHARACTER_VOICE_REGISTRY.get(spk, {}).get("voice_id", "Alnilam")
        txt = str(data.get("raw_bookmarked_text") or data.get("text_ru_with_bookmarks") or "")
        cue = str(data.get("emotion_cue") or data.get("style_prompt") or "determined")
        return cls(
            turn_index=int(data.get("turn_index", 0)),
            speaker_id=spk,
            voice_id=str(data.get("voice_id") or default_vid),
            raw_bookmarked_text=txt,
            window_start_sec=float(data.get("window_start_sec", 0.2)),
            window_end_sec=float(data.get("window_end_sec", 4.5)),
            emotion_cue=cue,
        )


@dataclass
class StatusWindowSpec:
    window_type: str
    theme_color: str
    header_title: str
    body_lines: List[str]
    appear_sec: float = 0.4
    disappear_sec: float = 5.2
    rank_badge: Optional[str] = None
    resource_bar: Optional[Dict[str, Any]] = None
    screen_anchor: str = "TOP_RIGHT"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "window_type": self.window_type,
            "theme_color": self.theme_color,
            "header_title": self.header_title,
            "body_lines": list(self.body_lines),
            "appear_sec": self.appear_sec,
            "disappear_sec": self.disappear_sec,
            "rank_badge": self.rank_badge,
            "resource_bar": self.resource_bar,
            "screen_anchor": self.screen_anchor,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StatusWindowSpec":
        return cls(
            window_type=str(data.get("window_type", "TRAIT_INSPECT")),
            theme_color=str(data.get("theme_color", "BLUE_CYAN")),
            header_title=str(data.get("header_title", "")),
            body_lines=[str(x) for x in (data.get("body_lines") or [])],
            appear_sec=float(data.get("appear_sec", 0.4)),
            disappear_sec=float(data.get("disappear_sec", 5.2)),
            rank_badge=data.get("rank_badge"),
            resource_bar=data.get("resource_bar"),
            screen_anchor=str(data.get("screen_anchor", "TOP_RIGHT")),
        )


@dataclass
class ShotManifestEntry:
    shot_id: str
    act_id: int
    chapter_ref: str
    duration_sec: float
    chain_mode: str
    chain_depth: int
    start_frame_anchor: str
    character_sheet_refs: List[str]
    omni_visual_prompt: str
    allowed_vfx_tags: List[str] = field(default_factory=list)
    end_frame_anchor: Optional[str] = None
    status_window_overlay: Optional[StatusWindowSpec] = None
    dialogue_turns: List[DialogueTurn] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "shot_id": self.shot_id,
            "act_id": self.act_id,
            "chapter_ref": self.chapter_ref,
            "duration_sec": self.duration_sec,
            "chain_mode": self.chain_mode,
            "chain_depth": self.chain_depth,
            "start_frame_anchor": self.start_frame_anchor,
            "end_frame_anchor": self.end_frame_anchor,
            "character_sheet_refs": list(self.character_sheet_refs),
            "omni_visual_prompt": self.omni_visual_prompt,
            "allowed_vfx_tags": list(self.allowed_vfx_tags),
            "status_window_overlay": self.status_window_overlay.to_dict() if self.status_window_overlay else None,
            "dialogue_turns": [t.to_dict() for t in self.dialogue_turns],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ShotManifestEntry":
        ov = data.get("status_window_overlay")
        return cls(
            shot_id=str(data["shot_id"]),
            act_id=int(data.get("act_id", 1)),
            chapter_ref=str(data.get("chapter_ref", "001")),
            duration_sec=float(data.get("duration_sec", 8.0)),
            chain_mode=str(data.get("chain_mode", "HARD_ANCHOR_RESET")),
            chain_depth=int(data.get("chain_depth", 0)),
            start_frame_anchor=str(data.get("start_frame_anchor", "")),
            end_frame_anchor=data.get("end_frame_anchor"),
            character_sheet_refs=[str(x) for x in (data.get("character_sheet_refs") or [])],
            omni_visual_prompt=str(data.get("omni_visual_prompt", "")),
            allowed_vfx_tags=[str(x) for x in (data.get("allowed_vfx_tags") or [])],
            status_window_overlay=StatusWindowSpec.from_dict(ov) if isinstance(ov, dict) else None,
            dialogue_turns=[DialogueTurn.from_dict(t) for t in (data.get("dialogue_turns") or [])],
        )


@dataclass
class ActSpec:
    act_id: int
    title_ru: str
    flow_project_name: str
    bgm_track_path: str
    shots: List[ShotManifestEntry] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "act_id": self.act_id,
            "title_ru": self.title_ru,
            "flow_project_name": self.flow_project_name,
            "bgm_track_path": self.bgm_track_path,
            "shots": [s.to_dict() for s in self.shots],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActSpec":
        return cls(
            act_id=int(data["act_id"]),
            title_ru=str(data.get("title_ru", "")),
            flow_project_name=str(data.get("flow_project_name", "")),
            bgm_track_path=str(data.get("bgm_track_path", "")),
            shots=[ShotManifestEntry.from_dict(s) for s in (data.get("shots") or [])],
        )


@dataclass
class EpisodeManifest:
    episode_id: str
    target_resolution: str
    target_fps: int
    audio_sample_rate: int
    character_voice_registry: Dict[str, Dict[str, Any]]
    acts: List[ActSpec] = field(default_factory=list)

    def all_shots(self) -> List[ShotManifestEntry]:
        out: List[ShotManifestEntry] = []
        for act in self.acts:
            out.extend(act.shots)
        return out

    def to_dict(self) -> Dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "target_resolution": self.target_resolution,
            "target_fps": self.target_fps,
            "audio_sample_rate": self.audio_sample_rate,
            "character_voice_registry": dict(self.character_voice_registry),
            "acts": [a.to_dict() for a in self.acts],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EpisodeManifest":
        return cls(
            episode_id=str(data.get("episode_id", "ttd_ep01_prologue_stage0")),
            target_resolution=str(data.get("target_resolution", "1280x720")),
            target_fps=int(data.get("target_fps", 24)),
            audio_sample_rate=int(data.get("audio_sample_rate", 48000)),
            character_voice_registry=dict(data.get("character_voice_registry") or CHARACTER_VOICE_REGISTRY),
            acts=[ActSpec.from_dict(a) for a in (data.get("acts") or [])],
        )


def load_ep01_3act_manifest(path: Union[str, Path] = "config/ep01_3act_manifest.json") -> EpisodeManifest:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"3-Act Episode Manifest not found: {path}")
    data = json.loads(p.read_text(encoding="utf-8"))
    return EpisodeManifest.from_dict(data)


def validate_ep01_3act_manifest(manifest: EpisodeManifest) -> Dict[str, Any]:
    errors: List[str] = []
    if len(manifest.acts) != 3:
        errors.append(f"Expected 3 acts, got {len(manifest.acts)}")

    shots = manifest.all_shots()
    if not (100 <= len(shots) <= 140):
        errors.append(f"Expected 100..140 shots, got {len(shots)}")

    for act in manifest.acts:
        if not act.shots:
            errors.append(f"Act {act.act_id} has 0 shots")
            continue
        if act.shots[0].chain_mode != "HARD_ANCHOR_RESET" or act.shots[0].chain_depth != 0:
            errors.append(f"Act {act.act_id} first shot {act.shots[0].shot_id} must be HARD_ANCHOR_RESET (depth 0)")

    for idx, s in enumerate(shots, start=1):
        expected_id = f"SHOT-{idx:03d}"
        if s.shot_id != expected_id:
            errors.append(f"Shot index {idx} expected '{expected_id}', got '{s.shot_id}'")
        if s.chain_depth < 0 or s.chain_depth > 3:
            errors.append(f"{s.shot_id}: chain_depth={s.chain_depth} exceeds max depth 3")
        if s.chain_mode == "HARD_ANCHOR_RESET" and s.chain_depth != 0:
            errors.append(f"{s.shot_id}: HARD_ANCHOR_RESET must have chain_depth=0")
        if s.chain_mode == "FRAME_CHAIN_LAST_TO_FIRST" and not (1 <= s.chain_depth <= 3):
            errors.append(f"{s.shot_id}: FRAME_CHAIN_LAST_TO_FIRST must have chain_depth in 1..3")

        for turn in s.dialogue_turns:
            reg = manifest.character_voice_registry.get(turn.speaker_id)
            if not reg:
                errors.append(f"{s.shot_id}: unknown speaker_id '{turn.speaker_id}'")
            elif turn.voice_id != reg.get("voice_id"):
                errors.append(
                    f"{s.shot_id}: speaker {turn.speaker_id} voice_id '{turn.voice_id}' != '{reg.get('voice_id')}'"
                )
            if turn.window_end_sec > s.duration_sec - 0.5 + 1e-6:
                errors.append(
                    f"{s.shot_id}: turn {turn.turn_index} window_end_sec={turn.window_end_sec} violates 0.5s closed-mouth tail (duration={s.duration_sec})"
                )

    return {
        "valid": len(errors) == 0,
        "total_shots": len(shots),
        "total_duration_sec": round(sum(s.duration_sec for s in shots), 2),
        "errors": errors,
    }

