/**
 * Piano Layout Configuration
 * Editable constants for fine-tuning black key positioning
 * All values are fractions (0.0-1.0) for proportional scaling
 */

// Vertical offset for black keys as fraction of key height (0.0-0.3)
// Increase this value to move black keys higher (more separation from white keys)
// Decrease to move black keys lower (closer to white keys)
// Example: 0.18 = 18% of key height
// EDIT THIS VALUE to adjust how high black keys appear above white keys
// Reduced to bring black keys closer to white keys after white keys are lowered
export const BLACK_KEY_Y_OFFSET_FRAC = 0.18;

// Extra horizontal spacing between black keys as fraction of white key width (0.0-0.1)
// Increase this value to spread black keys further apart
// Decrease this value to bring black keys closer together
// Example: 0.01 = 1% of white key width
// Note: This spacing is applied symmetrically around the center
// EDIT THIS VALUE to adjust horizontal spacing between black keys
export const BLACK_KEY_X_SPACING_FRAC = 0.01;
