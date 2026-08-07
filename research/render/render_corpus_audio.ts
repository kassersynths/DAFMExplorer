/**
 * Deterministic batch renderer for the YM2612 corpus.
 *
 * Usage (from research/render after `npm install`):
 *   node --import tsx render_corpus_audio.ts --shard 0/16 --mode probe [--limit K]
 *   node --import tsx render_corpus_audio.ts --shard 0/16 --mode final --gain G
 *   node --import tsx render_corpus_audio.ts --shard 0/16 --probe-only
 *
 * Manifest format: JSON array of {config_id, CON, FL, M1_AR, ...} as written by
 * dafm_audio.render_manifest.build_render_queue. Render protocol is loaded from
 * ../configs/render.yaml so the Python config_hash stays authoritative.
 *
 * Output: mono PCM24 WAV + .meta.json under scratch/audio/<prefix>/<id>.wav.
 * Python soundfile converts WAV -> FLAC 24-bit afterwards
 * (dafm_audio.render_manifest.encode_wav_to_flac). Hash target is always the
 * float32 LE PCM buffer, never container bytes.
 *
 * YM2612.update(n) returns [left[], right[]] of chip-native integer samples.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parse as parseYaml } from "yaml";
import {
  OP_NAMES,
  encodeWavPcm24,
  pcmSha256,
  peakRms,
  renderNote,
  timingFromRenderYaml,
  type PatchParams,
} from "./lib_render.ts";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const RESEARCH = path.resolve(__dirname, "..");

type QueueRow = { config_id: string } & Record<string, number | string>;

function parseArgs(argv: string[]) {
  const out: Record<string, string | boolean> = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith("--")) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (!next || next.startsWith("--")) {
        out[key] = true;
      } else {
        out[key] = next;
        i++;
      }
    }
  }
  return out;
}

function db(x: number): number {
  return x <= 0 ? -240 : 20 * Math.log10(x);
}

function rowToPatch(row: QueueRow): PatchParams {
  const patch: any = { CON: Number(row.CON), FL: Number(row.FL) };
  for (const op of OP_NAMES) {
    for (const p of ["AR", "D1R", "D2R", "RR", "D1L", "TL", "KS", "MUL", "DT1"]) {
      patch[`${op}_${p}`] = Number(row[`${op}_${p}`]);
    }
  }
  return patch as PatchParams;
}

function loadRenderConfig(): any {
  const p = path.join(RESEARCH, "configs", "render.yaml");
  return parseYaml(fs.readFileSync(p, "utf8"));
}

function loadQueue(manifestPath: string): QueueRow[] {
  const raw = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  if (Array.isArray(raw)) return raw as QueueRow[];
  // Legacy wrapped format { items: [{config_id, params}] }
  if (raw.items) {
    return raw.items.map((it: any) => ({ config_id: it.config_id, ...it.params }));
  }
  throw new Error("unrecognised manifest format");
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help || args.h) {
    console.log(
      "Usage: node --import tsx render_corpus_audio.ts --shard i/N [--limit K] " +
        "[--mode probe|final] [--probe-only] [--gain G] [--manifest path] [--force]",
    );
    process.exit(0);
  }
  const manifestPath = String(args.manifest ?? path.join(RESEARCH, "artifacts", "render_queue.json"));
  const shard = String(args.shard ?? "0/1");
  let mode = String(args.mode ?? "final");
  if (args["probe-only"]) mode = "probe";
  const outDir = String(args.outDir ?? args["out-dir"] ?? path.join(RESEARCH, "scratch", "audio"));
  const statsOut = String(
    args.statsOut ??
      args["stats-out"] ??
      path.join(RESEARCH, "scratch", "render_stats.jsonl")
  );
  const force = Boolean(args.force);
  const limit = args.limit != null ? parseInt(String(args.limit), 10) : null;
  const gainArg = args.gain != null ? parseFloat(String(args.gain)) : null;

  if (!fs.existsSync(manifestPath)) {
    console.error("missing --manifest", manifestPath);
    process.exit(2);
  }

  const [iStr, nStr] = shard.split("/");
  const shardIndex = parseInt(iStr, 10);
  const shardTotal = parseInt(nStr, 10);
  if (!Number.isInteger(shardIndex) || !Number.isInteger(shardTotal) || shardTotal < 1) {
    throw new Error(`invalid --shard ${shard}`);
  }
  if (shardIndex < 0 || shardIndex >= shardTotal) {
    throw new Error(`shard index ${shardIndex} out of range for N=${shardTotal}`);
  }

  const renderCfg = loadRenderConfig();
  const timing = timingFromRenderYaml(renderCfg);
  const probeGain = renderCfg.gain?.probe_gain ?? 1 / 4096;
  const configuredGlobal = renderCfg.gain?.global_gain;
  let gain: number;
  if (mode === "probe") {
    gain = gainArg ?? probeGain;
  } else {
    gain = gainArg ?? (configuredGlobal != null ? Number(configuredGlobal) : NaN);
    if (!(gain > 0)) {
      throw new Error(
        "final mode requires --gain G or render.yaml gain.global_gain " +
          "(set after the probe / render-gain pass)",
      );
    }
  }

  // Optional config_hash from sibling provenance / index
  let configHash = "unknown";
  const indexPath = path.join(RESEARCH, "artifacts", "render_index.json");
  if (fs.existsSync(indexPath)) {
    configHash = JSON.parse(fs.readFileSync(indexPath, "utf8")).config_hash ?? configHash;
  }

  const aud = renderCfg.audibility ?? {};
  const peakThresh = aud.peak_dbfs_threshold ?? -60;
  const rmsThresh = aud.rms_dbfs_threshold ?? -70;
  const minDur = aud.min_audible_duration_s ?? 0.05;
  const prefixLen = renderCfg.output?.shard_prefix_len ?? 2;

  // Contiguous shards over config_id-sorted queue (stable resume boundaries).
  let items = loadQueue(manifestPath)
    .slice()
    .sort((a, b) => (a.config_id < b.config_id ? -1 : a.config_id > b.config_id ? 1 : 0));
  const shardSize = Math.ceil(items.length / shardTotal);
  const shardStart = shardIndex * shardSize;
  items = items.slice(shardStart, shardStart + shardSize);
  if (limit != null) items = items.slice(0, limit);

  fs.mkdirSync(outDir, { recursive: true });
  fs.mkdirSync(path.dirname(statsOut), { recursive: true });
  const statsFh = fs.openSync(statsOut, "w");

  const peaks: number[] = [];
  let written = 0;
  let skipped = 0;
  let clipped = 0;
  let audibleN = 0;
  const t0 = Date.now();

  console.error(
    `STAGE_START stage=render_ts shard=${shardIndex}/${shardTotal} items=${items.length} mode=${mode}`
  );

  for (const item of items) {
    const rel = path.join(item.config_id.slice(0, prefixLen), `${item.config_id}.wav`);
    const outPath = path.join(outDir, rel);
    const metaPath = outPath.replace(/\.wav$/, ".meta.json");

    if (!force && mode === "final" && fs.existsSync(outPath) && fs.existsSync(metaPath)) {
      skipped++;
      const meta = JSON.parse(fs.readFileSync(metaPath, "utf8"));
      peaks.push(meta.peak);
      fs.writeSync(statsFh, JSON.stringify({ ...meta, config_id: item.config_id, path: rel }) + "\n");
      continue;
    }

    const patch = rowToPatch(item);
    const pcm = renderNote(patch, timing, gain);
    const { peak, rms } = peakRms(pcm);
    peaks.push(peak);
    const hash = pcmSha256(pcm);
    const isClipped = peak > 0.999;
    if (isClipped) clipped++;

    const floor = Math.max(1e-6, peak * 0.01);
    let audibleSamples = 0;
    for (let i = 0; i < pcm.length; i++) {
      if (Math.abs(pcm[i]) >= floor) audibleSamples++;
    }
    const audibleDur = audibleSamples / timing.sampleRate;
    const isAudible =
      db(peak) >= peakThresh && db(rms) >= rmsThresh && audibleDur >= minDur;
    if (isAudible) audibleN++;

    const meta = {
      config_id: item.config_id,
      config_hash: configHash,
      pcm_sha256: hash,
      peak,
      rms,
      peak_dbfs: db(peak),
      rms_dbfs: db(rms),
      audible: isAudible,
      clipped: isClipped,
      gain,
      sample_rate: timing.sampleRate,
      n_samples: pcm.length,
      path: rel,
    };

    if (mode === "final") {
      fs.mkdirSync(path.dirname(outPath), { recursive: true });
      fs.writeFileSync(outPath, encodeWavPcm24(pcm, timing.sampleRate));
      fs.writeFileSync(metaPath, JSON.stringify(meta, null, 2));
      written++;
    } else {
      written++;
    }
    fs.writeSync(statsFh, JSON.stringify(meta) + "\n");
  }

  fs.closeSync(statsFh);
  const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
  console.error(
    `STAGE_DONE stage=render_ts shard=${shardIndex}/${shardTotal} items=${items.length} written=${written} skipped=${skipped} clipped=${clipped} elapsed_s=${elapsed}`
  );

  console.log(
    JSON.stringify({
      shard: `${shardIndex}/${shardTotal}`,
      mode,
      items: items.length,
      written,
      skipped,
      clipped,
      audible: audibleN,
      peaks,
      max_peak: peaks.length ? Math.max(...peaks) : 0,
      gain,
      elapsed_s: Number(elapsed),
    })
  );
}

main();
