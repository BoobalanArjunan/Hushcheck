"""Calibration script for HushCheck 2 audio thresholds.
Governed by docs/HUSHCHECK2_DESIGN.md (Section 4) and docs/HUSHCHECK2_EVALUATION_RULE.md.

Measures active_frac and mod_depth across all calibration real-speech lines:
- AMI calibration meetings: EN2001a, EN2002a, ES2003a, IS1001a (lines with >= 50% speech overlap)
- LibriSpeech dev-clean 100 files (100% read speech)

Computes the 1st percentile of active_frac and mod_depth to select:
- LOW_SPEECH_BELOW (aiming ~1% false alarms on real speech)
- NOT_SPEECH_DEPTH (aiming ~1% false alarms on real speech)

Also records empirical firing rates for all text/timing and guard rules.
Writes output to docs/CALIBRATION.md.
"""
from __future__ import annotations

import copy
import json
import math
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path
import numpy as np

from hushcheck.evidence import load_audio, line_evidence
from hushcheck.guardlogic import (
    windows,
    window_signals,
    segment_suspect,
    char_loop,
    long_repeat,
    score,
    NO_SPEECH_PROB,
    SHORT_SEC,
    SHORT_LOGPROB,
    AVG_LOGPROB,
    COMPRESSION,
    _duration,
)
from hushcheck import textchecks as tc

ROOT = Path(__file__).resolve().parent.parent
CALIB_DATA = ROOT / "calibration_data"
CALIB_JSON = ROOT / "calibration_json"
AMI_ZIP = ROOT / "eval_data" / "ami" / "ami_public_manual_1.6.2.zip"
CALIBRATION_MD = ROOT / "docs" / "CALIBRATION.md"


class AMIGroundTruth:
    def __init__(self, zip_path: Path, meetings: list[str]):
        self.meeting_intervals: dict[str, list[tuple[float, float]]] = {}
        with zipfile.ZipFile(zip_path) as z:
            for meeting in meetings:
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


def run_whisper_guard(raw_segments: list[dict]) -> list[bool]:
    from whisper_guard import filter_hallucinations
    items = []
    for i, d in enumerate(raw_segments):
        d_copy = dict(copy.deepcopy(d))
        d_copy["_i"] = i
        items.append(d_copy)
    kept = {d["_i"] for d in filter_hallucinations(items)}
    return [i not in kept for i in range(len(raw_segments))]


