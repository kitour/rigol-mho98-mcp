# MHO98 pass/fail mask

`mask.py` exposes `get_mask`, `set_mask`, `read_mask`, and `mask_action` using
the documented `:MASK` subtree. The feature covers all 13 documented commands:

- settings/status: `ENABle`, `SOURce`, `OPERate`, `X`, `Y`,
  `OUTPut:ENABle`, `OUTPut:EVENt`, and `OUTPut:TIME`;
- counters: `FAILed?`, `PASSed?`, and `TOTal?`;
- actions: `CREate` and `RESet`.

```python
from rigol_mcp.mho98.mask import get_mask, mask_action, read_mask, set_mask

set_mask(
    session,
    enabled=True,
    source="CHAN1",
    x_div=0.24,
    y_div=0.48,
    aux_enabled=False,
)
mask_action(session, action="create")
mask_action(session, action="start")
result = read_mask(session)
mask_action(session, action="stop")
```

`set_mask(enabled=True)` only enables the test. It never sends
`:MASK:OPERate RUN`; use `mask_action(action="start")` explicitly. `create`
requires an enabled, stopped test. `stop` sends only `OPERate STOP`, and
`reset` sends only `:MASK:RESet`, which clears pass/fail/total counters rather
than resetting the instrument.

The setter validates every submitted field before the first write. `x_div` is
`0.01..2 div`, `y_div` is `0.04..2 div`, and `aux_time_s` is `100 ns..10 ms`.
Sources are `CHAN1` through `CHAN4`; events are `FAIL` or `PASS`. AUX output
is not enabled or configured unless requested explicitly. Assigning a source
is also explicit because the instrument automatically enables a disabled
analog channel when selected; the returned `effects` field reports this
documented side effect.

Enable, create, and start are refused before any mask write when the existing
state is horizontal `ROLL`, delayed sweep (Zoom), waveform recording, or
waveform playback. The tools do not change those conflicting states.

`get_mask` returns the eight setting/status readbacks. `read_mask` queries
counters only when the mask is enabled and returns `failed`, `passed`, and
`total`. `pass_ratio` is `passed / total`; it is `None` when `total == 0`, so
zero counts remain distinguishable from a measured 0% pass result. Action
results contain complete post-action `settings` and `results` readback.
