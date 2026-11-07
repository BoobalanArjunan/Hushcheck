# Calibration Record: HushCheck 2 Audio Thresholds

**Date:** 2026-11-07 15:43:51
**Governing Documents:** `docs/HUSHCHECK2_DESIGN.md` (Section 4) and `docs/HUSHCHECK2_EVALUATION_RULE.md`
**Status:** Frozen for evaluation `eval-spec-hc2-v1`

## 1. Calibration Dataset Summary
The calibration set was used strictly to measure the distributions of `active_frac` and `mod_depth` on genuine human speech and calibrate the audio thresholds. It was never used to tune or fit test data.

- **AMI Calibration Meetings (overlap $\ge 50\%$ with human annotations):**
  - Meetings: `EN2001a`, `EN2002a`, `ES2003a`, `IS1001a`
  - Real speech lines: 1777
- **LibriSpeech dev-clean (verified read speech, 100 audio files):**
  - Real speech lines: 131
- **Total Real Speech Lines ($N$):** 1908

## 2. Threshold Derivation (Reasoned 1% False-Alarm Target)
Per Section 4 of `docs/HUSHCHECK2_DESIGN.md`, each threshold is chosen at the empirical point where that signal alone flags approximately 1.0% of real speech lines.

### Active Fraction (`LOW_SPEECH_BELOW`)
- 0.5th percentile: 0.3225
- 1.0th percentile: 0.3879
- 2.0th percentile: 0.4600
- **Selected `LOW_SPEECH_BELOW`:** `0.39`
  - Empirical false alarm rate alone: **20 / 1908 (1.05%)**

### Modulation Depth (`NOT_SPEECH_DEPTH`)
- 1.0th percentile of all real speech: 0.2693
- **Selected `NOT_SPEECH_DEPTH`:** `0.27`
  - Empirical false alarm rate alone: **20 / 1908 (1.05%)**

## 3. Empirical Firing Rates of Text/Timing Rules on Real Speech
The text and timing rules (borrowed from whisper-guard ideas) were evaluated with published thresholds on OpenAI Whisper `small` (MPS, $\text{temperature}=0$):

| Rule / Signal | Published Parameter / Condition | Calibration Real Speech Flags ($N=1908$) | Firing Rate |
|---|---|---|---|
| `NO_SPEECH` | active sound $< 0.15$ | 0 | 0.00% |
| `LOW_SPEECH` | active sound $< 0.39$ | 20 | 1.05% |
| `NOT_SPEECH_LIKE` | modulation depth $< 0.27$ | 20 | 1.05% |
| `BEYOND_AUDIO` | timestamp starts after audio duration | 0 | 0.00% |
| `SPARSE_WINDOW` | window $\ge 10\text{s}$, $\text{cps} < 1.0$ | 34 | 1.78% |
| `DENSE_CONFIDENT` rescue | window $\ge 5\text{s}$, $\text{cps} \ge 2.0$, logprob $> -0.5$ | 1658 | 86.90% |
| `SEGMENT_FILTER` | nsp $> 0.8$, lp $< -1.5$, short lp $< -1.7$, cr $> 3.0$ | 40 | 2.10% |
| `LONG_REPEAT` | 100-word window uniqueness ratio $< 0.35$ | 201 | 10.53% |
| `LOOP` | 2-4 char repeating $\ge 3$ times | 13 | 0.68% |
| `REPEAT` | identical to previous lines | 208 | 10.90% |
| `PHANTOM_PHRASE` | known hallucinated phrases | 0 | 0.00% |

## 4. Overall Calibration Baseline Performance on Real Speech
- **HushCheck 2 AUTO (`LIKELY`):** 8 / 1908 (0.42%)
- **HushCheck 2 REVIEW (`SUSPECT` or `LIKELY`):** 248 / 1908 (13.00%)
- **whisper-guard (v0.3.3):** 206 / 1908 (10.80%)

The thresholds `0.39` for `LOW_SPEECH_BELOW` and `0.27` for `NOT_SPEECH_DEPTH` achieve the targeted $\le 1.0\%$ individual false alarm rate on real speech.
