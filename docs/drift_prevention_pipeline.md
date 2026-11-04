# Technical Pipeline for Detail-Drift Prevention & Scene Continuation

**Document ID**: `PIPE-DRIFT-PREV-001`  
**Version**: 1.0.0 (Production Master)  
**Target Platform**: Google Flow (`flow.google.com`) & Google Veo 3.1 (`veo_3_1_extension_lite`, `veo_3_1_t2v_fast_audio`)  
**Target Project**: `https://flow.google.com/project/7d9a2a67-9cd2-4a79-932e-717d2e29257f`  
**Benchmark Scope**: "I Became the Tyrant of a Defense Game" (Manga Intro Sequence, Frames 001–026)  
**Style Benchmark**: Fortiche Production Arcane Painterly Aesthetic (Oil/Gouache Impasto, 3D Chiaroscuro Rim)  

---

## 1. Executive Summary & Purpose

In generative episodic animation, **detail drift** is the compounding divergence of character geometry, costume heraldry, palette grading, and architectural layout across successive shots. Text-to-video diffusion samplers reinitialize from stochastic noise on every clip generation, causing character faces to warp, costumes to mutate, and camera coordinates to snap disjointedly between cuts.

This document establishes the authoritative, end-to-end technical pipeline to eliminate detail drift in Google Flow for the prologue sequence (Frames 001–026) of *Tyrant of the Tower Defense Game*. The pipeline locks identity and continuity through three interlocking mechanisms:
1. **Durable Identity Anchoring (Ingredients & Character Entities)**: Binding high-resolution canonical reference sheets to persistent `@Entity` tokens (Slot 0 Face and Slot 1 Body Turnaround) and asset ingredients (`referenceImages`).
2. **Kinetic Continuity via Scene Continuation Mode**: Employing Google Veo 3.1 Lite (`>> Режим продолжения (Veo 3.1 - Lite)` / `veo_3_1_extension_lite`) to seed every successive clip from the trailing 24 frames (1.0 second @ 24 fps) of the preceding clip buffer.
3. **Delta-Grammar Prompt Engineering**: Enforcing structured prompts that fix Fortiche Arcane style tokens and character descriptors while restricting prompt modifications to camera vectors, lighting shifts, and physical actions across 7 cinematic narrative beats.

---

## 2. Detail-Drift Root Causes & The Three-Tier Mitigation Framework

### 2.1 The Mathematics of Latent Drift in Diffusion Models
When generating a video segment $S_k$ via text-to-video (T2V), the model samples:
$$\mathbf{z}_0^{(k)} \sim \mathcal{N}(\mathbf{0}, \mathbf{I})$$
Conditioned solely on prompt embeddings $\mathbf{c}_k = \text{TextEncoder}(P_k)$, the reverse denoising path converges to an arbitrary local minimum:
$$\mathbf{z}_0^{(k)} = \mathcal{D}\left( \mathbf{z}_T^{(k)}, \mathbf{c}_k \right)$$
Even when $P_k$ and $P_{k+1}$ share 95% identical tokens, the variance between seeds $\mathbf{z}_T^{(k)}$ and $\mathbf{z}_T^{(k+1)}$ causes dramatic visible discrepancies:
- **Facial Geometry**: Morphing jawlines, shifting eye spacing, and changing perceived age.
- **Costume Permutations**: Inconsistent hood drawstrings, changing fabric textures, and shifting chest emblems.
- **Lighting Discontinuities**: Key light direction flipping from stage-left to stage-right across cuts.
- **Palette Wandering**: Sky-blue fleece shifting to navy, or dark charcoal shadows turning warm sepia.

### 2.2 The Three-Tier Flow Mitigation Framework
To ensure frame-accurate continuity, Google Flow decouples static identity constraints from dynamic kinetic instructions:

```
+-----------------------------------------------------------------------------------------+
| LEVEL 1: STRUCTURAL IDENTITY (Character Entities & Ingredients)                         |
| - Fixed reference sheets registered in Project Asset Pool                               |
| - Slot 0 (Face close-up) + Slot 1 (3-view turnaround triptych)                          |
| - Injected via 'referenceEntities' and 'referenceImages' on wire API                    |
| - Invariant: Facial proportions, hoodie silhouette, plate armor damage stay frozen      |
+-----------------------------------------------------------------------------------------+
                                             |
                                             v
+-----------------------------------------------------------------------------------------+
| LEVEL 2: TEMPORAL KINETIC CONTINUITY (Scene Builder Continuation Mode)                  |
| - Initiated via '>> Режим продолжения (Veo 3.1 - Lite)'                                 |
| - Trailing 24 frames (1.0s @ 24fps) extracted from Clip N as seed window                |
| - Injected via 'continuationSeedWindow' into Veo 3.1 extension pipeline                 |
| - Invariant: Velocity vectors, monitor phosphor glow, and particle momentum carry over  |
+-----------------------------------------------------------------------------------------+
                                             |
                                             v
+-----------------------------------------------------------------------------------------+
| LEVEL 3: DELTA-GRAMMAR PROMPT STEERING (Prompt Bar ProseMirror)                         |
| - [Fortiche Arcane Style Anchor] + [@Entity Mention] + [Delta Action] + [Camera Vector] |
| - No conflicting re-descriptions of character physical features                         |
| - Invariant: Only verbs, spatial coordinates, and atmospheric lighting are modulated    |
+-----------------------------------------------------------------------------------------+
```


