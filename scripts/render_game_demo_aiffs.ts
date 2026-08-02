/**
 * Render game-demo exemplars (AIFF) for fingerprint / brightness slides.
 * Usage (repo root): npx --yes tsx scripts/render_game_demo_aiffs.ts
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { YM2612 } from "../webapp/services/audio/ym2612_core.ts";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");
const SRC =
  process.argv[2] != null
    ? path.resolve(process.argv[2])
    : path.join(ROOT, "artifacts", "game_demo_exemplars.json");
const OUT_DIR = path.join(ROOT, "Ludo2026-DAFMExplorer-LaTeX", "videos", "presets");

const CLOCK = 7670448;
const SAMPLE_RATE = 44100;
const NOTE_MIDI = 60;
const ATTACK_S = 0.05;
const HOLD_S = 1.2;
const RELEASE_S = 0.45;
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
};

type Exemplar = {
  id: string;
  label: string;
  CON: number;
  FL: number;
  Brightness: number;
  aiff: string;
  params: {
    algorithm: number;
    feedback: number;
    ams: number;
    pms: number;
    lfrq: number;
    operators: { m1: Op; c1: Op; m2: Op; c2: Op };
  };
};

function writePatch(ym: any, patch: Exemplar["params"]) {
  const ch = 0;
  ym.write(0xb0 + ch, ((patch.feedback & 7) << 3) | (patch.algorithm & 7));
  ym.write(0xb4 + ch, 0xc0 | ((patch.ams & 3) << 4) | (patch.pms & 7));
  const ops = [patch.operators.m1, patch.operators.c1, patch.operators.m2, patch.operators.c2];
  ops.forEach((op, i) => {
    const off = OP_REG_OFFSETS[i];
    ym.write(0x30 + ch + off, ((op.dt1 & 7) << 4) | (op.mul & 15));
    ym.write(0x40 + ch + off, op.tl & 127);
    ym.write(0x50 + ch + off, ((op.ks & 3) << 6) | (op.ar & 31));
    ym.write(0x60 + ch + off, (op.ams_en ? 0x80 : 0) | (op.d1r & 31));
    ym.write(0x70 + ch + off, op.d2r & 31);
    ym.write(0x80 + ch + off, ((op.d1l & 15) << 4) | (op.rr & 15));
    ym.write(0x90 + ch + off, 0);
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
    let s = Math.max(-1, Math.min(1, mono[i]));
    ssndData.writeInt16BE((s * 32767) | 0, i * 2);
  }
  let ssndPayload = Buffer.concat([Buffer.alloc(8), ssndData]);
  if (ssndPayload.length % 2) ssndPayload = Buffer.concat([ssndPayload, Buffer.alloc(1)]);

  const comm = Buffer.concat([
    Buffer.from([0, 1]),
    (() => {
      const b = Buffer.alloc(4);
      b.writeUInt32BE(n, 0);
      return b;
    })(),
    Buffer.from([0, 16]),
    float80(sampleRate),
  ]);
  let commPad = comm;
  if (commPad.length % 2) commPad = Buffer.concat([commPad, Buffer.alloc(1)]);

  const chunks = Buffer.concat([
    Buffer.from("COMM"),
    (() => {
      const b = Buffer.alloc(4);
      b.writeUInt32BE(commPad.length, 0);
      return b;
    })(),
    commPad,
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

function renderExemplar(ex: Exemplar): Float32Array {
  const ym = new (YM2612 as any)();
  ym.init(CLOCK, SAMPLE_RATE);
  ym.reset();
  ym.config(14);
  writePatch(ym, ex.params);

  const totalSamples = Math.floor((ATTACK_S + HOLD_S + RELEASE_S) * SAMPLE_RATE);
  const attackN = Math.floor(ATTACK_S * SAMPLE_RATE);
  const holdN = Math.floor(HOLD_S * SAMPLE_RATE);
  const out = new Float32Array(totalSamples);
  const CHUNK = 2048;
  let written = 0;
  let keyed = false;
  let released = false;

  while (written < totalSamples) {
    if (!keyed && written >= attackN) {
      noteOn(ym, NOTE_MIDI);
      keyed = true;
    }
    if (!released && written >= attackN + holdN) {
      noteOff(ym);
      released = true;
    }
    const n = Math.min(CHUNK, totalSamples - written);
    const frames = ym.update(n);
    const GAIN = 1.0 / 4096.0;
    for (let i = 0; i < n; i++) {
      const L = frames[0][i] * GAIN;
      const R = frames[1][i] * GAIN;
      out[written + i] = 0.5 * (L + R);
    }
    written += n;
  }
  const fade = Math.floor(0.01 * SAMPLE_RATE);
  for (let i = 0; i < fade; i++) {
    out[i] *= i / fade;
    out[totalSamples - 1 - i] *= i / fade;
  }
  return out;
}

function main() {
  if (!fs.existsSync(SRC)) {
    console.error("Missing", SRC, "— run scripts/select_game_demo_exemplars.py first");
    process.exit(1);
  }
  const data = JSON.parse(fs.readFileSync(SRC, "utf8")) as { exemplars: Exemplar[] };
  fs.mkdirSync(OUT_DIR, { recursive: true });

  const files: Record<string, unknown>[] = [];
  for (const ex of data.exemplars) {
    const pcm = renderExemplar(ex);
    const outPath = path.join(OUT_DIR, ex.aiff);
    fs.writeFileSync(outPath, encodeAiff(pcm, SAMPLE_RATE));
    console.log("wrote", ex.aiff, ex.label, `CON=${ex.CON}`, `B=${ex.Brightness}`);
    files.push({
      aiff: ex.aiff,
      id: ex.id,
      label: ex.label,
      CON: ex.CON,
      FL: ex.FL,
      Brightness: ex.Brightness,
    });
  }
  fs.writeFileSync(
    path.join(OUT_DIR, "game_demo_manifest.json"),
    JSON.stringify({ format: "aiff", note_midi: NOTE_MIDI, sample_rate: SAMPLE_RATE, files }, null, 2)
  );
  console.log("done", files.length);
}

main();
