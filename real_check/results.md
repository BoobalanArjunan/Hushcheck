# hushcheck real-data check

43 files, 257 transcript lines, 39 labelled invented, 218 real.

| method | invented caught | invented missed | false alarms | precision | recall | false-alarm rate on real lines |
|---|---|---|---|---|---|---|
| hushcheck LIKELY | 10 | 29 | 1 | 91% | 26% | 0.5% |
| hushcheck LIKELY+SUSPECT | 31 | 8 | 13 | 70% | 79% | 6.0% |
| text checks only | 20 | 19 | 0 | 100% | 51% | 0.0% |
| whisper-guard | 20 | 19 | 22 | 48% | 51% | 10.1% |

Decision rule (set before looking): hushcheck LIKELY must catch clearly more invented lines than whisper-guard with the same or fewer false alarms,
and must beat 'text checks only' (otherwise the audio part adds nothing). With fewer than about 30 invented lines the table is too small to trust.
