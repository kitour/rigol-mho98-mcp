# MHO98 system, capabilities, and instrument errors

The native system feature is intentionally limited to practical documented
controls. Its tools are registered in the MHO98 server.

## Tools

`get_system` reads the ordinary system settings: AUX output mode, language,
beeper, calendar date, clock time, clock visibility, power-on configuration,
power behavior, front-panel/touch lock, low-power mode, and the system AUTO
gate. It performs only the documented setting queries; it does not read the
error queue, reset, reboot, or change acquisition state.

`set_system` accepts only explicitly supplied fields. Supported fields are
`aux_output`, `language`, `beeper`, `date`, `time`, `show_time`, `power_on`,
`power_status`, `locked`, `low_power`, and `autoscale`. Descriptive aliases
`clock_visibility`, `front_panel_lock`, and `auto_gate` are accepted for the
corresponding canonical fields. All supplied values are validated before the
first instrument interaction. Dates use `{"year", "month", "day"}` and are
checked with real calendar rules, including leap years; times use
`{"hours", "minutes", "seconds"}`. `TIME?` readback accepts both the
comma-delimited guide form and the colon-delimited form returned by some
instruments; DATE/TIME writes remain comma-delimited. Omitted fields are not written, and the
complete result is read back from the instrument after writes.

If `:SYSTem:LOWPower?` returns an unrecognized value, `get_system` keeps the
trimmed reply in `low_power_raw`, reports `low_power: null`, lists
`low_power` in `unavailable`, and adds a warning. It does not assign meaning
to the value. An unrelated `set_system` change remains usable and preserves
that unknown readback; an explicit `low_power` request is rejected before any
write while the current low-power state is unknown.

Low-power mode may change instrument power behavior and responsiveness. The
front-panel lock disables front-panel keys and touch operation. These settings
are opt-in fields: the utility never implicitly enables them, disables them, or
restores an earlier value.

`get_capabilities` reports the exact `*IDN?` identity, the raw module flag
string and parsed flags, raw DG status, analog-channel and grid counts, SCPI
version, and both documented option status and validity results. By default it
queries the useful generator subset `BND`, `AFG100`, and `AFG50`. Pass an option
list for a selected set or `"all"` for all eleven documented option types.
DG status and option results remain independent; for example, `dg_status: "0"`
and `option_status.AFG50: "1"` are both preserved. Option evidence is not a
claim that the physical feature is present or working.

`read_instrument_error` performs exactly one `:SYSTem:ERRor?` query. That
documented query consumes one queue entry. The result contains the parsed
integer `code`, message text, and original `raw` response. There are no loops,
automatic drains, or clears, and the tool is marked non-read-only because the
instrument queue is consumed.

The feature deliberately excludes system reset/reboot, option installation or
uninstallation, passwords/network settings, keyboard self-test, screenshots,
setup binary transfer, and transport changes. Less common documented commands
remain available through the existing catalog.
