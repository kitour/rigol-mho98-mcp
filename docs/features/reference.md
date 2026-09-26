# MHO98 reference waveform tools

`reference.py` provides `get_reference`, `set_reference`, and
`reference_action` for the ten documented reference slots, Ref1 through
Ref10. The root MHO98 server registers the module's `TOOLS` list separately.

```python
from rigol_mcp.mho98.reference import get_reference, reference_action, set_reference

set_reference(
    session,
    reference=1,
    source="CHAN1",
    scale_v_div=2.0,
    offset_v=0.5,
    color="GREEN",
    label_visible=True,
    label="golden capture",
)
state = get_reference(session, reference=1)
reference_action(session, reference=1, action="SAVE")
reference_action(session, reference=1, action="CURRENT")
reference_action(session, reference=1, action="RESET")
```

Configuration preserves omitted fields and returns actual instrument readback.
`SAVE` is an explicit, slot-specific waveform capture; configuration never
silently saves or overwrites another slot. `RESET` sends only
`:REFerence:RESet <ref>`, resetting that reference display's scale and offset;
it never sends `*RST`. `CURRENT`, `SAVE`, and `RESET` have no documented query
forms, so the action handler does not invent `?` commands and instead returns
the selected slot's queryable state after the action.

Sources are `CHAN1`-`CHAN4`, `MATH1`-`MATH4`, and `D0`-`D15`. A source must be
currently enabled before selection. Digital sources additionally require the
documented digital-channel enable status; the tool does not enable channels or
the logic probe implicitly. Reference slots are strictly 1 through 10.

Reference scale is positive and is checked against the guide's probe-ratio and
input-impedance range when the source is an analog channel. The guide gives no
fixed scale range for MATH or digital reference sources, so those finite,
positive values remain subject to instrument enforcement. Offset is checked
against `-10 * scale` through `+10 * scale`, using the effective scale before
any write. Labels are ASCII-safe SCPI quoted strings with control characters
and command delimiters rejected before the first write.

The standard waveform tool intentionally remains unchanged: the documented
waveform transfer API accepts only `CHAN1`-`CHAN4` and `MATH1`-`MATH4`, not `REF`
sources. This feature therefore exposes no undocumented reference-trace
download API.