---

## 3. Google Flow Reference Sheet (Ingredients) Upload & Entity Binding Protocol

### 3.1 Character Entity Registration (Dual-Slot Architecture)
In Google Flow, consistent character performance requires creating persistent **Character Entities** (`referenceEntities`). Each character is bound using a two-slot anchor system:
- **Slot 0 (Face Profile & Features)**: High-resolution tight crop of the head and face showing facial contours, eye color, insomnia rings, expression range, and hair parting.
- **Slot 1 (Full-Body Turnaround Triptych)**: Clean three-angle view (front, 3/4, side/rear) establishing costume cut, fold geometry, drapery, footwear, and accessory attachment points.

#### 3.1.1 Canonical Entity Definitions
For Episode 1 Intro Sequence, two primary Character Entities and one special silhouette entity are registered:

1. **`@Ash_Streamer` (Main Character / Streamer)**:
   - **Slot 0 Face Anchor**: `output/canonical_arcane_concepts/streamer_ash_desk.png` (tight crop of face illuminated by monitor phosphor, dilated pupils, messy jet-black fringe, dark insomnia eye rings).
   - **Slot 1 Body Turnaround**: `output/canonical_arcane_concepts/streamer_ash_turnaround.png` (triptych turnaround in oversized sky-blue fleece hoodie `#88bbee`, dark joggers, pushed-up sleeves, over-ear studio headphones).
   - **Role**: Drives Beat 1, Beat 2, Beat 4, Beat 5, and Beat 6.

2. **`@Lucas_Knight` (Vanguard Knight Lucas)**:
   - **Slot 0 Face Anchor**: `output/canonical_arcane_concepts/knight_lucas_portrait.png` (noble chiseled portrait, tousled golden hair clotted with soot and sweat, royal-blue irises, thin cheek scar).
   - **Slot 1 Body Turnaround**: `output/canonical_arcane_concepts/knight_lucas_turnaround.png` (triptych turnaround in battle-damaged silver plate armor, monster claw gouges, scorched breastplate, tattered royal-blue mantle).
   - **Role**: Drives Beat 7 (Rampart Battle) and Game MVP card.

3. **`@Lucas_Solitary_Back` (The Tragic Silhouette Anchor)**:
   - **Special Slot Anchor**: `output/canonical_arcane_concepts/knight_lucas_solitary_back.png` (broad shoulders hunched forward, dented backplate, frayed cape tassels, heavy broadsword resting tip-down, pitch-black void).
   - **Role**: Drives Beat 7 climax (Frames 025 -> 026 transition into infinite darkness).

#### 3.1.2 Entity Registration Wire API (`flow.createEntity`)
When registering `@Ash_Streamer` in project `7d9a2a67-9cd2-4a79-932e-717d2e29257f`, Flow dispatches:
```json
POST /fx/api/trpc/flow.createEntity
{
  "projectId": "7d9a2a67-9cd2-4a79-932e-717d2e29257f",
  "name": "Ash_Streamer",
  "description": "Hardcore Korean tactical gamer in sky-blue fleece hoodie and black studio headphones",
  "entityType": "ENTITY_TYPE_CHARACTER",
  "slots": [
    {
      "slotIndex": 0,
      "slotType": "SLOT_TYPE_FACE",
      "imageGcsUri": "gs://flow-prod-assets/7d9a2a67/streamer_ash_desk_face.png"
    },
    {
      "slotIndex": 1,
      "slotType": "SLOT_TYPE_BODY_TURNAROUND",
      "imageGcsUri": "gs://flow-prod-assets/7d9a2a67/streamer_ash_turnaround.png"
    }
  ]
}
```

### 3.2 Asset Ingredients Registration (`referenceImages`)
Environmental plates, game screens, and broadcast HUDs are registered as **Asset Ingredients** (`IMAGE_USAGE_TYPE_ASSET`). Unlike character entities, assets condition the background canvas, lighting temperature, and UI framing without introducing facial latents:

