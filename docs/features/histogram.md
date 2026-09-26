# MHO98 histogram

`get_histogram`, `set_histogram`, `read_histogram`, and `histogram_action` expose
the 11 documented `:HISTogram` entries.

```python
from rigol_mcp.mho98.histogram import get_histogram, histogram_action, read_histogram, set_histogram

set_histogram(session, enabled=True, type="HOR", source="CHAN1", left=-0.004, right=0.004)
settings = get_histogram(session)
statistics = read_histogram(session)
histogram_action(session, action="save_csv", path="C:/histogram.csv")
```

`set_histogram` preserves omitted settings, requires a complete ordered
`left`/`right` or `bottom`/`top` pair, validates the active pair against the
current timebase or selected channel scale/offset, applies type/source
dependencies in order, and returns instrument readback. Only the range pair
for the active `HOR` or `VERT` type is queried. Histogram enablement is the
documented display control; no separate display command is invented.

`read_histogram` parses the actual `:HISTogram:STATistics:RESult?` text into
named values with normalized SI units and retained raw fields. The guide does
not document a histogram-bin query, so no bins are fabricated from the range.

CSV save paths are instrument paths under `C:/` or `D:/`, not local export
paths; the filename must end in `.csv` and be at most 26 characters.

Reset is intentionally unsupported. The guide spells it `:HISTogram:RESet?`,
but does not establish whether that spelling is an action or a query. Until
authoritative syntax is available, `histogram_action(action="reset")` fails
with this documented limitation and sends no speculative command.
