# MHO98 MCP server

The executable is [`.venv/bin/rigol-mho98`](/Users/kitour/Documents/RIGOL_MCP/rigol-mcp/.venv/bin/rigol-mho98)
and its source entry point is `rigol_mcp.mho98.server:main`. It runs an MHO98-only
MCP stdio server. Each transaction is serialized. Normal operations send no
implicit `*IDN?` or SCPI error queries and never retry commands after a fault.
Identity and error queries are explicit tools.

## Fast operation policy (2026-09-26)

- Settings/actions send the requested commands without before/after snapshots,
  comparison reads, option probes or automatic error-queue checks. Responses
  acknowledge transmission (`sent`, `verified: false`), not instrument acceptance.
- Measurements retain result interpretation: source, mode, unit and calibration
  metadata as applicable. No display/option preflight or unrelated full-state dump.
- Protocol-routed fields can read one selector when the caller omits the mode;
  supplying that selector avoids the lookup. No physical state cache is assumed.
- Waveform reads retain transfer-selector preservation and waveform preamble
  conversion; restoring selectors uses tracked writes, without another snapshot.
- `get_*` explicitly requests settings; `idn`, `get_capabilities` and
  `read_instrument_error` explicitly request diagnostics. They are never added
  around ordinary settings/measurements by the server.
- Existing validation records below describe earlier versions. The fast paths
  were checked offline; no new hardware roundtrip campaign was performed.

See [fast operation implementation notes](docs/FAST_OPERATIONS.md).

## Human-owned channel input settings

Input impedance, measurement units, and probe ratio are set by the human at the
instrument, or changed remotely only when the human explicitly requests them.
Never infer these from coupling, vertical scale, experiment goals, or presets.

- `set_channel` excludes these three fields and rejects them before any I/O.
  Every other channel setting is REQUIRED on every call: display, bandwidth,
  invert, coupling, scale, offset, deskew, fine scale, label visibility/text,
  and bias. Missing or null values are rejected locally before any write.
  Codex must construct the complete packet rather than reuse unknown old state.
- `set_channel_input` sends only explicitly human-requested input fields.
  Its description is an agent instruction; the server cannot independently
  authenticate whether a tool argument originated in a human instruction.
- `write_command` rejects partial channel writes. Ordinary channel changes use
  the complete packet; the three human-owned fields use the human-directed tool.
- Do not use reset/setup restore/AUTO as an indirect workaround for this policy.
- Do not fill these fields when constructing a complete settings packet. Leave
  them under human control; do not add preflight reads or readback verification.

## Configuration

The normal USB configuration is:

```sh
RIGOL_USB=1 \
RIGOL_OUTPUT_DIR=/Users/kitour/Documents/RIGOL_MCP/output \
/Users/kitour/Documents/RIGOL_MCP/rigol-mcp/.venv/bin/rigol-mho98
```

The server reuses the existing USBTMC backend selection. Set
`RIGOL_USB_SERIAL` when more than one Rigol USB instrument is visible. LAN is
available with `RIGOL_IP=<instrument-address>` when `RIGOL_USB` is not enabled.
`RIGOL_OUTPUT_DIR` is the absolute destination for new waveform, screenshot,
and binary artifacts. Normal MHO98 I/O has no application timeout by default:
the session requests PyVISA's infinite timeout. Positive finite `timeout_ms`
overrides are applied and read back, with setup failing if the transport does
not apply the requested value. For pyvisa-py USB, default-policy I/O uses
libusb's `timeout=0` only during the transfer and restores the VISA infinite
value afterward; other VISA backends retain their own infinite-timeout
behavior.

## Tools and scope

The server currently exposes 90 tools:

- identity and catalog: `idn`, `search_commands`, `describe_command`
- catalog execution: `query_command`, `write_command`
- acquisition: `get_acquisition`, `set_acquisition`, `acquisition_control`
- channels and measurements: `get_channel`, `set_channel`, `set_channel_input`, `measure`,
  `measure_between`, `measure_statistics`
- timing and trigger: `get_timebase`, `set_timebase`, `get_trigger`,
  `set_trigger`
- waveform and binary transfer: `get_waveform`, `export_waveform_csv`,
  `screenshot`, `download_binary`, `restore_setup`
