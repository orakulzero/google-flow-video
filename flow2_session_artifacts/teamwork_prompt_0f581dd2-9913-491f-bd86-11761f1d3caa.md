Generate an animated first-run video sequence for Episode 1 of the manga adaptation ("Я тиран в оборонительной игре") exploring frame-to-frame (sprite-to-sprite) transitions from sequential manga panels (frame_001.jpg to frame_026.jpg), stopping at the designated back-view panel ("Его спина выглядит так грустно..."), and delivering the assembled video sequence without voiceover in the report.

Working directory: e:\ANTIGRAVITY\flow_video_testbench
Integrity mode: development

## Requirements

### R1. Manga Panel Inpainting & Preprocessing
Prepare the sequential manga panels from `e:\ANTIGRAVITY\flow_video_testbench\output\ttd_arcane_characters\episode1_frames\ep01\` from `frame_001.jpg` up to `frame_026.jpg` (matching the target panel "ЕГО СПИНА ВЫГЛЯДИТ ТАК ГРУСТНО...." / Lucas back-view) by removing/inpainting dialogue speech bubbles, sound effects, and text overlays so that visual elements transition cleanly between frames.

### R2. Frame-to-Frame Animation Generation in Google Flow
Generate animated scene transitions across the sequential panels using Google Flow (project `https://flow.google.com/project/7d9a2a67-9cd2-4a79-932e-717d2e29257f`) via the configured Chrome profile (`C:\Users\Orakul Grey\AppData\Local\ffroliva\gflow-cli\profile_default`) and proxy (`http://127.0.0.1:7890`). The team decides the exact transition structure and keyframe selection to achieve smooth visual continuity up to the target panel `frame_026.jpg`.

### R3. Video Assembly and Silent Video Delivery
Assemble the generated video transitions into a unified 720p MP4 video sequence covering the story progression from `frame_001.jpg` to `frame_026.jpg`. The assembled video must strictly contain only the video track, with no voiceover or audio track. Deliver the video and visual sequence summary directly to the target report directory at `C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f\`.

## Acceptance Criteria

### Video Sequence & Scope
- [ ] The video sequence begins at `frame_001.jpg` and ends at `frame_026.jpg` (Lucas standing in darkness with caption "Его спина выглядит так грустно...").
- [ ] Speech bubbles and text overlays are removed/inpainted from the animated frames to maintain clean sprite-to-sprite transitions.
- [ ] The output deliverable is a 720p MP4 file with smooth visual continuity between scenes.
- [ ] The delivered MP4 file contains no audio streams or voiceover tracks (completely silent video sequence).

### Delivery & Verification
- [ ] The assembled MP4 video file is placed in `output/` and linked/presented in the session report at `C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f\`.
- [ ] Programmatic verification (e.g. via ffprobe / media inspection script) confirms 720p resolution, codec integrity, and zero audio channels.
