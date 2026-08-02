"""
Extract spoken lines from speaker_script_en.md and synthesize a full narration (MP3).
Usage (repo root or notes folder):
  pip install edge-tts
  python scripts/narrate_speaker_script.py
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "Ludo2026-DAFMExplorer-LaTeX" / "notes" / "speaker_script_en.md"
OUT_DIR = ROOT / "Ludo2026-DAFMExplorer-LaTeX" / "notes" / "audio"
OUT_MP3 = OUT_DIR / "speaker_script_en_narration.mp3"
OUT_TXT = OUT_DIR / "speaker_script_en_narration.txt"

# Natural male EN-US voice (change if you prefer)
VOICE = "en-US-AndrewNeural"
# Slightly slower for conference-style delivery
RATE = "-5%"


def extract_spoken_text(md: str) -> str:
    parts: list[str] = []
    # Capture blockquotes under **Say:** until next **Convey:** or --- or ##
    pattern = re.compile(
        r"\*\*Say:\*\*\s*\n((?:>.*\n)+)",
        re.MULTILINE,
    )
    for m in pattern.finditer(md):
        block = m.group(1)
        lines = []
        for line in block.splitlines():
            line = re.sub(r"^>\s?", "", line)
            # Drop stage directions like *[Click S1]*
            line = re.sub(r"\*\[[^\]]*\]\*", "", line)
            # Italics markers
            line = line.replace("*", "")
            line = line.replace("→", " to ")
            line = line.replace("—", " — ")
            line = re.sub(r"\s+", " ", line).strip()
            if line:
                lines.append(line)
        if lines:
            # Pause between slides
            parts.append(" ".join(lines))
    return "\n\n...\n\n".join(parts)


async def synthesize(text: str, out: Path) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, VOICE, rate=RATE)
    await communicate.save(str(out))


def main() -> None:
    md = SCRIPT.read_text(encoding="utf-8")
    text = extract_spoken_text(md)
    if not text.strip():
        raise SystemExit("No spoken text found")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_TXT.write_text(text, encoding="utf-8")
    print(f"Wrote text ({len(text)} chars) -> {OUT_TXT}")
    print(f"Synthesizing with {VOICE}...")
    asyncio.run(synthesize(text, OUT_MP3))
    print(f"Wrote narration -> {OUT_MP3} ({OUT_MP3.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
