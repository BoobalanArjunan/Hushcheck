"""Exploratory Analysis on used-up evaluation data (eval-spec-v2).
Label: EXPLORATORY, NOT EVIDENCE.
Governed by HUSHCHECK2_DESIGN.md Section 7.
Does not alter any thresholds.
"""
import copy
import json
from pathlib import Path
from hushcheck import analyse_files
from hushcheck import guardlogic as gl
from whisper_guard import filter_hallucinations

ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = ROOT / "eval_data"
JSON_DIR = ROOT / "eval_json"

def find_audio(stem):
    for ext in [".wav", ".flac", ".ogg"]:
        p = EVAL_DIR / f"{stem}{ext}"
        if p.exists(): return p
        p_ami = EVAL_DIR / "ami" / f"{stem}{ext}"
        if p_ami.exists(): return p_ami
    raise FileNotFoundError(stem)

def main():
    print("=== HushCheck 2 Exploratory Analysis (NOT EVIDENCE) ===\n")
    json_files = sorted(JSON_DIR.glob("*.json"))

    total_segs = 0
    signals_count = {}
    hc1_likely_count = 0
    hc1_review_count = 0
    hc2_likely_count = 0
    hc2_review_count = 0
    wg_count = 0
    union_count = 0

    for jf in json_files:
        stem = jf.stem
        audio_path = find_audio(stem)
        with open(jf, "r", encoding="utf-8") as f:
            data = json.load(f)
        segs = data.get("segments", [])
        if not segs:
            continue
        total_segs += len(segs)

        # HushCheck 1
        an = analyse_files(audio_path, jf)
        findings = an.findings

        # whisper-guard
        items = [dict(copy.deepcopy(s), _i=i) for i, s in enumerate(segs)]
        kept = {d["_i"] for d in filter_hallucinations(items)}
        wg_flags = [i not in kept for i in range(len(segs))]

        # Group into windows for HushCheck 2
        ws = gl.windows(segs)

        for i, s in enumerate(segs):
            f1 = findings[i] if i < len(findings) else None
            is_hc1_l = (f1.level == "LIKELY") if f1 else False
            is_hc1_r = (f1.level in ("LIKELY", "SUSPECT")) if f1 else False
            is_wg = wg_flags[i]

            # Collect audio signals from HC1
            audio_sigs = {}
            if f1:
                for code, _ in f1.reasons:
                    if code in ("NO_SPEECH", "BEYOND_AUDIO", "LOW_SPEECH", "NOT_SPEECH_LIKE"):
                        audio_sigs[code] = gl.score({code: 1}, [])[1]  # or existing weight
                        if code in ("NO_SPEECH", "BEYOND_AUDIO"):
                            audio_sigs[code] = 3
                        else:
                            audio_sigs[code] = 1

            # HushCheck 2 evaluation
            level_hc2, score_hc2, active_sigs = gl.score(audio_sigs, [s])
            is_hc2_l = (level_hc2 == "LIKELY")
            is_hc2_r = (level_hc2 in ("LIKELY", "SUSPECT"))

            for k in active_sigs:
                signals_count[k] = signals_count.get(k, 0) + 1

            if is_hc1_l: hc1_likely_count += 1
            if is_hc1_r: hc1_review_count += 1
            if is_hc2_l: hc2_likely_count += 1
            if is_hc2_r: hc2_review_count += 1
            if is_wg: wg_count += 1
            if is_hc1_r or is_wg: union_count += 1

    print(f"Total evaluated segments: {total_segs}")
    print("\n--- Detection Counts ---")
    print(f"HushCheck 1 LIKELY: {hc1_likely_count}")
    print(f"HushCheck 1 REVIEW: {hc1_review_count}")
    print(f"whisper-guard Flags: {wg_count}")
    print(f"Union (HC1 Review OR WG): {union_count}")
    print(f"HushCheck 2 LIKELY (Multi-family): {hc2_likely_count}")
    print(f"HushCheck 2 REVIEW: {hc2_review_count}")
    print("\n--- Signal Firing Rates ---")
    for sig, cnt in sorted(signals_count.items(), key=lambda x: -x[1]):
        print(f"  {sig:20s}: {cnt:4d} ({cnt/total_segs*100:.1f}%)")

if __name__ == "__main__":
    main()

