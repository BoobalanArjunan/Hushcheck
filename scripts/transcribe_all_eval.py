"""Transcribe all staged evaluation audio using OpenAI Whisper small on MPS (Apple Silicon).
Saves raw JSON files to eval_json/.
Zero temperature (greedy decoding).
Does not evaluate or modify anything.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
import whisper
import torch

ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = ROOT / "eval_data"
JSON_DIR = ROOT / "eval_json"
JSON_DIR.mkdir(parents=True, exist_ok=True)

AUDIO_FILES = [
    EVAL_DIR / "music_debussy_clair_de_lune.ogg",
    EVAL_DIR / "music_chopin_nocturne_op9_no1.flac",
    EVAL_DIR / "music_chopin_nocturne_op9_no2.flac",
    EVAL_DIR / "noise_rain_thunder.ogg",
    EVAL_DIR / "noise_rain_concrete.wav",
    EVAL_DIR / "ami" / "ES2002a.Mix-Headset.wav",
    EVAL_DIR / "ami" / "IS1000a.Mix-Headset.wav",
    EVAL_DIR / "ami" / "TS3003a.Mix-Headset.wav",
]


def main():
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Loading Whisper small on {device}...")
    model = whisper.load_model("small", device=device)
    print("Model loaded successfully.\n")

    for idx, audio_path in enumerate(AUDIO_FILES, 1):
        if not audio_path.exists():
            print(f"ERROR: Audio file not found: {audio_path}", file=sys.stderr)
            sys.exit(1)
        dest_json = JSON_DIR / f"{audio_path.stem}.json"
        print(f"[{idx}/{len(AUDIO_FILES)}] Transcribing {audio_path.name} ({audio_path.stat().st_size // (1024*1024)} MB)...")
        sys.stdout.flush()

        t0 = time.time()
        res = model.transcribe(str(audio_path), temperature=0.0)
        elapsed = time.time() - t0

        # Save standard whisper JSON
        with open(dest_json, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2, ensure_ascii=False)

        num_segs = len(res.get("segments", []))
        print(f"  -> Completed in {elapsed:.1f}s. Emitted {num_segs} segments. Saved {dest_json.name}")
        sys.stdout.flush()

    print("\nAll evaluation files successfully transcribed to eval_json/")


if __name__ == "__main__":
    main()
