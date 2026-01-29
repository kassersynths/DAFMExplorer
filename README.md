<p align="center">
  <img src="images/logo-kasser-synths.svg" alt="Kasser Synths Logo" width="300"/>
</p>

<h1 align="center">DAFMExplorer</h1>

<p align="center">
  <strong>Data Science meets FM Synthesis</strong><br>
  Exploring 93,000+ FM presets from the Sega Genesis/Mega Drive era
</p>

<p align="center">
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-notebooks">Notebooks</a> •
  <a href="#-web-app">Web App</a> •
  <a href="#-dataset">Dataset</a> •
  <a href="#-contributing">Contributing</a>
</p>

<p align="center">
  <a href="https://colab.research.google.com/github/kassersynths/DAFMExplorer/blob/main/01-Data_Extraction.ipynb">
    <img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open Data Extraction in Colab"/>
  </a>
  <a href="https://colab.research.google.com/github/kassersynths/DAFMExplorer/blob/main/02-Data_Analysis.ipynb">
    <img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open Data Analysis in Colab"/>
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License"/>
  </a>
</p>

<p align="center">
  <small><a href="https://www.kassersynths.com">kassersynths.com</a> · <a href="https://www.tindie.com/stores/kassersynths/">Tindie</a> · <a href="https://www.youtube.com/watch?v=VieWvUKpT6k">Arcade demos</a></small>
</p>

---

## 🎯 What is DAFMExplorer?

**DAFMExplorer** is an open-source educational project that combines **Data Science** and **FM Synthesis** to explore the sonic legacy of the Sega Genesis/Mega Drive era. 

Through interactive Jupyter notebooks and a web application, you'll learn:

- 🎵 **FM Synthesis fundamentals** - How the YM2612 chip created iconic sounds
- 📊 **Data Science techniques** - PCA, clustering, embeddings, and recommendation systems
- 🎮 **Gaming history** - Composers, tools (GEMS), and regional differences
- 🔍 **Preset exploration** - Find similar sounds and discover patterns

<p align="center">
  <img src="images/Sega-Genesis-Mod1-Bare.jpg" alt="Sega Genesis" width="400"/>
  <br>
  <em>The Sega Genesis/Mega Drive - Home of the YM2612 chip</em>
</p>

---

## 🚀 Quick Start

### Option 1: Google Colab (Recommended)

No installation required! Click the badges below to run the notebooks directly in your browser:

| Notebook | Description | Open in Colab |
|----------|-------------|---------------|
| **01-Data_Extraction** | Web scraping, data cleaning, preprocessing | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/kassersynths/DAFMExplorer/blob/main/01-Data_Extraction.ipynb) |
| **02-Data_Analysis** | ML analysis, clustering, visualizations | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/kassersynths/DAFMExplorer/blob/main/02-Data_Analysis.ipynb) |

### Option 2: Local Installation

```bash
# Clone the repository
git clone https://github.com/kassersynths/DAFMExplorer.git
cd DAFMExplorer

# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Launch Jupyter
jupyter notebook
```

---

## 📓 Notebooks

### 01 - Data Extraction

**From Chips to Dataframes: The Complete Data Pipeline**

This notebook handles all data extraction and preprocessing:

- 📦 **OPM File Parsing** - Extract 93,000+ presets from the DrWashington collection
- 🎮 **Game Name Extraction** - Parse filenames to identify source games
- 🧹 **Deduplication** - Remove volume-based duplicates (TL parameter)
- 🌐 **Web Scraping**:
  - GEMS game list from [Sega Retro](https://segaretro.org/GEMS)
  - Composer mappings from [VGMrips](https://vgmrips.net)
  - Composer info from Wikipedia
- ✅ **Data Validation** - Parameter range checks and quality control

**Key Concepts Covered:**
- Regular expressions for text parsing
- Web scraping with BeautifulSoup
- Data cleaning and normalization
- Caching strategies for expensive operations

### 02 - Data Analysis

**The Sound of a Generation: Data Science on 93,000 FM Presets**

This notebook performs comprehensive analysis:

- 📊 **Parameter Analysis** - Distribution of CON, FL, TL, MUL, AR, DT1/DT2
- 🧮 **Feature Engineering** - Brightness Index, Complexity Score
- 📉 **Dimensionality Reduction** - PCA for variance analysis
- 🗺️ **2D Embeddings** - t-SNE/UMAP for visualization
- 🎯 **Clustering** - KMeans with automatic elbow detection
- 🔍 **Recommendation System** - Nearest Neighbors for similar presets
- 🎼 **Composer Analysis** - Style signatures and regional patterns
- 🛠️ **GEMS Analysis** - Template sounds vs custom presets

**Key Concepts Covered:**
- StandardScaler for feature normalization
- PCA explained variance analysis
- t-SNE vs UMAP trade-offs
- KMeans clustering and the elbow method
- Nearest Neighbors for recommendations
- Interactive Plotly visualizations

---

## 🌐 Web App

An interactive single-page application to explore the 7 SONIC REALMS of FM synthesis:

```bash
cd webapp
npm install
npm run dev
```

### Features

- 🗺️ **Interactive 2D Embedding Map** - Explore 22,000+ presets visualized in 2D space with 7 distinct clusters
- 🎹 **Real-time FM Synthesis** - Play presets using the built-in YM2612 synthesizer with piano keyboard
- 🔍 **Advanced Filtering** - Filter by cluster, composer, game, nationality, and GEMS usage
- 🎯 **Similar Presets Discovery** - Find the 10 most similar presets to any selected preset
- 💾 **6 Memory Slots** - Save up to 6 presets and download them as a ZIP file (DMP format)
- 🎚️ **Octave Control** - Adjust octave range (0-7) with visual slider and numpad controls
- 📊 **Preset Information** - View detailed metadata including game, composer, nationality, cluster, and GEMS status
- 🎨 **7 SONIC REALMS** - Explore distinct clusters: Raw Signals, Neon Action, Polished Arcade, High-Speed Chiptune, Deep Space FM, Fantasy Atmospheres, Experimental Playgrounds

If you want to hear the same kind of FM in hardware form, we’ve recorded short Arcade demos on YouTube: [demo 1](https://www.youtube.com/watch?v=VieWvUKpT6k), [demo 2](https://www.youtube.com/watch?v=prvEFqbcZrc).

### Tech Stack

- React 19 + TypeScript
- Vite
- Tailwind CSS (Kasser Synths theme)
- JSZip (for preset downloads)

### Deployment

The webapp is a static site that can be deployed to any static hosting service:

- **Vercel** (recommended): `vercel` or connect GitHub repo
- **Netlify**: Drag & drop `dist/` folder
- **GitHub Pages**: Configure GitHub Actions
- **Cloudflare Pages**: Connect repository

See [webapp/README.md](webapp/README.md) for detailed deployment instructions.

---

## 📊 Dataset

### Source

The preset data comes from the **DrWashington collection**, a complete archive of Project2612 data containing OPM files extracted from VGM recordings of Sega Genesis games.

### Statistics

| Metric | Value |
|--------|-------|
| Total Presets | ~93,000 |
| Unique Games | ~700 |
| Parameters per Preset | 58 |
| GEMS Games | ~200 |

### Parameters

Each preset contains 58 parameters:

| Category | Parameters | Description |
|----------|------------|-------------|
| **LFO** | LFRQ, AMD, PMD, WF, NFRQ | Low-frequency oscillator |
| **Channel** | PAN, FL, CON, AMS, PMS, SLOT, NE | Global settings |
| **Operators** | AR, D1R, D2R, RR, D1L, TL, KS, MUL, DT1, DT2, AMS-EN | ×4 operators |

### Generated Artifacts

The notebooks generate several cached files in `artifacts/`:

| File | Description |
|------|-------------|
| `presets_final.csv` | Cleaned dataset with all enrichments |
| `embedding_coordinates.csv` | 2D coordinates for visualization |
| `gems_games.csv` | List of games that used GEMS |
| `vgmrips_composers.csv` | Game-composer mappings |
| `composers_info.csv` | Composer nationalities |
| `cluster_results.joblib` | KMeans clustering results |
| `nn_index.joblib` | Nearest Neighbors index |

---

## 🎹 FM Synthesis Primer

### The YM2612 Chip

The **YM2612** (OPN2) was the FM synthesis chip in the Sega Genesis/Mega Drive:

- **4 operators** per channel (M1, C1, M2, C2)
- **8 algorithms** defining operator connections
- **6 FM channels** + 1 PSG channel

### Key Parameters

| Parameter | Range | Description |
|-----------|-------|-------------|
| **CON** (Algorithm) | 0-7 | How operators connect |
| **FL** (Feedback) | 0-7 | Self-modulation of operator 1 |
| **TL** (Total Level) | 0-127 | Volume/attenuation |
| **MUL** (Multiplier) | 0-15 | Frequency ratio |
| **AR** (Attack Rate) | 0-31 | How fast sound starts |
| **DT1/DT2** (Detune) | 0-7/0-3 | Pitch variation |

### Notable Composers

- **Yuzo Koshiro** (Japan) - Streets of Rage, Shinobi III
- **Masato Nakamura** (Japan) - Sonic the Hedgehog
- **Howard Drossin** (USA) - Comix Zone
- **Tommy Tallarico** (USA) - Earthworm Jim

---

## 🤝 Contributing

We welcome contributions! Here's how you can help:

### Ways to Contribute

- 🐛 **Bug Reports** - Found an issue? Open a GitHub issue
- 💡 **Feature Requests** - Have an idea? Let us know
- 📝 **Documentation** - Improve explanations or add examples
- 🔧 **Code** - Fix bugs or implement new features
- 🎨 **Design** - Improve visualizations or UI

### Development Setup

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Run tests (if applicable)
5. Commit: `git commit -m 'Add amazing feature'`
6. Push: `git push origin feature/amazing-feature`
7. Open a Pull Request

### Code Style

- Python: Follow PEP 8
- TypeScript: Use ESLint configuration
- Notebooks: Clear markdown explanations between code cells

---

## 📁 Project Structure

```
DAFMExplorer/
├── 01-Data_Extraction.ipynb    # Data extraction notebook
├── 02-Data_Analysis.ipynb      # Data analysis notebook
├── requirements.txt            # Python dependencies
├── LICENSE                     # MIT License
├── README.md                   # This file
├── artifacts/                  # Generated data files (cached)
│   ├── presets_final.csv
│   ├── embedding_coordinates.csv
│   ├── cluster_results.joblib
│   ├── nn_index.joblib
│   └── ...
├── data/
│   ├── raw/                    # Original data files
│   │   └── OPM presets.zip
│   └── processed/              # Processed data
│       └── all_instruments_final.csv
├── images/                     # Images for notebooks and webapp
│   └── logo-kasser-synths.svg
├── scripts/
│   └── generate_webapp_data.py # Script to generate presets.json
└── webapp/                     # React web application
    ├── App.tsx                 # Main application component
    ├── index.tsx               # Entry point
    ├── index.html              # HTML template
    ├── package.json            # Node dependencies
    ├── vite.config.ts          # Vite configuration
    ├── tsconfig.json           # TypeScript configuration
    ├── vercel.json             # Vercel deployment config
    ├── README.md               # Webapp documentation
    ├── components/             # React components
    │   ├── PresetMap.tsx       # 2D embedding visualization
    │   ├── FilterPanel.tsx     # Filter controls
    │   ├── SynthPanel.tsx      # Piano keyboard and octave controls
    │   ├── SlotsGrid.tsx       # 6 preset memory slots
    │   ├── BottomBar.tsx       # Oscilloscope and download
    │   ├── PresetInfo.tsx      # Preset details display
    │   ├── PresetParamsAccordion.tsx  # FM parameters accordion
    │   ├── SimilarInstrumentsAccordion.tsx  # Similar presets accordion
    │   ├── InfoEasterEgg.tsx   # Project information modal
    │   └── Accordion.tsx       # Reusable accordion component
    ├── hooks/
    │   └── usePresetData.ts    # Data loading hook
    ├── services/
    │   ├── audio/              # Audio engine
    │   └── dmpLoader.ts        # DMP file handling
    ├── types/
    │   └── preset.ts           # TypeScript types
    ├── utils/
    │   ├── clusterUtils.ts     # Cluster utilities
    │   ├── gemsNormalizer.ts   # GEMS normalization
    │   └── pianoLayout.ts      # Piano configuration
    └── public/
        ├── data/
        │   └── presets.json    # Preset dataset (generated)
        └── logo-kasser-synths.svg
```

---

## 📜 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **DrWashington** - For the comprehensive OPM preset collection
- **Project2612** - For preserving VGM files
- **VGMrips** - For game-composer mappings
- **Sega Retro** - For GEMS documentation
- **The chiptune community** - For keeping retro sound alive

---

## 📬 Contact

**Kasser Synths**

- Website: [kassersynths.com](https://www.kassersynths.com)
- Tindie: [kassersynths](https://www.tindie.com/stores/kassersynths/)
- GitHub: [@kassersynths](https://github.com/kassersynths)

---

<p align="center">
  Made with ❤️ for the retro gaming and chiptune community
  <br><br>
  <strong>KASSER SYNTHS</strong>
</p>
