/**
 * Synth Panel Component - Right side panel with octave selector and hex keys
 * Responsive, numpad support, visual octave scale
 * Piano with correct layout: white keys linear, black keys positioned above
 */

import React, { useState, useRef, useEffect } from 'react';

import type { DatasetPreset } from '../types/preset';
import { resolveClusterForPreset } from '../utils/clusterUtils';
import { BLACK_KEY_Y_OFFSET_FRAC, BLACK_KEY_X_SPACING_FRAC } from '../utils/pianoLayout';

interface SynthPanelProps {
  activeSlot: number; // For display only
  onSlotChange: (slot: number) => void; // Kept for compatibility but not used in UI
  onNoteOn: (note: number) => void;
  onNoteOff: (note: number) => void;
  activePreset: DatasetPreset | null; // Preset in the active slot
}

// Hexagonal Key Component with blue electric border
// All keys (white and black) use the same size
const HexKey: React.FC<{
  label: string;
  type: 'white' | 'black';
  active: boolean;
  onDown: () => void;
  onUp: () => void;
  className?: string;
  style?: React.CSSProperties;
}> = ({ label, type, active, onDown, onUp, className = '', style = {} }) => {
  const isWhite = type === 'white';
  
  const colors = {
    top: active ? '#bc13fe' : (isWhite ? '#e5e5e5' : '#1a1a1a'),
    left: active ? '#8a0eb8' : (isWhite ? '#b0b0b0' : '#0d0d0d'),
    right: active ? '#630a85' : (isWhite ? '#999999' : '#000000'),
  };

  // Use provided style if it has width/height, otherwise use default clamp sizes
  // All keys use the same size now
  const hasCustomSize = style.width || style.height;
  const defaultSize = { 
    width: 'clamp(36px, 5vw, 48px)', 
    height: 'clamp(56px, 7vw, 72px)' 
  };
  
  const finalStyle = hasCustomSize 
    ? { width: '100%', height: '100%', ...style }
    : { ...defaultSize, ...style };

  return (
    <div 
      className={`relative cursor-pointer select-none transition-transform active:scale-95 ${className}`}
      style={{ ...finalStyle, overflow: 'visible' }}
      onMouseDown={onDown}
      onMouseUp={onUp}
      onMouseLeave={onUp}
      onTouchStart={(e) => { e.preventDefault(); onDown(); }}
      onTouchEnd={(e) => { e.preventDefault(); onUp(); }}
    >
      {/* Hexagon shape with complete blue border */}
      <div 
        className="w-full h-full absolute inset-0"
        style={{ 
          clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)',
          filter: active
            ? 'drop-shadow(0 0 2px #00eaff) drop-shadow(0 0 4px rgba(0, 234, 255, 0.6)) drop-shadow(0 0 8px rgba(0, 234, 255, 0.4))'
            : 'drop-shadow(0 0 1px #00eaff) drop-shadow(0 0 2px rgba(0, 234, 255, 0.5))',
          overflow: 'visible',
        }}
      >
        {/* Border outline using SVG - complete blue border around hexagon */}
        <svg 
          className="absolute inset-0 w-full h-full pointer-events-none"
          style={{ zIndex: 25, overflow: 'visible' }}
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
        >
          <polygon
            points="50,0 100,25 100,75 50,100 0,75 0,25"
            fill="none"
            stroke="#00eaff"
            strokeWidth="0.5"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
        
        {/* Top Face */}
        <div 
          className="absolute top-0 left-0 w-full h-1/2 z-20 transition-colors duration-75"
          style={{ backgroundColor: colors.top, clipPath: 'polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)' }}
        />
        
        {/* Left Face */}
        <div 
          className="absolute bottom-0 left-0 w-1/2 h-3/4 z-10 transition-colors duration-75"
          style={{ backgroundColor: colors.left, clipPath: 'polygon(0% 0%, 100% 33%, 100% 100%, 50% 100%, 0% 66%)' }} 
        />

        {/* Right Face */}
        <div 
          className="absolute bottom-0 right-0 w-1/2 h-3/4 z-10 transition-colors duration-75"
          style={{ backgroundColor: colors.right, clipPath: 'polygon(100% 0%, 100% 66%, 50% 100%, 0% 100%, 0% 33%)' }}
        />
      </div>
    </div>
  );
};

