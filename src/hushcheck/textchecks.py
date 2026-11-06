"""Checks that look only at the text (and the line's length in time). These are the same kind of rules other tools use; they are not the new part."""
from __future__ import annotations

import re

# Phrases speech-to-text engines are known to invent on silence or music (seen in public Whisper reports). The list is short on purpose:
# it is incomplete, and a real person can say "thank you". A match alone is only a SUSPECT. Add more with --phrases FILE.
PHANTOM_PHRASES = (
    "thank you for watching", "thanks for watching", "thank you for watching this video", "please subscribe", "like and subscribe",
    "subtitles by the amara.org community", "subtitles by the amaraorg community", "untertitel im auftrag des zdf", "untertitelung des zdf",
    "sottotitoli creati dalla comunità amaraorg", "sottotitoli e revisione a cura di qtss", "subtítulos realizados por la comunidad de amaraorg",
    "sous-titres réalisés par la communauté d'amaraorg", "sous-titrage société radio-canada", "ご視聴ありがとうございました",
    "ご視聴ありがとうございました。", "谢谢观看", "謝謝觀看", "感谢观看", "字幕由amaraorg社区提供", "gracias por ver el video", "gracias por ver",
    "merci d'avoir regardé cette vidéo", "obrigado por assistir", "спасибо за просмотр", "продолжение следует", "субтитры сделал dimatorzok",
)
MAX_PHRASE_EXTRA_CHARS = 15
LOOP_UNIQUE_RATIO = 0.35
LOOP_MIN_WORDS = 12
MAX_CPS = 35.0            # letters per second above this is not human speech
REPEAT_LOOKBACK = 3

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"\s+")
_CHAR_LOOP = re.compile(r"(\D{1,4}?)\1{3,}")


def normalize(t: str) -> str:
    return _WS.sub(" ", _PUNCT.sub("", t.lower())).strip()


def phantom_match(t: str, phrases=PHANTOM_PHRASES) -> str | None:
    n = normalize(t)
    if not n:
        return None
    for p in phrases:
        pn = normalize(p)
        if pn and pn in n and len(n) <= len(pn) + MAX_PHRASE_EXTRA_CHARS:
            return p
    return None


def loop_kind(t: str) -> str | None:
    n = normalize(t)
    words = n.split()
    run = 1
    for i in range(1, len(words)):
        run = run + 1 if words[i] == words[i - 1] else 1
        if run >= 4:
            return f"the word '{words[i]}' repeated {run}+ times"
    if len(words) >= LOOP_MIN_WORDS and len(set(words)) / len(words) < LOOP_UNIQUE_RATIO:
        return f"only {len(set(words))} different words in {len(words)}"
    m = _CHAR_LOOP.search(n.replace(" ", ""))   # digits are never matched (non-digits only), so numbers like 1000000 are safe
    if m:
        return f"the letters '{m.group(1)}' repeated"
    return None


def letters_per_second(t: str, dur: float) -> float | None:
    n = sum(c.isalnum() for c in t)
    return n / dur if dur > 0 and n else None


def repeats_previous(t: str, prev_texts) -> bool:
    n = normalize(t)
    return len(n) >= 3 and any(n == normalize(p) for p in prev_texts[-REPEAT_LOOKBACK:])
