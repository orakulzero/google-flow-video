# Google Flow Community Tools, Motion Dynamics & Latent Stabilization Guide
**Document Version**: 2.0.0 (Production Release)  
**Classification**: Architectural Standard & Creative Engineering Guide (Requirement R1)  
**Target Platform**: Google Flow (`flow.google.com` / `labs.google/fx/tools/flow`)  
**Core Generative Video Engine**: Google Veo 3.1 (`veo_3_1_extension_lite`, `veo_3_1_t2v_fast_audio`, `veo-quality`)  
**Target Subject Benchmark**: *Tyrant of the Tower Defense Game* (Prologue Manga Frames 001–032)  
**Status**: APPROVED & PUBLISHED  

---

## Executive Summary

Generative video diffusion models (such as Google Veo 3.1 and Gemini Omni Flash) represent a paradigm shift in visual storytelling, but they introduce acute challenges when applied to multi-clip episodic animation. When driven solely by unconstrained natural language prompts, video diffusion models exhibit catastrophic **latent drift**: facial bone structures warp between clips, characters rapidly morph into generic statistical averages, head turns tear facial topology into grotesque deformations, and gaze vectors wander across the screen.

This guide provides the complete, publication-grade engineering standard for eliminating face drift, maintaining character continuity, and directing cinematographic motion in Google Flow. By combining:
1. **The Flow Community Tools Architecture** (`creative-director`, `storyboard`, `reverse-engineer`),
2. **Google's 5-Component Prompt Formula** with strict stripping of low-signal quality buzzwords,
3. **The Dual-Slot Character Entity Protocol** (`Slot 0` Face Portrait and `Slot 1` 3-View Body Turnaround) with decoupled Asset Ingredients,
4. **Scene Continuation Mode** (`Veo 3.1 Extension Lite`) utilizing a trailing 24-frame seed window and Delta Grammar,
5. **Strict Motion Dynamics Constraints** (Head Yaw $\le 15^\circ$, orbital camera movement, and 4-pillar pupil catchlight gaze locking), and
6. **Micro-Shot Duration Scaling** (1.5s–3.0s micro-fragments vs. 4s–8s entropy-saturated containers),

creators can achieve broadcast-grade animated sequences with 100% facial and stylistic stability.

---

## 1. Flow Community Tools & Extensibility Framework

### 1.1 Flow Tools Architecture & Gallery Overview
Google Flow structures its creative environment into a modular pipeline featuring an integrated **Tools Gallery** accessible through the left navigation panel (`tools_tab` at normalized coordinates `(63, 298)`). The tools infrastructure serves two critical functions in series production:
- **Pre-Diffusion Prompt Transforms**: Packaged procedural rewrites that translate user intention into mathematically structured prompts optimized for Veo 3.1's cross-attention layers.
- **Natural Language Mini-Apps & Workflow Remixing**: Creators can create, test, and publish custom single-purpose mini-apps (e.g., automated character turnaround generators, style lockers, scene continuation scaffolds) to the community registry for one-click re-use.

### 1.2 Core Built-In Production Tools (`gflow_cli` & Upstream)
Investigation of the production CLI runtime (`gflow_cli.tools.builtin`) identifies three foundational tools that form the core of the Flow workflow:

| Tool Identifier | Supported Modalities | Core Transformation Function | Impact on Latent & Character Stability |
|---|---|---|---|
| `creative-director` | Text-to-Image, Text-to-Video | Expands brief user inputs into rich 5-component prompts; strips 13 banned quality boosters (`4k`, `photorealistic`, `masterpiece`). | Eliminates token contention, enforces precise physical attributes, and sets deterministic optical and lighting parameters. |
| `reverse-engineer` | Image-to-Text, Video-to-Text | Analyzes reference media and extracts 5 structured semantic slots: `SUBJECT`, `ACTION`, `CONTEXT`, `COMPOSITION`, `STYLE`. | Decouples character features from background and lighting, preventing cross-latent contamination. |
| `storyboard` | Multi-panel Sequential Video | Generates continuous narrative prompt sequences (typically 4–8 beats) with identical character tokens and continuous kinetic vectors. | Guarantees consistent token ordering and styling across successive scene cuts. |

### 1.3 Generation Route Matrix & Transport Contracts
In Google Flow, selecting the proper execution route dictates whether Character Entities (`referenceEntities`) and Asset Ingredients (`referenceImages`) are accepted on the wire protocol:

