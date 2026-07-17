# Ludo2026 Beamer — DAFMExplorer

English Beamer deck for **Ludo2026**, Session 9 (*Synthesis, Served Three Ways*):

**Exploring the Sonic Universe of the Sega Genesis: Data Science, FM Synthesis, and 93,000+ Presets**

Abraham Casas (Electronics & CTO) & Maria Cerro (Design & CEO), Kasser Synths.  
Abraham presents (~20 min + Q&A).

## Build

**Recommended (brand fonts from the site):**

```bash
cd Ludo2026-DAFMExplorer-LaTeX
latexmk -pdfxe main.tex
# or: xelatex main.tex && xelatex main.tex
```

pdfLaTeX also works (`latexmk -pdf`) with the same colours, but falls back to Latin Modern instead of Spartan/Oxanium.

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
| `assets/photo_abraham.png` / `photo_maria.png` | Replace with real portraits |
| `assets/fig_*.png` | EDA charts from exploratory subset (`webapp/public/data/presets.json`) |
| `assets/*.jpg|png` | Historical / archival images from repo `images/` |
| `videos/V1.mp4` … `V3.mp4` | See `videos/README.md` |

**Corpus wording:** full archive **93,000+** presets; EDA charts may use the app’s exploratory subset (~22k). Say this once if asked.

## Speaker materials

- `notes/speaker_script_es.md` — Spanish script (~20 min) with video cues  
- `videos/README.md` — recording checklist  

## Live demo (optional, ≤90 s)

https://dafm-explorer.vercel.app/  
Keep offline fallback: Video 3 + embedding slide.
