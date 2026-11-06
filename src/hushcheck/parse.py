"""Reading a transcript: SRT, WebVTT, or Whisper-style JSON. Every reader returns a list of Segment(start, end, text), seconds."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


class HushError(ValueError):
    """A problem the user can fix (bad input or option). The CLI shows it without a traceback."""


@dataclass
class Segment:
    start: float
    end: float
    text: str = ""
    extra: dict = field(default_factory=dict)   # any other keys of a JSON segment (kept, never used for the verdict)


_TIME = r"(?:(\d+):)?(\d{1,2}):(\d{2})[,.](\d{1,3})"
_ARROW = re.compile(rf"^\s*{_TIME}\s*-->\s*{_TIME}")


def _t(h, m, s, ms) -> float:
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000.0


def read_text(path: Path) -> str:
    try:
        return Path(path).read_bytes().decode("utf-8-sig", errors="replace")
    except OSError as e:
        raise HushError(f"cannot read {Path(path).name}: {e}") from None


def parse_subtitles(text: str, name: str = "transcript") -> list:
    segs, lines, i = [], text.replace("\r\n", "\n").replace("\r", "\n").split("\n"), 0
    while i < len(lines):
        m = _ARROW.match(lines[i])
        if not m:
            i += 1
            continue
        g = m.groups()
        i += 1
        body = []
        while i < len(lines) and lines[i].strip() != "":
            body.append(lines[i].strip())
            i += 1
        segs.append(Segment(_t(*g[:4]), _t(*g[4:]), " ".join(body)))
    if not segs:
        raise HushError(f"{name}: no 'start --> end' lines found (is this an SRT or VTT file?)")
    return segs


def parse_json(text: str, name: str = "transcript") -> list:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise HushError(f"{name}: not valid JSON ({e})") from None
    if isinstance(data, dict):
        data = data.get("segments")
    if not isinstance(data, list):
        raise HushError(f"{name}: expected a list of segments, or an object with a 'segments' list")
    segs = []
    for n, d in enumerate(data, 1):
        if not isinstance(d, dict) or "start" not in d or "end" not in d:
            raise HushError(f"{name}: segment {n} needs 'start' and 'end' (seconds) and 'text'")
        try:
            s, e = float(d["start"]), float(d["end"])
        except (TypeError, ValueError):
            raise HushError(f"{name}: segment {n}: start and end must be numbers (seconds)") from None
        segs.append(Segment(s, e, str(d.get("text", "") or "").strip(), {k: v for k, v in d.items() if k not in ("start", "end", "text")}))
    if not segs:
        raise HushError(f"{name}: no segments found")
    return segs


def read_transcript(path) -> list:
    p = Path(path)
    ext = p.suffix.lower()
    text = read_text(p)
    if ext in (".srt", ".vtt"):
        return parse_subtitles(text, p.name)
    if ext == ".json":
        return parse_json(text, p.name)
    raise HushError(f"{p.name}: use an .srt, .vtt or .json transcript")


def format_srt(segs) -> str:
    def ts(x):
        x = max(0.0, x)
        ms = int(round(x * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    return "".join(f"{i}\n{ts(s.start)} --> {ts(s.end)}\n{s.text}\n\n" for i, s in enumerate(segs, 1))
