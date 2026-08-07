"""Build the hardware-validation VGM (version 1.61) and its manifest.

The VGM is the single source of truth for the command stream: the same file
drives the real YM2612/YM3438 path and ``vgm_player.ts`` through the emulator.
Timing waits are in samples at 44100 Hz by VGM specification, independent of the
chip clock stored in the header (8 MHz for the Kasser instrument).

Corpus-block slots (10 medoids / PCA extremes) are Phase-2 placeholders: the
diagnostic block can be generated and recorded immediately.
"""

from __future__ import annotations

import argparse
import json
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dafm_audio.chip import (
    OPERATOR_REGISTER_OFFSETS,
    REG_AMS_EN_D1R,
    REG_BLOCK_FNUM_HIGH,
    REG_DAC_ENABLE,
    REG_D1L_RR,
    REG_D2R,
    REG_DT1_MUL,
    REG_FB_ALGORITHM,
    REG_FNUM_LOW,
    REG_KEY_ON_OFF,
    REG_KS_AR,
    REG_LFO,
    REG_MODE,
    REG_PAN_AMS_PMS,
    REG_SSG_EG,
    REG_TL,
    fnum_block,
)
from dafm_audio.paths import HARDWARE_DIR, HW_DIR, ensure_dirs, load_config

# VGM command bytes
CMD_YM2612_PORT0 = 0x52
CMD_YM2612_PORT1 = 0x53
CMD_WAIT_N = 0x61
CMD_WAIT_735 = 0x62
CMD_WAIT_882 = 0x63
CMD_END = 0x66


@dataclass
class VgmBuilder:
    """Accumulate YM2612 port-0 writes and sample-accurate waits."""

    sample_rate: int = 44100
    data: bytearray = field(default_factory=bytearray)
    sample_cursor: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)

    def write_reg(self, addr: int, value: int, port: int = 0) -> None:
        cmd = CMD_YM2612_PORT0 if port == 0 else CMD_YM2612_PORT1
        self.data.append(cmd)
        self.data.append(addr & 0xFF)
        self.data.append(value & 0xFF)

    def wait_samples(self, n: int) -> None:
        n = int(n)
        if n <= 0:
            return
        self.sample_cursor += n
        while n > 0:
            if n == 735:
                self.data.append(CMD_WAIT_735)
                n = 0
            elif n == 882:
                self.data.append(CMD_WAIT_882)
                n = 0
            elif n <= 16:
                self.data.append(0x70 | (n - 1))
                n = 0
            else:
                chunk = min(n, 65535)
                self.data.append(CMD_WAIT_N)
                self.data.append(chunk & 0xFF)
                self.data.append((chunk >> 8) & 0xFF)
                n -= chunk

    def wait_seconds(self, seconds: float) -> None:
        self.wait_samples(int(round(seconds * self.sample_rate)))

    def mark(self, kind: str, **fields: Any) -> None:
        self.events.append({"kind": kind, "sample": self.sample_cursor, **fields})


def _op_from_dict(d: dict[str, Any]) -> dict[str, int]:
    return {
        "tl": int(d.get("tl", 127)),
        "mul": int(d.get("mul", 1)),
        "ar": int(d.get("ar", 31)),
        "d1r": int(d.get("d1r", 0)),
        "d2r": int(d.get("d2r", 0)),
        "rr": int(d.get("rr", 15)),
        "d1l": int(d.get("d1l", 0)),
        "ks": int(d.get("ks", 0)),
        "dt1": int(d.get("dt1", 0)),
    }


def _default_silent_ops() -> list[dict[str, int]]:
    return [_op_from_dict({"tl": 127}) for _ in range(4)]


