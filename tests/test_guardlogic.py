"""Unit tests and planted-bug mutation checks for hushcheck.guardlogic.
Verifies all published thresholds, windowing, rescue rules, and multi-family scoring invariants.
"""
import pytest
from hushcheck import guardlogic as gl


# ---------------------------------------------------------------- windowing & density
def test_windows_consecutive_grouping():
    segs = [
        {"start": 0.0, "end": 2.0, "text": "hello world", "no_speech_prob": 0.1, "avg_logprob": -0.2},
        {"start": 2.0, "end": 5.0, "text": "how are you", "no_speech_prob": 0.1, "avg_logprob": -0.2},
        {"start": 5.0, "end": 10.0, "text": "next window", "no_speech_prob": 0.8, "avg_logprob": -1.6},
    ]
    ws = gl.windows(segs)
    assert len(ws) == 2
    assert len(ws[0]["segs"]) == 2
    assert ws[0]["start"] == 0.0 and ws[0]["end"] == 5.0
    assert ws[0]["dur"] == 5.0
    assert ws[1]["start"] == 5.0 and ws[1]["end"] == 10.0


def test_windows_non_consecutive_not_merged():
    # If segments at 0s and 60s share the same metrics, they must NOT be merged into one 60s window
    segs = [
        {"start": 0.0, "end": 5.0, "text": "part one", "no_speech_prob": 0.1, "avg_logprob": -0.2},
        {"start": 5.0, "end": 10.0, "text": "part two", "no_speech_prob": 0.5, "avg_logprob": -0.8},
        {"start": 60.0, "end": 65.0, "text": "part three", "no_speech_prob": 0.1, "avg_logprob": -0.2},
    ]
    ws = gl.windows(segs)
    assert len(ws) == 3


def test_windows_invalid_timing_handled_safely():
    segs = [
        {"start": "bad", "end": 5.0, "text": "corrupt", "no_speech_prob": 0.1, "avg_logprob": -0.2},
        {"start": 5.0, "end": None, "text": "missing", "no_speech_prob": 0.1, "avg_logprob": -0.2},
    ]
    ws = gl.windows(segs)
    assert len(ws) == 1
    assert ws[0]["dur"] is None and ws[0]["cps"] is None


def test_char_density():
    # Letters/digits/CJK only; spaces and punctuation ignored
    d = gl.char_density("Hello, world! 123", 2.0)
    # "Helloworld123" = 13 chars / 2.0s = 6.5 chars/s
    assert d == 6.5
    assert gl.char_density("...", 5.0) == 0.0
    assert gl.char_density("test", 0.0) == 0.0


# ---------------------------------------------------------------- sparse window
def test_sparse_window_triggers():
    # 12 seconds with only "Hello" (5 chars) -> 5 / 12 = 0.417 chars/s (< 1.0)
    w = {"dur": 12.0, "cps": 0.417, "logprob": -0.3}
    sig = gl.window_signals(w)
    assert sig.get("SPARSE_WINDOW") == 2


def test_sparse_window_does_not_trigger_when_short():
    # Short window (< 10s) must never trigger sparse window
    w = {"dur": 8.0, "cps": 0.5, "logprob": -0.3}
    sig = gl.window_signals(w)
    assert "SPARSE_WINDOW" not in sig


def test_sparse_window_does_not_trigger_when_dense():
    # 15s window with normal speech (5.0 chars/s)
    w = {"dur": 15.0, "cps": 5.0, "logprob": -0.3}
    sig = gl.window_signals(w)
    assert "SPARSE_WINDOW" not in sig


# ---------------------------------------------------------------- dense confident rescue
def test_dense_confident_rescue():
    # 6.0s duration, 4.0 chars/s, logprob -0.2 -> dense & confident
    w = {"dur": 6.0, "cps": 4.0, "logprob": -0.2}
    sig = gl.window_signals(w)
    assert sig.get("_dense_confident") is True


def test_dense_rescue_requires_min_duration():
    # 1.0s phrase ("謝謝觀看") is dense (4 chars/1s = 4.0 cps) but duration < 5.0s -> NOT rescued
    w = {"dur": 1.0, "cps": 4.0, "logprob": -0.1}
    sig = gl.window_signals(w)
    assert sig.get("_dense_confident") is False


def test_dense_rescue_requires_high_confidence():
    # 6.0s duration, 4.0 chars/s, but logprob -0.8 (<= -0.5) -> NOT rescued
    w = {"dur": 6.0, "cps": 4.0, "logprob": -0.8}
    sig = gl.window_signals(w)
    assert sig.get("_dense_confident") is False


