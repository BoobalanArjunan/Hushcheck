import json

import numpy as np
import pytest
import soundfile as sf

from hushcheck import HushError, Segment, activity_from_array, analyse_files, analyse_segments, read_transcript
from hushcheck import evidence as ev
from hushcheck import report
from hushcheck import textchecks as tc
from hushcheck.cli import main
from hushcheck.parse import format_srt, parse_json, parse_subtitles
from synth import SR, make_audio

SPEECH_AT = [("speech", 1, 6), ("speech", 12, 17)]          # talking 1-6 s and 12-17 s; silence 6-12 s and after 17 s


def audio(parts=SPEECH_AT, **kw):
    return activity_from_array(make_audio(parts, seconds=22, **kw), SR)


def run(segs, a=None, **kw):
    return analyse_segments([Segment(*s) for s in segs], a or audio(**kw))


def levels(an):
    return [f.level for f in an.findings]


# ---------------------------------------------------------------- parsing
SRT = "1\n00:00:01,000 --> 00:00:02,500\nHello there\n\n2\n00:00:03,000 --> 00:00:04,000\nline one\nline two\n"


def test_srt_and_vtt():
    s = parse_subtitles(SRT)
    assert [(x.start, x.end, x.text) for x in s] == [(1.0, 2.5, "Hello there"), (3.0, 4.0, "line one line two")]
    v = parse_subtitles("WEBVTT\n\n00:01.000 --> 00:02.500\nHi\n\n01:00:00.000 --> 01:00:01.000\nHour\n")
    assert v[0].start == 1.0 and v[1].start == 3600.0


def test_srt_crlf_and_bom(tmp_path):
    p = tmp_path / "a.srt"
    p.write_bytes(b"\xef\xbb\xbf" + SRT.replace("\n", "\r\n").encode())
    assert len(read_transcript(p)) == 2


def test_json_forms_and_extra_keys():
    a = parse_json(json.dumps({"segments": [{"start": 0, "end": 1, "text": " Hi ", "no_speech_prob": 0.9}]}))
    assert a[0].text == "Hi" and a[0].extra == {"no_speech_prob": 0.9}
    assert len(parse_json(json.dumps([{"start": "1.5", "end": 2, "text": "x"}]))) == 1
    assert parse_json(json.dumps([{"start": 0, "end": 1}]))[0].text == ""


@pytest.mark.parametrize("bad", ["not json", "{}", "[]", '[{"start":0}]', '[{"start":"a","end":1}]', "[1]", '{"segments": 3}'])
def test_json_errors(bad):
    with pytest.raises(HushError):
        parse_json(bad)


def test_subtitle_errors_and_extension(tmp_path):
    with pytest.raises(HushError):
        parse_subtitles("just text")
    p = tmp_path / "t.docx"
    p.write_text("x")
    with pytest.raises(HushError, match="use an .srt"):
        read_transcript(p)
    with pytest.raises(HushError):
        read_transcript(tmp_path / "missing.srt")


def test_srt_roundtrip():
    s = parse_subtitles(SRT)
    assert [(x.start, x.end, x.text) for x in parse_subtitles(format_srt(s))] == [(x.start, x.end, x.text) for x in s]
    assert "-00" not in format_srt([Segment(-1.0, 0.5, "a")])


# ---------------------------------------------------------------- text checks
@pytest.mark.parametrize("t", ["Thank you for watching!", "thanks for watching", "  THANK YOU FOR WATCHING.  ", "Untertitel im Auftrag des ZDF, 2020",
                               "Subtitles by the Amara.org community", "谢谢观看", "Thank you for watching. Bye"])
def test_phantom_phrases_found(t):
    assert tc.phantom_match(t)


@pytest.mark.parametrize("t", ["", "...", "Thank you", "So thank you for watching the baby while we were out at dinner last night",
                               "I will watch it tomorrow"])
def test_phantom_phrases_not_found(t):
    assert tc.phantom_match(t) is None


def test_custom_phrases():
    assert tc.phantom_match("Visit example dot com", ("visit example dot com",))


