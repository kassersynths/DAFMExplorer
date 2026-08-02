/**
 * Pedagogical YM2612 notes: carrier / FM stack / LFO-AM / feedback.
 * Usage: npx --yes tsx scripts/render_fm_pedagogy_aiffs.ts
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { YM2612 } from "../webapp/services/audio/ym2612_core.ts";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");
const OUT_DIR = path.join(ROOT, "Ludo2026-DAFMExplorer-LaTeX", "videos", "presets");

const CLOCK = 7670448;
const SAMPLE_RATE = 44100;
const NOTE_MIDI = 60;
const ATTACK_S = 0.04;
const HOLD_S = 1.6;
const RELEASE_S = 0.5;
const OP_REG_OFFSETS = [0x00, 0x08, 0x04, 0x0c];

type Op = {
  ar: number;
  d1r: number;
  d2r: number;
  rr: number;
  d1l: number;
  tl: number;
  ks: number;
  mul: number;
  dt1: number;
  ams_en: number;
  ssg?: number;
};

type Patch = {
  name: string;
  algorithm: number;
  feedback: number;
  ams: number;
  pms: number;
  /** LFO: enable bit + speed 0–7 written to reg 0x22 */
  lfo: number;
  operators: [Op, Op, Op, Op]; // M1, C1, M2, C2
};

const silent = (tl = 127): Op => ({
  ar: 31,
  d1r: 0,
  d2r: 0,
  rr: 15,
  d1l: 0,
  tl,
  ks: 0,
  mul: 1,
  dt1: 0,
  ams_en: 0,
});

const PATCHES: Patch[] = [
  {
    name: "demo_carrier_only.aiff",
    algorithm: 7,
    feedback: 0,
    ams: 0,
    pms: 0,
    lfo: 0,
    operators: [
      silent(),
      { ar: 31, d1r: 0, d2r: 0, rr: 10, d1l: 0, tl: 12, ks: 0, mul: 1, dt1: 0, ams_en: 0 },
      silent(),
      silent(),
    ],
  },
  {
    // Alg.4: M1→C1 and M2→C2; mute second pair → classic 2-op FM colour
    name: "demo_fm_stack.aiff",
    algorithm: 4,
    feedback: 0,
    ams: 0,
    pms: 0,
    lfo: 0,
    operators: [
      { ar: 31, d1r: 5, d2r: 2, rr: 8, d1l: 2, tl: 18, ks: 0, mul: 6, dt1: 0, ams_en: 0 },
      { ar: 31, d1r: 4, d2r: 1, rr: 8, d1l: 1, tl: 10, ks: 0, mul: 1, dt1: 0, ams_en: 0 },
      silent(),
      silent(),
    ],
  },
  {
    // Same single carrier, LFO AM depth max (AMS) — tremolo, not FM sidebands
    name: "demo_am_lfo.aiff",
    algorithm: 7,
    feedback: 0,
    ams: 3,
    pms: 0,
    lfo: 0x8 | 4, // enable + mid speed
    operators: [
      silent(),
      { ar: 31, d1r: 0, d2r: 0, rr: 10, d1l: 0, tl: 12, ks: 0, mul: 1, dt1: 0, ams_en: 1 },
      silent(),
      silent(),
    ],
  },
  {
    name: "demo_feedback.aiff",
    algorithm: 4,
    feedback: 7,
    ams: 0,
    pms: 0,
    lfo: 0,
    operators: [
      { ar: 31, d1r: 8, d2r: 3, rr: 10, d1l: 3, tl: 22, ks: 0, mul: 1, dt1: 0, ams_en: 0 },
      { ar: 31, d1r: 5, d2r: 2, rr: 8, d1l: 2, tl: 14, ks: 0, mul: 1, dt1: 0, ams_en: 0 },
      silent(),
      silent(),
    ],
  },
];

function float80(x: number): Buffer {
  const buf = Buffer.alloc(10);
  if (x === 0) return buf;
  let sign = 0;
  let v = x;
  if (v < 0) {
    sign = 0x8000;
    v = -v;
  }
  const exp = Math.floor(Math.log2(v));
  const mant = BigInt(Math.round(v * Math.pow(2, 63 - exp)));
  buf.writeUInt16BE((exp + 16383) | sign, 0);
  buf.writeBigUInt64BE(mant, 2);
  return buf;
}

