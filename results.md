# HushCheck 2 Evaluation Report (EVAL)

**Date:** 2026-11-07T10:52:19
**Governing Rule:** `docs/HUSHCHECK2_EVALUATION_RULE.md` (Tag: `eval-spec-hc2-v1`)
**Status:** STOPPED

## 1. Summary of Claims
| Claim | Metric | Point Estimate | Cluster-Bootstrap 95% CI | Target | Status |
|---|---|---|---|---|---|
| **Claim (a): AUTO (LIKELY)** | Real Speech False-Alarm Rate (Strict) | 0.98% (27/2744) | [0.05%, 2.56%] | $\le 1.0\%$, upper $\le 3.0\%$ | PASS |
| | *Exploratory: Excl. Decoder Collapse* | *0.21% (5/2398)* | *[0.00%, 0.58%]* | *(exploratory, not claim)* | *Info* |
| | AMI Silence-Pause Recall | 56.52% (130/230) | [33.33%, 83.54%] | $\ge 70.0\%$, lower $\ge 55.0\%$ | FAIL |
| | Total LIKELY Flags | 213 | — | $\ge 30$ | PASS |
| **Claim (b): REVIEW** | Recall vs whisper-guard diff | +31.60% | [+14.08%, +44.24%] | $> 0$ (paired bootstrap) | PASS |
| | Recall vs text-only diff | +25.69% | [+12.31%, +36.24%] | $> 0$ (paired bootstrap) | PASS |
| | Real Speech False-Alarm Rate (Strict) | 17.09% (469/2744) | [5.25%, 37.69%] | $\le 2.0\%$, upper $\le 4.0\%$ | FAIL |
| | *Exploratory: Excl. Decoder Collapse* | *5.13% (123/2398)* | *[2.72%, 7.31%]* | *(exploratory, not claim)* | *Info* |

## 2. Overall Comparison Across Methods ($N_{real}=2744$, $N_{invented}=288$)
| Method | Mode | Invented Recall (All 288) | AMI Silence Recall (230) | Real Speech False Alarms (2744) | Real FA Excl. Collapse (2398) |
|---|---|---|---|---|---|
| **HushCheck 2** | AUTO (`LIKELY`) | 64.6% | 56.5% | 27/2744 (0.98%) | 5/2398 (0.21%) |
| **HushCheck 2** | REVIEW (`LIKELY+SUS`) | 86.5% | 83.0% | 469/2744 (17.09%) | 123/2398 (5.13%) |
| **whisper-guard (v0.3.3)** | Default filter | 54.9% | 43.9% | 293/2744 (10.68%) | 2/2398 (0.08%) |
| **Text-only Baseline** | Regex/phantom | 60.8% | 50.9% | 347/2744 (12.65%) | — |

## 3. Per-Recording Table
| Recording | Category | Lines | Real Lines | Real FA (LIKELY) | Real FA (Review) | Real FA (WG) | Invented Lines | Inv Caught (LIKELY) | Inv Caught (Review) | Inv Caught (WG) | Ambiguous |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `EN2003a.Mix-Headset` | ami | 523 | 485 | 1 | 24 | 0 | 13 | 5 | 12 | 0 | 25 |
| `EN2004a.Mix-Headset` | ami | 1003 | 963 | 0 | 76 | 0 | 14 | 5 | 10 | 0 | 26 |
| `EN2005a.Mix-Headset` | ami | 191 | 183 | 0 | 8 | 1 | 2 | 0 | 0 | 0 | 6 |
| `ES2004a.Mix-Headset` | ami | 485 | 414 | 15 | 242 | 230 | 37 | 13 | 31 | 22 | 34 |
| `IS1003a.Mix-Headset` | ami | 323 | 194 | 2 | 20 | 1 | 92 | 41 | 68 | 27 | 37 |
| `TS3004a.Mix-Headset` | ami | 487 | 352 | 9 | 97 | 61 | 72 | 66 | 70 | 52 | 63 |
| `music_bach_partita3_prelude` | music | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `music_beethoven_symphony5_allegro` | music | 15 | 0 | 0 | 0 | 0 | 15 | 15 | 15 | 15 | 0 |
| `music_joplin_the_entertainer` | music | 8 | 0 | 0 | 0 | 0 | 8 | 8 | 8 | 8 | 0 |
| `music_tchaikovsky_waltz_flowers` | music | 16 | 0 | 0 | 0 | 0 | 16 | 16 | 16 | 16 | 0 |
| `music_vivaldi_winter_allegro` | music | 7 | 0 | 0 | 0 | 0 | 7 | 5 | 7 | 7 | 0 |
| `music_vivaldi_winter_largo` | music | 5 | 0 | 0 | 0 | 0 | 5 | 5 | 5 | 5 | 0 |
| `noise_rain_thunder` | noise | 1 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 0 | 0 |
| `noise_sea_waves` | noise | 1 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 1 | 0 |
| `noise_waterfall_birds` | noise | 2 | 0 | 0 | 0 | 0 | 2 | 2 | 2 | 2 | 0 |
| `noise_wind_pine_forest` | noise | 3 | 0 | 0 | 0 | 0 | 3 | 3 | 3 | 3 | 0 |
| `1320-122617-0001` | librispeech | 3 | 3 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| `1320-122617-0002` | librispeech | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `1320-122617-0003` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `1320-122617-0004` | librispeech | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `1320-122617-0005` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `1320-122617-0006` | librispeech | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `1320-122617-0010` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `1320-122617-0011` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `1320-122617-0012` | librispeech | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `1320-122617-0013` | librispeech | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `1320-122617-0015` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `1320-122617-0017` | librispeech | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `1320-122617-0019` | librispeech | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `1320-122617-0020` | librispeech | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `1320-122617-0021` | librispeech | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `1320-122617-0022` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `1320-122617-0025` | librispeech | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `1320-122617-0026` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `1320-122617-0033` | librispeech | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `1320-122617-0036` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `1320-122617-0040` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `1320-122617-0041` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-75918-0000` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-75918-0001` | librispeech | 4 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-75918-0002` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-75918-0003` | librispeech | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-75918-0004` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-75918-0005` | librispeech | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-75918-0006` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-75918-0007` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-75918-0008` | librispeech | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-75918-0009` | librispeech | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-75918-0010` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-75918-0011` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-75918-0012` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-75918-0013` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-75918-0014` | librispeech | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-75918-0015` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-75918-0016` | librispeech | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-75918-0017` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-75918-0018` | librispeech | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-75918-0019` | librispeech | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-75918-0020` | librispeech | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0000` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0001` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0002` | librispeech | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0003` | librispeech | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0004` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0005` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0006` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0007` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0008` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0009` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0010` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0011` | librispeech | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0012` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0013` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0014` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0015` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0016` | librispeech | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0017` | librispeech | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0018` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0019` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0020` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0021` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0022` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0023` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0024` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0025` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0026` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0027` | librispeech | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-76324-0028` | librispeech | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0000` | librispeech | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0001` | librispeech | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0002` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0003` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0004` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0005` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0006` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0007` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0008` | librispeech | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0009` | librispeech | 4 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0010` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0011` | librispeech | 2 | 2 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0012` | librispeech | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0013` | librispeech | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0014` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0015` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0016` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0017` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0018` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0019` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0020` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0021` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0022` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0023` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0024` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0025` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0026` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `6930-81414-0027` | librispeech | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
