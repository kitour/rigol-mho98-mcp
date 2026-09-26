# MHO98 FFT tools

`fft.py` exports `get_fft`, `set_fft`, and `read_fft` through its `TOOLS`
list. The root server registers that list explicitly.

```python
from rigol_mcp.mho98.fft import get_fft, read_fft, set_fft

state = get_fft(session, math=1)
set_fft(
    session,
    math=1,
    source="CHAN1",
    window="HANN",
    unit="DB",
    mode="AVER",
    averages=16,
    scale=2.0,
    offset=0.0,
    start_hz=10.0,
    end_hz=10_000_000.0,
    search_enabled=True,
    peak_count=5,
    order="AMP",
)
peaks = read_fft(session, math=1)
full = read_fft(session, math=1, full_spectrum=True, points=1000)
```

`math` selects MATH1 through MATH4. `set_fft` writes only requested settings and
returns actual instrument readback. The instrument can change omitted values
itself: on this MHO98 firmware, enabling MATH FFT display automatically adjusted
scale, offset, center/range, start/end, and peak threshold. A caller that needs
full restoration must retain these values and restore them with display OFF,
then restore the original operator/display. The representative hardware trial
verified this restoration and a 16-point native sample read; see
[hardware trial](../FEATURE_TRIAL.md).

It validates the complete submitted state
before its first write. Frequency settings use exactly one complete form:
`center_hz` plus `range_hz`, or `start_hz` plus `end_hz`; the two forms cannot
be mixed. `operator="FFT"` (or `select_fft=True`) is required when changing a
non-FFT math operator. `display=True` can be requested explicitly. The tool
never enables an analog channel, and a source must be one of the documented
`CHAN1`-`CHAN4` or `MATH1`-`MATH3` FFT sources; a math channel cannot source
itself.

`get_fft` reports `fft_configured: false` and no FFT fields when the selected
MATH operator is not FFT. It does not mistake another math operator's saved
settings for active FFT configuration. FFT vertical settings are returned as
`scale` and `offset`; frequency settings are returned in Hz as
`center_hz`, `range_hz`, `start_hz`, and `end_hz` (also grouped under
`frequency`). The effective FFT unit and mode are returned as `unit` (`VRMS`
or `DB`) and `mode` (`NORM`, `AVER`, or `MAXH`).

`read_fft` defaults to the documented peak table and requires the selected
MATH operator/display and enabled FFT peak search. It reads
`:MATHn:FFT:SEARch:RES?`; each `peaks` row retains `raw`,
`frequency_raw`, `amplitude_raw`, and the instrument-reported
`amplitude_unit`, while providing parsed `frequency_hz` and numeric
`amplitude`. Units such as `dBV`, `dBm`, and `DB` remain distinct. An empty
table is a valid result (`count` 0). The returned frequency axis is Hz and
the amplitude axis remains per-row instrument units; this feature does not
fabricate full spectral bins or infer a frequency axis from a waveform
preamble. `scope` is explicitly `peak_table_only`.

With `full_spectrum=True`, the tool reads the actual `MATHn` waveform through
the documented NORM/ASC waveform path. The result includes `spectrum.samples`
and `spectrum.amplitude`, the raw waveform preamble (`preamble_raw`), native
time-like x coordinates (`native_axis`), and the instrument-reported FFT unit
with its query provenance. The guide documents FFT display frequency settings
and peak results, but does not establish that the MATH waveform preamble x
coordinate is Hz or define a full-bin transfer. Therefore the result marks
the axis `unresolved` and does not provide `frequency_hz` by default.

Callers with an independently established calibration may provide
`axis_encoding={"unit": "Hz", "scale": ..., "offset": ...}`. The tool then
reports `encoded_axis` using `offset + native * scale` and only labels it
`frequency_hz` when the caller declared `unit: "Hz"`. This is caller-declared
metadata, not a format verification by the instrument.
