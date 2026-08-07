# Timbre similarity in FM synthesis — operator runbook

English-only research package. Everything for this study lives under `research/`
(code) and `TISMIR-SoundSimilarity-LaTeX/` (paper). The only inheritance from the
rest of the repository is `data/processed/all_instruments_final.csv` and the
YM2612 emulator core used as a measuring instrument.

## Machines

| Profile | Hardware | Env var |
|---------|----------|---------|
| `a` (default) | 40 GB RAM, RTX 3050 Ti 4 GB | `DAFM_MACHINE=a` |
| `b` | 64 GB RAM, RTX 5060 Ti 16 GB (Blackwell → CUDA 12.8+) | `DAFM_MACHINE=b` |

Embeddings (Family B) run on machine B. Render shards can be split across both.

## Install

```bash
cd research
python -m pip install -e ".[dev]"
# Machine B embeddings:
#   pip install -e ".[machine-b,embeddings]" --index-url https://download.pytorch.org/whl/cu128
make install-node
make doctor
```

## Runbook (copy-paste)

Each step has a **gate**. Green → continue. Red → stop and fix.

### 1. Where am I?

```bash
make status
```

### 2. Build the corpus (either machine, ~1 min)

```bash
make corpus
make check-corpus
```

**Produces:** `artifacts/corpus_v1.parquet`, splits, TL-variant groups, stats.  
**Expect:** 93832 presets; unique `config_id` count after DT1 canonicalisation and
effective-parameter dedup (lower than the naive 38158).  
**Gate:** `make check-corpus` prints `VERDICT: GREEN`.

### 3. Render queue

```bash
make render-manifest
```

**Produces:** `artifacts/render_queue.json`, `render_manifest.parquet`.

### 4. Global gain probe (either machine)

```bash
make render-gain
# or smoke:  python -m dafm_audio.cli render-gain --limit 50
```

**Produces:** `artifacts/global_gain.json` — one gain for the whole corpus.  
**Do not** normalise per file (E1 needs relative level).

### 5. Render audio (CPU; both machines in parallel on disjoint shards)

```bash
# Machine A (shards 0–7 by default in machines.yaml):
set DAFM_MACHINE=a
make render SHARD=0/16
# … repeat for 1/16 .. 7/16

# Machine B:
set DAFM_MACHINE=b
make render SHARD=8/16
```

Smoke:

```bash
make render SHARD=0/1 LIMIT=10
make encode-flac LIMIT=10
make check-render
```

**Produces:** `scratch/audio/<pp>/<config_id>.wav` (+ `.meta.json`), then FLAC.  
**Disk:** ~8.5 GB FLAC for the full corpus. **Never sync audio between machines** —
regenerate from the manifest; PCM SHA256 is the check.  
**Gate:** `make check-render` → GREEN (zero clipping, hashes present).

If you kill a shard mid-way: re-run the same `SHARD=`; existing files are skipped
unless `--force`.

### 6. Features

```bash
# Family A (CPU, either machine):
python -m dafm_audio.cli features --family a

# Family B embeddings (machine B):
set DAFM_MACHINE=b
python -m dafm_audio.cli features --family b

make check-features
```

**Produces:** `artifacts/features.parquet` (+ embeddings parquet).  
**Gate:** no NaNs in kept columns.

### 7. Spaces + evaluation

```bash
make spaces
make check-spaces
make evaluate
make check-eval
```

E1 alone (cheap, central figure):

```bash
python -m dafm_audio.cli evaluate --experiment E1
```

### 8. Morph (Capacity A; no audio required)

```bash
make morph
```

### 9. Hardware validation VGM

```bash
make hw-vgm
# Play artifacts/hw/validation_battery_v1.vgm on the Kasser instrument (8 MHz).
# Record one continuous 24-bit WAV (no limiter), then:
python hardware/segment_recording.py --wav path/to/recording.wav
python hardware/compare_hw_emu.py
```

Diagnostic block can be recorded before Phase 2. Corpus medoids need features.

### 10. HuggingFace export + figures + paper

```bash
make hf-export
make figures
cd ../TISMIR-SoundSimilarity-LaTeX && make
```

## Tests / CI

```bash
make test
make smoke          # 10-preset end-to-end (needs Node)
```

## Sentinel logs

Long stages emit lines like:

```text
STAGE_DONE stage=render shard=3/16 items=4770 elapsed_s=612
```

Logs live under `scratch/logs/`.
