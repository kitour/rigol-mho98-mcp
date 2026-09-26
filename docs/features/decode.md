# MHO98 decode tools

`decode.py` exports `get_decode`, `set_decode`, and `read_decode_events`. The
decoder scope is all nine BUS modes in the reference: I2C (`IIC`), SPI,
RS232/UART, Parallel (`PAR`), CAN (including the documented CAN-FD fields),
LIN, I2S (`IIS`), FlexRay (`FLEX`), and M1553.

Common fields are `display`, `format` (`HEX`, `ASCII`, `DEC`, `BIN`), `event`,
`label`, `position` (`-250..250`), and `thresholds`. Omitted fields are read
first and preserved. Every supplied value, including dependent values, is
validated before the first write. Source names are `CHAN1`-`CHAN4` or `D0`-
`D15`; this tool never enables analog or digital inputs automatically.

Existing flat fields remain available for I2C, SPI, and RS232/UART. Added
protocol fields can be passed as named flat fields or in `details`:

```python
set_decode(session, protocol="PARALLEL", details={
    "bus_source": "USER", "clock_source": "D0", "slope": "BOTH",
    "width": 8, "bit": 3, "source": "D3",
    "endian": "POSITIVE", "polarity": "NEGATIVE",
})
set_decode(session, protocol="CAN", details={
    "source": "CHAN1", "signal_type": "CANH", "baud": 500000,
    "sample_point": 80, "fd_baud": 2000000, "fd_sample_point": 75,
})
set_decode(session, protocol="LIN", details={
    "source": "CHAN2", "standard": "V2X", "baud": 19200, "parity": True,
})
set_decode(session, protocol="I2S", details={
    "clock_source": "CHAN1", "data_source": "CHAN3", "ws_source": "CHAN2",
    "alignment": "RJ", "clock_slope": "POSITIVE", "word_width": 16,
    "receive_width": 16, "ws_low": "LEFT", "endian": "MSB",
    "polarity": "POSITIVE",
})
set_decode(session, protocol="FLEXRAY", details={
    "source": "CHAN1", "baud": 10000000, "sample_point": 50,
    "signal_type": "BP", "channel": "A",
})
set_decode(session, protocol="M1553", details={"source": "CHAN4"})
```

Parallel supports the documented preset bus sources, clock source, `POSITIVE`,
`NEGATIVE`, or `BOTH` slope, width, selected bit/source, endian, and polarity.
`width`, `bit`, and per-bit `source` require the final `bus_source` to be
`USER`; writes are ordered as bus, width, bit, source. CAN validates the
documented signal types (`TX`, `RX`, `CANH`, `CANL`, `DIFFERENTIAL`), normal
baud (`10 kbit/s..5 Mbit/s`), sample point (`10..90`), and CAN-FD baud/sample
point (`1..10 Mbit/s`, `10..90`). LIN supports parity, `V1X`, `V2X`, `MIXED`,
and `2.4 kbit/s..20 Mbit/s`. I2S supports all documented clock/data/WS
sources, alignment, clock slope, word/receive widths (`4..32`), WS-low side,
endian, and polarity. FlexRay supports its three baud values, source, sample
point, signal type, and channel A/B. M1553 has its documented source field.

Parallel readback also preserves firmware bit-order responses `LSB` and `MSB`
as-is. These are readback-only compatibility tokens: they are not converted to
`POSITIVE`/`NEGATIVE`, and the setter continues to accept and write only the
documented `POSITIVE`/`NEGATIVE` endian values. When `LSB` or `MSB` is returned,
the result includes `metadata.manual_discrepancy` with the raw response and a
note that the supplied manual documents `NEG`/`POS` instead.

Threshold names are restricted by mode: `PAL`/`PALCLK`, `CAN`/`CANSUB1`,
`LIN`, `I2SClk`/`DATA`/`WS`, `FLEX`, `1553`, the existing serial names, and
`CH1`-`CH4`. Disabled conditional lines are not queried; channel thresholds
are checked against the channel scale/offset when that dependency is
available.

The reference has one unresolved CAN ambiguity: it documents `FDBaud` and
`FDSPoint` as CAN-FD settings but defines no separate CAN/CAN-FD mode or
enable command. The implementation therefore exposes those exact optional
fields and does not invent a mode switch. It also does not claim that a
logic-analyzer input or an instrument protocol option is installed; an
instrument-side option error remains an explicit instrument error.

`read_decode_events` only calls `:BUSn:DATA?`; it does not enable display or
the event table. It returns the protocol line, variable CSV columns/string
rows, full count, bounded rows, and truncation status. An optional new CSV is
created below `session.output_dir` without overwriting an existing file.
