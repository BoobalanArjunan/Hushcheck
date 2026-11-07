# HushCheck 2: Design Note

**Author:** Boobalan Arjunan  **Status:** proposal, not yet implemented  **Date:** 7 Nov 2026

## 0. Instructions for the implementer (read first)
1. Do **not** run anything on evaluation data. Do **not** change any threshold in `src/hushcheck/` until the evaluation rule
   (`HUSHCHECK2_EVALUATION_RULE.md`) is committed and tagged.
2. Do **not** reuse the data from the first evaluation (tag `eval-spec-v2`: AMI ES2002a, IS1000a, TS3003a; the three piano
   tracks; the two noise tracks; the 43 development clips). It is used up. It may be used only for the one exploratory analysis
   in section 7, which is labelled "not evidence".
3. Never use `--force`. Never paste tokens anywhere. Audio files stay out of git.
4. Everything borrowed from whisper-guard is credited (section 5).

## 1. Why a version 2
HushCheck 1 was evaluated once under pre-set criteria and did not meet them (strict mode: 53% recall on silence inventions;
review mode: 3.7% false alarms against whisper-guard's 0.4%). Its weakness: evidence from the audio alone scored 1 or 2 points for
text invented over music or over pauses with room noise, so it could not reach the auto-flag level.
whisper-guard (MIT, Hevin Yeh) reasons only from Whisper's own numbers and text/timing, and its README says it cannot catch a
"fluent phantom" (one grammatical sentence with healthy metrics over silence). HushCheck's audio evidence is what it lacks.
The two kinds of evidence are independent, so agreement between them is a principled basis for the auto-flag level.

## 2. What HushCheck 2 is
A report-only checker: for each transcript line it says LIKELY (auto-flag), SUSPECT (review) or OK, with the reasons.
It never edits a transcript. Two evidence families:
- **Audio evidence** (existing): from the audio under the line's time span.
- **Text/timing evidence** (new, from whisper-guard's ideas, reimplemented): from the transcript's own timing, text and Whisper metrics.

**Principle:** LIKELY needs a score of at least 3, and a score of 3 reached from one family alone is allowed only for the
two strongest audio signals. Otherwise LIKELY needs evidence from **both** families.

## 3. Signals and weights (fixed before any test; reasoned, not fitted)
Existing signals (agent: copy exact names, weights and thresholds from the code into this table before freezing).

| Signal | Family | Weight | Meaning |
|---|---|---|---|
| NO_SPEECH | audio | 3 | active sound under the line below `NO_SPEECH_BELOW` (0.15) |
| BEYOND_AUDIO | audio | 3 | the line starts after the audio ends |
| LOW_SPEECH | audio | 1 | active sound below `LOW_SPEECH_BELOW` (see 4) |
| NOT_SPEECH_LIKE | audio | 1 | syllable-rate modulation depth below `NOT_SPEECH_DEPTH` (0.20) |
| REPEAT | text | 1 | repeated text |
| PHANTOM_PHRASE | text | (as in code) | phrase-list match |

New signals:

| Signal | Family | Weight | Source idea | Rule |
|---|---|---|---|---|
| SPARSE_WINDOW | text/timing | 2 | whisper-guard `_sparse_flags` | a decoding window of at least 10 s with under 1.0 letters/digits/CJK characters per second |
| LOOP | text | 1 | whisper-guard L4 | a 2-4 character unit repeated 3 or more times; purely numeric units are exempt (see 5) |
| LONG_REPEAT | text | 1 | whisper-guard L3 (windowed) | word-uniqueness ratio averaged over 100-word windows below 0.35 |

New guard (not a signal): **DENSE_CONFIDENT** (whisper-guard "rescue"). A decoding window of at least 5 s, at least 2.0
characters per second and `avg_logprob` above -0.5 is treated as speech **as far as Whisper's own `no_speech_prob` is concerned**.
It never cancels audio evidence: it only stops a high `no_speech_prob` from being counted against the line.

Decoding window: consecutive segments with identical `(no_speech_prob, avg_logprob)` form one window (this is how Whisper
reports a 30 s decoding window). A window without usable numeric `start`/`end` is never judged by timing rules.

Batch silence gate (if HushCheck uses a batch-level no-speech gate): use the smaller of the plain mean and the duration-weighted
mean, so a few short silent tails cannot outvote long clear speech.

Short segments (under 1.6 s) use a more lenient `avg_logprob` limit (-1.7 instead of -1.5), because brief real utterances score low.

**Modes:** AUTO = LIKELY (score at least 3, with the principle in section 2). REVIEW = LIKELY or SUSPECT (score at least 1).

## 4. Thresholds: calibrated on separate data, then frozen
Thresholds that decide false alarms on real speech (`LOW_SPEECH_BELOW`, `NOT_SPEECH_DEPTH`) are **not** chosen by looking at
the first evaluation's errors (the 0.28 in `eval-spec-v2` was fitted to the 43 development clips and is retired).
Procedure (all on the **calibration set** of the evaluation rule, never on the test set):
1. Measure the active fraction and modulation depth for every real-speech line.
2. Set each threshold at the value where that signal alone would flag about 1% of those real lines.
3. Write the chosen values, the number of lines used and the date into `docs/CALIBRATION.md`, commit, then freeze.
The whisper-guard numbers (10 s / 1.0 chars per s; 5 s / 2.0 chars per s / -0.5; 1.6 s / -1.7) are used **as published**, not
tuned. They were measured by whisper-guard's author on faster-whisper large-v3, and this project uses openai-whisper `small`, so
`docs/CALIBRATION.md` also records how often each text/timing rule fires on the calibration set's real speech.


## 6. Tests and hygiene (before any real data)
- Unit tests for every signal on generated audio and hand-written transcripts, including the cases whisper-guard's own tests
  cover as principles: numbers are never flagged as loops; 30 s of clear speech plus short silent tails is not wiped; a long real
  transcript is not flagged as repetitive; a 1 s phrase over silence is not treated as a dense window.
- Planted-bug checks (mutation tests): change a threshold, a comparison or a weight and confirm a test fails.
- A version test like whisper-guard's `test_version.py`: the version in the package must equal the installed metadata, with one
  source for the version number.
- A regression test that pins the unit-test corpus results. It is a **regression guard, not accuracy evidence**; say so in the
  README, as whisper-guard does.

## 7. One exploratory analysis allowed on the used-up data
Compute, on the saved eval-spec-v2 transcripts, the union "HushCheck 1 flags OR whisper-guard drops/rewrites" and the new signals'
firing rates. Label the output **"exploratory, not evidence"**. It informs whether the idea is worth finishing. It must not be
used to choose or change any threshold.

## 8. audioaudit
Until HushCheck 2 passes its evaluation, `audioaudit` lists the transcript check as **experimental** and excludes it from the
default run. If only one mode passes, only that mode is documented and enabled.

## 9. README statements to prepare (only what is true)
- "HushCheck 1 did not meet its pre-set criteria on its single evaluation (results.md); version 2 changes the design."
- The borrowed ideas and their source, with the licence.
- The evaluation set, its size, its limits (lines within a recording are not independent), and the results with cluster-bootstrap
  ranges, once they exist.

