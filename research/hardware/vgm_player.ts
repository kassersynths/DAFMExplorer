/**
 * Play a VGM through the YM2612 emulator and write a reference mono WAV.
 *
 * Usage (from research/render after npm install, or with npx tsx):
 *   node --import tsx ../hardware/vgm_player.ts --vgm path.vgm --out ref.wav
 *
 * The same VGM drives hardware recording; comparing that take to this reference
 * isolates chip/analogue difference from command-stream confounds.
 *
 * YM2612.update(n) returns [left[], right[]] of chip-native integer samples.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { YM2612 } from "../../webapp/services/audio/ym2612_core.ts";
import { encodeWavPcm24 } from "../render/lib_render.ts";

type YmChip = {
  init: (clock: number, rate: number) => void;
  reset: () => void;
  config: (bits: number) => void;
  write: (addr: number, val: number) => void;
  update: (n: number) => [number[], number[]];
};

function stageLog(kind: string, fields: Record<string, string | number>): void {
  const parts = Object.entries(fields).map(([k, v]) => `${k}=${String(v).replace(/ /g, "_")}`);
  console.error(`${kind} ${parts.join(" ")}`);
}

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_VGM = path.join(__dirname, "validation_battery_v1.vgm");
const DEFAULT_OUT = path.join(__dirname, "..", "artifacts", "hw", "emu_reference.wav");

const SAMPLE_RATE = 44100;
const DAC_PRECISION = 14;
const DEFAULT_GAIN = 1 / 4096;

type Cli = {
  vgm: string;
  out: string;
  gain: number;
  clockOverride: number | null;
};

function parseArgs(argv: string[]): Cli {
  let vgm = DEFAULT_VGM;
  let out = DEFAULT_OUT;
  let gain = DEFAULT_GAIN;
  let clockOverride: number | null = null;
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--vgm") vgm = path.resolve(argv[++i]);
    else if (a === "--out") out = path.resolve(argv[++i]);
    else if (a === "--gain") gain = Number(argv[++i]);
    else if (a === "--clock") clockOverride = Number(argv[++i]);
    else if (a === "--help" || a === "-h") {
      console.log(
        "Usage: node --import tsx vgm_player.ts [--vgm path] [--out path] [--gain G] [--clock Hz]",
      );
      process.exit(0);
    } else throw new Error(`unknown argument: ${a}`);
  }
  return { vgm, out, gain, clockOverride };
}

function readU32(buf: Buffer, off: number): number {
  return buf.readUInt32LE(off);
}

function parseVgmHeader(buf: Buffer): {
  version: number;
  dataOffset: number;
  clockHz: number;
  totalSamples: number;
  loopOffset: number;
} {
  if (buf.toString("ascii", 0, 4) !== "Vgm ") {
    throw new Error("not a VGM file");
  }
  const version = readU32(buf, 0x08);
  const totalSamples = readU32(buf, 0x18);
  const loopOffset = readU32(buf, 0x1c);
  const clockHz = readU32(buf, 0x2c) & 0x3fffffff; // mask dual-chip flags
  let dataOffsetRel = 0x0c;
  if (version >= 0x150) {
    dataOffsetRel = readU32(buf, 0x34);
  }
  const dataOffset = 0x34 + dataOffsetRel;
  return { version, dataOffset, clockHz, totalSamples, loopOffset };
}

/**
 * Stream VGM commands into the chip, collecting mono float32 audio.
 * Supports YM2612 port writes (0x52/0x53), waits, and end-of-data.
 */
