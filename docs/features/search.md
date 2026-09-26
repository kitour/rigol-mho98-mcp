# Search and navigation

The MHO98 search/navigation workflow is exposed by `search.py`:

```text
set_search(mode="EDGE", source="CHAN1", slope="POSITIVE", threshold_v=0.2,
           enabled=True)
read_search_events(start=1, limit=25)
set_navigation(mode="SEARCH", enabled=True)
navigate(mode="SEARCH", action="next")
```

`get_search` returns the enabled state, mode, selected event, and event count.
EDGE returns slope/source/threshold; PULSE returns polarity/qualifier/source,
lower and upper widths, and threshold. The single `source` field follows the
selected mode. `read_search_events` uses the documented 1-based
`:SEARch:VALue? <index>` table and returns only actual event values, including
their raw response and unit; it does not invent voltage, width, or other
columns. `limit` is bounded to 1 through 1000.

Pulse widths are seconds and must be 800 ps through 10 s. `BETWEEN` requires
`lower_width_s < upper_width_s`. Thresholds are checked against the selected
channel's documented `-4.5*scale-offset` through `4.5*scale-offset` range.
Omitted fields remain instrument-owned and mode-inapplicable fields are not
queried.

Navigation supports `TIME` and `SEARCH`, with TIME-only `speed` and `play`
settings. `navigate` accepts `FIRST`, `LAST`, `NEXT`, or `BACK` and sends only
the corresponding documented action. SEARCH configuration/actions require the
instrument already to report `STOP`; no implicit `:STOP` is sent. Reads never
enable search or playback.
