/**
 * Info Easter Egg Component - Subtle button that opens project info
 */

import React, { useState, useRef, useEffect } from 'react';

export const InfoEasterEgg: React.FC = () => {
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

  return (
    <div ref={panelRef} className="relative">
      {/* Subtle Easter Egg Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-6 h-6 sm:w-7 sm:h-7 flex items-center justify-center text-white/30 hover:text-kasser-blue transition-colors group"
        title="About DAFMExplorer"
        aria-label="Project information"
      >
        <svg 
          className="w-4 h-4 sm:w-5 sm:h-5 group-hover:scale-110 transition-transform" 
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24"
        >
          <path 
            strokeLinecap="round" 
            strokeLinejoin="round" 
            strokeWidth={2} 
            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" 
          />
        </svg>
      </button>

      {/* Info Panel */}
      {isOpen && (
        <div className="absolute top-full right-0 mt-2 w-[90vw] sm:w-[500px] md:w-[600px] max-w-[600px] bg-black/95 backdrop-blur-xl border border-[#333] rounded-lg shadow-2xl overflow-hidden z-50">
          {/* Header */}
          <div className="p-4 border-b border-[#222] bg-gradient-to-r from-kasser-violet/20 to-kasser-blue/20">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-display font-bold text-white uppercase tracking-wider">
                  DAFMExplorer
                </h3>
                <p className="text-xs text-kasser-blue mt-0.5">by KASSER SYNTHS</p>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="text-white/50 hover:text-white transition-colors"
                aria-label="Close"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          {/* Content */}
          <div className="p-4 max-h-[70vh] overflow-y-auto scrollbar-thin scrollbar-thumb-gray-800 scrollbar-track-transparent space-y-4">
            {/* What is DAFMExplorer */}
            <div>
              <h4 className="text-sm font-bold text-kasser-violet uppercase tracking-wider mb-2">
                What is DAFMExplorer?
              </h4>
              <p className="text-xs text-white leading-relaxed">
                <strong className="text-kasser-blue">DAFMExplorer</strong> is an open-source educational project that combines <strong className="text-white">Data Science</strong> and <strong className="text-white">FM Synthesis</strong> to explore the sonic legacy of the Sega Genesis/Mega Drive era.
              </p>
            </div>

            {/* Key Features */}
            <div>
              <h4 className="text-sm font-bold text-kasser-violet uppercase tracking-wider mb-2">
                What You'll Learn
              </h4>
              <ul className="text-xs text-white space-y-1.5">
                <li className="flex items-start gap-2">
                  <span className="text-kasser-blue mt-0.5">🎵</span>
                  <span><strong className="text-kasser-blue">FM Synthesis fundamentals</strong> - How the YM2612 chip created iconic sounds</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-kasser-blue mt-0.5">📊</span>
                  <span><strong className="text-kasser-blue">Data Science techniques</strong> - PCA, clustering, embeddings, and recommendation systems</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-kasser-blue mt-0.5">🎮</span>
                  <span><strong className="text-kasser-blue">Gaming history</strong> - Composers, tools (GEMS), and regional differences</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-kasser-blue mt-0.5">🔍</span>
                  <span><strong className="text-kasser-blue">Preset exploration</strong> - Find similar sounds and discover patterns</span>
                </li>
              </ul>
            </div>

            {/* Dataset Info */}
            <div>
              <h4 className="text-sm font-bold text-kasser-violet uppercase tracking-wider mb-2">
                The Dataset
              </h4>
              <p className="text-xs text-white leading-relaxed mb-2">
                The preset data comes from the <strong className="text-kasser-blue">DrWashington collection</strong>, a complete archive of Project2612 data containing OPM files extracted from VGM recordings of Sega Genesis games.
              </p>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="bg-[#111] p-2 rounded border border-[#222]">
                  <span className="text-kasser-blue font-bold">~93,000</span>
                  <span className="text-white/70 block text-[10px]">Total Presets</span>
                </div>
                <div className="bg-[#111] p-2 rounded border border-[#222]">
                  <span className="text-kasser-blue font-bold">~700</span>
                  <span className="text-white/70 block text-[10px]">Unique Games</span>
                </div>
                <div className="bg-[#111] p-2 rounded border border-[#222]">
                  <span className="text-kasser-blue font-bold">58</span>
                  <span className="text-white/70 block text-[10px]">Parameters per Preset</span>
                </div>
                <div className="bg-[#111] p-2 rounded border border-[#222]">
                  <span className="text-kasser-blue font-bold">~200</span>
                  <span className="text-white/70 block text-[10px]">GEMS Games</span>
                </div>
              </div>
            </div>

            {/* Acknowledgments */}
            <div>
              <h4 className="text-sm font-bold text-kasser-violet uppercase tracking-wider mb-2">
                Acknowledgments
              </h4>
              <p className="text-xs text-white/80 leading-relaxed">
                <strong className="text-white">DrWashington</strong> - For the comprehensive OPM preset collection<br/>
                <strong className="text-white">Project2612</strong> - For preserving VGM files<br/>
                <strong className="text-white">VGMrips</strong> - For game-composer mappings<br/>
                <strong className="text-white">Sega Retro</strong> - For GEMS documentation<br/>
                <strong className="text-white">The chiptune community</strong> - For keeping retro sound alive
              </p>
            </div>

            {/* Footer */}
            <div className="pt-2 border-t border-[#222] text-center">
              <p className="text-[10px] text-white/60">
                Made with ❤️ for the retro gaming and chiptune community
              </p>
              <p className="text-xs text-kasser-violet font-bold mt-1">
                KASSER SYNTHS
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