function encodeAiff(mono: Float32Array, sampleRate: number): Buffer {
  const n = mono.length;
  const ssndData = Buffer.alloc(n * 2);
  for (let i = 0; i < n; i++) {
    const s = Math.max(-1, Math.min(1, mono[i]));
    ssndData.writeInt16BE((s * 32767) | 0, i * 2);
  }
  let ssndPayload = Buffer.concat([Buffer.alloc(8), ssndData]);
  if (ssndPayload.length % 2) ssndPayload = Buffer.concat([ssndPayload, Buffer.alloc(1)]);
  let comm = Buffer.concat([
    Buffer.from([0, 1]),
    (() => {
      const b = Buffer.alloc(4);
      b.writeUInt32BE(n, 0);
      return b;
    })(),
    Buffer.from([0, 16]),
    float80(sampleRate),
  ]);
  if (comm.length % 2) comm = Buffer.concat([comm, Buffer.alloc(1)]);
  const chunks = Buffer.concat([
    Buffer.from("COMM"),
    (() => {
      const b = Buffer.alloc(4);
      b.writeUInt32BE(comm.length, 0);
      return b;
    })(),
    comm,
    Buffer.from("SSND"),
    (() => {
      const b = Buffer.alloc(4);
      b.writeUInt32BE(ssndPayload.length, 0);
      return b;
    })(),
    ssndPayload,
  ]);
  const formSize = 4 + chunks.length;
  const out = Buffer.alloc(8 + formSize);
  out.write("FORM", 0);
  out.writeUInt32BE(formSize, 4);
  out.write("AIFF", 8);
  chunks.copy(out, 12);
  return out;
}

function writePatch(ym: any, patch: Patch) {
  ym.write(0x22, patch.lfo & 0xff);
  const ch = 0;
  ym.write(0xb0 + ch, ((patch.feedback & 7) << 3) | (patch.algorithm & 7));
  ym.write(0xb4 + ch, 0xc0 | ((patch.ams & 3) << 4) | (patch.pms & 7));
  patch.operators.forEach((op, i) => {
    const off = OP_REG_OFFSETS[i];
    ym.write(0x30 + ch + off, ((op.dt1 & 7) << 4) | (op.mul & 15));
    ym.write(0x40 + ch + off, op.tl & 127);
    ym.write(0x50 + ch + off, ((op.ks & 3) << 6) | (op.ar & 31));
    ym.write(0x60 + ch + off, (op.ams_en ? 0x80 : 0) | (op.d1r & 31));
    ym.write(0x70 + ch + off, op.d2r & 31);
    ym.write(0x80 + ch + off, ((op.d1l & 15) << 4) | (op.rr & 15));
    ym.write(0x90 + ch + off, (op.ssg ?? 0) & 15);
  });
}

function noteOn(ym: any, midi: number) {
  const freq = 440 * Math.pow(2, (midi - 69) / 12);
  let block = Math.floor((midi - 12) / 12);
  if (block < 0) block = 0;
  if (block > 7) block = 7;
  const mult = (freq * 1048576 * 144) / CLOCK;
  let fnum = Math.round(mult / Math.pow(2, block - 1));
  while (fnum > 2047 && block < 7) {
    block++;
    fnum = Math.round(mult / Math.pow(2, block - 1));
  }
  if (fnum > 2047) fnum = 2047;
  ym.write(0xa4, (block << 3) | ((fnum >> 8) & 7));
  ym.write(0xa0, fnum & 0xff);
  ym.write(0x28, 0xf0 | 0);
}

function noteOff(ym: any) {
  ym.write(0x28, 0x00 | 0);
}

function render(patch: Patch): Float32Array {
  const ym = new (YM2612 as any)();
  ym.init(CLOCK, SAMPLE_RATE);
  ym.reset();
  ym.config(14);
  writePatch(ym, patch);
  const total = Math.floor((ATTACK_S + HOLD_S + RELEASE_S) * SAMPLE_RATE);
  const attackN = Math.floor(ATTACK_S * SAMPLE_RATE);
  const holdN = Math.floor(HOLD_S * SAMPLE_RATE);
  const out = new Float32Array(total);
  let written = 0;
  let keyed = false;
  let released = false;
  const CHUNK = 2048;
  while (written < total) {
    if (!keyed && written >= attackN) {
      noteOn(ym, NOTE_MIDI);
      keyed = true;
    }
    if (!released && written >= attackN + holdN) {
      noteOff(ym);
      released = true;
    }
    const n = Math.min(CHUNK, total - written);
    const frames = ym.update(n);
    const GAIN = 1.0 / 4096.0;
    for (let i = 0; i < n; i++) {
      out[written + i] = 0.5 * (frames[0][i] + frames[1][i]) * GAIN;
    }
    written += n;
  }
  const fade = Math.floor(0.01 * SAMPLE_RATE);
  for (let i = 0; i < fade; i++) {
    out[i] *= i / fade;
    out[total - 1 - i] *= i / fade;
  }
  return out;
}

function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  for (const p of PATCHES) {
    console.log("Rendering", p.name);
    const pcm = render(p);
    fs.writeFileSync(path.join(OUT_DIR, p.name), encodeAiff(pcm, SAMPLE_RATE));
  }
  console.log("Wrote", PATCHES.length, "pedagogy AIFFs ->", OUT_DIR);
}

main();