def test_loops():
    assert tc.loop_kind("you you you you")
    assert tc.loop_kind("a b a b a b a b a b a b a b a b")
    assert tc.loop_kind("ahahahahahah") or tc.loop_kind("hahahahaha")
    assert tc.loop_kind("The meeting is at three, then we go home and eat.") is None
    assert tc.loop_kind("The total is 1000000000 dollars") is None
    assert tc.loop_kind("no no no yes") is None                     # three in a row is ordinary speech
    assert tc.loop_kind("") is None


def test_speed_and_repeat():
    assert tc.letters_per_second("abcdefghij", 0.1) == pytest.approx(100)
    assert tc.letters_per_second("abc", 0) is None and tc.letters_per_second("...", 1) is None
    assert tc.repeats_previous("Okay.", ["fine", "okay", "x"])
    assert not tc.repeats_previous("Okay.", ["okay", "a", "b", "c"])      # only the last three lines count
    assert not tc.repeats_previous("ok", ["ok"])                        # too short to call a repeat
    assert not tc.repeats_previous("hello", [])


# ---------------------------------------------------------------- audio evidence
def test_activity_speech_vs_silence():
    a = audio()
    assert a.reliable
    assert ev.line_evidence(a, 1.5, 5.5).active_frac > 0.9
    assert ev.line_evidence(a, 7, 11).active_frac < 0.05
    assert ev.line_evidence(a, 18, 21).active_frac < 0.05


def test_speech_pulses_music_does_not():
    a = activity_from_array(make_audio([("speech", 1, 6), ("music", 8, 13)], seconds=15), SR)
    s, m = ev.line_evidence(a, 1.5, 5.5), ev.line_evidence(a, 8.5, 12.5)
    assert s.mod_depth > 0.35 and m.mod_depth < 0.10
    assert m.active_frac > 0.9                                          # music has sound; only the pulse check tells it apart


def test_short_line_has_no_depth():
    assert ev.line_evidence(audio(), 2, 3).mod_depth is None            # 1 s is too short to judge pulsing


def test_beyond_audio_and_clipping():
    a = audio()
    assert ev.line_evidence(a, 30, 31).beyond_audio
    assert not ev.line_evidence(a, 20, 40).beyond_audio                 # starts inside, runs past the end: fine
    assert ev.line_evidence(a, -5, 0.2).active_frac == 0.0              # negative start is clamped, not an error


def test_constant_noise_is_unreliable():
    x = (np.random.RandomState(1).randn(SR * 10) * 0.1).astype(np.float32)
    a = activity_from_array(x, SR)
    assert not a.reliable and "constant" in a.reason


def test_digital_silence_is_reliable_and_all_inactive():
    a = activity_from_array(np.zeros(SR * 5, np.float32), SR)
    assert a.reliable and not a.active.any()


def test_too_short_audio():
    with pytest.raises(HushError):
        activity_from_array(np.zeros(100, np.float32), SR)


def test_other_sample_rates():
    for sr in (8000, 22050, 44100):
        x = make_audio([("speech", 1, 4)], seconds=8, sr=sr)
        a = activity_from_array(x, sr)
        assert ev.line_evidence(a, 1.5, 3.5).active_frac > 0.9 and ev.line_evidence(a, 5, 7).active_frac < 0.05


# ---------------------------------------------------------------- verdicts
def test_real_lines_over_speech_are_ok():
    an = run([(1, 3.5, "The quarterly numbers look better than expected"), (3.5, 6, "and we should plan the next steps carefully"),
              (12, 17, "Let us move on to the next item on the agenda today")])
    assert levels(an) == ["OK", "OK", "OK"] and an.likely_rate == 0


def test_invented_line_over_silence_is_likely():
    an = run([(1, 6, "Hello and welcome to the show today"), (7, 11, "Please remember to hit the bell button"), (18, 21, "See you next time")])
    assert levels(an) == ["OK", "LIKELY", "LIKELY"]
    assert an.findings[1].reasons[0][0] == "NO_SPEECH"


