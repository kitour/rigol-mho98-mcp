# MHO98 Bode-plot tools

`bode.py` exports `get_bode`, `set_bode`, and `bode_action` through its
`TOOLS` list. The root server owns registration of that list.

The tools cover the 11 documented Bode settings: Bode enable, run/stop state,
LOG/LINE sweep type, input and output reference channels, start and stop
frequency, points per decade, voltage amplitude, and gain/phase curve display.
Channels are `CHAN1` through `CHAN4`; the guide documents no channel-enable
operation, so the tools never enable source or oscilloscope channels.

`get_bode` reads configuration and one documented voltage range. Use
`amplitude_range` (`ALL`, `10`, `100`, `1K`, `10K`, `100K`, `1M`, `10M`, or
`25M`) to select the `:BODeplot:VOLTage? <range>` readback. Amplitudes are
validated to 20 mV–10 V. Start/stop are validated to 10 Hz–3 MHz and
100 Hz–30 MHz, respectively, with the documented `start <= stop / 10`
relationship. Points per decade are validated to 10–100.

`set_bode` preserves omitted fields, validates the complete final frequency
pair before its first write, orders endpoint writes so intermediate values
remain legal, and returns readback. Gain or phase display changes require the
current Bode status to be STOP; the setter does not stop it implicitly. It
also never writes `RUNStop`, so it cannot start or stop a sweep implicitly.

Use `bode_action` with `START` or `STOP` for explicit run control. `START` may
drive the built-in generator output into the circuit under test. No generator
output channel is enabled by these tools.

Access checks the documented `:SYSTem:DGSTatus?` and AFG100/AFG50 (or
documented BND bundle) option-status queries. A DG-zero result is retained as
`dg_available: false`; when a documented option is positive, the existing Bode
configuration readback is still required and the result reports the raw DG
status, option evidence, and a discrepancy warning. DG zero with all-negative
option status remains an explicit error. Command syntax is never treated as
proof of a license.

The supplied Bode guide documents no numeric trace/result query and no
instrument-side CSV/export facility. There is therefore no `read_bode` tool,
no invented trace-download command, and no numeric response claim beyond the
documented configuration/amplitude readbacks.
