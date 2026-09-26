# MHO98 measurement settings

`rigol_mcp.mho98.measurement_settings` controls the MHO98 measurement setup;
the existing `measure`, `measure_between`, and `measure_statistics` handlers
remain read-only value queries. Registering an item is therefore an explicit
action and is never implied by fetching its value.

```python
from rigol_mcp.mho98.measurement_settings import (
    get_measurement_settings,
    measurement_action,
    set_measurement_settings,
)

measurement_action(
    session,
    action="register_item",
    item="VPP",
    source="CH1",
)
set_measurement_settings(
    session,
    area="CURSOR",
    cursor_a_s=-2.0e-3,
    cursor_b_s=2.0e-3,
    threshold_type="PERCENT",
    threshold_min=10,
    threshold_mid=50,
    threshold_max=90,
    statistics_count=100,
    statistics_display=True,
)
settings = get_measurement_settings(session)
```

`set_measurement_settings` accepts named fields only. Omitted fields are not
written. Threshold updates validate the complete final `MIN < MID < MAX`
relationship before the first write, and percentage thresholds additionally
stay in 0–100% with the documented one-percentage-point separation around
`MID`. The writes are ordered so the instrument's intermediate bound checks do
not reject a valid combined update.

Other supported settings include measurement/all-measure source, phase and
delay source pairs, measurement area/type, cursor linking, auto-cursor
indicator, statistics count/display, amplitude auto/manual and manual
top/base method, histogram enable/result, category, and the built-in counter.
The counter value and histogram result are queried only when their respective
features are enabled. Cursor positions are queried only for cursor-region
readback, and manual top/base only for manual amplitude readback.

Actions are `register_item`, `register_statistic_item`, `delete_items`,
`reset_statistics`, and `reset_threshold_defaults`. The reset action is only
`:MEASure:STATistic:RESet`; it is not an instrument reset. Threshold defaults
uses the documented `:MEASure:THReshold:DEFault` action.

The reference documents `PSB` and `DSB` as equivalent Source B commands and
explicitly documents `PSB?`. Both `phase_source_b` and `delay_source_b` use the
canonical `PSB` setter/query; when both are requested, matching values produce
one write and one query, while conflicting values are rejected before any
write. The documented `PSA?`, `PSB?`, and `DSA?` queries remain in use for the
existing A/source fields. The reference also describes threshold absolute
ranges as dependent on probe ratio/vertical scale, so the client validates
finite values and ordering but leaves instrument-specific absolute range
enforcement to the scope.