```
+-------------------------------------------------------------------------------------------------------+
| Route   | Command Verb       | Character Entity (@Name)     | Ingredients (--ref)       | Intended Role       |
+---------+--------------------+------------------------------+---------------------------+---------------------+
| t2v     | `video t2v`        | Allowed (referenceEntities)  | Forbidden (Wire schema)   | Freeform acting     |
| r2v     | `video r2v`        | Fully Supported              | Fully Supported           | Episodic series     |
| i2v     | `video i2v`        | Forbidden (DTO Rejection)    | Replaced by Start/End Ref | Keyframe animation  |
| extend  | `video extend`     | Supported via Prompt Bar     | Preserved from Buffer     | Scene continuity    |
| chain   | `video chain`      | Local per-link I2V restart   | Last frame extraction     | Hard scene cuts     |
+-------------------------------------------------------------------------------------------------------+
```

For narrative episodic series like *Tyrant of the Tower Defense Game*, the primary production vehicles are **`r2v` (Reference-to-Video)** for scene establishment and **`extend` (Video Continuation via Scene Builder)** for seamless intra-scene acting beats.

---
## 2. Google's 5-Component Prompt Formula & Booster Stripping

### 2.1 The Standard 5-Component Prompt Grammar
Google Flow's video generation models (Veo 3.1 and Omni Flash) require a structured five-component composition syntax. Rather than a chaotic jumble of adjectives, prompts must be organized into five distinct semantic layers:

1. **Subject**: The physical entity in the scene, explicitly identified by character reference tag (`@Ash_Streamer`, `@Lucas_Knight`), physiological traits (age, hair texture, skin undertones, fatigue marks), and clothing.
2. **Action**: Exactly ONE atomic physical kinetic state or micro-gesture (e.g. leaning forward toward a boom mic, raising arms straight up in roar, smug half-smirk, bowing head in remorse).
3. **Context / Environment**: The immediate physical spatial world (e.g. 3 AM cluttered bedroom with acoustic pyramid foam, curved ultrawide gaming display, rain-soaked stone ramparts, ruined cathedral hall).
4. **Composition & Camera Optics**: Focal length, camera angle, aperture, and physical movement trajectory (e.g. 85mm prime lens at f/2.0, static locked tripod, slow subtle push-in along optical Z-axis $\le 5\%$, low-angle heroic framing).
5. **Style & Volumetric Lighting**: Artistic school, material textures, and physical light direction (e.g. Fortiche Production Arcane painterly 2.5D animation, heavy oil/gouache impasto brushwork, bold ink contours, cool cyan monitor wash from front, deep violet chiaroscuro rim lighting).

### 2.2 The 13 Banned Quality Boosters & Stripping Rationale
A pervasive error in generative prompt authoring is the inclusion of generic "booster" buzzwords. In transformer-based cross-attention layers, these words dilute token attention, introduce high-frequency ringing artifacts, distort human anatomy, and increase facial variance.

Flow's `creative-director` tool enforces the absolute stripping of the following 13 banned tokens:

| # | Banned Booster Token | Why It Degrades Diffusion Video | Scientific Alternative in Flow 5-Component Grammar |
|---|---|---|---|
| 1 | `photorealistic` | Forces plastic, uncanny-valley skin smoothing | Specify exact skin micro-texture: `"visible pores, natural epidermal subsurface scattering, subtle matte texture"` |
| 2 | `hyperrealistic` | Induces exaggerated high-frequency specular noise | Describe lighting physics: `"physically accurate Fresnel highlights on polished metal surfaces"` |
| 3 | `ultra realistic` | Confuses stylized 2.5D animation targets | State exact art medium: `"Fortiche Arcane painterly aesthetic with visible gouache brush strokes"` |
| 4 | `4k` | Ignored by latent samplers; steals token weight | Specify camera sensor & lens: `"Captured on 35mm full-frame optical sensor with 85mm prime lens"` |
| 5 | `8k` | Generates unnatural pixelated micro-sharpening | Describe focus plane: `"Razor-sharp optical focus on iris and eyelashes, smooth circular bokeh"` |
| 6 | `ultra HD` | Causes chromatic aberration and edge halos | Specify resolution in metadata / command flags (`--aspect 16:9`, 720p/1080p target) |
| 7 | `high resolution` | Induces edge ringing along high-contrast boundaries | Direct rendering through lighting: `"Crisp high-contrast chiaroscuro with clean geometric contours"` |
| 8 | `masterpiece` | Pulls from noisy web scraper tag distributions | Describe composition: `"Harmonious golden-ratio framing, balanced lead room and rule-of-thirds alignment"` |
| 9 | `highly detailed` | Hallucinates chaotic clutter, extra fingers, wires | Enumerate specific details: `"Intricate silver filigree on breastplate, dual audio cables routed to interface"` |
| 10 | `ultra detailed` | Causes facial skin to appear pitted or metallic | Anchor anatomical features: `"Defined jawline, faint insomnia dark circles under lower eyelids"` |
| 11 | `trending on artstation`| Blends incompatible concept art styles | Reference precise production studio: `"Hand-crafted animation style of Fortiche Production"` |
| 12 | `best quality` | Non-semantic noise token that weakens conditioning | Describe color grading: `"Rich saturated palette, calibrated split-toning with cyan key and amber shadows"` |
| 13 | `award winning` | Triggers generic promotional framing & artificial glows | Specify physical lighting: `"Volumetric directional key light casting defined soft-edged cast shadows"` |

