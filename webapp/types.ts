
export enum FMAlgorithm {
  ALGO_0, ALGO_1, ALGO_2, ALGO_3, ALGO_4, ALGO_5, ALGO_6, ALGO_7
}

export interface OperatorParams {
  id: number;
  ar: number; // Attack Rate (0-31)
  dr: number; // Decay Rate (0-31)
  sr: number; // Sustain Rate (0-31)
  rr: number; // Release Rate (0-15)
  sl: number; // Sustain Level (0-15)
  tl: number; // Total Level (Output Level) (0-127)
  mul: number; // Frequency Multiplier (0-15)
  dt: number; // Detune (0-7)
  rs: number; // Rate Scaling (0-3)
  ams: boolean; // Amplitude Modulation Enable
}

export interface YM2612Patch {
  name: string;
  description?: string; // AI Generated description
  algorithm: FMAlgorithm;
  feedback: number; // 0-7
  lfoFreq: number; // 0-7 (LFO Speed)
  ams: number; // Amplitude Modulation Sensitivity
  fms: number; // Frequency Modulation Sensitivity
  operators: [OperatorParams, OperatorParams, OperatorParams, OperatorParams]; // 4 Operators
}

export const DEFAULT_PATCH: YM2612Patch = {
  name: "INIT SINE",
  description: "Basic sine wave initialization.",
  algorithm: FMAlgorithm.ALGO_7, // All separate
  feedback: 0,
  lfoFreq: 0,
  ams: 0,
  fms: 0,
  operators: [
    { id: 0, ar: 31, dr: 0, sr: 0, rr: 4, sl: 0, tl: 0, mul: 1, dt: 0, rs: 0, ams: false },
    { id: 1, ar: 31, dr: 0, sr: 0, rr: 4, sl: 0, tl: 0, mul: 1, dt: 0, rs: 0, ams: false },
    { id: 2, ar: 31, dr: 0, sr: 0, rr: 4, sl: 0, tl: 0, mul: 1, dt: 0, rs: 0, ams: false },
    { id: 3, ar: 31, dr: 0, sr: 0, rr: 4, sl: 0, tl: 0, mul: 1, dt: 0, rs: 0, ams: false },
  ]
};
