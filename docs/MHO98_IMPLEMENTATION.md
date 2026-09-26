# MHO98 implementation handoff

This note records the implementation boundary and the offline evidence for the
MHO98-only MCP server. The original upstream implementation remains available
under `src/rigol_mcp/scope.py`, `src/rigol_mcp/drivers.py`, and
`src/rigol_mcp/server.py`; the MHO98 server is a separate package and entry
point.

## Source and provenance

- Baseline repository: `ef09519` (`Steer clients toward data tools over screenshot`).
- Programming guide: `/Users/kitour/Downloads/MHO98_ProgrammingGuide_EN.pdf`.
- Programming guide SHA-256: `99f85d87e152bf1bcd247a9983cb9cb67de10be042b09eb78fe426033d297b24`.
- Modular source archive: `/Users/kitour/Downloads/MHO98_SCPI_AI_modular.zip`.
- Modular archive SHA-256: `e82141dd79a17b95aec336579b4591e52d396aefb68394a5a36e8c67f717489a`.
- Safe extraction destination: `/Users/kitour/Documents/RIGOL_MCP/reference/`.

The package contains a 654-entry execution index with command syntax, argument
types, static ranges and syntax corrections. Manual prose, examples and extracted
Markdown are excluded from distribution. Original references are kept outside
the repository. This index does not establish runtime option availability or
hardware behavior.

## Runtime boundary

The installed executable is:

```text
/Users/kitour/Documents/RIGOL_MCP/rigol-mcp/.venv/bin/rigol-mho98
```

USB uses `RIGOL_USB=1` and optionally `RIGOL_USB_SERIAL`. LAN uses
`RIGOL_IP=<address>` when USB is not enabled. Derived files go below the
absolute `RIGOL_OUTPUT_DIR`. A session requires an exact `MHO98` model field in
`*IDN?`, uses process and interprocess transaction locks, and closes permanently
after a transport fault so an uncertain write cannot be replayed silently.

The default session timeout is `None`, which requests PyVISA's infinite
`VI_TMO_INFINITE` value. Positive integer `timeout_ms` overrides are applied and
read back; unsupported or rejected timeout assignments fail session setup
instead of being ignored. In the installed PyVISA-py 0.8.1 USB path,
`pyvisa_py/usb.py` maps VISA infinity to `interface.timeout=2**32-1`. For the
default no-time-limit policy, this implementation changes that live interface
to `0` only while each USB transfer runs, then restores the VISA infinite
value. PyUSB/libusb interprets zero as no transfer timeout. A backend that does
not expose this pyvisa-py interface is limited to that backend's interpretation
of the PyVISA infinite setting; no third-party code is monkeypatched.

Transport faults do not reset the target device and do not reset hub ports or
USB power. `recover_connection` performs one fresh open and verifies the target
IDN, including USB serial `MHO9A274501253`, without replaying the failed
command. Host USB enumeration disappearance cannot be repaired by SCPI or by
this reconnect path. The earlier screenshot timeout followed by an empty USB
enumeration is recorded as an observation, not as a proven root cause.

For USB resources, text responses use a bounded 4 MiB logical-message read and
binary responses use one bounded low-level VISA read sized from the caller's
payload limit. The binary reader disables the VISA termchar only for that read,
restores it afterward, accepts EOM with no ASCII terminator as well as LF/CRLF,
and rejects truncated declarations, oversize blocks, invalid trailers, and
non-complete VISA statuses. Receive errors include the read stage and received
byte count. LAN socket resources retain exact-field reads so a cap-sized raw
read cannot wait for the full cap after the message has already completed.

The 89 registered tools are:

```text
idn, download_binary, restore_setup,
search_commands, describe_command, query_command, write_command,
get_acquisition, set_acquisition, acquisition_control,
get_channel, set_channel,
measure, measure_between, measure_statistics,
get_timebase, set_timebase, get_trigger, set_trigger,
get_waveform, export_waveform_csv, screenshot, recover_connection,
get_decode, set_decode, read_decode_events,
get_fft, set_fft, read_fft,
get_generator, set_generator, set_generator_output,
get_logic_analyzer, set_logic_analyzer,
get_math, set_math, math_action,
get_measurement_settings, set_measurement_settings, measurement_action,
get_cursor, set_cursor, read_cursor, get_dvm, set_dvm, read_dvm,
get_counter, set_counter, read_counter, counter_action,
get_bode, set_bode, bode_action,
get_histogram, set_histogram, read_histogram, histogram_action,
get_mask, set_mask, read_mask, mask_action,
get_recording, set_recording, recording_action,
get_reference, set_reference, reference_action,
get_search, set_search, read_search_events,
get_navigation, set_navigation, navigate,
get_storage, set_storage, save_file, load_file,
get_autoset, set_autoset, run_autoset,
get_display, set_display, display_action, get_quick_action, set_quick_action,
get_system, set_system, get_capabilities, read_instrument_error
```

Current coverage and latest hardware findings are documented in
`docs/ALL_FEATURES.md`; the final 89-tool implementation stage and its pending
trials are in `docs/NATIVE_COMPLETION.md`. `docs/FIRST_BATCH.md` and the historical 22-tool smoke
records below predate the latest additions and remain historical evidence.

