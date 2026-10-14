#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render a vertical video from a scene manifest.

Manifest shape::

    {
      "output": "out/video.mp4",
      "fps": 30,
      "tts_bin": "edge-tts",
      "voice": "id-ID-ArdiNeural",
      "rate": "+6%",
      "caption": {"font": "DejaVu Sans", "size": 64, "margin_v": 300,
                   "max_words": 3, "max_chars": 26, "border": 5},
      "scenes": [
        {"id": "S1", "image": "frames/01.png",
         "narration": "...", "tail": 2.0}
      ]
    }

Each scene: a still image (1080x1920) plus one narration line. Scene duration is the
measured audio length plus `tail` seconds of read pause, rounded to whole frames.

Usage::

    python3 render_vertical.py manifest.json          # render
    python3 render_vertical.py manifest.json --check   # plan only, no render
    python3 render_vertical.py manifest.json --reuse   # keep existing audio/SRT

Sentence boundaries in captions come from the TTS engine's own SRT and are exact.
Word grouping inside a sentence is allocated by text length, so it is an estimate.
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------- utilities ---
def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def durasi_media(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)])
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe gagal untuk {path}: {r.stderr.strip()[:200]}")
    return float(r.stdout.strip())


def dimensi(path):
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height", "-of", "csv=p=0", str(path)])
    return r.stdout.strip()


