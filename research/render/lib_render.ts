/**
 * Shared YM2612 write helpers for the corpus renderer and the VGM player.
 *
 * Register conventions match research/configs/render.yaml and the chip docs:
 * LFO off, both channels forced, SSG-EG zeroed, A4 latched before A0.
 */

import { createHash } from "node:crypto";
import { YM2612 } from "../../webapp/services/audio/ym2612_core.ts";

export const OP_NAMES = ["M1", "C1", "M2", "C2"] as const;
export const OP_REG_OFFSETS = [0x00, 0x08, 0x04, 0x0c] as const;

export type OperatorParams = {
  AR: number;
  D1R: number;
  D2R: number;
  RR: number;
  D1L: number;
  TL: number;
  KS: number;
  MUL: number;
  DT1: number;
};

export type PatchParams = {
  CON: number;
  FL: number;
} & {
  [K in `${(typeof OP_NAMES)[number]}_${keyof OperatorParams}`]: number;
};

export type RenderTiming = {
  sampleRate: number;
  clockHz: number;
  noteMidi: number;
  preRollS: number;
  sustainS: number;
  releaseS: number;
  edgeFadeS: number;
  dacPrecision: number;
  channel: number;
};

export function fnumBlock(midi: number, clockHz: number): { fnum: number; block: number } {
  const freq = 440 * Math.pow(2, (midi - 69) / 12);
  let block = Math.floor((midi - 12) / 12);
  if (block < 0) block = 0;
  if (block > 7) block = 7;
  const mult = (freq * 1048576 * 144) / clockHz;
  let fnum = Math.round(mult / Math.pow(2, block - 1));
  while (fnum > 2047 && block < 7) {
    block++;
    fnum = Math.round(mult / Math.pow(2, block - 1));
  }
  if (fnum > 2047) fnum = 2047;
  return { fnum, block };
}

export function keyCode(fnum: number, block: number): number {
  const f11 = (fnum >> 10) & 1;
  const f10 = (fnum >> 9) & 1;
  const f9 = (fnum >> 8) & 1;
  const f8 = (fnum >> 7) & 1;
  const n3 = f11;
  const n2 = (f11 & (f10 | f9 | f8)) | ((1 - f11) & f10 & f9 & f8);
  return ((block & 7) << 2) | (n3 << 1) | n2;
}

export function createChip(timing: RenderTiming): any {
  const ym = new (YM2612 as any)();
  ym.init(timing.clockHz, timing.sampleRate);
  ym.reset();
  ym.config(timing.dacPrecision);
  // Explicit init matching render.yaml / hardware battery.
  ym.write(0x22, 0); // LFO off
  ym.write(0x27, 0); // normal mode
  ym.write(0x2b, 0); // DAC off
  return ym;
}

export function writePatch(ym: any, patch: PatchParams, channel = 0): void {
  ym.write(0xb0 + channel, ((patch.FL & 7) << 3) | (patch.CON & 7));
  // Force both channels (0xC0). PAN from the corpus is therefore inert.
  ym.write(0xb4 + channel, 0xc0);
  for (let i = 0; i < 4; i++) {
    const op = OP_NAMES[i];
    const off = OP_REG_OFFSETS[i];
    const dt1 = (patch as any)[`${op}_DT1`] & 7;
    const mul = (patch as any)[`${op}_MUL`] & 15;
    const tl = (patch as any)[`${op}_TL`] & 127;
    const ks = (patch as any)[`${op}_KS`] & 3;
    const ar = (patch as any)[`${op}_AR`] & 31;
    const d1r = (patch as any)[`${op}_D1R`] & 31;
    const d2r = (patch as any)[`${op}_D2R`] & 31;
    const d1l = (patch as any)[`${op}_D1L`] & 15;
    const rr = (patch as any)[`${op}_RR`] & 15;
    ym.write(0x30 + channel + off, (dt1 << 4) | mul);
    ym.write(0x40 + channel + off, tl);
    ym.write(0x50 + channel + off, (ks << 6) | ar);
    ym.write(0x60 + channel + off, d1r); // AMS-EN left clear; LFO is off anyway
    ym.write(0x70 + channel + off, d2r);
    ym.write(0x80 + channel + off, (d1l << 4) | rr);
    ym.write(0x90 + channel + off, 0); // SSG-EG = 0
  }
}

