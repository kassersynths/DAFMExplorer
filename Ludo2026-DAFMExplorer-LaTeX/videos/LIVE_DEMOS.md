# Live demos — VGM + presets (Ludo2026)

Optional VGM outside the PDF (e.g. **L2** Pulseman). Composer / GEMS / fingerprint demos are mostly **inline AIFF** in Acrobat/Reader (`main.pdf`).

Total live audio budget: **≈90–120 s** across the talk (not counting optional pre-recorded V1–V3).

## Offline setup (do this before the conference)

1. **VGM player**
   - Foobar2000 + [foo_input_vgm / in_vgm](https://vgmrips.net/), or **VGMPlay**
2. **Download packs** from [VGMrips](https://vgmrips.net/) (search game name → Mega Drive / Genesis) if you still want stage VGM:
   - *Pulseman* (optional L2)
   - *Nightmare Circus* / *Thunder Force IV* (optional extras; NC/TF4 AIFFs are already in the PDF)
3. Copy the `.vgm` / `.vgz` files into `videos/vgm/` (create folder) and rename clearly, e.g.:
   - `L2_pulseman_stage.vgz`
4. **DAFMExplorer offline fallback:** open https://dafm-explorer.vercel.app/ once on venue Wi‑Fi *or* run the local `webapp` build; pre-filter each game in a browser tab.
5. **Audio route:** laptop headphone-out → venue mixer; set a single volume for VGM and preset so jumps are small.
6. **PDF:** open `main.pdf` in **Adobe Acrobat/Reader** (inline star sounds). Rebuild: `latexmk` in this folder (LuaLaTeX).

## Cue sheet (VGM → app)

| Cue | Slide | VGM (≈10–15 s) | Preset in DAFMExplorer | Say (EN gist) |
|-----|-------|----------------|------------------------|---------------|
| **YK/MN/HK/NH** (PDF inline) | Composer signatures — hear four voices | — | `composer_*.aiff` (SoR / Sonic / Golden Axe / Gunstar) | “Same MIDI note — four neighbourhoods inside the shared Alg.4/FL=7 grammar.” |
| **NK** (PDF inline) | Kodaka \& Uematsu | — | `composer_kodaka_con2_fl7_b0p553.aiff` | “Kodaka leans Alg.2 — routing outlier with full feedback.” |
| **L2** | Game fingerprints | *Pulseman* energetic stage | Filter `Pulseman` → preset with **CON = 5** | “The histogram isn’t abstract: the score commits to a wiring.” |
| **NC / TF4** (PDF inline) | GEMS — different FM grammar | — | AIFF buttons on slide: `game_nightmare_circus_con2_fl0.aiff` vs TF~IV | “Alg.2 + FL=0 (GEMS) vs non-GEMS neighbourhood — tool gap, not quality score.” |

Optional extras if time: *Gunstar Heroes* (variety), *Phantasy Star IV* (darker/atmospheric).

## Game-demo AIFF cues (fingerprints / brightness)

Rendered from real OPM presets in the corpus (`scripts/select_game_demo_exemplars.py` → `scripts/render_game_demo_aiffs.ts`). Same MIDI note as the star demos. Files: `videos/presets/game_*.aiff`.

| Cue | Game | Role on slide | CON | Notes |
|-----|------|---------------|-----|-------|
| **PM** | Pulseman | commit / bright | 5 | ≈75% Alg.5 brand |
| **TF4** | Thunder Force IV | variety | 0 | leaves Alg.4 |
| **GH** | Gunstar Heroes | variety | 5 | multi-CON score |
| **SoR3** | Streets of Rage 3 | variety | 2 | multi-CON score |
| **BaR** | Adventures of Batman \& Robin | bright end | 0 | high Brightness\_Index |
| **Rst** | Ristar | rounder | 2 | mid–high, less harsh |
| **S3K** | Sonic 3 \& Knuckles | rounder | 5 | mid–high |
| **TPW** | Thunder Pro Wrestling | dark | 4 | low brightness |
| **Tick** | The Tick | dark | 2 | low brightness |
| **Tin** | Tinhead | dark | 4 | low brightness |
| **TG2** | Top Gear 2 | dark | 0 | racing / groove |

Full soundtrack VGMs (optional live): still download from VGMrips into `videos/vgm/` — not embedded in the PDF.

## Suggested preset IDs (exploratory app subset)

Use if the UI search is slow — search game name first, then click near these:

| Game | Example preset name | Notes | App `id` |
|------|---------------------|-------|----------|
| Streets of Rage | Instrument 7 | CON 4, FL 7, very bright | 16093 |
| Pulseman | Instrument 3 | CON 5, high brightness | 11938 |
| Nightmare Circus | Instrument 7 | CON 2, FL 0 | 10158 |
| Thunder Force IV | Instrument 7 | CON 4, FL 7 | 19258 |

(IDs from `webapp/public/data/presets.json` — may shift if the dataset is regenerated.)

## Timing tips

- Trim VGMs to a **loop-friendly 12 s** (Audacity / foobar convert) so you don’t talk over a long intro.
- Order on stage: **play VGM → mute → play preset → one sentence**.
- If Wi‑Fi dies: skip DAFMExplorer; use PDF star AIFFs or files in `videos/presets/`.

## Legal / courtesy

VGMs are for research/demo in a scholarly talk; prefer official VGMrips packs; don’t redistribute copyrighted ROMs — only the rip packs you already use for research.
