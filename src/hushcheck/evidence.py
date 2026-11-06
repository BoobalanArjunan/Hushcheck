"""What does the AUDIO say about each transcript line? Plain signal processing, no model.

Sound is cut into 10 ms frames; the energy in the speech band (100 Hz to 4 kHz) of each frame is measured. A frame is "active" when it is
clearly louder than the quiet parts of the same file. Per transcript line we report:
  active_frac : share of the line's time that has sound
  mod_depth   : how strongly the loudness pulses at syllable speed (3-8 Hz). Talking pulses; a steady hum or sustained music does not.
Both are rough. Rhythmic music can pulse like speech, and noise as loud as the speech cannot be told from it (``reliable`` says so).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

from .parse import HushError

FRAME_S = 0.01
CONTRAST_DB = 12.0         # loud vs quiet parts must differ by this much, else activity cannot be trusted
THRESHOLD_FRACTION = 0.3   # active above floor + 30% of the way up to the loud level
ABS_MIN_DB = -65.0         # frames quieter than this are never "active"
FILL_GAP_S = 0.25
MIN_RUN_S = 0.10
MOD_BAND = (3.0, 8.0)
MOD_MIN_FRAMES = 150       # 1.5 s of audio needed to judge pulsing


@dataclass
class Audio:
    db: np.ndarray
    lin: np.ndarray
    active: np.ndarray
    hop_s: float
    duration_s: float
    reliable: bool
    floor_db: float
    top_db: float
    reason: str = ""


@dataclass
class LineEvidence:
    active_frac: float
    mod_depth: float | None   # None when the line is too short or too quiet to judge
    beyond_audio: bool


def _runs(mask):
    d = np.diff(np.concatenate(([0], mask.astype(np.int8), [0])))
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))


def activity_from_array(x: np.ndarray, sr: int) -> Audio:
    hop = max(int(round(sr * FRAME_S)), 1)
    hi = min(4000.0, 0.45 * sr)
    sos = signal.butter(4, [min(100.0, 0.5 * hi), hi], "band", fs=sr, output="sos")
    y = signal.sosfilt(sos, x.astype(np.float64)) if len(x) else x
    nf = len(y) // hop
    hop_s = hop / sr
    if nf < 2:
        raise HushError("the audio is too short to analyse")
    fr = y[: nf * hop].reshape(nf, hop)
    lin = np.sqrt((fr ** 2).mean(axis=1))
    db = 20 * np.log10(lin + 1e-9)
    floor, top = float(np.percentile(db, 10)), float(np.percentile(db, 95))
    contrast = top - floor
    silent_file = top < ABS_MIN_DB
    reliable = bool(silent_file or contrast >= CONTRAST_DB)
    reason = "" if reliable else (f"loud and quiet parts differ by only {contrast:.0f} dB (constant noise or music?), so silence cannot be told apart reliably")
    thr = max(floor + THRESHOLD_FRACTION * contrast, ABS_MIN_DB)
    active = db > thr
    fill = int(round(FILL_GAP_S / hop_s))
    for s, e in _runs(~active):                       # fill short gaps between active runs
        if s > 0 and e < nf and e - s <= fill:
            active[s:e] = True
    mn = int(round(MIN_RUN_S / hop_s))
    for s, e in _runs(active):                        # drop tiny blips
        if e - s < mn:
            active[s:e] = False
    return Audio(db, lin, active, hop_s, len(x) / sr, reliable, floor, top, reason)


def load_audio(path) -> Audio:
    p = Path(path)
    try:
        data, sr = sf.read(str(p), always_2d=True, dtype="float32")
    except Exception as e:                              # soundfile raises several error types
        raise HushError(f"cannot read audio {p.name}: {e}") from None
    return activity_from_array(data.mean(axis=1), sr)


def line_evidence(a: Audio, start: float, end: float) -> LineEvidence:
    if start >= a.duration_s:
        return LineEvidence(0.0, None, True)
    i0 = max(int(start / a.hop_s), 0)
    i1 = min(max(int(np.ceil(end / a.hop_s)), i0 + 1), len(a.active))
    seg = a.active[i0:i1]
    frac = float(seg.mean()) if len(seg) else 0.0
    depth = None
    if len(seg) >= MOD_MIN_FRAMES and frac >= 0.15:
        env = a.lin[i0:i1]
        m = float(env.mean())
        if m > 0:
            sos = signal.butter(2, MOD_BAND, "band", fs=1.0 / a.hop_s, output="sos")
            band = signal.sosfiltfilt(sos, env - m)
            depth = float(np.sqrt((band ** 2).mean()) / m)
    return LineEvidence(frac, depth, False)
