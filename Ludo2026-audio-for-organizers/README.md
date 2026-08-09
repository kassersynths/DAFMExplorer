# Ludo2026 — audio cues for organizers

**Talk:** Exploring the Sonic Universe of the Sega Genesis  
**Authors:** Abraham Casas & Maria Cerro (Kasser Synths)  
**Session:** Session 9 — Synthesis, Served Three Ways  

These MP3s are the **inline slide sounds** from the Beamer deck (converted from AIFF).  
Each folder matches a slide block, in **talk order**. Files inside are numbered left-to-right / top-to-bottom as on the slide.

Format: MP3 (LAME VBR ~190 kbps), mono, 44.1 kHz. Short single-note YM2612 renders (same MIDI note across comparisons).

Also see `manifest.csv` for a machine-readable list.

---

## Cue map

| # | Folder | Beamer slide title | Files |
|---|--------|--------------------|-------|
| 01 | `01_Anatomy-of-FM-preset` | Anatomy of a FM synthesis preset | Carrier → FM stack → AM LFO → Feedback |
| 02 | `02_SSG-EG_FB-ALG_AMS` | SSG-EG, FB / ALG, L/R, AMS / PMS | Feedback max · AMS tremolo *(same demos as 01)* |
| 03 | `03_Game-fingerprints_commit-vs-variety` | Game fingerprints — commit vs variety | Pulseman · Thunder Force IV · Gunstar · SoR3 |
| 04 | `04_Brightness-by-game_sweet-spot` | Brightness by game — a shared sweet spot | Batman & Robin · Pulseman · Ristar · Sonic 3&K |
| 05 | `05_Dark-outliers_warmth-over-bite` | Dark outliers — choosing warmth over bite | Spider-Man · The Tick · Tinhead · Top Gear 2 |
| 06 | `06_GEMS_different-FM-grammar` | GEMS — a different FM grammar | Nightmare Circus (GEMS) · Thunder Force IV (non-GEMS) |
| 07 | `07_Composer-signatures_four-voices` | Composer signatures — hear four voices | Koshiro · Nakamura · Kawaguchi · Hanzawa |
| 08 | `08_Composer-Kodaka-outlier` | More signatures — Kodaka & Uematsu | Kodaka Alg.2 |

---

## Notes for editing / AV

- Clips are **very short** (~1–2 s held notes). Leave a beat of silence between cues if mixing into a recording.
- Some sources are reused on later slides (e.g. Pulseman, Feedback, Thunder Force IV); folders 02/04/06 may duplicate audio intentionally so each slide is self-contained.
- These are **research/demo renders** of FM presets (not full game soundtrack VGMs).
- Contact: Kasser Synths — https://www.kassersynths.com · https://dafm-explorer.vercel.app/

---

## How these were produced

Source AIFFs: `Ludo2026-DAFMExplorer-LaTeX/videos/presets/`  
Converted with ffmpeg (`libmp3lame -qscale:a 2`).
