"""Family A: hand-crafted timbre descriptors.

Dual loudness paths (raw + EBU R128), Timbre Toolbox-like features via librosa,
HPSS harmonic/percussive ratio, and optional AudioCommons timbral models with a
declared fallback when the unmaintained package cannot be imported.

Inaudible renders are excluded (returned as ``None``) rather than imputed, matching
``features.yaml`` silence policy.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from tqdm import tqdm

from . import logs, provenance
from .paths import (
    AUDIO_STATS,
    CORPUS_PARQUET,
    FEATURES_EXCLUDED_PARQUET,
    FEATURES_PARQUET,
    RENDER_MANIFEST,
    audio_path,
    ensure_dirs,
    load_config,
)

logger = logging.getLogger(__name__)

# Optional AudioCommons. Declared absent rather than blocking the stage.
_TIMBRAL_MODELS = None
_TIMBRAL_IMPORT_ERROR: str | None = None
try:
    import timbral_models as _TIMBRAL_MODELS  # type: ignore
except ImportError as exc:  # pragma: no cover - environment dependent
    _TIMBRAL_IMPORT_ERROR = str(exc)


def _features_cfg() -> dict[str, Any]:
    return load_config("features")


def _render_cfg() -> dict[str, Any]:
    return load_config("render")


def load_audio(path: str | Path, *, target_sr: int | None = None) -> tuple[np.ndarray, int]:
    """Load mono float32 audio from FLAC/WAV via soundfile, optional resample with soxr VHQ."""
    import soundfile as sf

    path = Path(path)
    y, sr = sf.read(str(path), always_2d=False, dtype="float32")
    if y.ndim > 1:
        y = np.mean(y, axis=1).astype(np.float32)
    y = np.asarray(y, dtype=np.float32)
    if target_sr is not None and int(sr) != int(target_sr):
        y = resample_audio(y, int(sr), int(target_sr))
        sr = int(target_sr)
    return y, int(sr)


def resample_audio(y: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    """Resample with soxr VHQ as declared in ``features.yaml``."""
    if sr_in == sr_out:
        return np.asarray(y, dtype=np.float32)
    cfg = _features_cfg().get("resampling", {})
    quality = cfg.get("quality", "VHQ")
    try:
        import soxr

        return soxr.resample(y, sr_in, sr_out, quality=quality).astype(np.float32)
    except ImportError:
        import librosa

        return librosa.resample(y, orig_sr=sr_in, target_sr=sr_out, res_type="soxr_vhq").astype(
            np.float32
        )


def apply_loudness_path(
    y: np.ndarray,
    sr: int,
    path_cfg: dict[str, Any],
) -> tuple[np.ndarray, dict[str, float]]:
    """Return audio for one loudness path plus gain metadata."""
    meta = {
        "lufs": float("nan"),
        "gain_db": 0.0,
        "clipped_gain": 0.0,
    }
    if not path_cfg.get("normalize", False):
        return y, meta

    import pyloudnorm as pyln

    meter = pyln.Meter(sr)
    # Near-silence makes integrated loudness undefined.
    if float(np.max(np.abs(y))) < 1e-8:
        meta["lufs"] = float("-inf")
        return y, meta
    try:
        loudness = float(meter.integrated_loudness(y))
    except Exception:
        meta["lufs"] = float("nan")
        return y, meta
    meta["lufs"] = loudness
    target = float(path_cfg.get("target_lufs", -23.0))
    max_gain_db = float(path_cfg.get("max_gain_db", 40.0))
    gain_db = target - loudness
    clipped = 0.0
    if gain_db > max_gain_db:
        clipped = 1.0
        gain_db = max_gain_db
    meta["gain_db"] = float(gain_db)
    meta["clipped_gain"] = clipped
    gain = 10.0 ** (gain_db / 20.0)
    return (y * gain).astype(np.float32), meta


def is_inaudible(y: np.ndarray, sr: int, cfg: dict[str, Any] | None = None) -> bool:
    """Audibility gate from ``render.yaml`` thresholds measured on PCM."""
    aud = (cfg or _render_cfg()).get("audibility", {})
    peak_thr = float(aud.get("peak_dbfs_threshold", -60.0))
    rms_thr = float(aud.get("rms_dbfs_threshold", -70.0))
    min_dur = float(aud.get("min_audible_duration_s", 0.05))
    if len(y) / sr < min_dur:
        return True
    peak = float(np.max(np.abs(y))) if len(y) else 0.0
    if peak <= 0.0:
        return True
    peak_db = 20.0 * np.log10(peak + 1e-12)
    rms = float(np.sqrt(np.mean(np.square(y))))
    rms_db = 20.0 * np.log10(rms + 1e-12)
    return peak_db < peak_thr or rms_db < rms_thr


def _envelope(y: np.ndarray, frame_length: int, hop_length: int) -> np.ndarray:
    import librosa

    return librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]


def log_attack_time(
    y: np.ndarray,
    sr: int,
    *,
    frame_length: int,
    hop_length: int,
    start_ratio: float,
    stop_ratio: float,
) -> float:
    """Log10 of attack duration in seconds (Timbre Toolbox convention)."""
    env = _envelope(y, frame_length, hop_length)
    if env.size == 0 or float(np.max(env)) <= 0.0:
        return float("nan")
    peak = float(np.max(env))
    start_thr = start_ratio * peak
    stop_thr = stop_ratio * peak
    above_start = np.where(env >= start_thr)[0]
    if above_start.size == 0:
        return float("nan")
    i0 = int(above_start[0])
    after = np.where(env[i0:] >= stop_thr)[0]
    if after.size == 0:
        return float("nan")
    i1 = i0 + int(after[0])
    duration = max((i1 - i0) * hop_length / sr, 1e-6)
    return float(np.log10(duration))


def temporal_centroid(y: np.ndarray, sr: int, *, frame_length: int, hop_length: int) -> float:
    env = _envelope(y, frame_length, hop_length)
    if env.size == 0 or float(np.sum(env)) <= 0.0:
        return float("nan")
    times = np.arange(env.size) * hop_length / sr
    return float(np.sum(times * env) / np.sum(env))


def effective_duration(
    y: np.ndarray,
    sr: int,
    *,
    frame_length: int,
    hop_length: int,
    energy_ratio: float = 0.4,
) -> float:
    """Duration carrying ``energy_ratio`` of cumulative energy."""
    env = _envelope(y, frame_length, hop_length)
    energy = np.square(env)
    total = float(np.sum(energy))
    if total <= 0.0:
        return 0.0
    cum = np.cumsum(energy) / total
    n = int(np.searchsorted(cum, energy_ratio)) + 1
    return float(n * hop_length / sr)


def spectral_flux(S: np.ndarray) -> np.ndarray:
    """Half-wave rectified spectral flux over magnitude frames."""
    if S.shape[1] < 2:
        return np.zeros(max(S.shape[1], 1), dtype=np.float64)
    diff = np.diff(S, axis=1)
    flux = np.sum(np.maximum(diff, 0.0), axis=0)
    return np.concatenate([[0.0], flux])


def spectral_moments(S: np.ndarray, freqs: np.ndarray) -> dict[str, np.ndarray]:
    """Centroid, spread, skewness and kurtosis of the magnitude spectrum."""
    power = np.maximum(S, 0.0)
    total = np.sum(power, axis=0) + 1e-12
    centroid = np.sum(freqs[:, None] * power, axis=0) / total
    centered = freqs[:, None] - centroid[None, :]
    var = np.sum((centered**2) * power, axis=0) / total
    spread = np.sqrt(np.maximum(var, 0.0))
    safe_spread = np.where(spread > 1e-12, spread, 1.0)
    skew = np.sum((centered**3) * power, axis=0) / total / (safe_spread**3)
    kurt = np.sum((centered**4) * power, axis=0) / total / (safe_spread**4)
    return {
        "centroid": centroid,
        "spread": spread,
        "skewness": skew,
        "kurtosis": kurt,
    }


def _stats(prefix: str, values: np.ndarray, stats: list[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    arr = np.asarray(values, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        for s in stats:
            out[f"{prefix}_{s}"] = float("nan")
        return out
    for s in stats:
        if s == "mean":
            out[f"{prefix}_{s}"] = float(np.mean(arr))
        elif s == "std":
            out[f"{prefix}_{s}"] = float(np.std(arr))
        elif s == "median":
            out[f"{prefix}_{s}"] = float(np.median(arr))
        else:
            out[f"{prefix}_{s}"] = float("nan")
    return out


def extract_timbre_toolbox(
    y: np.ndarray,
    sr: int,
    family_cfg: dict[str, Any],
    suffix: str,
) -> dict[str, float]:
    """Timbre Toolbox-like battery implemented with librosa."""
    import librosa
    from scipy import stats as scipy_stats

    tt = family_cfg.get("timbre_toolbox", {})
    n_fft = int(family_cfg.get("n_fft", 2048))
    hop = int(family_cfg.get("hop_length", 512))
    frame = int(family_cfg.get("frame_length", 2048))
    center = bool(family_cfg.get("center", True))
    n_mfcc = int(tt.get("n_mfcc", 20))
    mfcc_stats = list(tt.get("mfcc_stats", ["mean", "std"]))

    feats: dict[str, float] = {}
    S = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop, center=center))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc, n_fft=n_fft, hop_length=hop)
    for i in range(n_mfcc):
        feats.update(_stats(f"mfcc{i+1}{suffix}", mfcc[i], mfcc_stats))

    moments = spectral_moments(S, freqs)
    for name, series in moments.items():
        feats[f"spectral_{name}{suffix}"] = float(np.nanmean(series))

    feats[f"spectral_rolloff{suffix}"] = float(
        np.nanmean(librosa.feature.spectral_rolloff(S=S, sr=sr)[0])
    )
    feats[f"spectral_flatness{suffix}"] = float(np.nanmean(librosa.feature.spectral_flatness(S=S)[0]))
    feats[f"spectral_bandwidth{suffix}"] = float(
        np.nanmean(librosa.feature.spectral_bandwidth(S=S, sr=sr)[0])
    )
    flux = spectral_flux(S)
    feats[f"spectral_flux{suffix}"] = float(np.nanmean(flux))

    # Crest / slope / decrease are cheap extras listed in the config.
    peak = np.max(S, axis=0) + 1e-12
    rms_spec = np.sqrt(np.mean(np.square(S), axis=0)) + 1e-12
    feats[f"spectral_crest{suffix}"] = float(np.nanmean(peak / rms_spec))
    # Spectral slope via linear regression of log-magnitude vs frequency.
    log_mag = np.log(S + 1e-12)
    slopes = []
    for t in range(log_mag.shape[1]):
        slope, _, _, _, _ = scipy_stats.linregress(freqs, log_mag[:, t])
        slopes.append(slope)
    feats[f"spectral_slope{suffix}"] = float(np.nanmean(slopes)) if slopes else float("nan")
    # Spectral decrease (Peeters): weighted relative drop from the first bin.
    k = np.arange(1, S.shape[0])
    decrease = []
    for t in range(S.shape[1]):
        num = np.sum((S[1:, t] - S[0, t]) / k)
        den = np.sum(S[1:, t]) + 1e-12
        decrease.append(num / den)
    feats[f"spectral_decrease{suffix}"] = float(np.nanmean(decrease)) if decrease else float("nan")

    start_r = float(tt.get("attack_start_ratio", 0.02))
    stop_r = float(tt.get("attack_stop_ratio", 0.80))
    feats[f"log_attack_time{suffix}"] = log_attack_time(
        y, sr, frame_length=frame, hop_length=hop, start_ratio=start_r, stop_ratio=stop_r
    )
    feats[f"temporal_centroid{suffix}"] = temporal_centroid(
        y, sr, frame_length=frame, hop_length=hop
    )
    feats[f"effective_duration{suffix}"] = effective_duration(
        y, sr, frame_length=frame, hop_length=hop
    )
    # Release slope: linear fit on the log envelope after the peak.
    env = _envelope(y, frame, hop)
    if env.size > 4 and float(np.max(env)) > 0:
        peak_i = int(np.argmax(env))
        tail = env[peak_i:]
        if tail.size > 2:
            t = np.arange(tail.size) * hop / sr
            slope, _, _, _, _ = scipy_stats.linregress(t, np.log(tail + 1e-12))
            feats[f"release_slope{suffix}"] = float(slope)
        else:
            feats[f"release_slope{suffix}"] = float("nan")
    else:
        feats[f"release_slope{suffix}"] = float("nan")
    feats[f"zero_crossing_rate{suffix}"] = float(
        np.nanmean(librosa.feature.zero_crossing_rate(y, frame_length=frame, hop_length=hop)[0])
    )

    # Harmonic descriptors (best-effort; undefined on noise-like signals).
    try:
        f0 = librosa.yin(y, fmin=50, fmax=2000, sr=sr, frame_length=frame)
        f0 = f0[np.isfinite(f0) & (f0 > 0)]
        feats[f"f0_median{suffix}"] = float(np.median(f0)) if f0.size else float("nan")
    except Exception:
        feats[f"f0_median{suffix}"] = float("nan")

    # Lightweight placeholders kept for schema stability when full harmonic analysis fails.
    feats.setdefault(f"inharmonicity{suffix}", float("nan"))
    feats.setdefault(f"odd_even_ratio{suffix}", float("nan"))
    feats.setdefault(f"tristimulus_1{suffix}", float("nan"))
    feats.setdefault(f"tristimulus_2{suffix}", float("nan"))
    feats.setdefault(f"tristimulus_3{suffix}", float("nan"))

    if np.isfinite(feats[f"f0_median{suffix}"]) and feats[f"f0_median{suffix}"] > 0:
        f0_med = feats[f"f0_median{suffix}"]
        # Crude harmonic energy ratios on the mean spectrum.
        mean_S = np.mean(S, axis=1)
        harm_amps = []
        for h in range(1, 11):
            target = h * f0_med
            bin_i = int(np.argmin(np.abs(freqs - target)))
            harm_amps.append(float(mean_S[bin_i]))
        harm = np.asarray(harm_amps)
        if harm.sum() > 0:
            odd = harm[0::2].sum()
            even = harm[1::2].sum()
            feats[f"odd_even_ratio{suffix}"] = float(odd / (even + 1e-12))
            feats[f"tristimulus_1{suffix}"] = float(harm[0] / harm.sum())
            feats[f"tristimulus_2{suffix}"] = float(harm[1:4].sum() / harm.sum())
            feats[f"tristimulus_3{suffix}"] = float(harm[4:].sum() / harm.sum())
            # Partial inharmonicity proxy: deviation of peaks near harmonic bins.
            feats[f"inharmonicity{suffix}"] = float(
                np.mean(np.abs(np.diff(harm) / (harm[:-1] + 1e-12)))
            )

    return feats


def extract_hpss(
    y: np.ndarray,
    sr: int,
    family_cfg: dict[str, Any],
    suffix: str,
) -> dict[str, float]:
    """Harmonic/percussive energy ratio via HPSS (Driedger et al.)."""
    hpss_cfg = family_cfg.get("hpss", {})
    if not hpss_cfg.get("enabled", True):
        return {}
    import librosa

    margin = float(hpss_cfg.get("margin", 1.0))
    kernel = int(hpss_cfg.get("kernel_size", 31))
    y_h, y_p = librosa.effects.hpss(y, margin=margin, kernel_size=kernel)
    e_h = float(np.sum(np.square(y_h)))
    e_p = float(np.sum(np.square(y_p)))
    return {
        f"hpss_harmonic_energy{suffix}": e_h,
        f"hpss_percussive_energy{suffix}": e_p,
        f"hpss_harmonic_percussive_ratio{suffix}": float(e_h / (e_p + 1e-12)),
    }


def extract_audiocommons(path: Path, family_cfg: dict[str, Any], suffix: str) -> dict[str, Any]:
    """AudioCommons timbral models with declared fallback flag."""
    ac = family_cfg.get("audiocommons", {})
    out: dict[str, Any] = {
        f"audiocommons_available{suffix}": 0.0,
        f"audiocommons_fallback{suffix}": 1.0,
    }
    if not ac.get("enabled", True):
        return out
    models = [m for m in ac.get("models", []) if m not in set(ac.get("excluded_models", []))]
    for name in models:
        out[f"ac_{name}{suffix}"] = float("nan")

    if _TIMBRAL_MODELS is None:
        logger.warning(
            "timbral_models unavailable (%s); AudioCommons features skipped (declared fallback)",
            _TIMBRAL_IMPORT_ERROR,
        )
        return out

    out[f"audiocommons_available{suffix}"] = 1.0
    out[f"audiocommons_fallback{suffix}"] = 0.0
    extractors = {
        "brightness": "timbral_brightness",
        "hardness": "timbral_hardness",
        "depth": "timbral_depth",
        "roughness": "timbral_roughness",
        "warmth": "timbral_warmth",
        "sharpness": "timbral_sharpness",
        "booming": "timbral_booming",
    }
    for name in models:
        fn_name = extractors.get(name)
        if fn_name is None or not hasattr(_TIMBRAL_MODELS, fn_name):
            continue
        try:
            value = getattr(_TIMBRAL_MODELS, fn_name)(str(path))
            out[f"ac_{name}{suffix}"] = float(value)
        except Exception as exc:  # pragma: no cover - model-specific failures
            logger.debug("AudioCommons %s failed on %s: %s", name, path.name, exc)
            if ac.get("on_failure", "fallback") == "fail":
                raise
    return out


def extract_one(path: str | Path, cfg: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Extract Family A features for one audio file.

    Returns ``None`` when the render is inaudible (exclude policy).
    """
    cfg = cfg or _features_cfg()
    path = Path(path)
    family = cfg.get("family_a", {})
    target_sr = int(family.get("sample_rate", 44100))
    y, sr = load_audio(path, target_sr=target_sr)

    if is_inaudible(y, sr):
        return None

    row: dict[str, Any] = {
        "audio_path": str(path),
        "sample_rate": sr,
        "n_samples": int(len(y)),
        "audiocommons_import_error": _TIMBRAL_IMPORT_ERROR or "",
    }

    for path_cfg in cfg.get("loudness", {}).get("paths", []):
        name = path_cfg["name"]
        suffix = f"_{name}"
        y_path, meta = apply_loudness_path(y, sr, path_cfg)
        row[f"loudness_lufs{suffix}"] = meta["lufs"]
        row[f"loudness_gain_db{suffix}"] = meta["gain_db"]
        row[f"loudness_gain_clipped{suffix}"] = meta["clipped_gain"]
        row.update(extract_timbre_toolbox(y_path, sr, family, suffix))
        row.update(extract_hpss(y_path, sr, family, suffix))
        # AudioCommons reads from file; only meaningful on the raw path once.
        if name == "raw":
            row.update(extract_audiocommons(path, family, suffix))
        else:
            # Mirror availability flags with NaN features for schema stability.
            ac = family.get("audiocommons", {})
            row[f"audiocommons_available{suffix}"] = row.get("audiocommons_available_raw", 0.0)
            row[f"audiocommons_fallback{suffix}"] = row.get("audiocommons_fallback_raw", 1.0)
            for model in ac.get("models", []):
                if model in set(ac.get("excluded_models", [])):
                    continue
                row[f"ac_{model}{suffix}"] = float("nan")

    return row


