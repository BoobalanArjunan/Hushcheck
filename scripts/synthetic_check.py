"""hushcheck on synthetic audio with KNOWN content: how many planted invented lines are caught, and how many real lines are wrongly flagged,
as noise and level change. Includes the cases hushcheck is expected to MISS (invented words over real talking) so the limits are visible.

    python scripts/synthetic_check.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from hushcheck import Segment, activity_from_array, analyse_segments  # noqa: E402
from synth import SR, make_audio  # noqa: E402

PHRASES = ["Thank you for watching", "Please subscribe to the channel", "That is all for today friends", "The weather will be warm tomorrow afternoon"]


def case(seed, kind, noise_db, level_db, beat_hz):
    rng = np.random.RandomState(seed)
    parts, lines, t = [], [], 1.0
    for k in range(6):
        d = rng.uniform(3, 6)
        parts.append(("speech", t, t + d))
        lines.append((t, t + d, f"real line number {k} spoken here today", "real"))
        t += d + 0.5
        g = rng.uniform(3, 7)
        txt = PHRASES[rng.randint(len(PHRASES))]
        if kind == "silence":
            lines.append((t + 0.2, t + g - 0.2, txt, "invented"))
        elif kind == "music":
            parts.append(("music", t, t + g))
            lines.append((t + 0.2, t + g - 0.2, txt, "invented"))
        t += g
    x = make_audio(parts, seconds=t + 2, noise_db=noise_db, level_db=level_db, seed=seed, music_level_db=level_db, beat_hz=beat_hz)
    return activity_from_array(x, SR), lines


def main():
    print("| invented text sits over | conditions | invented lines caught as LIKELY | caught as LIKELY or SUSPECT | real lines wrongly flagged |")
    print("|---|---|---|---|---|")
    for kind, noise, level, beat, label in [("silence", -58, 0, 0, "clean"), ("silence", -45, -10, 0, "noisy"), ("silence", -50, -25, 0, "quiet recording"),
                                            ("music", -58, 0, 0, "steady music"), ("music", -58, 0, 6.0, "rhythmic music (6 Hz pulse)")]:
        inv = likely = anyf = real = wrong = 0
        for seed in range(30):
            a, lines = case(seed, kind, noise, level, beat)
            an = analyse_segments([Segment(s, e, t) for s, e, t, _ in lines], a)
            for f, (_, _, _, k) in zip(an.findings, lines):
                if k == "invented":
                    inv += 1
                    likely += f.level == "LIKELY"
                    anyf += f.level != "OK"
                else:
                    real += 1
                    wrong += f.level != "OK"
        print(f"| {kind} | {label} | {likely}/{inv} | {anyf}/{inv} | {wrong}/{real} |")
    print("\nNot shown, because it cannot work: invented words spoken over real talking look exactly like real words to an audio check.")


if __name__ == "__main__":
    main()
