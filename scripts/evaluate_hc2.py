"""HushCheck 2 Evaluation Runner.
Governed strictly by docs/HUSHCHECK2_EVALUATION_RULE.md (Tag: eval-spec-hc2-v1).
Supports --mode dry-run (on calibration data) and --mode eval (on test data).

Never touches test data when running in --mode dry-run.
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
import numpy as np

from hushcheck.analyze import LOW_SPEECH_BELOW, NOT_SPEECH_DEPTH
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
AMI_ZIP = ROOT / "eval_data" / "ami" / "ami_public_manual_1.6.2.zip"


# Wilson score confidence interval (secondary, optimistic)
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


class AMIGroundTruth:
    def __init__(self, zip_path: Path):
        self.meeting_intervals: dict[str, list[tuple[float, float]]] = {}
        with zipfile.ZipFile(zip_path) as z:
            for name in z.namelist():
                if name.startswith("words/") and name.endswith(".words.xml"):
                    m_id = name.split("/")[1].split(".")[0]
                    if m_id not in self.meeting_intervals:
                        self.meeting_intervals[m_id] = []
                    tree = ET.fromstring(z.read(name))
                    for w in tree.iter():
                        if not w.tag.endswith("w"):
                            continue
                        st = w.attrib.get("starttime")
                        et = w.attrib.get("endtime")
                        if st is not None and et is not None:
                            s, e = float(st), float(et)
                            if e > s:
                                self.meeting_intervals[m_id].append((s, e))

        for m_id, raw_intervals in self.meeting_intervals.items():
            raw_intervals.sort()
            merged = []
            for s, e in raw_intervals:
                if not merged or s > merged[-1][1]:
                    merged.append([s, e])
                else:
                    merged[-1][1] = max(merged[-1][1], e)
            self.meeting_intervals[m_id] = [(s, e) for s, e in merged]

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


def run_text_only(raw_segments: list[dict]) -> list[bool]:
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


def evaluate_hc2_segments(audio_path: Path, segments: list[dict]) -> list[dict]:
    audio = load_audio(audio_path)

    file_windows = windows(segments)
    seg_windows = []
    for w in file_windows:
        wsig = window_signals(w)
        for s in w["segs"]:
            seg_windows.append((w, wsig))

    long_rep_flags = compute_segment_long_repeats(segments)

    out = []
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

        audio_signals = {}
        if ev.beyond_audio:
            audio_signals["BEYOND_AUDIO"] = 3
        elif ev.active_frac < 0.15:
            audio_signals["NO_SPEECH"] = 3
        else:
            if ev.active_frac < LOW_SPEECH_BELOW:
                audio_signals["LOW_SPEECH"] = 1
            if ev.mod_depth is not None and ev.mod_depth < NOT_SPEECH_DEPTH:
                audio_signals["NOT_SPEECH_LIKE"] = 1

        text_signals = {}
        if sparse:
            text_signals["SPARSE_WINDOW"] = 2
        if seg_filter:
            text_signals["SEGMENT_FILTER"] = 1
        if long_rep:
            text_signals["LONG_REPEAT"] = 1
        if loop_flag:
            text_signals["LOOP"] = 1
        if rep_prev:
            text_signals["REPEAT"] = 1
        if ph_match:
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

        is_collapse = bool(loop_flag or long_rep or rep_prev)

        out.append({
            "start": st,
            "end": et,
            "text": text,
            "level": level,
            "score": total_score,
            "audio_signals": audio_signals,
            "text_signals": text_signals,
            "active_frac": ev.active_frac,
            "mod_depth": ev.mod_depth,
            "likely": (level == "LIKELY"),
            "review": (level in ("LIKELY", "SUSPECT")),
            "is_collapse": is_collapse,
        })
        prev_texts.append(text)

    return out


def cluster_bootstrap_eval(
    recordings_data: list[dict],
    n_resamples: int = 10000,
    seed: int = 42,
) -> dict:
    rng = np.random.default_rng(seed)
    n_rec = len(recordings_data)

    rec_real_total = np.array([r["n_real"] for r in recordings_data])
    rec_real_fa_likely = np.array([r["n_real_fa_likely"] for r in recordings_data])
    rec_real_fa_review = np.array([r["n_real_fa_review"] for r in recordings_data])
    rec_real_fa_wg = np.array([r["n_real_fa_wg"] for r in recordings_data])

    rec_real_non_collapse = np.array([r["n_real_non_collapse"] for r in recordings_data])
    rec_real_fa_likely_non_collapse = np.array([r["n_real_fa_likely_non_collapse"] for r in recordings_data])
    rec_real_fa_review_non_collapse = np.array([r["n_real_fa_review_non_collapse"] for r in recordings_data])
    rec_real_fa_wg_non_collapse = np.array([r["n_real_fa_wg_non_collapse"] for r in recordings_data])

    rec_sil_total = np.array([r["n_silence"] for r in recordings_data])
    rec_sil_caught_likely = np.array([r["n_silence_caught_likely"] for r in recordings_data])

    rec_inv_total = np.array([r["n_invented"] for r in recordings_data])
    rec_inv_caught_review = np.array([r["n_inv_caught_review"] for r in recordings_data])
    rec_inv_caught_wg = np.array([r["n_inv_caught_wg"] for r in recordings_data])
    rec_inv_caught_textonly = np.array([r["n_inv_caught_textonly"] for r in recordings_data])

    boot_likely_far = []
    boot_review_far = []
    boot_likely_far_non_collapse = []
    boot_review_far_non_collapse = []
    boot_silence_recall = []
    boot_review_recall = []
    boot_diff_recall_wg = []
    boot_diff_recall_textonly = []

    for _ in range(n_resamples):
        sample_indices = rng.choice(n_rec, size=n_rec, replace=True)

        tot_real = np.sum(rec_real_total[sample_indices])
        if tot_real > 0:
            far_likely = np.sum(rec_real_fa_likely[sample_indices]) / tot_real
            far_review = np.sum(rec_real_fa_review[sample_indices]) / tot_real
            boot_likely_far.append(far_likely)
            boot_review_far.append(far_review)

        tot_real_nc = np.sum(rec_real_non_collapse[sample_indices])
        if tot_real_nc > 0:
            far_likely_nc = np.sum(rec_real_fa_likely_non_collapse[sample_indices]) / tot_real_nc
            far_review_nc = np.sum(rec_real_fa_review_non_collapse[sample_indices]) / tot_real_nc
            boot_likely_far_non_collapse.append(far_likely_nc)
            boot_review_far_non_collapse.append(far_review_nc)

        tot_sil = np.sum(rec_sil_total[sample_indices])
        if tot_sil > 0:
            rec_sil = np.sum(rec_sil_caught_likely[sample_indices]) / tot_sil
            boot_silence_recall.append(rec_sil)

        tot_inv = np.sum(rec_inv_total[sample_indices])
        if tot_inv > 0:
            rec_rev = np.sum(rec_inv_caught_review[sample_indices]) / tot_inv
            rec_wg = np.sum(rec_inv_caught_wg[sample_indices]) / tot_inv
            rec_to = np.sum(rec_inv_caught_textonly[sample_indices]) / tot_inv
            boot_review_recall.append(rec_rev)
            boot_diff_recall_wg.append(rec_rev - rec_wg)
            boot_diff_recall_textonly.append(rec_rev - rec_to)

    def ci95(arr: list[float]) -> tuple[float, float]:
        if not arr:
            return 0.0, 0.0
        return float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))

    return {
        "likely_far_ci": ci95(boot_likely_far),
        "review_far_ci": ci95(boot_review_far),
        "likely_far_nc_ci": ci95(boot_likely_far_non_collapse),
        "review_far_nc_ci": ci95(boot_review_far_non_collapse),
        "silence_recall_ci": ci95(boot_silence_recall),
        "review_recall_ci": ci95(boot_review_recall),
        "diff_recall_wg_ci": ci95(boot_diff_recall_wg),
        "diff_recall_textonly_ci": ci95(boot_diff_recall_textonly),
    }


def run_pipeline(mode: str = "dry-run"):
    ami_gt = AMIGroundTruth(AMI_ZIP)

    if mode == "dry-run":
        audio_dir = ROOT / "calibration_data"
        json_dir = ROOT / "calibration_json"
        out_report = ROOT / "calibration_dry_run_report.md"
        out_ambig = ROOT / "calibration_ambiguous_lines.csv"
        print("=== EXECUTING DRY-RUN ON CALIBRATION DATA ===")
    else:
        audio_dir = ROOT / "test_data"
        json_dir = ROOT / "test_json"
        out_report = ROOT / "results.md"
        out_ambig = ROOT / "ambiguous_lines.csv"
        print("=== EXECUTING SINGLE EVALUATION ON TEST DATA ===")

    audio_files = []
    for sub in ["ami", "music", "noise", "librispeech"]:
        p = audio_dir / sub
        if p.exists():
            for f in sorted(p.iterdir()):
                if f.suffix.lower() in [".wav", ".flac", ".ogg", ".mp3"]:
                    audio_files.append((sub, f))

    print(f"Found {len(audio_files)} recordings in {audio_dir}.")

    all_lines = []
    ambiguous_lines = []
    recordings_data = []

    for sub, audio_file in audio_files:
        stem = audio_file.stem
        if sub == "librispeech":
            # Support dev-clean (calib) or test-clean (test)
            libri_json = json_dir / "librispeech_dev_clean_100.json"
            if not libri_json.exists():
                libri_json = json_dir / "librispeech_test_clean_100.json"
            if not libri_json.exists():
                continue
            with open(libri_json, encoding="utf-8") as jf:
                libri_data = json.load(jf)
            if stem not in libri_data:
                continue
            segments = libri_data[stem].get("segments", [])
        else:
            json_file = json_dir / f"{stem}.json"
            if not json_file.exists():
                print(f"Transcript missing for {audio_file.name}, skipping.")
                continue
            with open(json_file, encoding="utf-8") as jf:
                data = json.load(jf)
            segments = data.get("segments", [])

        hc2_eval = evaluate_hc2_segments(audio_file, segments)
        wg_flags = run_whisper_guard(segments)
        to_flags = run_text_only(segments)

        rec_stats = {
            "name": stem,
            "category": sub,
            "n_lines": len(segments),
            "n_real": 0,
            "n_real_fa_likely": 0,
            "n_real_fa_review": 0,
            "n_real_fa_wg": 0,
            "n_real_fa_textonly": 0,
            "n_real_non_collapse": 0,
            "n_real_fa_likely_non_collapse": 0,
            "n_real_fa_review_non_collapse": 0,
            "n_real_fa_wg_non_collapse": 0,
            "n_silence": 0,
            "n_silence_caught_likely": 0,
            "n_silence_caught_review": 0,
            "n_silence_caught_wg": 0,
            "n_silence_caught_textonly": 0,
            "n_invented": 0,
            "n_inv_caught_likely": 0,
            "n_inv_caught_review": 0,
            "n_inv_caught_wg": 0,
            "n_inv_caught_textonly": 0,
            "n_ambiguous": 0,
        }

        meeting_id = stem.split(".")[0] if sub == "ami" else None

        for idx, seg in enumerate(segments):
            st, et = seg.get("start", 0.0), seg.get("end", 0.0)
            text = seg.get("text", "").strip()
            hc2 = hc2_eval[idx]
            wg = wg_flags[idx]
            to = to_flags[idx]

            if sub in ("music", "noise"):
                label = "invented"
                line_cat = sub
            elif sub == "librispeech":
                label = "real"
                line_cat = "read_speech"
            elif sub == "ami":
                ov = ami_gt.get_overlap_ratio(meeting_id, st, et)
                if ov >= 0.50:
                    label = "real"
                    line_cat = "ami_speech"
                elif ov < 0.20:
                    label = "invented"
                    line_cat = "ami_silence"
                else:
                    label = "ambiguous"
                    line_cat = "ami_ambiguous"
            else:
                label = "unknown"
                line_cat = "unknown"

            line_entry = {
                "recording": stem,
                "category": line_cat,
                "label": label,
                "start": st,
                "end": et,
                "text": text,
                "hc2_level": hc2["level"],
                "hc2_score": hc2["score"],
                "hc2_likely": hc2["likely"],
                "hc2_review": hc2["review"],
                "wg_flag": wg,
                "text_only_flag": to,
                "is_collapse": hc2["is_collapse"],
            }

            if label == "ambiguous":
                rec_stats["n_ambiguous"] += 1
                ambiguous_lines.append(line_entry)
                continue

            all_lines.append(line_entry)

            if label == "real":
                rec_stats["n_real"] += 1
                if hc2["likely"]:
                    rec_stats["n_real_fa_likely"] += 1
                if hc2["review"]:
                    rec_stats["n_real_fa_review"] += 1
                if wg:
                    rec_stats["n_real_fa_wg"] += 1
                if to:
                    rec_stats["n_real_fa_textonly"] += 1

                # Exploratory non-collapse tracking
                if not hc2["is_collapse"]:
                    rec_stats["n_real_non_collapse"] += 1
                    if hc2["likely"]:
                        rec_stats["n_real_fa_likely_non_collapse"] += 1
                    if hc2["review"]:
                        rec_stats["n_real_fa_review_non_collapse"] += 1
                    if wg:
                        rec_stats["n_real_fa_wg_non_collapse"] += 1

            elif label == "invented":
                rec_stats["n_invented"] += 1
                if hc2["likely"]:
                    rec_stats["n_inv_caught_likely"] += 1
                if hc2["review"]:
                    rec_stats["n_inv_caught_review"] += 1
                if wg:
                    rec_stats["n_inv_caught_wg"] += 1
                if to:
                    rec_stats["n_inv_caught_textonly"] += 1

                if line_cat == "ami_silence":
                    rec_stats["n_silence"] += 1
                    if hc2["likely"]:
                        rec_stats["n_silence_caught_likely"] += 1
                    if hc2["review"]:
                        rec_stats["n_silence_caught_review"] += 1
                    if wg:
                        rec_stats["n_silence_caught_wg"] += 1
                    if to:
                        rec_stats["n_silence_caught_textonly"] += 1

        recordings_data.append(rec_stats)

    with open(out_ambig, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["recording", "start", "end", "text", "hc2_level", "hc2_score", "wg_flag"])
        for amb in ambiguous_lines:
            writer.writerow([amb["recording"], f"{amb['start']:.2f}", f"{amb['end']:.2f}", amb["text"], amb["hc2_level"], amb["hc2_score"], amb["wg_flag"]])
    print(f"Wrote {len(ambiguous_lines)} ambiguous lines to {out_ambig.name}")

    total_real = sum(r["n_real"] for r in recordings_data)
    total_real_nc = sum(r["n_real_non_collapse"] for r in recordings_data)
    total_invented = sum(r["n_invented"] for r in recordings_data)
    total_silence = sum(r["n_silence"] for r in recordings_data)
    total_ambiguous = len(ambiguous_lines)
    n_recordings = len(recordings_data)

    print(f"\n================ EVALUATION SUMMARY ({mode}) ================")
    print(f"Recordings evaluated:    {n_recordings}")
    print(f"Total lines evaluated:   {len(all_lines) + total_ambiguous}")
    print(f"  - Real speech lines:   {total_real} (excluding decoder collapses: {total_real_nc})")
    print(f"  - Invented lines:      {total_invented} (AMI silence-pause: {total_silence})")
    print(f"  - Ambiguous lines:     {total_ambiguous} (excluded)")

    inconclusive = (total_real < 300 or total_invented < 100 or n_recordings < 10)
    if inconclusive:
        print(f"\n*** INCONCLUSIVE: Sample size below pre-registered rules (real: {total_real}/300, inv: {total_invented}/100, rec: {n_recordings}/10) ***")

    # Point estimates & Wilson intervals (Primary Claim)
    tot_likely_fa = sum(r["n_real_fa_likely"] for r in recordings_data)
    p_likely_far, w_likely_far_low, w_likely_far_high = wilson_interval(tot_likely_fa, total_real)

    tot_review_fa = sum(r["n_real_fa_review"] for r in recordings_data)
    p_review_far, w_review_far_low, w_review_far_high = wilson_interval(tot_review_fa, total_real)

    # Exploratory non-collapse false alarm rates
    tot_likely_fa_nc = sum(r["n_real_fa_likely_non_collapse"] for r in recordings_data)
    p_likely_far_nc = tot_likely_fa_nc / max(1, total_real_nc)

    tot_review_fa_nc = sum(r["n_real_fa_review_non_collapse"] for r in recordings_data)
    p_review_far_nc = tot_review_fa_nc / max(1, total_real_nc)

    tot_wg_fa_nc = sum(r["n_real_fa_wg_non_collapse"] for r in recordings_data)
    p_wg_far_nc = tot_wg_fa_nc / max(1, total_real_nc)

    tot_sil_caught_likely = sum(r["n_silence_caught_likely"] for r in recordings_data)
    p_sil_rec, w_sil_rec_low, w_sil_rec_high = wilson_interval(tot_sil_caught_likely, total_silence)

    tot_inv_caught_review = sum(r["n_inv_caught_review"] for r in recordings_data)
    p_rev_rec, w_rev_rec_low, w_rev_rec_high = wilson_interval(tot_inv_caught_review, total_invented)

    tot_inv_caught_wg = sum(r["n_inv_caught_wg"] for r in recordings_data)
    p_wg_rec, w_wg_rec_low, w_wg_rec_high = wilson_interval(tot_inv_caught_wg, total_invented)

    tot_inv_caught_to = sum(r["n_inv_caught_textonly"] for r in recordings_data)
    p_to_rec, w_to_rec_low, w_to_rec_high = wilson_interval(tot_inv_caught_to, total_invented)

    tot_likely_flags = tot_likely_fa + sum(r["n_inv_caught_likely"] for r in recordings_data)

    print("Running 10,000 cluster bootstrap resamples over recordings...")
    boot_res = cluster_bootstrap_eval(recordings_data, n_resamples=10000, seed=42)

    claim_a_far_ok = (p_likely_far <= 0.010 and boot_res["likely_far_ci"][1] <= 0.030)
    claim_a_rec_ok = (p_sil_rec >= 0.70 and boot_res["silence_recall_ci"][0] >= 0.55)
    claim_a_flags_ok = (tot_likely_flags >= 30)
    claim_a_pass = (claim_a_far_ok and claim_a_rec_ok and claim_a_flags_ok and not inconclusive)

    claim_b_rec_wg_ok = (boot_res["diff_recall_wg_ci"][0] > 0.0)
    claim_b_rec_to_ok = (boot_res["diff_recall_textonly_ci"][0] > 0.0)
    claim_b_far_ok = (p_review_far <= 0.020 and boot_res["review_far_ci"][1] <= 0.040)
    claim_b_pass = (claim_b_rec_wg_ok and claim_b_rec_to_ok and claim_b_far_ok and not inconclusive)

    print("\n--- RESULTS ---")
    print(f"Claim (a) AUTO (LIKELY):")
    print(f"  Real FAR (Strict Claim):              {p_likely_far*100:.2f}% (Cluster 95% CI: {boot_res['likely_far_ci'][0]*100:.2f}% - {boot_res['likely_far_ci'][1]*100:.2f}%) [target <= 1.0% point, <= 3.0% CI upper] -> {'PASS' if claim_a_far_ok else 'FAIL'}")
    print(f"  * Exploratory (excl. decoder collapse): {p_likely_far_nc*100:.2f}% ({tot_likely_fa_nc}/{total_real_nc}) [Cluster 95% CI: {boot_res['likely_far_nc_ci'][0]*100:.2f}% - {boot_res['likely_far_nc_ci'][1]*100:.2f}%]")
    print(f"  Silence Recall:                       {p_sil_rec*100:.2f}% (Cluster 95% CI: {boot_res['silence_recall_ci'][0]*100:.2f}% - {boot_res['silence_recall_ci'][1]*100:.2f}%) [target >= 70.0% point, >= 55.0% CI lower] -> {'PASS' if claim_a_rec_ok else 'FAIL'}")
    print(f"  LIKELY Flags:                         {tot_likely_flags} [target >= 30] -> {'PASS' if claim_a_flags_ok else 'FAIL'}")
    print(f"  Overall Claim (a): {'PASSED' if claim_a_pass else 'FAILED'}")

    print(f"\nClaim (b) REVIEW (LIKELY+SUSPECT):")
    print(f"  Invented Recall vs whisper-guard paired diff: {p_rev_rec*100 - p_wg_rec*100:+.2f}% (Cluster 95% CI: {boot_res['diff_recall_wg_ci'][0]*100:+.2f}% to {boot_res['diff_recall_wg_ci'][1]*100:+.2f}%) [target > 0] -> {'PASS' if claim_b_rec_wg_ok else 'FAIL'}")
    print(f"  Invented Recall vs text-only paired diff:     {p_rev_rec*100 - p_to_rec*100:+.2f}% (Cluster 95% CI: {boot_res['diff_recall_textonly_ci'][0]*100:+.2f}% to {boot_res['diff_recall_textonly_ci'][1]*100:+.2f}%) [target > 0] -> {'PASS' if claim_b_rec_to_ok else 'FAIL'}")
    print(f"  Real FAR (Strict Claim):              {p_review_far*100:.2f}% (Cluster 95% CI: {boot_res['review_far_ci'][0]*100:.2f}% - {boot_res['review_far_ci'][1]*100:.2f}%) [target <= 2.0% point, <= 4.0% CI upper] -> {'PASS' if claim_b_far_ok else 'FAIL'}")
    print(f"  * Exploratory (excl. decoder collapse): {p_review_far_nc*100:.2f}% ({tot_review_fa_nc}/{total_real_nc}) [Cluster 95% CI: {boot_res['review_far_nc_ci'][0]*100:.2f}% - {boot_res['review_far_nc_ci'][1]*100:.2f}%]")
    print(f"  Overall Claim (b): {'PASSED' if claim_b_pass else 'FAILED'}")

    md = f"""# HushCheck 2 Evaluation Report ({mode.upper()})

