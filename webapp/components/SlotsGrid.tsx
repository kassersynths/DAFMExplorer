/**
 * Slots Grid Component - 6 clickable slot cards
 */

import React from 'react';
import type { YM2612Patch } from '../types';

interface SlotsGridProps {
  slots: YM2612Patch[];
  activeSlotIndex: number;
  onSlotClick: (slotIndex: number) => void;
  onSlotClear?: (slotIndex: number) => void;
}

export const SlotsGrid: React.FC<SlotsGridProps> = ({
  slots,
  activeSlotIndex,
  onSlotClick,
  onSlotClear,
}) => {
  return (
    <div className="grid grid-cols-3 gap-2">
      {slots.map((slot, index) => {
        const isActive = index === activeSlotIndex;
        const isEmpty = !slot || !slot.name || slot.name === 'INIT SINE';
        
        return (
          <div
            key={index}
            onClick={() => onSlotClick(index)}
            className={`relative p-3 rounded-lg border cursor-pointer transition-all ${
              isActive
                ? 'bg-kasser-violet/20 border-kasser-violet shadow-[0_0_15px_rgba(188,19,254,0.4)]'
                : 'bg-[#111] border-[#333] hover:border-[#444]'
            }`}
          >
            {/* Slot Number */}
            <div className="flex items-center justify-between mb-2">
              <span className={`text-[10px] font-bold uppercase tracking-wider ${
                isActive ? 'text-kasser-violet' : 'text-gray-500'
              }`}>
                Slot {index + 1}
              </span>
              {!isEmpty && onSlotClear && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onSlotClear(index);
                  }}
                  className="w-4 h-4 flex items-center justify-center text-gray-500 hover:text-white transition-colors"
                  title="Clear slot"
                >
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>

            {/* Content */}
            {isEmpty ? (
              <div className="text-center py-2">
                <p className="text-[9px] text-gray-600 uppercase tracking-wider">Empty</p>
                <p className="text-[8px] text-gray-700 mt-0.5">Select a preset</p>
              </div>
            ) : (
              <div>
                {/* Game */}
                <p className={`text-[9px] truncate mb-1 ${
                  isActive ? 'text-kasser-violet/90' : 'text-gray-500'
                }`}>
                  {slot.description || 'No game'}
                </p>
                {/* Name */}
                <p className={`text-[10px] font-bold truncate ${
                  isActive ? 'text-white' : 'text-gray-300'
                }`}>
                  {slot.name}
                </p>
              </div>
            )}

            {/* Active indicator */}
            {isActive && (
              <div className="absolute top-1 right-1 w-2 h-2 rounded-full bg-kasser-violet animate-pulse" />
            )}
          </div>
        );
      })}
    </div>
  );
};
