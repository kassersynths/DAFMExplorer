# TISMIR — Sound Similarity in YM2612 FM Presets

LaTeX scaffold for a Transactions of the ISMIR (TISMIR) article on timbre /
sound similarity over a large corpus of YM2612 game presets.

## Template

This folder uses the official lightweight TISMIR style (`tismir.sty`) from
[ismir/paper_templates_TISMIR_old](https://github.com/ismir/paper_templates_TISMIR_old).
For camera-ready layout closer to the published journal format, switch to
[ismir/paper_templates_TISMIR_new](https://github.com/ismir/paper_templates_TISMIR_new).
Both are accepted by TISMIR.

## Build

```bash
make          # pdflatex → bibtex → pdflatex × 2
make clean
```

Requirements: a TeX distribution with `pdflatex`, `bibtex`, and the fonts
pulled in by `tismir.sty` (Fourier / Quattrocento / Charter / Inconsolata).

## Figures and tables

**Do not hand-edit generated assets.** Figures and tables for the manuscript
are produced by the research pipeline:

```bash
cd ../research
make figures    # or: dafm figures
```

That command writes into:

- `figures/` — PDF/PNG plots for inclusion from `main.tex`
- `tables/` — optional exported TeX/CSV table fragments

Until evaluation artifacts exist under `research/artifacts/results/`, the
figure generator skips missing inputs gracefully and leaves placeholders.

Empty trackers: `figures/.gitkeep`, `tables/.gitkeep`.

## Scope reminder

The paper analysis starts from scratch. The only inheritance from earlier
repository work is `data/processed/all_instruments_final.csv`. Morph /
macro-control material is future outlook only, not a claimed contribution.

## Layout

| Path | Role |
|------|------|
| `main.tex` | Article skeleton (structure only) |
| `references.bib` | Bibliography |
| `tismir.sty` / `tismir.png` | Official lightweight TISMIR style |
| `Makefile` | `pdflatex` + `bibtex` build |
| `figures/` | Generated figures |
| `tables/` | Generated tables |
