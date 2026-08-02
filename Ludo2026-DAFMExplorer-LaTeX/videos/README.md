# Video recording checklist (Ludo2026)

Play videos **outside** the PDF (VLC / browser) when the slide shows the cue — more reliable than embedded PDF media at conferences.

Place files here as:

- `V1.mp4`
- `V2.mp4`
- `V3.mp4`

## V1 — Data extraction (~45–60 s)

**Slide cue:** *Data extraction — Making the archive speak*

**Show:** OPM text (or zip entry) → parsed row with game name, composer, nationality, GEMS flag.

**Say (EN gist):** “Same file that once lived as chip commands becomes a row we can count, filter, and compare.”

**Avoid:** Long scrolling through code; notebook filenames on screen.

## V2 — Technique you can hear (~45–60 s)

**Slide cue:** *EDA: Feedback as a binary aesthetic*

**Show / play:** Two short YM2612 notes — feedback **0** vs **7** (same patch family if possible), or two extreme presets from the corpus.

**Say:** “The histogram is not abstract: composers treat feedback as a switch between clean control and grit.”

Alternative if easier: Algorithm 4 “two-voice” patch vs a denser algorithm — keep it sonic, not theoretical.

## V3 — History you can hear (~60–75 s)

**Slide cue:** *Composer signatures — hear four voices* (PDF inline AIFFs)

**Play 2–4 short presets** on the slide (same MIDI note), e.g.:

1. Koshiro / *Streets of Rage* (`composer_koshiro_…`)
2. Nakamura / *Sonic* Star Light (`composer_nakamura_…`)
3. Optional: Kawaguchi / Hanzawa; Kodaka Alg.~2 on the next slide

**Say:** “Data points back to people, tools, and games — not only averages.”

## Optional live app (≤60–90 s)

URL: https://dafm-explorer.vercel.app/

Open map → click a neighbourhood → play → filter by composer or GEMS.  
If Wi‑Fi fails: skip; composer AIFFs + the embedding slide are enough.

## Live VGM + presets (preferred for the room)

See **[LIVE_DEMOS.md](LIVE_DEMOS.md)** for the cue sheet. Composer block is **inline AIFF** (YK/MN/HK/NH/NK); optional VGM leftovers:

| Cue | Game | Point |
|-----|------|-------|
| YK…NK | Composer AIFFs in PDF | Shared grammar, different ears |
| L2 | *Pulseman* | Alg. 5 commitment → CON=5 preset |
| NC / TF4 | GEMS vs non-GEMS | Tool-shaped patch contrast |

Prepare offline VGMs in `videos/vgm/` and keep DAFMExplorer tabs pre-filtered.
