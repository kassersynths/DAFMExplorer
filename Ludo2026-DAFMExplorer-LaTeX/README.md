# Ludo2026 Beamer — DAFMExplorer

English Beamer deck for **Ludo2026**, Session 9 (*Synthesis, Served Three Ways*):

**Exploring the Sonic Universe of the Sega Genesis: Data Science, FM Synthesis, and 93,000+ Presets**

Abraham Casas (Electronics & CTO) & Maria Cerro (Design & CEO), Kasser Synths.  
Abraham presents (~20 min + Q&A).

## Build

**Recommended (brand fonts + Adobe inline star AIFFs):**

```bash
cd Ludo2026-DAFMExplorer-LaTeX
latexmk          # LuaLaTeX via .latexmkrc
# or: latexmk -pdflua main.tex
```

Open `main.pdf` in **Adobe Acrobat/Reader** to click S1–S5. Re-render audio from repo root: `npx --yes tsx scripts/render_con_eda_aiffs.ts`.

XeLaTeX keeps fonts but cannot embed Beamer `\sound`; use LuaLaTeX for the talk PDF.

### Brand (from [kassersynths.com](https://www.kassersynths.com/))

| Token | Value | Role |
|-------|-------|------|
| Magenta | `#ff02ff` | Primary accent / structure / footline |
| Cyan | `#00edff` | Secondary accent / bullets / links |
| Gold | `#f1c034` | Alert highlights |
| Black / panel | `#0a0a0a` / `#161922` | Slide backgrounds |
| Blue | `#0089f7` | Supporting accent (charts) |
| Headings | League Spartan (≈ site **Spartan**) | Titles / frame titles |
| Body | **Oxanium** | Running text |

Fonts live in `assets/fonts/`.

## Narrative focus

Slides emphasise **data extraction** and **exploratory data analysis** (FM history, operators, CON/FL, brightness, GEMS, composers/regions). PCA/ML and the web app appear only briefly at the end.

Do **not** structure the talk as “notebook 01 / 02”. Internally, material maps to:

| Talk language | Source in repo |
|---------------|----------------|
| Data extraction | `01-Data_Extraction.ipynb` |
| Data analysis / EDA | `02-Data_Analysis.ipynb` |

## Assets

| Path | Role |
|------|------|
| `assets/logo-kasser-synths.png` | Title / closing |
| `assets/photo_abraham.jpg` / `photo_maria.jpg` | Local portraits (gitignored); PNG placeholders optional |
| `assets/fig_*.png` | EDA charts from exploratory subset (`webapp/public/data/presets.json`) |
| `assets/*.jpg|png` | Historical / archival images from repo `images/` |
| `videos/V1.mp4` … `V3.mp4` | See `videos/README.md` |

**Corpus wording:** full archive **93,000+** presets; EDA charts may use the app’s exploratory subset (~22k). Say this once if asked.

## Speaker materials

- `notes/speaker_script_en.md` — **English spoken script, slide by slide** (~20 min)  
- `notes/audio/speaker_script_en_narration.mp3` — TTS draft narration (regenerate: `python scripts/narrate_speaker_script.py`)  
- `notes/speaker_script_es.md` — Spanish outline / cues  
- `videos/LIVE_DEMOS.md` — VGM + star AIFF cue sheet  
- `videos/README.md` — recording checklist

## Live demo (optional, ≤90 s)

https://dafm-explorer.vercel.app/  
Keep offline fallback: Video 3 + embedding slide.
