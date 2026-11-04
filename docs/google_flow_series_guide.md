# Google Flow Series Production Manual & Scene Builder Technical Guide

**Version**: 1.0.0 (Production Release)  
**Target Environment**: Google Flow (`flow.google.com` / `labs.google/fx/tools/flow`)  
**Core Video Engine**: Google Veo 3.1 (`veo_3_1_extension_lite`, `veo_3_1_t2v_fast_audio`, `veo-quality`)  
**Target Project**: `https://flow.google.com/project/7d9a2a67-9cd2-4a79-932e-717d2e29257f`  
**Reference Benchmark**: *Tyrant of the Tower Defense Game* (Manga Frames 001–026, Arcane Painterly Aesthetic)  

---

## Executive Summary

Producing an episodic, multi-scene animated series with generative diffusion models presents a fundamental challenge: **latent detail drift**. When relying purely on stochastic text prompts, each generated clip re-samples facial features, costume embroidery, color palettes, and environmental geometry from generic distribution latents. Across a continuous sequence, characters suffer identity collapse, costumes mutate, and architectural layouts warp.

Google Flow provides an industrial-grade solution to this problem through a structured, multi-tier consistency architecture:
1. **Durable Identity Anchoring**: Character Entities (`referenceEntities`) binding a Slot 0 Face portrait and a Slot 1 3-view body turnaround triptych into a persistent UUID, invokable via inline `@Name` prompt mentions.
2. **Prop & Environmental Consistency**: Ingredients Mode (`referenceImages`), binding visual assets, tactical UI screens, and room layouts to generation latent seeds without polluting character identity latents.
3. **Temporal Kinetic Continuity**: Scene Builder Video Continuation (`>> Режим продолжения (Veo 3.1 - Lite)` / `veo_3_1_extension_lite`), which seeds successive 8-second clips from the trailing 24 frames (1.0 second @ 24 fps) of the preceding clip.
4. **Continuation Prompt Grammar**: Delta-oriented prompt engineering through the video editing prompt bar (`flow-edit-video-prompt-box .ProseMirror`), steering camera momentum and scene transitions while preserving reference sheet immutability.

This manual documents the comprehensive technical architecture, wire API protocol, DOM selectors, UI interaction recipes, and seam mitigation workflows required for professional animated series production in Google Flow.

---

