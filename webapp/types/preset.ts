/**
 * Types for the Kasser Preset Explorer
 */

// Operator parameters (M1, C1, M2, C2)
export interface OperatorData {
  ar: number;    // Attack Rate (0-31)
  d1r: number;   // Decay 1 Rate (0-31)
  d2r: number;   // Decay 2 Rate (0-31)
  rr: number;    // Release Rate (0-15)
  d1l: number;   // Decay 1 Level (0-15)
  tl: number;    // Total Level (0-127)
  ks: number;    // Key Scale (0-3)
  mul: number;   // Multiplier (0-15)
  dt1: number;   // Detune 1 (0-7)
  dt2: number;   // Detune 2 (0-3)
  ams_en: number; // AM Enable (0-1)
}

// Full FM parameters
export interface FMParams {
  lfrq: number;  // LFO Frequency
  amd: number;   // AM Depth
  pmd: number;   // PM Depth
  wf: number;    // Waveform
  nfrq: number;  // Noise Frequency
  pan: number;   // Pan (0-3)
  ams: number;   // AM Sensitivity
  pms: number;   // PM Sensitivity
  slot: number;  // Slot mask
  ne: number;    // Noise Enable
  m1: OperatorData;
  c1: OperatorData;
  m2: OperatorData;
  c2: OperatorData;
}

// Single preset from the dataset
export interface DatasetPreset {
  id: number;
  name: string;
  game: string;
  x: number;           // Embedding X coordinate
  y: number;           // Embedding Y coordinate
  cluster: number;     // Cluster ID (0-6)
  composer: string | null;
  nationality: string;
  gems: boolean;       // Uses GEMS driver
  brightness: number;  // Brightness Index (0-1)
  complexity: number;  // Complexity Score (0-1)
  con: number;         // Algorithm/Connection (0-7)
  fl: number;          // Feedback Level (0-7)
  params: FMParams;
}

// Cluster statistics
export interface ClusterStats {
  id: number;
  modeCon: number;
  modeFl: number;
  avgBrightness: number;
  avgComplexity: number;
  presetCount: number;
  topGame: string;
}

// Composer statistics
export interface ComposerStats {
  name: string;
  nationality: string;
  presetCount: number;
  games: string[];
}

// Game statistics
export interface GameStats {
  name: string;
  composer: string | null;
  nationality: string;
  gems: boolean;
  presetCount: number;
}

// Metadata
export interface DataMeta {
  totalPresets: number;
  totalClusters: number;
  totalComposers: number;
  totalGames: number;
  generatedAt: string;
}

// Complete dataset structure
export interface PresetDataset {
  presets: DatasetPreset[];
  clusters: ClusterStats[];
  composers: ComposerStats[];
  games: GameStats[];
  nationalities: string[];
  meta: DataMeta;
}

// Filter state
export interface PresetFilters {
  clusters: number[];           // Selected cluster IDs
  composer: string | null;      // Selected composer
  nationality: string | null;   // Selected nationality
  game: string | null;          // Selected game
  gems: boolean | null;         // GEMS filter (null = all)
  brightnessRange: [number, number];
  complexityRange: [number, number];
  searchQuery: string;
}

// Color mode for the map
export type MapColorMode = 
  | 'cluster' 
  | 'nationality' 
  | 'gems' 
  | 'brightness' 
  | 'complexity';

// App tabs
export type AppTab = 'explorer' | 'clusters' | 'composers' | 'games';

// Cluster colors (Kasser palette)
export const CLUSTER_COLORS: Record<number, string> = {
  0: '#bc13fe',  // Violet
  1: '#00eaff',  // Cyan
  2: '#00ff88',  // Green
  3: '#ff0080',  // Magenta
  4: '#00d4ff',  // Blue
  5: '#ff5722',  // Orange
  6: '#8b5cf6',  // Purple
};

// Official Cluster Names for UI display
export const CLUSTER_NAMES: Record<number, string> = {
  0: 'Raw Signals',
  1: 'Neon Action',
  2: 'Polished Arcade',
  3: 'High-Speed Chiptune',
  4: 'Deep Space FM',
  5: 'Fantasy Atmospheres',
  6: 'Experimental Playgrounds',
};

// Nationality colors
export const NATIONALITY_COLORS: Record<string, string> = {
  'Japan': '#e60012',    // Red
  'USA': '#3b82f6',      // Blue
  'UK': '#22c55e',       // Green
  'Unknown': '#6b7280',  // Gray
};

// Default filter state
export const DEFAULT_FILTERS: PresetFilters = {
  clusters: [],
  composer: null,
  nationality: null,
  game: null,
  gems: null,
  brightnessRange: [0, 1],
  complexityRange: [0, 1],
  searchQuery: '',
};