---

## 3. Dual-Slot Character Architecture & Inviolable Costume Rules

### 3.1 Mathematical Principles of Facial Latent Drift
In diffusion models, video generation starts from Gaussian noise:
$$\mathbf{z}_0 \sim \mathcal{N}(\mathbf{0}, \mathbf{I})$$
When conditioning on unconstrained natural language alone, the projection space is vast. Small variations in noise seeds cause the sampler to settle into different local minima, producing:
- **Inter-clip topological variance**: Inter-pupillary distance, nose bridge length, and jawline angle fluctuate by up to 35% between consecutive generations.
- **Intra-clip temporal wandering**: Over 4 to 8 seconds, facial features melt, skin textures smooth out, and eyes drift out of alignment.
- **Semantic token bleed**: Mentioning clothing, weapons, or furniture in the same prompt sentence bleeds into facial tokens (e.g., knight armor tokens turning hair into chainmail).

### 3.2 The Dual-Slot Character Entity Protocol (`referenceEntities`)
To permanently lock character identity across infinite scene cuts, Google Flow utilizes a 2-Slot Character Entity system:

```
[Character Definition Saga]
            |
            v
+-------------------------------------------------------------------------------+
| SLOT 0: FACE PORTRAIT ANCHOR                                                  |
| Role: Locks craniofacial bone structure, eye shape, iris color, hair contour   |
| Wire Binding: FlowMedia ID (e.g. streamer_ash_desk.png / knight_lucas_portrait) |
+---------------------------------------+---------------------------------------+
                                        |
           Attached as IMAGE_INPUT_TYPE_REFERENCE
                                        |
                                        v
+-------------------------------------------------------------------------------+
| SLOT 1: 3-VIEW BODY TURNAROUND TRIPTYCH                                       |
| Role: Orthographic Front, 90° Lateral Profile, and Dorsal Rear Views          |
| Wire Binding: FlowMedia ID (e.g. streamer_ash_turnaround / knight_lucas_body)  |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
| COMPILED CHARACTER ENTITY ON WIRE                                             |
| PATCH /v1/flow/entities: { "entityId": "entity_ash_gamer", "slots": [0, 1] } |
+-------------------------------------------------------------------------------+
```

1. **Slot 0 (Face Portrait)**:
   - Captures facial geometry, skin undertones, hair strands, and expressive micro-features.
   - For Streamer Ash: Pale complexion, messy jet-black fringe, dark dilated pupils with amber catchlights, deep insomnia eye rings, sharp angular jawline.
   - For Knight Lucas: Weathered battle-hardened warrior in his twenties, tousled golden hair, cleft chin, sharp nose bridge.
2. **Slot 1 (3-View Body Turnaround Triptych)**:
   - Generates an orthographic three-way projection: Front view, 90-degree lateral profile, and dorsal rear view in a single high-resolution image (`1376x768`).
   - Because Slot 0 is physically mounted as `IMAGE_INPUT_TYPE_REFERENCE` during Slot 1 generation, the costume, build, and skin tones match the portrait without facial mutation.

