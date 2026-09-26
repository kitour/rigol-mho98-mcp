# Representative hardware trial — 2026-09-26

Target: RIGOL MHO98, serial MHO9A274501253, firmware 00.01.00, USB only.
User requested minimal functional trial and correction after MCP refresh.
Prior passing offline/getter/native-setting checks were carried forward.
Two independent Luna/high workers authored disjoint harnesses; root reviewed
and executed them sequentially on the single instrument. No application I/O
timeouts, USB resets, power operations or failed-command retries were added.

## Outcome: 17 successful cases

| Group | Representative check | Result |
|---|---|---|
| Decode | BUS1 CAN and LIN selection, details readback, restore PARALLEL | 2 passed after readback fix |
| Trigger | PULSE and CAN mode selection/readback, restore EDGE | 2 passed |
| Generator | Source1 1000 -> 1001 -> 1000 Hz, output remains OFF | Passed |
| Bode | Points per decade change/restore, sweep remains stopped | Passed |
| MATH | Grid setting change/restore | Passed |
| Measurement | Statistics count change/restore | Passed |
| Cursor | Manual mode selection, restore OFF | Passed |
| DVM | Mode change/restore | Passed |
| Counter | Resolution digits change/restore | Passed |
| Histogram | Height change/restore while disabled | Passed |
| Recording | Record interval change/restore while stopped | Passed |
| Search | Edge slope change/restore | Passed |
| Reference | Ref1 color change/restore | Passed |
| Storage | Filename prefix change/restore; no file save/load | Passed |
| Native FFT | Select FFT/display, retrieve 16 finite samples/native coordinates, restore | Passed |

Each touched setting was restored with readback verification. MATH1 returned to
ADD/display OFF; the complete original/final MATH readback (except dynamic title)
also matched. FFT auto-adjusted values were restored and verified separately.
No acquisition RUN/STOP, generator output enable, Bode sweep, screen capture,
mask generation, file overwrite, or error-queue clear was performed.

## Fix and observation

1. **Parallel decode endian readback:** the Markdown guide specifies NEG/POS,
   but the actual `:BUS1:PARallel:ENDian?` response was `LSB`. The getter rejected
   that before any trial write. `decode.py` now preserves LSB/MSB as bit-order
   tokens, retains documented NEG/POS behavior, and returns raw/discrepancy
   metadata. It does not invent a mapping between these meanings. Setter
   acceptance remains the documented tokens. Focused decode tests: **11 passed**.
   Retried only the failed decode cases; both passed with restoration.
2. **Native FFT display automatically adjusts values:** display ON changed
   scale/offset, frequency center/range and peak threshold. The first harness
   flagged this and restored operator/display; root then explicitly restored
   the saved FFT values with successful readback. The corrected harness records
   actual auto-adjustment, reads 16 samples, restores all changed FFT fields with
   display OFF, and restores the original MATH operator/display. This trial
   passed. Tool help/docs now describe the hardware behavior.

The normal app MCP process still held the old decode module after the source
fix: a final direct `get_decode` call reproduced the old endian rejection.
Corrected fresh-process trials passed. Restart `rigol-mho98` once to load this
fix into the normal connector; this is separate from the already resolved
89-tool inventory refresh.

## Four skips and limits

- I2S/IIS, FlexRay and M1553: corresponding AUDio/FLEX/AERO option status and
  validity returned 0; BND also returned 0. These modes were not enabled.
- Mask: not in enabled/stopped prerequisites; no implicit enabling performed.

This validates command/settings paths and sample transfer, not signal-analysis
accuracy. No known external signals were connected, so decoded event correctness,
physical generator output, Bode sweep accuracy and full-depth capture throughput
remain untested. FFT frequency-axis interpretation, WORD encoding and other
previous manual ambiguities remain as recorded in ALL_FEATURES.md.

## Evidence

- [Priority trial](../output/feature-trial/priority-20260926/evidence.json):
  successful trigger/generator/Bode cases, initial decode failures and options.
- [Decode retry](../output/feature-trial/decode-20260926-r2/evidence.json):
  CAN/LIN success with restoration; option skips.
- [Secondary trial](../output/feature-trial/secondary-20260926/evidence.json):
  ten successful roundtrips and the mask prerequisite skip.
- [Initial FFT trial](../output/feature-trial/fft-20260926/evidence.json) and
  [follow-up restoration](../output/feature-trial/fft-20260926/restoration-followup.json):
  observed auto-adjustment and restoration of saved values.
- [Corrected FFT trial](../output/feature-trial/fft-20260926-r2/evidence.json):
  actual 16-point samples, native axis, complete restoration.
