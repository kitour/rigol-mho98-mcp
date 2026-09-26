# MHO98 waveform tools

`get_waveform` reads `CHAN1`-`CHAN4` or `MATH1`-`MATH4` in `NORM`, `MAX`, or
`RAW` mode and in `ASC`, `BYTE`, or `WORD` format. Existing calls such as
`get_waveform(session, source="CH1", start=1, points=1000)` remain NORM/ASC
reads.

```python
screen = get_waveform(session, source="CH1", mode="NORM", format="ASC", points=1000)
raw = get_waveform(session, source="CH1", mode="RAW", format="BYTE", start=1, points=100_000)
word = get_waveform(
    session, source="CH1", mode="RAW", format="WORD", points=1000,
    encoding={"byte_order": "little", "signed": False},
)
large = get_waveform(
    session, source="CH1", mode="RAW", format="BYTE", points=500_000_000,
    filename="capture.bin",
)
csv_result = export_waveform_csv(
    session, source="CH1", mode="MAX", start=1, points=100_000, filename="capture.csv"
)
```

The waveform implementation uses these state rules:

- NORM is screen data and is limited to positions 1 through 1,000.
- RAW is internal memory and requires the current trigger status to be STOP.
  The tool never sends STOP or RUN.
- MAX reads screen data in RUN and internal memory in STOP. Other trigger
  statuses are rejected rather than treated as either state.
- MATH sources accept NORM only. Channel display state is checked but never
  enabled implicitly.
- RAW/MAX STOP ranges are checked once against `:ACQuire:MDEPth?` when that
  query reports a numeric current depth. The documented depth reaches 500M
  points in single-channel mode; `AUTO` is left to the instrument's current
  range rather than guessed.

Transfers are chunked (10,000 points by default), and CSV/raw-file exports do
not buffer a complete capture. Inline results are limited to 100,000 points;
larger reads require `filename`. Binary files contain the exact concatenated
BYTE/WORD payload bytes and return encoding metadata. `Session.binary_query`
validates each definite-length block, and the tool checks each chunk's exact
byte count.

BYTE interpretation follows the guide's documented formula:
`(sample - yorigin - yreference) * yincrement`. The guide specifies WORD as
two bytes but does not specify byte order or signedness. Interpreted WORD
reads therefore require caller-declared `encoding`/`word_encoding`; their
metadata says `caller_declared`, not hardware-verified. A raw WORD file needs
no interpretation and reports the preamble format separately. The equivalent
explicit arguments `word_byte_order` and `word_signed` are also accepted.

The reference has two relevant limits that should not be conflated: waveform
preamble text says its point field ranges to 50,000,000, while the acquisition
guide documents current memory depth up to 500,000,000 (subject to enabled
channel count). This implementation uses the current `:ACQuire:MDEPth?` value
for RAW/MAX validation and preserves the preamble as returned.