`query_command` and `write_command` require a catalog ID, explicit index values,
and an ordered argument list. The intended sequence is `search_commands`, then
`describe_command`, then one validated command call. Binary commands are routed
to dedicated handlers. `HISTogram:RESet?` is rejected as an ambiguous action;
SMB password commands are rejected. There is no unrestricted public raw-SCPI
tool.

Waveform RAW CSV export streams up to the documented current memory depth
(maximum 500M points) and requires the scope to already be in `STOP`; it never
stops acquisition implicitly. Inline reads are limited to 100,000 points;
larger reads require files. ASC, BYTE, and raw WORD transfers are implemented;
interpreted WORD requires caller-declared encoding. `download_binary`
creates a new bounded BUS/image/setup artifact. `restore_setup` reads an existing
`.stp` file below `RIGOL_OUTPUT_DIR` and replaces the complete instrument setup.

## Validation evidence

The recorded offline baseline before later focused additions was:

```text
rtk proxy .venv/bin/pytest -q
204 passed
```

The root integration handoff separately recorded a later limited validation of
40 passed checks. These counts are kept separate from the baseline because the
later feature workers added focused tests.

The no-hardware MCP protocol smoke was:

```text
rtk proxy .venv/bin/python \
  /Users/kitour/Documents/RIGOL_MCP/output/validation/stdio_no_hardware_smoke.py
```

Evidence artifact:
`/Users/kitour/Documents/RIGOL_MCP/output/validation/stdio-no-hardware-smoke-20260926T040949+0900.json`.
It records protocol `2025-11-25`, server `rigol-mho98`, 22 tools, successful
catalog search/describe calls, and `isError` responses for an unknown tool and
invalid arguments.

The earlier `USBError[Errno 13] Access denied` opening failure is historical;
the user resolved it before the later hardware smoke. That later run verified
the MHO98 identity, state getters, a valid CH1 VPP result of `0.10567`, a
1,000-point NORM ASCII waveform, and a 64-row NORM CSV. The CSV is
`/Users/kitour/Documents/RIGOL_MCP/output/validation/mho98-norm-64-20260926T042300+0900.csv`
with SHA-256
`7f27e7f57f37874fec5375611a2b92d4ebe5b0c2a46e4d95c5d08c0f2ffdfe99`.
The full call record is
`/Users/kitour/Documents/RIGOL_MCP/output/validation/stdio-hardware-smoke-resume-20260926T042300+0900.json`.

The same run timed out on `:DISPlay:DATA? PNG`. USB enumeration was empty after
that timeout, so the guarded harness could not restore CH1 to OFF. At that failure,
the recorded state had CH1 ON with its original 50 ohm, DC, probe 100, 0.5 V/div,
bandwidth-limit OFF settings. The authorized impedance/coupling round trip and
RAW acquisition exercise were not reached. Guard and restoration evidence is
`/Users/kitour/Documents/RIGOL_MCP/output/validation/guarded-hardware-smoke-20260926T042257+0900.json`.

The earlier USB receive correction had the following offline validation:

```text
rtk proxy .venv/bin/pytest -q tests/test_mho98_foundation.py
19 passed

rtk proxy .venv/bin/python -m py_compile \
  src/rigol_mcp/mho98/session.py tests/test_mho98_foundation.py
```

The focused VISA-like tests cover a complete header and payload in one read,
EOM without LF, and fault-closed truncated/oversize responses.

### 2026-09-26 no-timeout and reconnect verification

The independent Luna/high worker completed the timeout/reset-removal changes
with 28 focused tests passing and compilation passing. Root integration
inspection confirmed no USB reset or hub-control calls remain in the MHO98
package. A Sol/high worker authored and ran the minimal fresh-stdio harness;
its sandbox could not enumerate the target. IORegistry and an approved
target-only descriptor read established the exact device was present. Root
then executed that reviewed harness through the normal approval path, without
changing worker sandbox settings or production source.

Evidence: `output/usb-reconnect-check-host-20260926/report.json`.
Passed: exact IDN, CH1 readback, `recover_connection` with `stage=fresh_open`,
one PNG, and a post-transfer IDN. Screenshot: 1024x600 RGBA, 75,659 bytes,
1.325186 seconds; decoded with Pillow and visually inspected.
SHA-256: `e65e7f975f533324d4e3cd934d028d8949f90ff732842cf057d3afc88b3af91f`.
CH1 readback was ON, 1 Mohm, DC, probe 1, 0.05 V/div. No setting, USB reset,
power operation, or failed-command replay occurred. This run used infinite
server I/O and MCP ClientSession read timeout None. It does not prove recovery
from OS-level USB disappearance, and the original failure cause remains unknown.
Codex's separate MCP per-tool deadline is unchanged; its documented default
is 60 seconds (https://learn.chatgpt.com/docs/extend/mcp?surface=cli).
Existing MCP processes need a restart to load corrected source.

`/Users/kitour/Documents/RIGOL_MCP/output/validation/command-coverage.json` and
`command-coverage-routing.py/.json` are an offline syntax-routing inventory.
They show query selection for 595 of 654 entries and write selection for 582 of
654 entries, but they are not full argument validation or hardware coverage.