**Date:** {json.loads(json.dumps(str(np.datetime64('now'))))}
**Governing Rule:** `docs/HUSHCHECK2_EVALUATION_RULE.md` (Tag: `eval-spec-hc2-v1`)
**Status:** {'INCONCLUSIVE' if inconclusive else ('PASSED' if (claim_a_pass and claim_b_pass) else 'STOPPED')}

## 1. Summary of Claims
| Claim | Metric | Point Estimate | Cluster-Bootstrap 95% CI | Target | Status |
|---|---|---|---|---|---|
| **Claim (a): AUTO (LIKELY)** | Real Speech False-Alarm Rate (Strict) | {p_likely_far*100:.2f}% ({tot_likely_fa}/{total_real}) | [{boot_res['likely_far_ci'][0]*100:.2f}%, {boot_res['likely_far_ci'][1]*100:.2f}%] | $\\le 1.0\\%$, upper $\\le 3.0\\%$ | {'PASS' if claim_a_far_ok else 'FAIL'} |
| | *Exploratory: Excl. Decoder Collapse* | *{p_likely_far_nc*100:.2f}% ({tot_likely_fa_nc}/{total_real_nc})* | *[{boot_res['likely_far_nc_ci'][0]*100:.2f}%, {boot_res['likely_far_nc_ci'][1]*100:.2f}%]* | *(exploratory, not claim)* | *Info* |
| | AMI Silence-Pause Recall | {p_sil_rec*100:.2f}% ({tot_sil_caught_likely}/{total_silence}) | [{boot_res['silence_recall_ci'][0]*100:.2f}%, {boot_res['silence_recall_ci'][1]*100:.2f}%] | $\\ge 70.0\\%$, lower $\\ge 55.0\\%$ | {'PASS' if claim_a_rec_ok else 'FAIL'} |
| | Total LIKELY Flags | {tot_likely_flags} | — | $\\ge 30$ | {'PASS' if claim_a_flags_ok else 'FAIL'} |
| **Claim (b): REVIEW** | Recall vs whisper-guard diff | {p_rev_rec*100 - p_wg_rec*100:+.2f}% | [{boot_res['diff_recall_wg_ci'][0]*100:+.2f}%, {boot_res['diff_recall_wg_ci'][1]*100:+.2f}%] | $> 0$ (paired bootstrap) | {'PASS' if claim_b_rec_wg_ok else 'FAIL'} |
| | Recall vs text-only diff | {p_rev_rec*100 - p_to_rec*100:+.2f}% | [{boot_res['diff_recall_textonly_ci'][0]*100:+.2f}%, {boot_res['diff_recall_textonly_ci'][1]*100:+.2f}%] | $> 0$ (paired bootstrap) | {'PASS' if claim_b_rec_to_ok else 'FAIL'} |
| | Real Speech False-Alarm Rate (Strict) | {p_review_far*100:.2f}% ({tot_review_fa}/{total_real}) | [{boot_res['review_far_ci'][0]*100:.2f}%, {boot_res['review_far_ci'][1]*100:.2f}%] | $\\le 2.0\\%$, upper $\\le 4.0\\%$ | {'PASS' if claim_b_far_ok else 'FAIL'} |
| | *Exploratory: Excl. Decoder Collapse* | *{p_review_far_nc*100:.2f}% ({tot_review_fa_nc}/{total_real_nc})* | *[{boot_res['review_far_nc_ci'][0]*100:.2f}%, {boot_res['review_far_nc_ci'][1]*100:.2f}%]* | *(exploratory, not claim)* | *Info* |