| Ingredient Identifier | Source Canonical File | Resolution | Conditioning Function |
|---|---|---|---|
| `ING_STREAMER_ROOM` | `output/canonical_arcane_concepts/streamer_room_environment.png` | 1376x768 (16:9) | Locks dark bedroom layout, acoustic foam pyramid wall tiles, and violet LED ambient glow |
| `ING_STREAMER_PC` | `output/canonical_arcane_concepts/streamer_pc_desk_closeup.png` | 1376x768 (16:9) | Locks scissor boom arm mic, desktop mixer, curved ultrawide monitor, and RGB keyboard |
| `ING_GAME_SCREEN` | `output/canonical_arcane_concepts/game_save_the_empire_screen.png` | 1376x768 (16:9) | Locks gothic stone monument, imperial rune typography, and tactical fortress map |
| `ING_STREAM_HUD` | `output/canonical_arcane_concepts/stream_overlay_chat_donation.png` | 1376x768 (16:9) | Locks dark translucent streaming HUD, live chat column, and golden 300,000 KRW donation card |
| `ING_MASTER_SHEET` | `output/canonical_arcane_concepts/master_contact_sheet.png` | 2112x1376 (Grid) | Master reference sheet used for global multi-turn consistency auditing |

### 3.3 DOM Selectors & UI Binding Steps in Flow Project Editor
To bind reference ingredients and entities inside Project `7d9a2a67-9cd2-4a79-932e-717d2e29257f`:
1. **Open Ingredients Drawer**: Click `button.add-menu-trigger` (`X=120, Y=140`) on the left navigation dock.
2. **Upload Concept Artifacts**: Click `button.sidebar-upload-btn` (`X=145, Y=210`), select all 9 PNG artifacts from `output/canonical_arcane_concepts/`.
3. **Wait for Ingestion**: Poll until `button.detail-add-to-prompt-btn:not([disabled])` is active (timeout: 25,000ms).
4. **Create Character Entity**: In the asset detail modal, select `Create Entity` -> assign name `Ash_Streamer` -> assign Slot 0 to face crop, Slot 1 to turnaround -> click `Save Entity`. Repeat for `Lucas_Knight`.
5. **Assign Ingredient to Prompt**: Click on the uploaded asset card -> click `Add to Prompt as Reference` -> verifies tag `[REF: ING_STREAMER_ROOM]` appears in the active composer.


---

## 4. Scene Continuation Mode Protocol (`Veo 3.1 - Lite` / `veo_3_1_extension_lite`)

### 4.1 Theoretical Mechanics of Video Extension
Google Veo 3.1 Lite's Continuation Mode (`>> Режим продолжения (Veo 3.1 - Lite)`) operates by conditioning the generative latent trajectory on a pre-existing video segment rather than pure text noise:
$$\mathbf{z}_0^{[t_0, t_0 + \Delta t]} = \mathcal{G}_{\text{extension}}\left( \mathbf{z}_{\text{seed}}^{[t_0 - 1.0s, t_0]}, P_{\text{continuation}}, \theta \right)$$
The engine samples a contiguous **seed window of exactly 24 frames at 24.0 fps (1.0 second)** from the trailing boundary of the previous clip. This seed window preserves:
1. **Dynamic Lighting Invariants**: Directional screen wash from computer monitors or firelight from burning siege engines.
2. **Velocity & Optical Flow Vectors**: Ongoing camera motion (dolly in, pan, tilt) and subject micro-kinetics (hair motion, blinking, shoulder breathing).
3. **Atmospheric Density**: Drifting smoke, embers, rain streaks, and lens flares.

### 4.2 Exact Step-by-Step UI Invocation Protocol
To execute a seamless continuation in Google Flow Scene Builder:
1. **Locate Target Clip on Timeline**: In `flow-scene-timeline`, click on the trailing edge of the completed clip (e.g. Clip 1).
2. **Trigger Extension Menu**: Click the contextual `+` trigger button:
   ```css
   flow-scene-timeline button.add-clip-button
   ```
3. **Select Continuation Mode**: From the Material CDK overlay popup, select the continuation item:
   ```css
   .cdk-overlay-pane [role='menuitem']:has(mat-icon:text-is('keyboard_double_arrow_right'))
   ```
   *(UI label: `>> Режим продолжения (Veo 3.1 - Lite)` or `Extend Video (Veo 3.1 - Lite)`)*.
4. **Inspect Generated Extension Stub**: Flow instantiates a new 8-second linked clip block immediately following Clip 1 with a link glyph indicating continuous latent chaining.
5. **Open Video Edit Prompt Bar**: Focus the prompt box:
   ```css
   flow-edit-video-prompt-box .ProseMirror
   ```
   *(Placeholder: `Опишите, как отредактировать это видео...` / `Describe how to continue or edit this video...`)*.
6. **Inject Delta Prompt**: Input the specific transition prompt following the Delta-Grammar specification (Section 5). Do NOT re-describe immutable character traits; only state the kinetic camera and narrative delta.
7. **Submit & Monitor Generation**: Press `Enter` or click `button.generate-clip-btn`. Flow issues the continuation RPC and begins rendering.

