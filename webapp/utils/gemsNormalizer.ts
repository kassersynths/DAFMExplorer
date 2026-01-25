/**
 * GEMS value normalizer - Robust normalization for GEMS filter
 */

/**
 * Normalize GEMS value to boolean
 * @param value - Raw GEMS value from dataset (can be boolean, number, string, null, undefined)
 * @returns true if value indicates GEMS, false otherwise (including null/undefined)
 */
export function normalizeGems(value: unknown): boolean {
  // Handle null/undefined/empty string as false
  if (value === null || value === undefined || value === '') {
    return false;
  }

  // Handle boolean
  if (typeof value === 'boolean') {
    return value;
  }

  // Handle number
  if (typeof value === 'number') {
    return value !== 0;
  }

  // Handle string
  if (typeof value === 'string') {
    const normalized = value.toLowerCase().trim();
    // True values
    if (['true', '1', 'yes', 'y', 'gems'].includes(normalized)) {
      return true;
    }
    // False values (explicit)
    if (['false', '0', 'no', 'n', ''].includes(normalized)) {
      return false;
    }
    // Default: if it's a non-empty string that doesn't match false patterns, treat as true
    // (but this shouldn't happen with proper data)
    return normalized.length > 0;
  }

  // Default: any other type is false
  return false;
}