## 2. Overall Comparison Across Methods ($N_{{real}}={total_real}$, $N_{{invented}}={total_invented}$)
| Method | Mode | Invented Recall (All {total_invented}) | AMI Silence Recall ({total_silence}) | Real Speech False Alarms ({total_real}) | Real FA Excl. Collapse ({total_real_nc}) |
|---|---|---|---|---|---|
| **HushCheck 2** | AUTO (`LIKELY`) | {sum(r['n_inv_caught_likely'] for r in recordings_data)/max(1,total_invented)*100:.1f}% | {p_sil_rec*100:.1f}% | {tot_likely_fa}/{total_real} ({p_likely_far*100:.2f}%) | {tot_likely_fa_nc}/{total_real_nc} ({p_likely_far_nc*100:.2f}%) |
| **HushCheck 2** | REVIEW (`LIKELY+SUS`) | {p_rev_rec*100:.1f}% | {sum(r['n_silence_caught_review'] for r in recordings_data)/max(1,total_silence)*100:.1f}% | {tot_review_fa}/{total_real} ({p_review_far*100:.2f}%) | {tot_review_fa_nc}/{total_real_nc} ({p_review_far_nc*100:.2f}%) |
| **whisper-guard (v0.3.3)** | Default filter | {p_wg_rec*100:.1f}% | {sum(r['n_silence_caught_wg'] for r in recordings_data)/max(1,total_silence)*100:.1f}% | {sum(r['n_real_fa_wg'] for r in recordings_data)}/{total_real} ({sum(r['n_real_fa_wg'] for r in recordings_data)/max(1,total_real)*100:.2f}%) | {tot_wg_fa_nc}/{total_real_nc} ({p_wg_far_nc*100:.2f}%) |
| **Text-only Baseline** | Regex/phantom | {p_to_rec*100:.1f}% | {sum(r['n_silence_caught_textonly'] for r in recordings_data)/max(1,total_silence)*100:.1f}% | {sum(r['n_real_fa_textonly'] for r in recordings_data)}/{total_real} ({sum(r['n_real_fa_textonly'] for r in recordings_data)/max(1,total_real)*100:.2f}%) | — |

## 3. Per-Recording Table
| Recording | Category | Lines | Real Lines | Real FA (LIKELY) | Real FA (Review) | Real FA (WG) | Invented Lines | Inv Caught (LIKELY) | Inv Caught (Review) | Inv Caught (WG) | Ambiguous |
|---|---|---|---|---|---|---|---|---|---|---|---|
"""
    for r in recordings_data:
        md += f"| `{r['name']}` | {r['category']} | {r['n_lines']} | {r['n_real']} | {r['n_real_fa_likely']} | {r['n_real_fa_review']} | {r['n_real_fa_wg']} | {r['n_invented']} | {r['n_inv_caught_likely']} | {r['n_inv_caught_review']} | {r['n_inv_caught_wg']} | {r['n_ambiguous']} |\n"

    with open(out_report, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Wrote report to {out_report.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["dry-run", "eval"], default="dry-run", help="Evaluation mode")
    args = parser.parse_args()
    run_pipeline(args.mode)