### 4.3 Wire RPC Protocol (`rqZuUc`, `uwAyfb`, `fZytfe`)
Under the hood, Flow dispatches the continuation through three sequential RPC calls:
1. **`rqZuUc` (Clip Buffer Lock)**:
   Extracts and encodes the trailing 24 frames (`t=7.0s` to `t=8.0s`) of Clip $N$ into an ephemeral MP4 seed chunk stored in Cloud Storage.
2. **`uwAyfb` (Extension Dispatch)**:
   Sends the generation payload specifying model `veo_3_1_extension_lite`, seed URI, bound `@Entity` pointers, and delta prompt text.
3. **`fZytfe` (Timeline Splice)**:
   Upon render completion, stitches the new 8.0s clip onto the timeline, locking the seam boundary.

### 4.4 Seam Trimming & Audio Crossfade Protocol
Veo 3.1 continuation generates an 8.0-second clip where the initial 1.0s blends from the seed frame. To achieve a perfectly fluid, broadcast-grade cut without duplicate motion or freeze frames:
1. **Frame Trim Rule**: Each raw clip contains 7.0 seconds of novel kinetic action + 1.0 second of motion transition.
2. **FFmpeg Assembly Filter**:
   When exporting the full sequence outside Flow, concatenate clips using an exact 0.5s or 1.0s cross-dissolve (`xfade`) to smooth any sub-pixel boundary micro-jitter:
   ```bash
   ffmpeg -i clip01.mp4 -i clip02.mp4 -filter_complex \
     "[0:v][1:v]xfade=transition=fade:duration=0.5:offset=7.5[v]" \
     -map "[v]" -c:v libx264 -pix_fmt yuv420p intro_sequence_master.mp4
   ```


---

## 5. Exact 7-Beat Narrative Continuity Chain (Frames 001–026)

Every narrative beat in the intro sequence translates into an exact Google Flow clip configuration with locked ingredients, continuation anchors, and verified Fortiche Arcane prompts.

```
+-----------------------------------------------------------------------------------------------------------------------------------------+
| BEAT 1 (00:00-00:08) | BEAT 2 (00:08-00:16) | BEAT 3 (00:16-00:24) | BEAT 4 (00:24-00:32) | BEAT 5 (00:32-00:40) | BEAT 6 (00:40-00:48) | BEAT 7 (00:48-00:56) |
| CRT Fanfare & Roar   | Shout into Boom Mic  | Gothic Empire Portal | Crossroads Tactical  | 300k KRW Donation    | Chat Mourning Priest | Rampart to Void      |
| Frames 001-003       | Frames 004, 008, 010 | Frames 005-007       | Frames 009, 011-013  | Frames 014-017       | Frames 018-022, 024  | Frames 023, 025-026  |
| Clean: frame001/002  | Clean: frame004      | Clean: frame005      | Clean: frame009/011  | Clean: frame014/016  | Clean: frame020/021  | Clean: frame023/026  |
+-----------------------------------------------------------------------------------------------------------------------------------------+
```

### 5.1 Beat 1: CRT Game Clear Fanfare to Raw Gamer Triumph (Frames 001–003)
- **Narrative Action**: Retro CRT monitor bursts into pixel fireworks and golden clear runes ("CONGRATULATIONS! GAME CLEAR!"). The camera pulls back dynamically as Streamer Ash leaps upward from his ergonomic gaming chair, roaring with both arms raised straight into the air in overwhelming ecstasy after a decade of failure.
- **Manga Panels**: Frame 001 (CRT Screen), Frame 002 (Ecstatic Victory Pose - Keyframe 01), Frame 003 (Face Close-Up).
- **Source Anchor Images**: `output/ttd_ep01_manga_transitions/clean_frames/keyframe_01_frame002.png` & `ep01_frame_001_clean.png`.
- **Bound Ingredients**:
  * Character Entity: `@Ash_Streamer` (Slot 0 Face, Slot 1 Body Turnaround).
  * Asset Ingredient: `ING_STREAMER_ROOM` (dark bedroom, acoustic foam, violet LEDs).
  * Asset Ingredient: `ING_STREAMER_PC` (ultrawide monitor, RGB keyboard).
- **Continuation Mode**: `Initial Clip Generation` (T2V / R2V with Image Reference Anchor).
- **Aspect Ratio & Frame Profile**: 16:9 widescreen (`1280x720`), 24.0 fps, 8.0 seconds.
- **Exact Prompt Template**:
  ```text
  Fortiche Production Arcane painterly style, visible oil and gouache impasto brushwork, bold graphic ink contours, 3D chiaroscuro volumetric rim lighting. High-speed cinematic dolly pullback from a glowing CRT gaming monitor displaying vibrant golden pixel fanfare runes into a dim nighttime gaming studio. Subject @Ash_Streamer wearing his oversized sky-blue fleece hoodie with pushed-up sleeves and matte-black studio headphones leaps out of his black ergonomic gaming chair, throwing both arms straight into the air in a roaring victory celebration. Intense cold cyan monitor glow illuminates his torso and sweat-beaded forehead, casting long dramatic shadows against the dark acoustic foam wall panels behind him. Camera smoothly tracks upward with his ecstatic motion. Sound of digital retro victory fanfare dissolving into breathless human shouting and rattling keyboard keys. No text, no captions, no watermark.
  ```

