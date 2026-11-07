"""Transcribe the calibration set using Whisper small on MPS (Apple Silicon).
Transcribes ONLY calibration_data/ into calibration_json/.
Never touches test_data/.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
import torch
import whisper

ROOT = Path(__file__).resolve().parent.parent
CALIB_DIR = ROOT / "calibration_data"
JSON_DIR = ROOT / "calibration_json"
JSON_DIR.mkdir(parents=True, exist_ok=True)

AMI_DIR = CALIB_DIR / "ami"
LIBRI_DIR = CALIB_DIR / "librispeech"


def main():
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Loading Whisper small on {device}...")
    model = whisper.load_model("small", device=device)
    print("Model loaded successfully.\n")

    # 1. Calibration AMI meetings
    ami_files = sorted(AMI_DIR.glob("*.wav"))
    print(f"Found {len(ami_files)} calibration AMI meetings.")
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

    # 2. Calibration LibriSpeech files
    libri_files = sorted(LIBRI_DIR.glob("*.flac"))
    print(f"\nFound {len(libri_files)} LibriSpeech dev-clean files.")
    libri_transcripts = {}
    dest_libri_json = JSON_DIR / "librispeech_dev_clean_100.json"
    if dest_libri_json.exists():
        print("LibriSpeech already transcribed.")
    else:
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
        print(f"Completed 100 LibriSpeech files in {time.time()-t0:.1f}s. Saved {dest_libri_json.name}")

    print("\nCalibration transcription completed successfully.")


if __name__ == "__main__":
    main()

