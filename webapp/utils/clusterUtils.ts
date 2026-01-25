/**
 * Cluster utility functions for consistent color and name mapping
 */

import { CLUSTER_COLORS, CLUSTER_NAMES } from '../types/preset';

/**
 * Get cluster color by ID or name
 */
export function getClusterColor(clusterIdOrName: number | string): string {
  if (typeof clusterIdOrName === 'number') {
    return CLUSTER_COLORS[clusterIdOrName] || '#666';
  }
  
  // If it's a name, find the ID first
  const clusterId = Object.entries(CLUSTER_NAMES).find(
    ([_, name]) => name === clusterIdOrName
  )?.[0];
  
  if (clusterId) {
    return CLUSTER_COLORS[parseInt(clusterId)] || '#666';
  }
  
  return '#666';
}

/**
 * Get cluster name by ID
 */
export function getClusterName(clusterId: number): string {
  return CLUSTER_NAMES[clusterId] || `Cluster ${clusterId}`;
}

/**
 * Resolve cluster ID from preset (handles both cluster and clusterId fields)
 */
export function resolveClusterId(preset: { cluster?: number; clusterId?: number }): number {
  return preset.cluster ?? preset.clusterId ?? 0;
}

/**
 * SINGLE SOURCE OF TRUTH: Resolve cluster information for a preset
 * This function MUST be used everywhere to ensure consistency between map and panel
 * 
 * @param preset - Preset object with cluster information
 * @returns Cluster info with id, name, and color
 */
export function resolveClusterForPreset(preset: { cluster?: number; clusterId?: number; clusterName?: string } | null | undefined): {
  id: number;
  name: string;
  color: string;
} {
  // Handle null/undefined
  if (!preset) {
    return {
      id: 0,
      name: 'Unknown Cluster',
      color: '#666',
    };
  }

  // If preset has clusterName directly, try to find it
  if (preset.clusterName && typeof preset.clusterName === 'string') {
    const clusterId = Object.entries(CLUSTER_NAMES).find(
      ([_, name]) => name === preset.clusterName
    )?.[0];
    
    if (clusterId !== undefined) {
      const id = parseInt(clusterId);
      return {
        id,
        name: preset.clusterName,
        color: getClusterColor(id),
      };
    }
  }

  // Resolve cluster ID from preset
  const id = resolveClusterId(preset);
  
  // Validate cluster ID is in valid range (0-6)
  const validId = (id >= 0 && id <= 6) ? id : 0;
  
  const name = getClusterName(validId);
  const color = getClusterColor(validId);
  
  // Final guard: ensure we never return a number as name
  const finalName = (name && !name.match(/^Cluster \d+$/)) ? name : CLUSTER_NAMES[validId] || 'Unknown Cluster';
  
  return {
    id: validId,
    name: finalName,
    color,
  };
}

/**
 * Get cluster name and color for a preset
 * Alias for resolveClusterForPreset to maintain backward compatibility
 * @deprecated Use resolveClusterForPreset for consistency
 */
export function getClusterInfo(preset: { cluster?: number; clusterId?: number; clusterName?: string } | null | undefined): {
  id: number;
  name: string;
  color: string;
} {
  return resolveClusterForPreset(preset);
}