## Table of Contents
1. [Google Flow Series Production Architecture](#1-google-flow-series-production-architecture)
2. [Character Entities & Reference Sheets (Slot 0 & Slot 1 Architecture)](#2-character-entities--reference-sheets-slot-0--slot-1-architecture)
3. [Ingredients Mode (`referenceImages`) & Asset Binding](#3-ingredients-mode-referenceimages--asset-binding)
4. [Scene Builder Video Continuation Mode (`Veo 3.1 - Lite`)](#4-scene-builder-video-continuation-mode-veo-31---lite)
5. [Prompt Bar Editing Grammar & Delta Directives](#5-prompt-bar-editing-grammar--delta-directives)
6. [Step-by-Step UI Guide for Project `7d9a2a67-9cd2-4a79-932e-717d2e29257f`](#6-step-by-step-ui-guide-for-project-7d9a2a67-9cd2-4a79-932e-717d2e29257f)
7. [Seam Handling & Multi-Scene Transition Protocol](#7-seam-handling--multi-scene-transition-protocol)
8. [Automated Telemetry, Quality Control & Verification](#8-automated-telemetry-quality-control--verification)

---

## 1. Google Flow Series Production Architecture

### 1.1 The Nature of Latent Detail Drift
In traditional diffusion-based text-to-video (T2V), every prompt dispatch:
$$\mathcal{Z}_0 \sim \mathcal{N}(0, \mathbf{I})$$
initializes from white Gaussian noise. Even when prompts share 95% of identical descriptor tokens (e.g., *"young gamer in dark oversized hoodie with headphones"*), the sampler converges to distinct local minima. This yields noticeable discrepancies:
- **Facial Topology**: Shifting bone structure, eye shape, and age.
- **Costume Permutations**: Shifting zipper placement, cord thickness, and sleeve silhouettes.
- **Lighting Discontinuities**: Key light angles flipping between cuts.

### 1.2 Two-Tier Consistency Solution
To establish broadcast-quality episodic consistency, Google Flow decouples **identity invariants** from **kinetic dynamics**:

```
+---------------------------------------------------------------------------------+
|                                Google Flow Project                              |
|                                                                                 |
|   +--------------------------+               +------------------------------+   |
|   |    Character Entities    |               |      Ingredients / Assets    |   |
|   |   (Slot 0 Face Anchor)   |               |   (Prop / Map / Environment) |   |
|   |  (Slot 1 Body Turnaround)|               |   referenceImages: [...]     |   |
|   |  referenceEntities: [...]|               +--------------+---------------+   |
|   +-------------+------------+                              |                   |
|                 |                                           |                   |
|                 +---------------------+---------------------+                   |
|                                       |                                         |
|                                       v                                         |
|                       +-------------------------------+                         |
|                       |  Initial Clip Generation      |                         |
|                       |  (Veo 3.1 Quality / Fast)     |                         |
|                       +---------------+---------------+                         |
|                                       |                                         |
|                                       v                                         |
|               +-----------------------------------------------+                 |
|               | Flow Scene Builder Timeline                   |                 |
|               |  [Clip 1: Streamer Battlestation (0-8s)]       |                 |
|               +-----------------------+-----------------------+                 |
|                                       |                                         |
|                        Trailing 24 frames (1.0s seed)                           |
|                                       |                                         |
|                                       v                                         |
|               +-----------------------------------------------+                 |
|               | >> Режим продолжения (Veo 3.1 - Lite)          |                 |
|               |  [Clip 2: Monitor Immersion (8-16s)]          |                 |
|               +-----------------------+-----------------------+                 |
|                                       |                                         |
|                        Trailing 24 frames (1.0s seed)                           |
|                                       |                                         |
|                                       v                                         |
|               +-----------------------------------------------+                 |
|               | >> Режим продолжения (Veo 3.1 - Lite)          |                 |
|               |  [Clip 3: Knight Lucas Rampart (16-24s)]      |                 |
|               +-----------------------------------------------+                 |
+---------------------------------------------------------------------------------+
```

### 1.3 Flow Timeline & Scene Builder Concepts
The Flow Scene Builder organizes multi-shot narratives into a contiguous timeline:
- **Clip**: An individual 8-second video asset generated via T2V, R2V, I2V, or Extension.
- **Scene**: A logical narrative container holding one or more sequentially linked clips.
- **Add-Clip Control**: A context-sensitive timeline trigger (`button.add-clip-button`) allowing creators to append new shots or invoke continuation mode directly off the previous shot's trailing frame buffer.

## 2. Character Entities & Reference Sheets (Slot 0 & Slot 1 Architecture)

### 2.1 Domain Model & Wire Representation
A Character in Google Flow is a project-scoped entity (`entityType = "CHARACTER"`). Unlike basic image uploads, a Character binds visual identity across multiple orthogonal camera projections and links voice/personality telemetry.

```json
{
  "entityId": "entity_ash_gamer_01",
  "entityType": "CHARACTER",
  "displayName": "Ash_Streamer",
  "characterInfo": {
    "personalityNotes": "Exhausted competitive tower defense gamer, hyper-focused, dark humor, calculating.",
    "audioReferences": [
      {
        "presetVoiceId": "Charon"
      }
    ],
    "imageReferences": [
      {
        "workflowId": "wf_face_slot0_uuid"
      },
      {
        "workflowId": "wf_body_slot1_uuid"
      }
    ]
  },
  "thumbnailMediaId": "media_face_slot0_uuid"
}
```

### 2.2 The Two-Slot Generation Saga (Slot 0 & Slot 1)
Google Flow synthesizes Character Entities through a two-step generative saga that guarantees anatomical identity lock between face and body:

```
[User Prompts Face]
        |
        v
+-------------------------------------------------------+
| Slot 0: Face Portrait Generation                      |
| Endpoint: POST /v1/projects/{id}/flowMedia:batch...   |
| Prompt: High-res front/three-quarter portrait         |
| Output: primaryMediaId_face                           |
+---------------------------+---------------------------+
                            |
           Seeds Slot 1 via IMAGE_INPUT_TYPE_REFERENCE
                            |
                            v
+-------------------------------------------------------+
| Slot 1: 3-View Body Turnaround Generation             |
| UI Trigger: mat-icon 'accessibility_new' (Create Body)|
| Seed: primaryMediaId_face attached as reference       |
| Wrapped Prompt: "front view, side profile, back view" |
| Output: primaryMediaId_body (Triptych matching Face)  |
+---------------------------+---------------------------+
                            |
                            v
+-------------------------------------------------------+
| Entity Finalization & Storage                         |
| Endpoint: PATCH /v1/flow/entities                     |
| Bound Slots: [Slot 0 (Face), Slot 1 (3-View Body)]    |
+-------------------------------------------------------+
```

1. **Slot 0 (Face Portrait)**:
   - Captures facial geometry, eye spacing, scar tissue, skin undertones, and hair styling.
   - For *Tyrant of the Tower Defense Game*, `@Ash_Streamer` establishes pale complexion, messy dark hair, intense amber-tinted eyes, and chronic dark eye circles.
   - For `@Lucas_Knight`, Slot 0 establishes weathered 40-year-old steel-gray hair, a jagged monster claw scar across the left cheek, and a grim, resolute jawline.
2. **Slot 1 (3-View Body Turnaround Triptych)**:
   - When the creator clicks `accessibility_new` ("Create Body") in the Flow character editor, the UI automatically binds the generated Slot 0 `primaryMediaId` as an `IMAGE_INPUT_TYPE_REFERENCE` seed.
   - Flow dispatches a wrapped prompt enforcing a standardized orthographic triptych: front view, 90-degree lateral profile, and rear dorsal view.
   - Because the diffusion latent is conditioned directly on the Slot 0 face latent, the character's clothing, build, and coloration match the portrait without facial warping.

### 2.3 Invoking Characters via `@Name` Mentions
In both the text prompt bar and continuation prompt composer:
- Typing `@` opens the Flow asset picker overlay (`.cdk-overlay-pane`).
- Typing `@Ash_Streamer` surfaces the Character chip.
- When submitted, the client parses `@Ash_Streamer` into the wire request payload:
  ```json
  "referenceEntities": [
    {
      "entityId": "entity_ash_gamer_01"
    }
  ]
  ```
- The backend video diffusion pipeline clamps facial and costume latents to the registered reference sheets, suppressing detail drift across all frames of the clip.

### 2.4 The Inviolable Costume Separation Rule
A common pitfall in generative video pipelines is attempting to mutate a character's costume via in-prompt modifiers (e.g., typing `@Ash_Streamer wearing plate armor with a sword`).
- **Failure Mode**: The model experiences latent contention between the Slot 1 reference sheet (oversized hoodie & gaming headset) and the contradictory text prompt (heavy gothic armor). This results in horrific hybrid artifacts (hoodies rendered out of steel, headsets fused into helmets, tearing textures).
- **The Golden Rule**: **Costume variants must be registered as separate Character Entities that share the identical Slot 0 Face seed.**
  - `Entity 1`: `@Ash_Streamer` -> Slot 0: Ash Face Seed; Slot 1: Gaming Hoodie, Headset, Ergonomic chair pose.
  - `Entity 2`: `@Prince_Ash` -> Slot 0: Ash Face Seed; Slot 1: Imperial Prince Overcoat, Gold Epaulets, Command Baton.
  - `Entity 3`: `@Lucas_Knight` -> Slot 0: Lucas Face Seed; Slot 1: Battered Blackened Plate Armor, Lion Tabard, Spiked Shield.
- Transitioning between costumes is handled strictly by cutting between clips or utilizing continuation mode where the camera leaves one character and enters a new scene.

## 3. Ingredients Mode (`referenceImages`) & Asset Binding

### 3.1 Role & Distinction: Characters vs. Ingredients
While Character Entities (`referenceEntities`) enforce durable multi-angle anatomical identity for conscious agents, **Ingredients Mode** (`referenceImages`) anchors inanimate assets, environments, and stylistic art treatments.

| Dimension | Character Entities (`referenceEntities`) | Ingredients (`referenceImages`) |
|---|---|---|
| **Primary Target** | Faces, body proportions, recurring protagonists. | Props, room layouts, UI screens, weapon models, art styles. |
| **Slot Architecture** | Slot 0 (Face) + Slot 1 (3-View Body Turnaround). | Single or multi-image asset pool with `IMAGE_USAGE_TYPE_ASSET`. |
| **Invocation** | Inline `@CharacterName` chip in prompt. | Media Library attachment (`--ref` flag or UI asset tray). |
| **Model Constraints** | Strong anatomical and facial topology clamping. | Feature map, texture, and compositional layout guidance. |
| **Costume Mutability**| Strictly immutable per entity. | Flexible, can be combined with character entities. |

### 3.2 Wire Protocol & Image Usage Specification
When an ingredient asset is attached to a generation session on `flow.google.com`, the client constructs the request payload using `referenceImages`:

```json
{
  "aspectRatio": "VIDEO_ASPECT_RATIO_LANDSCAPE",
  "textInput": {
    "structuredPrompt": {
      "parts": [
        {
          "text": "Cinematic dark fantasy anime, close-up of tactical game screen displaying @SaveTheEmpireMap..."
        }
      ]
    }
  },
  "referenceImages": [
    {
      "mediaId": "media_game_map_tactical_uuid",
      "imageUsageType": "IMAGE_USAGE_TYPE_ASSET"
    },
    {
      "mediaId": "media_streamer_room_layout_uuid",
      "imageUsageType": "IMAGE_USAGE_TYPE_ASSET"
    }
  ],
  "referenceEntities": [
    {
      "entityId": "entity_ash_gamer_01"
    }
  ]
}
```

### 3.3 Video Generation Route Comparison: T2V vs. R2V vs. I2V
Selecting the appropriate generation route dictates whether reference entities and ingredients can be injected:

```
+---------------------------------------------------------------------------------------+
| Route   | Description          | Character (@Name) | Ingredients (--ref) | Start/End  |
+---------+----------------------+-------------------+--------------------+------------+
| t2v     | Pure Text-to-Video   | Supported         | Not Supported      | N/A        |
|         | Generates from text  | (referenceEntities| (Phase 3 in wire)  |            |
|         | + character latent.  | allowed)          |                    |            |
+---------+----------------------+-------------------+--------------------+------------+
| r2v     | Reference-to-Video   | Supported         | Fully Supported    | N/A        |
|         | (Ingredients Mode)   | (Pairs entity ID  | (referenceImages   |            |
|         | Combines character   | with image refs)  | attached to DTO)   |            |
|         | + prop/style images. |                   |                    |            |
+---------+----------------------+-------------------+--------------------+------------+
| i2v     | Image-to-Video       | Forbidden         | Forbidden          | Required   |
|         | Animates explicit    | (DTO rejects      | (Replaced by       | (Initial + |
|         | initial frame.       | referenceEntities)| frame buffers)     | optional)  |
+---------------------------------------------------------------------------------------+
```

1. **`t2v` (Text-to-Video)**:
   - Best for open-ended character acting shots without rigid environmental or prop constraints.
   - Accepts `@CharacterName`, locking the face and outfit while allowing dynamic background composition.
2. **`r2v` (Reference-to-Video / Ingredients Mode)**:
   - The primary production workhorse for animated series scenes.
   - Allows creators to co-dispatch `@CharacterName` alongside canonical environment art (`streamer_room_environment.png`) and specific props (`stream_overlay_chat_donation.png`).
3. **`i2v` (Image-to-Video)**:
   - Used when a scene must begin from an exact 2D illustration frame (e.g., manga title card).
   - Rejects `referenceEntities` and `referenceImages` because the initial frame already fully defines the visual field.

### 3.4 Canonical Asset Pool for "Tyrant of the Tower Defense Game"
For the opening sequence (Manga Frames 001–026), four canonical ingredients must be staged in the media library:
1. `asset_streamer_room`: Cluttered bedroom battlestation, ultrawide curved monitor, RGB mechanical keyboard, acoustic wall paneling, cold blue and warm amber ambient lighting.
2. `asset_game_screen_map`: Top-down tactical fortress defense map, isometric grid, stone bastion towers under siege by glowing red monster icons, and victory banner.
3. `asset_stream_overlay`: Dark Twitch-style stream layout with scrolling viewer chat pane, subscriber counters, and live donation notifications (300,000 Won).
4. `asset_citadel_ramparts`: High-resolution matte painting of Crossroads Fortress ramparts at night under torrential rain, showing stone crenellations, iron braziers, and the abyssal Black Fog.

## 4. Scene Builder Video Continuation Mode (`Veo 3.1 - Lite`)

### 4.1 Concept & Purpose
Rather than generating isolated, disjointed 8-second clips that must be manually cut together, Google Flow’s **Scene Builder Video Continuation** (`>> Режим продолжения (Veo 3.1 - Lite)`) enables progressive, multi-clip continuous shot generation. By conditioning the generative diffusion model on the terminal latent states of the preceding clip, the system maintains flawless kinetic momentum, camera velocity, lighting color temperature, and atmospheric particle trajectories across scene boundaries.

### 4.2 UI Entry Point & Interaction Flow
To initiate video continuation in Google Flow Scene Builder:
1. Open the project timeline: `https://flow.google.com/project/{projectId}/edit/{mediaId}`.
2. At the far right edge of the active video clip on `flow-scene-timeline`, locate and click the Add-Clip control:
   - **DOM Selector**: `flow-scene-timeline button.add-clip-button`
3. In the popup CDK overlay menu, select the Video Continuation menu item:
   - **DOM Selector**: `.cdk-overlay-pane [role='menuitem']:has(mat-icon:text-is('keyboard_double_arrow_right'))`
   - **Localized Label (Russian)**: `>> Режим продолжения (Veo 3.1 - Lite)`
   - **Localized Label (English)**: `>> Extend (Veo 3.1 - Lite)`
4. The timeline appends a linked continuation ghost clip, and the right-hand panel mounts the continuation prompt bar (`flow-edit-video-prompt-box .ProseMirror`).

### 4.3 Wire Protocol & Endpoint Pipeline
The video extension workflow triggers three sequential RPC transactions:

```
[UI Trigger Click: >> Extend (Veo 3.1 - Lite)]
                       |
                       v
    1. POST /fx/api/trpc/flow.rqZuUc (Session RPC)
       Creates server-side Scene entity bound to source mediaId
                       |
                       v
    2. POST /fx/api/trpc/flow.uwAyfb (Session RPC)
       Fetches and validates the newly created Scene record
                       |
                       v
    3. POST /v1/video:batchAsyncGenerateVideoExtendVideo (fZytfe)
       Dispatches billed extension generation to Veo 3.1 Lite engine
```

### 4.4 The 24-Frame Trailing Seed Window
A critical architectural parameter of `veo_3_1_extension_lite` is the exact seed window:
- **Seed Window**: Exactly **24 frames at 24.0 fps** (precisely 1.000 second).
- **Frame Index Range**: `startFrameIndex = 1`, `endFrameIndex = 24` sampled from the tail end of the source video.
- **Wire Payload Structure**:

```json
{
  "aspectRatio": "VIDEO_ASPECT_RATIO_LANDSCAPE",
  "textInput": {
    "structuredPrompt": {
      "parts": [
        {
          "text": "Camera continues pushing forward directly past @Ash_Streamer's shoulder, smoothly transitioning focal plane from his headphones into the bright glass surface of the primary gaming monitor..."
        }
      ]
    }
  },
  "videoModelKey": "veo_3_1_extension_lite",
  "metadata": {
    "sceneId": "scene_ttd_prologue_01"
  },
  "videoInput": {
    "mediaId": "media_streamer_clip01_uuid",
    "startFrameIndex": 1,
    "endFrameIndex": 24
  },
  "mediaGenerationContext": {
    "batchId": "6fee37d3-b168-4485-bcf2-18fc1608b761",
    "audioFailurePreference": "RETURN_SILENCED_VIDEOS",
    "sceneContext": {
      "sceneId": "scene_ttd_prologue_01",
      "position": 1
    }
  }
}
```

### 4.5 Operational Invariants & Constraints
1. **Strict Aspect Ratio Locking**:
   - The continuation clip automatically inherits and locks the aspect ratio of the parent clip.
   - Allowed: `VIDEO_ASPECT_RATIO_LANDSCAPE` (`16:9` widescreen, 1280x720) and `VIDEO_ASPECT_RATIO_PORTRAIT` (`9:16` vertical, 720x1280).
   - **Forbidden**: Square (`1:1`) aspect ratio is unsupported by `veo_3_1_extension_lite` and will fail validation.
2. **Fixed Frame Rate**:
   - The engine strictly processes at 24 fps. Seed frames and output clips are guaranteed 24.00 fps cadence.
3. **Credit Expenditure**:
   - Each extension call triggers a billed generation (`fZytfe`) spending 1 video credit.

## 5. Prompt Bar Editing Grammar & Delta Directives

### 5.1 UI Element & Contextual Behavior
When Video Continuation mode is active, the Scene Builder interface presents the prompt composer dock:
- **DOM Selector**: `flow-edit-video-prompt-box .ProseMirror`
- **Localized Placeholder (Russian)**: `"Опишите, как отредактировать это видео..."`
- **Localized Placeholder (English)**: `"Describe how to edit this video..."`
- **Submit Action**: `flow-edit-video-prompt-box flow-generate-icon-button button`

Unlike standard initial prompt boxes that require complete scene world-building from scratch, this prompt composer expects **delta instructions** describing how the world, camera, and subjects evolve over the next 8-second segment.

### 5.2 The 4 Golden Rules of Continuation Grammar

#### Rule 1: Describe the State Delta (Never Restart Context)
- **Failure Pattern**: Re-establishing the scene from scratch:
  - ❌ *Incorrect*: `"A young man with dark hair in a hoodie is sitting at a gaming desk with three computer monitors in a dark room..."*
  - *Result*: The model interprets this as a new establishing shot, causing the camera to jump cut backwards to a wide view, disrupting the continuous flow.
- **Success Pattern**: Describing the seamless continuation of motion from the 24-frame trailing seed:
  - ✅ *Correct*: `"Camera continues pushing forward directly past @Ash_Streamer's shoulder, smoothly transitioning focal plane from his headphones into the bright glass surface of the primary gaming monitor..."*
  - *Result*: The camera maintains forward momentum without a hitch, executing a fluid push-in.

#### Rule 2: Kinetic Camera Verbs Lead the Sentence
Generative video models prioritize tokens at the start of the prompt sequence. In continuation mode, leading with camera trajectory verbs locks spatial continuity:
- **Primary Kinetic Verbs**:
  - `"Camera smoothly dollies forward across the stone parapet..."`
  - `"Continuous crane tilt descending through the storm clouds..."`
  - `"Lateral tracking shot sliding left behind the row of roaring braziers..."`
  - `"Seamless rack focus from foreground cracked shield to background rain-slick battlements..."`
- **Avoid Passive Phrasing**: Avoid phrases like `"We can see"` or `"There is a shot of"`.

#### Rule 3: Reference Sheet Immutability Lock
When an entity mention like `@Ash_Streamer` or `@Lucas_Knight` is active:
- **Do Not Instruct Costume Alterations**: Never instruct the character to take off their hoodie, equip plate armor, or change eye color inside the continuation prompt. The Slot 1 body sheet will fight the text prompt, generating severe latent noise and limb deformities.
- **Handling Transformation/Costume Changes**:
  - Step A: Move the camera away from the character (e.g., zoom into the monitor, pan into billowing smoke, or tilt up to the sky).
  - Step B: End the clip on the neutral environment/object.
  - Step C: Start the subsequent clip with the new costume entity (`@Prince_Ash`) already established.

#### Rule 4: Multi-Layer Atmospheric & Sound Integration
Veo 3.1 features cross-modal audiovisual synchronization. Atmospheric audio cues in the continuation prompt directly govern physical motion cadence and particle behavior:
- **Lighting & Specular Anchors**: Include explicit lighting interactions (`"flickering amber brazier light glinting off wet steel"`, `"pulsing cyan monitor bloom illuminating flying dust motes"`).
- **Sound Effects (SFX) Cues**: Mentioning specific acoustics assists the model in synchronizing movement speeds:
  - `"Ambient hum of cooling fans and frantic mechanical keyboard clicks..."`
  - `"Heavy rain splashing on cold granite battlements with distant rolling thunder..."`
  - `"Resonant metallic groan as the iron fortress portcullis locks into place..."`

### 5.3 Continuation Prompt Template Structure
Every continuation prompt should follow this structured 5-part architecture:

```
[1. KINETIC CAMERA DIRECTIVE] +
[2. SEED TRANSITION ANCHOR] +
[3. CHARACTER ACTING / SUBJECT DELTA] +
[4. ENVIRONMENTAL & PARTICULATE EVOLUTION] +
[5. LIGHTING, SFX & STYLE RE-ANCHOR]
```

**Example Production Prompt (Screen Zoom Transition)**:
> `"Smooth continuous push-in gliding past @Ash_Streamer's right ear and gaming headset, blurring the physical room out of focus as the camera immerses into the glowing ultrawide monitor screen. The pixel tactical interface of 'Save the Empire' expands to fill the entire frame, revealing glowing red monster path lines converging on Crossroads Fortress. Golden victory runes burst across the central display. High contrast Arcane anime aesthetic, digital scanlines, buzzing monitor hum, resonant orchestral victory chime."`

## 6. Step-by-Step UI Guide for Project `7d9a2a67-9cd2-4a79-932e-717d2e29257f`

### 6.1 Calibration & Normalized Coordinate Map
All automation and manual interactions on `flow.google.com` map to a normalized `[0..1000] x [0..1000]` coordinate grid as codified in `FlowUIMap` (`src/flow_ui_controller.py`):

| Control Identifier | Normalized Coordinate `(X, Y)` | Description / Purpose |
|---|---|---|
| `characters_tab` | `(63, 168)` | Left navigation sidebar: Character entities & reference sheets |
| `scenebuilder_btn`| `(63, 206)` | Left navigation sidebar: Open Scene Builder Timeline |
| `library_tab` | `(48, 252)` | Media library & uploaded reference ingredients |
| `prompt_textarea` | `(892, 885)` | Main text prompt input field (`flow-edit-video-prompt-box`) |
| `add_media_btn` | `(832, 922)` | Attach reference image or character via `@` picker |
| `settings_btn` | `(958, 922)` | Open generation settings (aspect ratio, model tier) |
| `aspect_16_9_option`| `(863, 543)` | Lock 16:9 widescreen landscape output |
| `confirm_never_radio`| `(830, 303)` | Disable modal confirmation dialogues for automated runs |
| `video_model_dropdown`| `(905, 618)`| Select active video engine (`Veo 3.1 - Quality` / `Lite`) |
| `generate_submit_btn` | `(976, 922)` | Submit generation / extension request (`flow-generate-icon-button`) |

### 6.2 Step-by-Step Manual UI Execution Sequence

#### Step 1: Access Project & Authenticate Session
1. Navigate directly to the project URL:  
   `https://flow.google.com/project/7d9a2a67-9cd2-4a79-932e-717d2e29257f`
2. Ensure active authentication with Google Account credentials holding Veo 3.1 generation entitlements.
3. If the profile prompt appears, dismiss it via `profile_close_btn` at `(972, 94)`.

#### Step 2: Register Character Entities & Upload Ingredients
1. Click `characters_tab` at `(63, 168)`.
2. Click **Create Character** (`POST /fx/api/trpc/flow.createEntity`):
   - Set Name: `Ash_Streamer`.
   - In Portrait prompt, input the Slot 0 face prompt and click Generate.
   - Click the `accessibility_new` icon to switch to **Create Body** mode.
   - Flow automatically attaches the Slot 0 face image. Enter the body turnaround prompt and click Generate.
   - Assign voice persona `Charon` and save.
3. Repeat for `Lucas_Knight`:
   - Set Name: `Lucas_Knight`.
   - Generate Slot 0 (scarred face) and Slot 1 (battered blackened plate armor).
   - Assign voice persona `Charon` and save.
4. Click `library_tab` at `(48, 252)` and upload environmental assets:
   - `streamer_room_environment.png`
   - `game_save_the_empire_screen.png`
   - `stream_overlay_chat_donation.png`

#### Step 3: Configure Generation Parameters
1. Click `settings_btn` at `(958, 922)`.
2. Verify **Aspect Ratio**: Select `aspect_16_9_option` at `(863, 543)` (`16:9` landscape).
3. Verify **Outputs Count**: Ensure `outputs_x1_option` at `(842, 585)` is selected.
4. Verify **Video Model**: Click `video_model_dropdown` at `(905, 618)` and select `model_quality_option` (`Veo 3.1 - Quality`).
5. Click `settings_save_btn` at `(905, 926)` to close settings.

#### Step 4: Generate Base Clip 1 (Streamer Battlestation)
1. In `prompt_textarea` at `(892, 885)`, type `@Ash_Streamer` and select the entity chip.
2. Enter the full initial prompt for Scene 1 (Frames 001–005).
3. Click `generate_submit_btn` at `(976, 922)`.
4. Monitor generation until progress reaches 100% and the clip renders in the timeline.

#### Step 5: Mount Scene Builder Timeline & Invoke Continuation
1. In the left sidebar, click `scenebuilder_btn` at `(63, 206)`.
2. Select the generated Clip 1 to mount it in the timeline editor:  
   `/project/7d9a2a67-9cd2-4a79-932e-717d2e29257f/edit/{mediaId}`
3. Hover over the right edge of Clip 1 on `flow-scene-timeline` and click `button.add-clip-button`.
4. In the CDK overlay menu, select `>> Режим продолжения (Veo 3.1 - Lite)` (`keyboard_double_arrow_right`).
5. Verify that the prompt bar displays placeholder `"Опишите, как отредактировать это видео..."`.

#### Step 6: Dispatch Continuation Clip 2 (Monitor Immersion)
1. In `flow-edit-video-prompt-box .ProseMirror`, paste the continuation prompt for Scene 2 (Frames 006–014).
2. Click `generate_submit_btn`. Flow triggers `rqZuUc`, `uwAyfb`, and `fZytfe`.
3. Wait ~45–60 seconds for Veo 3.1 Lite extension generation to complete.
4. Verify that Clip 2 is seamlessly appended to Clip 1 on the timeline.

#### Step 7: Dispatch Continuation Clip 3 (Lucas Ramparts)
1. Select Clip 2 on `flow-scene-timeline`.
2. Click `button.add-clip-button` at the right edge of Clip 2.
3. Select `>> Режим продолжения (Veo 3.1 - Lite)`.
4. In the prompt bar, paste the continuation prompt for Scene 3 (Frames 015–026), describing the dissolution of the digital monitor into the wet stone ramparts of Crossroads Fortress.
5. Click `generate_submit_btn`.
6. Once rendered, preview the full 3-clip continuous sequence in the timeline player.

## 7. Seam Handling & Multi-Scene Transition Protocol

### 7.1 The 7.0-Second Motion + 1.0-Second Hold Frame Phenomenon
In Google Flow’s implementation of Veo 3.1:
- Each generated or extended segment is formatted into an 8.000-second container (192 frames @ 24 fps).
- **Physical Motion Envelope**: Generative diffusion actively animates across the first **7.000 seconds** (frames 0 through 168).
- **Terminal Hold Buffer**: The final **1.000 second** (frames 169 through 192, exactly 24 frames) exhibits near-zero velocity, acting as an intentional frozen "hold frame" and audio tail buffer designed to provide a safe landing zone for human timeline editors.

```
+-------------------------------------------------------------------------------+
| Frame 0                          Frame 168                    Frame 192       |
| [ 0.0s ] <------ Active Generative Motion (7.0s) ------> [ 7.0s ] < Hold > [ 8.0s ] |
+-------------------------------------------------------------------------------+
                                                                ^
                                       Extension Seeds Here ----+
```

### 7.2 Mitigation Strategies: Trimming vs. Cross-Fading
When chaining extended clips together into a finished master episode, leaving the hold frame in place causes jarring momentary stutters:

#### Strategy A: Direct Trim Assembly (Lossless Hard Cut)
Trim the trailing 24 frames (1.00s) from intermediate clips before concatenation. Because Clip 2 seeded directly from frames 168–192, cutting Clip 1 at frame 168 and joining Clip 2 creates an instantaneous velocity continuation:
```bash
# Trim intermediate clip to exact 7.00s active motion window
ffmpeg -y -ss 00:00:00.000 -to 00:00:07.000 -i clip_01_streamer.mp4 \
  -c:v libx264 -preset slow -crf 18 -c:a aac -b:a 192k clip_01_trimmed.mp4
```

#### Strategy B: 12-Frame Cross-Dissolve (Smooth Blending)
Apply a 0.5-second (12-frame) cross-dissolve (`xfade`) across the seam to mask any residual micro-jitter:
```bash
ffmpeg -y -i clip_01_streamer.mp4 -i clip_02_screen_zoom.mp4 \
  -filter_complex "[0:v][1:v]xfade=transition=fade:duration=0.5:offset=6.5[v]; \
                   [0:a][1:a]acrossfade=d=0.5[a]" \
  -map "[v]" -map "[a]" -c:v libx264 -crf 18 seam_smoothed.mp4
```

### 7.3 Canonical 3-Scene Sequence: "Tyrant of the Tower Defense Game"

```
+-----------------------------------------------------------------------------------------------+
| SEQUENCE BREAKDOWN: Manga Frames 001 - 026 (Arcane Dark Fantasy Aesthetic)                    |
+-----------------------------------------------------------------------------------------------+
| Shot 1: Streamer Battlestation (Frames 001-005) -> Initial Generation (R2V with @Ash_Streamer)|
| Shot 2: Screen Immersion & Map (Frames 006-014) -> Extension (>> Veo 3.1 - Lite on Shot 1)    |
| Shot 3: Lucas Citadel Ramparts (Frames 015-026) -> Extension (>> Veo 3.1 - Lite on Shot 2)    |
+-----------------------------------------------------------------------------------------------+
```

#### Clip 1: The Streamer's Climax (Frames 001–005)
- **Narrative Purpose**: Establish the protagonist (`@Ash_Streamer`) in the real world, beating the impossible final stage of the tower defense game after sleepless days of streaming.
- **Generation Mode**: `r2v` (Reference-to-Video) with Character `@Ash_Streamer` bound, 16:9, 8s, `Veo 3.1 - Quality`.
- **Ingredients Bound**: `streamer_room_environment.png`, `stream_overlay_chat_donation.png`.
- **Production Prompt**:
  > `Create a 16:9 cinematic dark fantasy anime video (8s) in Arcane aesthetic: Medium shot of young streamer @Ash_Streamer wearing a dark oversized zip-up hoodie with gaming headphones over his ears, sitting in an ergonomic chair at a cluttered gaming desk in a dimly lit bedroom. Multiple glowing ultrawide monitors illuminate his concentrated face with intense cyan and amber specular highlights, casting soft shadows across energy drink cans and a mechanical keyboard. The camera slowly pushes in on his intense dark eyes with amber glints as he rapidly clicks the gaming mouse in a frenzy, then lets out an exhausted sigh of triumph as screen reflections shift from dark combat to bright victory banners. High-contrast chiaroscuro, subtle screen flicker, ambient hum of cooling fans and mechanical keyboard clicks.`

#### Clip 2: The Digital Immersion (Frames 006–014)
- **Narrative Purpose**: Camera plunges past the streamer's shoulder into the monitor, transforming digital pixels into the living dark fantasy battlefield.
- **Generation Mode**: `>> Режим продолжения (Veo 3.1 - Lite)` triggered from Clip 1.
- **Ingredients Bound**: `game_save_the_empire_screen.png`.
- **Continuation Prompt ("Опишите, как отредактировать это видео...")**:
  > `Camera continues pushing forward directly past @Ash_Streamer's shoulder, smoothly transitioning focal plane from his headphones and hair into the bright glass surface of the primary gaming monitor. As the camera zooms into the screen, the room fades into darkness while the monitor displays the tactical UI of 'Save the Empire': a pixel-dark fantasy fortress map under siege, flashing red 'CRITICAL ATTRITION' warnings and an ornate gold 'STAGE CLEARED: EMPIRE SAVED' banner. Golden victory particles and digital pixels ripple outward across the screen surface, with electronic chime SFX transitioning into deep ominous military horn echoes.`

#### Clip 3: The Lonely Rampart of Lucas (Frames 015–026)
- **Narrative Purpose**: Digital reality washes away into the grim, soaking rain of Crossroads Fortress, revealing Knight Lucas standing alone in the darkness.
- **Generation Mode**: `>> Режим продолжения (Veo 3.1 - Lite)` triggered from Clip 2.
- **Character Bound**: `@Lucas_Knight`.
- **Ingredients Bound**: `asset_citadel_ramparts`.
- **Continuation Prompt ("Опишите, как отредактировать это видео...")**:
  > `The digital game interface and victory banners dissolve and wash away like digital rain, giving way to real torrential night downpour on cold monolithic stone. The camera smoothly glides forward through billowing black mist onto the wet granite ramparts of Crossroads Fortress under an eerie crimson blood moon. Standing alone at the stone crenellations is Knight Lucas, viewed from behind in a poignant medium-wide shot: his massive shoulders slump with bone-deep exhaustion, his dented blackened steel plate armor and faded navy-blue tabard are soaked and stained with beast blood, and his battered spiked iron tower shield rests heavily against the parapet. Flickering amber torchlight from a roaring iron brazier glints off his rain-slick pauldrons as he stares out into the silent abyss of the battlefield. Somber cinematic melancholy, heavy rain splashing on iron and stone, rolling distant thunder, howling wind.`

## 8. Automated Telemetry, Quality Control & Verification

### 8.1 VisualActionOracle & State Transition Telemetry
Automating Google Flow across headless or interactive desktop sessions requires deterministic proof that UI actions actually alter browser state rather than hanging on silent stalls.

In `src/flow_ui_controller.py`, every UI click or keypress is guarded by the **64-bit dHash VisualActionOracle** (`REQ-FLOW-UI-02`):
1. **Screen Capture**: Grab RGB framebuffer bytes immediately before input dispatch:
   $$\mathbf{I}_{\text{before}} \in \mathbb{R}^{W \times H \times 3}$$
2. **dHash Computation**: Convert to 8-bit grayscale, downsample to $9 \times 8$ bilinearly, and compute horizontal gradient sign bits:
   $$b_i = \begin{cases} 1 & \text{if } P(x, y) > P(x+1, y) \\ 0 & \text{otherwise} \end{cases}$$
3. **Hamming Distance Assertion**:
   $$\mathcal{H}(h_{\text{before}}, h_{\text{after}}) = \sum_{k=0}^{63} \left( h_{\text{before}}[k] \oplus h_{\text{after}}[k] \right) \ge 2$$
   - If $\mathcal{H} \ge 2$, the action transitions the UI with tag `[FACT]`.
   - If $\mathcal{H} < 2$, the action failed to trigger a DOM mutation and returns `[NO_CHANGE]`, triggering an automated retry or error escalation.

### 8.2 Production Verification Suite
To certify that local storyboard compilers, schema bridges, and UI controllers adhere to the specifications in this guide, run the comprehensive verification suite:

```bash
# Execute full flow studio verification (49 passing test cases)
python -m pytest tests/test_flow_studio.py -v

# Specific test cases validating Flow UI, Schema Bridge & TTD Lore Bible:
python -m pytest tests/test_flow_studio.py -k "test_req_flow_ui or test_ttd_r1 or test_ttd_r2" -v
```

### 8.3 Production Readiness Checklist
Before initiating high-credit batch generations for an animated episode, ensure every item on this checklist is satisfied:

- [x] **Character Slots Locked**: Slot 0 (Face) and Slot 1 (3-View Body) generated and saved as durable Character Entities (`Ash_Streamer`, `Lucas_Knight`).
- [x] **Costume Variants Isolated**: Any costume change (e.g., Gamer Hoodie vs. Prince Overcoat) registered as a distinct Character Entity sharing the same Face seed.
- [x] **Ingredients Pre-Uploaded**: Environmental backgrounds and UI screens uploaded to project media library with unique filenames to prevent picker collision.
- [x] **Aspect Ratio Locked**: Initial clip generated strictly at 16:9 (`VIDEO_ASPECT_RATIO_LANDSCAPE`). Square (1:1) is never used for continuation.
- [x] **Continuation Grammar Validated**: Prompts begin with kinetic camera verbs, describe state deltas, incorporate atmospheric audio cues, and never re-introduce established scenes from scratch.
- [x] **Seam Post-Processing Configured**: Downstream FFmpeg pipeline trims trailing 24 hold frames (1.00s) from intermediate clips before final concatenation.

---

**End of Guide — Document Reference**: `docs/google_flow_series_guide.md`
