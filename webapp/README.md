# DAFMExplorer Web Application

Interactive web application for exploring FM synthesis presets from the SEGA Genesis / Mega Drive era.

## 🚀 Quick Start

### Prerequisites

- Node.js 18+ and npm

### Installation

```bash
cd webapp
npm install
```

### Development

```bash
npm run dev
```

The application will be available at `http://localhost:3000`

### Production Build

```bash
npm run build
```

The production build will be generated in the `dist/` directory, ready for deployment.

### Preview Production Build

```bash
npm run preview
```

## 📦 Deployment

### Vercel (Recommended)

1. Install Vercel CLI: `npm i -g vercel`
2. Deploy: `vercel`
3. Or connect your GitHub repository to Vercel for automatic deployments

The application is a static site and works with any static hosting service:
- Vercel
- Netlify
- GitHub Pages
- Cloudflare Pages

## 🎨 Features

- **Interactive 2D Embedding Map**: Explore 22,000+ presets visualized in 2D space
- **Real-time FM Synthesis**: Play presets using the built-in YM2612 synthesizer
- **Preset Filtering**: Filter by cluster, composer, game, nationality, and GEMS usage
- **Similar Presets Discovery**: Find presets similar to any selected preset
- **6 Memory Slots**: Save up to 6 presets and download them as a ZIP file
- **Piano Keyboard**: Play notes using the numpad (0-9, /, *, +, -)
- **Octave Control**: Adjust octave range (0-7) with visual slider
- **Preset Information**: View detailed metadata for each preset

## 🛠️ Tech Stack

- **React 19** + **TypeScript**
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Styling with custom Kasser Synths theme
- **JSZip** - ZIP file generation for preset downloads

## 📁 Project Structure

```
webapp/
├── App.tsx                    # Main application component
├── index.tsx                 # Entry point
├── index.html                # HTML template
├── package.json             # Dependencies
├── vite.config.ts           # Vite configuration
├── tsconfig.json            # TypeScript configuration
├── vercel.json              # Vercel deployment config
├── README.md                # This file
├── components/              # React components
│   ├── PresetMap.tsx        # 2D embedding visualization
│   ├── FilterPanel.tsx      # Filter controls
│   ├── SynthPanel.tsx       # Piano keyboard and octave controls
│   ├── SlotsGrid.tsx        # 6 preset memory slots
│   ├── BottomBar.tsx        # Oscilloscope and download
│   ├── PresetInfo.tsx       # Preset details display
│   ├── PresetParamsAccordion.tsx  # FM parameters accordion
│   ├── SimilarInstrumentsAccordion.tsx  # Similar presets accordion
│   ├── InfoEasterEgg.tsx    # Project information modal
│   └── Accordion.tsx        # Reusable accordion component
├── hooks/
│   └── usePresetData.ts     # Data loading and filtering logic
├── services/
│   ├── audio/               # Audio engine and YM2612 core
│   └── dmpLoader.ts         # DMP file format handling
├── types/
│   └── preset.ts            # TypeScript type definitions
├── utils/
│   ├── clusterUtils.ts      # Cluster name/color utilities
│   ├── gemsNormalizer.ts    # GEMS value normalization
│   └── pianoLayout.ts       # Piano layout configuration
├── public/
│   ├── data/
│   │   └── presets.json     # Preset dataset (generated from notebooks)
│   └── logo-kasser-synths.svg
└── dist/                    # Production build output
```

## 📊 Data Format

The application expects `public/data/presets.json` with the following structure:

```typescript
{
  presets: Array<{
    id: number;
    name: string;
    game: string;
    composer?: string;
    nationality?: string;
    gems: boolean;
    cluster?: number;
    clusterId?: number;
    clusterName?: string;
    params: {
      // FM synthesis parameters
      con: number;
      fl: number;
      lfrq: number;
      ams: number;
      pms: number;
      // ... operator parameters
    };
    // ... embedding coordinates, scores, etc.
  }>;
  clusters: string[];
  composers: string[];
  games: string[];
  nationalities: string[];
}
```

Generate this file using the Jupyter notebooks in the root directory.

## 🎹 Controls

### Numpad Mapping

- **Notes**: `0`, `.`, `1-9`, `/`, `*` (C, C#, D, D#, E, F, F#, G, G#, A, A#, B, C+1)
- **Octave**: `+` (increase), `-` (decrease)

### Mouse/Touch

- Click on preset points in the map to load them
- Click on slots to switch active slot
- Use piano keys to play notes
- Use octave slider to change octave range

## 🔧 Configuration

### Piano Layout

Edit `utils/pianoLayout.ts` to adjust black key positioning:

- `BLACK_KEY_Y_OFFSET_FRAC`: Vertical offset (0.0-0.3)
- `BLACK_KEY_X_SPACING_FRAC`: Horizontal spacing (0.0-0.1)

### Cluster Colors

Cluster colors are defined in `types/preset.ts` and used consistently via `utils/clusterUtils.ts`.

## 📝 License

MIT License - See [LICENSE](../LICENSE) file for details.

## 🙏 Acknowledgments

- **DrWashington** - OPM preset collection
- **Project2612** - VGM preservation
- **Kasser Synths** - Development and design
