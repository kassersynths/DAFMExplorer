/**
 * Preset Map Component - 2D Embedding Visualization
 * Uses Canvas 2D for performance with ~22K points
 * No zoom - fixed view with active/inactive state visualization
 */

import React, { useRef, useEffect, useState, useCallback } from 'react';
import type { DatasetPreset, MapColorMode } from '../types/preset';
import { CLUSTER_COLORS, CLUSTER_NAMES, NATIONALITY_COLORS } from '../types/preset';
import { resolveClusterForPreset } from '../utils/clusterUtils';

interface PresetMapProps {
  allPresets: DatasetPreset[];         // All presets in the dataset
  filteredPresets: DatasetPreset[];    // Presets that match filters (active)
  selectedPreset: DatasetPreset | null;
  similarPresets: DatasetPreset[];
  onPresetClick: (preset: DatasetPreset) => void;
  onPresetHover: (preset: DatasetPreset | null) => void;
}

// Get color for preset - always based on cluster (using single source of truth)
function getPresetColor(preset: DatasetPreset): string {
  return resolveClusterForPreset(preset).color;
}

// Convert hex color to desaturated gray-tinted version
function desaturateColor(hexColor: string, amount: number = 0.8): string {
  // Parse hex
  const hex = hexColor.replace('#', '');
  const r = parseInt(hex.substring(0, 2), 16);
  const g = parseInt(hex.substring(2, 4), 16);
  const b = parseInt(hex.substring(4, 6), 16);
  
  // Convert to grayscale with slight hint of original color
  const gray = (r + g + b) / 3;
  const newR = Math.round(r * (1 - amount) + gray * amount * 0.3);
  const newG = Math.round(g * (1 - amount) + gray * amount * 0.3);
  const newB = Math.round(b * (1 - amount) + gray * amount * 0.3);
  
  return `rgb(${newR}, ${newG}, ${newB})`;
}

