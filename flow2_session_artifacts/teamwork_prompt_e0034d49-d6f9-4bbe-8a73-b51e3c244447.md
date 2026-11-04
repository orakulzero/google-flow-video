Develop the series production infrastructure and pilot test scene for an animated/cinematic dark fantasy series based on the manhwa/novel "Tyrant of the Tower Defense Game" (Тиран в оборонительной игре) using Google Flow and Veo 3.1.

Working directory: e:\ANTIGRAVITY\flow_video_testbench
Integrity mode: development

## Requirements

### R1. Series Production Infrastructure & Character Bible
Create the series production foundation and lore bible for "Tyrant of the Tower Defense Game" adapted for Google Flow and Veo 3.1. Document visual style tokens, character design specifications (Prince Ash Bornhater, Knight Lucas, Archer Lily, and monster waves), environmental aesthetics for the Crossroads southern fortress, and dark fantasy visual continuity guidelines.

### R2. Storyboard Templates & Prompt Generator
Implement reusable Flow storyboard templates and a prompt generation pipeline supporting `FlowStoryboard` and `FlowScene` structures. Ensure prompt structures include camera direction, lighting, motion dynamics, character visual anchors, and audio pacing markers compatible with Google Flow and Veo 3.1.

### R3. Pilot Test Scene Assembly & Voiceover Localization
Generate and assemble an end-to-end pilot test scene depicting the prologue / first wave defense of Crossroads. The scene must include Russian studio voiceover narration generated with the `voice_y0joebp3bwta` TTS preset, synchronized Russian subtitle tracks (.vtt and .srt), and an assembled 720p HD MP4 video integrated into the testbench preview player.

## Acceptance Criteria

### Pipeline and Test Verification
- [ ] `pytest tests/test_flow_studio.py -v` executes and passes with zero failures.
- [ ] Storyboard and character assets export valid `FlowStoryboard` JSON compatible with `src/flow_bridge.py`.

### Media Deliverables
- [ ] An assembled 720p HD MP4 video for the pilot test scene is generated in `output/` alongside corresponding `.vtt` and `.srt` subtitle files.
- [ ] Russian studio narration (`voice_y0joebp3bwta`) is rendered, non-empty, and synchronized with scene visual transitions and subtitle cues.
- [ ] The generated pilot test scene is registered and playable within the testbench HTML5 preview player (`output/index.html`).