def test_fluent_phantom_over_silence_with_good_grammar():
    """The case text-only filters miss: a normal sentence, nothing in it looks wrong, but nobody is talking."""
    an = run([(7, 11, "The weather will be warm and sunny tomorrow afternoon")])
    assert levels(an) == ["LIKELY"]


def test_phantom_phrase_over_speech_is_only_suspect():
    an = run([(1, 3, "Thank you for watching")])
    assert levels(an) == ["SUSPECT"]


def test_phantom_phrase_over_silence_is_likely():
    assert levels(run([(7, 9, "Thank you for watching!")])) == ["LIKELY"]


def test_loop_over_speech_is_suspect_and_over_silence_likely():
    assert levels(run([(1, 5, "you you you you you")])) == ["SUSPECT"]
    assert levels(run([(7, 11, "you you you you you")])) == ["LIKELY"]


def test_repeat_needs_help():
    two = run([(1, 3, "Okay then"), (3, 5, "Okay then")])
    assert levels(two) == ["OK", "SUSPECT"] and two.findings[1].reasons[0][0] == "REPEAT"
    assert levels(run([(7, 9, "Okay then"), (9, 11, "Okay then")])) == ["LIKELY", "LIKELY"]


def test_too_fast_and_bad_time():
    an = run([(2, 2.1, "this line has far too many letters for its time"), (3, 3, "zero length"), (5, 4, "backwards")])
    assert all(l == "LIKELY" or l == "SUSPECT" for l in levels(an))
    codes = {c for f in an.findings for c, _ in f.reasons}
    assert {"TOO_FAST", "BAD_TIME"} <= codes


def test_beyond_audio_line_is_likely():
    an = run([(40, 45, "Some text after the recording ended")])
    assert levels(an) == ["LIKELY"] and an.findings[0].reasons[0][0] == "BEYOND_AUDIO"


def test_music_with_phantom_phrase_likely_without_phrase_suspect():
    a = activity_from_array(make_audio([("speech", 1, 6), ("music", 8, 14)], seconds=16), SR)
    an = analyse_segments([Segment(9, 13, "Thank you for watching"), Segment(9, 13, "Please enjoy the rest of your evening")], a)
    assert levels(an) == ["LIKELY", "SUSPECT"]
    assert an.findings[1].reasons[0][0] == "NOT_SPEECH_LIKE"


def test_mostly_silent_long_line_is_suspect_not_likely():
    """A long line that is only partly over talking: worth a look, not a certain invention."""
    an = run([(4, 12, "Something said at the end of the first part and nothing after")])
    assert an.findings[0].level == "SUSPECT" and an.findings[0].reasons[0][0] in ("LOW_SPEECH",)


def test_hallucination_spoken_over_real_speech_cannot_be_caught():
    """Documented limit: wrong words over real talking look just like right words."""
    an = run([(1, 6, "Completely different words than were actually spoken here")])
    assert levels(an) == ["OK"]


def test_empty_lines_skipped_and_counted():
    an = run([(1, 3, ""), (3, 5, "   "), (7, 9, "invented over silence now")])
    assert an.skipped_empty == 2 and len(an.findings) == 1


def test_no_text_warning():
    an = run([(1, 3, "")])
    assert any("no text" in w for w in an.warnings) and an.likely_rate == 0.0


def test_unreliable_audio_uses_text_checks_only():
    x = (np.random.RandomState(2).randn(SR * 12) * 0.1).astype(np.float32)
    an = analyse_segments([Segment(1, 5, "Plain sentence about nothing in particular"), Segment(6, 9, "Thank you for watching")], activity_from_array(x, SR))
    assert levels(an) == ["OK", "SUSPECT"] and not an.reliable and any("audio check skipped" in w for w in an.warnings)


