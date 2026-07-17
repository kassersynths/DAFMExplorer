# Live demos — VGM + presets (Ludo2026)

Play **outside** the PDF. Goal: short VGM clip of a game → isolate a related preset in [DAFMExplorer](https://dafm-explorer.vercel.app/).

Total live audio budget: **≈90–120 s** across the talk (not counting optional pre-recorded V1–V3).

## Offline setup (do this before the conference)

1. **VGM player**
   - Foobar2000 + [foo_input_vgm / in_vgm](https://vgmrips.net/), or **VGMPlay**
2. **Download packs** from [VGMrips](https://vgmrips.net/) (search game name → Mega Drive / Genesis):
   - *Streets of Rage* (Bare Knuckle)
   - *Pulseman*
   - *Nightmare Circus*
   - *Thunder Force IV* (Lightening Force)
3. Copy the `.vgm` / `.vgz` files into `videos/vgm/` (create folder) and rename clearly, e.g.:
   - `L1_streets_of_rage_stage.vgz`
   - `L2_pulseman_stage.vgz`
   - `L3_nightmare_circus.vgz`
   - `L4_thunder_force_iv_stage.vgz`
4. **DAFMExplorer offline fallback:** open https://dafm-explorer.vercel.app/ once on venue Wi‑Fi *or* run the local `webapp` build; pre-filter each game in a browser tab.
5. **Audio route:** laptop headphone-out → venue mixer; set a single volume for VGM and preset so jumps are small.

## Cue sheet

| Cue | Slide | VGM (≈10–15 s) | Preset in DAFMExplorer | Say (EN gist) |
|-----|-------|----------------|------------------------|---------------|
| **L1** | Composer signatures | *Streets of Rage* stage / “Fighting in the Street” | Filter `Streets of Rage` → pick a **FL≈7**, bright lead/bass | “Same energy you just heard — now as a single voice decision.” |
| **L2** | Game fingerprints | *Pulseman* energetic stage | Filter `Pulseman` → preset with **CON = 5** | “The histogram isn’t abstract: the score commits to a wiring.” |
| **L3** | GEMS in practice | *Nightmare Circus* title/stage | Filter `Nightmare Circus` (GEMS) → any clear lead | “US title, GEMS toolchain — listen, then freeze one patch.” |
| **L4** | GEMS in practice (pair) | *Thunder Force IV* stage | Filter `Thunder Force IV` → preset with a **different CON** than L3 | “Custom driver world — different algorithm neighbourhood.” |

Optional extras if time: *Gunstar Heroes* (variety), *Phantasy Star IV* (darker/atmospheric).

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
- If Wi‑Fi dies: skip DAFMExplorer; play a pre-exported WAV of the same presets (render from the app at home into `videos/presets/`).

## Legal / courtesy

VGMs are for research/demo in a scholarly talk; prefer official VGMrips packs; don’t redistribute copyrighted ROMs — only the rip packs you already use for research.
