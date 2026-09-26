# Feature expansion — 2026-09-26

The subsequent [native completion batch](NATIVE_COMPLETION.md) adds 12 tools
for **89 current tools** and corrects measurement source-B readback. Its minimum
trials passed; the further [representative hardware trial](FEATURE_TRIAL.md)
passed 17 cases after one decode readback correction. Counts and smoke results
below record the preceding 77-tool checkpoint.

This completes the previously listed remaining feature groups, excluding USB
recovery work. This checkpoint registered **77 tools**, up from 34.
Implementation and focused checks used independent Luna/high workers; root
integrated the modules and executed the reviewed minimal USB smoke harness.
The supplied modular Markdown guide is the command authority.

## Coverage

| Group | Implemented scope | Reference |
|---|---|---|
| Decode | Parallel, IIC/I2C, SPI, UART/RS232, CAN including documented FD fields, LIN, IIS/I2S, FlexRay, M1553; event table | [decode](features/decode.md) |
| Trigger | Details for all 20 documented modes, including serial and nonserial modes | [trigger](features/trigger.md) |
| Waveform | NORM/MAX/RAW, ASC/BYTE/WORD, chunked CSV/raw files; previous 1M CSV cap removed | [waveform](features/waveform.md) |
| FFT | Settings, peak table, displayed MATH waveform sample transfer | [FFT](features/fft.md) |
| Math | Non-FFT arithmetic, functions, logic and filters; display reset | [math](features/math_operations.md) |
| Measurement | Thresholds, regions, sources, statistics and item registration/actions | [measurement](features/measurement_settings.md) |
| Cursor | Manual, tracking and XY configuration/readout | [cursor](features/cursor.md) |
| DVM / counter | Configuration, readings, documented counter actions | [DVM](features/dvm.md), [counter](features/counter.md) |
| Bode | Configuration and explicit sweep start/stop | [Bode](features/bode.md) |
| Histogram | Configuration, statistics and instrument CSV save | [histogram](features/histogram.md) |
| Mask | Configuration, results and documented actions | [mask](features/mask.md) |
| Recording | Record/playback settings and actions | [record](features/record.md) |
| Search / navigation | Search configuration, event results and navigation actions | [search](features/search.md) |
| Reference | Ref1–Ref10 settings, capture/current/display reset | [reference](features/reference.md) |
| Storage | Instrument-side setup, waveform, memory waveform and mask save; documented loads | [storage](features/storage.md) |
| Existing generator / LA | Retained first-batch configuration and explicit generator output controls | [generator](features/generator.md), [LA](features/logic_analyzer.md) |

The 654-entry catalog remains available for other documented commands.
Tool count is not a claim that all 654 commands or all combinations were tested.
Image handling and communication recovery were not expanded in this batch.

## Verification

Focused worker tests passed for each changed feature. Final focused counts:
decode 6, trigger 19, waveform/FFT together 15, math 4, measurement settings 3,
cursor 4, DVM 3, counter 5, Bode 4, histogram 4, mask 12, recording 11,
search/navigation 4, reference 6, storage 7. These are separate focused runs,
not a claimed full-suite regression run. Root checked 77 unique tool names
and valid JSON input schemas; a fresh stdio server advertised all 77 tools.

USB smoke used exact target `MHO9A274501253`, firmware `00.01.00`:

- Passed configuration getters: math, measurement settings, cursor, DVM,
  counter, histogram, mask, recording, search, navigation and reference.
- Passed 16-point NORM BYTE read and 16-point raw WORD file (32 bytes).
- Post-transfer identity passed. Waveform transfer settings were restored.
- Storage initially rejected the native firmware pathname `/data/UserData`
  through an outgoing-input validator. The getter was corrected to preserve
  native readback; a focused regression and only that failed hardware getter
  were rerun successfully. No file save/load was performed during smoke.
- Generator/Bode were skipped based on the preceding verified DG-unavailable
  response. Full FFT sample hardware smoke was skipped because MATH1 was ADD
  with display OFF. No signals were connected for numerical accuracy checks.

Evidence:

- [Initial smoke](../output/all-features-smoke/run-20260926-1328/report.json)
  retains the original storage error alongside successful checks.
- [Storage correction](../output/all-features-smoke/storage-fixed-20260926/report.json)
  records successful native path readback.
- [Raw WORD payload](../output/all-features-smoke/run-20260926-1328/raw-word.bin).
- [First-batch evidence](FIRST_BATCH.md) records prior decode/FFT/trigger
  configuration checks and DG availability.

Normal instrument I/O remains unlimited. No USB reset, power action,
generator output enable, or screenshot capture was used in this expansion.
Large-memory transfers were checked with focused simulated sessions; a full
500M-point hardware transfer was not run.

## Remaining specification and hardware limits

### Generator/Bode capability correction

A later read-only investigation resolved the earlier DG gate: the exact scope
reports `DGSTatus=0` and `MODules=1,0,0,0,0`, but `AFG50=1`, `AFG100=0`,
and `BND=0`. Documented source and Bode settings queries respond normally.
The old early rejection on DG=0 therefore prevented valid licensed readback.

Generator and Bode now accept positive documented option status together with
successful functional readback. Responses preserve the raw DG flag and option
evidence, including a discrepancy warning. All-negative capability remains
rejected. AFG50-only fallback limits sine frequency to 50 MHz and retains lower
waveform-specific limits. This is not a firmware upgrade or license change.

Luna/high implemented the bounded correction; 13 focused generator/Bode tests
passed. A fresh MCP hardware smoke passed `get_generator(channel=1)` and
`get_bode`. Source1 read SIN, 1 kHz, 5 Vpp, HighZ, output OFF. Bode read OFF/STOP,
LOG, CH1/CH2, 100 Hz–1 MHz, 10 points/decade, 0.2 V.
[Evidence](../output/all-features-smoke/generator-capability-20260926-r2/report.json).
The preceding harness attempt omitted required `channel` and stopped at input
validation; its separate original report is preserved. No output, sweep,
instrument setting, reset, or timeout change was performed.

### Still unresolved

- `:HISTogram:RESet?` has ambiguous action/query spelling in the guide and is
  explicitly rejected. Histogram statistics are available; a bin-download
  command is not documented.
- WORD byte order and signedness are undocumented. Raw transfer works;
  numerical interpretation requires explicit caller-declared encoding.
- FFT full-spectrum mode retrieves the displayed MATH waveform (NORM, at most
  1,000 points), not an undocumented full internal FFT-bin array. Its native
  x axis is retained; conversion to Hz requires caller-declared calibration.
  The documented peak table supplies parsed Hz values independently.
- Bode numeric trace download and REF trace download have no documented
  command path. Their settings/actions are available; no download command was
  invented. A*X+B math coefficients also have no documented setters.
- Generator/Bode configuration readback is hardware-verified after the above
  correction. Physical generator output and Bode sweep accuracy remain
  unverified. Implemented setters/actions for other groups
  have focused offline checks, not exhaustive physical validation.
- SMB password commands remain blocked. USB enumeration-loss recovery remains
  outside this work. Existing fresh-session reconnect behavior is unchanged.

Restart the existing `rigol-mho98` MCP process (or Codex) to load the new tools.
