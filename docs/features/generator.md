# MHO98 generator tools

`get_generator`, `set_generator`, and `set_generator_output` control the two
`:SOURce<n>` function/arbitrary waveform generator channels. `channel` is `1`
or `2`.

The implementation checks `:SYSTem:DGSTatus?` before generator access. A zero
reply is retained honestly as `dg_available: false`; it is not silently
converted to a present hardware module. When DG is zero, access is accepted
only if a documented `:SYSTem:OPTion:STATus?` query reports `AFG100`, `AFG50`,
or `BND` installed and the existing source queries return valid functional
readback. Results report `dg_status`, `generator_option_status`, the evidence
source, and a warning describing the DG/license discrepancy. DG zero with
all-negative option status is rejected. The tool does not upload files:
`arbitrary_path` must already be an instrument path beginning with `C:/` or
`D:/`.

## `get_generator`

Input:

```json
{"channel": 1}
```

The result includes effective `output_enabled`, `waveform`, `phase_deg`,
`amplitude_vpp`, `offset_v`, `high_v`, `low_v`, `load`, and modulation state.
It also returns `dg_available` and an `unavailable` list. `frequency_hz` and
`period_s` are `null` and listed unavailable for `DC` and `NOIS`; square duty,
ramp symmetry, arbitrary path, and modulation-specific fields are queried only
when applicable. Waveform replies use `SIN`, `SQU`, `RAMP`, `NOIS`, `DC`,
`ARB`, `EXPR`, `EXPF`, `ECG1`, `GAUS`, `LOR`, `HAV`, or `SINC`.

## `set_generator`

All fields are optional except `channel`; omitted settings are preserved. The
schema fields are:

| Field | Meaning |
|---|---|
| `waveform` | `SIN`, `SQU`, `RAMP`, `NOIS`, `DC`, `ARB`, `EXPR`, `EXPF`, `ECG1`, `GAUS`, `LOR`, `HAV`, `SINC` |
| `frequency_hz` / `period_s` | Select exactly one when changing the carrier timing |
| `phase_deg` | 0–360 degrees |
| `square_duty_percent` | 1–99, only for `SQU` |
| `ramp_symmetry_percent` | 0–100, only for `RAMP` |
| `amplitude_vpp`, `offset_v` | Voltage form |
| `high_v`, `low_v` | Alternative high/low voltage form; do not mix with the amplitude/offset form |
| `load` | `HighZ` or `50ohm` |
| `modulation_enabled` | Boolean modulation state |
| `modulation_type` | `AM`, `FM`, or `PM` |
| `modulation_frequency_hz`, `modulation_waveform` | Internal modulator settings; waveform is `SIN`, `SQU`, `TRI`, `UPR`, `DNR`, or `NOIS` |
| `am_depth_percent` | AM depth, 0–120 |
| `fm_deviation_hz` | FM deviation |
| `pm_deviation_deg` | PM deviation, 0–360 |
| `phase_sync` | `true` performs the documented phase-align command; `false` does nothing |
| `arbitrary_path` | Existing instrument `C:/...` or `D:/...` path, only with `ARB` |

The setter reads the current state and validates the complete requested state
before its first write. It never writes `OUTPut:STATe`; use
`set_generator_output` for that. A successful call returns the final instrument
readback. If a device/option error occurs after a write, the result instead has
`effective_readback` and `partial_failure` with the failed command, commands
already applied, and the error. No reset, retry, or automatic replay is done.

Documented carrier limits enforced before writing:

- Frequency is 2 mHz–100 MHz for sine with DG/AFG100/BND capability, or
  2 mHz–50 MHz when the DG-zero fallback is supported only by AFG50. Square
  and ARB remain at 20 MHz, built-in waveforms at 20 MHz, and ramp at 2 MHz.
  `DC` and `NOIS` have no frequency.
- At frequencies up to 50 MHz, amplitude is 1 mVpp–10 Vpp on `50ohm` and
  2 mVpp–20 Vpp on `HighZ`.
- Above 50 MHz (within the waveform limit), the corresponding ceilings are
  5 Vpp and 10 Vpp. Offset, high/low levels, and load are validated together.
- AM depth is 0–120%; internal AM/FM/PM frequency is 2 mHz–1 MHz; FM deviation
  is 2 mHz–carrier frequency and carrier plus deviation must remain within the
  carrier waveform limit; PM deviation is 0–360 degrees.

## `set_generator_output`

Input is `{"channel": 1, "enabled": true}`. `enabled` must be a real JSON
boolean; strings such as `"true"` and numbers such as `1` are rejected. This
tool changes only `:SOURce<n>:OUTPut:STATe` and returns the effective output
readback.
