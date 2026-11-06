"""Put the audio evidence and the text checks together into one verdict per transcript line."""
from __future__ import annotations

from dataclasses import dataclass, field

from . import evidence as ev
from . import textchecks as tc
from .parse import HushError, Segment, read_transcript

# Each reason adds weight. 3 or more = LIKELY invented, 1-2 = SUSPECT (look at it yourself).
WEIGHTS = {"NO_SPEECH": 3, "BEYOND_AUDIO": 3, "BAD_TIME": 2, "LOOP": 2, "TOO_FAST": 2, "PHANTOM_PHRASE": 2, "LOW_SPEECH": 1, "NOT_SPEECH_LIKE": 1, "REPEAT": 1}
LIKELY_AT = 3
NO_SPEECH_BELOW = 0.15     # less than this share of the line has sound -> nothing was said there
LOW_SPEECH_BELOW = 0.28
NOT_SPEECH_DEPTH = 0.20    # loudness pulses less than this at syllable speed -> sounds like a hum or music, not talking


@dataclass
class Finding:
    index: int
    start: float
    end: float
    text: str
    level: str                     # OK, SUSPECT, LIKELY
    score: int
    reasons: list = field(default_factory=list)   # [(code, plain-words detail)]
    active_frac: float | None = None
    mod_depth: float | None = None


@dataclass
class Analysis:
    name: str
    audio_s: float
    findings: list
    skipped_empty: int
    reliable: bool
    reliability_note: str
    warnings: list

    def of(self, level):
        return [f for f in self.findings if f.level == level]

    @property
    def likely_rate(self) -> float:
        return len(self.of("LIKELY")) / len(self.findings) if self.findings else 0.0


def analyse_segments(segs, audio: ev.Audio, name: str = "", phrases=tc.PHANTOM_PHRASES) -> Analysis:
    findings, prev, skipped = [], [], 0
    for i, s in enumerate(segs):
        if not s.text.strip():
            skipped += 1
            continue
        reasons = []
        le = ev.line_evidence(audio, s.start, s.end)
        if s.end <= s.start:
            reasons.append(("BAD_TIME", f"the line ends ({s.end:.2f}s) at or before it starts ({s.start:.2f}s)"))
        if le.beyond_audio:
            reasons.append(("BEYOND_AUDIO", f"the line starts at {s.start:.1f}s but the audio is only {audio.duration_s:.1f}s long"))
        elif audio.reliable and s.end > s.start:
            if le.active_frac < NO_SPEECH_BELOW:
                reasons.append(("NO_SPEECH", f"only {le.active_frac:.0%} of the line's time has any sound"))
            elif le.active_frac < LOW_SPEECH_BELOW:
                reasons.append(("LOW_SPEECH", f"only {le.active_frac:.0%} of the line's time has sound"))
            elif le.mod_depth is not None and le.mod_depth < NOT_SPEECH_DEPTH:
                reasons.append(("NOT_SPEECH_LIKE", f"the sound is steady, not pulsing like speech (depth {le.mod_depth:.2f})"))
        p = tc.phantom_match(s.text, phrases)
        if p:
            reasons.append(("PHANTOM_PHRASE", f"matches a known invented phrase: '{p}'"))
        lk = tc.loop_kind(s.text)
        if lk:
            reasons.append(("LOOP", lk))
        cps = tc.letters_per_second(s.text, s.end - s.start)
        if cps is not None and cps > tc.MAX_CPS:
            reasons.append(("TOO_FAST", f"{cps:.0f} letters per second is faster than anyone talks"))
        if tc.repeats_previous(s.text, prev):
            reasons.append(("REPEAT", "same text as one of the lines just before"))
        prev.append(s.text)
        score = sum(WEIGHTS[c] for c, _ in reasons)
        level = "LIKELY" if score >= LIKELY_AT else ("SUSPECT" if score >= 1 else "OK")
        findings.append(Finding(i, s.start, s.end, s.text, level, score, reasons, le.active_frac, le.mod_depth))
    warnings = []
    if not audio.reliable:
        warnings.append("audio check skipped: " + audio.reason + ". Only the text checks were used.")
    if not findings:
        warnings.append("the transcript has no text lines")
    return Analysis(name, audio.duration_s, findings, skipped, audio.reliable, audio.reason, warnings)


def analyse_files(audio_path, transcript_path, phrases=tc.PHANTOM_PHRASES) -> Analysis:
    segs = read_transcript(transcript_path)
    audio = ev.load_audio(audio_path)
    from pathlib import Path
    return analyse_segments(segs, audio, Path(audio_path).name, phrases)
