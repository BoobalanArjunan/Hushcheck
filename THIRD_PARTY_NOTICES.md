# Third-Party Notices & Acknowledgements

This project incorporates algorithmic concepts, published threshold values, and design principles adapted from:

### whisper-guard (v0.3.3)
- **Author**: Hevin Yeh
- **Repository**: [https://github.com/hevin-yeh/whisper-guard](https://github.com/hevin-yeh/whisper-guard)
- **License**: MIT License

```text
MIT License

Copyright (c) 2026 Hevin Yeh

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

Specifically, the following ideas are reimplemented in `src/hushcheck/guardlogic.py`:
1. Consecutive decoding window grouping by `(no_speech_prob, avg_logprob)`.
2. Sparse decoding window detection (`SPARSE_WINDOW`: duration $\ge 10\,\text{s}$ with $< 1.0\,\text{chars/s}$).
3. Dense confident window rescue rule (`_dense_confident`: duration $\ge 5\,\text{s}$, density $\ge 2.0\,\text{chars/s}$, $\text{avg\_logprob} > -0.5$).
4. Windowed word-uniqueness ratio check for long text repetitions (`LONG_REPEAT`: 100-word window uniqueness ratio $< 0.35$).
5. Repetitive character loop pattern matching with numeric data exceptions (`LOOP`).
6. Segment parameter filters (`no_speech_prob > 0.8`, `avg_logprob < -1.5`, short segment logprob $< -1.7$, `compression_ratio > 3.0`).

