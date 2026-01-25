/**
 * Preset Parameters Accordion - Similar to FilterPanel style
 */

import React, { useState, useRef, useEffect } from 'react';
import { PatchDataTable } from './PatchDataTable';
import type { YM2612Patch } from '../types';

interface PresetParamsAccordionProps {
  patch: YM2612Patch | null;
  disabled?: boolean;
}

export const PresetParamsAccordion: React.FC<PresetParamsAccordionProps> = ({
  patch,
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

  const hasContent = patch !== null && !disabled;

  return (
    <div ref={panelRef} className="absolute top-3 left-[180px] sm:left-[200px] z-30">
      {/* Toggle Button */}
      <button
        onClick={() => hasContent && setIsOpen(!isOpen)}
        disabled={!hasContent}
        className={`px-4 py-2 rounded-lg border backdrop-blur-sm transition-all flex items-center gap-2 ${
          !hasContent
            ? 'opacity-50 cursor-not-allowed bg-black/30 border-[#222] text-gray-600'
            : isOpen
              ? 'bg-kasser-blue border-kasser-blue text-white shadow-[0_0_15px_rgba(0,234,255,0.4)]'
              : 'bg-black/70 border-[#333] text-gray-300 hover:border-kasser-blue hover:text-white'
        }`}
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
        </svg>
        <span className="text-xs font-bold uppercase tracking-wider">Parameters</span>
      </button>

      {/* Parameters Panel */}
      {isOpen && hasContent && patch && (
        <div className="absolute top-full left-0 mt-2 w-[90vw] sm:w-[500px] md:w-[600px] max-w-[600px] bg-black/95 backdrop-blur-xl border border-[#333] rounded-lg shadow-2xl overflow-hidden">
          {/* Header */}
          <div className="p-3 border-b border-[#222] flex items-center justify-between">
            <div>
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">FM Parameters</h3>
              <p className="text-[10px] text-gray-500 mt-0.5">
                Patch: <span className="text-kasser-blue font-bold">{patch.name}</span>
              </p>
            </div>
          </div>

          {/* Content */}
          <div className="p-3 max-h-[70vh] overflow-y-auto scrollbar-thin scrollbar-thumb-gray-800 scrollbar-track-transparent">
            <PatchDataTable patch={patch} />
          </div>
        </div>
      )}
    </div>
  );
};
