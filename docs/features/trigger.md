# MHO98 trigger tools

`get_trigger` and `set_trigger` cover common controls and named detail fields
for all 20 documented MHO98 trigger modes. `EDGE` keeps its existing
top-level `source`, `slope`, and `level` contract. Other mode-specific fields
are passed in structured `details`; no raw SCPI escape is exposed.

The non-serial families provide their documented source, polarity/slope,
condition, timing, and threshold fields. `VIDEO` adds standard/sync/line;
`PATTERN` and `DURATION` use named channel maps such as
`{"CHAN1": "H", "CHAN2": "X"}`; `DELAY` uses named A/B fields; `SETUP`
uses named data/clock fields; and `NEDGE` exposes idle time and edge count.
The existing named schemas remain available for RS232/UART, I2C/IIC, SPI,
CAN, LIN, I2S/IIS, FlexRay, and M1553.

Sources are restricted per reference family: analog-only families reject
digital sources, while families documenting digital inputs accept `D0`–`D15`.
Analog levels use the selected channel’s `-4.5 * scale - offset` to
`4.5 * scale - offset` bounds; digital levels use `-15..15 V`. Dependent
getters query only fields valid for the active condition. Lower/upper timing
and threshold bounds, enum values, source restrictions, and dependent data
limits are validated before the first write. Writes follow prerequisite order
(source and condition before dependent values).

Example:

```python
set_trigger(scope, mode="PULSE", details={
    "condition": "IN_RANGE", "lower_width_s": 1e-6,
    "upper_width_s": 3e-6, "level": 0.2,
})
set_trigger(scope, mode="PATTERN", details={
    "pattern": {"CHAN1": "R", "CHAN2": "L", "CHAN3": "X", "CHAN4": "H"},
    "levels": {"CHAN1": 0.2, "CHAN2": -0.1},
})
```

The cited trigger chapters do not document additional non-serial parameters,
channel-enable actions, or automatic RUN/STOP behavior. Those are deliberately
not synthesized. Optional instrument licenses remain the instrument’s normal
SCPI response; this layer adds no recovery or availability logic.

`tests/test_mho98_trigger.py` retains the existing EDGE and serial coverage
and adds representative pulse/video/pattern/window/delay/setup round trips
plus a combined-bound rejection without hardware access.
