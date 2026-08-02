import fs from "node:fs";
import { YM2612 } from "../webapp/services/audio/ym2612_core.ts";

const data = JSON.parse(fs.readFileSync("artifacts/game_demo_exemplars.json", "utf8"));
const CLOCK = 7670448;
const SR = 44100;
const OFF = [0x00, 0x08, 0x04, 0x0c];

function render(ex: any): number {
  const ym = new (YM2612 as any)();
  ym.init(CLOCK, SR);
  ym.reset();
  ym.config(14);
  const p = ex.params;
  const ch = 0;
  ym.write(0xb0 + ch, ((p.feedback & 7) << 3) | (p.algorithm & 7));
  ym.write(0xb4 + ch, 0xc0 | ((p.ams & 3) << 4) | (p.pms & 7));
  const ops = [p.operators.m1, p.operators.c1, p.operators.m2, p.operators.c2];
  ops.forEach((op: any, i: number) => {
    const off = OFF[i];
    ym.write(0x30 + ch + off, ((op.dt1 & 7) << 4) | (op.mul & 15));
    ym.write(0x40 + ch + off, op.tl & 127);
    ym.write(0x50 + ch + off, ((op.ks & 3) << 6) | (op.ar & 31));
    ym.write(0x60 + ch + off, (op.ams_en ? 0x80 : 0) | (op.d1r & 31));
    ym.write(0x70 + ch + off, op.d2r & 31);
    ym.write(0x80 + ch + off, ((op.d1l & 15) << 4) | (op.rr & 15));
    ym.write(0x90 + ch + off, 0);
  });
  const midi = 60;
  const freq = 440 * Math.pow(2, (midi - 69) / 12);
  let block = Math.floor((midi - 12) / 12);
  let fnum = Math.round((freq * 1048576 * 144) / CLOCK / Math.pow(2, block - 1));
  while (fnum > 2047 && block < 7) {
    block++;
    fnum = Math.round((freq * 1048576 * 144) / CLOCK / Math.pow(2, block - 1));
  }
  ym.write(0xa4, (block << 3) | ((fnum >> 8) & 7));
  ym.write(0xa0, fnum & 0xff);
  ym.write(0x28, 0xf0);
  let peak = 0;
  for (let i = 0; i < SR; i++) {
    const f = ym.update(1);
    const s = (0.5 * (f[0][0] + f[1][0])) / 4096;
    peak = Math.max(peak, Math.abs(s));
  }
  return peak;
}

for (const id of ["GH", "TPW", "TIN", "PM"]) {
  const ex = data.exemplars.find((e: any) => e.id === id);
  const peak = render(ex);
  console.log(id, "peak", peak.toFixed(6), "alg", ex.params.algorithm, "FL", ex.params.feedback);
}