export const PresetMap: React.FC<PresetMapProps> = ({
  allPresets,
  filteredPresets,
  selectedPreset,
  similarPresets,
  onPresetClick,
  onPresetHover,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [hoveredPreset, setHoveredPreset] = useState<DatasetPreset | null>(null);
  const [canvasSize, setCanvasSize] = useState({ width: 800, height: 600 });

  // Create set of filtered preset IDs for quick lookup
  const filteredIds = React.useMemo(() => new Set(filteredPresets.map(p => p.id)), [filteredPresets]);

  // Calculate bounds of ALL data (not just filtered)
  const bounds = React.useMemo(() => {
    if (allPresets.length === 0) return { minX: 0, maxX: 1, minY: 0, maxY: 1 };
    
    let minX = Infinity, maxX = -Infinity;
    let minY = Infinity, maxY = -Infinity;
    
    for (const p of allPresets) {
      if (p.x < minX) minX = p.x;
      if (p.x > maxX) maxX = p.x;
      if (p.y < minY) minY = p.y;
      if (p.y > maxY) maxY = p.y;
    }
    
    // Add padding
    const padX = (maxX - minX) * 0.05;
    const padY = (maxY - minY) * 0.05;
    
    return {
      minX: minX - padX,
      maxX: maxX + padX,
      minY: minY - padY,
      maxY: maxY + padY,
    };
  }, [allPresets]);

  // Transform data coordinates to canvas coordinates (no zoom)
  const dataToCanvas = useCallback((x: number, y: number) => {
    const { minX, maxX, minY, maxY } = bounds;
    const dataWidth = maxX - minX;
    const dataHeight = maxY - minY;
    
    return {
      x: ((x - minX) / dataWidth) * canvasSize.width,
      y: ((y - minY) / dataHeight) * canvasSize.height,
    };
  }, [bounds, canvasSize]);

  // Find preset at canvas position (only active presets are clickable)
  const findPresetAtPosition = useCallback((canvasX: number, canvasY: number): DatasetPreset | null => {
    const threshold = 8;
    let closest: DatasetPreset | null = null;
    let closestDist = Infinity;
    
    // Only check filtered (active) presets for interaction
    for (const preset of filteredPresets) {
      const pos = dataToCanvas(preset.x, preset.y);
      const dist = Math.sqrt(Math.pow(pos.x - canvasX, 2) + Math.pow(pos.y - canvasY, 2));
      
      if (dist < threshold && dist < closestDist) {
        closest = preset;
        closestDist = dist;
      }
    }
    
    return closest;
  }, [filteredPresets, dataToCanvas]);

  // Handle resize
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    
    // Initial size with timeout to ensure container is rendered
    const updateSize = () => {
      const rect = container.getBoundingClientRect();
      const width = rect.width || 800;
      const height = rect.height || 600;
      if (width > 0 && height > 0) {
        setCanvasSize({ width, height });
      }
    };
    
    // Set initial size after a brief delay
    const timeoutId = setTimeout(updateSize, 100);
    updateSize(); // Also try immediately
    
    const resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          setCanvasSize({ width, height });
        }
      }
    });
    
    resizeObserver.observe(container);
    return () => {
      clearTimeout(timeoutId);
      resizeObserver.disconnect();
    };
  }, []);

  // Draw the map
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      console.warn('[PresetMap] Canvas ref not available');
      return;
    }
    
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      console.warn('[PresetMap] Could not get 2D context');
      return;
    }
    
    // Ensure valid canvas size - use minimum if invalid
    const width = Math.max(canvasSize.width, 400);
    const height = Math.max(canvasSize.height, 400);
    
    // Set canvas dimensions
    canvas.width = width;
    canvas.height = height;
    
    // Clear with visible background
    ctx.fillStyle = '#0a0a0a';
    ctx.fillRect(0, 0, width, height);
    
    // Draw grid
    ctx.strokeStyle = '#1a1a1a';
    ctx.lineWidth = 1;
    const gridSize = 50;
    for (let x = 0; x < width; x += gridSize) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    for (let y = 0; y < height; y += gridSize) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }
    
    // Point size based on dataset size
    const baseSize = allPresets.length > 10000 ? 2.5 : 3;
    
    // Create set for similar presets
    const similarIds = new Set(similarPresets.map(p => p.id));
    
    // First pass: Draw inactive (non-filtered) presets
    for (const preset of allPresets) {
      if (filteredIds.has(preset.id)) continue; // Skip active presets
      
      const pos = dataToCanvas(preset.x, preset.y);
      
      // Skip if outside viewport
      if (pos.x < -10 || pos.x > width + 10 ||
          pos.y < -10 || pos.y > height + 10) {
        continue;
      }
      
      // Desaturated/dimmed color for inactive presets
      const baseColor = getPresetColor(preset);
      const color = desaturateColor(baseColor, 0.85);
      
      // Draw point (smaller, dimmer)
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, baseSize * 0.7, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.globalAlpha = 0.25;
      ctx.fill();
    }
    
    ctx.globalAlpha = 1;
    
    // Second pass: Draw active (filtered) presets
    for (const preset of filteredPresets) {
      const pos = dataToCanvas(preset.x, preset.y);
      
      // Skip if outside viewport
      if (pos.x < -10 || pos.x > width + 10 ||
          pos.y < -10 || pos.y > height + 10) {
        continue;
      }
      
      const isSelected = selectedPreset?.id === preset.id;
      const isSimilar = similarIds.has(preset.id);
      
      // Determine color and size
      let color = getPresetColor(preset);
      let size = baseSize;
      let alpha = 0.85;
      
      if (isSimilar && !isSelected) {
        // Similar presets: purple ring
        size = baseSize * 1.4;
        alpha = 1;
      }
      
      if (isSelected) {
        // Selected preset: white with glow
        color = '#ffffff';
        size = baseSize * 2;
        alpha = 1;
      }
      
      // Draw point
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, size, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.globalAlpha = alpha;
      ctx.fill();
      
      // Draw ring for selected/similar
      if (isSelected) {
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 2;
        ctx.globalAlpha = 1;
        ctx.stroke();
        
        // Glow effect
        ctx.shadowBlur = 10;
        ctx.shadowColor = '#bc13fe';
        ctx.stroke();
        ctx.shadowBlur = 0;
      } else if (isSimilar) {
        ctx.strokeStyle = '#8b5cf6';
        ctx.lineWidth = 1.5;
        ctx.globalAlpha = 0.9;
        ctx.stroke();
      }
    }
    
    ctx.globalAlpha = 1;
    
    // Draw hovered preset tooltip
    if (hoveredPreset) {
      const pos = dataToCanvas(hoveredPreset.x, hoveredPreset.y);
      
      // Tooltip with cluster name - using single source of truth
      const clusterInfo = resolveClusterForPreset(hoveredPreset);
      const text = `${hoveredPreset.name}`;
      const subtext = `${hoveredPreset.game} • ${clusterInfo.name}`;
      
      ctx.font = 'bold 11px "Share Tech Mono", monospace';
      const metrics = ctx.measureText(text);
      ctx.font = '10px "Share Tech Mono", monospace';
      const subMetrics = ctx.measureText(subtext);
      
      const padding = 8;
      const tooltipWidth = Math.max(metrics.width, subMetrics.width) + padding * 2;
      const tooltipHeight = 36;
      
      let tooltipX = pos.x + 12;
      let tooltipY = pos.y - tooltipHeight - 8;
      
      // Keep tooltip in bounds
      if (tooltipX + tooltipWidth > width) {
        tooltipX = pos.x - tooltipWidth - 12;
      }
      if (tooltipY < 0) {
        tooltipY = pos.y + 18;
      }
      
      // Tooltip background
      ctx.fillStyle = 'rgba(0, 0, 0, 0.95)';
      ctx.fillRect(tooltipX, tooltipY, tooltipWidth, tooltipHeight);
      ctx.strokeStyle = getPresetColor(hoveredPreset);
      ctx.lineWidth = 1;
      ctx.strokeRect(tooltipX, tooltipY, tooltipWidth, tooltipHeight);
      
      // Text
      ctx.font = 'bold 11px "Share Tech Mono", monospace';
      ctx.fillStyle = '#ffffff';
      ctx.fillText(text, tooltipX + padding, tooltipY + 14);
      
      ctx.font = '10px "Share Tech Mono", monospace';
      ctx.fillStyle = '#888888';
      ctx.fillText(subtext, tooltipX + padding, tooltipY + 28);
    }
    
  }, [allPresets, filteredPresets, filteredIds, selectedPreset, similarPresets, 
      canvasSize, dataToCanvas, hoveredPreset, bounds]);

  // Mouse handlers (no drag/zoom - fixed view)
  const handleMouseMove = (e: React.MouseEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    
    const canvasX = e.clientX - rect.left;
    const canvasY = e.clientY - rect.top;
    
    // Find hovered preset (only active presets)
    const preset = findPresetAtPosition(canvasX, canvasY);
    setHoveredPreset(preset);
    onPresetHover(preset);
  };

  const handleMouseLeave = () => {
    setHoveredPreset(null);
    onPresetHover(null);
  };

  const handleClick = (e: React.MouseEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    
    const canvasX = e.clientX - rect.left;
    const canvasY = e.clientY - rect.top;
    
    const preset = findPresetAtPosition(canvasX, canvasY);
    if (preset) {
      onPresetClick(preset);
    }
  };

  // Show loading state if no presets
  if (allPresets.length === 0) {
    return (
      <div className="relative w-full h-full bg-[#0a0a0a] rounded-lg border border-[#222] flex items-center justify-center min-h-[400px]">
        <p className="text-white text-sm">Loading map...</p>
      </div>
    );
  }

  return (
    <div 
      ref={containerRef}
      className="relative w-full h-full bg-[#0a0a0a] rounded-lg border border-[#222] overflow-hidden min-h-[400px]"
    >
      <canvas
        ref={canvasRef}
        width={Math.max(canvasSize.width, 400)}
        height={Math.max(canvasSize.height, 400)}
        className="cursor-crosshair w-full h-full block"
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        onClick={handleClick}
      />
      
      {/* Stats overlay */}
      <div className="absolute bottom-2 right-2 px-2 py-1 bg-[#111]/80 border border-[#333] rounded text-[10px] text-white z-10">
        {filteredPresets.length.toLocaleString()} / {allPresets.length.toLocaleString()} presets
      </div>
    </div>
  );
};
