# HushCheck 2: Evaluation Rule (write, commit and tag BEFORE any test data is transcribed or scored)

**Author:** Boobalan Arjunan  **Status:** draft for review  **Tag to create on freezing:** `eval-spec-hc2-v1`

## 1. Principle
This rule applies to the single test run of HushCheck 2. The first evaluation's data is used up. Nothing here may be changed after
the test data is touched. If anything below is wrong, fix it BEFORE the test and create a new tag (`eval-spec-hc2-v2`); never move a tag.

## 2. Data (all new; record every recording ID, source and licence in `ATTRIBUTIONS.md`)
**Excluded (used up):** AMI ES2002a, IS1000a, TS3003a; the three piano tracks and two noise tracks of the first run; the 43 development clips.

| Set | Contents | Role |
|---|---|---|
| Calibration | 4 AMI meetings not used before (EN2001a, EN2002a, ES2003a, IS1001a); 100 LibriSpeech dev-clean files | choose the audio thresholds (design note section 4) and measure how often the text/timing rules fire on real speech |
| Test | at least 6 AMI meetings not used before (EN2003a, ES2004a, IS1003a, TS3004a, EN2004a, EN2005a); 100 LibriSpeech test-clean read speech files; at least 6 music-only recordings (at least 2 genres, not the used piano tracks); at least 4 noise-only recordings (not the used two) | the single scored run |
| Unseen reserve | 2 further recordings of each kind | opened only after the test, only for a sanity check |

Check each dataset's licence. Audio stays out of git. Test and calibration recordings must be different recordings.

## 3. Fixed settings
- Whisper: the same as the first run (openai-whisper 20250625, model `small`, `--temperature 0`). Record `pip freeze` in the repo.
- Transcripts are generated once, saved raw, and the same files go to HushCheck 2, whisper-guard (installed defaults) and the text-only
  baseline (the text checks in the HushCheck version being tested).
- The evaluation script is written first, then **dry-run on the calibration set** so that crashes and format problems happen there,
  not on the test data. After the script is frozen, any change is limited to crash fixes and must be logged (what changed, why, and
  that no result had been seen).

## 4. Labels (objective, fixed)
- Music-only and noise-only recordings: every line Whisper writes is **invented**.
- AMI: a line is **invented** if less than 20% of its time overlaps annotated speech, **real** if 50% or more does, **ambiguous**
  in between. Ambiguous lines are excluded from all tallies, written to `ambiguous_lines.csv`, and counted in the report.
- The "silence-pause" category is the AMI invented lines (defined by the labels, never by HushCheck's own measures).

## 5. Sizes
At least 100 invented lines and at least 300 real lines, from at least 10 recordings in total. If the invented total is under 100, or
the real total is under 300, the result is reported as **inconclusive**.

## 6. Statistics
Lines within a recording are not independent. The primary 95% ranges use a **cluster bootstrap over recordings** (10,000
resamples, recordings as the unit). Wilson ranges are reported as a secondary, optimistic view. For comparisons with whisper-guard,
use the paired difference over the same lines in the same bootstrap resamples. Report the per-recording table.

## 7. Claims (primary configuration: HushCheck 2 alone, no whisper-guard column)

**Claim (a): AUTO mode (LIKELY).**
- False-alarm rate on real lines: point estimate at most 1.0% and cluster-bootstrap upper bound at most 3.0%.
- Recall on AMI silence-pause inventions: point estimate at least 70% and cluster-bootstrap lower bound at least 55%.
- At least 30 LIKELY flags overall.

**Claim (b): REVIEW mode (LIKELY or SUSPECT).**
- Recall on all invented lines: higher than whisper-guard's, with the paired-difference cluster-bootstrap 95% range above zero;
  and higher than the text-only baseline's by the same test.
- False-alarm rate on real lines: point estimate at most 2.0% and cluster-bootstrap upper bound at most 4.0%.

**Disclosure of what changed from the first rule (written before the data exists):**
- Claim (a) recall target is 70% instead of 80%. 80% was a stretch target that the first design missed by a wide margin
  (53%); whisper-guard reached 72% on the same lines. The bar is not set below what whisper-guard reached.
- Claim (b)'s false-alarm condition is an absolute 2.0% instead of "no higher than whisper-guard's". A review mode feeds a human queue
  and accepts some false alarms; the stricter relative condition (not higher than whisper-guard's) is **also reported**, as information.
- The first-run data and whisper-guard's results on it were known when these numbers were chosen.
- **Pre-tag expansion of test set:** Added 2 further unused AMI meetings (`EN2004a`, `EN2005a`) and 100 LibriSpeech `test-clean`
  read speech files to the test set prior to tag freeze, expanding the real-speech clusters to 6 meetings and 100 audio files to ensure
  a robust cluster bootstrap.
- **Exploratory secondary metric:** A second clearly labelled line in the report reports real speech false alarms excluding lines whose
  text is an obvious decoder collapse (exploratory, not the claim), while keeping the primary strict labelling rule completely unchanged.

**Secondary, exploratory (no pass/fail, no claim):** the configuration "HushCheck 2 OR whisper-guard", false alarms excluding decoder collapses, and per-signal firing rates.

## 8. Decision
- Both claims pass: release HushCheck as an alpha pre-release with the full table, the limits and this rule's text.
- Only (a) passes: document and enable only AUTO mode; REVIEW stays experimental.
- Only (b) passes: document and enable only REVIEW mode; AUTO stays experimental.
- Neither passes or the result is inconclusive: stop. HushCheck stays public as a documented experiment, is excluded from `audioaudit`,
  and the findings go into an article. No further tuning on these data.
- One test run. Changes after it are a new version and need new data and a new rule.

## 9. Deliverables (committed and pushed whatever the outcome)
`results.md` (claims, per-recording table, bootstrap ranges), `ambiguous_lines.csv`, raw Whisper JSON, `pip freeze`, the evaluation
script with its edit log, `docs/CALIBRATION.md`, and the tag `eval-spec-hc2-v1` on the commit that holds this file and the code.

