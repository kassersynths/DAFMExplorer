/**
 * Filter Panel Component - Overlay filters on map (left side)
 */

import React, { useState, useRef, useEffect } from 'react';
import type { PresetFilters, ClusterStats, ComposerStats, GameStats } from '../types/preset';
import { CLUSTER_COLORS, CLUSTER_NAMES } from '../types/preset';
import { getClusterColor, getClusterName } from '../utils/clusterUtils';

interface FilterPanelProps {
  filters: PresetFilters;
  onFiltersChange: (filters: PresetFilters) => void;
  clusters: ClusterStats[];
  composers: ComposerStats[];
  games: GameStats[];
  nationalities: string[];
  stats: { total: number; filtered: number; percentage: number };
  onReset: () => void;
}

export const FilterPanel: React.FC<FilterPanelProps> = ({
  filters,
  onFiltersChange,
  clusters,
  composers,
  games,
  nationalities,
  stats,
  onReset,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  // Close panel when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  const updateFilter = <K extends keyof PresetFilters>(key: K, value: PresetFilters[K]) => {
    onFiltersChange({ ...filters, [key]: value });
  };

  const hasActiveFilters = 
    filters.clusters.length > 0 || 
    filters.nationality !== null || 
    filters.composer !== null || 
    filters.game !== null ||
    filters.gems !== null;

  return (
    <div ref={panelRef} className="absolute top-3 left-3 z-30">
      {/* Toggle Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`px-4 py-2 rounded-lg border backdrop-blur-sm transition-all flex items-center gap-2 ${
          isOpen
            ? 'bg-kasser-violet border-kasser-violet text-white shadow-[0_0_15px_rgba(188,19,254,0.4)]'
            : hasActiveFilters
              ? 'bg-kasser-violet/20 border-kasser-violet text-kasser-violet hover:bg-kasser-violet/30'
              : 'bg-black/70 border-[#333] text-gray-300 hover:border-kasser-violet hover:text-white'
        }`}
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
        </svg>
        <span className="text-xs font-bold uppercase tracking-wider">Filters</span>
        {hasActiveFilters && (
          <span className="w-2 h-2 rounded-full bg-kasser-violet animate-pulse" />
        )}
      </button>

      {/* Filter Panel */}
      {isOpen && (
        <div className="absolute top-full left-0 mt-2 w-72 bg-black/95 backdrop-blur-xl border border-[#333] rounded-lg shadow-2xl overflow-hidden">
          {/* Header */}
          <div className="p-3 border-b border-[#222] flex items-center justify-between">
            <div>
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">Filter Presets</h3>
              <p className="text-[10px] text-gray-500 mt-0.5">
                Showing <span className="text-kasser-violet font-bold">{stats.filtered.toLocaleString()}</span> of {stats.total.toLocaleString()}
              </p>
            </div>
            <button
              onClick={() => {
                onReset();
              }}
              className="text-[10px] text-gray-500 hover:text-kasser-violet transition-colors uppercase tracking-wider"
            >
              Reset
            </button>
          </div>

          {/* Filter Controls - Order: Cluster, Game, Composer, Nationality, GEMS */}
          <div className="p-3 flex flex-col gap-4 max-h-[60vh] overflow-y-auto scrollbar-thin scrollbar-thumb-gray-800 scrollbar-track-transparent">
            {/* 1. Cluster Filter */}
            <div>
              <label className="text-[9px] text-gray-500 uppercase tracking-wider mb-2 block">Cluster</label>
              <select
                value={filters.clusters.length === 1 ? filters.clusters[0] : ''}
                onChange={e => {
                  const val = e.target.value;
                  if (val === '') {
                    updateFilter('clusters', []);
                  } else {
                    updateFilter('clusters', [parseInt(val)]);
                  }
                }}
                className="w-full px-3 py-2 bg-[#111] border border-[#333] rounded text-xs text-white focus:border-kasser-violet focus:outline-none appearance-none cursor-pointer"
              >
                <option value="">All Clusters</option>
                {clusters.map(cluster => {
                  const clusterName = getClusterName(cluster.id);
                  const clusterColor = getClusterColor(cluster.id);
                  return (
                    <option key={cluster.id} value={cluster.id} style={{ color: clusterColor }}>
                      {clusterName} ({cluster.presetCount})
                    </option>
                  );
                })}
              </select>
              
              {/* Visual cluster chips */}
              <div className="flex flex-wrap gap-1 mt-2">
                {clusters.map(cluster => {
                  const clusterName = getClusterName(cluster.id);
                  const clusterColor = getClusterColor(cluster.id);
                  const isSelected = filters.clusters.length === 0 || filters.clusters.includes(cluster.id);
                  return (
                    <button
                      key={cluster.id}
                      onClick={() => {
                        if (filters.clusters.includes(cluster.id)) {
                          updateFilter('clusters', filters.clusters.filter(c => c !== cluster.id));
                        } else {
                          updateFilter('clusters', [...filters.clusters, cluster.id]);
                        }
                      }}
                      className={`px-2 py-1 text-[9px] rounded border transition-all flex items-center gap-1 ${
                        isSelected
                          ? 'opacity-100'
                          : 'opacity-50'
                      }`}
                      style={{
                        backgroundColor: isSelected && filters.clusters.includes(cluster.id)
                          ? clusterColor + '44'
                          : 'transparent',
                        borderColor: isSelected ? clusterColor + '88' : '#222',
                        color: isSelected ? clusterColor : '#666'
                      }}
                      title={clusterName}
                    >
                      <span
                        className="w-2 h-2 rounded-full flex-shrink-0"
                        style={{ backgroundColor: clusterColor }}
                      />
                      <span className="truncate max-w-[100px] font-semibold" style={{ color: clusterColor }}>{clusterName}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* 2. Game Filter (with search) */}
            <div>
              <label className="text-[9px] text-gray-500 uppercase tracking-wider mb-2 block">Game</label>
              <GameSearchSelect
                games={games}
                value={filters.game}
                onChange={val => updateFilter('game', val)}
              />
            </div>

            {/* 3. Composer Filter (with search) */}
            <div>
              <label className="text-[9px] text-gray-500 uppercase tracking-wider mb-2 block">Composer</label>
              <ComposerSearchSelect
                composers={composers}
                value={filters.composer}
                onChange={val => updateFilter('composer', val)}
              />
            </div>

            {/* 4. Nationality Filter */}
            <div>
              <label className="text-[9px] text-gray-500 uppercase tracking-wider mb-2 block">Nationality</label>
              <select
                value={filters.nationality || ''}
                onChange={e => updateFilter('nationality', e.target.value || null)}
                className="w-full px-3 py-2 bg-[#111] border border-[#333] rounded text-xs text-white focus:border-kasser-violet focus:outline-none appearance-none cursor-pointer"
              >
                <option value="">All Nationalities</option>
                {nationalities.map(nat => (
                  <option key={nat} value={nat}>{nat}</option>
                ))}
              </select>
            </div>

            {/* 5. GEMS Filter */}
            <div>
              <label className="text-[9px] text-gray-500 uppercase tracking-wider mb-2 block">GEMS</label>
              <select
                value={filters.gems === null ? '' : filters.gems ? 'yes' : 'no'}
                onChange={e => {
                  const val = e.target.value;
                  updateFilter('gems', val === '' ? null : val === 'yes');
                }}
                className="w-full px-3 py-2 bg-[#111] border border-[#333] rounded text-xs text-white focus:border-kasser-violet focus:outline-none appearance-none cursor-pointer"
              >
                <option value="">All Presets</option>
                <option value="yes">Yes (GEMS)</option>
                <option value="no">No (Custom)</option>
              </select>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// Game Search Select Component
const GameSearchSelect: React.FC<{
  games: GameStats[];
  value: string | null;
  onChange: (value: string | null) => void;
}> = ({ games, value, onChange }) => {
  const [search, setSearch] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const filteredGames = games.filter(g => 
    g.name.toLowerCase().includes(search.toLowerCase())
  ).slice(0, 50);

  const selectedGame = games.find(g => g.name === value);

  return (
    <div className="relative">
      <div
        className="w-full px-3 py-2 bg-[#111] border border-[#333] rounded text-xs text-white focus-within:border-kasser-violet cursor-text flex items-center gap-2"
        onClick={() => {
          setIsOpen(true);
          setTimeout(() => inputRef.current?.focus(), 0);
        }}
      >
        {value && !isOpen ? (
          <span className="flex-1 truncate">{value}</span>
        ) : (
          <input
            ref={inputRef}
            type="text"
            placeholder="Search games..."
            value={search}
            onChange={e => {
              setSearch(e.target.value);
              setIsOpen(true);
            }}
            onFocus={() => setIsOpen(true)}
            className="flex-1 bg-transparent outline-none placeholder-gray-500"
          />
        )}
        {value && (
          <button
            onClick={e => {
              e.stopPropagation();
              onChange(null);
              setSearch('');
            }}
            className="text-gray-500 hover:text-white"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-[#0a0a0a] border border-[#333] rounded max-h-48 overflow-y-auto z-50 shadow-xl">
          {filteredGames.length === 0 ? (
            <div className="px-3 py-2 text-[10px] text-gray-500">No games found</div>
          ) : (
            filteredGames.map(game => (
              <button
                key={game.name}
                onClick={() => {
                  onChange(game.name);
                  setSearch('');
                  setIsOpen(false);
                }}
                className="w-full px-3 py-2 text-left text-xs text-gray-300 hover:bg-[#1a1a1a] hover:text-white transition-colors flex justify-between items-center"
              >
                <span className="truncate">{game.name}</span>
                <span className="text-[9px] text-gray-600 ml-2">{game.presetCount}</span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
};

// Composer Search Select Component
const ComposerSearchSelect: React.FC<{
  composers: ComposerStats[];
  value: string | null;
  onChange: (value: string | null) => void;
}> = ({ composers, value, onChange }) => {
  const [search, setSearch] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const filteredComposers = composers.filter(c => 
    c.name.toLowerCase().includes(search.toLowerCase())
  ).slice(0, 50);

  return (
    <div className="relative">
      <div
        className="w-full px-3 py-2 bg-[#111] border border-[#333] rounded text-xs text-white focus-within:border-kasser-violet cursor-text flex items-center gap-2"
        onClick={() => {
          setIsOpen(true);
          setTimeout(() => inputRef.current?.focus(), 0);
        }}
      >
        {value && !isOpen ? (
          <span className="flex-1 truncate">{value}</span>
        ) : (
          <input
            ref={inputRef}
            type="text"
            placeholder="Search composers..."
            value={search}
            onChange={e => {
              setSearch(e.target.value);
              setIsOpen(true);
            }}
            onFocus={() => setIsOpen(true)}
            className="flex-1 bg-transparent outline-none placeholder-gray-500"
          />
        )}
        {value && (
          <button
            onClick={e => {
              e.stopPropagation();
              onChange(null);
              setSearch('');
            }}
            className="text-gray-500 hover:text-white"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-[#0a0a0a] border border-[#333] rounded max-h-48 overflow-y-auto z-50 shadow-xl">
          {filteredComposers.length === 0 ? (
            <div className="px-3 py-2 text-[10px] text-gray-500">No composers found</div>
          ) : (
            filteredComposers.map(composer => (
              <button
                key={composer.name}
                onClick={() => {
                  onChange(composer.name);
                  setSearch('');
                  setIsOpen(false);
                }}
                className="w-full px-3 py-2 text-left text-xs text-gray-300 hover:bg-[#1a1a1a] hover:text-white transition-colors flex justify-between items-center"
              >
                <div className="flex-1 min-w-0">
                  <span className="truncate block">{composer.name}</span>
                  <span className="text-[9px] text-gray-600">{composer.nationality}</span>
                </div>
                <span className="text-[9px] text-gray-600 ml-2">{composer.presetCount}</span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
};
