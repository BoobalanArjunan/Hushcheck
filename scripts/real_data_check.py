"""Real-data check for hushcheck: on REAL Whisper output, does it catch invented lines better than the other approaches?

You need: (1) audio files that contain silence, music or noise stretches (where Whisper tends to invent text), (2) Whisper JSON for each file, made with
the original openai-whisper CLI (`whisper file.wav --output_format json`) or faster-whisper saved as {"segments":[{"start","end","text","no_speech_prob",
"avg_logprob","compression_ratio"}]}, same base name as the audio, (3) a labels CSV made by LISTENING: one row per invented stretch

    file,start_s,end_s
    meeting1.wav,62.0,70.5

A transcript line counts as "invented" when its middle falls inside a labelled stretch; every other line counts as real. Mark the stretches before you
run anything, and do not change thresholds and re-test on the same files.

    python scripts/real_data_check.py --audio-dir audio/ --transcripts-dir json/ --labels labels.csv --out real_check

Compared (per transcript line: precision, recall, false alarms among real lines):
  hushcheck LIKELY, hushcheck LIKELY+SUSPECT, text checks only (phrase list, loops, repeats: hushcheck with the audio part switched off),
  whisper-guard if installed (pip install whisper-guard; it uses the Whisper numbers in your JSON). Your files are not changed. Writes <out>/results.md.
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from hushcheck import analyse_segments, load_audio  # noqa: E402
from hushcheck import textchecks as tc  # noqa: E402
from hushcheck.parse import Segment, parse_json  # noqa: E402

AUDIO_EXT = {".wav", ".flac", ".ogg", ".opus", ".mp3"}


def read_labels(path):
    spans = defaultdict(list)
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            spans[Path(r["file"]).stem].append((float(r["start_s"]), float(r["end_s"])))
    return spans


def is_invented(seg, spans):
    mid = (seg["start"] + seg["end"]) / 2
    return any(s <= mid <= e for s, e in spans)


def text_only(segs):
    out, prev = [], []
    for s in segs:
        out.append(bool(s.text.strip()) and bool(tc.phantom_match(s.text) or tc.loop_kind(s.text) or tc.repeats_previous(s.text, prev)))
        prev.append(s.text)
    return out


def guard_flags(raw):
    try:
        from whisper_guard import filter_hallucinations
    except ImportError:
        return None
    items = []
    for i, d in enumerate(raw):
        d = dict(copy.deepcopy(d))
        d["_i"] = i
        items.append(d)
    kept = {d["_i"] for d in filter_hallucinations(items)}
    return [i not in kept for i in range(len(raw))]


def tally(name, rows, flags, truth):
    tp = sum(f and t for f, t in zip(flags, truth))
    fp = sum(f and not t for f, t in zip(flags, truth))
    fn = sum((not f) and t for f, t in zip(flags, truth))
    real = sum(not t for t in truth)
    p, r = tp / max(1, tp + fp), tp / max(1, tp + fn)
    rows.append((name, tp, fn, fp, real, p, r, fp / max(1, real)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--audio-dir", required=True)
    ap.add_argument("--transcripts-dir", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--out", default="real_check")
    a = ap.parse_args()
    spans = read_labels(a.labels)
    truth, f_like, f_any, f_text, f_guard = [], [], [], [], []
    guard_ok, used, missing = True, 0, []
    for ap_ in sorted(Path(a.audio_dir).iterdir()):
        if ap_.suffix.lower() not in AUDIO_EXT:
            continue
        jp = Path(a.transcripts_dir) / (ap_.stem + ".json")
        if not jp.exists():
            missing.append(ap_.name)
            continue
        raw = json.loads(jp.read_text(encoding="utf-8"))
        raw = raw["segments"] if isinstance(raw, dict) else raw
        raw = [d for d in raw if str(d.get("text", "")).strip()]
        segs = parse_json(json.dumps(raw), jp.name)
        an = analyse_segments(segs, load_audio(ap_), ap_.name)
        by_idx = {f.index: f for f in an.findings}
        g = guard_flags(raw)
        guard_ok = guard_ok and g is not None
        for i, d in enumerate(raw):
            truth.append(is_invented(d, spans.get(ap_.stem, [])))
            f = by_idx[i]
            f_like.append(f.level == "LIKELY")
            f_any.append(f.level != "OK")
            f_guard.append(g[i] if g else False)
        f_text.extend(text_only(segs))
        used += 1
    if not truth:
        sys.exit("no matching audio + transcript pairs found")
    rows = []
    tally("hushcheck LIKELY", rows, f_like, truth)
    tally("hushcheck LIKELY+SUSPECT", rows, f_any, truth)
    tally("text checks only", rows, f_text, truth)
    if guard_ok:
        tally("whisper-guard", rows, f_guard, truth)
    n_inv = sum(truth)
    md = [f"# hushcheck real-data check", "", f"{used} files, {len(truth)} transcript lines, {n_inv} labelled invented, {len(truth) - n_inv} real.", ""]
    if missing:
        md.append(f"No transcript JSON for: {', '.join(missing)}\n")
    if not guard_ok:
        md.append("whisper-guard is not installed, so it is missing from the table (pip install whisper-guard).\n")
    md += ["| method | invented caught | invented missed | false alarms | precision | recall | false-alarm rate on real lines |", "|---|---|---|---|---|---|---|"]
    for name, tp, fn, fp, real, p, r, far in rows:
        md.append(f"| {name} | {tp} | {fn} | {fp} | {p:.0%} | {r:.0%} | {far:.1%} |")
    md += ["", "Decision rule (set before looking): hushcheck LIKELY must catch clearly more invented lines than whisper-guard with the same or fewer false alarms,",
           "and must beat 'text checks only' (otherwise the audio part adds nothing). With fewer than about 30 invented lines the table is too small to trust."]
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "results.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