- fresh session reconnect: `recover_connection`
- communication decode: `get_decode`, `set_decode`, `read_decode_events`
- FFT: `get_fft`, `set_fft`, `read_fft` (peak table and MATH waveform samples)
- generator: `get_generator`, `set_generator`, `set_generator_output`
- digital inputs: `get_logic_analyzer`, `set_logic_analyzer`

- math and measurement settings: `get_math`, `set_math`, `math_action`,
  `get_measurement_settings`, `set_measurement_settings`, `measurement_action`
- cursor/DVM/counter: `get_cursor`, `set_cursor`, `read_cursor`, `get_dvm`,
  `set_dvm`, `read_dvm`, `get_counter`, `set_counter`, `read_counter`, `counter_action`
- Bode/histogram/mask: `get_bode`, `set_bode`, `bode_action`, `get_histogram`,
  `set_histogram`, `read_histogram`, `histogram_action`, `get_mask`, `set_mask`,
  `read_mask`, `mask_action`
- recording and reference: `get_recording`, `set_recording`, `recording_action`,
  `get_reference`, `set_reference`, `reference_action`
- search/navigation: `get_search`, `set_search`, `read_search_events`,
  `get_navigation`, `set_navigation`, `navigate`
- instrument storage: `get_storage`, `set_storage`, `save_file`, `load_file`
- AUTO: `get_autoset`, `set_autoset`, `run_autoset`
- display and quick key: `get_display`, `set_display`, `display_action`,
  `get_quick_action`, `set_quick_action`
- system and capability: `get_system`, `set_system`, `get_capabilities`,
  `read_instrument_error`

Dedicated details now cover all nine documented decode families and all twenty
trigger modes. See [current feature coverage](docs/ALL_FEATURES.md) for exact
scope, examples, verification, and limitations. The [first batch](docs/FIRST_BATCH.md)
is historical. Image-related tools and USB recovery were not expanded.
New tools require existing MCP processes to restart.

The documented 654-command catalog is searched with `search_commands` and
inspected with `describe_command`; it is not exposed as 654 executable tools.
Catalog records contain command syntax, argument types, static constraints,
and syntax corrections; manual text and examples are not distributed. There is no public unrestricted raw-SCPI tool.

### Catalog command execution

Search first, inspect the selected entry, then pass its catalog ID to one
explicit query or write. For example, the channel scale entry is currently
`channel-n-scale-scale-099`:

```json
{"query":"SCALe","family":"channel","limit":20}
```

```json
{"id":"channel-n-scale-scale-099"}
```

```json
{"id":"channel-n-scale-scale-099","indices":{"n":1},"arguments":[]}
```

The last object is the `query_command` call. A write uses the same ID and index
with an ordered argument list, for example
`{"id":"channel-n-scale-scale-099","indices":{"n":1},"arguments":[0.1]}`.
Indices and arguments are checked against the catalog entry; ambiguous manual
syntax and binary commands are rejected by this text executor.

Waveform transfers support ASC/BYTE/WORD and chunked file export up to the
documented current memory depth (maximum 500M points). RAW requires the
instrument already to be in `STOP`; the tool never stops it implicitly.
Inline results are capped at 100,000 points; larger captures require a file.
WORD interpretation requires explicit caller-declared byte order and signedness;
raw WORD files need neither. See [waveform details](docs/features/waveform.md).
`download_binary` writes a new bounded BUS/image/setup artifact.
`restore_setup` uploads an existing `.stp` file and replaces the complete
instrument setup, so it is an explicit state changing operation.

The following operations are rejected: `HISTogram:RESet?` because the manual
entry is an ambiguous action, and SMB password commands because credentials must
not pass through the executor.

The catalog is a static documentation index. It does not automatically verify
dynamic state constraints, installed options, or physical instrument behavior.

The implementation reference is the supplied
`/Users/kitour/Downloads/MHO98_ProgrammingGuide_EN.pdf` with SHA-256
`99f85d87e152bf1bcd247a9983cb9cb67de10be042b09eb78fe426033d297b24` and the
modular source archive
`/Users/kitour/Downloads/MHO98_SCPI_AI_modular.zip`, extracted under
`/Users/kitour/Documents/RIGOL_MCP/reference/`.