def resolve_diagnostic(diag: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Resolve base: and fixed_overrides into a concrete static patch description."""
    base_id = diag.get("base")
    if base_id:
        base = resolve_diagnostic(by_id[base_id], by_id)
        out = {
            "id": diag["id"],
            "kind": diag["kind"],
            "description": diag.get("description", ""),
            "algorithm": base["algorithm"],
            "feedback": base["feedback"],
            "operators": [dict(op) for op in base["operators"]],
        }
    else:
        out = {
            "id": diag["id"],
            "kind": diag["kind"],
            "description": diag.get("description", ""),
            "algorithm": int(diag["algorithm"]),
            "feedback": int(diag.get("feedback", 0)),
            "operators": [_op_from_dict(op) for op in diag["operators"]],
        }
    overrides = diag.get("fixed_overrides") or {}
    apply_overrides(out, overrides)
    # Carry sweep metadata through for the builder.
    for key in ("sweep_param", "sweep_values"):
        if key in diag:
            out[key] = diag[key]
    return out


def apply_overrides(patch: dict[str, Any], overrides: dict[str, Any]) -> None:
    for key, value in overrides.items():
        if key == "feedback":
            patch["feedback"] = int(value)
            continue
        if key == "algorithm":
            patch["algorithm"] = int(value)
            continue
        # opN_param with N in 1..4 matching documentation slot order M1,C1,M2,C2
        if key.startswith("op") and "_" in key:
            head, param = key.split("_", 1)
            idx = int(head[2:]) - 1
            patch["operators"][idx][param] = int(value) if not isinstance(value, dict) else value
            continue
        if isinstance(value, dict):
            # envelope_combo style already handled at call site
            continue


def write_chip_defaults(v: VgmBuilder, channel: int = 0) -> None:
    v.write_reg(REG_MODE, 0)
    v.write_reg(REG_DAC_ENABLE, 0)
    v.write_reg(REG_LFO, 0)
    v.write_reg(REG_PAN_AMS_PMS + channel, 0xC0)


def write_patch(v: VgmBuilder, patch: dict[str, Any], channel: int = 0) -> None:
    write_chip_defaults(v, channel)
    alg = int(patch["algorithm"]) & 7
    fb = int(patch["feedback"]) & 7
    v.write_reg(REG_FB_ALGORITHM + channel, (fb << 3) | alg)
    v.write_reg(REG_PAN_AMS_PMS + channel, 0xC0)
    for i, op in enumerate(patch["operators"]):
        off = OPERATOR_REGISTER_OFFSETS[i]
        v.write_reg(REG_DT1_MUL + channel + off, ((op["dt1"] & 7) << 4) | (op["mul"] & 15))
        v.write_reg(REG_TL + channel + off, op["tl"] & 127)
        v.write_reg(REG_KS_AR + channel + off, ((op["ks"] & 3) << 6) | (op["ar"] & 31))
        v.write_reg(REG_AMS_EN_D1R + channel + off, op["d1r"] & 31)
        v.write_reg(REG_D2R + channel + off, op["d2r"] & 31)
        v.write_reg(REG_D1L_RR + channel + off, ((op["d1l"] & 15) << 4) | (op["rr"] & 15))
        v.write_reg(REG_SSG_EG + channel + off, 0)


def note_on(v: VgmBuilder, midi: int, clock_hz: int, channel: int = 0) -> None:
    fnum, block = fnum_block(midi, clock_hz)
    v.write_reg(REG_BLOCK_FNUM_HIGH + channel, (block << 3) | ((fnum >> 8) & 7))
    v.write_reg(REG_FNUM_LOW + channel, fnum & 0xFF)
    v.write_reg(REG_KEY_ON_OFF, 0xF0 | (channel & 7))


def note_off(v: VgmBuilder, channel: int = 0) -> None:
    v.write_reg(REG_KEY_ON_OFF, channel & 7)


def sync_pulse_patch() -> dict[str, Any]:
    """Loud short sine (alg 7, carrier TL=0) used as a sync marker."""
    ops = _default_silent_ops()
    ops[3] = _op_from_dict({"tl": 0, "mul": 1, "ar": 31, "rr": 15})
    return {"algorithm": 7, "feedback": 0, "operators": ops}


def emit_sync(v: VgmBuilder, cfg: dict[str, Any], clock_hz: int, midi: int = 60) -> None:
    timing = cfg["timing"]
    v.mark("sync_start")
    v.wait_seconds(timing["sync_lead_in_silence_s"])
    patch = sync_pulse_patch()
    gaps = list(timing["sync_gaps_s"])
    for i in range(int(timing["sync_pulse_count"])):
        write_patch(v, patch)
        note_on(v, midi, clock_hz)
        v.mark("sync_pulse", index=i)
        v.wait_seconds(timing["sync_pulse_s"])
        note_off(v)
        if i < len(gaps):
            v.wait_seconds(gaps[i])
    v.wait_seconds(timing["sync_lead_out_silence_s"])
    v.mark("sync_end")


def emit_static_note(
    v: VgmBuilder,
    patch: dict[str, Any],
    *,
    clock_hz: int,
    sustain_s: float,
    release_s: float,
    midi: int,
    test_id: str,
) -> None:
    v.mark("test_start", test_id=test_id, test_kind="static")
    write_patch(v, patch)
    note_on(v, midi, clock_hz)
    v.wait_seconds(sustain_s)
    note_off(v)
    v.wait_seconds(release_s)
    v.mark("test_end", test_id=test_id)


def emit_sweep(
    v: VgmBuilder,
    patch: dict[str, Any],
    *,
    clock_hz: int,
    step_s: float,
    release_s: float,
    midi: int,
    test_id: str,
    sweep_param: str,
    sweep_values: list[Any],
) -> None:
    v.mark("test_start", test_id=test_id, test_kind="sweep", sweep_param=sweep_param)
    for step_i, value in enumerate(sweep_values):
        step_patch = {
            "algorithm": patch["algorithm"],
            "feedback": patch["feedback"],
            "operators": [dict(op) for op in patch["operators"]],
        }
        if isinstance(value, dict):
            apply_overrides(step_patch, value)
        else:
            apply_overrides(step_patch, {sweep_param: value})
        write_patch(v, step_patch)
        note_on(v, midi, clock_hz)
        v.mark("sweep_step", test_id=test_id, index=step_i, value=value)
        v.wait_seconds(step_s)
        note_off(v)
        v.wait_seconds(min(release_s, 0.15))
    v.mark("test_end", test_id=test_id)


def emit_corpus_placeholder(
    v: VgmBuilder,
    *,
    index: int,
    clock_hz: int,
    sustain_s: float,
    release_s: float,
    midi: int,
) -> None:
    """Phase-2 placeholder: silence-length slot reserved for a real medoid later."""
    test_id = f"c{index:02d}_placeholder"
    v.mark("test_start", test_id=test_id, test_kind="corpus_placeholder", placeholder=True)
    # Keep timing identical to a static test so the manifest offsets stay valid
    # when Phase 2 fills in the real patch.
    silent = {
        "algorithm": 7,
        "feedback": 0,
        "operators": _default_silent_ops(),
    }
    write_patch(v, silent)
    note_on(v, midi, clock_hz)
    v.wait_seconds(sustain_s)
    note_off(v)
    v.wait_seconds(release_s)
    v.mark("test_end", test_id=test_id, placeholder=True)


def build_gd3(track_name: str) -> bytes:
    """Minimal GD3 tag (UTF-16LE fields) for the track name."""
    def u16(s: str) -> bytes:
        return s.encode("utf-16le") + b"\x00\x00"

    body = b"".join(
        [
            u16(track_name),
            u16(""),  # game EN
            u16(""),  # game JP
            u16(""),  # system EN
            u16(""),  # system JP
            u16("DAFMExplorer"),
            u16(""),  # author JP
            u16("2026"),
            u16("hardware validation battery"),
        ]
    )
    return b"Gd3 " + struct.pack("<II", 0x100, len(body)) + body


def wrap_vgm(
    data: bytes,
    *,
    clock_hz: int,
    header_size: int,
    gd3: bytes,
    total_samples: int,
) -> bytes:
    """Assemble a VGM 1.61 header + data + GD3.

    Offsets in the header are relative to their own field addresses, per the
    VGM specification (eof at 0x04 relative to 0x04, gd3 at 0x14 relative to
    0x14, data at 0x34 relative to 0x34).
    """
    data_offset_rel = header_size - 0x34
    file_size = header_size + len(data) + len(gd3)
    eof_offset = file_size - 4
    gd3_abs = header_size + len(data)
    gd3_offset = gd3_abs - 0x14

    header = bytearray(header_size)
    header[0:4] = b"Vgm "
    struct.pack_into("<I", header, 0x04, eof_offset)
    struct.pack_into("<I", header, 0x08, 0x00000161)  # version 1.61
    struct.pack_into("<I", header, 0x14, gd3_offset)
    struct.pack_into("<I", header, 0x18, total_samples)
    struct.pack_into("<I", header, 0x1C, 0)  # loop samples
    struct.pack_into("<I", header, 0x20, 0)  # rate (0 = use default)
    struct.pack_into("<I", header, 0x2C, clock_hz & 0xFFFFFFFF)
    struct.pack_into("<I", header, 0x34, data_offset_rel)
    return bytes(header) + data + gd3


def build_battery(cfg: dict[str, Any] | None = None) -> tuple[bytes, dict[str, Any]]:
    cfg = cfg or load_config("hardware_validation")
    vgm_cfg = cfg["vgm"]
    timing = cfg["timing"]
    clock_hz = int(vgm_cfg["clock_hz"])
    sr = int(vgm_cfg["wait_sample_rate"])
    midi = 60

    v = VgmBuilder(sample_rate=sr)
    by_id = {d["id"]: d for d in cfg["diagnostics"]}

    emit_sync(v, cfg, clock_hz, midi)

    test_order: list[str] = []
    for diag in cfg["diagnostics"]:
        resolved = resolve_diagnostic(diag, by_id)
        test_order.append(resolved["id"])
        if resolved["kind"] == "static":
            emit_static_note(
                v,
                resolved,
                clock_hz=clock_hz,
                sustain_s=timing["simple_test_sustain_s"],
                release_s=timing["simple_test_release_s"],
                midi=midi,
                test_id=resolved["id"],
            )
        elif resolved["kind"] == "sweep":
            emit_sweep(
                v,
                resolved,
                clock_hz=clock_hz,
                step_s=timing["sweep_step_s"],
                release_s=timing["simple_test_release_s"],
                midi=midi,
                test_id=resolved["id"],
                sweep_param=resolved["sweep_param"],
                sweep_values=list(resolved["sweep_values"]),
            )
        else:
            raise ValueError(f"unknown diagnostic kind: {resolved['kind']}")
        v.wait_seconds(timing["guard_silence_s"])
        v.mark("guard", after=resolved["id"])

    n_corpus = int(cfg["corpus_block"]["n_medoids"]) + int(cfg["corpus_block"]["n_pca_extremes"])
    for i in range(1, n_corpus + 1):
        emit_corpus_placeholder(
            v,
            index=i,
            clock_hz=clock_hz,
            sustain_s=timing["simple_test_sustain_s"],
            release_s=timing["simple_test_release_s"],
            midi=midi,
        )
        test_order.append(f"c{i:02d}_placeholder")
        v.wait_seconds(timing["guard_silence_s"])
        v.mark("guard", after=f"c{i:02d}_placeholder")

    if cfg.get("repeat_first_test_at_end"):
        first = resolve_diagnostic(cfg["diagnostics"][0], by_id)
        emit_static_note(
            v,
            first,
            clock_hz=clock_hz,
            sustain_s=timing["simple_test_sustain_s"],
            release_s=timing["simple_test_release_s"],
            midi=midi,
            test_id=f"{first['id']}__repeat",
        )
        test_order.append(f"{first['id']}__repeat")

    emit_sync(v, cfg, clock_hz, midi)

    v.data.append(CMD_END)
    gd3 = build_gd3(vgm_cfg["gd3_track_name"])
    raw = wrap_vgm(
        bytes(v.data),
        clock_hz=clock_hz,
        header_size=int(vgm_cfg["header_size"]),
        gd3=gd3,
        total_samples=v.sample_cursor,
    )

    segments = []
    for ev in v.events:
        if ev["kind"] == "test_start":
            segments.append(
                {
                    "test_id": ev["test_id"],
                    "kind": ev.get("kind"),
                    "start_sample": ev["sample"],
                    "placeholder": bool(ev.get("placeholder", False)),
                }
            )
        elif ev["kind"] == "test_end" and segments:
            for seg in reversed(segments):
                if seg["test_id"] == ev["test_id"] and "end_sample" not in seg:
                    seg["end_sample"] = ev["sample"]
                    break

    manifest = {
        "battery_version": cfg["battery_version"],
        "clock_hz": clock_hz,
        "wait_sample_rate": sr,
        "total_samples": v.sample_cursor,
        "duration_s": v.sample_cursor / sr,
        "test_order": test_order,
        "segments": segments,
        "events": v.events,
        "diagnostics": [d["id"] for d in cfg["diagnostics"]],
        "corpus_placeholders": n_corpus,
        "notes": {
            "corpus_block": "Phase 2 placeholders; replace after medoids exist",
            "fnum_compensation": False,
        },
    }
    return raw, manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build hardware validation VGM + manifest")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: research/artifacts/hw)",
    )
    args = parser.parse_args(argv)
    ensure_dirs()
    out_dir = args.out_dir or HW_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    raw, manifest = build_battery()
    vgm_path = out_dir / "validation_battery_v1.vgm"
    man_path = out_dir / "manifest.json"
    vgm_path.write_bytes(raw)
    man_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    # Convenience copy under research/hardware/ for the TS player default path.
    HARDWARE_DIR.mkdir(parents=True, exist_ok=True)
    (HARDWARE_DIR / "validation_battery_v1.vgm").write_bytes(raw)
    (HARDWARE_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "vgm": str(vgm_path),
                "manifest": str(man_path),
                "total_samples": manifest["total_samples"],
                "duration_s": manifest["duration_s"],
                "n_tests": len(manifest["test_order"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
