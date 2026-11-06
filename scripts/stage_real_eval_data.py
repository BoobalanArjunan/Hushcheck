"""Stages the authentic real-world evaluation dataset into eval_data/.
All files are downloaded directly from open-licensed repositories (Wikimedia Commons).
Audio files are kept strictly local and excluded from git version control.
NO EVALUATIONS OR INFERENCE ARE RUN BY THIS SCRIPT.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = ROOT / "eval_data"

DATASET_SOURCES = {
    # 1. Pure Instrumental Music (100% Non-Speech by definition)
    "music_chopin_nocturne_op9_no2": {
        "title": "File:Chopin - Nocturne No. 2 in E-flat major, Op. 9 No. 2 (Frank Levy).flac",
        "category": "pure_music",
        "description": "Solo piano performance by Frank Levy",
        "license": "Creative Commons Attribution 3.0 Unported"
    },
    "music_debussy_clair_de_lune": {
        "title": "File:Clair de lune (Claude Debussy) Suite bergamasque.ogg",
        "category": "pure_music",
        "description": "Claude Debussy Suite bergamasque Clair de lune",
        "license": "Public Domain"
    },
    "music_chopin_nocturne_op9_no1": {
        "title": "File:Chopin - Nocturne No. 1 in B-flat minor, Op. 9 No. 1 (Olga Gurevich).flac",
        "category": "pure_music",
        "description": "Solo piano performance by Olga Gurevich",
        "license": "Creative Commons Attribution 3.0 Unported"
    },
    # 2. Pure Environmental Noise (100% Non-Speech by definition)
    "noise_rain_thunder": {
        "title": "File:Rain thunder and birds.ogg",
        "category": "pure_noise",
        "description": "Natural ambient field recording of rain, thunder, and birds",
        "license": "Creative Commons Attribution-ShareAlike 3.0 Unported"
    },
    "noise_rain_concrete": {
        "title": "File:Rain on Concrete during storm with thunder.wav",
        "category": "pure_noise",
        "description": "Field recording of thunderstorm rain on concrete",
        "license": "Creative Commons CC0 1.0 Universal Public Domain"
    },
    # 3. Real Unscripted Speech with Natural Pauses & Room Acoustics
    "speech_iran_contra_hearing": {
        "title": "File:Rep. Edward Boland Questions Secretary of Defense Caspar Weinberger During the Iran-Contra Hearings.ogg",
        "category": "real_dialogue_with_pauses",
        "description": "Authentic historical hearing dialogue with natural unscripted pauses, turn-taking, and room acoustics",
        "license": "Public Domain"
    }
}

USER_AGENT = "HushCheckRealDataStager/1.0 (https://github.com/BoobalanArjunan/Hushcheck; open-source-eval@example.org) Python-urllib/3.13"


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
            time.sleep(1)
            return
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(4 * (attempt + 1))
            else:
                raise


def main():
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    for key, info in DATASET_SOURCES.items():
        ext = info["title"].split(".")[-1]
        dest = EVAL_DIR / f"{key}.{ext}"
        url = get_commons_url(info["title"])
        download_file(url, dest)
        manifest.append({
            "key": key,
            "filename": dest.name,
            "category": info["category"],
            "title": info["title"],
            "license": info["license"],
            "size_kb": dest.stat().st_size // 1024
        })

    with open(EVAL_DIR / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nSuccessfully staged {len(manifest)} authentic evaluation files in {EVAL_DIR}")


if __name__ == "__main__":
    main()