export const SynthPanel: React.FC<SynthPanelProps> = ({
  activeSlot,
  onSlotChange,
  onNoteOn,
  onNoteOff,
  activePreset,
}) => {
  const [octave, setOctave] = useState(3);
  const [activeNotes, setActiveNotes] = useState<Set<number>>(new Set());
  const keyToNoteRef = useRef<Record<string, number>>({});

  // Numpad mapping: C -> 0, C# -> ., D -> 1, D# -> 2, E -> 3, F -> 4, F# -> 5, G -> 6, G# -> 7, A -> 8, A# -> 9, B -> /, C(oct+1) -> *
  const NUMPAD_MAP: Record<string, number> = {
    'Numpad0': 0,      // C
    'NumpadDecimal': 1, // C#
    'Numpad1': 2,      // D
    'Numpad2': 3,      // D#
    'Numpad3': 4,      // E
    'Numpad4': 5,      // F
    'Numpad5': 6,      // F#
    'Numpad6': 7,      // G
    'Numpad7': 8,      // G#
    'Numpad8': 9,      // A
    'Numpad9': 10,     // A#
    'NumpadDivide': 11, // B
    'NumpadMultiply': 12, // C (next octave)
  };

  // Keyboard mapping - ONLY numpad, no letter keys
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.repeat || e.ctrlKey || e.metaKey || e.altKey) return;
      
      // Handle numpad octave change
      if (e.code === 'NumpadAdd' || e.code === 'NumpadSubtract') {
        e.preventDefault();
        setOctave(prev => {
          if (e.code === 'NumpadAdd') {
            return Math.min(7, prev + 1);
          } else {
            return Math.max(0, prev - 1);
          }
        });
        return;
      }

      // Handle numpad notes ONLY
      const numpadInterval = NUMPAD_MAP[e.code];
      if (numpadInterval !== undefined) {
        e.preventDefault();
        if (keyToNoteRef.current[e.code] !== undefined) return;

        const midiNote = (octave + 1) * 12 + numpadInterval;
        keyToNoteRef.current[e.code] = midiNote;
        
        onNoteOn(midiNote);
        
        setActiveNotes(prev => {
          const newSet = new Set(prev);
          newSet.add(midiNote);
          return newSet;
        });
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      // Handle numpad ONLY
      const numpadInterval = NUMPAD_MAP[e.code];
      if (numpadInterval !== undefined) {
        const midiNote = keyToNoteRef.current[e.code];
        if (midiNote !== undefined) {
          onNoteOff(midiNote);
          setActiveNotes(prev => {
            const newSet = new Set(prev);
            newSet.delete(midiNote);
            return newSet;
          });
          delete keyToNoteRef.current[e.code];
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [octave, onNoteOn, onNoteOff]);

  const playNote = (interval: number) => {
    const midiNote = (octave + 1) * 12 + interval;
    setActiveNotes(prev => new Set(prev).add(midiNote));
    onNoteOn(midiNote);
  };

  const stopNote = (interval: number) => {
    const midiNote = (octave + 1) * 12 + interval;
    setActiveNotes(prev => {
      const next = new Set(prev);
      next.delete(midiNote);
      return next;
    });
    onNoteOff(midiNote);
  };

  const handleOctaveChange = (newOctave: number) => {
    const clamped = Math.max(0, Math.min(7, newOctave));
    setOctave(clamped);
  };

  // Piano keys configuration - 13 notes: C, C#, D, D#, E, F, F#, G, G#, A, A#, B, C(oct+1)
  // White keys: C, D, E, F, G, A, B, C (8 keys)
  const whiteKeys = [
    { label: 'C', interval: 0 },
    { label: 'D', interval: 2 },
    { label: 'E', interval: 4 },
    { label: 'F', interval: 5 },
    { label: 'G', interval: 7 },
    { label: 'A', interval: 9 },
    { label: 'B', interval: 11 },
    { label: 'C', interval: 12 }, // Next octave
  ];

  // Black keys positioned between white keys
  // gapIndex: which gap between white keys (0=between C-D, 1=between D-E, 3=between F-G, 4=between G-A, 5=between A-B)
  const blackKeys = [
    { label: 'C#', interval: 1, gapIndex: 0 },   // Between C(0) and D(1)
    { label: 'D#', interval: 3, gapIndex: 1 },   // Between D(1) and E(2)
    { label: 'F#', interval: 6, gapIndex: 3 },   // Between F(3) and G(4)
    { label: 'G#', interval: 8, gapIndex: 4 },   // Between G(4) and A(5)
    { label: 'A#', interval: 10, gapIndex: 5 },   // Between A(5) and B(6)
  ];

  const whiteCount = 8;
  const blackCount = 5;
  
  // Key dimensions - responsive and proportional
  const keyHeight = 'clamp(56px, 7vw, 72px)';
  const whiteWidthPercent = 100 / whiteCount; // 12.5% per white key
  
  // Y offset: use CSS calc to apply BLACK_KEY_Y_OFFSET_FRAC as fraction of key height
  // This ensures the offset is proportional to the actual key height (which uses clamp)
  // Negative value moves keys up
  // Format: calc(-1 * clamp(...) * 0.18) = calc(clamp(...) * -0.18)
  const yOffsetCalc = `calc(${keyHeight} * -${BLACK_KEY_Y_OFFSET_FRAC})`;
  
  // White keys offset: push white keys down significantly
  // Using margin-top instead of transform for better compatibility
  // Increased values to lower white keys more
  const whiteKeysOffset = 'clamp(32px, 6vh, 48px)';

  return (
    <div className="flex flex-col h-full overflow-hidden" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Piano Keys - Takes remaining space (flex: 1) */}
      <div className="flex-1 min-h-0 flex items-center justify-center py-2 sm:py-4 bg-[#080808]/50 rounded border border-[#222]/50" style={{ overflow: 'visible', paddingTop: 'clamp(12px, 2vh, 20px)', paddingBottom: 'clamp(8px, 1vh, 12px)' }}>
        <div className="relative w-full" style={{ maxWidth: '100%', overflow: 'visible', height: '100%' }}>
          {/* White Keys Row - Base layer - Each key is exactly 1/8 of width */}
          {/* White keys are pushed down significantly using margin-top */}
          <div className="relative flex w-full" style={{ gap: 0, overflow: 'visible', marginTop: whiteKeysOffset }}>
            {whiteKeys.map((key, index) => {
              const midi = (octave + 1) * 12 + key.interval;
              const isActive = activeNotes.has(midi);
              const isLast = index === whiteKeys.length - 1;
              const hideClass = isLast ? "hidden sm:block" : "block";
              
              return (
                <div 
                  key={`white-${index}`} 
                  className={`relative ${hideClass}`}
                  style={{ 
                    width: `${whiteWidthPercent}%`,
                    flexShrink: 0,
                    overflow: 'visible',
                  }}
                >
                  <div style={{ width: '100%', height: keyHeight, overflow: 'visible' }}>
                    <HexKey 
                      label={key.label} 
                      type="white" 
                      active={isActive}
                      onDown={() => playNote(key.interval)}
                      onUp={() => stopNote(key.interval)}
                      style={{ width: '100%', height: '100%' }}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          {/* Black Keys Row - Overlay layer - Proportional offsets */}
          <div className="absolute top-0 left-0 w-full h-full pointer-events-none" style={{ zIndex: 30, overflow: 'visible' }}>
            {blackKeys.map((blackKey, blackIndex) => {
              const blackMidi = (octave + 1) * 12 + blackKey.interval;
              const isBlackActive = activeNotes.has(blackMidi);
              
              // Calculate base position: center of the gap between white keys
              const gapCenterPercent = (blackKey.gapIndex + 1) * whiteWidthPercent;
              
              // Apply extra horizontal spacing: offset from center (proportional to white key width)
              const centerIndex = (blackCount - 1) / 2;
              const horizontalOffsetPercent = (blackIndex - centerIndex) * BLACK_KEY_X_SPACING_FRAC * whiteWidthPercent;
              
              // Calculate final left position with clamp to ensure it stays within 0-100%
              const baseLeft = gapCenterPercent - (whiteWidthPercent / 2) + horizontalOffsetPercent;
              const clampedLeft = Math.max(0, Math.min(100 - whiteWidthPercent, baseLeft));
              
              return (
                <div
                  key={`black-${blackKey.label}`}
                  className="absolute pointer-events-auto"
                  style={{
                    left: `${clampedLeft}%`,
                    top: 0,
                    width: `${whiteWidthPercent}%`,
                    height: keyHeight,
                    overflow: 'visible',
                    transform: `translateY(${yOffsetCalc})`,
                  }}
                >
                  <HexKey 
                    label={blackKey.label} 
                    type="black" 
                    active={isBlackActive}
                    onDown={() => playNote(blackKey.interval)}
                    onUp={() => stopNote(blackKey.interval)}
                    style={{ width: '100%', height: '100%' }}
                  />
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Octave Slider + Help Text - Fixed height container */}
      <div className="flex-shrink-0 flex flex-col gap-2 p-3 sm:p-4" style={{ flex: '0 0 auto' }}>
        {/* Octave Slider */}
        <div className="flex flex-col gap-1.5">
          {/* Label */}
          <div className="text-center">
            <span className="text-[10px] sm:text-[11px] text-white/80 font-bold uppercase tracking-wider">Octave</span>
          </div>
          
          <div className="flex items-center gap-2">
            {/* Decrease Button */}
            <button
              onClick={() => handleOctaveChange(octave - 1)}
              className="w-8 h-8 sm:w-10 sm:h-10 bg-[#111] border border-[#333] rounded text-white hover:border-kasser-blue hover:bg-kasser-blue/20 transition-colors flex items-center justify-center flex-shrink-0"
              aria-label="Decrease octave"
            >
              <svg className="w-4 h-4 sm:w-5 sm:h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
              </svg>
            </button>

            {/* Slider */}
            <div className="flex-1 relative">
              <input
                type="range"
                min="0"
                max="7"
                value={octave}
                onChange={(e) => handleOctaveChange(parseInt(e.target.value))}
                className="w-full h-2 bg-[#222] rounded-lg appearance-none cursor-pointer"
                style={{
                  background: `linear-gradient(to right, #00eaff 0%, #00eaff ${(octave / 7) * 100}%, #222 ${(octave / 7) * 100}%, #222 100%)`
                }}
              />
              <style>{`
                input[type="range"]::-webkit-slider-thumb {
                  appearance: none;
                  width: 16px;
                  height: 16px;
                  border-radius: 50%;
                  background: #00eaff;
                  border: 2px solid #00eaff;
                  box-shadow: 0 0 8px rgba(0, 234, 255, 0.8);
                  cursor: pointer;
                }
                input[type="range"]::-moz-range-thumb {
                  width: 16px;
                  height: 16px;
                  border-radius: 50%;
                  background: #00eaff;
                  border: 2px solid #00eaff;
                  box-shadow: 0 0 8px rgba(0, 234, 255, 0.8);
                  cursor: pointer;
                }
              `}</style>
              
              {/* Visual Scale with Numbers (0-7) */}
              <div className="absolute top-3 left-0 right-0 flex justify-between px-0.5">
                {[0, 1, 2, 3, 4, 5, 6, 7].map((oct) => (
                  <div
                    key={oct}
                    className="flex flex-col items-center gap-0.5"
                  >
                    <div
                      className={`w-1 h-1 sm:w-1.5 sm:h-1.5 rounded-full transition-all ${
                        oct === octave
                          ? 'bg-kasser-blue w-2 h-2 sm:w-2.5 sm:h-2.5 shadow-[0_0_8px_rgba(0,234,255,0.8)]'
                          : 'bg-[#444]'
                      }`}
                    />
                    <span className={`text-[8px] sm:text-[9px] font-bold transition-colors ${
                      oct === octave ? 'text-kasser-blue' : 'text-white/50'
                    }`}>
                      {oct}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Increase Button */}
            <button
              onClick={() => handleOctaveChange(octave + 1)}
              className="w-8 h-8 sm:w-10 sm:h-10 bg-[#111] border border-[#333] rounded text-white hover:border-kasser-blue hover:bg-kasser-blue/20 transition-colors flex items-center justify-center flex-shrink-0"
              aria-label="Increase octave"
            >
              <svg className="w-4 h-4 sm:w-5 sm:h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
            </button>
          </div>
        </div>
        
        {/* Help Text - Single line */}
        <div className="text-center">
          <p className="text-[9px] sm:text-[10px] text-white font-bold whitespace-nowrap sm:whitespace-normal">
            <span>Numpad: <span className="text-kasser-blue">0 . 1-9 / *</span> for notes</span>
            <span className="hidden sm:inline">   •   </span>
            <span className="block sm:inline">Octave: <span className="text-kasser-blue">+</span> / <span className="text-kasser-blue">-</span> (numpad)</span>
          </p>
        </div>
      </div>

      {/* Preset Info Panel - Fixed height at bottom, always visible (with placeholder when no preset) */}
      <div className="flex-shrink-0 bg-[#080808] border border-[#333] rounded p-2 sm:p-2.5 overflow-hidden" style={{ flex: '0 0 clamp(140px, 18vh, 180px)', height: 'clamp(140px, 18vh, 180px)' }}>
        {activePreset ? (() => {
          // Calculate cluster info once to ensure consistency with map/tooltip
          const clusterInfo = resolveClusterForPreset(activePreset);
          return (
            <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-[9px] sm:text-[10px]">
              <div className="min-w-0">
                <span className="text-white/60 font-bold uppercase tracking-wider text-[8px] sm:text-[9px]">Game</span>
                <p className="text-white font-semibold mt-0.5 truncate leading-tight">{activePreset.game}</p>
              </div>
              <div className="min-w-0">
                <span className="text-white/60 font-bold uppercase tracking-wider text-[8px] sm:text-[9px]">Name</span>
                <p className="text-white font-semibold mt-0.5 truncate leading-tight">{activePreset.name}</p>
              </div>
              <div className="min-w-0">
                <span className="text-white/60 font-bold uppercase tracking-wider text-[8px] sm:text-[9px]">Composer</span>
                <p className="text-white font-semibold mt-0.5 truncate leading-tight">{activePreset.composer || 'Unknown'}</p>
              </div>
              <div className="min-w-0">
                <span className="text-white/60 font-bold uppercase tracking-wider text-[8px] sm:text-[9px]">Nationality</span>
                <p className="text-white font-semibold mt-0.5 truncate leading-tight">{activePreset.nationality}</p>
              </div>
              <div className="min-w-0">
                <span className="text-white/60 font-bold uppercase tracking-wider text-[8px] sm:text-[9px]">Cluster</span>
                <p className="font-semibold mt-0.5 truncate leading-tight" style={{ color: clusterInfo.color }}>
                  {clusterInfo.name}
                </p>
              </div>
              <div className="min-w-0">
                <span className="text-white/60 font-bold uppercase tracking-wider text-[8px] sm:text-[9px]">GEMS</span>
                <p className={`font-semibold mt-0.5 truncate leading-tight ${activePreset.gems ? 'text-kasser-blue' : 'text-white/70'}`}>
                  {activePreset.gems ? 'Yes' : 'No'}
                </p>
              </div>
            </div>
          );
        })() : (
          <div className="h-full flex items-center justify-center">
            <p className="text-gray-500 text-xs text-center px-4 leading-relaxed">
              Click on a preset in the map<br />
              <span className="text-kasser-blue">to explore its sonic details</span>
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
