"""Curates a benchmark set of 14 audio files for HushCheck evaluation.
Downloads open-source CC / Public Domain audio from Wikimedia Commons
and standardizes them into 16kHz mono WAV format in audio/.

Categories:
- 3 meetings/interviews with long silences
- 3 podcasts with intro/outro music
- 2 calls with hold music
- 3 videos with background music
- 3 clean continuous speech files
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "cache_raw"
AUDIO_DIR = ROOT / "audio"

RAW_FILES = {
    "speech_interview": "File:Mike Peters on Politics and Emotion (Interview 1984).mp3",
    "speech_article1": "File:FelixJMcCool(spoken Wikipedia En).ogg",
    "speech_article2": "File:Spoken Wikipedia en Hogettes.ogg",
    "speech_chiptune": "File:Spoken Wikipedia - English - chiptune.oga",
    "music_piano1": "File:Chopin - Waltz in D-flat Op-64 No-1 (Minute) (Piano Performance by eldüendesüarez).wav",
    "music_piano2": "File:Chopin - Waltz in E Op-Posth (Piano Performance by eldüendesüarez).wav",
}

USER_AGENT = "HushCheckDatasetCurator/1.0 (https://github.com/BoobalanArjunan/Hushcheck; test@example.org) Python-urllib/3.13"


def get_commons_url(title: str) -> str:
    api_url = f"https://commons.wikimedia.org/w/api.php?action=query&titles={urllib.parse.quote(title)}&prop=imageinfo&iiprop=url&format=json"
    req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                pages = data["query"]["pages"]
                for p in pages.values():
                    if "imageinfo" in p and p["imageinfo"]:
                        return p["imageinfo"][0]["url"]
            raise RuntimeError(f"Could not find URL for {title}")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(3 * (attempt + 1))
            else:
                raise


def download_file(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 1000:
        print(f"Already cached: {dest.name}")
        return
    print(f"Downloading {dest.name}...")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as f:
                while chunk := resp.read(65536):
                    f.write(chunk)
            print(f"Saved {dest.name} ({dest.stat().st_size // 1024} KB)")
            time.sleep(2)
            return
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 4 * (attempt + 1)
                print(f"Rate limited (429), waiting {wait}s...")
                time.sleep(wait)
            else:
                raise



def run_ffmpeg(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    local_raw: dict[str, Path] = {}
    for key, title in RAW_FILES.items():
        ext = title.split(".")[-1]
        dest = RAW_DIR / f"{key}.{ext}"
        url = get_commons_url(title)
        download_file(url, dest)
        local_raw[key] = dest

    print("All raw files downloaded. Now assembling the 14 audio test files...")

    # Helper: silence generator
    silence = "anullsrc=r=16000:cl=mono"

    # --- 1. Clean continuous speech (3 files) ---
    print("Building clean speech files...")
    # clean_speech_1: 45s from article1
    run_ffmpeg([
        "ffmpeg", "-y", "-ss", "10", "-t", "45", "-i", str(local_raw["speech_article1"]),
        "-ar", "16000", "-ac", "1", str(AUDIO_DIR / "clean_speech_1.wav")
    ])
    # clean_speech_2: 45s from interview
    run_ffmpeg([
        "ffmpeg", "-y", "-ss", "30", "-t", "45", "-i", str(local_raw["speech_interview"]),
        "-ar", "16000", "-ac", "1", str(AUDIO_DIR / "clean_speech_2.wav")
    ])
    # clean_speech_3: 45s from article2
    run_ffmpeg([
        "ffmpeg", "-y", "-ss", "15", "-t", "45", "-i", str(local_raw["speech_article2"]),
        "-ar", "16000", "-ac", "1", str(AUDIO_DIR / "clean_speech_3.wav")
    ])

    # --- 2. Meetings/interviews with long silences (3 files) ---
    print("Building meeting with long silences files...")
    # meeting_silence_1: 20s speech, 18s silence, 20s speech
    run_ffmpeg([
        "ffmpeg", "-y",
        "-ss", "10", "-t", "20", "-i", str(local_raw["speech_interview"]),
        "-f", "lavfi", "-t", "18", "-i", silence,
        "-ss", "40", "-t", "20", "-i", str(local_raw["speech_interview"]),
        "-filter_complex", "[0:a][1:a][2:a]concat=n=3:v=0:a=1[out]",
        "-map", "[out]", "-ar", "16000", "-ac", "1", str(AUDIO_DIR / "meeting_silence_1.wav")
    ])

    # meeting_silence_2: 25s speech, 22s silence, 20s speech
    run_ffmpeg([
        "ffmpeg", "-y",
        "-ss", "60", "-t", "25", "-i", str(local_raw["speech_article1"]),
        "-f", "lavfi", "-t", "22", "-i", silence,
        "-ss", "90", "-t", "20", "-i", str(local_raw["speech_article1"]),
        "-filter_complex", "[0:a][1:a][2:a]concat=n=3:v=0:a=1[out]",
        "-map", "[out]", "-ar", "16000", "-ac", "1", str(AUDIO_DIR / "meeting_silence_2.wav")
    ])

    # meeting_silence_3: 18s speech, 16s silence, 22s speech
    run_ffmpeg([
        "ffmpeg", "-y",
        "-ss", "10", "-t", "18", "-i", str(local_raw["speech_chiptune"]),
        "-f", "lavfi", "-t", "16", "-i", silence,
        "-ss", "35", "-t", "22", "-i", str(local_raw["speech_chiptune"]),
        "-filter_complex", "[0:a][1:a][2:a]concat=n=3:v=0:a=1[out]",
        "-map", "[out]", "-ar", "16000", "-ac", "1", str(AUDIO_DIR / "meeting_silence_3.wav")
    ])

    # --- 3. Podcasts with intro or outro music (3 files) ---
    print("Building podcast intro/outro files...")
    # podcast_intro_outro_1: 12s music intro, 35s speech, 12s music outro
    run_ffmpeg([
        "ffmpeg", "-y",
        "-ss", "0", "-t", "12", "-i", str(local_raw["music_piano1"]),
        "-ss", "20", "-t", "35", "-i", str(local_raw["speech_article1"]),
        "-ss", "25", "-t", "12", "-i", str(local_raw["music_piano1"]),
        "-filter_complex", "[0:a][1:a][2:a]concat=n=3:v=0:a=1[out]",
        "-map", "[out]", "-ar", "16000", "-ac", "1", str(AUDIO_DIR / "podcast_intro_outro_1.wav")
    ])

    # podcast_intro_outro_2: 15s music intro, 30s speech, 15s music outro
    run_ffmpeg([
        "ffmpeg", "-y",
        "-ss", "5", "-t", "15", "-i", str(local_raw["music_piano2"]),
        "-ss", "10", "-t", "30", "-i", str(local_raw["speech_interview"]),
        "-ss", "30", "-t", "15", "-i", str(local_raw["music_piano2"]),
        "-filter_complex", "[0:a][1:a][2:a]concat=n=3:v=0:a=1[out]",
        "-map", "[out]", "-ar", "16000", "-ac", "1", str(AUDIO_DIR / "podcast_intro_outro_2.wav")
    ])

    # podcast_intro_outro_3: 10s music intro, 40s speech, 10s music outro
    run_ffmpeg([
        "ffmpeg", "-y",
        "-ss", "15", "-t", "10", "-i", str(local_raw["music_piano1"]),
        "-ss", "20", "-t", "40", "-i", str(local_raw["speech_article2"]),
        "-ss", "40", "-t", "10", "-i", str(local_raw["music_piano1"]),
        "-filter_complex", "[0:a][1:a][2:a]concat=n=3:v=0:a=1[out]",
        "-map", "[out]", "-ar", "16000", "-ac", "1", str(AUDIO_DIR / "podcast_intro_outro_3.wav")
    ])

    # --- 4. Calls with hold music (2 files) ---
    print("Building call hold music files...")
    # call_hold_music_1: 45s of piano hold music
    run_ffmpeg([
        "ffmpeg", "-y", "-ss", "0", "-t", "45", "-i", str(local_raw["music_piano1"]),
        "-ar", "16000", "-ac", "1", str(AUDIO_DIR / "call_hold_music_1.wav")
    ])

    # call_hold_music_2: 6s spoken prompt ("please hold..."), 40s music
    run_ffmpeg([
        "ffmpeg", "-y",
        "-ss", "2", "-t", "6", "-i", str(local_raw["speech_article2"]),
        "-ss", "10", "-t", "40", "-i", str(local_raw["music_piano2"]),
        "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[out]",
        "-map", "[out]", "-ar", "16000", "-ac", "1", str(AUDIO_DIR / "call_hold_music_2.wav")
    ])

    # --- 5. Videos with background music (3 files) ---
    print("Building video with background music files...")
    # video_bg_music_1: 45s speech with low volume background music (-18dB)
    run_ffmpeg([
        "ffmpeg", "-y",
        "-ss", "10", "-t", "45", "-i", str(local_raw["speech_interview"]),
        "-ss", "0", "-t", "45", "-i", str(local_raw["music_piano1"]),
        "-filter_complex", "[1:a]volume=0.18[bg];[0:a][bg]amix=inputs=2:duration=first[out]",
        "-map", "[out]", "-ar", "16000", "-ac", "1", str(AUDIO_DIR / "video_bg_music_1.wav")
    ])

    # video_bg_music_2: 45s speech with background music (-16dB)
    run_ffmpeg([
        "ffmpeg", "-y",
        "-ss", "15", "-t", "45", "-i", str(local_raw["speech_article1"]),
        "-ss", "10", "-t", "45", "-i", str(local_raw["music_piano2"]),
        "-filter_complex", "[1:a]volume=0.20[bg];[0:a][bg]amix=inputs=2:duration=first[out]",
        "-map", "[out]", "-ar", "16000", "-ac", "1", str(AUDIO_DIR / "video_bg_music_2.wav")
    ])

    # video_bg_music_3: 45s speech with background music (-14dB)
    run_ffmpeg([
        "ffmpeg", "-y",
        "-ss", "5", "-t", "45", "-i", str(local_raw["speech_chiptune"]),
        "-ss", "20", "-t", "45", "-i", str(local_raw["music_piano1"]),
        "-filter_complex", "[1:a]volume=0.22[bg];[0:a][bg]amix=inputs=2:duration=first[out]",
        "-map", "[out]", "-ar", "16000", "-ac", "1", str(AUDIO_DIR / "video_bg_music_3.wav")
    ])

    wav_files = sorted(list(AUDIO_DIR.glob("*.wav")))
    print(f"\nSuccessfully generated {len(wav_files)} audio files in {AUDIO_DIR}:")
    for f in wav_files:
        print(f"  - {f.name} ({f.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
