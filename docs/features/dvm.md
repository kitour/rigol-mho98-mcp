# MHO98 DVM

`get_dvm` and `set_dvm` cover the DVM enable state, analog source, and mode.
Sources are `CHAN1` through `CHAN4`; modes are exactly `ACRMs`, `DC`, and
`DCRMs`.

```python
from rigol_mcp.mho98.dvm import get_dvm, read_dvm, set_dvm

set_dvm(session, enabled=True, source="CHAN2", mode="DC")
settings = get_dvm(session)
reading = read_dvm(session)
```

`read_dvm` queries `:DVM:CURRent?` only when `:DVM:ENABle?` reports enabled.
It never enables a channel or changes timebase/acquisition. The result keeps
the instrument's raw reply and unit; invalid or overflow replies are returned
as `valid: false` rather than presented as a measurement.
