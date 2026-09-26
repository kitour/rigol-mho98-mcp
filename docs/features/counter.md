# MHO98 dedicated counter

`get_counter`, `set_counter`, `read_counter`, and `counter_action` expose the
dedicated `:COUNter` commands. This is separate from the legacy
`:MEASure:COUNter` settings.

```python
from rigol_mcp.mho98.counter import get_counter, read_counter, set_counter

set_counter(session, enabled=True, source="CHAN1", mode="FREQ", digits=5)
settings = get_counter(session)
reading = read_counter(session)  # e.g. {"value": 1000.0, "unit": "Hz"}
```

Sources are `CHAN1`–`CHAN4` and `D0`–`D15`; modes are `FREQ`, `PER`, and
`TOT`. `digits` (3–6) and `statistics` are queried and accepted only outside
`TOT`. Omitted settings are preserved and setters return instrument readback.
`read_counter` never enables the counter or starts acquisition; frequency,
period, and totalize readings use `Hz`, `s`, and `count`, respectively, while
retaining the raw reply and reporting invalid sentinel/non-numeric replies as
`valid: false`.

Clear explicitly with `counter_action(session, action="clear")`; it is allowed
only in `TOT` mode and sends only `:COUNter:TOTalize:CLEar`.
