"""Evaluate HushCheck, whisper-guard, and Text-only checks on the authentic evaluation dataset.
Governed strictly by docs/FIX_PROPOSAL_AND_LABELLING_RULE.md (Tag: eval-spec-v2).
This script runs exactly once on the pre-transcribed eval_json/ transcripts.
"""
from __future__ import annotations

import copy
import csv
import json
import math
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = ROOT / "eval_data"
JSON_DIR = ROOT / "eval_json"
AMI_ZIP = EVAL_DIR / "ami" / "ami_public_manual_1.6.2.zip"
RESULTS_FILE = ROOT / "results.md"
AMBIGUOUS_FILE = ROOT / "ambiguous_lines.csv"

# 1. Wilson score confidence interval
def wilson_interval(k: int, n: int, z: float = 1.95996) -> tuple[float, float, float]:
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    return p, max(0.0, center - margin), min(1.0, center + margin)


def format_pct(p: float, low: float, high: float) -> str:
    return f"{p*100:.1f}% ({low*100:.1f}–{high*100:.1f}%)"


# 2. AMI Speech Intervals Loader
class AMIGroundTruth:
    def __init__(self, zip_path: Path):
        self.meeting_intervals: dict[str, list[tuple[float, float]]] = {}
        with zipfile.ZipFile(zip_path) as z:
            # Meetings of interest
            for meeting in ["ES2002a", "IS1000a", "TS3003a"]:
                raw_intervals = []
                for name in z.namelist():
                    if name.startswith(f"words/{meeting}") and name.endswith(".words.xml"):
                        tree = ET.fromstring(z.read(name))
                        for w in tree.iter():
                            if not w.tag.endswith("w"):
                                continue
                            st = w.attrib.get("starttime")
                            et = w.attrib.get("endtime")
                            if st is not None and et is not None:
                                s, e = float(st), float(et)
                                if e > s:
                                    raw_intervals.append((s, e))
                raw_intervals.sort()
                # Merge overlapping or touching intervals
                merged = []
                for s, e in raw_intervals:
                    if not merged or s > merged[-1][1]:
                        merged.append([s, e])
                    else:
                        merged[-1][1] = max(merged[-1][1], e)
                self.meeting_intervals[meeting] = [(s, e) for s, e in merged]

    def get_overlap_ratio(self, meeting: str, seg_start: float, seg_end: float) -> float:
        duration = max(1e-6, seg_end - seg_start)
        intervals = self.meeting_intervals.get(meeting, [])
        overlap_s = 0.0
        for s, e in intervals:
            if e <= seg_start:
                continue
            if s >= seg_end:
                break
            ov_start = max(s, seg_start)
            ov_end = min(e, seg_end)
            if ov_end > ov_start:
                overlap_s += (ov_end - ov_start)
        return overlap_s / duration


def find_audio_file(stem: str) -> Path:
    # Check eval_data/
    for ext in [".wav", ".flac", ".ogg", ".mp3"]:
        p = EVAL_DIR / f"{stem}{ext}"
        if p.exists():
            return p
        p_ami = EVAL_DIR / "ami" / f"{stem}{ext}"
        if p_ami.exists():
            return p_ami
    raise FileNotFoundError(f"Could not find audio for stem {stem} in {EVAL_DIR}")


def run_whisper_guard(raw_segments: list[dict]) -> list[bool]:
    from whisper_guard import filter_hallucinations
    items = []
    for i, d in enumerate(raw_segments):
        d_copy = dict(copy.deepcopy(d))
        d_copy["_i"] = i
        items.append(d_copy)
    kept = {d["_i"] for d in filter_hallucinations(items)}
    return [i not in kept for i in range(len(raw_segments))]


def run_text_only(raw_segments: list[dict]) -> list[bool]:
    from hushcheck import textchecks as tc
    out = []
    prev_texts = []
    for s in raw_segments:
        txt = s.get("text", "").strip()
        flagged = bool(txt) and bool(
            tc.phantom_match(txt) or tc.loop_kind(txt) or tc.repeats_previous(txt, prev_texts)
        )
        out.append(flagged)
        prev_texts.append(txt)
    return out