# ------------------------------------------------------------------- caption ---
def baca_srt(path):
    cue = []
    isi = Path(path).read_text(encoding="utf-8")
    for blok in re.split(r"\n\s*\n", isi.strip()):
        baris = [b for b in blok.splitlines() if b.strip()]
        if len(baris) < 3:
            continue
        m = re.match(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", baris[1])
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        a = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        b = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        cue.append((a, b, " ".join(baris[2:])))
    return cue


def jam_ass(d):
    d = max(0.0, d)
    return f"{int(d // 3600):d}:{int((d % 3600) // 60):02d}:{d % 60:05.2f}"


def pecah(teks, mulai, selesai, maks_kata, maks_kar):
    """Split one cue into groups of words; time allocated by text length."""
    kata = teks.split()
    kel = []
    i = 0
    while i < len(kata):
        potong = kata[i:i + maks_kata]
        while len(" ".join(potong)) > maks_kar and len(potong) > 1:
            potong = potong[:-1]
        kel.append(" ".join(potong))
        i += len(potong)
    total = sum(len(k) for k in kel) or 1
    panjang = max(0.05, selesai - mulai)
    hasil, t = [], mulai
    for k in kel:
        d = panjang * len(k) / total
        hasil.append((t, t + d, k))
        t += d
    return hasil


# --------------------------------------------------------------------- main ---
def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    man_path = Path(argv[1])
    periksa = "--check" in argv
    pakai_ulang = "--reuse" in argv

    man = json.loads(man_path.read_text(encoding="utf-8"))
    akar = man_path.parent
    fps = int(man.get("fps", 30))
    suara = man.get("voice", "id-ID-ArdiNeural")
    laju = man.get("rate", "+6%")
    tts_bin = man.get("tts_bin", "edge-tts")
    cap = man.get("caption", {})
    font = cap.get("font", "DejaVu Sans")
    fsize = int(cap.get("size", 64))
    margin_v = int(cap.get("margin_v", 300))
    maks_kata = int(cap.get("max_words", 3))
    maks_kar = int(cap.get("max_chars", 26))
    batas = int(cap.get("border", 5))

    if not shutil.which(tts_bin) and not Path(tts_bin).exists():
        print(f"TTS tidak ditemukan: {tts_bin}\n"
              f"Pasang yang baru di venv sendiri: python3 -m venv ~/.local/ttsvenv && "
              f"~/.local/ttsvenv/bin/pip install -U edge-tts")
        return 2

    audio_dir = akar / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    keluaran = akar / man.get("output", "video.mp4")
    keluaran.parent.mkdir(parents=True, exist_ok=True)

    # --- 1. audio + SRT per adegan ---
    adegan = []
    for i, s in enumerate(man["scenes"], 1):
        gambar = akar / s["image"]
        if not gambar.exists():
            print(f"gambar tidak ada: {gambar}")
            return 2
        d = dimensi(gambar)
        if d != "1080,1920":
            print(f"PERINGATAN {s['id']}: gambar {d}, seharusnya 1080,1920")
        mp3 = audio_dir / f"{s['id']}.mp3"
        srt = audio_dir / f"{s['id']}.srt"
        if not (pakai_ulang and mp3.exists() and srt.exists()):
            r = run([tts_bin, "--voice", suara, f"--rate={laju}", "--text", s["narration"],
                     "--write-media", str(mp3), "--write-subtitles", str(srt)])
            if r.returncode != 0 or not mp3.exists():
                print(f"TTS gagal untuk {s['id']}: {r.stderr.strip()[:300]}")
                return 1
        d_audio = durasi_media(mp3)
        tail = float(s.get("tail", 2.0))
        bingkai = round((d_audio + tail) * fps)
        adegan.append({"id": s["id"], "gambar": gambar, "mp3": mp3, "srt": srt,
                       "audio": d_audio, "frames": bingkai, "durasi": bingkai / fps})
        print(f"  {s['id']}: audio {d_audio:6.2f}s + jeda {tail:.1f}s = {bingkai/fps:6.2f}s")

    # --- 2. waktu absolut ---
    t = 0.0
    for a in adegan:
        a["mulai"] = t
        t += a["durasi"]
    total = t
    print(f"\ntotal: {total:.2f}s ({round(total*fps)} bingkai)")
    if periksa:
        print("(--check: berhenti sebelum render)")
        return 0

    # --- 3. caption ASS ---
    kepala = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n"
        "WrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: cap,{font},{fsize},&H00FFFFFF,&H000000FF,&H00101420,&H80000000,-1,0,0,0,100,100,"
        f"0,0,1,{batas},0,2,50,50,{margin_v},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    baris = []
    for a in adegan:
        for cue in baca_srt(a["srt"]):
            for (m, s, teks) in pecah(cue[2], cue[0], cue[1], maks_kata, maks_kar):
                baris.append(f"Dialogue: 0,{jam_ass(a['mulai']+m)},{jam_ass(a['mulai']+s)},cap,,0,0,0,,"
                             f"{teks.upper()}")
    ass = akar / "caption.ass"
    ass.write_text(kepala + "\n".join(baris) + "\n", encoding="utf-8")
    print(f"caption: {len(baris)} baris -> {ass.name}")

    # --- 4. ffmpeg ---
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for a in adegan:
        cmd += ["-loop", "1", "-t", f"{a['durasi']:.4f}", "-i", str(a["gambar"])]
    for a in adegan:
        cmd += ["-i", str(a["mp3"])]
    n = len(adegan)
    fc = []
    for i, a in enumerate(adegan):
        fc.append(f"[{i}:v]scale=1080:1920,setsar=1,fps={fps},fade=t=in:st=0:d=0.18,"
                  f"trim=duration={a['durasi']:.4f},setpts=PTS-STARTPTS[v{i}]")
    for i, a in enumerate(adegan):
        fc.append(f"[{n+i}:a]apad,atrim=0:{a['durasi']:.4f},asetpts=PTS-STARTPTS[a{i}]")
    fc.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vcat]")
    fc.append("".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[aout]")
    fc.append(f"[vcat]ass={ass}[vout]")
    cmd += ["-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-r", str(fps), "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
            "-movflags", "+faststart", "-shortest", str(keluaran)]
    print("\nrender...")
    r = run(cmd)
    if r.returncode != 0:
        print("GAGAL:\n", r.stderr[-2000:])
        return 1

    print(f"selesai: {keluaran}")
    print(run(["ffprobe", "-v", "error", "-show_entries",
               "format=duration,size:stream=codec_name,width,height",
               "-of", "default=noprint_wrappers=1", str(keluaran)]).stdout.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