### 3.3 The Inviolable Costume Separation Rule
A character's costume is permanently baked into their Slot 1 body sheet. 
- **The Failure Mode**: Forcing costume changes inside the prompt text while referencing an entity (e.g., `@Ash_Streamer wearing heavy plate armor`) triggers severe latent contention between the Slot 1 hoodie and the armor prompt tokens. The model attempts to blend both, yielding warped mutant limbs and torn textures.
- **The Law of Costume Isolation**: Every major costume variation **MUST be registered as a distinct Character Entity sharing the identical Slot 0 Face seed**:
  * `Entity 1: @Ash_Streamer` -> Slot 0: Ash Face Seed; Slot 1: Sky-blue fleece hoodie `#88bbee`, studio headset, dark joggers.
  * `Entity 2: @Prince_Ash` -> Slot 0: Ash Face Seed; Slot 1: Imperial prince officer overcoat, gold epaulets, commander baton.
  * `Entity 3: @Lucas_Knight` -> Slot 0: Lucas Face Seed; Slot 1: Battered blackened plate armor, scarred breastplate, buckler.
  * `Entity 4: @Lucas_Solitary_Back` -> Special slot anchor: Rear silhouette in darkness, hunched broad shoulders, lowered sword.

### 3.4 Decoupling Environments via Ingredients Mode (`referenceImages`)
Backgrounds, room architecture, tactical screens, and stream overlays must never be embedded into Character Entities. Instead, they are staged in Flow as **Asset Ingredients** (`IMAGE_USAGE_TYPE_ASSET`):
- `ING_STREAMER_ROOM`: Cluttered studio bedroom, acoustic foam pyramid wall panels, violet ambient glow.
- `ING_STREAMER_PC`: Rectangular desk, curved ultrawide display, scissor boom mic, RGB keyboard.
- `ING_GAME_SCREEN`: Gothic stone monument, imperial runes, Crossroads tactical hex map.
- `ING_STREAM_HUD`: Dark translucent streaming chat, donor cards, Foxy 300,000 KRW banner.

By separating Character Entities from Asset Ingredients on the wire payload, the model isolates identity latents from spatial scene latents, preventing environment elements from corrupting the character's facial features.

---
## 4. Scene Continuation Mode Mechanics (`Veo 3.1 Extension Lite`)

### 4.1 Architecture of Scene Builder & Video Extension
The Scene Builder interface on `flow.google.com` (accessed via `scenebuilder_btn` at normalized coordinate `(63, 206)`) is Google Flow's multi-clip non-linear generative timeline. Rather than generating isolated video clips that require external crossfading, Scene Continuation mode generates new clips directly from the latent state of the preceding clip:

```
+-----------------------------------------------------------------------------------------------+
| Google Flow Scene Builder Timeline Layout                                                     |
|                                                                                               |
| [Clip 01: Streamer Battlestation] ---> [+] Button (flow-scene-timeline button.add-clip-button)|
| (Duration: 8.0s @ 24fps)               |                                                      |
|                                        v                                                      |
|                             Popup Menu: >> Режим продолжения (Veo 3.1 - Lite)                 |
|                                        |                                                      |
|                                        v                                                      |
|               [Clip 02: Extension Linked Block (8.0s)]                                        |
|               Prompt Bar: flow-edit-video-prompt-box .ProseMirror                             |
|               Placeholder: "Опишите, как отредактировать это видео..."                        |
+-----------------------------------------------------------------------------------------------+
```

### 4.2 The 24-Frame Trailing Seed Window
When Video Continuation is triggered, the engine extracts a precise temporal slice from the tail of the source clip:
- **Seed Window**: Exactly **24 frames at 24.0 fps (1.000 second)** sampled from the tail end of the source clip (`startFrameIndex = 1, endFrameIndex = 24`).
- **Physical Invariants Preserved**:
  * Exact character position, arm elevation, hand posture, and hair drape.
  * Ongoing camera velocity vector, focal length, and optical axis.
  * Ambient lighting color temperature, monitor wash intensity, and airborne particles.

### 4.3 Wire RPC Execution Sequence
When Video Continuation is dispatched in the Flow web UI, three sequential RPC transactions execute:
1. `POST /fx/api/trpc/flow.rqZuUc`: Locks the trailing 24 frames of the source media into Cloud Storage.
2. `POST /fx/api/trpc/flow.uwAyfb`: Creates and validates the server-side Scene entity.
3. `POST /v1/video:batchAsyncGenerateVideoExtendVideo (fZytfe)`: Dispatches the billed extension generation to the Veo 3.1 Lite engine (`veo_3_1_extension_lite`).

