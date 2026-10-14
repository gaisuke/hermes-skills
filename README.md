# Hermes skills

Kumpulan skill untuk [Hermes Agent](https://github.com/NousResearch/hermes-agent).
Sebuah skill adalah folder berisi `SKILL.md` — prosedur yang dibaca agen saat tugasnya
relevan, bukan kode yang selalu ikut ke setiap percakapan.

## Isi

| Skill | Kegunaan |
|---|---|
| [`vertical-video-pipeline`](vertical-video-pipeline/) | Membuat video vertikal 9:16 (Reels/Shorts/TikTok) dari skrip per adegan: narasi TTS, caption terbakar yang waktunya akurat, latar dari HTML, dirakit ffmpeg. Tanpa wajah, tanpa aplikasi editor. |

## Memasang

Tambahkan repo ini sebagai sumber, lalu cari dan pasang:

```bash
hermes skills tap add gaisuke/hermes-skills
hermes skills search "vertical video"
hermes skills inspect gaisuke/hermes-skills/vertical-video-pipeline
hermes skills install gaisuke/hermes-skills/vertical-video-pipeline
```

Sumbernya dihapus lagi dengan `hermes skills tap remove gaisuke/hermes-skills`, dan
skill yang sudah dipasang dengan `hermes skills uninstall`.

## Syarat `vertical-video-pipeline`

- `ffmpeg` dengan filter `ass`, `concat`, `fade`
- **edge-tts ≥ 7.3.1.** Versi 7.2.7 gagal dengan `403 Invalid response status`; skema token
  Microsoft berubah. Pasang di venv sendiri supaya tidak mengubah venv Hermes:

  ```bash
  python3 -m venv ~/.local/ttsvenv
  ~/.local/ttsvenv/bin/pip install -U edge-tts
  ```

- Suara Indonesia: `id-ID-ArdiNeural` (pria), `id-ID-GadisNeural` (wanita)

Sesudah terpasang, satu perintah merender seluruh video:

```bash
python3 ~/.hermes/skills/media/vertical-video-pipeline/scripts/render_vertical.py manifest.json
```

Lihat bagian *Procedure* dan *Pitfalls* di dalam `SKILL.md` — di situ tercatat tujuh jebakan
yang sudah pernah memakan waktu, termasuk `mobile=True` yang membuat pengambilan gambar
menggantung, dan tangkapan layar situs yang terpotong bila dipotret pada lebar 1080.

## Lisensi

MIT.