### 5.2 Beat 2: Direct Shouting into Boom Mic & Screen Address (Frames 004, 008, 010)
- **Narrative Action**: Continuing directly from the victory leap, Ash drops forward onto the desk, leaning aggressively into the cardioid boom microphone, shouting his raw relief to the webcam. He then straightens slightly, cocking his head with a confident, charismatic smirk and pointing his index finger straight at the camera lens: *"See? What did I tell you all?"*.
- **Manga Panels**: Frame 004 (Shouting into mic), Frame 008 (Smug finger point), Frame 010 (Persona introduction).
- **Source Anchor Images**: `output/ttd_ep01_manga_transitions/clean_frames/ep01_frame_004_clean.png` & `ep01_frame_008_clean.png`.
- **Bound Ingredients**:
  * Character Entity: `@Ash_Streamer` (lock sky-blue fleece `#88bbee`, insomnia eye rings, headset).
  * Asset Ingredient: `ING_STREAMER_PC` (scissor boom mic, foam pop filter, desk perimeter).
- **Continuation Mode**: `>> Режим продолжения (Veo 3.1 - Lite)` seeded from Beat 1 trailing 24 frames.
- **Continuation Window**: Exactly 24 frames @ 24fps (1.0s seed).
- **Exact Prompt Template**:
  ```text
  Continue directly from previous clip. Fortiche Production Arcane painterly style, visible gouache impasto textures, volumetric chiaroscuro rim lighting. Subject @Ash_Streamer leans aggressively forward toward the foreground studio condenser microphone on its scissor boom arm, teeth bared in an ecstatic victorious shout with hair strands fluttering. The camera smoothly glides around to a dynamic 3/4 broadcast close-up as Ash leans back slightly, eyes sparkling with adrenaline, flashing a charismatic, smug half-smirk directly into the camera lens and pointing his index finger forward with confident authority. Dynamic cyan and lavender monitor luminescence pulses across the desk surface, reflecting off the metal boom arm and keyboard keycaps. Seamless kinetic momentum from the preceding clip.
  ```

### 5.3 Beat 3: Screen Immersion: Dissolve from Streamer into Gothic Empire Monument (Frames 005–007)
- **Narrative Action**: As Ash points at the screen, the camera pushes rapidly into his dark, dilated pupils. A seamless match-dissolve carries the viewer through the monitor glass into the mythic game world. Emerging from swirling golden mana dust is the monolithic weathered granite monument of Crossroads fortress, deeply chiseled with the imperial title "SAVE THE EMPIRE".
- **Manga Panels**: Frame 005 (Title Monument - Keyframe 02), Frame 006 (Decade of Failure), Frame 007 (The Sole Clearer).
- **Source Anchor Images**: `output/ttd_ep01_manga_transitions/clean_frames/keyframe_02_frame005.png`.
- **Bound Ingredients**:
  * Character Entity: `@Ash_Streamer` (initiating dissolve).
  * Asset Ingredient: `ING_GAME_SCREEN` (gothic granite portal, ancient runes, golden dust motes).
- **Continuation Mode**: `>> Режим продолжения (Veo 3.1 - Lite)` seeded from Beat 2 trailing 24 frames.
- **Continuation Window**: Exactly 24 frames @ 24fps (1.0s seed).
- **Exact Prompt Template**:
  ```text
  Continue directly from previous clip. Fortiche Production Arcane painterly style, heavy impasto brushstrokes, rich chiaroscuro atmosphere. Rapid cinematic push-in toward the streamer's dark eyes dissolves seamlessly into the surface of the ultrawide monitor. The digital screen dissolves into a sprawling dark-fantasy world at twilight. A massive ancient gothic stone portal emerges from swirling grey mist and golden mana motes. Deep Romanesque chisels carve the majestic words SAVE THE EMPIRE into cracked weathered granite blocks draped in dead creeping vines. Cold mountain wind sweeps across the stonework, scattering glowing embers and dust across the letterbox frame. Solemn, epic imperial brass fanfare swells. Seamless visual dissolve from the preceding shot.
  ```