def test_dense_rescue_clears_text_signals_only():
    # High no_speech_prob segment inside a dense confident window
    segs = [{
        "start": 0.0, "end": 6.0,
        "text": "This is a confident real speech sentence spoken clearly.",
        "no_speech_prob": 0.95,
        "avg_logprob": -0.2,
        "compression_ratio": 1.2
    }]
    # Without audio evidence, text signals should be cleared by rescue
    text_sig = gl.evaluate_text_signals(segs)
    assert text_sig == {}

    # Score with audio evidence: rescue must NEVER clear audio evidence!
    level, total, signals = gl.score({"NOT_SPEECH_LIKE": 1}, segs)
    assert "NOT_SPEECH_LIKE" in signals
    assert total == 1
    assert level == "SUSPECT"


# ---------------------------------------------------------------- segment filters
def test_segment_suspect_no_speech():
    assert gl.segment_suspect({"start": 0, "end": 2, "no_speech_prob": 0.85})
    assert not gl.segment_suspect({"start": 0, "end": 2, "no_speech_prob": 0.75, "avg_logprob": -0.5})


def test_segment_suspect_avg_logprob():
    # Normal segment: threshold is -1.5
    assert gl.segment_suspect({"start": 0, "end": 3.0, "avg_logprob": -1.6})
    assert not gl.segment_suspect({"start": 0, "end": 3.0, "avg_logprob": -1.4})


def test_segment_suspect_short_segment_lenient_logprob():
    # Brief utterance (< 1.6s) uses lenient threshold -1.7
    assert not gl.segment_suspect({"start": 0, "end": 1.2, "avg_logprob": -1.6})  # passes lenient
    assert gl.segment_suspect({"start": 0, "end": 1.2, "avg_logprob": -1.8})      # fails lenient


def test_segment_suspect_compression_ratio():
    assert gl.segment_suspect({"start": 0, "end": 3.0, "compression_ratio": 3.5})
    assert not gl.segment_suspect({"start": 0, "end": 3.0, "compression_ratio": 2.5})


# ---------------------------------------------------------------- loops & numeric exemptions
def test_char_loop_detected():
    assert gl.char_loop("hahahaha")
    assert gl.char_loop("thank you thank you thank you")
    assert gl.char_loop("abcabcabcabc")
    assert not gl.char_loop("normal conversational phrase without looping")


def test_char_loop_numeric_exemptions():
    # Numbers and amounts must NEVER be flagged as loops
    assert not gl.char_loop("The amount is 1,000,000,000 dollars")
    assert not gl.char_loop("$1,000,000,000,000")
    assert not gl.char_loop("Call 0912121212 for support")
    assert not gl.char_loop("Connecting to 192.168.1.1 now")

    # Decoder collapse: 20+ repeating digits is flagged
    assert gl.char_loop("00000000000000000000")


# ---------------------------------------------------------------- long text repetition
def test_long_repeat_flagged():
    # 100 words with only 10 unique words -> ratio 0.10 (< 0.35)
    repetitive_words = ["apple", "banana", "orange", "grape", "melon"] * 25
    assert gl.long_repeat(repetitive_words)


def test_long_repeat_not_flagged_on_real_speech():
    # Natural diverse text over 150 words
    real_words = (
        "The committee met on Tuesday morning to discuss the financial budget and capital allocations. "
        "Several proposals were considered regarding infrastructure development, healthcare improvements, "
        "and technological advancements. Representatives from each department provided their strategic "
        "assessments and projected expenditure for the upcoming fiscal quarter. Consensus was reached "
        "on prioritizing renewable energy investments and expanding digital public services across the country. "
        "Further evaluations will take place during the next scheduled session."
    ).lower().split()
    assert not gl.long_repeat(real_words)


# ---------------------------------------------------------------- batch silence score
def test_batch_silence_score():
    # 30s of clear speech (no_speech=0.05) + three 1s silent tails (no_speech=0.90)
    segs = [
        {"start": 0.0, "end": 30.0, "no_speech_prob": 0.05},
        {"start": 30.0, "end": 31.0, "no_speech_prob": 0.90},
        {"start": 31.0, "end": 32.0, "no_speech_prob": 0.90},
        {"start": 32.0, "end": 33.0, "no_speech_prob": 0.90},
    ]
    score = gl.batch_silence_score(segs)
    # Plain mean is (0.05 + 0.9*3)/4 = 0.6875
    # Weighted mean is (0.05*30 + 0.9*3)/33 = 4.2 / 33 = 0.127
    # min(0.6875, 0.127) = 0.127
    assert score < 0.15  # Clear speech is protected from being wiped by short tails!


# ---------------------------------------------------------------- multi-family scoring invariants
def test_scoring_text_only_never_likely():
    # Text signals alone reaching score 3 (e.g. SPARSE_WINDOW=2 + LOOP=1) must NOT be LIKELY
    segs = [{
        "start": 0.0, "end": 12.0,
        "text": "hahahaha",
        "no_speech_prob": 0.0,
        "avg_logprob": -0.8
    }]
    level, total, signals = gl.score({}, segs)
    assert "SPARSE_WINDOW" in signals and "LOOP" in signals
    assert total >= 3
    assert level == "SUSPECT"  # Invariant: text alone cannot reach LIKELY!