def main():
    print("Loading AMI official ground-truth annotations...")
    ami_gt = AMIGroundTruth(AMI_ZIP)

    from hushcheck import analyse_files

    json_files = sorted(JSON_DIR.glob("*.json"))
    if not json_files:
        print("ERROR: No JSON transcripts found in eval_json/", file=sys.stderr)
        return

    print(f"Found {len(json_files)} transcript JSON files in eval_json/.\n")

    corpus_records = []
    ambiguous_records = []

    for jf in json_files:
        stem = jf.stem
        audio_path = find_audio_file(stem)
        with open(jf, "r", encoding="utf-8") as f:
            trans_data = json.load(f)
        raw_segments = trans_data.get("segments", [])
        if not raw_segments:
            print(f"[{stem}] 0 segments emitted by Whisper.")
            continue

        # Run hushcheck
        analysis = analyse_files(audio_path, jf)
        findings = analysis.findings

        # Run whisper-guard
        guard_flags = run_whisper_guard(raw_segments)

        # Run text checks
        text_flags = run_text_only(raw_segments)

        print(f"[{stem}] {len(raw_segments)} segments. Audio: {audio_path.name}")

        is_pure_music = stem.startswith("music_")
        is_pure_noise = stem.startswith("noise_")
        is_ami = ("ES2002a" in stem or "IS1000a" in stem or "TS3003a" in stem)
        ami_meeting_id = stem.split(".")[0] if is_ami else None

        for idx, seg in enumerate(raw_segments):
            st, et = seg["start"], seg["end"]
            txt = seg["text"].strip()
            finding = findings[idx] if idx < len(findings) else None
            hush_likely = (finding.level == "LIKELY") if finding else False
            hush_review = (finding.level in ("LIKELY", "SUSPECT")) if finding else False
            wguard = guard_flags[idx]
            txt_flag = text_flags[idx]

            rec = {
                "file": stem,
                "index": idx,
                "start": st,
                "end": et,
                "duration": et - st,
                "text": txt,
                "hush_likely": hush_likely,
                "hush_review": hush_review,
                "hush_level": finding.level if finding else "UNKNOWN",
                "hush_score": finding.score if finding else 0,
                "whisper_guard": wguard,
                "text_only": txt_flag,
            }

            if is_pure_music:
                rec["category"] = "pure_music"
                rec["label"] = "invented"
                rec["overlap_ratio"] = 0.0
                corpus_records.append(rec)
            elif is_pure_noise:
                rec["category"] = "pure_noise"
                rec["label"] = "invented"
                rec["overlap_ratio"] = 0.0
                corpus_records.append(rec)
            elif is_ami:
                ov = ami_gt.get_overlap_ratio(ami_meeting_id, st, et)
                rec["overlap_ratio"] = ov
                if ov < 0.20:
                    rec["category"] = "ami_silence"
                    rec["label"] = "invented"
                    corpus_records.append(rec)
                elif ov >= 0.50:
                    rec["category"] = "ami_speech"
                    rec["label"] = "real"
                    corpus_records.append(rec)
                else:
                    rec["category"] = "ami_ambiguous"
                    rec["label"] = "ambiguous"
                    ambiguous_records.append(rec)

    # Export ambiguous lines
    with open(AMBIGUOUS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "index", "start", "end", "duration", "overlap_ratio", "text", "hush_level", "whisper_guard", "text_only"])
        writer.writeheader()
        for r in ambiguous_records:
            writer.writerow({
                "file": r["file"],
                "index": r["index"],
                "start": f"{r['start']:.2f}",
                "end": f"{r['end']:.2f}",
                "duration": f"{r['duration']:.2f}",
                "overlap_ratio": f"{r['overlap_ratio']:.3f}",
                "text": r["text"],
                "hush_level": r["hush_level"],
                "whisper_guard": r["whisper_guard"],
                "text_only": r["text_only"],
            })
    print(f"\nSaved {len(ambiguous_records)} ambiguous lines to {AMBIGUOUS_FILE.name}")

    # Compute Evaluation Metrics
    real_lines = [r for r in corpus_records if r["label"] == "real"]
    invented_lines = [r for r in corpus_records if r["label"] == "invented"]
    silence_invented = [r for r in invented_lines if r["category"] == "ami_silence"]
    music_invented = [r for r in invented_lines if r["category"] == "pure_music"]
    noise_invented = [r for r in invented_lines if r["category"] == "pure_noise"]

    N_real = len(real_lines)
    N_inv = len(invented_lines)
    N_silence = len(silence_invented)
    N_music = len(music_invented)
    N_noise = len(noise_invented)

    print(f"\nEvaluation Corpus Counts:")
    print(f"  Real Speech Lines (AMI >=50% speech): {N_real}")
    print(f"  Invented Lines Total: {N_inv}")
    print(f"    - AMI Silence Inventions (<20% speech): {N_silence}")
    print(f"    - Pure Music Inventions: {N_music}")
    print(f"    - Pure Noise Inventions: {N_noise}")
    print(f"  Ambiguous Lines Excluded (20-50% speech): {len(ambiguous_records)}")

    # False Alarms on Real Speech
    def get_far(detector_key):
        fa = sum(1 for r in real_lines if r[detector_key])
        return fa, *wilson_interval(fa, N_real)

    hush_likely_fa, hush_likely_far, hl_far_lo, hl_far_hi = get_far("hush_likely")
    hush_review_fa, hush_review_far, hr_far_lo, hr_far_hi = get_far("hush_review")
    wguard_fa, wguard_far, wg_far_lo, wg_far_hi = get_far("whisper_guard")
    text_fa, text_far, txt_far_lo, txt_far_hi = get_far("text_only")

    # Recall on Invented Lines
    def get_recall(lines, detector_key):
        caught = sum(1 for r in lines if r[detector_key])
        n = len(lines)
        return caught, *wilson_interval(caught, n)

    # Silence inventions recall (Claim a)
    sil_hl_caught, sil_hl_rec, sil_hl_lo, sil_hl_hi = get_recall(silence_invented, "hush_likely")
    sil_hr_caught, sil_hr_rec, sil_hr_lo, sil_hr_hi = get_recall(silence_invented, "hush_review")
    sil_wg_caught, sil_wg_rec, sil_wg_lo, sil_wg_hi = get_recall(silence_invented, "whisper_guard")
    sil_txt_caught, sil_txt_rec, sil_txt_lo, sil_txt_hi = get_recall(silence_invented, "text_only")

    # All inventions recall (Claim b)
    all_hl_caught, all_hl_rec, all_hl_lo, all_hl_hi = get_recall(invented_lines, "hush_likely")
    all_hr_caught, all_hr_rec, all_hr_lo, all_hr_hi = get_recall(invented_lines, "hush_review")
    all_wg_caught, all_wg_rec, all_wg_lo, all_wg_hi = get_recall(invented_lines, "whisper_guard")
    all_txt_caught, all_txt_rec, all_txt_lo, all_txt_hi = get_recall(invented_lines, "text_only")

    # Music & Noise recall breakdowns
    mus_hr_caught, mus_hr_rec, mus_hr_lo, mus_hr_hi = get_recall(music_invented, "hush_review")
    mus_wg_caught, mus_wg_rec, mus_wg_lo, mus_wg_hi = get_recall(music_invented, "whisper_guard")
    noi_hr_caught, noi_hr_rec, noi_hr_lo, noi_hr_hi = get_recall(noise_invented, "hush_review")
    noi_wg_caught, noi_wg_rec, noi_wg_lo, noi_wg_hi = get_recall(noise_invented, "whisper_guard")

    # Verdict Evaluation
    claim_a_pass = (
        N_real >= 300 and
        hush_likely_far <= 0.010 and
        hl_far_hi <= 0.025 and
        (N_silence >= 30 and sil_hl_rec >= 0.80)
    )

    # Claim b: Review recall clearly higher than whisper-guard (non-overlapping intervals) AND FAR <= whisper-guard's FAR AND recall > text_only
    recall_clearly_higher = (hr_far_lo > wg_far_hi) if False else (all_hr_lo > all_wg_hi)
    far_not_worse = (hush_review_far <= wguard_far)
    beats_text = (all_hr_rec > all_txt_rec)

    claim_b_pass = (
        N_inv >= 100 and
        recall_clearly_higher and
        far_not_worse and
        beats_text
    )

    is_inconclusive = (N_inv < 100 or N_real < 300)

    # Build results.md markdown document
    res_md = f"""# Authentic Benchmark Results: HushCheck vs. Whisper-Guard

**Protocol Tag**: `eval-spec-v2`  
**Execution Timestamp**: November 2026  
**Execution Status**: Single Run Completed (Frozen Specification)

---

## 1. Executive Summary & Verdict

| Claim | Locked Criterion | Observed Result | Status |
|---|---|---|---|
| **Claim (a): Auto-flag (`LIKELY`)** | FAR $\\le 1.0\\%$ (95% upper bound $\\le 2.5\\%$ on $N \\ge 300$), Silence Recall $\\ge 80\\%$ ($N \\ge 30$) | FAR: {format_pct(hush_likely_far, hl_far_lo, hl_far_hi)} ({hush_likely_fa}/{N_real} FAs). Silence Recall: {format_pct(sil_hl_rec, sil_hl_lo, sil_hl_hi)} ({sil_hl_caught}/{N_silence}). | **{'PASS' if claim_a_pass else ('INCONCLUSIVE' if is_inconclusive else 'FAIL')}** |
| **Claim (b): Review (`LIKELY+SUSPECT`)** | Recall clearly higher than whisper-guard (non-overlapping 95% Wilson intervals), FAR $\\le$ whisper-guard's, Recall > text-only ($N \\ge 100$) | Review Recall: {format_pct(all_hr_rec, all_hr_lo, all_hr_hi)} ({all_hr_caught}/{N_inv}) vs. WG: {format_pct(all_wg_rec, all_wg_lo, all_wg_hi)} ({all_wg_caught}/{N_inv}). FAR: {format_pct(hush_review_far, hr_far_lo, hr_far_hi)} vs. WG: {format_pct(wguard_far, wg_far_lo, wg_far_hi)}. | **{'PASS' if claim_b_pass else ('INCONCLUSIVE' if is_inconclusive else 'FAIL')}** |

{'### Overall Verdict: PASS — HushCheck passes both locked claims under frozen specification.' if (claim_a_pass and claim_b_pass) else ('### Overall Verdict: INCONCLUSIVE — Total sample size fell below the pre-fixed threshold (requires N_inv >= 100 and N_real >= 300).' if is_inconclusive else '### Overall Verdict: STOP RULE TRIGGERED — One or more claims did not satisfy the strict locked criteria.')}

---

## 2. False-Alarm Rate on Real Human Speech ($N = {N_real}$)

Evaluated on natural multi-speaker conversation in the AMI Meeting Corpus with $\\ge 50\\%$ annotated speech overlap.

| Method | False Alarms | False-Alarm Rate (Point) | 95% Wilson Confidence Interval |
|---|---|---|---|
| **HushCheck `LIKELY` (Auto-flag)** | {hush_likely_fa} | {hush_likely_far*100:.2f}% | {format_pct(hush_likely_far, hl_far_lo, hl_far_hi)} |
| **HushCheck `LIKELY+SUSPECT` (Review)** | {hush_review_fa} | {hush_review_far*100:.2f}% | {format_pct(hush_review_far, hr_far_lo, hr_far_hi)} |
| **`whisper-guard` (Default)** | {wguard_fa} | {wguard_far*100:.2f}% | {format_pct(wguard_far, wg_far_lo, wg_far_hi)} |
| **Text-only Checks** | {text_fa} | {text_far*100:.2f}% | {format_pct(text_far, txt_far_lo, txt_far_hi)} |

---

## 3. Recall on Invented Lines (Hallucinations)

### A. Hallucinations Over AMI Meeting Pauses & Silence ($N = {N_silence}$)
Defined by AMI ground-truth annotations ($< 20\\%$ speech overlap).

| Method | Caught | Recall (Point) | 95% Wilson Confidence Interval |
|---|---|---|---|
| **HushCheck `LIKELY`** | {sil_hl_caught} | {sil_hl_rec*100:.1f}% | {format_pct(sil_hl_rec, sil_hl_lo, sil_hl_hi)} |
| **HushCheck `LIKELY+SUSPECT`** | {sil_hr_caught} | {sil_hr_rec*100:.1f}% | {format_pct(sil_hr_rec, sil_hr_lo, sil_hr_hi)} |
| **`whisper-guard`** | {sil_wg_caught} | {sil_wg_rec*100:.1f}% | {format_pct(sil_wg_rec, sil_wg_lo, sil_wg_hi)} |
| **Text-only Checks** | {sil_txt_caught} | {sil_txt_rec*100:.1f}% | {format_pct(sil_txt_rec, sil_txt_lo, sil_txt_hi)} |

### B. All Invented Lines Across the Authentic Corpus ($N = {N_inv}$)
Including AMI silence pauses ($N={N_silence}$), pure instrumental music ($N={N_music}$), and pure environmental noise ($N={N_noise}$).

| Method | Caught | Recall (Point) | 95% Wilson Confidence Interval |
|---|---|---|---|
| **HushCheck `LIKELY+SUSPECT` (Review)** | {all_hr_caught} | {all_hr_rec*100:.1f}% | {format_pct(all_hr_rec, all_hr_lo, all_hr_hi)} |
| **HushCheck `LIKELY` (Auto-flag)** | {all_hl_caught} | {all_hl_rec*100:.1f}% | {format_pct(all_hl_rec, all_hl_lo, all_hl_hi)} |
| **`whisper-guard` (Default)** | {all_wg_caught} | {all_wg_rec*100:.1f}% | {format_pct(all_wg_rec, all_wg_lo, all_wg_hi)} |
| **Text-only Checks** | {all_txt_caught} | {all_txt_rec*100:.1f}% | {format_pct(all_txt_rec, all_txt_lo, all_txt_hi)} |

### C. Category Recall Breakdown (Review Mode)

| Category | Total Lines | HushCheck Review Caught | HushCheck Recall | whisper-guard Caught | whisper-guard Recall |
|---|---|---|---|---|---|
| **AMI Silence Pauses** | {N_silence} | {sil_hr_caught} | {sil_hr_rec*100:.1f}% | {sil_wg_caught} | {sil_wg_rec*100:.1f}% |
| **Pure Instrumental Music** | {N_music} | {mus_hr_caught} | {mus_hr_rec*100:.1f}% | {mus_wg_caught} | {mus_wg_rec*100:.1f}% |
| **Pure Environmental Noise** | {N_noise} | {noi_hr_caught} | {noi_hr_rec*100:.1f}% | {noi_wg_caught} | {noi_wg_rec*100:.1f}% |

---

## 4. Ambiguous Lines Logged & Excluded

Total ambiguous lines ($20\\% \\le \\text{{overlap}} < 50\\%$): **{len(ambiguous_records)} lines**.  
Exported to [`ambiguous_lines.csv`](./ambiguous_lines.csv) with full start/end timestamps and detector verdicts.

---

## 5. Decision Rule Check Details

- **Claim (a) Checks**:
  - Sample size $N_{{real}} \\ge 300$: **{N_real}** ({'PASS' if N_real >= 300 else 'FAIL'})
  - False-Alarm Rate point estimate $\\le 1.0\\%$: **{hush_likely_far*100:.2f}%** ({'PASS' if hush_likely_far <= 0.010 else 'FAIL'})
  - False-Alarm Rate 95% Wilson upper bound $\\le 2.5\\%$: **{hl_far_hi*100:.2f}%** ({'PASS' if hl_far_hi <= 0.025 else 'FAIL'})
  - Silence recall $\\ge 80\\%$ ($N_{{silence}} \\ge 30$): **{sil_hl_rec*100:.1f}%** ($N={N_silence}$) ({'PASS' if (N_silence >= 30 and sil_hl_rec >= 0.80) else ('INCONCLUSIVE' if N_silence < 30 else 'FAIL')})

- **Claim (b) Checks**:
  - Sample size $N_{{inv}} \\ge 100$: **{N_inv}** ({'PASS' if N_inv >= 100 else 'FAIL'})
  - Recall clearly higher than whisper-guard (non-overlapping 95% intervals): **{format_pct(all_hr_rec, all_hr_lo, all_hr_hi)} vs. {format_pct(all_wg_rec, all_wg_lo, all_wg_hi)}** ({'PASS' if all_hr_lo > all_wg_hi else 'FAIL'})
  - FAR no higher than whisper-guard's: **{hush_review_far*100:.2f}% vs. {wguard_far*100:.2f}%** ({'PASS' if hush_review_far <= wguard_far else 'FAIL'})
  - Recall higher than text-checks-only: **{all_hr_rec*100:.1f}% vs. {all_txt_rec*100:.1f}%** ({'PASS' if all_hr_rec > all_txt_rec else 'FAIL'})
"""

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        f.write(res_md)

    print(f"\nSuccessfully generated {RESULTS_FILE.name}!")
    print(f"Overall Status: {'PASS' if (claim_a_pass and claim_b_pass) else ('INCONCLUSIVE' if is_inconclusive else 'FAIL')}")


if __name__ == "__main__":
    main()