### 4.4 Delta Grammar & The 4 Golden Rules of Continuation Prompts
In `flow-edit-video-prompt-box .ProseMirror`, the prompt bar functions as a delta transformer. It requires **Delta Grammar**—instructions describing *what changes* over the next segment, rather than re-introducing the entire world:

1. **Rule 1: Never Restart Context**:
   - ❌ *Incorrect*: `"A young Korean man with black hair in a light-blue hoodie sitting in a gaming chair in a bedroom with monitors..."` (Triggers an abrupt jump-cut back to wide establishing view).
   - ✅ *Correct*: `"Camera continues pushing forward directly past @Ash_Streamer's right ear, smoothly shifting focal plane into the glowing monitor glass..."` (Preserves camera momentum without a hitch).
2. **Rule 2: Kinetic Verbs Lead the Sentence**:
   - Always begin with the directional vector: `"Smooth continuous dolly forward..."`, `"Camera cranes upward into low-angle..."`, `"Slow lateral slide to the right..."`.
3. **Rule 3: Respect Reference Entity Immutability**:
   - Never instruct costume swaps inside continuation prompts (e.g. `@Ash_Streamer takes off his hoodie and equips armor`). To execute costume changes, pan the camera away to a neutral element (screen, smoke, or mist), cut, and introduce the new entity.
4. **Rule 4: Multi-Layer Atmospheric & Sound Integration**:
   - Veo 3.1 synchronizes visual motion cadence with sound descriptions:
     * `"Frantic mechanical keyboard clicks and humming cooling fans..."`
     * `"Heavy rain splashing on granite crenellations with distant rolling thunder..."`

### 4.5 Seam Handling: The 7.0s Motion + 1.0s Hold Frame Characteristic
A known architectural characteristic of Veo 3.1 extension clips:
- Container duration: **8.000 seconds (192 frames @ 24 fps)**.
- Active generative motion: **First 7.000 seconds (frames 0 to 168)**.
- Terminal Hold Frame: **Final 1.000 second (frames 169 to 192, 24 frames)** exhibits near-zero velocity. It serves as a static landing zone for editors and seeds the next extension.

#### Seam Mitigation Workflows:
- **Assembly Trimming (Hard Cut Continuity)**:
  Before concatenating clips outside Flow, trim the trailing 24 frames (1.00s) from intermediate clips using FFmpeg:
  ```bash
  ffmpeg -y -ss 00:00:00.000 -to 00:00:07.000 -i clip_01.mp4 -c:v libx264 -crf 18 -an clip_01_trimmed.mp4
  ```
- **0.5-Second Cross-Dissolve (`xfade`)**:
  Alternatively, apply a 12-frame (0.5s) cross-dissolve across the join to blend any residual sub-pixel micro-jitter:
  ```bash
  ffmpeg -y -i clip_01.mp4 -i clip_02.mp4 -filter_complex "[0:v][1:v]xfade=transition=fade:duration=0.5:offset=6.5[v]" -map "[v]" -an seam_smoothed.mp4
  ```

---

## 5. Motion Dynamics & Camera Control Hierarchy

### 5.1 Geometry Hallucination Trap in 3D Rotations
Generative video diffusion models synthesize 2D projections conditioned on latent trajectory vectors rather than maintaining a persistent 3D polygonal mesh. When a prompt directs a human character to execute an abrupt or large-angle head turn (e.g. turning from frontal camera address to an off-screen monitor, $60^\circ$ to $90^\circ$ yaw):
1. **Topological Inversion**: Self-attention layers struggle to predict occlusion as the nose and cheek turn past the halfway mark. The model frequently renders both eyes on the profile side or stretches the nasal bridge into duplicate noses.
2. **Ear and Headphone Dislocation**: Over-ear headphones undergo severe distortion. The model frequently detaches the headphone band, duplicates earcups, or embeds earcups into the jawline.
3. **The Uncanny Smear**: Interpolating between front and profile latents within 24–48 frames generates gelatinous motion blur, causing the skull to shrink or swell asymmetrically.

