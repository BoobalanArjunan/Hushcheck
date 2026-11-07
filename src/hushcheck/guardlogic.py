"""Window and density logic, reimplemented from the ideas in whisper-guard 0.3.3 (MIT, Hevin Yeh).
Credit: see THIRD_PARTY_NOTICES.md. Published thresholds verified against guard.py.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional

# Published thresholds from whisper-guard 0.3.3
NO_SPEECH_PROB: float = 0.8
AVG_LOGPROB: float = -1.5
SHORT_SEC: float = 1.6
SHORT_LOGPROB: float = -1.7
COMPRESSION: float = 3.0

RESCUE_MIN_SEC: float = 5.0
RESCUE_CPS: float = 2.0
RESCUE_LOGPROB: float = -0.5

SPARSE_MIN_SEC: float = 10.0
SPARSE_CPS: float = 1.0

REPEAT_WINDOW_WORDS: int = 100
REPEAT_UNIQUE_RATIO: float = 0.35  # verified from whisper-guard guard.py GuardConfig.repetition_threshold

LOOP_MIN_PATTERN: int = 2
LOOP_MAX_PATTERN: int = 4
LOOP_MIN_REPEATS: int = 3
LOOP_NUMERIC_MIN_SPAN: int = 20

# Patterns
_ALPHANUM_ONLY = re.compile(r"[\W_]", re.UNICODE)
_NUMERIC_UNIT = re.compile(r"^[\d.,:/+\-$%]+$")
_THOUSANDS_GROUP = re.compile(r"^[.,]\d{3}$")
_CHAR_LOOP = re.compile(r"(.{%d,%d})\1{%d,}" % (LOOP_MIN_PATTERN, LOOP_MAX_PATTERN, LOOP_MIN_REPEATS - 1))
_SPAN_LOOP = re.compile(r"(.{20,}?)\1{2,}")
_PHRASE_LOOP = re.compile(r"(.{3,}?)(?:\s+\1){2,}")


def char_density(text: str, duration: float) -> float:
    """Letters, digits, and CJK characters per second; spaces and punctuation excluded."""
    if duration <= 0:
        return 0.0
    clean = _ALPHANUM_ONLY.sub("", text)
    return len(clean) / duration


def _duration(s: Dict[str, Any]) -> Optional[float]:
    start, end = s.get("start"), s.get("end")
    for v in (start, end):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            return None
    d = float(end) - float(start)
    return d if d > 0 else None


def windows(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group consecutive segments that share the same (no_speech_prob, avg_logprob).

    Whisper outputs segments from the same 30 s decoding window with identical
    (no_speech_prob, avg_logprob) pairs.
    """
    if not segments:
        return []
    out = []
    i = 0
    n = len(segments)
    while i < n:
        nsp = segments[i].get("no_speech_prob")
        lp = segments[i].get("avg_logprob")
        key = (nsp, lp)
        j = i + 1
        while j < n and (segments[j].get("no_speech_prob"), segments[j].get("avg_logprob")) == key:
            j += 1
        window_segs = segments[i:j]

        # Timing validity check
        if all(_duration(s) is not None for s in window_segs):
            start = float(window_segs[0]["start"])
            end = float(window_segs[-1]["end"])
            dur = max(end - start, 1e-6)
            text = "".join(s.get("text", "") for s in window_segs)
            cps = char_density(text, dur)
        else:
            start, end, dur, cps = None, None, None, None

        out.append({
            "segs": window_segs,
            "start": start,
            "end": end,
            "dur": dur,
            "cps": cps,
            "logprob": lp if lp is not None else 0.0,
            "no_speech_prob": nsp if nsp is not None else 0.0,
        })
        i = j
    return out


def window_signals(w: Dict[str, Any]) -> Dict[str, Any]:
    """Detect sparse windows and dense confident speech in a decoding window."""
    sig: Dict[str, Any] = {}
    dur = w.get("dur")
    cps = w.get("cps")
    lp = w.get("logprob", 0.0)

    if dur is not None and cps is not None:
        if dur >= SPARSE_MIN_SEC and cps < SPARSE_CPS:
            sig["SPARSE_WINDOW"] = 2
        sig["_dense_confident"] = (
            dur >= RESCUE_MIN_SEC
            and cps >= RESCUE_CPS
            and lp > RESCUE_LOGPROB
        )
    else:
        sig["_dense_confident"] = False
    return sig


def segment_suspect(s: Dict[str, Any]) -> bool:
    """Individual segment filter checks."""
    dur = _duration(s)
    nsp = s.get("no_speech_prob", 0.0)
    lp = s.get("avg_logprob", 0.0)
    cr = s.get("compression_ratio", 1.0)

    if nsp > NO_SPEECH_PROB:
        return True
    if dur is not None and dur < SHORT_SEC:
        if lp < SHORT_LOGPROB:
            return True
    else:
        if lp < AVG_LOGPROB:
            return True
    if cr > COMPRESSION:
        return True
    return False


