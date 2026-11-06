# HushCheck: Fix Proposal and Labelling Rule

**Author**: Boobalan Arjunan  
**Date**: November 2026  
**Status**: Proposal for Review (Prior to Execution)

---

## 1. Locked Evaluation Rule (Fixed in Advance)

This protocol governs the single evaluation round on the authentic dataset. No thresholds will be altered after running this evaluation.

1. **Two Claims, Evaluated Separately**:
   - **Claim (a) Auto-flag Mode (`LIKELY`)**: Must achieve **$\ge$ 90% precision** on real speech lines.
   - **Claim (b) Human Review Mode (`LIKELY+SUSPECT`)**: Must catch **clearly more invented lines** than `whisper-guard`, with a false-alarm rate on real speech **no higher than `whisper-guard`'s**, and catch more invented lines than text-only checks.
2. **Statistical Rigor**: "Clearly more" requires that the 95% confidence intervals (Wilson score intervals) do not overlap.
3. **One Fix Round**: Exactly one fix round is permitted. If the criteria are not satisfied on the authentic dataset, we stop and do not publish to PyPI.
4. **Data Isolation**: The authentic evaluation dataset is tested exactly once, after this proposal is locked.

---

## 2. Staged Authentic Dataset & Licensing

All audio files are staged locally in `eval_data/` and excluded from Git version control (`.gitignore`).

| Category | Source File | Description | License | Role in Benchmark |
|---|---|---|---|---|
| **Pure Music** | `music_chopin_nocturne_op9_no2.flac` | Frank Levy (piano), Chopin Nocturne Op. 9 No. 2 | CC BY 3.0 | 100% Non-speech |
| **Pure Music** | `music_debussy_clair_de_lune.ogg` | Claude Debussy, Suite bergamasque *Clair de lune* | Public Domain | 100% Non-speech |
| **Pure Music** | `music_chopin_nocturne_op9_no1.flac` | Olga Gurevich (piano), Chopin Nocturne Op. 9 No. 1 | CC BY 3.0 | 100% Non-speech |
| **Pure Noise** | `noise_rain_thunder.ogg` | Real ambient nature recording: rain, thunder, birds | CC BY-SA 3.0 | 100% Non-speech |
| **Pure Noise** | `noise_rain_concrete.wav` | Real field recording: thunderstorm rain on concrete | CC0 1.0 (Public Domain) | 100% Non-speech |
| **Real Dialogue** | `speech_iran_contra_hearing.ogg` | Rep. Boland & Sec. Weinberger Iran-Contra hearing | Public Domain | Real speech with natural pauses & room tone |
| **Unseen Reserve** | `unseen/` (3 files) | 1 real music track, 1 real speech track, 1 real dialogue | Various Open | Held out untouched until post-fix validation |

---

## 3. Objective Labelling Rules

To eliminate subjective human bias:

1. **Non-Speech Rule (Pure Music & Environmental Noise)**:
   - For all files in the **Pure Music** and **Pure Noise** categories, there is zero human speech throughout the entire audio duration (`0.0s` to `<end>`).
   - Therefore, **any text segment emitted by OpenAI Whisper is 100% invented by definition**.
   - No subjective listening or timestamp guessing is required; the ground-truth interval is `(0.0, duration)`.

2. **Real Speech Rule (Hearing Dialogue & Clean Speech)**:
   - For continuous spoken sections, all transcript lines representing words actually spoken by participants are marked **Real** (`is_invented = False`).
   - Extended conversational silences and pause intervals between speaker turns are identified by listening prior to running the tool, with start and end timestamps recorded in `labels.csv`.

---

## 4. Single Round 1 Fix Proposal (Acoustic Reasoning)

Threshold adjustments are grounded in acoustic signal properties rather than fitting to the 43 development clips:

### Fix A: Adjust `LOW_SPEECH_BELOW` from 0.35 to 0.25
- **Acoustic Rationale**: Human speech is naturally punctuated by breathing and inter-phrase pauses. In natural conversational dialogue, a short sentence (e.g., 3.5 seconds) followed by a 1-second pause before the next turn naturally yields an active acoustic fraction around 28%–32%. The previous threshold of 0.35 treated any segment with less than 35% sound as `LOW_SPEECH`, penalizing natural conversational pacing (accounting for 9 of the 13 false alarms on real dialogue). Lowering the boundary to **0.25** accommodates natural phrase pauses while continuing to catch segments where 75%+ of the time is empty silence.

### Fix B: Adjust `NOT_SPEECH_DEPTH` from 0.20 to 0.15
- **Acoustic Rationale**: Speech over background musical accompaniment or unmodulated speaking styles often displays modulation depths in the 0.16–0.19 range. A threshold of **0.15** strictly isolates genuinely flat acoustic profiles (continuous droning hums, steady organ/synth chords) without misclassifying accompanied or monotone human voices.

### Fix C: Preservation of Strict Auto-Flag Precision (`LIKELY`)
- `LIKELY` will continue to require a score of $\ge 3$.
- `NO_SPEECH` over silence (weight 3) and `BEYOND_AUDIO` (weight 3) automatically qualify as `LIKELY`.
- Music-only segments without textual repetition will remain in `SUSPECT` (weight 1 for `NOT_SPEECH_LIKE`), ensuring that `LIKELY` maintains its high precision ($\ge 90\%$) requirement for auto-flagging.
