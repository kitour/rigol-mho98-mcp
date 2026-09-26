# MHO98 logic-analyzer tools

`logic_analyzer.py` provides `get_logic_analyzer` and `set_logic_analyzer` for
the documented `:LA` display/configuration commands. The tools cover LA enable,
D0-D15 enable and labels, POD1/POD2 display and thresholds, active channel,
auto-sort, and waveform display size.

Example:

```python
from rigol_mcp.mho98.logic_analyzer import get_logic_analyzer, set_logic_analyzer

state = get_logic_analyzer(session, channels=["D0", "D3"])
state = set_logic_analyzer(
    session,
    enabled=True,
    channels={"D3": {"enabled": True, "label": "CLK"}},
    pod1_display=True,
    pod1_threshold_v=1.8,
    active_channel="D3",
    size="LARGE",
)
```

`get_logic_analyzer` always reads top-level LA state and both POD states; its
optional `channels` list limits the per-channel enable/label queries. Setter
validation is completed before the first write. It does not implicitly enable a
digital channel or POD to satisfy an active-channel request, and `LARGE` is
accepted only with at most eight enabled channels. Labels are printable ASCII
without SCPI delimiters, and thresholds are limited to -15 V through +15 V.

The programming guide documents these commands for use with the logic-analyzer
probe, but module support does not prove that an external probe is connected.
The tools therefore report instrument query/write failures as received and do
not invent hardware-presence status. They configure state only; no digital
waveform extraction is promised by this feature.