def decorrelate(
    df: pd.DataFrame,
    *,
    threshold: float | None = None,
    method: str = "pearson",
    protected: set[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Drop Family A columns with absolute correlation above threshold.

    Returns ``(reduced_df, drop_trace)`` where ``drop_trace`` records which column
    was removed and which retained column it was correlated with.
    """
    cfg = _features_cfg().get("decorrelation", {})
    if not cfg.get("enabled", True):
        return df, pd.DataFrame(columns=["dropped", "kept", "abs_corr"])

    thr = float(threshold if threshold is not None else cfg.get("threshold", 0.9))
    method = cfg.get("method", method)
    protected = protected or {
        "config_id",
        "core_id",
        "audio_path",
        "sample_rate",
        "n_samples",
        "audiocommons_import_error",
        "excluded",
        "reason",
    }

    numeric = [
        c
        for c in df.columns
        if c not in protected and pd.api.types.is_numeric_dtype(df[c])
    ]
    if len(numeric) < 2:
        return df, pd.DataFrame(columns=["dropped", "kept", "abs_corr"])

    corr = df[numeric].corr(method=method).abs()
    drop: list[str] = []
    trace: list[dict[str, Any]] = []
    remaining = list(numeric)
    # Greedy: for each pair above threshold, drop the later column (stable order).
    for i, a in enumerate(numeric):
        if a in drop:
            continue
        for b in numeric[i + 1 :]:
            if b in drop:
                continue
            r = float(corr.loc[a, b])
            if r > thr:
                drop.append(b)
                remaining = [c for c in remaining if c != b]
                trace.append({"dropped": b, "kept": a, "abs_corr": r})

    kept_cols = [c for c in df.columns if c not in drop]
    return df[kept_cols].copy(), pd.DataFrame(trace)


def _config_ids_to_process(limit: int | None) -> pd.DataFrame:
    """Resolve the list of configurations with audio, preferring the render manifest."""
    if RENDER_MANIFEST.exists():
        manifest = pd.read_parquet(RENDER_MANIFEST)
        if "is_audible" in manifest.columns:
            manifest = manifest[manifest["is_audible"].fillna(True)]
        cols = [c for c in ("config_id", "core_id", "audio_path") if c in manifest.columns]
        out = manifest[cols].drop_duplicates("config_id")
    elif CORPUS_PARQUET.exists():
        corpus = pd.read_parquet(CORPUS_PARQUET)
        from .corpus import unique_configs

        configs = unique_configs(corpus)
        out = configs[["config_id", "core_id"]].copy()
        out["audio_path"] = out["config_id"].map(lambda cid: str(audio_path(cid)))
    else:
        raise FileNotFoundError(
            f"missing {RENDER_MANIFEST} and {CORPUS_PARQUET}; build corpus/render first"
        )

    if AUDIO_STATS.exists():
        stats = pd.read_parquet(AUDIO_STATS)
        if "is_audible" in stats.columns:
            audible = set(stats.loc[stats["is_audible"], "config_id"].astype(str))
            out = out[out["config_id"].astype(str).isin(audible)]

    out = out.reset_index(drop=True)
    if limit is not None:
        out = out.head(int(limit))
    return out


def extract_corpus(limit: int | None = None) -> pd.DataFrame:
    """Batch-extract Family A features with parquet checkpointing.

    Already-processed ``config_id`` values are skipped so the stage is resumable.
    """
    ensure_dirs()
    cfg = _features_cfg()
    jobs = _config_ids_to_process(limit)

    done: set[str] = set()
    frames: list[pd.DataFrame] = []
    if FEATURES_PARQUET.exists():
        existing = pd.read_parquet(FEATURES_PARQUET)
        done = set(existing["config_id"].astype(str))
        frames.append(existing)

    excluded_rows: list[dict[str, Any]] = []
    if FEATURES_EXCLUDED_PARQUET.exists():
        excluded_rows.extend(pd.read_parquet(FEATURES_EXCLUDED_PARQUET).to_dict(orient="records"))

    pending = jobs[~jobs["config_id"].astype(str).isin(done)]
    logger.info("Family A: %d pending of %d (limit=%s)", len(pending), len(jobs), limit)

    with logs.stage("descriptors", pending=len(pending), total=len(jobs)) as done_fields:
        batch: list[dict[str, Any]] = []
        checkpoint_every = 256
        for _, job in tqdm(pending.iterrows(), total=len(pending), desc="descriptors"):
            cid = str(job["config_id"])
            path = Path(job["audio_path"]) if "audio_path" in job and pd.notna(job["audio_path"]) else audio_path(cid)
            if not path.exists():
                excluded_rows.append(
                    {"config_id": cid, "reason": "missing_audio", "audio_path": str(path)}
                )
                continue
            try:
                feats = extract_one(path, cfg)
            except Exception as exc:
                logger.exception("descriptor failure for %s", cid)
                excluded_rows.append(
                    {"config_id": cid, "reason": f"error:{type(exc).__name__}", "audio_path": str(path)}
                )
                continue
            if feats is None:
                excluded_rows.append(
                    {"config_id": cid, "reason": "inaudible", "audio_path": str(path)}
                )
                continue
            feats["config_id"] = cid
            if "core_id" in job and pd.notna(job["core_id"]):
                feats["core_id"] = job["core_id"]
            batch.append(feats)
            if len(batch) >= checkpoint_every:
                frames.append(pd.DataFrame(batch))
                pd.concat(frames, ignore_index=True).to_parquet(FEATURES_PARQUET, index=False)
                batch.clear()

        if batch:
            frames.append(pd.DataFrame(batch))

        if not frames:
            result = pd.DataFrame()
        else:
            result = pd.concat(frames, ignore_index=True)
            result, drop_trace = decorrelate(result)
            if len(drop_trace):
                drop_path = FEATURES_PARQUET.with_name("features_decorrelation_trace.parquet")
                drop_trace.to_parquet(drop_path, index=False)
            result.to_parquet(FEATURES_PARQUET, index=False)

        if excluded_rows:
            pd.DataFrame(excluded_rows).drop_duplicates("config_id", keep="last").to_parquet(
                FEATURES_EXCLUDED_PARQUET, index=False
            )

        provenance.write(
            FEATURES_PARQUET,
            stage="descriptors",
            inputs={"n_jobs": len(jobs)},
            params={
                "feature_version": cfg.get("feature_version"),
                "audiocommons_available": _TIMBRAL_MODELS is not None,
                "audiocommons_import_error": _TIMBRAL_IMPORT_ERROR,
            },
            metrics={
                "n_features_rows": int(len(result)),
                "n_excluded": len(excluded_rows),
                "n_columns": int(result.shape[1]) if len(result) else 0,
            },
            seeds={"features": int(cfg.get("determinism", {}).get("seed", 42))},
        )
        done_fields["rows"] = len(result)
        done_fields["excluded"] = len(excluded_rows)

    return result