function playVgm(
  ym: YmChip,
  buf: Buffer,
  dataOffset: number,
  gain: number,
): Float32Array {
  const chunks: Float32Array[] = [];
  let i = dataOffset;
  let done = false;

  const flushWait = (n: number) => {
    if (n <= 0) return;
    const CHUNK = 4096;
    let left = n;
    while (left > 0) {
      const m = Math.min(CHUNK, left);
      const frames = ym.update(m);
      const mono = new Float32Array(m);
      for (let s = 0; s < m; s++) {
        mono[s] = 0.5 * (frames[0][s] * gain + frames[1][s] * gain);
      }
      chunks.push(mono);
      left -= m;
    }
  };

  while (!done && i < buf.length) {
    const cmd = buf[i++];
    if (cmd === 0x66) {
      done = true;
      break;
    }
    if (cmd === 0x52 || cmd === 0x53) {
      const addr = buf[i++];
      const val = buf[i++];
      const full = cmd === 0x53 ? addr | 0x100 : addr;
      ym.write(full, val);
      continue;
    }
    if (cmd === 0x61) {
      const n = buf[i] | (buf[i + 1] << 8);
      i += 2;
      flushWait(n);
      continue;
    }
    if (cmd === 0x62) {
      flushWait(735);
      continue;
    }
    if (cmd === 0x63) {
      flushWait(882);
      continue;
    }
    if (cmd >= 0x70 && cmd <= 0x7f) {
      flushWait((cmd & 0x0f) + 1);
      continue;
    }
    // Dual-chip / PCM / other: skip conservatively by known sizes where possible.
    if (cmd === 0x67) {
      // data block: 0x67 0x66 tt ss ss ss ss <data>
      i += 1; // 0x66
      i += 1; // type
      const size = buf.readUInt32LE(i);
      i += 4 + size;
      continue;
    }
    if (cmd >= 0x30 && cmd <= 0x3f) {
      i += 1;
      continue;
    }
    if (cmd >= 0x40 && cmd <= 0x4f) {
      i += 2;
      continue;
    }
    if (cmd >= 0x50 && cmd <= 0x5f) {
      i += 2;
      continue;
    }
    if (cmd >= 0xa0 && cmd <= 0xbf) {
      i += 2;
      continue;
    }
    if (cmd >= 0xc0 && cmd <= 0xdf) {
      i += 3;
      continue;
    }
    if (cmd >= 0xe0 && cmd <= 0xff) {
      i += 4;
      continue;
    }
    throw new Error(`unsupported VGM command 0x${cmd.toString(16)} at offset ${i - 1}`);
  }

  let total = 0;
  for (const c of chunks) total += c.length;
  const out = new Float32Array(total);
  let o = 0;
  for (const c of chunks) {
    out.set(c, o);
    o += c.length;
  }
  return out;
}

function main() {
  const cli = parseArgs(process.argv.slice(2));
  if (!fs.existsSync(cli.vgm)) {
    throw new Error(
      `missing VGM: ${cli.vgm}. Run research/hardware/build_validation_vgm.py first.`,
    );
  }
  const buf = fs.readFileSync(cli.vgm);
  const header = parseVgmHeader(buf);
  const clock = cli.clockOverride ?? header.clockHz;

  stageLog("STAGE_START", {
    stage: "vgm_player",
    vgm: path.basename(cli.vgm),
    clock,
    total_samples: header.totalSamples,
  });

  const ym = new (YM2612 as any)() as YmChip;
  ym.init(clock, SAMPLE_RATE);
  ym.reset();
  ym.config(DAC_PRECISION);

  const started = Date.now();
  const mono = playVgm(ym, buf, header.dataOffset, cli.gain);
  fs.mkdirSync(path.dirname(cli.out), { recursive: true });
  fs.writeFileSync(cli.out, encodeWavPcm24(mono, SAMPLE_RATE));

  let peak = 0;
  for (let i = 0; i < mono.length; i++) {
    const a = Math.abs(mono[i]);
    if (a > peak) peak = a;
  }

  stageLog("STAGE_DONE", {
    stage: "vgm_player",
    out: path.basename(cli.out),
    n_samples: mono.length,
    peak: peak.toFixed(6),
    elapsed_s: ((Date.now() - started) / 1000).toFixed(1),
  });
  console.log(
    JSON.stringify(
      {
        out: cli.out,
        clock_hz: clock,
        n_samples: mono.length,
        duration_s: mono.length / SAMPLE_RATE,
        peak,
      },
      null,
      2,
    ),
  );
}

try {
  main();
} catch (err) {
  stageLog("STAGE_FAIL", {
    stage: "vgm_player",
    error: err instanceof Error ? err.name : "Error",
  });
  console.error(err);
  process.exit(1);
}
