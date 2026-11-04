Generate a cinematic, Arcane-inspired multi-angle gameplay sequence of the Episode 1 prologue climax ("Я тиран в оборонительной игре"), depicting the final boss battle with dynamic camera transitions, programmatic manga-style stream chat and donation overlays, and rich cinematic sound design with Russian narration.

Working directory: e:\ANTIGRAVITY\flow_video_testbench
Integrity mode: development

Reference: https://t.me/incubeai_pro/3564

## Requirements

### R1. Cinematic Boss Fight Multi-Angle Sequence
Generate a cinematic gameplay sequence depicting the climax of the Episode 1 prologue boss battle (Lucas vs. Boss) in Arcane visual style, using multiple dynamic camera angles, high environmental detail, and fluid combat transitions without awkward character artifacts. The sequence must progress through the battle climax, the `CLEAR! Congratulations!` victory fanfare, and conclude with the transition to Lucas's solitary back fading into void.

### R2. Programmatic Manga-Style Stream Chat and Donation Overlays
Implement dynamic 2D manga/comic-style stream chat messages, user nickname popups, and donation notifications (including "FOXY 300,000 KRW") composited directly onto the video. Overlays must feature sharp, legible typography with stylized Webtoon speech bubbles and comment frames synchronized with the sequence action beats.

### R3. Comprehensive Sound Design and Narration
Produce and composite a multi-layered cinematic audio track comprising combat impact sound effects, environmental sound design, victory fanfare, stream ambiance, and synchronized Russian studio narration using `voice_y0joebp3bwta`.

### R4. Automated Verification Pipeline
Integrate automated verification scripts validating the complete production output, including storyboard matrix consistency, media container parameters, and quality compliance.

## Acceptance Criteria

### Media Composition & Visual Quality
- [ ] Video renders as an MP4 file with minimum 720p resolution (1280x720 or 1920x1080) at standard frame rate (24 or 30 fps).
- [ ] The sequence contains multi-angle cuts illustrating the boss fight, the victory fanfare, and the concluding transition to Lucas's solitary back.
- [ ] Manga-style floating chat bubbles and donation popups ("FOXY 300,000 KRW") are burned into the video with legible text and accurate timing synchronization.

### Audio Integrity
- [ ] Audio track is multiplexed into the MP4 container with synchronized stereo audio (combat SFX, fanfare, and `voice_y0joebp3bwta` Russian narration) without clipping or audio drift.

### Programmatic Verification
- [ ] `pytest tests/test_flow_studio.py` passes with zero failures.
- [ ] An automated validation script executes FFmpeg stream probe checks confirming video duration, resolution, audio codec, and non-zero bitrate across all rendered deliverables.