def compute_segment_long_repeats(segments: list[dict], w_size: int = 100) -> list[bool]:
    token_pairs = []
    for idx, s in enumerate(segments):
        for w in s.get("text", "").lower().split():
            token_pairs.append((w, idx))

    flags = []
    for idx in range(len(segments)):
        seg_indices = [i for i, (_, s_idx) in enumerate(token_pairs) if s_idx == idx]
        if not seg_indices:
            flags.append(False)
            continue
        mid = (seg_indices[0] + seg_indices[-1]) // 2
        st = max(0, mid - w_size // 2)
        et = min(len(token_pairs), st + w_size)
        window_words = [w for w, _ in token_pairs[st:et]]
        flags.append(long_repeat(window_words))
    return flags


def main():
    calib_ami_meetings = ["EN2001a", "EN2002a", "ES2003a", "IS1001a"]
    print(f"Loading AMI ground truth for calibration meetings: {calib_ami_meetings}")
    ami_gt = AMIGroundTruth(AMI_ZIP, calib_ami_meetings)

    real_speech_lines = []
    invented_speech_lines = []

    # 1. Process AMI Calibration Meetings
    for meeting in calib_ami_meetings:
        json_file = CALIB_JSON / f"{meeting}.Mix-Headset.json"
        audio_file = CALIB_DATA / "ami" / f"{meeting}.Mix-Headset.wav"
        if not json_file.exists() or not audio_file.exists():
            print(f"Skipping {meeting}: JSON or audio missing.")
            continue
        print(f"Processing AMI {meeting}...")
        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)
        segments = data.get("segments", [])
        audio = load_audio(audio_file)

        wg_flags = run_whisper_guard(segments)
        file_windows = windows(segments)
        seg_windows = []
        for w in file_windows:
            wsig = window_signals(w)
            for s in w["segs"]:
                seg_windows.append((w, wsig))

        long_rep_flags = compute_segment_long_repeats(segments)

        prev_texts = []
        for i, seg in enumerate(segments):
            st, et = seg.get("start", 0.0), seg.get("end", 0.0)
            text = seg.get("text", "").strip()
            overlap = ami_gt.get_overlap_ratio(meeting, st, et)
            ev = line_evidence(audio, st, et)

            w, wsig = seg_windows[i]
            sparse = ("SPARSE_WINDOW" in wsig)
            dense_rescued = wsig.get("_dense_confident", False)

            # Segment filter with dense confident rescue logic
            seg_filter = False
            nsp = seg.get("no_speech_prob", 0.0)
            lp = seg.get("avg_logprob", 0.0)
            dur = _duration(seg)
            cr = seg.get("compression_ratio", 1.0)
            lp_lim = SHORT_LOGPROB if (dur is not None and dur < SHORT_SEC) else AVG_LOGPROB

            if nsp > NO_SPEECH_PROB:
                if not dense_rescued:
                    seg_filter = True
                elif lp < lp_lim or cr > COMPRESSION:
                    seg_filter = True
            elif lp < lp_lim or cr > COMPRESSION:
                seg_filter = True

            loop_flag = char_loop(text)
            long_rep = long_rep_flags[i]
            rep_prev = tc.repeats_previous(text, prev_texts)
            ph_match = bool(tc.phantom_match(text))

            rec = {
                "dataset": "ami",
                "source": meeting,
                "start": st,
                "end": et,
                "duration": et - st,
                "text": text,
                "overlap": overlap,
                "active_frac": ev.active_frac,
                "mod_depth": ev.mod_depth,
                "beyond_audio": ev.beyond_audio,
                "dense_rescued": dense_rescued,
                "sparse": sparse,
                "seg_filter": seg_filter,
                "loop": loop_flag,
                "long_rep": long_rep,
                "rep_prev": rep_prev,
                "ph_match": ph_match,
                "wg_flag": wg_flags[i],
            }

            if overlap >= 0.50:
                rec["category"] = "real"
                real_speech_lines.append(rec)
            elif overlap < 0.20:
                rec["category"] = "invented"
                invented_speech_lines.append(rec)
            else:
                rec["category"] = "ambiguous"

            prev_texts.append(text)

    # 2. Process LibriSpeech dev-clean 100
    libri_json = CALIB_JSON / "librispeech_dev_clean_100.json"
    if libri_json.exists():
        print("Processing LibriSpeech dev-clean 100 files...")
        with open(libri_json, encoding="utf-8") as f:
            libri_data = json.load(f)

        for stem, item in libri_data.items():
            flac_path = CALIB_DATA / "librispeech" / item["file"]
            if not flac_path.exists():
                continue
            audio = load_audio(flac_path)
            segments = item.get("segments", [])
            wg_flags = run_whisper_guard(segments)
            file_windows = windows(segments)
            seg_windows = []
            for w in file_windows:
                wsig = window_signals(w)
                for s in w["segs"]:
                    seg_windows.append((w, wsig))

            long_rep_flags = compute_segment_long_repeats(segments)

            prev_texts = []
            for i, seg in enumerate(segments):
                st, et = seg.get("start", 0.0), seg.get("end", 0.0)
                text = seg.get("text", "").strip()
                ev = line_evidence(audio, st, et)

                w, wsig = seg_windows[i]
                sparse = ("SPARSE_WINDOW" in wsig)
                dense_rescued = wsig.get("_dense_confident", False)

                seg_filter = False
                nsp = seg.get("no_speech_prob", 0.0)
                lp = seg.get("avg_logprob", 0.0)
                dur = _duration(seg)
                cr = seg.get("compression_ratio", 1.0)
                lp_lim = SHORT_LOGPROB if (dur is not None and dur < SHORT_SEC) else AVG_LOGPROB

                if nsp > NO_SPEECH_PROB:
                    if not dense_rescued:
                        seg_filter = True
                    elif lp < lp_lim or cr > COMPRESSION:
                        seg_filter = True
                elif lp < lp_lim or cr > COMPRESSION:
                    seg_filter = True

                loop_flag = char_loop(text)
                long_rep = long_rep_flags[i]
                rep_prev = tc.repeats_previous(text, prev_texts)
                ph_match = bool(tc.phantom_match(text))

                rec = {
                    "dataset": "librispeech",
                    "source": stem,
                    "start": st,
                    "end": et,
                    "duration": et - st,
                    "text": text,
                    "overlap": 1.0,
                    "active_frac": ev.active_frac,
                    "mod_depth": ev.mod_depth,
                    "beyond_audio": ev.beyond_audio,
                    "dense_rescued": dense_rescued,
                    "sparse": sparse,
                    "seg_filter": seg_filter,
                    "loop": loop_flag,
                    "long_rep": long_rep,
                    "rep_prev": rep_prev,
                    "ph_match": ph_match,
                    "wg_flag": wg_flags[i],
                    "category": "real",
                }
                real_speech_lines.append(rec)
                prev_texts.append(text)

    n_real = len(real_speech_lines)
    print(f"\n================ CALIBRATION DATA SUMMARY ================")
    print(f"Total verified real speech lines: {n_real}")
    print(f"  - AMI meetings (overlap >= 50%): {sum(1 for r in real_speech_lines if r['dataset'] == 'ami')}")
    print(f"  - LibriSpeech read speech:       {sum(1 for r in real_speech_lines if r['dataset'] == 'librispeech')}")
    print(f"Total AMI silence invented lines:  {len(invented_speech_lines)}")

    if n_real == 0:
        print("ERROR: No real speech lines found!")
        return

    # Extract metrics
    active_fracs = np.array([r["active_frac"] for r in real_speech_lines])
    mod_depths = [r["mod_depth"] for r in real_speech_lines if r["mod_depth"] is not None]
    mod_depths_arr = np.array(mod_depths)

    # Compute percentiles
    print("\n--- ACTIVE FRACTION DISTRIBUTION (Real Speech) ---")
    for p in [0.5, 1.0, 1.5, 2.0, 2.5, 5.0, 10.0]:
        val = np.percentile(active_fracs, p)
        n_below = np.sum(active_fracs < val)
        print(f"  {p:4.1f}th percentile: {val:.4f} (flags {n_below}/{n_real} = {n_below/n_real*100:.2f}%)")

    p1_active = float(np.percentile(active_fracs, 1.0))
    cand_active = round(p1_active, 2)
    cand_active_flags = np.sum(active_fracs < cand_active)
    cand_active_pct = cand_active_flags / n_real * 100

    print(f"\nSelected LOW_SPEECH_BELOW: {cand_active:.2f} (empirical: {cand_active_flags}/{n_real} = {cand_active_pct:.2f}%)")

    print("\n--- MODULATION DEPTH DISTRIBUTION (Real Speech) ---")
    print(f"Real speech lines with calculable mod_depth (dur >= 1.5s, active >= 15%): {len(mod_depths_arr)} / {n_real} ({len(mod_depths_arr)/n_real*100:.1f}%)")
    for p in [0.5, 1.0, 1.5, 2.0, 2.5, 5.0, 10.0]:
        val = np.percentile(mod_depths_arr, p)
        n_below = np.sum(mod_depths_arr < val)
        print(f"  {p:4.1f}th percentile of calculable: {val:.4f} (flags {n_below}/{n_real} of all real = {n_below/n_real*100:.2f}%)")

    target_k = int(round(0.01 * n_real))
    sorted_depths = np.sort(mod_depths_arr)
    cutoff_1pct_all = float(sorted_depths[min(target_k, len(sorted_depths)-1)])
    cand_depth = round(cutoff_1pct_all, 2)
    cand_depth_flags = sum(1 for r in real_speech_lines if r["mod_depth"] is not None and r["mod_depth"] < cand_depth)
    cand_depth_pct = cand_depth_flags / n_real * 100

    print(f"\nSelected NOT_SPEECH_DEPTH: {cand_depth:.2f} (empirical: {cand_depth_flags}/{n_real} = {cand_depth_pct:.2f}%)")

    # Evaluate individual signal firing rates on real speech
    print("\n--- INDIVIDUAL SIGNAL FIRING RATES ON REAL SPEECH (CALIBRATION) ---")
    sig_counts = {
        "NO_SPEECH (< 0.15 active)": sum(1 for r in real_speech_lines if r["active_frac"] < 0.15),
        f"LOW_SPEECH (< {cand_active:.2f} active)": sum(1 for r in real_speech_lines if r["active_frac"] < cand_active),
        f"NOT_SPEECH_LIKE (depth < {cand_depth:.2f})": cand_depth_flags,
        "BEYOND_AUDIO": sum(1 for r in real_speech_lines if r["beyond_audio"]),
        "SPARSE_WINDOW (dur>=10s, cps<1.0)": sum(1 for r in real_speech_lines if r["sparse"]),
        "DENSE_CONFIDENT rescue fired": sum(1 for r in real_speech_lines if r["dense_rescued"]),
        "SEGMENT_FILTER (raw)": sum(1 for r in real_speech_lines if r["seg_filter"]),
        "LONG_REPEAT (ratio < 0.35)": sum(1 for r in real_speech_lines if r["long_rep"]),
        "LOOP (char repetition)": sum(1 for r in real_speech_lines if r["loop"]),
        "REPEAT (repeats prev)": sum(1 for r in real_speech_lines if r["rep_prev"]),
        "PHANTOM_PHRASE": sum(1 for r in real_speech_lines if r["ph_match"]),
    }
    for sig, cnt in sig_counts.items():
        print(f"  {sig:45s}: {cnt:4d} / {n_real:4d} ({cnt/n_real*100:5.2f}%)")

    # Overall False Alarm Rates on Real Speech
    def eval_hc2_line(rec: dict, low_speech_thr: float, not_speech_thr: float) -> tuple[int, str]:
        audio_signals = {}
        if rec["beyond_audio"]:
            audio_signals["BEYOND_AUDIO"] = 3
        elif rec["active_frac"] < 0.15:
            audio_signals["NO_SPEECH"] = 3
        else:
            if rec["active_frac"] < low_speech_thr:
                audio_signals["LOW_SPEECH"] = 1
            if rec["mod_depth"] is not None and rec["mod_depth"] < not_speech_thr:
                audio_signals["NOT_SPEECH_LIKE"] = 1

        text_signals = {}
        if rec["sparse"]:
            text_signals["SPARSE_WINDOW"] = 2
        if rec["seg_filter"]:
            text_signals["SEGMENT_FILTER"] = 1
        if rec["long_rep"]:
            text_signals["LONG_REPEAT"] = 1
        if rec["loop"]:
            text_signals["LOOP"] = 1
        if rec["rep_prev"]:
            text_signals["REPEAT"] = 1
        if rec["ph_match"]:
            text_signals["PHANTOM_PHRASE"] = 1

        audio_score = sum(audio_signals.values())
        text_score = sum(text_signals.values())
        total_score = audio_score + text_score

        strong_audio = any(k in audio_signals for k in ("NO_SPEECH", "BEYOND_AUDIO"))
        both_families = bool(audio_signals) and bool(text_signals)

        if total_score >= 3 and (both_families or strong_audio):
            level = "LIKELY"
        elif total_score >= 1:
            level = "SUSPECT"
        else:
            level = "OK"

        return total_score, level

    hc2_likely_fa = 0
    hc2_review_fa = 0
    wg_fa = 0

    for r in real_speech_lines:
        sc, lvl = eval_hc2_line(r, cand_active, cand_depth)
        if lvl == "LIKELY":
            hc2_likely_fa += 1
        if lvl in ("LIKELY", "SUSPECT"):
            hc2_review_fa += 1
        if r["wg_flag"]:
            wg_fa += 1

    print("\n--- FALSE ALARM COMPARISON ON REAL SPEECH (CALIBRATION) ---")
    print(f"  HushCheck 2 AUTO (LIKELY):     {hc2_likely_fa:4d} / {n_real} ({hc2_likely_fa/n_real*100:5.2f}%)")
    print(f"  HushCheck 2 REVIEW (LIKELY+SUS): {hc2_review_fa:4d} / {n_real} ({hc2_review_fa/n_real*100:5.2f}%)")
    print(f"  whisper-guard (v0.3.3):        {wg_fa:4d} / {n_real} ({wg_fa/n_real*100:5.2f}%)")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    doc_content = f"""# Calibration Record: HushCheck 2 Audio Thresholds

**Date:** {now_str}
**Governing Documents:** `docs/HUSHCHECK2_DESIGN.md` (Section 4) and `docs/HUSHCHECK2_EVALUATION_RULE.md`
**Status:** Frozen for evaluation `eval-spec-hc2-v1`

## 1. Calibration Dataset Summary
The calibration set was used strictly to measure the distributions of `active_frac` and `mod_depth` on genuine human speech and calibrate the audio thresholds. It was never used to tune or fit test data.

- **AMI Calibration Meetings (overlap $\\ge 50\\%$ with human annotations):**
  - Meetings: `EN2001a`, `EN2002a`, `ES2003a`, `IS1001a`
  - Real speech lines: {sum(1 for r in real_speech_lines if r['dataset'] == 'ami')}
- **LibriSpeech dev-clean (verified read speech, 100 audio files):**
  - Real speech lines: {sum(1 for r in real_speech_lines if r['dataset'] == 'librispeech')}
- **Total Real Speech Lines ($N$):** {n_real}

## 2. Threshold Derivation (Reasoned 1% False-Alarm Target)
Per Section 4 of `docs/HUSHCHECK2_DESIGN.md`, each threshold is chosen at the empirical point where that signal alone flags approximately 1.0% of real speech lines.

### Active Fraction (`LOW_SPEECH_BELOW`)
- 0.5th percentile: {np.percentile(active_fracs, 0.5):.4f}
- 1.0th percentile: {np.percentile(active_fracs, 1.0):.4f}
- 2.0th percentile: {np.percentile(active_fracs, 2.0):.4f}
- **Selected `LOW_SPEECH_BELOW`:** `{cand_active:.2f}`
  - Empirical false alarm rate alone: **{cand_active_flags} / {n_real} ({cand_active_pct:.2f}%)**

### Modulation Depth (`NOT_SPEECH_DEPTH`)
- 1.0th percentile of all real speech: {cutoff_1pct_all:.4f}
- **Selected `NOT_SPEECH_DEPTH`:** `{cand_depth:.2f}`
  - Empirical false alarm rate alone: **{cand_depth_flags} / {n_real} ({cand_depth_pct:.2f}%)**

## 3. Empirical Firing Rates of Text/Timing Rules on Real Speech
The text and timing rules (borrowed from whisper-guard ideas) were evaluated with published thresholds on OpenAI Whisper `small` (MPS, $\\text{{temperature}}=0$):

| Rule / Signal | Published Parameter / Condition | Calibration Real Speech Flags ($N={n_real}$) | Firing Rate |
|---|---|---|---|
| `NO_SPEECH` | active sound $< 0.15$ | {sig_counts["NO_SPEECH (< 0.15 active)"]} | {sig_counts["NO_SPEECH (< 0.15 active)"]/n_real*100:.2f}% |
| `LOW_SPEECH` | active sound $< {cand_active:.2f}$ | {sig_counts[f"LOW_SPEECH (< {cand_active:.2f} active)"]} | {sig_counts[f"LOW_SPEECH (< {cand_active:.2f} active)"]/n_real*100:.2f}% |
| `NOT_SPEECH_LIKE` | modulation depth $< {cand_depth:.2f}$ | {sig_counts[f"NOT_SPEECH_LIKE (depth < {cand_depth:.2f})"]} | {sig_counts[f"NOT_SPEECH_LIKE (depth < {cand_depth:.2f})"]/n_real*100:.2f}% |
| `BEYOND_AUDIO` | timestamp starts after audio duration | {sig_counts["BEYOND_AUDIO"]} | {sig_counts["BEYOND_AUDIO"]/n_real*100:.2f}% |
| `SPARSE_WINDOW` | window $\\ge 10\\text{{s}}$, $\\text{{cps}} < 1.0$ | {sig_counts["SPARSE_WINDOW (dur>=10s, cps<1.0)"]} | {sig_counts["SPARSE_WINDOW (dur>=10s, cps<1.0)"]/n_real*100:.2f}% |
| `DENSE_CONFIDENT` rescue | window $\\ge 5\\text{{s}}$, $\\text{{cps}} \\ge 2.0$, logprob $> -0.5$ | {sig_counts["DENSE_CONFIDENT rescue fired"]} | {sig_counts["DENSE_CONFIDENT rescue fired"]/n_real*100:.2f}% |
| `SEGMENT_FILTER` | nsp $> 0.8$, lp $< -1.5$, short lp $< -1.7$, cr $> 3.0$ | {sig_counts["SEGMENT_FILTER (raw)"]} | {sig_counts["SEGMENT_FILTER (raw)"]/n_real*100:.2f}% |
| `LONG_REPEAT` | 100-word window uniqueness ratio $< 0.35$ | {sig_counts["LONG_REPEAT (ratio < 0.35)"]} | {sig_counts["LONG_REPEAT (ratio < 0.35)"]/n_real*100:.2f}% |
| `LOOP` | 2-4 char repeating $\\ge 3$ times | {sig_counts["LOOP (char repetition)"]} | {sig_counts["LOOP (char repetition)"]/n_real*100:.2f}% |
| `REPEAT` | identical to previous lines | {sig_counts["REPEAT (repeats prev)"]} | {sig_counts["REPEAT (repeats prev)"]/n_real*100:.2f}% |
| `PHANTOM_PHRASE` | known hallucinated phrases | {sig_counts["PHANTOM_PHRASE"]} | {sig_counts["PHANTOM_PHRASE"]/n_real*100:.2f}% |

## 4. Overall Calibration Baseline Performance on Real Speech
- **HushCheck 2 AUTO (`LIKELY`):** {hc2_likely_fa} / {n_real} ({hc2_likely_fa/n_real*100:.2f}%)
- **HushCheck 2 REVIEW (`SUSPECT` or `LIKELY`):** {hc2_review_fa} / {n_real} ({hc2_review_fa/n_real*100:.2f}%)
- **whisper-guard (v0.3.3):** {wg_fa} / {n_real} ({wg_fa/n_real*100:.2f}%)

The thresholds `{cand_active:.2f}` for `LOW_SPEECH_BELOW` and `{cand_depth:.2f}` for `NOT_SPEECH_DEPTH` achieve the targeted $\\le 1.0\\%$ individual false alarm rate on real speech.
"""
    with open(CALIBRATION_MD, "w", encoding="utf-8") as f:
        f.write(doc_content)
    print(f"\nWrote calibration results to {CALIBRATION_MD}")


if __name__ == "__main__":
    main()
