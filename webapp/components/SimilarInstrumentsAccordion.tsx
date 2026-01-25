/**
 * Similar Instruments Accordion - Similar to FilterPanel style
 */

import React, { useState, useRef, useEffect } from 'react';
import type { DatasetPreset } from '../types/preset';
import { resolveClusterForPreset } from '../utils/clusterUtils';

interface SimilarInstrumentsAccordionProps {
  presets: DatasetPreset[];
  onPresetClick?: (preset: DatasetPreset) => void;
  disabled?: boolean;
}

export const SimilarInstrumentsAccordion: React.FC<SimilarInstrumentsAccordionProps> = ({
  presets,
  onPresetClick,
  disabled = false,
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

  const hasContent = presets.length > 0 && !disabled;
  const displayPresets = presets.slice(0, 5); // Top 5

  return (
    <div ref={panelRef} className="absolute top-3 left-[360px] sm:left-[400px] z-30">
      {/* Toggle Button */}
      <button
        onClick={() => hasContent && setIsOpen(!isOpen)}
        disabled={!hasContent}
        className={`px-4 py-2 rounded-lg border backdrop-blur-sm transition-all flex items-center gap-2 ${
          !hasContent
            ? 'opacity-50 cursor-not-allowed bg-black/30 border-[#222] text-gray-600'
            : isOpen
              ? 'bg-kasser-violet border-kasser-violet text-white shadow-[0_0_15px_rgba(188,19,254,0.4)]'
              : 'bg-black/70 border-[#333] text-gray-300 hover:border-kasser-violet hover:text-white'
        }`}
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
        </svg>
        <span className="text-xs font-bold uppercase tracking-wider">Similar</span>
        {hasContent && (
          <span className="w-2 h-2 rounded-full bg-kasser-violet animate-pulse" />
        )}
      </button>

      {/* Similar Instruments Panel */}
      {isOpen && hasContent && (
        <div className="absolute top-full left-0 mt-2 w-80 bg-black/95 backdrop-blur-xl border border-[#333] rounded-lg shadow-2xl overflow-hidden">
          {/* Header */}
          <div className="p-3 border-b border-[#222]">
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">Similar Instruments</h3>
            <p className="text-[10px] text-gray-500 mt-0.5">
              Top {displayPresets.length} most similar
            </p>
          </div>

          {/* List */}
          <div className="max-h-[60vh] overflow-y-auto scrollbar-thin scrollbar-thumb-gray-800 scrollbar-track-transparent">
            {displayPresets.map((preset, index) => (
              <button
                key={preset.id}
                onClick={() => onPresetClick?.(preset)}
                className="w-full p-3 text-left border-b border-[#111] hover:bg-[#111] transition-colors group"
              >
                <div className="flex items-start gap-2">
                  {/* Rank */}
                  <span className="text-[10px] text-white font-mono w-4 font-bold">
                    {index + 1}.
                  </span>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    {(() => {
                      const clusterInfo = resolveClusterForPreset(preset);
                      return (
                        <>
                          <div className="flex items-center gap-2">
                            <span
                              className="w-2 h-2 rounded-full flex-shrink-0"
                              style={{ backgroundColor: clusterInfo.color }}
                            />
                            <span 
                              className="text-xs truncate transition-colors font-bold"
                              style={{ color: clusterInfo.color }}
                            >
                              {preset.name}
                            </span>
                          </div>
                          <p className="text-[10px] text-kasser-blue truncate mt-0.5">
                            {preset.game}
                          </p>
                          <p 
                            className="text-[9px] truncate mt-0.5 font-semibold"
                            style={{ color: clusterInfo.color }}
                          >
                            {clusterInfo.name}
                          </p>
                        </>
                      );
                    })()}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