export function noteOn(ym: any, midi: number, clockHz: number, channel = 0, slots = 15): void {
  const { fnum, block } = fnumBlock(midi, clockHz);
  // High byte latched first.
  ym.write(0xa4 + channel, (block << 3) | ((fnum >> 8) & 7));
  ym.write(0xa0 + channel, fnum & 0xff);
  ym.write(0x28, ((slots & 15) << 4) | (channel & 7));
}

export function noteOff(ym: any, channel = 0): void {
  ym.write(0x28, channel & 7);
}

export function renderNote(
  patch: PatchParams,
  timing: RenderTiming,
  gain: number
): Float32Array {
  const ym = createChip(timing);
  writePatch(ym, patch, timing.channel);

  const preN = Math.floor(timing.preRollS * timing.sampleRate);
  const susN = Math.floor(timing.sustainS * timing.sampleRate);
  const relN = Math.floor(timing.releaseS * timing.sampleRate);
  const total = preN + susN + relN;
  const out = new Float32Array(total);
  const CHUNK = 2048;
  let written = 0;
  let keyed = false;
  let released = false;

  while (written < total) {
    if (!keyed && written >= preN) {
      noteOn(ym, timing.noteMidi, timing.clockHz, timing.channel, 15);
      keyed = true;
    }
    if (!released && written >= preN + susN) {
      noteOff(ym, timing.channel);
      released = true;
    }
    const n = Math.min(CHUNK, total - written);
    const frames = ym.update(n);
    for (let i = 0; i < n; i++) {
      const L = frames[0][i] * gain;
      const R = frames[1][i] * gain;
      out[written + i] = 0.5 * (L + R);
    }
    written += n;
  }

  const fade = Math.floor(timing.edgeFadeS * timing.sampleRate);
  for (let i = 0; i < fade && i < total; i++) {
    const w = i / fade;
    out[i] *= w;
    out[total - 1 - i] *= w;
  }
  return out;
}

export function pcmSha256(samples: Float32Array): string {
  // Little-endian float32, matching Python provenance.sha256_pcm.
  const buf = Buffer.alloc(samples.length * 4);
  for (let i = 0; i < samples.length; i++) {
    buf.writeFloatLE(samples[i], i * 4);
  }
  return createHash("sha256").update(buf).digest("hex");
}

export function peakRms(samples: Float32Array): { peak: number; rms: number } {
  let peak = 0;
  let sumSq = 0;
  for (let i = 0; i < samples.length; i++) {
    const a = Math.abs(samples[i]);
    if (a > peak) peak = a;
    sumSq += samples[i] * samples[i];
  }
  return { peak, rms: Math.sqrt(sumSq / Math.max(samples.length, 1)) };
}

export function encodeWavPcm24(mono: Float32Array, sampleRate: number): Buffer {
  const n = mono.length;
  const dataBytes = n * 3;
  const buffer = Buffer.alloc(44 + dataBytes);
  buffer.write("RIFF", 0);
  buffer.writeUInt32LE(36 + dataBytes, 4);
  buffer.write("WAVE", 8);
  buffer.write("fmt ", 12);
  buffer.writeUInt32LE(16, 16);
  buffer.writeUInt16LE(1, 20); // PCM
  buffer.writeUInt16LE(1, 22); // mono
  buffer.writeUInt32LE(sampleRate, 24);
  buffer.writeUInt32LE(sampleRate * 3, 28);
  buffer.writeUInt16LE(3, 32);
  buffer.writeUInt16LE(24, 34);
  buffer.write("data", 36);
  buffer.writeUInt32LE(dataBytes, 40);
  let o = 44;
  for (let i = 0; i < n; i++) {
    let s = Math.max(-1, Math.min(1, mono[i]));
    let v = Math.round(s * 8388607);
    buffer[o++] = v & 0xff;
    buffer[o++] = (v >> 8) & 0xff;
    buffer[o++] = (v >> 16) & 0xff;
  }
  return buffer;
}

export function timingFromRenderYaml(cfg: any): RenderTiming {
  return {
    sampleRate: cfg.timing.sample_rate,
    clockHz: cfg.chip.clock_hz,
    noteMidi: cfg.timing.note_midi,
    preRollS: cfg.timing.pre_roll_s,
    sustainS: cfg.timing.sustain_s,
    releaseS: cfg.timing.release_s,
    edgeFadeS: cfg.timing.edge_fade_s,
    dacPrecision: cfg.chip.dac_precision,
    channel: cfg.chip.channel ?? 0,
  };
}
