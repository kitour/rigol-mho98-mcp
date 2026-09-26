# MHO98 display and quick-key configuration

`rigol_mcp.mho98.display` exports `get_display`, `set_display`,
`display_action`, `get_quick_action`, and `set_quick_action`, together with the
module `TOOLS` list. The display tools cover the documented non-image
`:DISPlay` settings only; screenshot transfer is deliberately outside this
feature.

```python
from rigol_mcp.mho98.display import set_display, set_quick_action

display = set_display(
    session,
    display_type="VECTors",
    persistence_time="0.5",
    grid="HALF",
    waveform_brightness=70,
)
quick = set_quick_action(session, operation="SRESet")
```

`get_display` and every display setter read the instrument's actual values.
Omitted display fields are preserved. Display type accepts `VECTors`/`VECT`,
grid accepts `FULL`, `HALF`, or `NONE`, and the boolean fields are `rulers`,
`ruler_tracking`, `color`, and `wavehold`. Waveform brightness is 1–100;
grid and cursor brightness are 0–100. Persistence uses the documented tokens
`MIN`, `0.1`, `0.2`, `0.5`, `1`, `2`, `5`, `10`, and `INFinite`/`INF`; numeric
tokens remain strings in readbacks.

`display_action(session, action="clear")` sends only `:DISPlay:CLEar` and
returns display readback. It does not send `:RUN` or `:STOP`; waveform hold may
change what is displayed but is not an acquisition control.

Quick-key configuration accepts both the documented long spellings and the
instrument's returned short spellings: `SIMage`/`SIM`, `SWAVe`/`SWAV`,
`SSETup`/`SSET`, `AMEasure`/`AME`, `SRESet`/`SRES`, `RECord`/`REC`, and
`SSAVe`/`SSAV`. `set_quick_action` changes only `:QUICk:OPERation`; it never
performs the selected quick operation.
