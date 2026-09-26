# Minimal runtime I/O — 2026-09-26

## Current contract

All original 89 tools remain registered; `set_channel_input` adds one human-directed tool (90 total). Settings/actions send explicitly requested SCPI
commands. They do not take before/after snapshots, probe installed options,
check enabled sources, compare existing settings, poll completion, or query the
SCPI error queue. Static argument parsing remains local. Acknowledgments report
`sent`/`written` and `verified: false`; they are not confirmed physical state.
Binary setup upload follows the same contract. Transport failures propagate;
commands are never retried or replayed automatically.

Session text/binary read/write operations add no implicit `*IDN?` or error query.
The configured USB serial selection and interprocess transaction lock remain.
Explicit identity, capability, error and recovery tools still perform the
requested diagnostics. No new timeout, USB reset or power operation was added.

## Complete channel packets

The previous partial three-command channel example is superseded. `set_channel`
requires all 11 ordinary fields on every call (missing/null values fail locally
before I/O): display, bandwidth, invert, coupling, scale, offset, deskew,
fine_scale, label_visible, label and bias. Every supplied field is sent, even if
its requested value might already be active. Ordinary channel writes through
`write_command` are blocked so a partial catalog command cannot bypass this rule.
The three human-owned input fields remain excluded.

A complete normal CH4 packet for ON / AC / scale 1 includes bandwidth OFF,
offset/bias/deskew 0, invert/fine scale/label visibility OFF, and label CH4.
It produces 11 SCPI writes and no queries. This packet uses the existing
human-selected units and probe ratio; legacy `_v` argument names do not change
physical input units. An explicit display ON is first, and OFF is last.

## Necessary reads

- Protocol-dependent trigger details, decoder fields, search fields and generator
  modulation fields may read one mode selector when it is omitted and needed to
  form the SCPI header. Provide the selector to avoid that lookup.
- Ordinary measurements keep source/item/statistic metadata, acquisition type,
  and source units when the measurement is amplitude dependent.
- DVM/counter reads keep their mode/source. Cursor reads keep mode/source/units,
  without querying indicators, screen positions, or a timebase prerequisite.
- FFT results keep actual operator and FFT source/window/mode. A non-FFT MATH
  operator is reported as no FFT measurement, never relabeled as FFT. Spectrum
  amplitude units and waveform preamble remain; native x is not assumed Hz.
- Histogram results keep source/type/range; search events keep mode and search
  conditions. Decoder CSV carries its protocol/header in the payload.
- Waveforms keep the six transfer selectors needed to restore the preexisting
  transfer setup plus preamble/data reads. The restore uses tracked writes,
  without a second six-query snapshot. Numeric parsing and binary framing remain.
- Explicit `get_*` calls return requested settings; normal operations never call
  them just to verify another operation. Generator/Bode getters no longer probe
  option availability before reading their configuration.

## Changed code

The feature modules under `src/rigol_mcp/mho98/`, `session.py`, `binary.py` and
`command.py` implement this contract. No global MCP configuration changed.
The active already-running server must be reconnected/restarted to load these
Python changes; a fresh process imports the new implementation immediately.

## Minimal verification

- Luna control-group offline smoke: 23 writes, zero queries.
- Luna measurement-group offline smoke: 19 setters/actions, 49 writes, zero queries.
- Integration smoke: actual Session with a fake wire proves three channel writes
  and zero queries, zero-query FFT/EDGE setters, no hidden IDN/error traffic on
  text reads or binary writes, retained measurement context, retained waveform
  values/time/preamble and selector restoration, and 89 registered tools.
- Command: `rtk proxy .venv/bin/python output/fast-integration/smoke.py` — PASS.

No oscilloscope setting was changed for this refactor. No hardware speed claim
is made. Older tests asserting automatic snapshots/prerequisites describe the
superseded API contract and were not run as a broad regression campaign.

## Human-owned inputs — subsequent policy update

Impedance, units, and probe ratio are excluded from ordinary channel setting
packets. Human front-panel changes are respected; remote changes require an
explicit human instruction via `set_channel_input`. `set_channel` rejects those
keys before writing anything; generic catalog writes to those three commands
are rejected too. No automatic default or inference is allowed.

Offline targeted check passed: all three ordinary-channel changes rejected
before I/O; normal ON/scale/AC still sends three commands; human-directed input
settings send only supplied commands; catalog impedance bypass rejected; zero
queries. No hardware changes were made. The server needs a reconnect to expose
the updated schema and additional tool.

## Complete packet correction and actual send

After a user photo showed CH4 still at 250 MHz bandwidth and CH1 at 50 ohm/W,
the ordinary channel schema and handler were changed to require all 11 fields.
No workers/subagents were used for this correction.

Offline check passed: omission of any of the 11 fields causes zero writes; a
complete packet sends 11 commands including BWLimit OFF; no protected input
commands or queries occur; a partial catalog channel write is rejected.

The running MCP then sent complete packets to CH1–4 (44 total commands, about
20.5 s). All packets included BWLimit OFF and the other ordinary fields above.
CH1 used DC with scale 1 in its human-selected W unit, because the user-reported
50-ohm input cannot support AC. CH2–4 requested AC with scale 1. Impedance/unit/
probe commands were not sent. These are transmission results, not readback
confirmation. The updated required-field schema/guard loads on MCP reconnect;
the actual packets in this run were already complete.