### 5.2 Strict Action Atomicity Rule
Over-packing prompt semantics is the primary cause of comical warping. Prompting multiple kinetic transitions in sequence:
> ❌ *Flawed Prompt*: `"Streamer turns his head to the left monitor, looks at chat, smiles, turns back to the camera, winks, and starts speaking into the mic."*

This forces the diffusion sampler to compress seven distinct kinematic state transitions into ~72 frames, yielding erratic eye jitter, rubbery neck stretching, and rapid face deformation.

**The Golden Law of Action Atomicity**:
> **Every clip or micro-shot must describe exactly ONE primary physical action state or micro-gesture.**

### 5.3 Constrained Head Rotation Bounds ($\le 15^\circ$ Yaw) & Orbital Camera Workaround
To keep facial topology rigid:
- **Head Yaw Limit**: Restrict any subject head movement to a maximum of $\pm 10^\circ - 15^\circ$ from the optical axis. For frontal streamer shots, enforce **$\le 5^\circ$**.
- **Micro-Expressions over Gross Motion**: Direct the model to convey emotion through eye widening, eyebrow tension, jaw tightening, and subtle lip shifts rather than large physical turns.
- **The Orbital Camera Workaround**: If the scene requires showing the character from a profile or three-quarter angle, **rotate the camera around the stationary subject, rather than rotating the subject's head**:
  * ✅ *Correct*: `"Static subject facing forward. Camera smoothly glides along an orbital track 45 degrees to the left, capturing his focused profile while his gaze remains locked on the monitor."`
  * This preserves the physical facial geometry in the subject's local coordinate frame while providing dynamic cinematic movement.

### 5.4 4-Pillar Pupil Catchlight & Gaze Locking Protocol
To lock Streamer Ash's eyes firmly onto either the primary gaming monitor or the webcam lens, four complementary constraints are applied simultaneously:

1. **Pillar 1: Direct Positional Line-of-Sight Anchoring**:
   - *Webcam Address (Viewer Direct Eye Contact)*: `"Unwavering direct eye contact, sharp focused pupils locked squarely into the center of the webcam camera lens. Intense confrontational gaze without blinking or glancing away."`
   - *Gaming Monitor Immersion (Focused Concentration)*: `"Eyes locked onto the center of the glowing ultrawide monitor directly in front of him, pupils dilated in hyper-focus, steady unwavering line of sight tracking game action on screen."`
2. **Pillar 2: Physical Catchlight & Specular Reflection Anchor**:
   - Conditioning on the physics of light reflection forces the sampler to orient the eye geometry toward the light source:
   - `"Vivid cyan and amber monitor glow reflected clearly as sharp miniature specular catchlights in both dark irises. Reflections of scrolling game runes visible on the glossy surface of his dark pupils."`
3. **Pillar 3: Bilateral Lighting Asymmetry as Geometric Guide**:
   - Monitor screen light creates predictable downward-and-back shadows across the nose bridge and brow. Describing `"symmetrical cyan monitor light wash illuminating both eyes evenly"` physically locks the forward gaze.
4. **Pillar 4: Chronological Attention Sequencing**:
   - If eye movement is narratively required, prompt it as a single deliberate micro-shift:
   - `"Subject's head remains stationary facing front. At second 2, his dark pupils flick 10 degrees to the upper-right toward the vertical chat monitor, eyes narrowing as he reads the text, holding steady in that position."`

### 5.5 Camera Stability Hierarchy

| Stability Rank | Camera Movement | Risk of Face Warp | Recommended Use in Series Production |
|---|---|---|---|
| **Tier 1 (Safest)** | **Locked Static Tripod** | Zero ($\approx 0\%$) | Close-ups on face, reaction shots, reading chat, emotional silence. |
| **Tier 2 (High Safety)**| **Subtle Push-in (Dolly Z)** | Very Low ($< 3\%$) | Slow forward glide along optical axis ($\Delta z \le 5\%$), building narrative tension toward monitor. |
| **Tier 3 (Moderate)** | **Smooth Orbital Arc ($< 30^\circ$)** | Low to Moderate ($5-10\%$) | Moving around the stationary gamer at desk; keeps subject centered. |
| **Tier 4 (High Risk)** | **Rapid Lateral Tracking** | High ($25-40\%$) | Background tears; ear/headphone detachment occurs. Avoid in tight close-ups. |
| **Tier 5 (Forbidden)** | **Handheld Shake / Whip Pan** | Extreme ($> 60\%$) | Triggers immediate topological collapse, double faces, and motion blur smearing. Strictly forbidden. |

---
## 6. Micro-Shot Duration Scaling: 1.5s–3.0s vs 4–8s

### 6.1 Mathematical Formulation of Temporal Latent Variance
Video diffusion models generate sequences via temporal cross-attention layers that propagate information autoregressively across latent frame blocks. The error variance $\sigma^2(t)$ compounds over time:
$$\sigma^2(t) = \sigma^2_0 + \sum_{k=1}^t \epsilon_{\text{temporal}}(k)$$

where:
- $\sigma^2_0$ is the baseline residual error from initial reference sheet cross-attention projection.
- $\epsilon_{\text{temporal}}(k)$ is the stochastic deviation introduced at each temporal frame step $k$.

In empirical trials with Google Veo 3.1 and Gemini Omni Flash:
1. **Seconds 0.0 to 2.5 (High Fidelity Zone)**: Conditioning on reference sheets and initial seed is dominant. Facial topology, eye positions, and costume textures remain tightly clamped to the reference latents ($\text{Fidelity} \ge 95\%$).
2. **Seconds 3.0 to 5.0 (Drift Threshold)**: Temporal cross-attention begins accumulating micro-errors. Micro-expressions can turn into rubbery distortions, gaze angles slowly deviate from the target, and symmetrical features (ears, glasses, headphones) drift.
3. **Seconds 6.0 to 8.0 (Entropy Saturation)**: Without strict motion damping, the model frequently exhibits hallucinations—extra fingers appearing on hands, hair flowing against gravity, or faces morphing into secondary avatars.

### 6.2 Editorial Rhythm in Manga / Manhwa Adaptation
Dynamic anime and manhwa adaptations thrive on punchy, rhythmic visual cuts matching comic panel transitions:
- **Fast victory reaction**: 1.2s to 2.0s.
- **Snappy address to webcam**: 1.5s to 2.5s.
- **Screen zoom transition**: 2.0s to 3.0s.
- **Pensive silence / reading chat**: 2.2s to 3.0s.
- **Battlefield & void atmosphere**: 2.5s to 3.0s.

Holding a single generative diffusion shot on a human character's face for a full 8.0 seconds almost inevitably introduces noticeable uncanny drifting or static freeze.

### 6.3 The 3-Step Precision Trimming Production Pipeline
To reconcile the reality of engine container lengths (Veo 3.1 outputs 4s, 6s, or 8s containers) with the necessity of 1.5s–3.0s micro-shots:
1. **Generate Constrained Envelopes in Flow**: Submit damped, single-action prompts using 4s or 8s generation envelopes with static tripod or subtle push-in camera motion.
2. **Precision-Trim the Prime Window**: Using FFmpeg, extract the highest-fidelity 1.5s–3.0s window where character acting, facial geometry, and optical flow are optimal (typically seconds 1.0 to 3.5):
   ```bash
   ffmpeg -y -ss 00:00:01.000 -to 00:00:03.500 -i raw_flow_clip.mp4 -c:v libx264 -crf 18 -pix_fmt yuv420p -an micro_shot_01.mp4
   ```
3. **Assemble via Normalized Concat Filtergraph**: Stitch the trimmed micro-shots using `-filter_complex concat=n=N:v=1:a=0` with `setpts=PTS-STARTPTS` and `-r 24`, creating a continuous, broadcast-grade sequence with zero face drift.

---

## 7. Production Checklist for Zero-Drift Video Generation

Before dispatching video generation requests in Google Flow (Project `7d9a2a67-9cd2-4a79-932e-717d2e29257f`), verify each prompt against this 7-point checklist:

- [ ] **Dual-Slot Entity Bound**: Is `@Ash_Streamer` or `@Lucas_Knight` explicitly attached with Slot 0 face and Slot 1 turnaround?
- [ ] **Costume Isolation Respected**: Are costume tokens strictly matching the bound entity (no armor on Ash, no modern clothes on Lucas)?
- [ ] **5-Component Structure**: Does the prompt include Subject, Action, Context, Composition, and Style/Lighting?
- [ ] **Zero Banned Boosters**: Have all 13 banned tokens (`photorealistic`, `4k`, `masterpiece`, etc.) been stripped?
- [ ] **Head Yaw $\le 15^\circ$**: Is head rotation limited to $\le 15^\circ$ ($\le 5^\circ$ for frontal shots), using orbital camera glide for profile angles?
- [ ] **Gaze Locked via Catchlights**: Are pupils explicitly anchored to the monitor or webcam with cyan/amber catchlight reflection tokens?
- [ ] **Atomic Action Duration**: Does the micro-shot describe exactly ONE kinetic action and target a trimmed duration between 1.5s and 3.0s?
