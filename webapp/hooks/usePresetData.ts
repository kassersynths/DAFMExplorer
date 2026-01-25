/**
 * Hook to load and manage preset data
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import type { 
  PresetDataset, 
  DatasetPreset, 
  PresetFilters, 
  DEFAULT_FILTERS 
} from '../types/preset';
import { normalizeGems } from '../utils/gemsNormalizer';
import { resolveClusterForPreset } from '../utils/clusterUtils';

interface UsePresetDataReturn {
  // Data
  dataset: PresetDataset | null;
  loading: boolean;
  error: string | null;
  
  // Filtered data
  filteredPresets: DatasetPreset[];
  
  // Filters
  filters: PresetFilters;
  setFilters: React.Dispatch<React.SetStateAction<PresetFilters>>;
  resetFilters: () => void;
  
  // Selection
  selectedPreset: DatasetPreset | null;
  setSelectedPreset: (preset: DatasetPreset | null) => void;
  
  // Similar presets
  similarPresets: DatasetPreset[];
  
  // Stats
  stats: {
    total: number;
    filtered: number;
    percentage: number;
  };
}

const DEFAULT_FILTER_STATE: PresetFilters = {
  clusters: [],
  composer: null,
  nationality: null,
  game: null,
  gems: null,
  brightnessRange: [0, 1],
  complexityRange: [0, 1],
  searchQuery: '',
};

/**
 * Find K nearest presets in embedding space
 */
function findSimilarPresets(
  preset: DatasetPreset, 
  allPresets: DatasetPreset[], 
  k: number = 10
): DatasetPreset[] {
  const distances = allPresets.map(p => ({
    preset: p,
    distance: Math.sqrt(
      Math.pow(p.x - preset.x, 2) + 
      Math.pow(p.y - preset.y, 2)
    )
  }));
  
  return distances
    .filter(d => d.preset.id !== preset.id)
    .sort((a, b) => a.distance - b.distance)
    .slice(0, k)
    .map(d => d.preset);
}

/**
 * Apply filters to presets
 */
function applyFilters(presets: DatasetPreset[], filters: PresetFilters): DatasetPreset[] {
  return presets.filter(preset => {
    // Cluster filter - use resolveClusterForPreset for consistency
    if (filters.clusters.length > 0) {
      const clusterInfo = resolveClusterForPreset(preset);
      if (!filters.clusters.includes(clusterInfo.id)) {
        return false;
      }
    }
    
    // Composer filter
    if (filters.composer && preset.composer !== filters.composer) {
      return false;
    }
    
    // Nationality filter
    if (filters.nationality && preset.nationality !== filters.nationality) {
      return false;
    }
    
    // Game filter
    if (filters.game && preset.game !== filters.game) {
      return false;
    }
    
    // GEMS filter - robust normalization
    if (filters.gems !== null) {
      const presetHasGems = normalizeGems(preset.gems);
      // If filter is YES, only include presets with GEMS=true
      // If filter is NO, only include presets with GEMS=false
      if (filters.gems !== presetHasGems) {
        return false;
      }
    }
    
    // Brightness range
    if (preset.brightness < filters.brightnessRange[0] || 
        preset.brightness > filters.brightnessRange[1]) {
      return false;
    }
    
    // Complexity range
    if (preset.complexity < filters.complexityRange[0] || 
        preset.complexity > filters.complexityRange[1]) {
      return false;
    }
    
    // Search query (name or game)
    if (filters.searchQuery) {
      const query = filters.searchQuery.toLowerCase();
      const nameMatch = preset.name.toLowerCase().includes(query);
      const gameMatch = preset.game.toLowerCase().includes(query);
      const composerMatch = preset.composer?.toLowerCase().includes(query) || false;
      if (!nameMatch && !gameMatch && !composerMatch) {
        return false;
      }
    }
    
    return true;
  });
}

export function usePresetData(): UsePresetDataReturn {
  const [dataset, setDataset] = useState<PresetDataset | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<PresetFilters>(DEFAULT_FILTER_STATE);
  const [selectedPreset, setSelectedPreset] = useState<DatasetPreset | null>(null);
  
  // Load data on mount
  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        setError(null);
        
        const response = await fetch('/data/presets.json');
        if (!response.ok) {
          throw new Error(`Failed to load data: ${response.status}`);
        }
        
        const data: PresetDataset = await response.json();
        setDataset(data);
        
        console.log(`Loaded ${data.presets.length} presets`);
      } catch (err) {
        console.error('Error loading preset data:', err);
        setError(err instanceof Error ? err.message : 'Failed to load data');
      } finally {
        setLoading(false);
      }
    }
    
    loadData();
  }, []);
  
  // Apply filters
  const filteredPresets = useMemo(() => {
    if (!dataset) return [];
    return applyFilters(dataset.presets, filters);
  }, [dataset, filters]);
  
  // Find similar presets when selection changes
  const similarPresets = useMemo(() => {
    if (!selectedPreset || !dataset) return [];
    return findSimilarPresets(selectedPreset, dataset.presets, 10);
  }, [selectedPreset, dataset]);
  
  // Reset filters
  const resetFilters = useCallback(() => {
    setFilters(DEFAULT_FILTER_STATE);
  }, []);
  
  // Stats
  const stats = useMemo(() => {
    const total = dataset?.presets.length || 0;
    const filtered = filteredPresets.length;
    const percentage = total > 0 ? Math.round((filtered / total) * 100) : 0;
    return { total, filtered, percentage };
  }, [dataset, filteredPresets]);
  
  return {
    dataset,
    loading,
    error,
    filteredPresets,
    filters,
    setFilters,
    resetFilters,
    selectedPreset,
    setSelectedPreset,
    similarPresets,
    stats,
  };
}
