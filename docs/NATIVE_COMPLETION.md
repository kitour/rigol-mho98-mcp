# Native implementation completion — 2026-09-26

Further representative feature tests are recorded in [FEATURE_TRIAL.md](FEATURE_TRIAL.md):
17 successful hardware cases, four prerequisite skips, one decode readback fix,
and FFT display auto-adjustment/restoration evidence.

## Subsequent minimum trial completed

After the user restarted Codex, the four prepared focused suites passed:
AUTO, display, system and measurement settings, **19 tests**. A fresh stdio
MCP connection advertised all **89 tools** with the expected annotations.

Hardware trials on `MHO9A274501253`, firmware `00.01.00`, found and fixed two
system readback assumptions:

- `TIME?` returns `HH:MM:SS` on this firmware. The parser now accepts both that
  form and the documented comma form, with unchanged range checks. Outgoing
  time commands remain comma-delimited. Focused system tests then passed 5.
- `LOWPower?` returns `255`, whose meaning is not documented. It is preserved
  as `low_power_raw: "255"`, with `low_power: null` and an explicit warning.
  Other system settings remain usable; an explicit low-power change is blocked
  before any write while the state is unknown. Final focused system tests
  passed 8. This does not claim low-power support or fix firmware behavior.

The corrected trial passed AUTO/display/system/capability/measurement getters;
quick-key readback passed in the first attempt. Phase and delay source B both
returned CHAN2. AFG50 status and validity both returned 1 despite DG status 0.
Roundtrips passed for AUTO peak, grid brightness and clock visibility. Final
restoration verified peak=true, brightness=50, show_time=true. No acquisition,
generator output, locks, power, screenshot, reset or error-queue action was used.

Evidence: [passing trial](../output/native-trial/run-20260926-r3/evidence.json).
The first and second attempt evidence remains alongside it; both stopped
before writes on the parser errors above. Getter snapshots were refreshed for
the eventual setting roundtrip. No all-command or signal-accuracy test campaign
was run.

The configured executable is the correct repository entry point and has no
tool allow/deny list. After the user's MCP refresh, this conversation's actual
tool inventory also contained all 89 tools. A direct `get_system` call through
the refreshed connector returned the corrected TIME/LOWPower fields. The earlier
23-tool client metadata mismatch is resolved; its cause was not established.

The sections below record the implementation checkpoint before these trials.

User direction: finish feasible instrument-native implementation first, then
trial and fix. PC-side FFT/analysis alternatives are postponed. USB recovery
remains outside scope. No instrument command was sent in this stage.

## Completed code

The server registers **89 tools**, previously 77. Independent Luna/high workers
implemented the feature modules; root integrated registration and metadata.

| Addition | Tools / change | Detail |
|---|---|---|
| AUTO | get_autoset, set_autoset, run_autoset | [Settings, gate and recording/playback prerequisites](features/autoset.md) |
| Display | get_display, set_display, display_action | [Persistence, brightness, grid, rulers, color, hold, explicit clear](features/display.md) |
| Quick key | get_quick_action, set_quick_action | Changes assignment only; does not execute the assigned action |
| System | get_system, set_system | [Documented settings, calendar/time and explicit lock/power fields](features/system.md) |
| Capabilities | get_capabilities | Raw identity/modules and documented option status/validity; preserves conflicting evidence |
| Instrument error | read_instrument_error | Consumes exactly one queue entry explicitly; never silently drains |
| Measurement | delay_source_b readback through PSB? | [Guide explicitly equates PSB/DSB](features/measurement_settings.md); matching aliases deduplicate and conflicting B aliases reject before writes |
| MCP metadata | set_channel and set_timebase are non-read-only | Corrected misleading annotations for setters |

The supplied Markdown and existing feature implementations were compared for
concrete missing functionality. This found the PSB/DSB alias gap above; the
other existing feature groups have documented native routes through dedicated
tools or the catalog. This is an implementation inventory, not proof that every
documented command and state combination works on firmware.

Less common IEEE488, LAN, option-management and other documented commands retain
the catalog route. This batch adds no network configuration, license changes,
image transfer, resets, or host-side calculation substitute.

## Checks performed

- Worker source/test syntax checks passed.
- Root imported registration without opening an instrument, parsed package
  source syntax, and checked all 89 unique names and JSON input schemas.
- No `set_*` tool is annotated read-only after integration.
- Functional pytest runs and instrument trials for this batch have **not run**.
  Test files are prepared for the next stage.

## Minimal next trial stage

1. Run focused new/changed fake-session tests: AUTO, display, system and
   measurement settings. Fix concrete failures only.
2. Restart the MCP process; check new tool registration and one representative
   readback each for AUTO, display, system/capabilities and measurement source B.
3. Try one reversible setting per changed group and restore it. Keep AUTO run,
   display clearing, error-queue consumption, locks and low-power changes out
   of getter-only smoke; exercise actions deliberately where needed.
4. For remaining protocol detail, generator/Bode output, WORD encoding and FFT
   axis checks, use targeted trials suited to the actual signal connections.
   Share the one USB instrument sequentially. Normal I/O remains unlimited;
   no automatic reset or command replay.

Do not rerun already passed earlier checks unless the relevant implementation
changed or a concrete failure requires it. Previous hardware evidence stays in
[ALL_FEATURES.md](ALL_FEATURES.md).

## Remaining unresolved specification

These require authoritative clarification or targeted hardware evidence before
claiming support: histogram reset's question-mark syntax, WORD byte order and
signedness, native FFT waveform frequency-axis interpretation, Bode/REF numeric
trace download and undocumented A*X+B coefficient setters. They are not filled
with guessed commands. Existing ASCII/BYTE transfer, native FFT samples/peaks,
and documented configuration/actions remain available.

Existing Codex MCP processes need restarting to load this stage.
