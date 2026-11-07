"""Stage test set files into test_data/.
DO NOT TRANSCRIBE OR RUN EVALUATION ON THESE FILES.
They are staged in advance per HUSHCHECK2_EVALUATION_RULE.md.
"""
from __future__ import annotations

import json
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEST_DIR = ROOT / "test_data"
TEST_AMI = TEST_DIR / "ami"
TEST_MUSIC = TEST_DIR / "music"
TEST_NOISE = TEST_DIR / "noise"

for d in (TEST_AMI, TEST_MUSIC, TEST_NOISE):
    d.mkdir(parents=True, exist_ok=True)

USER_AGENT = "HushCheck2Stager/1.0 (https://github.com/BoobalanArjunan/Hushcheck; open-eval@example.org) Python-urllib/3.13"

# 1. 4 AMI Meetings for Test (all unused)
TEST_MEETINGS = ["EN2003a", "ES2004a", "IS1003a", "TS3004a"]

# 2. 6 Fresh Music Tracks (different genres, non-speech)
COMMONS_MUSIC = {
    "music_joplin_the_entertainer": {
        "title": "File:Scott Joplin - The Entertainer (1902).ogg",
        "genre": "ragtime_piano",
        "license": "Public Domain"
    },
    "music_vivaldi_winter_largo": {
        "title": "File:11 - Vivaldi Winter mvt 2 Largo - John Harrison violin.ogg",
        "genre": "violin_concerto",
        "license": "Creative Commons Attribution-ShareAlike 3.0 Unported"
    },
    "music_beethoven_symphony5_allegro": {
        "title": "File:Ludwig van Beethoven - Symphonie 5 c-moll - 1. Allegro con brio.ogg",
        "genre": "symphonic_orchestra",
        "license": "Public Domain"
    },
    "music_bach_partita3_prelude": {
        "title": "File:Bach Partita 3 for Violin Prelude 01.wav",
        "genre": "solo_violin",
        "license": "Public Domain"
    },
    "music_tchaikovsky_waltz_flowers": {
        "title": "File:Waltz of the Flowers - Concert Band - United States Air Force Band.mp3",
        "genre": "concert_band",
        "license": "Public Domain"
    },
    "music_vivaldi_winter_allegro": {
        "title": "File:12 - Vivaldi Winter mvt 3 Allegro - John Harrison violin.ogg",
        "genre": "violin_concerto",
        "license": "Creative Commons Attribution-ShareAlike 3.0 Unported"
    }
}

# 3. 4 Fresh Environmental Noise Tracks (non-speech)
COMMONS_NOISE = {
    "noise_sea_waves": {
        "title": "File:Sea waves.wav",
        "category": "ocean_surf",
        "license": "Creative Commons Attribution-ShareAlike 3.0 Unported"
    },
    "noise_waterfall_birds": {
        "title": "File:Waterfall and birds sounds.wav",
        "category": "waterfall_nature",
        "license": "Creative Commons Attribution 3.0 Unported"
    },
    "noise_wind_pine_forest": {
        "title": "File:Wind in Swedish pine forest at 25 mps.ogg",
        "category": "wind_ambience",
        "license": "Creative Commons Attribution-ShareAlike 3.0 Unported"
    },
    "noise_rain_thunder": {
        "title": "File:Rain and thunder.ogg",
        "category": "storm_ambience",
        "license": "Creative Commons Attribution-ShareAlike 3.0 Unported"
    }
}


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
    if dest.exists() and dest.stat().st_size > 10000:
        print(f"Already cached: {dest.name} ({dest.stat().st_size // 1024} KB)")
        return
    print(f"Downloading {dest.name}...")
    cmd = ["curl", "-sSL", "--retry", "5", "--retry-delay", "3", "-H", f"User-Agent: {USER_AGENT}", url, "-o", str(dest)]
    res = subprocess.run(cmd)
    if res.returncode == 0 and dest.exists() and dest.stat().st_size > 1000:
        print(f"Saved {dest.name} ({dest.stat().st_size // 1024} KB)")
        time.sleep(2)
    else:
        raise RuntimeError(f"Failed to download {url}")


def main():
    print("=== Staging Test Set (HELD UNTOUCHED) ===")

    # 1. AMI Meetings
    for m in TEST_MEETINGS:
        dest = TEST_AMI / f"{m}.Mix-Headset.wav"
        url = f"https://groups.inf.ed.ac.uk/ami/AMICorpusMirror//amicorpus/{m}/audio/{m}.Mix-Headset.wav"
        download_file(url, dest)

    # 2. Music
    for key, info in COMMONS_MUSIC.items():
        ext = info["title"].split(".")[-1]
        dest = TEST_MUSIC / f"{key}.{ext}"
        try:
            url = get_commons_url(info["title"])
            download_file(url, dest)
        except Exception as e:
            print(f"Warning: could not fetch {key}: {e}")

    # 3. Noise
    for key, info in COMMONS_NOISE.items():
        ext = info["title"].split(".")[-1]
        dest = TEST_NOISE / f"{key}.{ext}"
        try:
            url = get_commons_url(info["title"])
            download_file(url, dest)
        except Exception as e:
            print(f"Warning: could not fetch {key}: {e}")

    print("\nTest set staged in test_data/. WILL REMAIN UNTOUCHED UNTIL FROZEN EVALUATION.")


if __name__ == "__main__":
    main()
