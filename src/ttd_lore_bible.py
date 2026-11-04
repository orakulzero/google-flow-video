"""
src/ttd_lore_bible.py
Tyrant of the Tower Defense Game - Series Production Foundation & Lore Bible.
Adaptive dark fantasy world-building, character design specifications,
monster bestiary, environmental aesthetics, and Veo 3.1 visual anchors.

Zero literal Cyrillic rule: all localized Russian strings use unicode escapes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ColorToken:
    token_id: str
    name: str
    hex_code: str
    rgb: Tuple[int, int, int]
    description: str
    usage: str
    semantic_role: str = ""

    def __post_init__(self) -> None:
        if not self.semantic_role:
            object.__setattr__(self, "semantic_role", self.description or self.usage)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CharacterPhase:
    phase_id: str
    name: str
    description: str
    visual_anchor: str
    emotional_state: str
    facial_expression: str
    stance_and_motion: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CharacterProfile:
    character_id: str
    name_en: str
    name_ru: str
    title_en: str
    title_ru: str
    role: str
    archetype: str
    physical_appearance: str
    facial_features: str
    costume_and_armor: str
    weapons_and_artifacts: List[str]
    psychological_profile: str
    master_visual_anchor: str
    phases: Dict[str, CharacterPhase] = field(default_factory=dict)
    key_tokens: List[str] = field(default_factory=list)
    visual_anchors: List[str] = field(default_factory=list)
    costume_tokens: List[str] = field(default_factory=list)
    signature_gear: List[str] = field(default_factory=list)
    personality_traits: List[str] = field(default_factory=list)
    voice_persona: str = "voice_y0joebp3bwta"
    voice_style: str = "grim authoritative Russian commander"

    def get_anchor(self, phase: Optional[str] = None) -> str:
        if phase and phase in self.phases:
            return self.phases[phase].visual_anchor
        return self.master_visual_anchor

    def to_prompt_tokens(self, phase: Optional[str] = None) -> str:
        return self.get_anchor(phase)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MonsterSpec:
    species_id: str
    name_en: str
    name_ru: str
    tier: str
    visual_anchors: List[str]
    behavior_tokens: List[str]
    threat_description: str
    category: str = "Aerial Swarm"
    threat_tier: str = "Tier 1"
    combat_behavior: str = ""
    anatomy_and_materials: str = ""
    master_visual_anchor: str = ""
    defeat_mechanic: Optional[str] = None
    key_tokens: List[str] = field(default_factory=list)
    monster_id: str = ""

    def __post_init__(self) -> None:
        if not self.monster_id:
            object.__setattr__(self, "monster_id", self.species_id)
        if not self.threat_tier:
            object.__setattr__(self, "threat_tier", self.tier)
        if not self.combat_behavior and self.behavior_tokens:
            object.__setattr__(self, "combat_behavior", "; ".join(self.behavior_tokens))
        if not self.master_visual_anchor and self.visual_anchors:
            object.__setattr__(self, "master_visual_anchor", "; ".join(self.visual_anchors))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


MonsterProfile = MonsterSpec


@dataclass(frozen=True)
class EnvironmentSpec:
    setting_id: str
    name_en: str
    name_ru: str
    architecture_anchors: List[str]
    atmosphere_anchors: List[str]
    strategic_zones: Dict[str, str]
    setting_type: str = "Fortress Citadel"
    architecture: str = ""
    weather_and_atmosphere: str = ""
    lighting_model: str = ""
    tactical_zones: List[str] = field(default_factory=list)
    master_visual_anchor: str = ""
    key_tokens: List[str] = field(default_factory=list)
    env_id: str = ""

    def __post_init__(self) -> None:
        if not self.env_id:
            object.__setattr__(self, "env_id", self.setting_id)
        if not self.architecture and self.architecture_anchors:
            object.__setattr__(self, "architecture", "; ".join(self.architecture_anchors))
        if not self.weather_and_atmosphere and self.atmosphere_anchors:
            object.__setattr__(self, "weather_and_atmosphere", "; ".join(self.atmosphere_anchors))
        if not self.tactical_zones and self.strategic_zones:
            object.__setattr__(self, "tactical_zones", list(self.strategic_zones.values()))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


EnvironmentProfile = EnvironmentSpec


@dataclass(frozen=True)
class PromptTemplate:
    template_id: str
    title: str
    scene_archetype: str
    camera_motion: str
    lighting_directive: str
    character_anchor: str
    environment_anchor: str
    action_directive: str
    composition_and_style: str

    def format_prompt(
        self,
        action: Optional[str] = None,
        camera: Optional[str] = None,
        lighting: Optional[str] = None,
    ) -> str:
        cam = camera or self.camera_motion
        light = lighting or self.lighting_directive
        act = action or self.action_directive
        return (
            f"In a single continuous unbroken cinematic shot, {cam}. "
            f"{self.environment_anchor}. {self.character_anchor}. "
            f"{act}. {light}, {self.composition_and_style}."
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LoreBible:
    series_title_en: str
    series_title_ru: str
    world_setting: str
    attrition_rules: List[str]
    black_fog_mechanics: str
    commander_axioms: List[str]
    characters: Dict[str, CharacterProfile]
    bestiary: Dict[str, MonsterSpec]
    environments: Dict[str, EnvironmentSpec]
    color_palette: Dict[str, ColorToken]
    prompt_templates: Dict[str, PromptTemplate]
    master_negative_prompt: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ==============================================================================
# Master Negative Prompts & Lore Rules
# ==============================================================================

TTD_MASTER_NEGATIVE_PROMPT: str = (
    "bright cheerful colors, oversaturated, high fantasy glossy armor, clean pristine clothes, "
    "modern weapons, modern firearms, modern clothing, sci-fi elements, sci-fi weapons, "
    "cute anime tropes, chibi, distorted hands, extra fingers, missing limbs, extra limbs, "
    "bad anatomy, deformed facial features, blurry textures, blurry artifacts, low-res, "
    "plastic skin, 3d CGI doll look, watermarks, text overlays, subtitles in image, "
    "smooth cartoon render, neon lighting, neon lights."
)

TTD_NEGATIVE_PROMPT_TOKENS: List[str] = [
    "bright cheerful colors",
    "high fantasy glossy armor",
    "clean pristine clothes",
    "modern firearms",
    "sci-fi elements",
    "cute anime tropes",
    "chibi",
    "distorted hands",
    "extra fingers",
    "extra limbs",
    "missing limbs",
    "bad anatomy",
    "deformed facial features",
    "blurry textures",
    "plastic skin",
    "smooth cartoon render",
    "neon lights",
]

LORE_RULES: Dict[str, str] = {
    "permadeath": (
        "Every casualty on the ramparts is permanent. Fallen defenders are gone forever "
        "with zero imperial reinforcements from the capital."
    ),
    "attrition_economy": (
        "Weapons fracture, siege munitions deplete, defensive battlements suffer cumulative structural damage, "
        "and garrison morale suffers continuous psychological erosion."
    ),
    "black_fog_miasma": (
        "Supernatural wall of roiling pitch-black mist 300 meters beyond the fortress moat. "
        "Waves emerge abruptly from the miasma with zero early astronomical warning."
    ),
    "tyrant_persona": (
        "Prince Ash maintains an icy, ruthlessly calculating persona to enforce combat discipline "
        "and prevent mass panic among terrified recruits."
    ),
    "hell_mode_clairvoyance": (
        "Trauma-driven master gamer tactical intuition translating complex battlefield states "
        "into geometric unit morale vectors and attrition equations."
    ),
}


# ==============================================================================
# Semantic Color Palette Registry (10 Tokens)
# ==============================================================================

COLOR_PALETTE: Dict[str, ColorToken] = {
    "basalt_stone": ColorToken(
        token_id="basalt_stone",
        name="Basalt Stone",
        hex_code="#2B2D31",
        rgb=(43, 45, 49),
        description="Dominant wall masonry, stone gargoyles, rain-slick stone pavements",
        usage="Fortress granite masonry and wet stone battlements",
    ),
    "obsidian_iron": ColorToken(
        token_id="obsidian_iron",
        name="Obsidian Iron",
        hex_code="#121316",
        rgb=(18, 19, 22),
        description="Heavy plate armor, officer trench coat, spiked gate ironwork, dark weapons",
        usage="Cold forged steel and blackened defensive ironwork",
    ),
    "scorched_steel": ColorToken(
        token_id="scorched_steel",
        name="Scorched Steel",
        hex_code="#3E434D",
        rgb=(62, 67, 77),
        description="Lucas scarred armor, sword blades, crossbow mechanisms, armor rivets",
        usage="Battle-tested tempered weapons and gouged armor plates",
    ),
    "oxidized_brass": ColorToken(
        token_id="oxidized_brass",
        name="Oxidized Brass",
        hex_code="#7A6A4E",
        rgb=(122, 106, 78),
        description="Ash coat trim, weathered buckles, antique banner poles, brazier chains",
        usage="Tarnished aristocratic embroidery and vintage mechanisms",
    ),
    "abyssal_fog": ColorToken(
        token_id="abyssal_fog",
        name="Abyssal Fog",
        hex_code="#090A0D",
        rgb=(9, 10, 13),
        description="Supernatural mist boundary, night sky voids, deep shadow crevices",
        usage="Ominous dungeon rift horizon and bottomless kill-zone moat",
    ),
    "midnight_storm": ColorToken(
        token_id="midnight_storm",
        name="Midnight Storm",
        hex_code="#0F1722",
        rgb=(15, 23, 34),
        description="Cloud masses, rain atmosphere, Lucas faded guard tabard",
        usage="Driving rain skybox and nocturnal shadows",
    ),
    "pitch_amber": ColorToken(
        token_id="pitch_amber",
        name="Pitch Amber",
        hex_code="#FF7700",
        rgb=(255, 119, 0),
        description="Roaring torch flames, brazier glow, explosion sparks, tactical eye glint",
        usage="Key practical lighting, parapet fires, and amber gaze highlights",
    ),
    "arterial_crimson": ColorToken(
        token_id="arterial_crimson",
        name="Arterial Crimson",
        hex_code="#8B0000",
        rgb=(139, 0, 0),
        description="Fresh blood on stone, torn mantle silk, boss eye-flames, danger vectors",
        usage="Visceral battlefield damage and supernatural menace",
    ),
    "arcane_cyan": ColorToken(
        token_id="arcane_cyan",
        name="Arcane Cyan",
        hex_code="#00E5FF",
        rgb=(0, 229, 255),
        description="Dispatch communication crystals, tactical trajectory telemetry highlights",
        usage="Mana signaling crystal and long-range aiming trajectory beam",
    ),
    "witch_fire_violet": ColorToken(
        token_id="witch_fire_violet",
        name="Witch-Fire Violet",
        hex_code="#4A154B",
        rgb=(74, 21, 75),
        description="Cursed aura around Living Armor boss, necrotic ghoul eye sockets",
        usage="Corrupt ethereal magic and abyssal boss aura",
    ),
}


# ==============================================================================
# Character Constants & Registry
# ==============================================================================

CHARACTER_ASH_BORNHATER = "ash_bornhater"
CHARACTER_KNIGHT_LUCAS = "knight_lucas"
CHARACTER_ARCHER_LILY = "archer_lily"

_ASH_PROFILE = CharacterProfile(
    character_id="ash_bornhater",
    name_en="Prince Ash Bornhater",
    name_ru="\u041f\u0440\u0438\u043d\u0446 \u042d\u0448 \u0411\u043e\u0440\u043d\u0445\u0435\u0439\u0442\u0435\u0440",
    title_en="36th Imperial Prince & Supreme Commander of Crossroads",
    title_ru="36-\u0439 \u0438\u043c\u043f\u0435\u0440\u0441\u043a\u0438\u0439 \u043f\u0440\u0438\u043d\u0446 \u0438 \u0432\u0435\u0440\u0445\u043e\u0432\u043d\u044b\u0439 \u043a\u043e\u043c\u0430\u043d\u0434\u0443\u044e\u0449\u0438\u0439 \u041f\u0435\u0440\u0435\u043a\u0440\u0451\u0441\u0442\u043a\u0430",
    role="Protagonist, Supreme Commander, Hell-Mode Transmigrator Strategist",
    archetype="Aristocratic Cold Strategist / Hell-Mode Survivor",
    physical_appearance=(
        "Tall lean athletic build (~182 cm), aristocratic posture tempered by combat readiness, "
        "pale skin, disheveled jet-black hair falling slightly over brow"
    ),
    facial_features=(
        "Sharp jawline, pronounced dark eye circles from chronic sleep deprivation, "
        "piercing cold dark eyes with calculating amber-gold glint, analytical unreadable expression"
    ),
    costume_and_armor=(
        "Battered charcoal-black officer greatcoat with faded gold embroidery and dark crimson lining, "
        "regal dark commander cloak, blackened iron gorget and pauldrons with faint eagle crest"
    ),
    weapons_and_artifacts=[
        "Polished dark steel tactical commander baton",
        "Lightweight duelist officer saber and rapier with wire-wrapped grip",
        "Oxidized silver signet ring with uncut obsidian imperial crest",
        "Pulsing azure mana dispatch crystal pendant",
    ],
    psychological_profile=(
        "Ruthless pragmatic outer facade to maintain garrison discipline, "
        "haunted by permadeath stakes and gaming trauma, geometric tactical deduction"
    ),
    master_visual_anchor=(
        "[Character: Prince Ash Bornhater, 36th Imperial Prince, lean athletic aristocratic build, "
        "disheveled jet-black hair falling over brow, sharp jawline, pale complexion with faint exhaustion "
        "shadows and dark eye circles, piercing cold dark eyes with sharp calculating amber-gold glint, "
        "battered charcoal-black officer greatcoat with faded gold embroidery and dark crimson lining, "
        "regal dark commander cloak, blackened iron gorget and pauldrons, silver-and-obsidian imperial signet ring, "
        "holding a polished tactical commander baton, cold resolute commanding expression, cinematic dark fantasy anime style]"
    ),
    phases={},
    key_tokens=[
        "disheveled black hair",
        "dark eye circles",
        "regal dark commander cloak",
        "commander baton",
        "amber-gold glint",
        "blackened iron gorget",
    ],
    visual_anchors=[
        "disheveled pitch-black hair",
        "dark eye circles from chronic sleep deprivation",
        "sharp aristocratic jawline",
        "piercing cold dark eyes with calculating amber-gold glint",
        "pale athletic aristocratic build",
    ],
    costume_tokens=[
        "regal dark commander cloak",
        "battered charcoal-black officer greatcoat with faded gold embroidery",
        "blackened iron gorget and pauldrons",
        "weathered crimson silk mantle lining",
        "dark tailored combat doublet",
    ],
    signature_gear=[
        "polished tactical commander baton",
        "lightweight duelist officer saber and rapier",
        "silver and obsidian imperial signet ring",
        "illuminated cyan dispatch crystal",
    ],
    personality_traits=[
        "unwavering calculating composure",
        "authoritative tactical commander",
        "ruthless pragmatic savior",
        "internal moral burden",
    ],
    voice_persona="voice_y0joebp3bwta",
    voice_style="grim authoritative Russian commander",
)

_LUCAS_PROFILE = CharacterProfile(
    character_id="knight_lucas",
    name_en="Knight Lucas",
    name_ru="\u0420\u044b\u0446\u0430\u0440\u044c \u041b\u0443\u043a\u0430\u0441",
    title_en="Commander of the Crossroads City Guard & Shield Vanguard",
    title_ru="\u041a\u043e\u043c\u0430\u043d\u0434\u0438\u0440 \u0433\u043e\u0440\u043e\u0434\u0441\u043a\u043e\u0439 \u0441\u0442\u0440\u0430\u0436\u0438 \u041f\u0435\u0440\u0435\u043a\u0440\u0451\u0441\u0442\u043a\u0430",
    role="Commander of the City Guard, Vanguard Defensive Tank",
    archetype="Immovable Shield Paragon / Veteran Knight",
    physical_appearance=(
        "Towering muscular powerhouse build standing nearly 2 meters tall (~192 cm), "
        "massive barrel chest, broad shoulders, immovable wall-like physical presence"
    ),
    facial_features=(
        "Weathered battle-scarred square face, short-cropped steel-gray hair, "
        "slate-gray resolute eyes, jagged monster claw scar across left cheek down to jawline"
    ),
    costume_and_armor=(
        "Heavy battle-worn blackened steel full plate armor and armour with deep dents and acid gouges, "
        "faded navy-blue tabard with faded fortress tower crest and lion crest heraldry"
    ),
    weapons_and_artifacts=[
        "Massive spiked iron tower shield and pavise with vertical claw furrows",
        "Heavy steel two-handed bastard sword and greatsword",
        "Battle-notched arming broadsword",
    ],
    psychological_profile=(
        "Absolute martial honor, unbreakable devotion to Prince Ash and Crossroads, "
        "unflinching willingness to become a living shield for the garrison"
    ),
    master_visual_anchor=(
        "[Character: Knight Lucas, Commander of the Guard, towering muscular shield knight, "
        "broad shoulders, weathered battle-scarred face, short steel-gray hair, slate-gray resolute eyes, "
        "claw scar across left cheek, heavy battle-worn blackened steel full plate armor with deep dents and gouges, "
        "faded navy tabard with faded tower crest and lion crest, massive spiked iron tower shield, "
        "heavy steel broadsword and two-handed bastard sword, steadfast heroic defensive stance, "
        "cinematic dark fantasy anime style]"
    ),
    phases={},
    key_tokens=[
        "muscular build",
        "heavy steel plate armour",
        "two-handed bastard sword",
        "lion crest",
        "spiked iron tower shield",
        "weathered battle-scarred",
    ],
    visual_anchors=[
        "towering muscular build standing nearly 2 meters tall",
        "weathered battle-scarred square face",
        "short-cropped steel-gray hair",
        "slate-gray resolute eyes",
        "jagged claw scar across left cheek",
    ],
    costume_tokens=[
        "heavy battle-worn blackened steel full plate armor and armour",
        "faded navy-blue linen tabard with lion crest and tower emblem",
        "articulated steel gauntlets and greaves",
        "gouged iron breastplate",
    ],
    signature_gear=[
        "massive iron-spiked tower shield and pavise",
        "heavy steel two-handed bastard sword and greatsword",
        "battle-notched broadsword",
    ],
    personality_traits=[
        "steadfast martial devotion",
        "unshakeable loyalty to Prince Ash",
        "protective vanguard guardian",
        "grim stoic courage",
    ],
    voice_persona="voice_y0joebp3bwta",
    voice_style="deep resonant loyal warrior",
)

_LILY_RECRUIT_PHASE = CharacterPhase(
    phase_id="recruit",
    name="Terrified Recruit",
    description="Overwhelmed inexperienced young archer during the initial monster wave breach",
    visual_anchor=(
        "[Character: Archer Lily recruit phase, petite agile teenage archer, delicate features, "
        "wide tearful hazel-green eyes filled with terror, pale trembling cheeks, messy ash-blonde hair braid, "
        "dark forest-green leather brigandine, hooded cowl draped over shoulders, trembling hands gripping a "
        "wooden composite bow, rain-soaked, fearful vulnerability, cinematic dark fantasy anime style]"
    ),
    emotional_state="Terrified, hyperventilating, struggling with combat panic",
    facial_expression="Wide dilated pupils, tear-streaked trembling cheeks, parted lips catching breath",
    stance_and_motion="Trembling hands gripping bow, retreating stance against parapet crenellations",
)

_LILY_SNIPER_PHASE = CharacterPhase(
    phase_id="sniper",
    name="Awakened Dead-Eye Sniper",
    description="Predatory hyper-focused sniper following Prince Ash's direct mental grounding",
    visual_anchor=(
        "[Character: Archer Lily awakened sniper phase, petite lithe sharpshooter, cold focused predator gaze, "
        "narrowed laser-precise hazel-amber eyes, razor-sharp jawline, dark green hooded cowl casting dramatic "
        "rim shadow over brow, steady draw of masterwork recurve horn bow, notched black steel bodkin arrow "
        "aimed directly at camera, deadly calm composure, cinematic dark fantasy anime style]"
    ),
    emotional_state="Predatory calm, lethal precision, total sensory lock on target core",
    facial_expression="Narrowed unwavering amber eyes, steady jawline, absolute stillness",
    stance_and_motion="Immovable anchored archery stance, taut war-bow draw, zero tremor",
)

_LILY_PROFILE = CharacterProfile(
    character_id="archer_lily",
    name_en="Archer Lily",
    name_ru="\u041b\u0443\u0447\u043d\u0438\u0446\u0430 \u041b\u0438\u043b\u0438",
    title_en="Scout Marksman & Precision Vanguard Sniper",
    title_ru="\u0421\u043d\u0430\u0439\u043f\u0435\u0440-\u0440\u0430\u0437\u0432\u0435\u0434\u0447\u0438\u043a \u0438 \u0441\u0442\u0440\u0435\u043b\u043e\u043a \u0430\u0432\u0430\u043d\u0433\u0430\u0440\u0434\u0430",
    role="Scout Sharpshooter, Long-Range Precision Marksman",
    archetype="Awakened Prodigy Sniper / Agile Scout",
    physical_appearance=(
        "Petite lithe agile frame (~162 cm), rapid traversal across crenellations, "
        "messy ash-blonde or light hazel hair tied in practical low braid resting over shoulder"
    ),
    facial_features=(
        "Delicate youthful facial features, expressive glowing amber eyes with hazel depths, "
        "intense predatory focus under mana concentration"
    ),
    costume_and_armor=(
        "Fitted forest-green and dark slate-gray reinforced leather brigandine with brass rivets, "
        "weatherproof forest-green hooded cowl draped over shoulders casting soft facial shadows, "
        "dark leather archery shooting bracers"
    ),
    weapons_and_artifacts=[
        "Masterwork custom recurve composite longbow of dark yew and horn",
        "Hardened leather quiver filled with black-fletched steel bodkin arrows",
        "Crimson alchemical whistling signaling arrows",
    ],
    psychological_profile=(
        "Transforms from a paralyzed conscript recruit into Crossroads' premier dead-eye sniper "
        "under Prince Ash's psychological awakening"
    ),
    master_visual_anchor=_LILY_SNIPER_PHASE.visual_anchor,
    phases={
        "recruit": _LILY_RECRUIT_PHASE,
        "sniper": _LILY_SNIPER_PHASE,
        "awakened_sniper": _LILY_SNIPER_PHASE,
    },
    key_tokens=[
        "hooded forest-green",
        "recurve war-bow",
        "amber eyes",
        "bodkin arrows",
        "leather brigandine",
        "composite bow",
    ],
    visual_anchors=[
        "slender agile scout perching on stone crenellations",
        "glowing amber eyes with hazel undertones",
        "messy ash-blonde braid resting over shoulder",
        "petite lithe agile frame",
    ],
    costume_tokens=[
        "hooded forest-green cowl draped over shoulders",
        "fitted dark forest-green leather brigandine with brass rivets",
        "dark leather archery bracers",
        "rain-soaked scout tunic",
    ],
    signature_gear=[
        "masterwork custom recurve composite war-bow",
        "hardened leather quiver with black-fletched steel bodkin arrows",
        "crimson alchemical whistling arrows",
    ],
    personality_traits=[
        "evolving from terrified recruit to laser-focused sniper",
        "deadly concentration under direct command",
        "poised marksman discipline",
    ],
    voice_persona="voice_y0joebp3bwta",
    voice_style="intense focused young marksman",
)

CHARACTERS: Dict[str, CharacterProfile] = {
    "ash_bornhater": _ASH_PROFILE,
    "knight_lucas": _LUCAS_PROFILE,
    "archer_lily": _LILY_PROFILE,
    # Short aliases for consumer convenience
    "ash": _ASH_PROFILE,
    "lucas": _LUCAS_PROFILE,
    "lily": _LILY_PROFILE,
}


# ==============================================================================
# Monster Bestiary Registry (First Wave & Stage 1 Boss)
# ==============================================================================

MONSTER_GARGOYLE = "black_scaled_gargoyle"
MONSTER_CHITINOUS_CRAWLER = "chitinous_crawler"
MONSTER_UNDEAD_GHOUL = "decayed_ghoul"
MONSTER_SIEGE_OGRE = "siege_ogre_vanguard"
BOSS_LIVING_ARMOR = "living_armor_vanguard"

_GARGOYLE_SPEC = MonsterSpec(
    species_id="black_scaled_gargoyle",
    name_en="Black-Scaled Gargoyle",
    name_ru="\u0427\u0435\u0440\u043d\u043e\u0447\u0435\u0448\u0443\u0439\u0447\u0430\u0442\u0430\u044f \u0433\u043e\u0440\u0433\u0443\u043b\u044c\u044f",
    tier="Tier 1 Aerial Swarm",
    category="Aerial Raider",
    threat_tier="Tier 1 Aerial Swarm",
    visual_anchors=[
        "swarming black-scaled gargoyles",
        "weathered porous gray basalt stone skin fused with sinewy muscle",
        "ragged bat wings with 4-meter wingspan",
        "sulfur-yellow slit eyes leaving faint motion trails",
        "obsidian razor talons capable of rending iron plate",
    ],
    behavior_tokens=[
        "terminal velocity dive bombing from dark storm clouds",
        "targeting high-elevation archers and officers on parapets",
        "razor claw rakes against iron battlements throwing sparks",
    ],
    threat_description="Bypasses rampart infantry to decapitate command personnel and scatter archers",
    master_visual_anchor=(
        "[Monster: Demonic Gargoyle aerial predator, weathered porous gray basalt stone skin fused with "
        "sinewy muscle, massive leathery ragged bat wings with clawed tips, glowing sulfur-yellow slit eyes, "
        "jagged stone fangs snarl, diving at high velocity from dark storm clouds over fortress ramparts, "
        "motion blur, menacing dark fantasy anime creature design]"
    ),
    key_tokens=[
        "swarming black-scaled gargoyles",
        "weathered porous gray basalt",
        "ragged bat wings",
        "sulfur-yellow slit eyes",
    ],
)

_CRAWLER_SPEC = MonsterSpec(
    species_id="chitinous_crawler",
    name_en="Chitinous Crawler",
    name_ru="\u0425\u0438\u0442\u0438\u043d\u043e\u0432\u044b\u0439 \u043f\u043e\u043b\u0437\u0443\u043d",
    tier="Tier 1 Subterranean & Wall Swarm",
    category="Wall-Breaching Arachnid Swarm",
    threat_tier="Tier 1 Subterranean & Wall Swarm",
    visual_anchors=[
        "chitinous multi-legged lurkers",
        "crimson bioluminescent eyes cluster",
        "iridescent oil-black carapace deflecting light arrows",
        "barbed scythe legs punching deep into stone masonry",
        "dripping acidic scissor mandibles",
    ],
    behavior_tokens=[
        "rapid vertical scaling of wet 90-degree stone walls",
        "swarming rampart crenellations from blind spots",
        "spitting caustic digestive acid eroding mortar",
    ],
    threat_description="Negates fortress height advantage by scuttling up outer walls at terrifying speed",
    master_visual_anchor=(
        "[Monster: Chitinous Crawler wall-scuttler, massive insectoid spider monstrosity, segmented "
        "iridescent oil-black carapace, eight elongated barbed scythe legs scaling vertical wet granite castle walls, "
        "cluster of glowing ruby compound eyes, dripping venomous mandibles, terrifying dark fantasy creature, "
        "macro cinematic tracking shot]"
    ),
    key_tokens=[
        "chitinous multi-legged lurkers",
        "crimson bioluminescent eyes",
        "iridescent oil-black carapace",
        "barbed scythe legs",
    ],
)

_GHOUL_SPEC = MonsterSpec(
    species_id="decayed_ghoul",
    name_en="Decayed Ghoul Shock Trooper",
    name_ru="\u0420\u0430\u0437\u043b\u043e\u0436\u0438\u0432\u0448\u0438\u0439\u0441\u044f \u0433\u0443\u043b\u044c",
    tier="Tier 1 Vanguard Attrition Horde",
    category="Undead Attrition Infantry",
    threat_tier="Tier 1 Vanguard Attrition Horde",
    visual_anchors=[
        "Undead Ghoul shock infantry",
        "rotting ash-gray flesh over jagged bones",
        "rusted iron chainmail and plate shards embedded in skin",
        "cyan witch-fire burning in hollow eye sockets",
        "charging horde with ravenous momentum",
    ],
    behavior_tokens=[
        "suicidal forward charge through kill-zone moats and stake traps",
        "forming corpse ramps against gates to allow swarming",
        "relentless advance ignoring lethal physical trauma",
    ],
    threat_description="Exhausts defensive ammunition and overwhelms barricades through endless meat-shield numbers",
    master_visual_anchor=(
        "[Monster Horde: Undead Ghoul shock infantry, grotesque decayed humanoid corpses, rotting ash-gray "
        "flesh over jagged bones, rusted iron armor shards embedded in skin, hollow eye sockets glowing with "
        "ghostly cyan witch-fire, rabid snarls, sprinting through burning mud and rain toward camera, "
        "dark fantasy anime horde]"
    ),
    key_tokens=[
        "Undead Ghoul shock infantry",
        "rotting ash-gray flesh",
        "cyan witch-fire",
        "charging horde",
    ],
)

_OGRE_SPEC = MonsterSpec(
    species_id="siege_ogre_vanguard",
    name_en="Siege Ogre Vanguard",
    name_ru="\u041e\u0441\u0430\u0434\u043d\u044b\u0439 \u043e\u0433\u0440 \u0430\u0432\u0430\u043d\u0433\u0430\u0440\u0434\u0430",
    tier="Tier 2 Vanguard Siege",
    category="Heavy Siege Juggernaut",
    threat_tier="Tier 2 Vanguard Siege",
    visual_anchors=[
        "towering 5-meter siege ogre with crude bone club and iron-plate armor",
        "hulking gray-skinned brute with thick scarred hide",
        "shackled iron chains and spiked leather harness",
        "yellow tusked underbite and bloodshot feral eyes",
    ],
    behavior_tokens=[
        "crushing battering impacts against fortress gates",
        "cleaving through barricade stakes and infantry ranks",
        "shaking masonry foundations with ground-pounding strikes",
    ],
    threat_description="Breaches outer reinforced gates and absorbs heavy ballista fire",
    master_visual_anchor=(
        "[Monster: Siege Ogre Vanguard, colossal 5-meter gray brute in crude iron-plate armor, "
        "dragging massive spiked bone club, battering fortress gates with catastrophic kinetic force, "
        "rain spraying off leathery hide, cinematic dark fantasy anime style]"
    ),
    key_tokens=[
        "towering 5-meter siege ogre",
        "crude bone club",
        "iron-plate armor",
        "battering fortress gates",
    ],
)

_LIVING_ARMOR_SPEC = MonsterSpec(
    species_id="living_armor_vanguard",
    name_en="Cursed Living Armor Vanguard",
    name_ru="\u041f\u0440\u043e\u043a\u043b\u044f\u0442\u044b\u0439 \u0436\u0438\u0432\u043e\u0439 \u0434\u043e\u0441\u043f\u0435\u0445",
    tier="Stage 1 Boss / Dread Colossus",
    category="Prologue / Stage 1 Boss",
    threat_tier="Stage 1 Boss / Dread Colossus",
    visual_anchors=[
        "Cursed Living Armor Vanguard",
        "blackened corrupted gothic plate armor",
        "glowing blood-red cursed flames bursting from helmet visor",
        "two-handed executioner greatsword dragging on stone sparking violently",
        "colossal 3.8-meter towering armored frame with spiked pauldrons",
    ],
    behavior_tokens=[
        "sweeping cleaves pulverizing stone ramparts and crushing shields",
        "impervious to standard physical arrows and non-enchanted steel",
        "exposing pulsing crimson soul-core during overhead attack recovery",
    ],
    threat_description=(
        "Annihilates entire defensive lines; requires Knight Lucas shield parry to stagger "
        "and Archer Lily precision enchanted bodkin shot into armpit seam"
    ),
    master_visual_anchor=(
        "[Boss: Cursed Living Armor Vanguard, colossal 3.8-meter towering suit of blackened corrupted "
        "gothic plate armor, spiked iron pauldrons, glowing blood-red cursed flames bursting from helmet visor "
        "and armor joints, dragging a massive jagged two-handed executioner greatsword sparking against wet stone, "
        "crushing presence, terrifying boss encounter, dramatic low-angle shot, cinematic dark fantasy anime style]"
    ),
    defeat_mechanic=(
        "Tactical Trinity: Lucas absorbs overhead cleave -> Ash identifies armpit joint seam -> "
        "Lily shoots enchanted bodkin arrow directly into the soul-core"
    ),
    key_tokens=[
        "Cursed Living Armor Vanguard",
        "blackened corrupted gothic plate armor",
        "glowing blood-red cursed flames",
        "two-handed executioner greatsword",
    ],
)

FIRST_WAVE_BESTIARY: Dict[str, MonsterSpec] = {
    "black_scaled_gargoyle": _GARGOYLE_SPEC,
    "chitinous_crawler": _CRAWLER_SPEC,
    "decayed_ghoul": _GHOUL_SPEC,
    "siege_ogre_vanguard": _OGRE_SPEC,
    "living_armor_vanguard": _LIVING_ARMOR_SPEC,
    # Aliases
    "gargoyle": _GARGOYLE_SPEC,
    "crawler": _CRAWLER_SPEC,
    "ghoul": _GHOUL_SPEC,
    "undead_ghoul": _GHOUL_SPEC,
    "siege_ogre": _OGRE_SPEC,
    "boss_living_armor": _LIVING_ARMOR_SPEC,
}


# ==============================================================================
# Environment Aesthetics (Crossroads Fortress)
# ==============================================================================

ENV_CROSSROADS_FORTRESS = "crossroads_fortress"

CROSSROADS_FORTRESS = EnvironmentSpec(
    setting_id="crossroads_fortress",
    name_en="Crossroads Fortress",
    name_ru="\u041a\u0440\u0435\u043f\u043e\u0441\u0442\u044c \u041f\u0435\u0440\u0435\u043a\u0440\u0451\u0441\u0442\u043e\u043a",
    setting_type="Dark Fantasy Frontier Fortress Citadel",
    architecture="Monolithic cyclopean dark granite and basalt bastion curtain walls",
    weather_and_atmosphere="Overcast tempest sky, driving torrential rain, roiling black fog in the distance",
    lighting_model="High-contrast chiaroscuro, flickering warm amber pitch torchlight, violet blood-moon rim",
    architecture_anchors=[
        "monolithic dark granite fortress ramparts",
        "30-meter high weathered wet stone walls",
        "cyclopean basalt citadel masonry",
        "heavy notched stone crenellations with iron arrow slits",
        "kill-zone moat pitted with explosion craters and charred stakes",
    ],
    atmosphere_anchors=[
        "overcast storm clouds churning under a blood-red moon",
        "driving torrential rain and rain-slick stone reflections",
        "roaring iron pitch braziers casting flickering warm amber torchlight",
        "creeping wall of unnatural roiling black fog in distant killing fields",
        "sparks and drifting black soot smoke caught in crosswinds",
    ],
    strategic_zones={
        "outer_moat": "Barren scorched kill-zone moat with deep stake pits and caltrops",
        "gatehouse": "Iron-reinforced cyclopean portcullis with murder holes and boiling pitch vats",
        "battlements": "Wide stone parapet walk accommodating heavy ballistas and archery squads",
        "commanders_spire": "Elevated central bastion stone platform commanding full tactical grid",
    },
    master_visual_anchor=(
        "[Environment: Fortress of Crossroads, monolithic dark granite fortress ramparts, "
        "30-meter high weathered wet stone walls, heavy notched crenellations, roaring iron pitch braziers "
        "casting flickering warm amber light, heavy torrential rain, rain-slick stone reflections, "
        "ominous black storm clouds swirling under a blood-red moon, creeping wall of unnatural roiling "
        "black fog in distant killing fields, dark fantasy grim atmosphere, cinematic photoreal anime aesthetic, "
        "wide establishing shot]"
    ),
    key_tokens=[
        "Crossroads",
        "black granite citadel",
        "granite fortress ramparts",
        "iron brazier",
        "kill-zone moat",
        "torrential rain",
        "creeping black fog",
        "blood-red moon",
    ],
)


# ==============================================================================
# Prompt Templates Catalog & API Functions
# ==============================================================================

PROMPT_TEMPLATES: Dict[str, PromptTemplate] = {
    "commander_establishing": PromptTemplate(
        template_id="commander_establishing",
        title="Commander Establishing on Bastion",
        scene_archetype="Command & Strategic Overview",
        camera_motion="slow push-in, steady locked camera",
        lighting_directive="volumetric lighting, flickering warm amber torchlight key, cyan mana rim",
        character_anchor=_ASH_PROFILE.master_visual_anchor,
        environment_anchor=CROSSROADS_FORTRESS.master_visual_anchor,
        action_directive="Prince Ash stands motionless at the stone parapet, holding commander baton and cyan dispatch crystal",
        composition_and_style="photoreal anime dark fantasy aesthetic, 8k resolution, cinematic composition",
    ),
    "vanguard_defense": PromptTemplate(
        template_id="vanguard_defense",
        title="Vanguard Shield Wall Defense",
        scene_archetype="Heroic Vanguard Combat",
        camera_motion="low-angle heroic dolly slide, heavy physical impact",
        lighting_directive="dramatic chiaroscuro, torch embers spraying, lightning flashes",
        character_anchor=_LUCAS_PROFILE.master_visual_anchor,
        environment_anchor=CROSSROADS_FORTRESS.master_visual_anchor,
        action_directive="Knight Lucas plants his iron-spiked tower shield into stone, absorbing violent diving monster impact",
        composition_and_style="visceral battlefield tension, photoreal anime dark fantasy style, 8k resolution",
    ),
    "sniper_awakening": PromptTemplate(
        template_id="sniper_awakening",
        title="Precision Sniper Climax Awakening",
        scene_archetype="Climax Sniper Shot",
        camera_motion="extreme macro tracking shot along arrow shaft, rack focus",
        lighting_directive="sharp edge contrast, azure mana glow on bodkin arrowhead, blood-red moon rim",
        character_anchor=_LILY_SNIPER_PHASE.visual_anchor,
        environment_anchor=CROSSROADS_FORTRESS.master_visual_anchor,
        action_directive="Archer Lily steadily draws her horn composite war-bow with taut lethal calm",
        composition_and_style="deadly precision, masterclass anime cinematography, 8k resolution",
    ),
    "swarm_surge": PromptTemplate(
        template_id="swarm_surge",
        title="Monster Swarm Surge & Rampart Breach",
        scene_archetype="Mass Siege Incursion",
        camera_motion="wide panoramic crane reveal from parapets down to the killing fields",
        lighting_directive="flashing orange pitch fire explosions against roiling black fog",
        character_anchor=_GHOUL_SPEC.master_visual_anchor,
        environment_anchor=CROSSROADS_FORTRESS.master_visual_anchor,
        action_directive="Hordes of undead sprint through burning stake moats while crawlers scale sheer vertical walls",
        composition_and_style="grimdark visceral siege warfare, fluid dynamic motion, photoreal anime aesthetic",
    ),
}


_LORE_BIBLE_SINGLETON: Optional[LoreBible] = None


def get_lore_bible() -> LoreBible:
    """Return the populated singleton LoreBible instance."""
    global _LORE_BIBLE_SINGLETON
    if _LORE_BIBLE_SINGLETON is None:
        _LORE_BIBLE_SINGLETON = LoreBible(
            series_title_en="Tyrant of the Tower Defense Game",
            series_title_ru="\u0422\u0438\u0440\u0430\u043d \u0432 \u043e\u0431\u043e\u0440\u043e\u043d\u0438\u0442\u0435\u043b\u044c\u043d\u043e\u0439 \u0438\u0433\u0440\u0435",
            world_setting=(
                "Southern frontier of the Everblack Empire: Fortress of Crossroads commanding "
                "the volcanic bluffs against the abyssal Black Fog."
            ),
            attrition_rules=[
                "Permanent death: no resurrection or reinforcement.",
                "Cumulative structural erosion of defenses.",
                "Psychological stress and morale attrition.",
            ],
            black_fog_mechanics=(
                "Supernatural miasma concealing infinite abyssal monster waves, "
                "churning before each stage deployment."
            ),
            commander_axioms=[
                "A commander must never show hesitation or fear.",
                "Every resource and soul is calculated for maximum defense efficiency.",
                "Look only at the target: the rest of the world does not exist.",
            ],
            characters=CHARACTERS,
            bestiary=FIRST_WAVE_BESTIARY,
            environments={ENV_CROSSROADS_FORTRESS: CROSSROADS_FORTRESS},
            color_palette=COLOR_PALETTE,
            prompt_templates=PROMPT_TEMPLATES,
            master_negative_prompt=TTD_MASTER_NEGATIVE_PROMPT,
        )
    return _LORE_BIBLE_SINGLETON


def get_character(character_id: str) -> CharacterProfile:
    """Lookup character profile by ID or alias."""
    cid = character_id.strip().lower()
    if cid in CHARACTERS:
        return CHARACTERS[cid]
    for key, prof in CHARACTERS.items():
        if cid in key or key in cid:
            return prof
    raise KeyError(f"Unknown character_id: {character_id}")


def get_character_anchor(character_id: str, phase: Optional[str] = None) -> str:
    """Retrieve the exact Veo 3.1 visual anchor prompt token for a character."""
    prof = get_character(character_id)
    return prof.get_anchor(phase)


def get_monster(monster_id: str) -> MonsterSpec:
    """Lookup monster profile by ID or alias."""
    mid = monster_id.strip().lower()
    if mid in FIRST_WAVE_BESTIARY:
        return FIRST_WAVE_BESTIARY[mid]
    for key, spec in FIRST_WAVE_BESTIARY.items():
        if mid in key or key in mid:
            return spec
    raise KeyError(f"Unknown monster_id: {monster_id}")


def get_monster_anchor(monster_id: str) -> str:
    """Retrieve the exact Veo 3.1 visual anchor prompt token for a monster/boss."""
    spec = get_monster(monster_id)
    return spec.master_visual_anchor or ("; ".join(spec.visual_anchors))


def get_environment(env_id: str = "crossroads_fortress") -> EnvironmentSpec:
    """Lookup environment profile by ID."""
    eid = env_id.strip().lower()
    if eid in STAGE0_ENVIRONMENTS:
        return STAGE0_ENVIRONMENTS[eid]
    return CROSSROADS_FORTRESS


def get_environment_anchor(env_id: str = "crossroads_fortress") -> str:
    """Retrieve the exact visual anchor prompt token for Crossroads Fortress or Forward Base."""
    return get_environment(env_id).master_visual_anchor


def get_color_palette() -> Dict[str, ColorToken]:
    """Return all semantic color tokens."""
    return dict(COLOR_PALETTE)


def get_color_token(token_name: str) -> ColorToken:
    """Lookup color token by name or snake_case key."""
    norm = token_name.strip().lower().replace(" ", "_")
    if norm in COLOR_PALETTE:
        return COLOR_PALETTE[norm]
    for tok in COLOR_PALETTE.values():
        if tok.name.lower() == token_name.strip().lower():
            return tok
    raise KeyError(f"Unknown color token: {token_name}")


def get_master_negative_prompt() -> str:
    """Return the master negative prompt string for Veo 3.1 / Omni 1.1 Flash generation."""
    return TTD_MASTER_NEGATIVE_PROMPT


def build_veo_scene_prompt(
    camera_motion: str,
    action: str,
    characters: Optional[List[str]] = None,
    character_phases: Optional[Dict[str, str]] = None,
    monsters: Optional[List[str]] = None,
    environment: str = "crossroads_fortress",
    lighting: Optional[str] = None,
    style_suffix: Optional[str] = None,
    scene_title: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """
    Construct a complete multi-layer scene prompt combining camera motion,
    environmental anchors, character anchors, monster anchors, physical action,
    lighting, and dark fantasy anime style directives.
    """
    cam = camera_motion.strip().rstrip(".")
    env_anchor = get_environment_anchor(environment)
    char_tokens: List[str] = []
    if characters:
        phases = character_phases or {}
        for c in characters:
            ph = phases.get(c)
            char_tokens.append(get_character_anchor(c, ph))

    monster_tokens: List[str] = []
    if monsters:
        for m in monsters:
            monster_tokens.append(get_monster_anchor(m))

    parts = [f"In a single continuous unbroken cinematic shot, {cam}."]
    parts.append(env_anchor)
    if char_tokens:
        parts.extend(char_tokens)
    if monster_tokens:
        parts.extend(monster_tokens)
    parts.append(action.strip().rstrip(".") + ".")
    if lighting:
        parts.append(lighting.strip().rstrip(".") + ",")
    style = (
        style_suffix
        or "cinematic dark fantasy anime style, 8k resolution, volumetric lighting, photoreal anime aesthetic"
    )
    parts.append(style.strip().rstrip(".") + ".")
    return " ".join(parts)


# Alias ensuring compatibility with unified TTD prompt generation contract
build_ttd_scene_prompt = build_veo_scene_prompt


# ==============================================================================
# Stage 0 Canonical Profiles (Prologue + Chapters 001-010 Ranobe / Manhwa Ep 1-2)
# ==============================================================================

CHARACTER_ASH_STAGE0 = "ash_stage0"
CHARACTER_LUCAS_STAGE0 = "lucas_stage0"
CHARACTER_MAGE_LILY = "mage_lily"
CHARACTER_HEALER_DAMIEN = "healer_damien"
CHARACTER_SHIELD_KEN = "shield_knight_ken"
CHARACTER_DIRECTOR_EIDER = "director_eider"

_ASH_STAGE0_PROFILE = CharacterProfile(
    character_id="ash_stage0",
    name_en="3rd Imperial Prince Ash 'Born Hater' Everblack",
    name_ru="3-\u0439 \u0438\u043c\u043f\u0435\u0440\u0441\u043a\u0438\u0439 \u043f\u0440\u0438\u043d\u0446 \u042d\u0448 \u042d\u0432\u0435\u0440\u0431\u043b\u044d\u043a",
    title_en="3rd Imperial Prince (EX-Rank Beginner Commander)",
    title_ru="3-\u0439 \u0438\u043c\u043f\u0435\u0440\u0441\u043a\u0438\u0439 \u043f\u0440\u0438\u043d\u0446 (\u041d\u0430\u0447\u0438\u043d\u0430\u044e\u0449\u0438\u0439 \u043a\u043e\u043c\u0430\u043d\u0434\u0438\u0440 EX-\u0440\u0430\u043d\u0433\u0430)",
    role="Protagonist, EX-Rank Beginner Commander -> Tyrant of the Battlefield",
    archetype="Hell-Mode Streamer Transmigrated into 23-Year-Old 3rd Prince",
    physical_appearance=(
        "23-year-old lean aristocratic commander, disheveled jet-black hair, pale skin with insomnia shadows, "
        "sharp amber-gold eyes"
    ),
    facial_features="Sharp aristocratic jawline, dark eye circles, piercing amber-gold irises",
    costume_and_armor="Black-and-gold Imperial Commander uniform with crimson cape and blackened iron gorget",
    weapons_and_artifacts=[
        "Commander saber and dagger (used to test Lily's Flame Skin)",
        "Tactical map of the Forward Base (Trait: Map Making)",
    ],
    psychological_profile=(
        "Unbroken gamer resolve; awakens Passive Skill [Indomitable Commander] in Stage 0 to grant 10m mental "
        "status immunity and snap Damien out of despair after Ken's death"
    ),
    master_visual_anchor=(
        "[Character: 3rd Imperial Prince Ash Everblack, age 23, EX-Rank Beginner Commander, disheveled jet-black hair, "
        "sharp amber-gold irises, black-and-gold Imperial Commander uniform with crimson cape, holding tactical dagger "
        "and saber, Fortiche Arcane 2.5D painterly style]"
    ),
    key_tokens=[
        "3rd Imperial Prince",
        "EX-Rank",
        "Map Making",
        "Evil Eye of Command",
        "Indomitable Commander",
    ],
    voice_persona="Alnilam",
    voice_style="authoritative young male commander",
)

_LUCAS_STAGE0_PROFILE = CharacterProfile(
    character_id="lucas_stage0",
    name_en="Knight Lucas MacGregor (Stage 0)",
    name_ru="\u0420\u044b\u0446\u0430\u0440\u044c \u041b\u0443\u043a\u0430\u0441 \u041c\u0430\u043a\u0433\u0440\u0435\u0433\u043e\u0440",
    title_en="3rd Prince's Bodyguard Knight (SSR-Rank Intermediate Knight)",
    title_ru="\u0420\u044b\u0446\u0430\u0440\u044c-\u0442\u0435\u043b\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u0435\u043b\u044c 3-\u0433\u043e \u043f\u0440\u0438\u043d\u0446\u0430 (SSR-\u0440\u0430\u043d\u0433)",
    role="SSR-Rank Vanguard Bodyguard Knight, Sole Survivor of Stage 50 Cathedral",
    archetype="Loyal Vanguard Knight Warned by Original Ash the Night Before",
    physical_appearance="22-year-old towering muscular knight, dirty-blonde hair, weathered bronze-tan skin",
    facial_features="Left cheek claw scar, natural steel-gray irises",
    costume_and_armor="Silver-and-dark-steel full plate armor with white-and-blue knight cape",
    weapons_and_artifacts=["Heavy steel broadsword", "Spiked iron tower shield"],
    psychological_profile=(
        "Unquestioning loyalty to Prince Ash because the original Ash warned him the night before possession: "
        "'Starting tomorrow I will act like a completely different person, but do not doubt me and continue to assist me'"
    ),
    master_visual_anchor=(
        "[Character: SSR-Rank Knight Lucas MacGregor, age 22, dirty-blonde hair, weathered bronze-tan skin, "
        "left cheek claw scar, natural steel-gray irises, silver-and-dark-steel plate armor with white-and-blue cape, "
        "wielding broadsword, Fortiche Arcane 2.5D painterly style]"
    ),
    key_tokens=["SSR-Rank", "Beastification", "dirty-blonde", "warned the night before"],
    voice_persona="Orus",
    voice_style="deep resonant loyal knight",
)

_MAGE_LILY_PROFILE = CharacterProfile(
    character_id="mage_lily",
    name_en="Fire Mage Lily",
    name_ru="\u041c\u0430\u0433 \u043e\u0433\u043d\u044f \u041b\u0438\u043b\u0438",
    title_en="Guard Party Fire Attack Mage (R-Rank, Trait: Flame Skin)",
    title_ru="\u041c\u0430\u0433 \u043e\u0433\u043d\u044f \u043e\u0442\u0440\u044f\u0434\u0430 \u0441\u0442\u0440\u0430\u0436\u0438 (R-\u0440\u0430\u043d\u0433, \u041e\u0433\u043d\u0435\u043d\u043d\u0430\u044f \u043a\u043e\u0436\u0430)",
    role="R-Rank Fire Mage & Central Battery Entrance Tank",
    archetype="Inverted-Trait Melee Mage Tank",
    physical_appearance="Young red-haired fire mage in white tunic, brown leather corset vest, and red hooded cloak",
    facial_features="Fierce amber-red eyes, defiant expression",
    costume_and_armor="White mage tunic, brown leather corset vest, red hooded cloak",
    weapons_and_artifacts=["Basic ember spell", "Trait: Flame Skin (turns body into flame to evade blades, consumes MP)"],
    psychological_profile=(
        "Possesses [Flame Skin] born from extreme childhood terror of blades after goblins killed her parents; "
        "turns her body into flame to evade physical attacks at the cost of MP per evasion. Blocks the sole narrow "
        "entrance to the central cannon battery until her MP hits 0, suffering permanent lower-body paralysis"
    ),
    master_visual_anchor=(
        "[Character: R-Rank Fire Mage Lily, red hair, white tunic, brown leather corset vest, red hooded cloak, "
        "body wreathed in fiery golden-red Flame Skin aura evading blade strikes at the cost of MP, "
        "Fortiche Arcane 2.5D painterly style]"
    ),
    key_tokens=[
        "R-Rank",
        "Fire Mage",
        "Flame Skin",
        "terror of blades",
        "consumes MP",
        "lower-body paralysis",
    ],
    voice_persona="Aoede",
    voice_style="fiery defiant young female mage",
)

_HEALER_DAMIEN_PROFILE = CharacterProfile(
    character_id="healer_damien",
    name_en="Healer Priest Damien",
    name_ru="\u0416\u0440\u0435\u0446-\u0446\u0435\u043b\u0438\u0442\u0435\u043b\u044c \u0414\u044d\u043c\u0438\u0435\u043d",
    title_en="Guard Party Intermediate Healer & Ancient Mana Cannon Gunner (N-Rank)",
    title_ru="\u0426\u0435\u043b\u0438\u0442\u0435\u043b\u044c \u0438 \u043d\u0430\u0432\u043e\u0434\u0447\u0438\u043a \u0414\u0440\u0435\u0432\u043d\u0435\u0439 \u041c\u0430\u043d\u0430-\u041f\u0443\u0448\u043a\u0438 (N-\u0440\u0430\u043d\u0433)",
    role="N-Rank Healer Priest & God-Tier Artillery Sniper",
    archetype="Timid Priest with Clairvoyance / All-Seeing Eye (+50 Vision, +999 Accuracy)",
    physical_appearance="18-year-old slender priest with tousled brown hair, thick round spectacles, black-and-gold cassock",
    facial_features="Gentle eyes behind thick spectacles that ignite with golden sniper rings and bleed tears when strained",
    costume_and_armor="Black-and-gold priest cassock and white stole",
    weapons_and_artifacts=[
        "Artifact: Ancient Mana Cannon (SR)",
        "Trait: Clairvoyance / All-Seeing Eye (Vision Range +50, Accuracy Score +999)",
        "Skills: Light of Healing, Light of Detoxification",
    ],
    psychological_profile=(
        "Close friend of Shield Knight Ken; falls into panic and despair when Ken dies outside the walls, "
        "then recovers when Ash provokes him and awakens [Indomitable Commander], firing the fatal 2nd shot "
        "that kills Black Spider Queen Orlop"
    ),
    master_visual_anchor=(
        "[Character: N-Rank Healer Priest Damien, age 18, tousled brown hair, removing thick round spectacles, "
        "black-and-gold priest cassock, pupils glowing with golden All-Seeing Eye sniper reticle shedding bloody tears, "
        "aiming the ornate white-and-gold SR Ancient Mana Cannon, Fortiche Arcane 2.5D painterly style]"
    ),
    key_tokens=[
        "N-Rank",
        "All-Seeing Eye",
        "Accuracy +999",
        "Ancient Mana Cannon (SR)",
        "second shot kills Queen Orlop",
    ],
    voice_persona="Fenrir",
    voice_style="earnest young male priest",
)

_SHIELD_KEN_PROFILE = CharacterProfile(
    character_id="shield_knight_ken",
    name_en="Shield Knight Ken",
    name_ru="\u0429\u0438\u0442\u043e\u043d\u043e\u0441\u0435\u0446 \u041a\u0435\u043d",
    title_en="Guard Party Shield Knight & Decoy Runner (N-Rank)",
    title_ru="\u0429\u0438\u0442\u043e\u043d\u043e\u0441\u0435\u0446 \u043e\u0442\u0440\u044f\u0434\u0430 \u0441\u0442\u0440\u0430\u0436\u0438 (N-\u0440\u0430\u043d\u0433)",
    role="N-Rank Shield Knight, Former Petty Thief, Damien's Friend",
    archetype="Self-Sacrificing Family Man & Stealth Aggro Decoy",
    physical_appearance="Scarred veteran shield-fighter in dark iron half-plate armor carrying a family locket",
    facial_features="Grim determined expression, rugged stubble, protective gaze",
    costume_and_armor="Weathered dark iron shield-knight armor with silver family locket of wife and child",
    weapons_and_artifacts=[
        "Iron kite shield and short sword",
        "Silver family locket with portrait of wife and child",
        "Trait: A Petty Thief's Way of Survival (consumes own HP to erase presence and drop enemy aggro)",
    ],
    psychological_profile=(
        "Former petty thief who became a knight for his family and befriended Damien; sorties alone outside the "
        "Forward Base to draw the Black Spider swarm away from the cannon battery, loses too much HP to activate "
        "his stealth trait, and dies heroically in action"
    ),
    master_visual_anchor=(
        "[Character: N-Rank Shield Knight Ken, rugged scarred fighter in dark iron half-plate armor holding iron shield "
        "and bloodstained silver family locket, drawing the Black Spider swarm outside the fortress walls, "
        "Fortiche Arcane 2.5D painterly style]"
    ),
    key_tokens=[
        "N-Rank",
        "A Petty Thief's Way of Survival",
        "consumes HP",
        "family locket",
        "dies in action outside walls",
    ],
    voice_persona="Charon",
    voice_style="gritty seasoned male shield knight",
)

_DIRECTOR_EIDER_PROFILE = CharacterProfile(
    character_id="director_eider",
    name_en="Aider (Eider)",
    name_ru="\u042d\u0439\u0434\u0435\u0440",
    title_en="Game Director & Administrative Aide of Crossroads",
    title_ru="\u0420\u0430\u0441\u043f\u043e\u0440\u044f\u0434\u0438\u0442\u0435\u043b\u044c \u0438\u0433\u0440\u044b \u0438 \u043f\u043e\u043c\u043e\u0449\u043d\u0438\u043a \u0432 \u041f\u0435\u0440\u0435\u043a\u0440\u0451\u0441\u0442\u043a\u0435",
    role="System Game Director & Prince Ash's Administrative Aide",
    archetype="Enigmatic Smiling Administrator",
    physical_appearance="Slender bespectacled administrator in immaculate dark tailored vest and coat",
    facial_features="Polite inscrutable smile, sharp eyes behind thin spectacles",
    costume_and_armor="Formal dark administrative attire of Crossroads",
    weapons_and_artifacts=["System survey ledger and Crossroads administrative seal"],
    psychological_profile="Pulls the streamer into Stage 0 after the Stage 50 clear survey and greets the 9 survivors at Crossroads",
    master_visual_anchor=(
        "[Character: Director Eider, slender administrator in formal dark coat and spectacles with an enigmatic polite smile, "
        "Fortiche Arcane 2.5D painterly style]"
    ),
    key_tokens=["Game Director", "Crossroads Aide", "Stage 50 survey"],
    voice_persona="Puck",
    voice_style="enigmatic polite male administrator",
)

STAGE0_CHARACTERS: Dict[str, CharacterProfile] = {
    "ash_stage0": _ASH_STAGE0_PROFILE,
    "lucas_stage0": _LUCAS_STAGE0_PROFILE,
    "mage_lily": _MAGE_LILY_PROFILE,
    "healer_damien": _HEALER_DAMIEN_PROFILE,
    "shield_knight_ken": _SHIELD_KEN_PROFILE,
    "director_eider": _DIRECTOR_EIDER_PROFILE,
    "damien": _HEALER_DAMIEN_PROFILE,
    "ken": _SHIELD_KEN_PROFILE,
    "eider": _DIRECTOR_EIDER_PROFILE,
}
CHARACTERS.update(STAGE0_CHARACTERS)

BOSS_BLACK_SPIDER_QUEEN_ORLOP = "black_spider_queen_orlop"
MONSTER_BLACK_SPIDER_SIEGE = "black_spider_siege"
MONSTER_BLACK_SPIDER_ASSAULT = "black_spider_assault"

_ORLOP_SPEC = MonsterSpec(
    species_id="black_spider_queen_orlop",
    name_en="Black Spider Queen Orlop (Lv.??)",
    name_ru="\u0427\u0451\u0440\u043d\u0430\u044f \u041f\u0430\u0443\u0447\u044c\u044f \u041a\u043e\u0440\u043e\u043b\u0435\u0432\u0430 \u041e\u0440\u043b\u043e\u043f",
    tier="Stage 0 Boss / Nightmare Legion Commander Rank 6",
    category="Stage 0 Arachnid Commander Boss",
    threat_tier="Lv.?? Nightmare Legion Commander Rank 6",
    visual_anchors=[
        "colossal Black Spider Queen Orlop towering over the distant forest nest",
        "obsidian chitin carapace with glowing crimson eye cluster and emerald acid sacs",
    ],
    behavior_tokens=[
        "commands 196 Lv.60 Black Spider Siege Soldiers and 912 Lv.55 Assault Soldiers (1,109 total)",
        "obliterated on the second shot of the SR Ancient Mana Cannon guided by Damien's All-Seeing Eye",
    ],
    threat_description="Commands the 1,109-strong Black Spider army besieging the Forward Base; drops her Mana Core upon death",
    master_visual_anchor=(
        "[Boss: Lv.?? Black Spider Queen Orlop, Nightmare Legion Commander Rank 6, colossal arachnid matriarch "
        "with jagged obsidian carapace, glowing crimson eyes, and glowing emerald venom sacs in the distant forest nest, "
        "Fortiche Arcane 2.5D dark fantasy style]"
    ),
    defeat_mechanic=(
        "Ken draws swarm outside walls -> Lily tanks battery entrance until MP=0 -> Ash awakens Indomitable Commander "
        "to cure Damien's despair -> Damien lands fatal 2nd shot with SR Ancient Mana Cannon"
    ),
    key_tokens=["Black Spider Queen Orlop", "Lv.??", "Nightmare Legion Commander Rank 6", "Mana Core"],
)

_SPIDER_SIEGE_SPEC = MonsterSpec(
    species_id="black_spider_siege",
    name_en="Black Spider Siege Soldier (Lv.60)",
    name_ru="\u041e\u0441\u0430\u0434\u043d\u044b\u0439 \u0447\u0451\u0440\u043d\u044b\u0439 \u043f\u0430\u0443\u043a (Lv.60)",
    tier="Lv.60 Siege Arachnid Artillery (196 units)",
    category="Long-Range Acid Artillery Swarm",
    threat_tier="Lv.60 Siege Arachnid",
    visual_anchors=["bloated emerald-green acid abdomen", "parabolic green acid artillery projectiles melting stone"],
    behavior_tokens=["196 siege spiders bombarding Forward Base ramparts with corrosive green acid"],
    threat_description="Melts Forward Base battlements with long-range green acid artillery",
    master_visual_anchor=(
        "[Monster: Lv.60 Black Spider Siege Soldier, heavy chitinous arachnid with glowing emerald acid abdomen "
        "launching corrosive green artillery shells, Fortiche Arcane 2.5D style]"
    ),
    key_tokens=["Lv.60", "196 units", "green acid artillery"],
)

_SPIDER_ASSAULT_SPEC = MonsterSpec(
    species_id="black_spider_assault",
    name_en="Black Spider Assault Soldier (Lv.55)",
    name_ru="\u0428\u0442\u0443\u0440\u043c\u043e\u0432\u043e\u0439 \u0447\u0451\u0440\u043d\u044b\u0439 \u043f\u0430\u0443\u043a (Lv.55)",
    tier="Lv.55 Assault Arachnid Swarm (912 units)",
    category="Wall-Scaling Melee Swarm",
    threat_tier="Lv.55 Assault Arachnid",
    visual_anchors=["razor scythe legs", "clustered red eyes", "venomous mandibles"],
    behavior_tokens=["912 assault spiders scaling the Forward Base walls and dropping mana stones when slain"],
    threat_description="Overwhelms the 200-man garrison through sheer numbers until only 9 survivors remain",
    master_visual_anchor=(
        "[Monster: Lv.55 Black Spider Assault Soldier, fast chitinous spider with red eyes and razor mandibles "
        "scaling burning stone walls, Fortiche Arcane 2.5D style]"
    ),
    key_tokens=["Lv.55", "912 units", "mana stones"],
)

STAGE0_BESTIARY: Dict[str, MonsterSpec] = {
    "black_spider_queen_orlop": _ORLOP_SPEC,
    "orlop": _ORLOP_SPEC,
    "black_spider_siege": _SPIDER_SIEGE_SPEC,
    "black_spider_assault": _SPIDER_ASSAULT_SPEC,
}
FIRST_WAVE_BESTIARY.update(STAGE0_BESTIARY)

ENV_FORWARD_BASE = "forward_base"
FORWARD_BASE_OUTPOST = EnvironmentSpec(
    setting_id="forward_base",
    name_en="Forward Base Outpost (Stage 0 Tutorial)",
    name_ru="\u041f\u0435\u0440\u0435\u0434\u043e\u0432\u043e\u0439 \u0424\u043e\u0440\u0442 (\u042d\u0442\u0430\u043f 0)",
    setting_type="Besieged Northern Frontier Outpost Before Crossroads",
    architecture="Scorched stone ramparts dissolved by green spider acid, stone command bunker, central SR Ancient Mana Cannon battery with a single narrow entrance",
    weather_and_atmosphere="Night siege transitioning to fiery dawn on March 1st, emerald acid smoke and burning braziers",
    lighting_model="Fortiche Arcane high-contrast chiaroscuro with emerald acid explosions, golden Flame Skin fire, and cyan Mana Cannon beam",
    architecture_anchors=[
        "acid-corroded stone battlements of the Forward Base",
        "torchlit stone command bunker with tactical map table",
        "central artillery bastion housing the ornate white-and-gold SR Ancient Mana Cannon with a single narrow doorway",
    ],
    atmosphere_anchors=[
        "emerald-green corrosive acid artillery shells bursting against stone",
        "1,109 Black Spiders swarming from the northern forest mist",
        "battlefield littered with glowing mana stones after Queen Orlop's death",
    ],
    strategic_zones={
        "outer_wall": "Held by SSR-Rank Lucas MacGregor and the remnants of the 200-man garrison",
        "outer_field": "Kill-zone where N-Rank Shield Knight Ken draws aggro and falls in action",
        "battery_corridor": "Single narrow entrance to the cannon battery blocked by R-Rank Lily with Flame Skin until MP=0",
        "cannon_bastion": "Central platform where N-Rank Damien fires the SR Ancient Mana Cannon under Ash's Indomitable Commander aura",
    },
    master_visual_anchor=(
        "[Environment: Forward Base Outpost in Stage 0, acid-scorched stone ramparts, torchlit command bunker, "
        "and central bastion with the ornate white-and-gold SR Ancient Mana Cannon, Fortiche Arcane 2.5D style]"
    ),
    key_tokens=["Forward Base", "Stage 0", "Ancient Mana Cannon", "9 survivors", "mana stones"],
)

STAGE0_ENVIRONMENTS: Dict[str, EnvironmentSpec] = {
    "forward_base": FORWARD_BASE_OUTPOST,
    "crossroads_fortress": CROSSROADS_FORTRESS,
}

get_character_profile = get_character
get_monster_profile = get_monster
get_environment_profile = get_environment

