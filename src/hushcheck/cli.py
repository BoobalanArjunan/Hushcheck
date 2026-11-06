from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, report
from .analyze import analyse_segments
from .evidence import load_audio
from .parse import HushError, read_transcript, read_text
from . import textchecks as tc


def build_parser():
    p = argparse.ArgumentParser(prog="hushcheck", description="Find transcript lines that a speech-to-text engine invented over silence or music.")
    p.add_argument("--version", action="version", version=f"hushcheck {__version__}")
    sub = p.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="check one audio file against its transcript (.srt, .vtt or Whisper-style .json)")
    c.add_argument("audio")
    c.add_argument("transcript")
    c.add_argument("--json", metavar="FILE", help="write a JSON report")
    c.add_argument("--csv", metavar="FILE", help="write a CSV with one row per line")
    c.add_argument("--write-clean", metavar="FILE.srt", help="write a copy of the transcript without the LIKELY lines (your original is never changed)")
    c.add_argument("--drop-suspect", action="store_true", help="with --write-clean, also drop SUSPECT lines")
    c.add_argument("--phrases", metavar="FILE", help="text file with more invented phrases to look for, one per line")
    c.add_argument("--max-likely-rate", type=float, metavar="X", help="exit with code 1 if more than this share (0 to 1) of lines is LIKELY")
    c.add_argument("--hide-suspect", action="store_true", help="do not list SUSPECT lines")
    return p


def main(argv=None) -> int:
    p = build_parser()
    a = p.parse_args(argv)
    if a.cmd != "check":
        p.print_help()
        return 2
    try:
        segs = read_transcript(a.transcript)
        phrases = tc.PHANTOM_PHRASES
        if a.phrases:
            extra = [ln.strip() for ln in read_text(Path(a.phrases)).splitlines() if ln.strip()]
            phrases = tc.PHANTOM_PHRASES + tuple(extra)
        if a.max_likely_rate is not None and not 0 <= a.max_likely_rate <= 1:
            raise HushError("--max-likely-rate must be between 0 and 1")
        res = analyse_segments(segs, load_audio(a.audio), Path(a.audio).name, phrases)
        print(report.text(res, show_suspect=not a.hide_suspect))
        if a.json:
            report.write_json(res, a.json)
        if a.csv:
            report.write_csv(res, a.csv)
        if a.write_clean:
            n = report.write_clean_srt(segs, res, a.write_clean, a.drop_suspect)
            print(f"\nWrote {a.write_clean} without {n} line(s). Your original transcript was not changed.")
    except HushError as e:
        print(f"hushcheck: {e}", file=sys.stderr)
        return 2
    if a.max_likely_rate is not None and res.likely_rate > a.max_likely_rate:
        print(f"\nFAIL: {res.likely_rate:.1%} of lines are LIKELY invented (limit {a.max_likely_rate:.1%})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
