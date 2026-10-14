---
name: vertical-video-pipeline
description: Render vertical MP4 from a scene script, with captions.
version: 0.1.0
author: Akhmad Dani Munif (gaisuke), Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [video, shorts, reels, tts, ffmpeg, captions, vertical]
    related_skills: [product-evidence-screenshots]
---

# Vertical Video Pipeline

Turn a structured scene script (JSON) into a finished 9:16 MP4: narration from TTS,
burned-in captions, still frames rendered from local HTML, assembled by ffmpeg.
Reach for this when a text or script asset needs to become vertical short-form video
without a video editor or a face on camera.

## When to Use

- A written script, thread, or article should become a 60-120s vertical video
- The video is screen graphics, diagrams, and text: no shooting, no presenter
- Captions must be timed to narration, not guessed
- You want one command to re-render after the script changes
- **Don't use for:** talking-head footage, motion graphics with complex animation
  (that is a Remotion or editor job), or anything needing licensed music you do not have

## Prerequisites

- `ffmpeg` with `ass`, `drawtext`, `concat`, `fade`, `zoompan` filters (`ffmpeg -filters` to check)
- A recent **edge-tts (>= 7.3.1)**. Version 7.2.7 fails with `403 Invalid response status`:
  Microsoft changed the token scheme. Install it in its own venv so you never mutate the
  Hermes runtime venv:
  `python3 -m venv ~/.local/ttsvenv && ~/.local/ttsvenv/bin/pip install -U edge-tts`
- A font named in the ASS style (DejaVu Sans is present on most Linux hosts: `fc-list | wc -l`)
- Optional, for frames from HTML: a browser you can drive and screenshot (`browser_exec`)
- Optional, for hosting: a web path already behind auth

## Quick Reference

```bash
# voices (Indonesian: id-ID-ArdiNeural male, id-ID-GadisNeural female)
EDGE_TTS_BIN --list-voices | grep -i id-ID

# caption timing straight from the engine (sentence-accurate)
EDGE_TTS_BIN --voice id-ID-ArdiNeural --rate=+6% --text "..." \
  --write-media scene.mp3 --write-subtitles scene.srt

# render the whole thing
python3 scripts/render_vertical.py manifest.json
```

## Procedure

1. **Write the script as data, not prose.** One JSON: per scene an `id`, the narration,
   the on-screen lines, and a `visual` spec. Keep narration and on-screen text as separate
   fields so a silent cut is just dropping one column.
   *Done when:* every scene has narration, on-screen text, and a visual spec, and no scene
   references a claim outside your source material.
2. **Reserve the frame bands before designing anything.** Top 200px, content 200-1400px,
   captions 1400-1720px, bottom 1720-1920px left empty (platform UI covers it).
   *Done when:* no frame puts content below 1400px.
   *Why:* captions are burned over the bottom band; content there collides.
3. **Render each frame as HTML at exactly 1080x1920, then screenshot it.** Drive the browser
   with `Emulation.setDeviceMetricsOverride(width=1080, height=1920, deviceScaleFactor=1,
   mobile=False)`, navigate to `file:///.../scene.html`, then
   `Page.captureScreenshot(clip={0,0,1080,1920}, captureBeyondViewport=True)`.
   *Done when:* `ffprobe` reports 1080x1920 for every frame.
4. **Generate narration audio per scene and measure it.** One TTS call per scene, plus its
   SRT. Take duration from `ffprobe -show_entries format=duration`, never from a
   words-per-second guess.
   *Done when:* every scene has an mp3 plus a measured duration in seconds.
5. **Set each scene's duration from its own audio**, plus a 2.0-2.5s read pause.
   Round to whole frames (`round(seconds * fps)`) so captions never drift.
   *Done when:* total lands inside your target window and scene starts are contiguous.
6. **Build the ASS caption file.** Use the SRT cue boundaries as anchors (they are exact)
   and split each cue into 2-4 word groups, allocating the cue's duration by text length.
   *Done when:* caption lines are uppercase, <= 2 lines, <= ~26 chars, margin 250-300px.
7. **Assemble with ffmpeg:** loop each still, `apad`+`atrim` each audio to its scene length,
   `concat` video and audio separately, burn captions with `ass=`, encode
   `libx264 -crf 20 -pix_fmt yuv420p -r 30 -c:a aac -movflags +faststart`.
   *Done when:* the command exits 0 and the MP4 exists.
   `scripts/render_vertical.py` does steps 4-7 from a manifest.
8. **Look at the output.** Extract frames at 3-4 timestamps and inspect them with
   `vision_analyze`; check caption readability and that nothing collides or is cut.
   *Done when:* you have seen the first frame, a middle frame, and the end card.

## Pitfalls

1. **`mobile=True` in the viewport override breaks `captureScreenshot` on `file://` pages**
   (it hangs until timeout) and also forces the page into a wider layout. Use `mobile=False`
   for local frames; use the page's own desktop width for live product screenshots.
2. **`captureScreenshot` is flaky** even when the page is fine. Wrap it: re-establish the
   tab, re-set metrics, retry 3-5 times with a short sleep. This is not a page problem.
3. **Capturing a real site at 1080 wide can cut its navigation.** Capture at the site's
   natural width (e.g. 1280) and let the frame scale it, instead of cropping to 1080.
4. **TTS pace varies per scene** (2.1-2.8 words/sec even at a fixed rate), so a global
   words-per-second assumption makes scenes too long or too short. Measure each one.
5. **edge-tts `--write-subtitles` gives sentence-level cues, not per-word.** Treat the cue
   boundaries as exact and the within-sentence split as an estimate; do not claim
   word-accurate karaoke captions.
6. **A bare `.mp4` URL often downloads instead of playing.** Ship a small HTML page with
   `<video controls playsinline poster>`, and put the file behind whatever auth already exists.
7. **Height math is unforgiving.** A 2-line headline at 100px plus a screenshot can exceed
   the 1200px content band; check the rendered frame, not the CSS intent.

## Verification

- `ffprobe -show_entries stream=codec_name,width,height -of default=noprint_wrappers=1 out.mp4`
  reports `h264`, `1080`, `1920`, and an `aac` stream.
- `ffmpeg -i out.mp4 -af volumedetect -f null -` reports a `mean_volume` near -19 dB and a
  `max_volume` below 0 dB (audio present, not clipped).
- Extracted frames show captions inside the 1400-1720px band and matching the narration
  spoken at that timestamp (check the content, not just that text exists).
- `moov` appears in the first few hundred bytes of the file (`+faststart` worked), and an
  HTTP `Range: bytes=0-1023` request to the hosted file answers `206`.
