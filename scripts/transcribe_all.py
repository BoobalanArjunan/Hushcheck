"""Run openai-whisper to transcribe all audio/*.wav files into json/*.json.
Saves JSON transcripts containing no_speech_prob, avg_logprob, and compression_ratio.
"""
from __future__ import annotations

import json
from pathlib import Path
import whisper

ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "audio"
JSON_DIR = ROOT / "json"

def main():
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    audio_files = sorted(list(AUDIO_DIR.glob("*.wav")))
    print(f"Found {len(audio_files)} audio files to transcribe.")

    print("Loading Whisper 'small' model...")
    model = whisper.load_model("small")
    print("Model loaded successfully.")

    for i, audio_path in enumerate(audio_files, 1):
        json_path = JSON_DIR / f"{audio_path.stem}.json"
        if json_path.exists():
            print(f"[{i}/{len(audio_files)}] Already transcribed: {json_path.name}")
            continue

        print(f"[{i}/{len(audio_files)}] Transcribing {audio_path.name}...")
        result = model.transcribe(str(audio_path), verbose=False)
        
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"    Saved {json_path.name} ({len(result.get('segments', []))} segments)")

    print("\nAll transcriptions completed successfully.")

if __name__ == "__main__":
    main()
