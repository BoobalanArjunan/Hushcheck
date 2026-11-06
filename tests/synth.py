"""Synthetic audio with KNOWN content: speech-like syllables, sustained music-like chords, and silence over a noise floor."""
import numpy as np

SR = 16000


def speech(t0, t1, seed, sr=SR):
    rng = np.random.RandomState(seed)
    n = int((t1 - t0) * sr)
    out = np.zeros(n)
    f0 = rng.uniform(110, 220)
    t = 0.0
    while t < (t1 - t0) - 0.03:
        d = min(rng.uniform(0.14, 0.26), (t1 - t0) - t)
        m = int(d * sr)
        tt = np.arange(m) / sr
        f = f0 * (1 + 0.05 * np.sin(2 * np.pi * 4 * tt + rng.rand() * 6))
        ph = 2 * np.pi * np.cumsum(f) / sr
        s = sum(np.sin(k * ph) / k ** 0.7 for k in range(1, 12))
        env = np.sin(np.pi * np.arange(m) / m) ** 0.5
        i = int(t * sr)
        out[i:i + m] += (0.25 * s * env)[: len(out) - i]
        t += d + rng.uniform(0.03, 0.08)
    return out


def music(t0, t1, seed, sr=SR, beat_hz=0.0):
    """Sustained chord with a slow swell. beat_hz > 0 adds a rhythmic pulse (a drum-like bed) that can fool the pulse check."""
    rng = np.random.RandomState(seed)
    n = int((t1 - t0) * sr)
    tt = np.arange(n) / sr
    base = rng.uniform(130, 260)
    x = sum(np.sin(2 * np.pi * base * r * tt + rng.rand() * 6) / (k + 1) for k, r in enumerate((1.0, 1.25, 1.5, 2.0, 3.0)))
    x = x * (0.7 + 0.3 * np.sin(2 * np.pi * 0.25 * tt + rng.rand() * 6))
    if beat_hz:
        x = x * (0.5 + 0.5 * (np.sin(2 * np.pi * beat_hz * tt) > 0.6))
    return 0.2 * x


def make_audio(parts, seconds=None, sr=SR, noise_db=-58.0, level_db=0.0, seed=0, music_level_db=0.0, beat_hz=0.0):
    """parts: [(kind, start_s, end_s)], kind 'speech' or 'music'. Everything else is silence (noise floor only). Returns mono float32."""
    seconds = seconds or max(e for _, _, e in parts) + 1.0
    n = int(seconds * sr)
    x = np.zeros(n)
    for k, (kind, s, e) in enumerate(parts):
        u = speech(s, e, seed * 100 + k, sr) * 10 ** (level_db / 20) if kind == "speech" else music(s, e, seed * 100 + k, sr, beat_hz) * 10 ** (music_level_db / 20)
        i = int(s * sr)
        x[i:i + len(u)] += u[: n - i]
    x += np.random.RandomState(seed + 999).randn(n) * 10 ** (noise_db / 20)
    return x.astype(np.float32)
