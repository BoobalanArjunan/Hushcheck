# HushCheck: Fix Proposal, Labelling Protocol, and Evaluation Specification

**Author**: Boobalan Arjunan  
**Date**: November 2026  
**Status**: Revised Specification for Review (Prior to Execution)

---

## 1. Locked Evaluation Criteria (Fixed in Advance)

This protocol governs the single evaluation run on the authentic evaluation dataset. No thresholds will be altered after this evaluation runs.

### Claim (a): Auto-flag Mode (`LIKELY`)
- **Metric**: False-alarm rate on real speech lines $\le 1.0\%$ (with the upper bound of the 95% Wilson score confidence interval $\le 2.5\%$).
- **Precision Target**: $\ge 90\%$ precision on silence and beyond-audio hallucinations.
- **Minimum Flag Threshold**: Requires at least $N \ge 30$ `LIKELY` flags in the test set to be statistically meaningful.

### Claim (b): Review Mode (`LIKELY + SUSPECT`)
- **Metric**: Recall on invented lines must be **clearly higher** than `whisper-guard` (defined as non-overlapping 95% Wilson score confidence intervals).
- **False Alarm Constraint**: False-alarm rate on real speech must be **no higher than `whisper-guard`'s** false-alarm rate.
- **Baseline Comparison**: Recall must be higher than the text-checks-only baseline.

### Stopping Rule
If both Claim (a) and Claim (b) pass, HushCheck proceeds toward release documentation. If either fails, we stop under the fixed rule; HushCheck remains documented as an experimental prototype with findings published in an article, and is not submitted to PyPI.

---

## 2. Fixed Whisper Inference Specification

To ensure run-to-run reproducibility and zero stochastic variance:
- **Engine**: OpenAI Whisper (`openai-whisper==20250625`, PyTorch 2.15).
- **Model**: `small` (`small.pt`, 461 MB).
- **Decoding**: Greedy decoding (`temperature = 0`), zero sampling variance:
  ```bash
  whisper <audio_file> --model small --temperature 0 --output_format json --output_dir <dir>
  ```
- **Fair Baseline**: The exact same JSON transcripts are evaluated by `hushcheck`, `whisper-guard`, and `text-only checks`.

---

## 3. Authentic Evaluation Corpus & Sizing

The evaluation set will contain **at least 100 invented lines** and **at least 100 real lines** across multiple independent recordings.

| Category | Dataset / Sources | Volume | Description & License |
|---|---|---|---|
| **A. Pure Instrumental Music** | Chopin Nocturnes (Levy & Gurevich), Debussy (*Clair de lune*), Joplin Ragtime | 5 complete tracks (~25 min) | CC BY 3.0 / Public Domain. **100% Non-speech**. |
| **B. Pure Environmental Noise** | Nature field recordings (rain on concrete, thunderstorm, nature ambience) | 3 tracks (~20 min) | CC0 / CC BY-SA 3.0. **100% Non-speech**. |
| **C. Natural Meetings with Pauses** | AMI Meeting Corpus (`ES2002a`, `IS1000a`, `TS3003a`) | 3 meetings (~60 min) | CC BY 4.0. Natural multi-speaker meetings with real conversational turn-taking, pauses, and room tone. |
| **D. Unseen Reserve** | 3 independent recordings (1 meeting, 1 music, 1 noise) | 3 files | Kept in `unseen_real/` and untouched until final check. |

---

## 4. Objective Labelling Protocol

To eliminate subjective manual bias:

1. **Non-Speech Rule (Pure Music & Environmental Noise)**:
   - Pure music and noise recordings contain zero human speech ($[0.0, \text{duration}]$).
   - Therefore, **100% of transcript lines emitted by Whisper on these tracks are defined as Invented**.

2. **Real Speech & Silence Overlap Rule (AMI Meetings)**:
   - Evaluated against AMI's official time-aligned speech word annotations (`ami_public_manual_1.6.2.zip`):
     - **Invented**: $< 20\%$ of the transcript line's duration overlaps annotated human speech.
     - **Real**: $\ge 50\%$ of the transcript line's duration overlaps annotated human speech.
     - **Ambiguous**: Lines with $20\% \le \text{overlap} < 50\%$ are excluded from tallies.

---

## 5. Single Round 1 Fix Proposal & Predicted Effects

### Fix A: Adjust `LOW_SPEECH_BELOW` from 0.35 to 0.28
- **Rationale**: In the development set, 9 of 13 false alarms occurred on natural speech phrases where inter-phrase breath or pause caused the acoustic active fraction to dip to 28%–34%. Setting `LOW_SPEECH_BELOW = 0.28` prevents flagging normal conversational breath pauses.
- **Predicted Effect on Recall**: This will slightly reduce recall on boundary segments where someone spoke for 28%–34% of a line, but will preserve detection on silence stretches ($< 15\%$, weight 3) and near-silences ($< 28\%$).

### Fix B: Retain `NOT_SPEECH_DEPTH = 0.20` (Do NOT Lower to 0.15)
- **Rationale**: Whisper's hallucinations over music have modulation depths around 0.16–0.18. Lowering this threshold to 0.15 would have turned off `NOT_SPEECH_LIKE` on music, collapsing recall on music-induced hallucinations. Keeping `0.20` preserves the core signal for detecting steady non-speech audio.

### Fix C: Scoring Dynamics for Music vs. Silence
- Hallucinations over **silence** trigger `NO_SPEECH` (weight 3) $\rightarrow$ `LIKELY` (Claim a).
- Hallucinations over **steady music** trigger `NOT_SPEECH_LIKE` (weight 1) or `NOT_SPEECH_LIKE` + `REPEAT` (weight 2) $\rightarrow$ `SUSPECT` (Claim b).
- Keeping `LIKELY_AT = 3` ensures that Claim (a) maintains its $\le 1.0\%$ false-alarm rate on real speech.