def test_scoring_strong_audio_alone_is_likely():
    # Strong audio signals (NO_SPEECH or BEYOND_AUDIO) can reach LIKELY on their own
    level, total, signals = gl.score({"NO_SPEECH": 3}, [])
    assert level == "LIKELY"
    assert total == 3

    level, total, signals = gl.score({"BEYOND_AUDIO": 3}, [])
    assert level == "LIKELY"


def test_scoring_weak_audio_plus_text_reaches_likely():
    # Weak audio (NOT_SPEECH_LIKE=1) + text (SPARSE_WINDOW=2) = total 3 WITH BOTH FAMILIES -> LIKELY!
    # This specifically solves the music and pause hallucination problem from HushCheck 1!
    segs = [{
        "start": 0.0, "end": 15.0,
        "text": "Thank you.",
        "no_speech_prob": 0.0,
        "avg_logprob": -0.4
    }]
    audio_sig = {"NOT_SPEECH_LIKE": 1}
    level, total, signals = gl.score(audio_sig, segs)
    assert total >= 3
    assert "NOT_SPEECH_LIKE" in signals
    assert "SPARSE_WINDOW" in signals
    assert level == "LIKELY"


# ================================================================
# PLANTED-BUG CHECKS (Mutation Tests)
# Each check intentionally tests a mutation to ensure our test suite catches it.
# ================================================================

class TestPlantedBugs:
    def test_planted_bug_sparse_cps_threshold(self, monkeypatch):
        # Normal: CPS 0.8 is flagged as sparse (0.8 < 1.0)
        w = {"dur": 12.0, "cps": 0.8, "logprob": -0.3}
        assert "SPARSE_WINDOW" in gl.window_signals(w)

        # Planted Bug: threshold lowered to 0.5 -> fails to catch CPS 0.8
        monkeypatch.setattr(gl, "SPARSE_CPS", 0.5)
        assert "SPARSE_WINDOW" not in gl.window_signals(w)

    def test_planted_bug_rescue_cps_threshold(self, monkeypatch):
        # Normal: CPS 2.2 is rescued (2.2 >= 2.0)
        w = {"dur": 6.0, "cps": 2.2, "logprob": -0.2}
        assert gl.window_signals(w)["_dense_confident"] is True

        # Planted Bug: threshold raised to 3.0 -> fails to rescue genuine speech at 2.2 cps
        monkeypatch.setattr(gl, "RESCUE_CPS", 3.0)
        assert gl.window_signals(w)["_dense_confident"] is False

    def test_planted_bug_repeat_unique_ratio(self, monkeypatch):
        # Normal: 100 words with 30 unique words (ratio 0.30) is flagged (0.30 < 0.35)
        words = ["word" + str(i % 30) for i in range(100)]
        assert gl.long_repeat(words) is True

        # Planted Bug: threshold lowered to 0.20 -> fails to catch ratio 0.30
        monkeypatch.setattr(gl, "REPEAT_UNIQUE_RATIO", 0.20)
        assert gl.long_repeat(words) is False

    def test_planted_bug_compression_threshold(self, monkeypatch):
        # Normal: CR 3.2 is flagged (3.2 > 3.0)
        s = {"start": 0, "end": 2, "compression_ratio": 3.2}
        assert gl.segment_suspect(s) is True

        # Planted Bug: threshold raised to 4.0 -> fails to catch CR 3.2
        monkeypatch.setattr(gl, "COMPRESSION", 4.0)
        assert gl.segment_suspect(s) is False

    def test_planted_bug_rescue_cancelling_audio(self):
        # Invariant: Dense rescue must NEVER cancel audio signals
        segs = [{
            "start": 0.0, "end": 6.0,
            "text": "Confident speech with high density and good logprob.",
            "no_speech_prob": 0.0,
            "avg_logprob": -0.1
        }]
        audio_signals = {"NOT_SPEECH_LIKE": 1}
        level, total, signals = gl.score(audio_signals, segs)

        # Audio signal must remain intact
        assert "NOT_SPEECH_LIKE" in signals
        assert total >= 1

    def test_planted_bug_text_only_allowed_likely(self):
        # Invariant: Score >= 3 from text signals alone must NEVER be LIKELY
        segs = [{
            "start": 0.0, "end": 15.0,
            "text": "hahahaha",
            "no_speech_prob": 0.0,
            "avg_logprob": -0.8
        }]
        text_signals = gl.evaluate_text_signals(segs)
        assert sum(text_signals.values()) >= 3

        level, total, _ = gl.score({}, segs)
        assert level == "SUSPECT"
        assert level != "LIKELY"

    def test_planted_bug_numbers_not_exempt(self):
        # Invariant: Currency with repeating zeros must not be flagged as char loop
        text = "The price was $1,000,000,000 in total"
        assert gl.char_loop(text) is False
