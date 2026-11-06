# Real-data check for hushcheck

Goal: find out if hushcheck catches invented lines on REAL Whisper output, and if it is better than whisper-guard and better than text-only checks.

1. **Audio.** Collect 10 to 20 files where Whisper tends to invent text: meetings or interviews with long silences, podcasts with intro/outro music, call recordings with hold music, videos with background music. Put them in `audio/`. Include some clean talking files too, so false alarms show up.
2. **Whisper output.** For each file make JSON with the same base name in `json/`:

       whisper audio/meeting1.wav --model small --output_format json --output_dir json/

   (openai-whisper's JSON has `no_speech_prob`, `avg_logprob`, `compression_ratio` per segment, which whisper-guard needs. If you use faster-whisper, save `{"segments":[{"start","end","text","no_speech_prob","avg_logprob","compression_ratio"}]}`.)
3. **Label by listening.** Make `labels.csv` with one row per stretch where the transcript text is invented (nobody said it):

       file,start_s,end_s
       meeting1.wav,62.0,70.5

   Do this BEFORE running the tool. You need at least about 30 invented lines in total for the table to mean anything.
4. **Run:**

       pip install -e .[dev] whisper-guard
       python scripts/real_data_check.py --audio-dir audio/ --transcripts-dir json/ --labels labels.csv --out real_check

5. **Read `real_check/results.md`.** It shows, per method: invented lines caught, missed, false alarms, precision, recall.
6. **Decide (rule fixed in advance).**
   - hushcheck LIKELY catches clearly more than whisper-guard with the same or fewer false alarms, and beats "text checks only": good, send me the table.
   - About equal or worse: send the table; I make one fix round (two at most).
   - Still not clearly better after round two: stop. Do not publish.

Do not change thresholds and re-test on the same files without telling me. Keep a few files unseen for the final check.