## Current validation status

The latest [representative hardware trial](docs/FEATURE_TRIAL.md) passed 17
cases: reversible settings across native features and a 16-point FFT sample
read. Four cases were skipped for option/prerequisite state. Parallel endian
readback was corrected for observed LSB, with 11 focused tests passing. FFT
display auto-adjustment is now documented and the trial restores those values.
Restart the existing MCP process to load the decode correction.

The final native implementation batch brings registration to 89 tools. AUTO,
display/quick-key and system utilities are implemented, and measurement source B
now uses the documented PSB alias. Source syntax, tool uniqueness and input
schemas passed static checks. New fake-session tests are prepared but not run;
new hardware trials are deferred until after this build stage. See
[native completion and pending trials](docs/NATIVE_COMPLETION.md).

Subsequent minimum trials are complete: the four focused suites passed 19
checks, and system readback fixes passed a final 8 focused checks. Native
getters and three reversible setting roundtrips passed on hardware with
restoration verified. See the linked trial record for the TIME colon-format
fix, unknown LOWPower=255 handling and remaining conversation-tool metadata
mismatch. The earlier build-stage deferral above is historical.

The preceding expansion passed focused feature tests and exposed 77 tools in a fresh
stdio MCP process. Hardware smoke verified twelve new configuration getters and
16-point BYTE/WORD transfers. Storage readback initially rejected the firmware's
native `/data/UserData` path; that parser was corrected and the failed getter
alone was rechecked successfully. See [coverage and evidence](docs/ALL_FEATURES.md).
The following transport history predates this expansion.

Subsequent generator/Bode investigation found AFG50 active despite DG status 0.
The capability gate now considers documented option status, preserves the
conflicting DG flag, and requires valid functional readback. Both getters passed
on hardware; physical output and sweep accuracy are still untested. See the
[capability correction](docs/ALL_FEATURES.md#generatorbode-capability-correction).

Real-hardware USB checks passed for identity and state getters, CH1 VPP, a
1,000-point NORM ASCII waveform, and a 64-row NORM CSV. The following screenshot
request timed out, after which the scope no longer enumerated over USB. This is
an observation, not a proven root cause. At that failure, the
recorded scope state had CH1 ON with its original 50 ohm, DC, probe 100,
0.5 V/div, bandwidth-limit OFF settings; the planned impedance/coupling round
trip and RAW exercise were not reached.

The USB receive path now reads one bounded VISA logical message, validates the
IEEE block in memory, accepts EOM without LF as well as LF/CRLF, restores the
binary-read termchar setting, and faults closed with read-stage and byte-count
diagnostics on malformed, incomplete, or oversize responses. USB text queries
use a 4 MiB bound for large ASCII waveform responses. LAN keeps its exact-length
socket path.

Transport faults close the session without resetting the instrument, USB
device, hub, or power and without replaying the failed command.
`recover_connection` only opens a fresh connection and verifies
`RIGOL TECHNOLOGIES,MHO98,MHO9A274501253,...`; it performs no USB topology
repair. Host USB enumeration disappearance cannot be fixed by SCPI reconnect,
so physical re-enumeration remains outside this server.

After the user replugged USB, the completed correction passed 28 focused
offline tests and a fresh MCP hardware check on 2026-09-26: exact IDN, CH1
readback, explicit fresh reconnect, one complete 1024x600 PNG (75,659 bytes,
1.325 seconds), and post-transfer IDN. No reset or power operation was used.
The new CH1 readback was ON, 1 Mohm, DC, probe 1, 0.05 V/div; this check did
not change those settings. The first worker-sandbox attempt could not enumerate
USB; an approved host execution of its reviewed harness succeeded. Evidence:
`output/usb-reconnect-check-host-20260926/report.json` and its PNG.
This proves fresh session reconnection, not unattended recovery from USB
enumeration loss. Codex's own MCP client timeout is separate from the server's
infinite I/O policy and has not been changed. Restart existing MCP processes
before using the corrected server. Earlier evidence and implementation notes are in
`docs/MHO98_IMPLEMENTATION.md`. The command coverage JSON files are syntax
routing inventories; they do not prove complete argument or hardware behavior.
