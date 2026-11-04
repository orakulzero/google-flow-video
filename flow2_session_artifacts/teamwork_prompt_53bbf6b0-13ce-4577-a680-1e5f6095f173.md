Acquire an Arcane animation style dataset (via pre-made frame packs or sliced video cuts) and establish reference-frame visual style conditioning and prompt tuning for Google Veo to reproduce Arcane visual style in generated video frames, running autonomously overnight with programmatic and visual verification.

Working directory: e:\ANTIGRAVITY\flow_video_testbench\veo_arcane_style
Integrity mode: development

## Requirements

### R1. Arcane Dataset Acquisition and Frame Curation
Download ready-made public datasets or packs of Arcane frames, and/or extract frames from downloaded Arcane video cuts using scene detection. Filter and curate frames into high-resolution reference pairs/sets depicting key character, lighting, and painterly texture styles from Arcane.

### R2. Veo Reference-Frame Style Conditioning Pipeline
Implement style conditioning and prompt tuning for Google Veo (and Gemini visual pipeline) using the curated Arcane reference frames as visual anchors. The pipeline must generate candidate video sequences reflecting Arcane's visual signature (stylized brushwork, dramatic dual-tone lighting, and graphic novel depth).

### R3. Automated Overnight Batch Execution
Run the complete pipeline as an autonomous overnight batch process that performs dataset staging, style conditioning iterations, and test video clip generation without manual intervention, mirroring final deliverables to `C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f`.

### R4. Dual Verification Suite
Provide an automated verification harness combining programmatic validation of media files with generated visual comparison sheets aligning Arcane reference frames side-by-side with the generated Veo output frames.

## Acceptance Criteria

### Dataset Integrity
- [ ] A curated dataset of Arcane reference frames is populated in `e:\ANTIGRAVITY\flow_video_testbench\veo_arcane_style\dataset\` with at least 50 distinct high-resolution frames (720p or higher) and an associated metadata index (JSON/CSV).

### Style Replication and Video Output
- [ ] At least 2 distinct test video clips (minimum 720p resolution, valid MP4 container with H.264/AVC video stream and non-zero duration) are generated using Veo reference conditioning reflecting the Arcane style.

### Verification and Artifacts
- [ ] Programmatic validation tests execute successfully via an automated test runner, confirming container parameters, resolution, and non-zero bitrate for all generated video deliverables.
- [ ] Visual comparison contact sheets (PNG/JPEG) are generated displaying input Arcane reference frames alongside corresponding generated output frames.
- [ ] Deliverables (video clips, comparison sheets, and test report) are mirrored to `C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f`.
