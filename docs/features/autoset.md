# MHO98 AUTO settings and action

`autoset.py` exposes `get_autoset`, `set_autoset`, and `run_autoset` for the
documented `:AUToset` commands and the `:SYSTem:AUToscale` gate.

The readback fields are `autoscale`, `peak`, `open_channels`, `overlap`,
`keep_coupling`, `lock`, and `enabled`. `set_autoset` preserves omitted fields
and returns fresh instrument readback. Friendly input aliases are accepted for
`peak_priority`, `enabled_channels_only`, `keepcoup`, `auto_scale`, and
`enable`.

`lock` and `enabled` describe the same capability from opposite sides:
`enabled == not lock`. Supplying both is allowed only when that relationship is
consistent; contradictory requests are rejected before any write. The setter
uses the documented `:AUToset:ENAble` command as the canonical write for this
alias pair and reads both documented `LOCK?` and `ENAble?` forms.

`run_autoset` is explicit and fail-closed. It requires the system AUTO gate to
be enabled, AUTO to be unlocked and enabled, and both documented recording and
playback operation states to be `STOP`. It never unlocks AUTO, stops recording
or playback, changes acquisition state, or polls for completion. The action
changes channel vertical scale, horizontal timebase, and trigger mode; its
result includes the command, effect description, and post-command AUTO
readback. No `*OPC?` or undocumented completion query is used.