def is_numeric_data(match: re.Match) -> bool:
    """True when a matched loop is genuine numeric data rather than a decoder loop."""
    unit = match.group(1)
    # Must contain at least one decimal digit
    if not any(ch.isdecimal() for ch in unit):
        return False
    # Must consist solely of numeric/currency punctuation
    if not _NUMERIC_UNIT.match(unit):
        return False
    # Thousands grouping like ",000" or ".000" is always data
    if _THOUSANDS_GROUP.match(unit):
        return True
    # Pure numeric run under LOOP_NUMERIC_MIN_SPAN is data
    return len(match.group(0)) < LOOP_NUMERIC_MIN_SPAN


def char_loop(text: str) -> bool:
    """True if text contains 2-4 character loops, phrase loops, or 20+ char loops repeated 3+ times, excluding numeric data."""
    for pattern in (_CHAR_LOOP, _SPAN_LOOP, _PHRASE_LOOP):
        for m in pattern.finditer(text):
            if not is_numeric_data(m):
                return True
    return False


def long_repeat(words: List[str]) -> bool:
    """True if word-uniqueness ratio averaged over 100-word windows is below 0.35."""
    if not words:
        return False
    w = max(int(REPEAT_WINDOW_WORDS), 3)
    if len(words) <= w:
        if len(words) < 12:
            return False
        return (len(set(words)) / len(words)) < REPEAT_UNIQUE_RATIO

    chunks = [words[i:i + w] for i in range(0, len(words), w)]
    if len(chunks) > 1 and len(chunks[-1]) < w:
        tail = chunks.pop()
        chunks[-1] = chunks[-1] + tail
    avg_ratio = sum(len(set(c)) / len(c) for c in chunks) / len(chunks)
    return avg_ratio < REPEAT_UNIQUE_RATIO


def batch_silence_score(segments: List[Dict[str, Any]]) -> float:
    """Batch-level no_speech score: min(plain mean, duration-weighted mean)."""
    if not segments:
        return 0.0
    durations = [_duration(s) for s in segments]
    probs = [s.get("no_speech_prob", 0.0) for s in segments]
    plain = sum(probs) / len(probs)
    if all(d is not None for d in durations):
        total_dur = sum(d for d in durations if d is not None)
        if total_dur > 0:
            weighted = sum(p * d for p, d in zip(probs, durations) if d is not None) / total_dur
            return min(plain, weighted)
    return plain


def evaluate_text_signals(segments: List[Dict[str, Any]]) -> Dict[str, int]:
    """Extract all text/timing signals from segments, applying dense rescue."""
    text_signals: Dict[str, int] = {}
    ws = [window_signals(w) for w in windows(segments)]

    if any("SPARSE_WINDOW" in s for s in ws):
        text_signals["SPARSE_WINDOW"] = 2

    # Segment filter triggers if any segment is suspect and not rescued by a dense confident window
    any_segment_bad = False
    for seg, w_sig in zip(segments, [ws[0] if ws else {}] * len(segments)):
        if segment_suspect(seg):
            # If segment is bad strictly due to no_speech_prob but window is dense confident, rescue it
            nsp = seg.get("no_speech_prob", 0.0)
            if nsp > NO_SPEECH_PROB and w_sig.get("_dense_confident"):
                # check if other filters trigger
                dur = _duration(seg)
                lp = seg.get("avg_logprob", 0.0)
                cr = seg.get("compression_ratio", 1.0)
                lp_lim = SHORT_LOGPROB if (dur is not None and dur < SHORT_SEC) else AVG_LOGPROB
                if lp < lp_lim or cr > COMPRESSION:
                    any_segment_bad = True
                    break
            else:
                any_segment_bad = True
                break

    if any_segment_bad:
        text_signals["SEGMENT_FILTER"] = 1

    all_text = " ".join(s.get("text", "") for s in segments)
    words = all_text.lower().split()
    if long_repeat(words):
        text_signals["LONG_REPEAT"] = 1

    if any(char_loop(s.get("text", "")) for s in segments):
        text_signals["LOOP"] = 1

    # Dense confident rescue: removes text-side signals only (never audio evidence)
    # Occurs when all windows in the evaluation span are dense and confident
    if ws and all(s.get("_dense_confident") for s in ws):
        # Sparse window by definition cannot be dense confident, but rescue clears other text signals
        text_signals.clear()

    return text_signals


def score(audio_signals: Dict[str, int], segments: List[Dict[str, Any]]) -> tuple[str, int, Dict[str, int]]:
    """Combine audio and text/timing signals into verdict according to HushCheck 2 principles.

    Returns:
        (level, total_score, active_signals)
        level: 'LIKELY', 'SUSPECT', or 'OK'
    """
    text_signals = evaluate_text_signals(segments)
    all_signals = {**audio_signals, **text_signals}
    total = sum(all_signals.values())

    # Principle: LIKELY needs score >= 3, and requires either:
    # 1. Evidence from BOTH families (audio and text/timing), OR
    # 2. Strong audio evidence (NO_SPEECH or BEYOND_AUDIO).
    strong_audio = any(k in audio_signals for k in ("NO_SPEECH", "BEYOND_AUDIO"))
    both_families = bool(audio_signals) and bool(text_signals)

    if total >= 3 and (both_families or strong_audio):
        level = "LIKELY"
    elif total >= 1:
        level = "SUSPECT"
    else:
        level = "OK"

    return level, total, all_signals
