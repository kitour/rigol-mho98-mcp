# MHO98 cursors

`rigol_mcp.mho98.cursor` exports `get_cursor`, `set_cursor`, and
`read_cursor`. The root MHO98 server registers this module's `TOOLS` list.
These tools cover all 41 documented cursor entries: global mode and indicator,
manual, track, and XY configuration, placement, and result queries.

```python
from rigol_mcp.mho98.cursor import get_cursor, read_cursor, set_cursor

set_cursor(
    session,
    mode="MANUAL",
    indicator=True,
    manual_type="TIME",
    manual_source="CHAN1",
    manual_tunit="SECOND",
    manual_vunit="SOURCE",
    manual_cax=-1.0e-3,
    manual_cbx=2.0e-3,
)
settings = get_cursor(session)
results = read_cursor(session)
```

`set_cursor` takes named fields only. Omitted fields are preserved from the
instrument and the return value is an effective readback. Manual fields are
valid only in manual mode; track fields are valid only in track mode; and
`xy_ax`, `xy_bx`, `xy_ay`, and `xy_by` are valid only in XY mode. Track has
independent source and position fields for Cursor A and B, plus the documented
X/Y tracking-axis setting. There is no cursor-link setting in the documented
`:CURSor` subtree; the separate measurement-region `cursor_linked` setting is
not invented or changed here.

XY mode is available only when `:TIMebase:MODE?` already returns `XY`.
`set_cursor` and `read_cursor` fail closed otherwise; they never enable XY,
change the timebase, or enable a channel or MATH output. Selecting a disabled
`CHAN1`-`CHAN4` or `MATH1`-`MATH4` source is rejected and must be preceded by an
explicit channel/MATH configuration call.

The returned mode uses the instrument abbreviations `OFF`, `MAN`, `TRAC`, or
`XY`. `get_cursor` reports placement separately under the active mode's
`screen_positions` object. For manual and track modes, X placement is in
seconds (`x_s`) and Y placement is source-amplitude coordinates (`y_v`); XY
placement is voltage (`x_v`/`y_v`). These are not waveform samples.

`read_cursor` queries only the active mode's physical `AXValue`, `AYValue`,
`BXValue`, `BYValue`, delta, and documented reciprocal-delta results. Each
reading retains `value`, `raw`, `valid`, and the documented unit: seconds and
Hz for manual/track time results, `source` for source-dependent amplitudes,
and V for XY results. The instrument does not return a concrete channel unit
with cursor values, so `source` is preserved rather than guessed as volts.

The programming guide is ambiguous about the exact screen-coordinate/range
semantics of manual `CAX`, `CAY`, `CBX`, and `CBY`: it only ties their ranges to
the current horizontal/vertical scale and position. The implementation sends
and reports the documented numeric positions, performs finite-number checks,
and leaves range enforcement to the scope; it does not invent pixel geometry,
linking behavior, or conversions.
