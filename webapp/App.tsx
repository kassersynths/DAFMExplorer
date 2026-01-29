/**
 * Kasser Preset Explorer - Main App
 * 
 * Single-page application for YM2612 preset exploration with:
 * - 2D embedding map visualization
 * - Real-time FM synthesis
 * - Preset filtering and search
 * - Similar preset discovery
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import JSZip from 'jszip';
import { AudioEngine } from './services/audio/audioEngine';
import { writeDMP, PRESETS } from './services/dmpLoader';
import { YM2612Patch, FMAlgorithm, DEFAULT_PATCH } from './types';
import { usePresetData } from './hooks/usePresetData';
import { PresetMap } from './components/PresetMap';
import { FilterPanel } from './components/FilterPanel';
import { PresetParamsAccordion } from './components/PresetParamsAccordion';
import { SimilarInstrumentsAccordion } from './components/SimilarInstrumentsAccordion';
import { SynthPanel } from './components/SynthPanel';
import { BottomBar } from './components/BottomBar';
import { SlotsGrid } from './components/SlotsGrid';
import { InfoEasterEgg } from './components/InfoEasterEgg';
import type { DatasetPreset } from './types/preset';
import { resolveClusterForPreset } from './utils/clusterUtils';

// Extended slot type to include preset metadata
interface SlotData {
  patch: YM2612Patch;
  game?: string;
  presetName?: string;
  presetId?: number; // Store preset ID for exact matching
}

// Convert dataset preset to YM2612Patch for the synth
function datasetPresetToPatch(preset: DatasetPreset): YM2612Patch {
  const p = preset.params;
  return {
    name: preset.name,
    description: `${preset.game}${preset.composer ? ` - ${preset.composer}` : ''}`,
    algorithm: preset.con as FMAlgorithm,
    feedback: preset.fl,
    lfoFreq: p.lfrq,
    ams: p.ams,
    fms: p.pms,
    operators: [
      {
        id: 0,
        ar: p.m1.ar,
        dr: p.m1.d1r,
        sr: p.m1.d2r,
        rr: p.m1.rr,
        sl: p.m1.d1l,
        tl: p.m1.tl,
        mul: p.m1.mul,
        dt: p.m1.dt1,
        rs: p.m1.ks,
        ams: p.m1.ams_en === 1,
      },
      {
        id: 1,
        ar: p.c1.ar,
        dr: p.c1.d1r,
        sr: p.c1.d2r,
        rr: p.c1.rr,
        sl: p.c1.d1l,
        tl: p.c1.tl,
        mul: p.c1.mul,
        dt: p.c1.dt1,
        rs: p.c1.ks,
        ams: p.c1.ams_en === 1,
      },
      {
        id: 2,
        ar: p.m2.ar,
        dr: p.m2.d1r,
        sr: p.m2.d2r,
        rr: p.m2.rr,
        sl: p.m2.d1l,
        tl: p.m2.tl,
        mul: p.m2.mul,
        dt: p.m2.dt1,
        rs: p.m2.ks,
        ams: p.m2.ams_en === 1,
      },
      {
        id: 3,
        ar: p.c2.ar,
        dr: p.c2.d1r,
        sr: p.c2.d2r,
        rr: p.c2.rr,
        sl: p.c2.d1l,
        tl: p.c2.tl,
        mul: p.c2.mul,
        dt: p.c2.dt1,
        rs: p.c2.ks,
        ams: p.c2.ams_en === 1,
      },
    ],
  };
}

// Initial presets for the 6 slots - loaded from the library
const INITIAL_PRESETS: YM2612Patch[] = [
  PRESETS.ELECTRO_BASS,
  PRESETS.PADS,
  PRESETS.DX_PIANO,
  PRESETS.SYNTH_BRASS,
  PRESETS.FM_SNARE,
  PRESETS.FM_KICK,
];

const App: React.FC = () => {
  // Audio state
  const [audioEngine, setAudioEngine] = useState<AudioEngine | null>(null);
  const [analyser, setAnalyser] = useState<AnalyserNode | null>(null);
  const [started, setStarted] = useState(false);
  
  // Preset slots with metadata
  const [presetSlots, setPresetSlots] = useState<SlotData[]>(
    INITIAL_PRESETS.map(patch => ({ patch, game: undefined, presetName: patch.name }))
  );
  const [activeSlotIndex, setActiveSlotIndex] = useState(0);
  
  // Download state
  const [isDownloading, setIsDownloading] = useState(false);
  
  // Hovered preset state
  const [hoveredPreset, setHoveredPreset] = useState<DatasetPreset | null>(null);
  
  // Preset data hook
  const {
    dataset,
    loading,
    error,
    filteredPresets,
    filters,
    setFilters,
    resetFilters,
    selectedPreset,
    setSelectedPreset,
    stats,
  } = usePresetData();

  // Find preset from active slot in dataset - SINGLE SOURCE OF TRUTH for active preset
  // This is the ONLY place that determines what preset is shown in the right panel
  const activeSlotPreset = React.useMemo(() => {
    if (!dataset) return null;
    const activeSlot = presetSlots[activeSlotIndex];
    if (!activeSlot) return null;
    
    let found: DatasetPreset | null = null;
    let searchMethod = '';
    
    // PRIORITY 1: Find by preset ID (most reliable - exact match)
    if (activeSlot.presetId !== undefined) {
      found = dataset.presets.find(p => p.id === activeSlot.presetId) || null;
      if (found) {
        searchMethod = 'by ID';
      }
    }
    
    // PRIORITY 2: Find by name AND game (exact match) - only if ID search failed
    // IMPORTANT: Names are NOT unique, only Game+Name combination is unique
    if (!found && activeSlot.presetName && activeSlot.game) {
      found = dataset.presets.find(
        p => p.name === activeSlot.presetName && p.game === activeSlot.game
      ) || null;
      if (found) {
        searchMethod = 'by name+game';
      }
    }
    
    // NO FALLBACK: Do NOT search by name only - names are not unique!
    // If we don't have ID or Game+Name, we cannot reliably find the preset
    // This prevents finding wrong presets with duplicate names
    
    // Debug log to verify cluster consistency (temporary - remove after verification)
    if (found) {
      const clusterInfo = resolveClusterForPreset(found);
      console.log(`[activeSlotPreset] Found: "${found.name}" (${found.game}) | Cluster: ${clusterInfo.name} (ID: ${clusterInfo.id}, color: ${clusterInfo.color}) | Method: ${searchMethod} | Slot had ID: ${activeSlot.presetId}`);
    } else if (activeSlot.presetName) {
      console.warn(`[activeSlotPreset] Could not find preset: "${activeSlot.presetName}" | Game: ${activeSlot.game || 'missing'} | ID: ${activeSlot.presetId || 'missing'} | Need either ID or Game+Name to find preset`);
    }
    
    return found;
  }, [dataset, presetSlots, activeSlotIndex]);

  // Calculate similar presets for active slot preset
  const activeSlotSimilarPresets = React.useMemo(() => {
    if (!activeSlotPreset || !dataset) return [];
    
    const distances = dataset.presets.map(p => ({
      preset: p,
      distance: Math.sqrt(
        Math.pow(p.x - activeSlotPreset.x, 2) + 
        Math.pow(p.y - activeSlotPreset.y, 2)
      )
    }));
    
    return distances
      .filter(d => d.preset.id !== activeSlotPreset.id)
      .sort((a, b) => a.distance - b.distance)
      .slice(0, 5)
      .map(d => d.preset);
  }, [activeSlotPreset, dataset]);

  // Initialize audio automatically when component mounts (no splash screen)
  useEffect(() => {
    if (!started && !loading && !error) {
      const engine = new AudioEngine();
      setAudioEngine(engine);
      setAnalyser(engine.getAnalyser());
      setStarted(true);
      engine.setPatch(presetSlots[0].patch);
    }
  }, [started, loading, error, presetSlots]);

  // Handle slot change
  const handleSlotChange = useCallback((slotIndex: number) => {
    if (slotIndex >= 0 && slotIndex < 6) {
      setActiveSlotIndex(slotIndex);
      if (audioEngine) {
        audioEngine.setPatch(presetSlots[slotIndex].patch);
      }
    }
  }, [audioEngine, presetSlots]);

  // Load preset from dataset to current slot
  const handleLoadPresetToSlot = useCallback((preset: DatasetPreset) => {
    const patch = datasetPresetToPatch(preset);
    
    setPresetSlots(prev => {
      const newSlots = [...prev];
      newSlots[activeSlotIndex] = {
        patch,
        game: preset.game,
        presetName: preset.name,
        presetId: preset.id, // Store ID for exact matching
      };
      return newSlots;
    });
    
    if (audioEngine) {
      audioEngine.setPatch(patch);
    }
  }, [activeSlotIndex, audioEngine]);

  // Clear a slot
  const handleSlotClear = useCallback((slotIndex: number) => {
    setPresetSlots(prev => {
      const newSlots = [...prev];
      newSlots[slotIndex] = {
        patch: DEFAULT_PATCH,
        game: undefined,
        presetName: undefined,
        presetId: undefined, // Clear ID when clearing slot
      };
      return newSlots;
    });
  }, []);

  // Handle clicking on a preset from the map - select AND load it
  const handlePresetClick = useCallback((preset: DatasetPreset) => {
    setSelectedPreset(preset);
    handleLoadPresetToSlot(preset);
  }, [setSelectedPreset, handleLoadPresetToSlot]);

  // Handle clicking on a similar preset
  const handleSimilarPresetClick = useCallback((preset: DatasetPreset) => {
    setSelectedPreset(preset);
    handleLoadPresetToSlot(preset);
  }, [setSelectedPreset, handleLoadPresetToSlot]);

  // Note handlers
  const handleNoteOn = useCallback((note: number) => {
    if (audioEngine) {
      audioEngine.noteOn(note);
    }
  }, [audioEngine]);

  const handleNoteOff = useCallback((note: number) => {
    if (audioEngine) {
      audioEngine.noteOff(note);
    }
  }, [audioEngine]);

  // Download bank as ZIP
  const handleDownloadBank = useCallback(async () => {
    setIsDownloading(true);
    
    try {
      const zip = new JSZip();
      const bankFolder = zip.folder('KASSER_BANK');
      
      if (bankFolder) {
        presetSlots.forEach((slot, index) => {
          const buffer = writeDMP(slot.patch);
          const fileName = `PATCH${(index + 1).toString().padStart(2, '0')}.dmp`;
          bankFolder.file(fileName, buffer);
        });
        
        const words = ['NEON', 'FM', 'GENESIS', 'BLAST', 'SYNTH', 'CHIP', 'WAVE', 'RETRO', 'CYBER', 'DRIVE'];
        const w1 = words[Math.floor(Math.random() * words.length)];
        const w2 = words[Math.floor(Math.random() * words.length)];
        const zipName = `KASSER_${w1}_${w2}_BANK.zip`;
        
        const content = await zip.generateAsync({ type: 'blob' });
        
        const url = window.URL.createObjectURL(content);
        const a = document.createElement('a');
        a.href = url;
        a.download = zipName;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }
    } catch (e) {
      console.error('Download failed:', e);
    } finally {
      setIsDownloading(false);
    }
  }, [presetSlots]);

  const currentPatch = presetSlots[activeSlotIndex].patch;

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-[#050505] flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-kasser-violet border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-400 text-sm">Loading preset data...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="min-h-screen bg-[#050505] flex items-center justify-center">
        <div className="text-center max-w-md p-6 bg-[#111] border border-red-500/50 rounded-lg">
          <p className="text-red-400 text-sm mb-2">Failed to load preset data</p>
          <p className="text-gray-500 text-xs">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen bg-[#050505] text-white font-mono bg-[radial-gradient(#222_1px,transparent_1px)] bg-[length:20px_20px] flex flex-col overflow-hidden">
      {/* Header with Branding */}
      <header className="sticky top-0 z-50 bg-[#050505]/95 backdrop-blur-xl border-b border-[#222] px-4 py-3">
        <div className="max-w-[1800px] mx-auto flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex flex-col">
            <h1 className="text-2xl sm:text-3xl font-display font-black text-white leading-tight">
              <span className="text-kasser-blue drop-shadow-[0_0_15px_rgba(0,234,255,0.6)]">DAFMExplorer</span>
              <span className="text-xs sm:text-sm text-kasser-violet font-bold ml-2 sm:ml-3">
                by <span className="text-white">KASSER SYNTHS</span>
              </span>
            </h1>
            <p className="text-[10px] sm:text-xs text-white/90 mt-1.5 max-w-2xl">
              Explore the <span className="text-kasser-violet">7 SONIC REALMS</span> of FM synthesis in the SEGA Genesis / Mega Drive.
            </p>
          </div>
          
          {/* Logo + Easter Egg Info Button */}
          <div className="flex items-center gap-3">
            <a href="https://www.tindie.com/stores/kassersynths/?ref=offsite_badges&utm_source=sellers_Kasser&utm_medium=badges&utm_campaign=badge_medium" target="_blank" rel="noopener noreferrer" className="shrink-0" title="I sell on Tindie">
              <img src="https://d2ss6ovg47m0r5.cloudfront.net/badges/tindie-mediums.png" alt="I sell on Tindie" width={150} height={78} className="h-[52px] w-auto" />
            </a>
            <img 
              src="/logo-kasser-synths.svg"
              alt="Kasser Synths" 
              className="w-auto opacity-90 hover:opacity-100 transition-opacity"
              style={{ 
                pointerEvents: 'none',
                height: 'clamp(80px, 10vh, 120px)',
                maxHeight: '120px',
                filter: 'brightness(0) invert(1) drop-shadow(0 0 2px rgba(0, 234, 255, 0.3))'
              }}
            />
            <InfoEasterEgg />
          </div>
        </div>
      </header>
      {/* Main Layout - Grid for balanced heights */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-3 p-3 min-h-0">
        {/* Left: Map Area */}
        <div className="flex flex-col gap-3 min-w-0 min-h-0">
          {/* Map Container */}
          <div className="flex-1 relative min-h-[300px]">
            {dataset && (
              <>
                <PresetMap
                  allPresets={dataset.presets}
                  filteredPresets={filteredPresets}
                  selectedPreset={activeSlotPreset}
                  similarPresets={activeSlotSimilarPresets}
                  onPresetClick={handlePresetClick}
                  onPresetHover={setHoveredPreset}
                />
                
                {/* Filter Panel Overlay */}
                <FilterPanel
                  filters={filters}
                  onFiltersChange={setFilters}
                  clusters={dataset.clusters}
                  composers={dataset.composers}
                  games={dataset.games}
                  nationalities={dataset.nationalities}
                  stats={stats}
                  onReset={resetFilters}
                />

                {/* Parameters Accordion */}
                <PresetParamsAccordion
                  patch={currentPatch}
                  disabled={!activeSlotPreset}
                />

                {/* Similar Instruments Accordion */}
                <SimilarInstrumentsAccordion
                  presets={activeSlotSimilarPresets}
                  onPresetClick={handleSimilarPresetClick}
                  disabled={!activeSlotPreset}
                />
              </>
            )}
          </div>

          {/* Bottom Bar: Oscilloscope + Download */}
          <div className="flex-shrink-0">
            <BottomBar
              analyser={analyser}
              onDownload={handleDownloadBank}
              isDownloading={isDownloading}
            />
          </div>
        </div>

        {/* Right: Info + Synth Panel */}
        <div className="flex flex-col gap-3 min-h-0">
          {/* Slots Grid */}
          <div className="flex-shrink-0">
            <SlotsGrid
              slots={presetSlots.map(slot => ({
                ...slot.patch,
                description: slot.game || slot.patch.description,
                name: slot.presetName || slot.patch.name,
              }))}
              activeSlotIndex={activeSlotIndex}
              onSlotClick={handleSlotChange}
              onSlotClear={handleSlotClear}
            />
          </div>

          {/* Synth Panel (Octave + Keys + Preset Info) - Fixed height to match left column */}
          <div className="flex-1 min-h-0 overflow-hidden" style={{ minHeight: 'clamp(360px, 42vh, 520px)', height: '100%' }}>
            <SynthPanel
              activeSlot={activeSlotIndex + 1}
              onSlotChange={(slot) => handleSlotChange(slot - 1)}
              onNoteOn={handleNoteOn}
              onNoteOff={handleNoteOff}
              activePreset={activeSlotPreset}
            />
          </div>

          {/* Similar Presets panel removed - similar presets are shown in the accordion above */}
        </div>
      </div>
    </div>
  );
};

export default App;
