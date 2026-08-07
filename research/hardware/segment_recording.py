"""Locate sync markers in a continuous hardware take and cut per-test segments.

The validation VGM begins (and ends) with an asymmetric pulse train that is easy
to find by cross-correlation. Once the leading sync is locked, segment sample
offsets from ``manifest.json`` map onto the recording; comparing leading vs
trailing sync estimates accumulated player/sound-card drift.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from dafm_audio.paths import HW_DIR, ensure_dirs, load_config


def _mono_mean(audio: np.ndarray) -> np.ndarray:
    audio = np.asarray(audio, dtype=np.float64)
    if audio.ndim == 1:
        return audio
    return 0.5 * (audio[:, 0] + audio[:, 1])


def synthesize_sync_template(cfg: dict[str, Any], sample_rate: int) -> np.ndarray:
    """Idealised sync pulse train (rectified tone bursts) matching the VGM timing.

    Not a chip-accurate waveform: only the envelope timing matters for locating
    the marker by cross-correlation against a real recording.
    """
    timing = cfg["timing"]
    pulse_n = int(round(timing["sync_pulse_s"] * sample_rate))
    gaps = [int(round(g * sample_rate)) for g in timing["sync_gaps_s"]]
    n_pulses = int(timing["sync_pulse_count"])

    # Tone inside each pulse so correlation is sharper than a rectangle alone.
    t = np.arange(pulse_n, dtype=np.float64) / sample_rate
    tone = 0.5 * np.sin(2 * np.pi * 440.0 * t)
    env = np.hanning(pulse_n)
    burst = tone * env

    parts: list[np.ndarray] = []
    for i in range(n_pulses):
        parts.append(burst)
        if i < len(gaps):
            parts.append(np.zeros(gaps[i], dtype=np.float64))
    return np.concatenate(parts) if parts else np.zeros(0)


def find_sync_offset(
    mono: np.ndarray,
    template: np.ndarray,
    *,
    search_start: int = 0,
    search_end: int | None = None,
) -> dict[str, Any]:
    """Return the sample index of the best normalised cross-correlation peak."""
    if search_end is None:
        search_end = len(mono)
    search_start = max(0, search_start)
    search_end = min(len(mono), search_end)
    region = mono[search_start:search_end]
    if len(region) < len(template):
        raise ValueError("search region shorter than sync template")

    # Normalised correlation via FFT convolution with reversed template.
    tpl = template - template.mean()
    tpl = tpl / (np.linalg.norm(tpl) + 1e-12)
    from numpy.fft import irfft, rfft

    n = len(region) + len(tpl) - 1
    nfft = 1 << int(np.ceil(np.log2(n)))
    corr = irfft(rfft(region, nfft) * rfft(tpl[::-1], nfft), nfft)[: n]
    # Energy normalisation of the moving window.
    win = np.ones(len(tpl), dtype=np.float64)
    energy = np.sqrt(np.convolve(region**2, win, mode="valid") + 1e-12)
    # corr 'full' alignment: peak index corresponds to start of template in region
    # when using correlate(mode='valid') semantics. Trim to valid length.
    valid = corr[len(tpl) - 1 : len(tpl) - 1 + len(energy)]
    normed = valid / energy
    peak_i = int(np.argmax(normed))
    return {
        "offset": search_start + peak_i,
        "correlation": float(normed[peak_i]),
        "search_start": search_start,
        "search_end": search_end,
    }


def estimate_drift(
    leading_offset: int,
    trailing_offset: int,
    *,
    expected_trailing: int,
    sample_rate: int,
) -> dict[str, Any]:
    """Compare observed trailing sync location to the manifest expectation."""
    observed_span = trailing_offset - leading_offset
    expected_span = expected_trailing  # relative to leading sync start in VGM
    sample_error = observed_span - expected_span
    return {
        "observed_span_samples": int(observed_span),
        "expected_span_samples": int(expected_span),
        "error_samples": int(sample_error),
        "error_s": sample_error / sample_rate,
        "ppm": (sample_error / max(expected_span, 1)) * 1e6,
    }


def segment_recording(
    audio_path: Path,
    manifest_path: Path,
    *,
    out_dir: Path | None = None,
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Cut per-test WAVs from a continuous take using the VGM manifest."""
    import soundfile as sf

    cfg = cfg or load_config("hardware_validation")
    ensure_dirs()
    out_dir = out_dir or (HW_DIR / "segments")
    out_dir.mkdir(parents=True, exist_ok=True)

    with manifest_path.open("r", encoding="utf-8") as fh:
        manifest = json.load(fh)

    audio, sr = sf.read(str(audio_path), dtype="float64", always_2d=True)
    mono = _mono_mean(audio)
    vgm_sr = int(manifest["wait_sample_rate"])

    # Resample recording onto the VGM wait grid if needed (simple linear; Phase 1).
    if sr != vgm_sr:
        duration = len(mono) / sr
        n_new = int(round(duration * vgm_sr))
        mono = np.interp(
            np.linspace(0, len(mono) - 1, n_new),
            np.arange(len(mono)),
            mono,
        )
        sr = vgm_sr

    template = synthesize_sync_template(cfg, sr)
    # Leading sync: search the first ~30 s (plus configured lead-in headroom).
    lead_search_end = min(len(mono), int(30 * sr))
    leading = find_sync_offset(mono, template, search_start=0, search_end=lead_search_end)

    # Trailing sync: search the last ~30 s.
    trail_search_start = max(0, len(mono) - int(30 * sr))
    trailing = find_sync_offset(
        mono, template, search_start=trail_search_start, search_end=len(mono)
    )

    sync_events = [e for e in manifest["events"] if e["kind"] == "sync_start"]
    if len(sync_events) < 2:
        raise ValueError("manifest lacks leading and trailing sync_start events")
    expected_trailing_rel = sync_events[-1]["sample"] - sync_events[0]["sample"]
    drift = estimate_drift(
        leading["offset"],
        trailing["offset"],
        expected_trailing=expected_trailing_rel,
        sample_rate=sr,
    )

    # Linear time map from VGM samples to recording samples.
    scale = (trailing["offset"] - leading["offset"]) / max(expected_trailing_rel, 1)
    origin = leading["offset"] - sync_events[0]["sample"] * scale

    written = []
    for seg in manifest["segments"]:
        if "end_sample" not in seg:
            continue
        start = int(round(origin + seg["start_sample"] * scale))
        end = int(round(origin + seg["end_sample"] * scale))
        start = max(0, min(len(mono), start))
        end = max(0, min(len(mono), end))
        if end <= start:
            continue
        clip = mono[start:end].astype(np.float32)
        out_path = out_dir / f"{seg['test_id']}.wav"
        sf.write(str(out_path), clip, sr, subtype="PCM_24")
        written.append(
            {
                "test_id": seg["test_id"],
                "path": str(out_path),
                "start": start,
                "end": end,
                "n_samples": int(end - start),
                "placeholder": bool(seg.get("placeholder", False)),
            }
        )

    report = {
        "audio": str(audio_path),
        "manifest": str(manifest_path),
        "sample_rate": sr,
        "leading_sync": leading,
        "trailing_sync": trailing,
        "drift": drift,
        "scale": scale,
        "segments_written": written,
    }
    report_path = out_dir / "segmentation_report.json"
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Segment a hardware validation recording")
    parser.add_argument("--audio", type=Path, required=True, help="Continuous take WAV")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=HW_DIR / "manifest.json",
        help="Battery manifest.json",
    )
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    report = segment_recording(args.audio, args.manifest, out_dir=args.out_dir)
    print(json.dumps({"drift": report["drift"], "n_segments": len(report["segments_written"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
