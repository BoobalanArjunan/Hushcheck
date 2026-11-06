from __future__ import annotations

import csv
import json
from pathlib import Path

from .parse import Segment, format_srt


def _t(x):
    m, s = divmod(max(x, 0.0), 60)
    return f"{int(m)}:{s:05.2f}"


def text(a, show_suspect=True) -> str:
    likely, susp = a.of("LIKELY"), a.of("SUSPECT")
    n = len(a.findings)
    lines = [f"hushcheck: {a.name}  ({a.audio_s:.0f} s of audio, {n} transcript lines checked)",
             f"  LIKELY invented: {len(likely)}   SUSPECT: {len(susp)}   OK: {n - len(likely) - len(susp)}"]
    for w in a.warnings:
        lines.append(f"  note: {w}")
    for title, items in (("LIKELY invented text", likely), ("SUSPECT (look at these yourself)", susp if show_suspect else [])):
        if items:
            lines += ["", title + ":"]
            for f in items:
                lines.append(f"  [{_t(f.start)}-{_t(f.end)}] \"{f.text[:70]}\"")
                lines += [f"      - {c}: {d}" for c, d in f.reasons]
    if not likely and not susp:
        lines += ["", "No line looks invented."]
    lines += ["", "A line spoken over real talking cannot be checked this way: if the audio has speech there, hushcheck cannot tell if the words are right."]
    return "\n".join(lines)


def to_dict(a) -> dict:
    return {"name": a.name, "audio_seconds": round(a.audio_s, 2), "audio_check_reliable": a.reliable, "warnings": a.warnings,
            "lines_checked": len(a.findings), "likely": len(a.of("LIKELY")), "suspect": len(a.of("SUSPECT")), "likely_rate": round(a.likely_rate, 4),
            "findings": [{"index": f.index, "start": f.start, "end": f.end, "text": f.text, "level": f.level, "score": f.score,
                          "active_frac": None if f.active_frac is None else round(f.active_frac, 3),
                          "mod_depth": None if f.mod_depth is None else round(f.mod_depth, 3),
                          "reasons": [{"code": c, "detail": d} for c, d in f.reasons]} for f in a.findings]}


def write_json(a, path):
    Path(path).write_text(json.dumps(to_dict(a), indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv(a, path):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["index", "start_s", "end_s", "level", "score", "reasons", "text"])
        for f in a.findings:
            w.writerow([f.index, f"{f.start:.3f}", f"{f.end:.3f}", f.level, f.score, ";".join(c for c, _ in f.reasons), f.text])


def write_clean_srt(segs, a, path, drop_suspect=False):
    drop = {f.index for f in a.findings if f.level == "LIKELY" or (drop_suspect and f.level == "SUSPECT")}
    Path(path).write_text(format_srt([s for i, s in enumerate(segs) if i not in drop]), encoding="utf-8")
    return len(drop)
