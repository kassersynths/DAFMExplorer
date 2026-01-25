/**
 * Accordion Component - Reusable collapsible panel matching FilterPanel style
 */

import React, { useState } from 'react';

interface AccordionProps {
  title: string;
  subtitle?: string;
  isOpen?: boolean;
  onToggle?: () => void;
  disabled?: boolean;
  children: React.ReactNode;
  className?: string;
}

export const Accordion: React.FC<AccordionProps> = ({
  title,
  subtitle,
  isOpen: controlledIsOpen,
  onToggle,
  disabled = false,
  children,
  className = '',
}) => {
  const [internalIsOpen, setInternalIsOpen] = useState(false);
  
  // Use controlled state if provided, otherwise use internal state
  const isOpen = controlledIsOpen !== undefined ? controlledIsOpen : internalIsOpen;
  const handleToggle = () => {
    if (disabled) return;
    if (onToggle) {
      onToggle();
    } else {
      setInternalIsOpen(!internalIsOpen);
    }
  };

  return (
    <div className={`bg-[#0a0a0a] border border-[#222] rounded-lg overflow-hidden ${className}`}>
      {/* Header */}
      <button
        onClick={handleToggle}
        disabled={disabled}
        className={`w-full px-4 py-3 border-b border-[#222] flex items-center justify-between transition-all ${
          disabled
            ? 'opacity-50 cursor-not-allowed'
            : 'hover:bg-[#111] cursor-pointer'
        } ${
          isOpen
            ? 'bg-[#111] border-b-kasser-violet/30'
            : ''
        }`}
      >
        <div className="flex items-center gap-2">
          <svg
            className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-90' : ''} ${
              disabled ? 'text-gray-600' : 'text-kasser-violet'
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          <div className="text-left">
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">{title}</h3>
            {subtitle && (
              <p className="text-[10px] text-gray-500 mt-0.5">{subtitle}</p>
            )}
          </div>
        </div>
        {!disabled && (
          <span className={`text-[10px] text-gray-500 transition-colors ${isOpen ? 'text-kasser-violet' : ''}`}>
            {isOpen ? 'Hide' : 'Show'}
          </span>
        )}
      </button>

      {/* Content */}
      {isOpen && !disabled && (
        <div className="p-4">
          {children}
        </div>
      )}
    </div>
  );
};
