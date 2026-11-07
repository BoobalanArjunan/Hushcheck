"""Transcribe the full test set once using Whisper small on Apple Silicon MPS (temperature=0.0).
Governed strictly by docs/HUSHCHECK2_EVALUATION_RULE.md (Tag: eval-spec-hc2-v1).
Saves raw transcripts to test_json/.
Runs exactly once.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
import torch
import whisper

ROOT = Path(__file__).resolve().parent.parent
TEST_DIR = ROOT / "test_data"
JSON_DIR = ROOT / "test_json"
JSON_DIR.mkdir(parents=True, exist_ok=True)


def main():
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Loading Whisper small on {device} (temperature=0.0)...")
    model = whisper.load_model("small", device=device)
    print("Model loaded successfully.\n")

    # 1. AMI Meetings (6 files)
    ami_files = sorted((TEST_DIR / "ami").glob("*.wav"))
    print(f"Found {len(ami_files)} test AMI meetings.")
    for idx, audio_path in enumerate(ami_files, 1):
        dest_json = JSON_DIR / f"{audio_path.stem}.json"
        if dest_json.exists():
            print(f"[AMI {idx}/{len(ami_files)}] Already transcribed: {dest_json.name}")
            continue
        print(f"[AMI {idx}/{len(ami_files)}] Transcribing {audio_path.name} ({audio_path.stat().st_size // (1024*1024)} MB)...")
        sys.stdout.flush()
        t0 = time.time()
        res = model.transcribe(str(audio_path), temperature=0.0)
        with open(dest_json, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2, ensure_ascii=False)
        print(f"  -> Completed in {time.time()-t0:.1f}s. Emitted {len(res.get('segments', []))} segments.")
        sys.stdout.flush()

    # 2. Music Tracks (6 files)
    music_files = sorted([f for f in (TEST_DIR / "music").iterdir() if f.suffix.lower() in [".wav", ".ogg", ".mp3", ".flac"]])
    print(f"\nFound {len(music_files)} test music tracks.")
    for idx, audio_path in enumerate(music_files, 1):
        dest_json = JSON_DIR / f"{audio_path.stem}.json"
        if dest_json.exists():
            print(f"[Music {idx}/{len(music_files)}] Already transcribed: {dest_json.name}")
            continue
        print(f"[Music {idx}/{len(music_files)}] Transcribing {audio_path.name}...")
        sys.stdout.flush()
        t0 = time.time()
        res = model.transcribe(str(audio_path), temperature=0.0)
        with open(dest_json, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2, ensure_ascii=False)
        print(f"  -> Completed in {time.time()-t0:.1f}s. Emitted {len(res.get('segments', []))} segments.")
        sys.stdout.flush()

    # 3. Noise Tracks (4 files)
    noise_files = sorted([f for f in (TEST_DIR / "noise").iterdir() if f.suffix.lower() in [".wav", ".ogg", ".mp3", ".flac"]])
    print(f"\nFound {len(noise_files)} test noise tracks.")
    for idx, audio_path in enumerate(noise_files, 1):
        dest_json = JSON_DIR / f"{audio_path.stem}.json"
        if dest_json.exists():
            print(f"[Noise {idx}/{len(noise_files)}] Already transcribed: {dest_json.name}")
            continue
        print(f"[Noise {idx}/{len(noise_files)}] Transcribing {audio_path.name}...")
        sys.stdout.flush()
        t0 = time.time()
        res = model.transcribe(str(audio_path), temperature=0.0)
        with open(dest_json, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2, ensure_ascii=False)
        print(f"  -> Completed in {time.time()-t0:.1f}s. Emitted {len(res.get('segments', []))} segments.")
        sys.stdout.flush()

    # 4. LibriSpeech test-clean (100 files)
    libri_files = sorted((TEST_DIR / "librispeech").glob("*.flac"))
    print(f"\nFound {len(libri_files)} LibriSpeech test-clean files.")
    dest_libri_json = JSON_DIR / "librispeech_test_clean_100.json"
    if dest_libri_json.exists():
        print(f"LibriSpeech test-clean already transcribed: {dest_libri_json.name}")
    else:
        libri_transcripts = {}
        t0 = time.time()
        for idx, audio_path in enumerate(libri_files, 1):
            res = model.transcribe(str(audio_path), temperature=0.0)
            libri_transcripts[audio_path.stem] = {
                "file": audio_path.name,
                "text": res.get("text", "").strip(),
                "segments": res.get("segments", [])
            }
            if idx % 20 == 0 or idx == len(libri_files):
                print(f"  [{idx}/{len(libri_files)}] transcribed...")
                sys.stdout.flush()
        with open(dest_libri_json, "w", encoding="utf-8") as f:
            json.dump(libri_transcripts, f, indent=2, ensure_ascii=False)
        print(f"Completed 100 LibriSpeech test-clean files in {time.time()-t0:.1f}s. Saved {dest_libri_json.name}")

    print("\nAll test transcripts generated and saved to test_json/.")


if __name__ == "__main__":
    main()