# ---------------------------------------------------------------- planted hallucinations across conditions
def random_case(seed, noise_db=-58.0, level_db=0.0):
    rng = np.random.RandomState(seed)
    parts, lines, t = [], [], 1.0
    for k in range(6):
        d = rng.uniform(3, 6)
        parts.append(("speech", t, t + d))
        lines.append((t, t + d, f"real line number {k} spoken here today", False))
        t += d + rng.uniform(0.3, 0.8)
        if rng.rand() < 0.6:
            g = rng.uniform(3, 7)
            lines.append((t + 0.2, t + g - 0.2, rng.choice(["Thank you for watching", "Please subscribe to the channel", "That is all for today friends",
                                                           "Subtitles by the Amara.org community"]), True))
            t += g
    x = make_audio(parts, seconds=t + 2, noise_db=noise_db, level_db=level_db, seed=seed)
    return activity_from_array(x, SR), lines


@pytest.mark.parametrize("noise_db,level_db", [(-58, 0), (-45, 0), (-40, -10), (-58, -30), (-50, -25)])
def test_planted_found_with_no_false_alarms(noise_db, level_db):
    caught = total = false_likely = 0
    for seed in range(15):
        a, lines = random_case(seed, noise_db, level_db)
        assert a.reliable
        an = analyse_segments([Segment(s, e, t) for s, e, t, _ in lines], a)
        for f, (_, _, _, planted) in zip(an.findings, lines):
            if planted:
                total += 1
                caught += f.level == "LIKELY"
            else:
                false_likely += f.level != "OK"
    assert total > 20 and caught == total and false_likely == 0


# ---------------------------------------------------------------- reports and CLI
def make_files(tmp_path, srt=None):
    sf.write(tmp_path / "a.wav", make_audio(SPEECH_AT, seconds=22), SR)
    (tmp_path / "a.srt").write_text(srt or "1\n00:00:01,000 --> 00:00:05,000\nreal talking happens here\n\n2\n00:00:07,000 --> 00:00:10,000\nThank you for watching\n\n3\n00:00:12,000 --> 00:00:16,000\nmore real talking here\n", encoding="utf-8")
    return tmp_path / "a.wav", tmp_path / "a.srt"


def test_cli_text_json_csv_clean(tmp_path, capsys):
    w, s = make_files(tmp_path)
    before = s.read_text(encoding="utf-8")
    code = main(["check", str(w), str(s), "--json", str(tmp_path / "r.json"), "--csv", str(tmp_path / "r.csv"), "--write-clean", str(tmp_path / "clean.srt")])
    out = capsys.readouterr().out
    assert code == 0 and "LIKELY invented: 1" in out and "Thank you for watching" in out
    assert s.read_text(encoding="utf-8") == before                      # original untouched
    d = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert d["likely"] == 1 and d["lines_checked"] == 3 and d["findings"][1]["reasons"][0]["code"] in ("NO_SPEECH", "PHANTOM_PHRASE")
    assert len((tmp_path / "r.csv").read_text(encoding="utf-8").splitlines()) == 4
    clean = parse_subtitles((tmp_path / "clean.srt").read_text(encoding="utf-8"))
    assert [c.text for c in clean] == ["real talking happens here", "more real talking here"]


def test_cli_gate(tmp_path, capsys):
    w, s = make_files(tmp_path)
    assert main(["check", str(w), str(s), "--max-likely-rate", "0.5"]) == 0
    assert main(["check", str(w), str(s), "--max-likely-rate", "0.1"]) == 1
    assert main(["check", str(w), str(s), "--max-likely-rate", "2"]) == 2


def test_cli_drop_suspect_and_hide(tmp_path, capsys):
    w, s = make_files(tmp_path, "1\n00:00:01,000 --> 00:00:04,000\nThank you for watching\n\n2\n00:00:12,000 --> 00:00:16,000\nreal talking\n")
    main(["check", str(w), str(s), "--write-clean", str(tmp_path / "c1.srt"), "--hide-suspect"])
    assert "SUSPECT: 1" in capsys.readouterr().out.split("SUSPECT (look")[0] and "Thank you" in (tmp_path / "c1.srt").read_text(encoding="utf-8")
    main(["check", str(w), str(s), "--write-clean", str(tmp_path / "c2.srt"), "--drop-suspect"])
    assert "Thank you" not in (tmp_path / "c2.srt").read_text(encoding="utf-8")