### 5.4 Beat 4: Crossroads Tactical War Room Map to Shadowy Bedroom (Frames 009, 011–013)
- **Narrative Action**: The camera tilts downward from the gothic monument into a top-down isometric war-room tactical map of Crossroads fortress. High stone walls, bastion towers, and glowing cyan tactical defense grids are swarmed by red hostile vector arrows. The camera then cranes upward and pulls back, revealing that the map is running on the curved monitor in Ash's pitch-black bedroom studio.
- **Manga Panels**: Frame 009 (Tactical defense grid), Frame 011 (Dark bedroom establishing shot), Frame 012 (Hardcore niche), Frame 013 (Channel profile UI).
- **Source Anchor Images**: `output/ttd_ep01_manga_transitions/clean_frames/ep01_frame_009_clean.png` & `ep01_frame_011_clean.png`.
- **Bound Ingredients**:
  * Asset Ingredient: `ING_GAME_SCREEN` (tactical fortress map, hex defense grid).
  * Asset Ingredient: `ING_STREAMER_ROOM` (dark room, acoustic foam tiles, blackout curtains).
  * Character Entity: `@Ash_Streamer` (silhouette in chair).
- **Continuation Mode**: `>> Режим продолжения (Veo 3.1 - Lite)` seeded from Beat 3 trailing 24 frames.
- **Continuation Window**: Exactly 24 frames @ 24fps (1.0s seed).
- **Exact Prompt Template**:
  ```text
  Continue directly from previous clip. Fortiche Production Arcane painterly aesthetic, bold ink contours, tactile impasto paint textures. Camera pans down to reveal an intricate military tactical map of Crossroads fortress drawn on aged imperial vellum parchment, overlaid with pulsing cyan defense grid lines and aggressive red demon attack vectors. The camera cranes back and tilts upward, revealing the tactical map is displayed on a high-end curved gaming monitor inside a dark studio apartment. Acoustic foam pyramid wall panels line the shadowy background, accented by subtle violet LED strip lights along the desk edges. Subject @Ash_Streamer sits silhouetted in his high-back chair, illuminated by the tactical blue display wash. Smooth camera deceleration and continuous lighting transition.
  ```


### 5.5 Beat 5: Workstation Climax & Foxy's 300,000 KRW Donation (Frames 014–017)
- **Narrative Action**: The camera arcs into a warm medium three-quarter angle of the broadcast desk. A sparkling golden donation alert card explodes on the secondary screen: *"Foxy donated 300,000 KRW!"*. Ash clasps his hands in sincere gratitude, bowing slightly to his webcam. He then reclines back into the cushioned headrest, cheeks flushed with pride, cheekily rubbing the tip of his nose in supreme satisfaction: *"Well, okay... I guess I was pretty awesome too."*.
- **Manga Panels**: Frame 014 (Donation Workstation - Keyframe 03), Frame 015 (World-First Clearance), Frame 016 (Smug Nose Rub), Frame 017 (Pinnacle of Pride).
- **Source Anchor Images**: `output/ttd_ep01_manga_transitions/clean_frames/keyframe_03_frame014.png` & `ep01_frame_016_clean.png`.
- **Bound Ingredients**:
  * Character Entity: `@Ash_Streamer` (sky-blue fleece, headphones, gratitude bow, relaxed smirk).
  * Asset Ingredient: `ING_STREAM_HUD` (golden alert card, streaming chat, dual monitor layout).
  * Asset Ingredient: `ING_STREAMER_PC` (desktop audio interface, mixer meters).
- **Continuation Mode**: `>> Режим продолжения (Veo 3.1 - Lite)` seeded from Beat 4 trailing 24 frames.
- **Continuation Window**: Exactly 24 frames @ 24fps (1.0s seed).
- **Exact Prompt Template**:
  ```text
  Continue directly from previous clip. Fortiche Production Arcane painterly style, visible gouache brushwork, warm volumetric chiaroscuro lighting. Camera smoothly tracks into a dynamic medium shot of @Ash_Streamer at his dual-monitor broadcast setup. A radiant golden donation notification card bursts with light on the vertical secondary screen. Ash smiles warmly with hands clasped together in grateful acknowledgment toward the webcam. He then exhales, leaning back lazily into the cushioned headrest of his black gaming chair, rubbing the tip of his nose with an index finger in a cheeky, smug expression of hard-earned gamer satisfaction. Warm amber donation light mingles with cool blue monitor reflections on his oversized hoodie. Fluid continuation of camera trajectory and ambient lighting.
  ```

