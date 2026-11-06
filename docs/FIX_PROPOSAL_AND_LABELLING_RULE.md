# HushCheck: Fix Proposal, Labelling Protocol, and Evaluation Specification

**Author**: Boobalan Arjunan  
**Date**: November 2026  
**Status**: Revised Specification for Review (Prior to Execution)

---

## 1. Locked Evaluation Criteria (Fixed in Advance)

This protocol governs the single evaluation run on the authentic evaluation dataset. No thresholds will be altered after this evaluation runs.

### Claim (a): Auto-flag Mode (`LIKELY`)
- **Metric 1 (False-Alarm Rate on Real Speech)**: False-alarm rate on real speech lines must be $\le 1.0\%$ point estimate, and the upper bound of the 95% Wilson score confidence interval must be $\le 2.5\%$. Evaluated on **at least $N \ge 300$ real speech lines**. *(Mathematical note: at $N = 100$, even 0 false alarms yields a 95% Wilson upper bound of $3.7\%$, making the $\le 2.5\%$ requirement unreachable; at $N \ge 300$, 0 false alarms yields an upper bound of $1.25\%$ and 1 false alarm yields $1.85\%$, making the criterion statistically sound and attainable on real corpora).*
- **Metric 2 (Recall on Silence / Near-Silence Inventions)**: Recall on hallucinations occurring over silence or near-silence ($< 15\%$ active sound) must be $\ge 80\%$ (lower bound of 95% Wilson interval $\ge 60\%$), evaluated on at least $N \ge 30$ silence/near-silence lines.
- **Precision Metric Dropped**: As noted in peer review, precision depends heavily on the class balance of the test set (and is trivially 100% on pure non-speech audio). Claim (a) is therefore evaluated strictly via False-Alarm Rate on real speech and Recall on silence/near-silence inventions.

### Claim (b): Review Mode (`LIKELY + SUSPECT`)
- **Metric**: Recall on invented lines must be **clearly higher** than `whisper-guard` (defined as non-overlapping 95% Wilson score confidence intervals).
- **False Alarm Constraint**: False-alarm rate on real speech must be **no higher than `whisper-guard`'s** false-alarm rate.
- **Baseline Comparison**: Recall must be higher than the text-checks-only baseline.

### Stopping Rule
If both Claim (a) and Claim (b) pass, HushCheck proceeds toward release documentation. If either fails, we stop under the fixed rule; HushCheck remains documented as an experimental prototype with findings published in an article, and is not submitted to PyPI.

---

## 2. Frozen Environment & Whisper Inference Specification

To ensure run-to-run reproducibility, complete immutability, and zero stochastic variance:
- **Python Version**: Python 3.13.3 (macOS arm64).
- **Core Library Versions (from `pip freeze`)**:
  - `openai-whisper==20250625`
  - `torch==2.15.0`
  - `whisper-guard==0.3.3`
  - `scipy==1.18.1`
  - `numpy==2.5.4`
  - `soundfile==0.14.0`
- **Whisper Model**: `small` (`small.pt`, 461 MB).
- **Decoding**: Greedy decoding (`temperature = 0`), zero sampling variance:
  ```bash
  whisper <audio_file> --model small --temperature 0 --output_format json --output_dir <dir>
  ```
- **Fair Baseline**: The exact same raw JSON transcripts are saved to disk and evaluated by `hushcheck`, `whisper-guard`, and `text-only checks`.
- **Single-Execution Invariant**: The evaluation script is run **exactly once** on the saved raw transcripts. No post-hoc rerun or secondary threshold tuning is allowed.
- **Git Freeze Tag**: Tagged as `eval-spec-v1` covering this specification document and the implementation of Fix A (`LOW_SPEECH_BELOW = 0.28`).

---

## 3. Authentic Evaluation Corpus & Sizing

The evaluation set will contain **at least 100 invented lines** and **at least 300 real speech lines** across multiple independent recordings.
- **Statistical Inconclusive Rule**: Pure music and noise may produce few invented lines if Whisper outputs nothing. If the total number of invented lines across the entire test set falls under 100, the result will be reported explicitly as **inconclusive** due to sample size limits.
- **Ambiguity Reporting**: All lines falling in the ambiguous overlap zone ($20\% \le \text{overlap} < 50\%$) will be logged with timestamps and included in the final report.

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

> [!NOTE]
> **Dev-Set Fitting Disclosure**: This single threshold adjustment (Fix A) was chosen based on false-alarm observations from the 43-file semi-synthetic development set. Per our experimental protocol, this is the single permitted fix round. Its generalization will be evaluated once on the authentic dataset without further retuning.

### Fix A: Adjust `LOW_SPEECH_BELOW` from 0.35 to 0.28
- **Rationale**: In the development set, 9 of 13 false alarms occurred on natural speech phrases where inter-phrase breath or pause caused the acoustic active fraction to dip to 28%–34%. Setting `LOW_SPEECH_BELOW = 0.28` prevents flagging normal conversational breath pauses.
- **Predicted Effect on Recall**: This will slightly reduce recall on boundary segments where someone spoke for 28%–34% of a line, but will preserve detection on silence stretches ($< 15\%$, weight 3) and near-silences ($< 28\%$).
- **Cost Trade-off**: We accept a modest drop in boundary recall in exchange for driving the False-Alarm Rate on real conversational speech below the 1.0% threshold.

### Fix B: Retain `NOT_SPEECH_DEPTH = 0.20` (Do NOT Lower to 0.15)
- **Rationale**: Whisper's hallucinations over music have modulation depths around 0.16–0.18. Lowering this threshold to 0.15 would have turned off `NOT_SPEECH_LIKE` on music, collapsing recall on music-induced hallucinations. Keeping `0.20` preserves the core signal for detecting steady non-speech audio.
- **Predicted Effect**: Preserves detection capability on pure music and continuous background noise without degrading review mode (`LIKELY + SUSPECT`) recall.

### Fix C: Scoring Dynamics for Music vs. Silence
- Hallucinations over **silence** trigger `NO_SPEECH` (weight 3) $\rightarrow$ `LIKELY` (Claim a).
- Hallucinations over **steady music** trigger `NOT_SPEECH_LIKE` (weight 1) or `NOT_SPEECH_LIKE` + `REPEAT` (weight 2) $\rightarrow$ `SUSPECT` (Claim b).
- Keeping `LIKELY_AT = 3` ensures that Claim (a) maintains its $\le 1.0\%$ false-alarm rate on real speech.