def test_cli_custom_phrases(tmp_path, capsys):
    w, s = make_files(tmp_path, "1\n00:00:07,000 --> 00:00:09,000\nVisit example dot com\n")
    (tmp_path / "p.txt").write_text("visit example dot com\n", encoding="utf-8")
    main(["check", str(w), str(s), "--phrases", str(tmp_path / "p.txt")])
    assert "PHANTOM_PHRASE" in capsys.readouterr().out


def test_cli_errors(tmp_path, capsys):
    w, s = make_files(tmp_path)
    assert main(["check", str(tmp_path / "nope.wav"), str(s)]) == 2
    assert main(["check", str(w), str(tmp_path / "nope.srt")]) == 2
    (tmp_path / "bad.wav").write_bytes(b"not audio")
    assert main(["check", str(tmp_path / "bad.wav"), str(s)]) == 2
    assert "hushcheck:" in capsys.readouterr().err
    assert main([]) == 2


def test_analyse_files_api(tmp_path):
    w, s = make_files(tmp_path)
    an = analyse_files(w, s)
    assert an.name == "a.wav" and len(an.of("LIKELY")) == 1


def test_stereo_audio_is_mixed(tmp_path):
    x = make_audio(SPEECH_AT, seconds=22)
    sf.write(tmp_path / "s.wav", np.stack([x, np.zeros_like(x)], axis=1), SR)
    _, s = make_files(tmp_path)
    assert len(analyse_files(tmp_path / "s.wav", s).of("LIKELY")) == 1


def test_report_text_notes_limit():
    t = report.text(run([(7, 9, "invented over silence now")]))
    assert "LIKELY" in t and "cannot tell if the words are right" in t
    assert "No line looks invented" in report.text(run([(1, 5, "real talking")]))


# ---------------------------------------------------------------- tests added after the planted-bug check (each pins one detail)
def test_short_click_in_silence_is_not_speech():
    x = make_audio([("speech", 1, 4)], seconds=12)
    x[int(8 * SR):int(8.05 * SR)] += 0.3                      # a 50 ms click
    a = activity_from_array(x, SR)
    assert not a.active[int(7.5 / a.hop_s):int(9 / a.hop_s)].any()


def test_negative_start_is_clamped_not_wrapped():
    a = audio()
    assert ev.line_evidence(a, -0.5, 3.0).active_frac > 0.5   # a negative start must not slice from the END of the audio


def test_depth_only_for_lines_with_enough_sound():
    a = audio()
    assert ev.line_evidence(a, 4, 10).mod_depth is not None    # about a third of the line has speech: judged
    assert ev.line_evidence(a, 5.5, 11.5).mod_depth is None    # almost none: not judged


def test_speech_on_one_channel_only_is_still_found(tmp_path):
    x = make_audio(SPEECH_AT, seconds=22)
    sf.write(tmp_path / "r.wav", np.stack([np.zeros_like(x), x], axis=1), SR)
    _, s = make_files(tmp_path)
    assert len(analyse_files(tmp_path / "r.wav", s).of("LIKELY")) == 1      # the right channel counts too (not only channel 0)


def test_almost_no_sound_is_no_speech_not_low_speech():
    an = run([(5.5, 11.5, "Something said after the talking had already ended")])
    assert an.findings[0].reasons[0][0] == "NO_SPEECH" and an.findings[0].level == "LIKELY"


def test_low_unique_ratio_alone_is_a_loop():
    words = "red blue green blue red green green red blue green red blue red green blue red".split()
    t = " ".join(words)
    assert len(words) >= 12 and tc.loop_kind(t) and "different words" in tc.loop_kind(t)


def test_short_text_is_not_judged_by_unique_ratio():
    assert tc.loop_kind("ok go ok go ok go ok") is None


def test_long_word_repeated_is_a_loop():
    k = tc.loop_kind("welcome welcome welcome welcome")
    assert k and "repeated 4" in k


def test_old_style_line_endings():
    assert len(parse_subtitles(SRT.replace("\n", "\r"))) == 2


def test_srt_never_writes_negative_times():
    assert format_srt([Segment(-1.0, 0.5, "a")]).startswith("1\n00:00:00,000 --> 00:00:00,500")
