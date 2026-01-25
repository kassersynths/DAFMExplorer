/**
 * Preset Info Component - Shows details of selected preset
 */

import React from 'react';
import type { DatasetPreset } from '../types/preset';
import { NATIONALITY_COLORS } from '../types/preset';
import { resolveClusterForPreset } from '../utils/clusterUtils';

interface PresetInfoProps {
  preset: DatasetPreset | null;
  onAddToSlot?: () => void;
}

// Nationality flag emojis
const NATIONALITY_FLAGS: Record<string, string> = {
  'Japan': '🇯🇵',
  'USA': '🇺🇸',
  'UK': '🇬🇧',
  'Unknown': '🌐',
};

export const PresetInfo: React.FC<PresetInfoProps> = ({
  preset,
  onAddToSlot,
}) => {
  // Return null if no preset - no placeholder, no rectangle, nothing
  if (!preset) {
    return null;
  }

  const clusterInfo = resolveClusterForPreset(preset);

  // Compact version: only essential fields, no scores, no button
  return (
    <div className="p-4 bg-[#0a0a0a] border border-[#222] rounded-lg h-full overflow-hidden">
      {/* Compact Info Grid */}
      <div className="grid grid-cols-2 gap-2">
        {/* Game */}
        <div className="bg-[#111] p-2 rounded border border-[#222]">
          <span className="text-[9px] text-white uppercase tracking-wider block font-bold">Game</span>
          <span className="text-xs text-white truncate block font-bold">
            {preset.game}
          </span>
        </div>

        {/* Name */}
        <div className="bg-[#111] p-2 rounded border border-[#222]">
          <span className="text-[9px] text-white uppercase tracking-wider block font-bold">Name</span>
          <span className="text-xs text-white truncate block font-bold">
            {preset.name}
          </span>
        </div>

        {/* Composer */}
        <div className="bg-[#111] p-2 rounded border border-[#222]">
          <span className="text-[9px] text-white uppercase tracking-wider block font-bold">Composer</span>
          <span className="text-xs text-white font-bold">
            {preset.composer || 'Unknown'}
          </span>
        </div>

        {/* Nationality */}
        <div className="bg-[#111] p-2 rounded border border-[#222]">
          <span className="text-[9px] text-white uppercase tracking-wider block font-bold">Nationality</span>
          <span className="text-xs text-white flex items-center gap-1 font-bold">
            <span>{NATIONALITY_FLAGS[preset.nationality] || '🌐'}</span>
            {preset.nationality}
          </span>
        </div>

        {/* Cluster - with official name and color */}
        <div className="bg-[#111] p-2 rounded border border-[#222]">
          <span className="text-[9px] text-white uppercase tracking-wider block font-bold">Cluster</span>
          <span className="text-xs flex items-center gap-1 font-bold" style={{ color: clusterInfo.color }}>
            <span
              className="w-2 h-2 rounded-full flex-shrink-0"
              style={{ backgroundColor: clusterInfo.color }}
            />
            <span className="truncate">{clusterInfo.name}</span>
          </span>
        </div>

        {/* GEMS */}
        <div className="bg-[#111] p-2 rounded border border-[#222]">
          <span className="text-[9px] text-white uppercase tracking-wider block font-bold">GEMS</span>
          <span className={`text-xs font-bold ${preset.gems ? 'text-kasser-blue' : 'text-white/70'}`}>
            {preset.gems ? 'Yes' : 'No'}
          </span>
        </div>
      </div>
    </div>
  );
};
