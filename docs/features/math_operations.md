# MHO98 non-FFT MATH tools

`math_operations.py` exports `get_math`, `set_math`, and `math_action` through
its `TOOLS` list. The root server registers that list separately from
the existing FFT tools.

The API covers the documented MATH display controls (`display`, `grid`,
`expand`, `waveform_type`, `label_visible`, `display_mode`), arithmetic and
function operators, logic operators and sources, filter type/cutoffs,
operator scale/offset/invert, differential distance, logic sensitivity and
thresholds, and the explicit `RESET` action. For example:

```python
from rigol_mcp.mho98.math_operations import get_math, set_math, math_action

set_math(session, math=1, operator="SUBT", source1="CHAN1", source2="CHAN2", scale=1.0)
state = get_math(session, math=1)
set_math(session, math=2, operator="BPAS", source1="CHAN1", cutoff1_hz=1_000, cutoff2_hz=10_000)
math_action(session, math=1, action="RESET")
```

Omitted fields are preserved. Readback includes only operator-specific fields
that apply to the effective operator: arithmetic has two `source` fields,
functions and filters have `source1`, logic has `logic_source1/2`, and FFT
returns a handoff note instead of duplicating FFT configuration. MATH source
graphs follow the manual: MATH1 cannot use a MATH output, MATH2 can use MATH1,
MATH3 can use MATH1-2, and MATH4 can use MATH1-3. Logic sources are limited to
CHAN1-CHAN4 and D0-D15. Analog channels are never enabled and the timebase is
never changed.

Band-pass and band-stop settings validate the complete `cutoff1_hz <
cutoff2_hz` pair before writing and order endpoint writes safely. `ZOOM`
requires the existing timebase zoom enable; the tool does not enable it. Logic
thresholds use the documented `(-4 * channel_scale - channel_offset)` through
`(4 * channel_scale - channel_offset)` range.

The source command is taken from the explicit `:MATH<n>:SOURce1` documentation,
which states that it applies to arithmetic, function, and filter operations.
The later filter note refers to `:MATH<n>:FFT:SOURce`; that is inconsistent
with the source1 entry and is not used here so FFT-specific ownership remains
with `fft.py`.

The manual’s waveform-type heading contains a duplicated `:MATH<n>:` segment,
but its explicit query line is `:MATH<n>:WAVetype?`; the implementation uses
the corresponding `:MATH<n>:WAVetype` set/query path. AX+B is exposed as the
documented `AXB` operator only: the supplied manual documents no coefficient
command, so no AX+B syntax is fabricated. FFT-specific settings remain in
`get_fft`/`set_fft`.