### 5.6 Beat 6: The Emotional Undercut: Reading Chat, Silence & Regret (Frames 018–022, 024)
- **Narrative Action**: Ash's cocky smirk slowly fades. His dark eyes dart sideways to the vertical monitor, scanning the chat stream. A viewer comment stops him cold: *"So sad the priestess died in the final battle :( she carried so hard..."*. The room's warmth evaporates into cold twilight blue. Ash sits in absolute silence, hands resting numbly on the mechanical keyboard, head bowed as survivor's guilt creeps into his expression. He attempts a cold, pragmatic rationalization: *"My goal was never to keep everyone alive anyway... It was to see the ending."*.
- **Manga Panels**: Frame 018 (Reading Chat), Frame 019 (Lingering Regret), Frame 020 (Sanghy's Chat), Frame 021 (Solemn Silence), Frame 022 (Fallen Comrades), Frame 024 (Pragmatic Rationalization).
- **Source Anchor Images**: `output/ttd_ep01_manga_transitions/clean_frames/ep01_frame_020_clean.png`, `ep01_frame_021_clean.png`, `ep01_frame_024_clean.png`.
- **Bound Ingredients**:
  * Character Entity: `@Ash_Streamer` (pensive downward gaze, half-lidded eyes, solemn posture).
  * Asset Ingredient: `ING_STREAM_HUD` (cyan chat stream, viewer avatar, comment box).
  * Asset Ingredient: `ING_STREAMER_PC` (keyboard keycaps, still hands).
- **Continuation Mode**: `>> Режим продолжения (Veo 3.1 - Lite)` seeded from Beat 5 trailing 24 frames.
- **Continuation Window**: Exactly 24 frames @ 24fps (1.0s seed).
- **Exact Prompt Template**:
  ```text
  Continue directly from previous clip. Fortiche Production Arcane painterly style, moody desaturated oil brushstrokes, harsh directional chiaroscuro. The confident smile on @Ash_Streamer's face gently dissolves into quiet contemplation. His dark eyes dart sideways toward the live chat stream scrolling on the vertical monitor. The room lighting dims into somber, desaturated steel-blue tones. Close-up on Ash's hands resting motionless upon the mechanical keyboard. Ash slowly lowers his head, eyes half-lidded with a profound, quiet guilt reflecting in his dark pupils. Subtle drifting camera dolly creates an intimate, melancholic atmosphere. Room room-tone fades to silence except for the faint hum of computer fans. Seamless continuation from the preceding shot.
  ```

### 5.7 Beat 7: Battlefield Rampart Carnage to Lucas Solitary Back in Dark Void (Frames 023, 025–026)
- **Narrative Action**: The downcast face of the streamer dissolves into the catastrophic reality of the game's final stage: the shattered stone ramparts of Crossroads fortress. The stone parapets are soaked in black blood and rain, littered with mangled bodies of imperial soldiers, splintered shields, and broken broadswords under swirling black smoke. The battlefield dissolves into an infinite, pitch-black void. Standing isolated in the absolute darkness is Vanguard Knight Lucas—seen from behind, broad muscular shoulders hunched forward under crushing grief, battered plate armor gouged by claws, tattered blue cape frayed into rags, greatsword held tip-down into unseen ground. Cold cyan rim lighting cuts his lonely silhouette: *"His back looks so sad..."*.
- **Manga Panels**: Frame 023 (Rampart Carnage - Keyframe 04), Frame 025 (Stage MVP Lucas Card), Frame 026 (Lucas Solitary Back in Void - Keyframe 05).
- **Source Anchor Images**: `output/ttd_ep01_manga_transitions/clean_frames/keyframe_04_frame023.png` & `keyframe_05_frame026.png`.
- **Bound Ingredients**:
  * Character Entity: `@Lucas_Knight` (SSR Vanguard Knight in scorched silver plate).
  * Character Entity / Silhouette: `@Lucas_Solitary_Back` (rear view, broad shoulders hunched, frayed blue cape).
  * Asset Ingredient: `ING_GAME_SCREEN` (shattered ramparts, black blood, smoke, rain).
- **Continuation Mode**: `>> Режим продолжения (Veo 3.1 - Lite)` seeded from Beat 6 trailing 24 frames.
- **Continuation Window**: Exactly 24 frames @ 24fps (1.0s seed).
- **Terminal Invariant**: Pitch-black abyss, bottom 33% luminance must satisfy $\text{Mean Luminance} \le 25.0$.
- **Exact Prompt Template**:
  ```text
  Continue directly from previous clip. Fortiche Production Arcane painterly style, heavy textured impasto oil paint, extreme chiaroscuro with cold cyan rim lighting. The somber streamer bedroom dissolves into the devastated stone battlements of Crossroads fortress after a horrific siege. Stone flagstones are drenched in black blood, rain puddles, and broken steel swords. The smoking ramparts dissolve into an infinite, pitch-black void. Standing completely solitary in the absolute darkness is @Lucas_Knight seen from behind. Broad muscular shoulders hunched forward under the crushing agony of survivor's guilt. Dented, battle-scarred silver-steel plate armor with deep monster claw gouges, tattered royal-blue cape frayed into ragged tassels hanging limp. Tousled golden hair visible at the nape of his bowed head. Heavy notched broadsword resting tip-down. Extreme cold rim light outlines his lonely silhouette against the pitch black void. Melancholic solo cello note fading into hollow wind. Seamless transition from previous clip.
  ```


---

## 6. Multi-Scene Transition Execution Protocol & Matrix

To guarantee continuous momentum without jarring jumps, the 7 narrative beats map into an uninterrupted 56-second video timeline (or 7 continuous clips):

| Clip # | Timecode Range | Narrative Focus | Boundary Ingress Anchor | Boundary Egress Anchor | Primary Camera Kinetic Vector | Bound Reference Entities & Assets |
|---|---|---|---|---|---|---|
| **01** | `00:00.000`–`00:08.000` | CRT Fanfare to Gamer Victory Roar | `ep01_frame_001_clean.png` | `keyframe_01_frame002.png` | Rapid dolly pullback & upward crane | `@Ash_Streamer`, `ING_STREAMER_ROOM`, `ING_STREAMER_PC` |
| **02** | `00:08.000`–`00:16.000` | Direct Shouting & Smug Finger Point | `keyframe_01_frame002.png` | `ep01_frame_008_clean.png` | 3/4 orbital glide & push to desk | `@Ash_Streamer`, `ING_STREAMER_PC` |
| **03** | `00:16.000`–`00:24.000` | Screen Immersion to Gothic Monument | `ep01_frame_008_clean.png` | `keyframe_02_frame005.png` | Macro push into pupil -> match dissolve | `@Ash_Streamer`, `ING_GAME_SCREEN` |
| **04** | `00:24.000`–`00:32.000` | Tactical Defense Grid to Dark Bedroom | `keyframe_02_frame005.png` | `ep01_frame_011_clean.png` | Top-down tilt -> high crane pull-back | `ING_GAME_SCREEN`, `ING_STREAMER_ROOM`, `@Ash_Streamer` |
| **05** | `00:32.000`–`00:40.000` | Workstation Climax & 300k KRW Donation | `ep01_frame_011_clean.png` | `ep01_frame_016_clean.png` | Slow lateral tracking dolly to chair | `@Ash_Streamer`, `ING_STREAM_HUD`, `ING_STREAMER_PC` |
| **06** | `00:40.000`–`00:48.000` | Chat Reading & Solemn Guilt Silence | `ep01_frame_016_clean.png` | `ep01_frame_021_clean.png` | Slow push-in to hands on keyboard | `@Ash_Streamer`, `ING_STREAM_HUD`, `ING_STREAMER_PC` |
| **07** | `00:48.000`–`00:56.000` | Rampart Carnage to Lucas Solitary Back | `ep01_frame_021_clean.png` | `keyframe_05_frame026.png` | High crane over battlements -> dissolve -> stationary low angle | `ING_GAME_SCREEN`, `@Lucas_Knight`, `@Lucas_Solitary_Back` |

---

## 7. Quality Assurance & Automated Verification Protocol

To verify complete fidelity and prevent regressions during production, the following four automated validation checks must pass on every render iteration:

### 7.1 Geometry & Aspect Ratio Invariant
- **Reference Sheets**: All canonical concept arts in `output/canonical_arcane_concepts/` must be exactly `1376x768` (native Imagen 3 16:9 widescreen format).
- **Master Contact Sheet**: `output/canonical_arcane_concepts/master_contact_sheet.png` must assemble all 9 cards into a 3x3 grid with golden headers and labels.
- **Rendered Video Canvas**: All generated video frames must render at `1280x720` or `1920x1080` (strict 16:9 aspect ratio, zero anamorphic distortion).

### 7.2 Terminal Keyframe Pitch-Black Darkness Invariant
- For Keyframe 05 (Beat 7 / Frame 026, Lucas Solitary Back in Void), the bottom third of the canvas ($y \in [480, 720]$) must maintain a pitch-black abyss:
  $$\mu_{\text{luminance}} = \frac{1}{W \cdot (H/3)} \sum_{x, y} (0.299 R + 0.587 G + 0.114 B) \le 25.0$$
- Any ambient light leak, floor grid reflection, or text badge bleeding into the bottom third triggers immediate rejection.

### 7.3 Character Palette Clamping Invariant
- `@Ash_Streamer` Hoodie color profile: Mean RGB in the torso bounding box must maintain cyan/sky-blue hue ($B > R$ and $G > R$, target `#88bbee` $\pm 15\%$).
- `@Lucas_Knight` Cape color profile: Mean RGB of mantle tassels must maintain royal blue ($B > 1.2 \times R$, target `#224488`).

### 7.4 Seam Continuity & Zero Jump-Cut Guard
- Between Clip $N$ (frames 144–168) and Clip $N+1$ (frames 0–24), the normalized cross-correlation (NCC) or Structural Similarity Index (SSIM) across the shared 24-frame seed window must satisfy $\text{SSIM} \ge 0.88$.
