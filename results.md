# Authentic Benchmark Results: HushCheck vs. Whisper-Guard

**Protocol Tag**: `eval-spec-v2`  
**Execution Timestamp**: November 2026  
**Execution Status**: Single Run Completed (Frozen Specification)

---

## 1. Executive Summary & Verdict

| Claim | Locked Criterion | Observed Result | Status |
|---|---|---|---|
| **Claim (a): Auto-flag (`LIKELY`)** | FAR $\le 1.0\%$ (95% upper bound $\le 2.5\%$ on $N \ge 300$), Silence Recall $\ge 80\%$ ($N \ge 30$) | FAR: 0.1% (0.0–0.7%) (1/758 FAs). Silence Recall: 53.3% (47.2–59.3%) (137/257). | **FAIL** |
| **Claim (b): Review (`LIKELY+SUSPECT`)** | Recall clearly higher than whisper-guard (non-overlapping 95% Wilson intervals), FAR $\le$ whisper-guard's, Recall > text-only ($N \ge 100$) | Review Recall: 91.1% (88.0–93.4%) (407/447) vs. WG: 84.1% (80.4–87.2%) (376/447). FAR: 3.7% (2.6–5.3%) vs. WG: 0.4% (0.1–1.2%). | **FAIL** |

### Overall Verdict: STOP RULE TRIGGERED — One or more claims did not satisfy the strict locked criteria.

---

## 2. False-Alarm Rate on Real Human Speech ($N = 758$)

Evaluated on natural multi-speaker conversation in the AMI Meeting Corpus with $\ge 50\%$ annotated speech overlap.

| Method | False Alarms | False-Alarm Rate (Point) | 95% Wilson Confidence Interval |
|---|---|---|---|
| **HushCheck `LIKELY` (Auto-flag)** | 1 | 0.13% | 0.1% (0.0–0.7%) |
| **HushCheck `LIKELY+SUSPECT` (Review)** | 28 | 3.69% | 3.7% (2.6–5.3%) |
| **`whisper-guard` (Default)** | 3 | 0.40% | 0.4% (0.1–1.2%) |
| **Text-only Checks** | 19 | 2.51% | 2.5% (1.6–3.9%) |

---

## 3. Recall on Invented Lines (Hallucinations)

### A. Hallucinations Over AMI Meeting Pauses & Silence ($N = 257$)
Defined by AMI ground-truth annotations ($< 20\%$ speech overlap).

| Method | Caught | Recall (Point) | 95% Wilson Confidence Interval |
|---|---|---|---|
| **HushCheck `LIKELY`** | 137 | 53.3% | 53.3% (47.2–59.3%) |
| **HushCheck `LIKELY+SUSPECT`** | 219 | 85.2% | 85.2% (80.4–89.0%) |
| **`whisper-guard`** | 186 | 72.4% | 72.4% (66.6–77.5%) |
| **Text-only Checks** | 168 | 65.4% | 65.4% (59.4–70.9%) |

### B. All Invented Lines Across the Authentic Corpus ($N = 447$)
Including AMI silence pauses ($N=257$), pure instrumental music ($N=111$), and pure environmental noise ($N=79$).

| Method | Caught | Recall (Point) | 95% Wilson Confidence Interval |
|---|---|---|---|
| **HushCheck `LIKELY+SUSPECT` (Review)** | 407 | 91.1% | 91.1% (88.0–93.4%) |
| **HushCheck `LIKELY` (Auto-flag)** | 238 | 53.2% | 53.2% (48.6–57.8%) |
| **`whisper-guard` (Default)** | 376 | 84.1% | 84.1% (80.4–87.2%) |
| **Text-only Checks** | 353 | 79.0% | 79.0% (75.0–82.5%) |

### C. Category Recall Breakdown (Review Mode)

| Category | Total Lines | HushCheck Review Caught | HushCheck Recall | whisper-guard Caught | whisper-guard Recall |
|---|---|---|---|---|---|
| **AMI Silence Pauses** | 257 | 219 | 85.2% | 186 | 72.4% |
| **Pure Instrumental Music** | 111 | 109 | 98.2% | 111 | 100.0% |
| **Pure Environmental Noise** | 79 | 79 | 100.0% | 79 | 100.0% |

---

## 4. Ambiguous Lines Logged & Excluded

Total ambiguous lines ($20\% \le \text{overlap} < 50\%$): **89 lines**.  
Exported to [`ambiguous_lines.csv`](./ambiguous_lines.csv) with full start/end timestamps and detector verdicts.

---

## 5. Decision Rule Check Details

- **Claim (a) Checks**:
  - Sample size $N_{real} \ge 300$: **758** (PASS)
  - False-Alarm Rate point estimate $\le 1.0\%$: **0.13%** (PASS)
  - False-Alarm Rate 95% Wilson upper bound $\le 2.5\%$: **0.74%** (PASS)
  - Silence recall $\ge 80\%$ ($N_{silence} \ge 30$): **53.3%** ($N=257$) (FAIL)

- **Claim (b) Checks**:
  - Sample size $N_{inv} \ge 100$: **447** (PASS)
  - Recall clearly higher than whisper-guard (non-overlapping 95% intervals): **91.1% (88.0–93.4%) vs. 84.1% (80.4–87.2%)** (PASS)
  - FAR no higher than whisper-guard's: **3.69% vs. 0.40%** (FAIL)
  - Recall higher than text-checks-only: **91.1% vs. 79.0%** (PASS)
