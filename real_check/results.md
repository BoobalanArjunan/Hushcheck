# hushcheck real-data check

17 files, 140 transcript lines, 10 labelled invented, 130 real.

| method | invented caught | invented missed | false alarms | precision | recall | false-alarm rate on real lines |
|---|---|---|---|---|---|---|
| hushcheck LIKELY | 8 | 2 | 0 | 100% | 80% | 0.0% |
| hushcheck LIKELY+SUSPECT | 8 | 2 | 4 | 67% | 80% | 3.1% |
| text checks only | 3 | 7 | 0 | 100% | 30% | 0.0% |
| whisper-guard | 0 | 10 | 1 | 0% | 0% | 0.8% |

Decision rule (set before looking): hushcheck LIKELY must catch clearly more invented lines than whisper-guard with the same or fewer false alarms,
and must beat 'text checks only' (otherwise the audio part adds nothing). With fewer than about 30 invented lines the table is too small to trust.
