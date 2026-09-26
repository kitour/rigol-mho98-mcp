# First feature batch — 2026-09-26

Historical checkpoint. The subsequent [feature completion](ALL_FEATURES.md)
supersedes the remaining-work list below and brings the server to 77 tools.

Added 11 tools, for 34 total, and extended existing trigger tools. Implementation
and feature checks used independent Luna/high workers through the direct worker
orchestrator MCP. No Sol worker was needed for this batch. Root integrated tool
registration and reviewed/executed the worker-authored minimal hardware harness.

## Implemented scope

| Feature | Tools | Details |
|---|---|---|
| Communication decode | get_decode, set_decode, read_decode_events | I2C/IIC, SPI, UART/RS232; BUS1-4 common settings; documented event table as columns/string rows and optional CSV |
| FFT | get_fft, set_fft, read_fft | MATH1-4 FFT settings and documented peak table, retaining amplitude units and converting reported frequency units to Hz |
| Generator | get_generator, set_generator, set_generator_output | Channels 1/2, waveform/timing/load/voltage, AM/FM/PM, instrument-side arbitrary files; output enable is explicit |
| Digital inputs | get_logic_analyzer, set_logic_analyzer | D0-15 and POD1/2 configuration; no digital waveform extraction |
| Communication trigger | existing get_trigger/set_trigger | Named conditional details for I2C/IIC, SPI, UART/RS232; common and EDGE behavior preserved |

Callable examples and actual parameter names:
[decode](features/decode.md), [FFT](features/fft.md),
[generator](features/generator.md), [logic analyzer](features/logic_analyzer.md),
[trigger](features/trigger.md).

## Minimum verification

Feature-focused tests: decode 5, generator 6, FFT 5, logic analyzer 5, trigger 10
(including existing trigger tests), all passed. Root checked 34 unique tool names
and valid JSON schemas. No full regression or signal-accuracy test campaign was run.

Fresh stdio MCP on MHO98 serial MHO9A274501253 verified:
- I2C decode settings and HEX/BIN setting readback.
- FFT selection/settings readback, with MATH display left disabled.
- LA/POD settings readback with no external-probe presence claim.
- I2C trigger mode/detail readback and restoration to original EDGE mode.
- Final identity response after settings restoration.

Generator query `:SYSTem:DGSTatus?` returned 0. The tools reported DG unavailable;
no generator setting or output was changed. Generator implementation is covered
offline, but hardware output/accuracy is unverified on this unit.
Later investigation found AFG50 active despite that flag and corrected the gate;
generator and Bode getters subsequently passed. See
[current capability evidence](ALL_FEATURES.md#generatorbode-capability-correction).

The first harness restoration supplied an unchanged label while BUS display was
off. Feature validation rejected it before writes; the harness incorrectly marked
that validation error as a transport failure. USB communication had not failed.
Root corrected the harness to restore only touched fields, then restored the
recorded settings separately and verified readbacks and IDN. The original report
is preserved as evidence, not relabeled as a fully passing run.

Evidence under `output/first-batch-smoke/run-20260926-0637/`:
- `report.json`: original fresh-stdio calls, successes, DG unavailability and harness error.
- `restoration.json`: BUS1 HEX/PAR, MATH1 HANN/display OFF/ADD restored, final IDN.
- `trigger.json`: EDGE -> IIC -> EDGE readbacks and final IDN.

Normal instrument I/O remains unlimited. No USB reset/power action or generator
output enable was used. This batch performed no screenshot acquisition.

## Remaining boundaries

- Dedicated decode and communication-trigger details for CAN/CAN-FD, LIN, I2S,
  FlexRay, M1553 and parallel decode are subsequent work; generic catalog routes exist.
- `read_fft` is peak-table-only. Full-spectrum bins/frequency-axis derivation is
  not claimed. Event and peak parsers were checked with documented/fake data;
  no connected signal was available for end-to-end numerical verification.
- Other function families (non-FFT math/filters, Bode, cursor, histogram, mask,
  recorder, etc.) and larger waveform transfer remain later batches.
- USB enumeration-loss recovery remains unresolved; fresh session reconnect is
  available without USB resets.
- Restart/reconnect existing MCP processes to discover the 11 new tools.
