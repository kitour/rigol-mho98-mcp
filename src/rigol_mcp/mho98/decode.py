"""Validated MHO98 BUS decoder controls and event-table reads.

All nine BUS modes documented by the MHO98 command reference are supported:
I2C, SPI, RS232, Parallel, CAN, LIN, I2S, FlexRay, and M1553.  Protocol
specific settings are returned flat for compatibility and may be supplied
through the ``details`` object when a call would otherwise be ambiguous.
"""

from __future__ import annotations

import csv
import io
import math
from numbers import Real
from pathlib import Path
from typing import Any, Mapping
import uuid

from .api import ToolSpec


SUPPORTED_PROTOCOLS = ("I2C", "SPI", "RS232", "PARALLEL", "CAN", "LIN", "IIS", "FLEXRAY", "M1553")
_PROTOCOL_MODES = {
    "I2C": "IIC",
    "IIC": "IIC",
    "SPI": "SPI",
    "RS232": "RS232",
    "UART": "RS232",
    "PARALLEL": "PAR",
    "PAR": "PAR",
    "LIN": "LIN",
    "CAN": "CAN",
    "IIS": "IIS",
    "I2S": "IIS",
    "FLEXRAY": "FLEX",
    "FLEX": "FLEX",
    "M1553": "M1553",
}
_MODE_TO_PROTOCOL = {
    "IIC": "I2C", "SPI": "SPI", "RS232": "RS232", "PAR": "PARALLEL",
    "PARALLEL": "PARALLEL", "LIN": "LIN", "CAN": "CAN", "IIS": "IIS", "I2S": "IIS", "FLEX": "FLEXRAY", "FLEXRAY": "FLEXRAY",
    "M1553": "M1553",
}
_PROTOCOL_ALIASES = {
    "I2C": "I2C", "IIC": "I2C", "SPI": "SPI", "RS232": "RS232", "UART": "RS232",
    "PARALLEL": "PARALLEL", "PAR": "PARALLEL", "LIN": "LIN", "CAN": "CAN",
    "IIS": "IIS", "I2S": "IIS", "FLEXRAY": "FLEXRAY", "FLEX": "FLEXRAY",
    "M1553": "M1553",
}

_I2C_FIELDS = frozenset({"clock_source", "data_source", "exchange", "address_bits"})
_SPI_FIELDS = frozenset(
    {
        "clock_source",
        "clock_slope",
        "miso_source",
        "mosi_source",
        "polarity",
        "miso_polarity",
        "mosi_polarity",
        "data_bits",
        "endian",
        "frame_mode",
        "timeout_s",
        "cs_source",
        "cs_polarity",
    }
)
_RS232_FIELDS = frozenset(
    {
        "tx_source",
        "rx_source",
        "polarity",
        "parity",
        "endian",
        "baud",
        "data_bits",
        "stop_bits",
    }
)
_PARALLEL_FIELDS = frozenset({"bus_source", "clock_source", "slope", "width", "bit", "source", "endian", "polarity"})
_CAN_FIELDS = frozenset({"source", "signal_type", "baud", "fd_baud", "sample_point", "fd_sample_point"})
_LIN_FIELDS = frozenset({"parity", "source", "standard", "baud"})
_IIS_FIELDS = frozenset({"clock_source", "data_source", "ws_source", "alignment", "clock_slope", "word_width", "receive_width", "ws_low", "endian", "polarity"})
_FLEXRAY_FIELDS = frozenset({"baud", "source", "sample_point", "signal_type", "channel"})
_M1553_FIELDS = frozenset({"source"})
_COMMON_FIELDS = frozenset({"display", "format", "event", "label", "position", "thresholds"})
_THRESHOLD_TYPES = {
    "I2C": frozenset({"SCL", "SDA", "CH1", "CH2", "CH3", "CH4"}),
    "SPI": frozenset({"CS", "CLK", "MISO", "MOSI", "CH1", "CH2", "CH3", "CH4"}),
    "RS232": frozenset({"TX", "RX", "CH1", "CH2", "CH3", "CH4"}),
    "PARALLEL": frozenset({"PAL", "PALCLK", "CH1", "CH2", "CH3", "CH4"}),
    "CAN": frozenset({"CAN", "CANSUB1", "CH1", "CH2", "CH3", "CH4"}),
    "LIN": frozenset({"LIN", "CH1", "CH2", "CH3", "CH4"}),
    "IIS": frozenset({"I2SCLK", "DATA", "WS", "CH1", "CH2", "CH3", "CH4"}),
    "FLEXRAY": frozenset({"FLEX", "CH1", "CH2", "CH3", "CH4"}),
    "M1553": frozenset({"1553", "CH1", "CH2", "CH3", "CH4"}),
}


def _bus(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in {1, 2, 3, 4}:
        raise ValueError("bus must be an integer from 1 through 4")
    return value


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    if isinstance(value, Real):
        result = float(value)
    elif isinstance(value, str):
        try:
            result = float(value.strip())
        except ValueError:
            raise ValueError(f"{name} must be a finite number") from None
    else:
        raise ValueError(f"{name} must be a finite number")
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    return result


def _integer(value: Any, name: str, low: int, high: int) -> int:
    result = _finite(value, name)
    if not result.is_integer() or not low <= result <= high:
        raise ValueError(f"{name} must be an integer from {low} through {high}")
    return int(result)


def _one_of_integers(value: Any, name: str, choices: set[int]) -> int:
    result = _integer(value, name, min(choices), max(choices))
    if result not in choices:
        listed = ", ".join(str(item) for item in sorted(choices))
        raise ValueError(f"{name} must be one of {listed}")
    return result


def _bool_input(value: Any, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        text = value.strip().upper()
        if text in {"1", "ON", "TRUE"}:
            return True
        if text in {"0", "OFF", "FALSE"}:
            return False
    raise ValueError(f"{name} must be a boolean")


def _bool_response(value: Any, name: str) -> bool:
    return _bool_input(value, name)


def _enum(value: Any, name: str, aliases: Mapping[str, str]) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError(f"{name} has an unsupported value: {value!r}")
    text = str(value).strip().upper()
    selected = aliases.get(text)
    if selected is None:
        choices = ", ".join(sorted(set(aliases.values())))
        raise ValueError(f"{name} must be one of {choices}")
    return selected


def _protocol(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("protocol must be one of the nine documented BUS modes")
    text = value.strip().upper()
    selected = _PROTOCOL_ALIASES.get(text)
    if selected is None:
        raise ValueError("protocol must be I2C, SPI, RS232/UART, PARALLEL, LIN, CAN, IIS/I2S, FLEXRAY, or M1553")
    return selected


def _mode_protocol(value: Any) -> tuple[str, str]:
    mode = str(value).strip().upper()
    if mode == "ASC":
        mode = "ASCII"
    canonical = _MODE_TO_PROTOCOL.get(mode)
    if canonical is None:
        # Preserve an unexpected instrument response without claiming support.
        canonical = mode or "UNKNOWN"
    if canonical == "FLEX":
        canonical = "FLEXRAY"
    elif canonical == "PAR":
        canonical = "PARALLEL"
    return canonical, mode


def _source(value: Any, name: str, *, allow_off: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be D0-D15, CHAN1-CHAN4" + (", or OFF" if allow_off else ""))
    text = value.strip().upper().replace(" ", "")
    if allow_off and text == "OFF":
        return text
    if text.startswith("CHANNEL"):
        text = "CHAN" + text[7:]
    elif text.startswith("CH") and not text.startswith("CHAN"):
        text = "CHAN" + text[2:]
    if text.startswith("D") and text[1:].isdigit() and 0 <= int(text[1:]) <= 15:
        return text
    if text.startswith("CHAN") and text[4:].isdigit() and 1 <= int(text[4:]) <= 4:
        return text
    raise ValueError(f"{name} must be D0-D15, CHAN1-CHAN4" + (", or OFF" if allow_off else ""))


def _parallel_bus_source(value: Any, name: str = "bus_source") -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be D7D0, D15D8, D15D0, D0D7, D8D15, D0D15, CHAN1-CHAN4, or USER")
    text = value.strip().upper().replace(" ", "")
    if text.startswith("CHANNEL"):
        text = "CHAN" + text[7:]
    elif text.startswith("CH") and not text.startswith("CHAN"):
        text = "CHAN" + text[2:]
    if text in {"D7D0", "D15D8", "D15D0", "D0D7", "D8D15", "D0D15", "USER"}:
        return text
    if text.startswith("CHAN") and text[4:].isdigit() and 1 <= int(text[4:]) <= 4:
        return text
    raise ValueError(f"{name} must be D7D0, D15D8, D15D0, D0D7, D8D15, D0D15, CHAN1-CHAN4, or USER")


def _threshold_type(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("threshold source names must be strings")
    text = value.strip().upper().replace("CHANNEL", "CH").replace(" ", "")
    aliases = {"CANSUB1": "CANSUB1", "I2SCLK": "I2SCLK", "1553": "1553", "PAL": "PAL", "PALCLK": "PALCLK", "CAN": "CAN", "LIN": "LIN", "FLEX": "FLEX", "DATA": "DATA", "WS": "WS"}
    if text in {"CH1", "CH2", "CH3", "CH4", "SCL", "SDA", "CS", "CLK", "MISO", "MOSI", "TX", "RX"}:
        return text
    if text in aliases:
        return aliases[text]
    raise ValueError(f"unsupported threshold source: {value!r}")


def _number_string(value: float) -> str:
    return format(value, ".15g")


def _common(session: Any, bus: int) -> dict[str, Any]:
    prefix = f":BUS{bus}:"
    raw_format = str(session.query(prefix + "FORMat?")).strip().upper()
    formats = {"HEX": "HEX", "ASC": "ASCII", "ASCII": "ASCII", "DEC": "DEC", "BIN": "BIN"}
    if raw_format not in formats:
        raise ValueError(f"invalid format response from MHO98: {raw_format!r}")
    return {
        "display": _bool_response(session.query(prefix + "DISPlay?"), "display"),
        "format": formats[raw_format],
        "event": _bool_response(session.query(prefix + "EVENt?"), "event"),
        "label": _bool_response(session.query(prefix + "LABel?"), "label"),
        "position": _integer(session.query(prefix + "POSition?"), "position", -250, 250),
    }


def _query_i2c(session: Any, bus: int) -> dict[str, Any]:
    prefix = f":BUS{bus}:IIC:"
    return {
        "clock_source": _source(session.query(prefix + "SCLK:SOURce?"), "clock_source"),
        "data_source": _source(session.query(prefix + "SDA:SOURce?"), "data_source"),
        "exchange": _bool_response(session.query(prefix + "EXCHange?"), "exchange"),
        "address_bits": _one_of_integers(session.query(prefix + "ADDBits?"), "address_bits", {7, 8, 10}),
    }


def _query_spi(session: Any, bus: int) -> dict[str, Any]:
    prefix = f":BUS{bus}:SPI:"
    slope = _enum(session.query(prefix + "SCLK:SLOPe?"), "clock_slope", {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE"})
    frame_mode = _enum(session.query(prefix + "MODE?"), "frame_mode", {"CS": "CS", "TIMEOUT": "TIMEOUT", "TIM": "TIMEOUT"})
    return {
        "clock_source": _source(session.query(prefix + "SCLK:SOURce?"), "clock_source"),
        "clock_slope": slope,
        "miso_source": _source(session.query(prefix + "MISO:SOURce?"), "miso_source", allow_off=True),
        "mosi_source": _source(session.query(prefix + "MOSI:SOURce?"), "mosi_source", allow_off=True),
        "polarity": _enum(session.query(prefix + "POLarity?"), "polarity", {"HIGH": "HIGH", "LOW": "LOW"}),
        "miso_polarity": _enum(session.query(prefix + "MISO:POLarity?"), "miso_polarity", {"HIGH": "HIGH", "LOW": "LOW"}),
        "mosi_polarity": _enum(session.query(prefix + "MOSI:POLarity?"), "mosi_polarity", {"HIGH": "HIGH", "LOW": "LOW"}),
        "data_bits": _integer(session.query(prefix + "DBITs?"), "data_bits", 4, 32),
        "endian": _enum(session.query(prefix + "ENDian?"), "endian", {"MSB": "MSB", "LSB": "LSB"}),
        "frame_mode": frame_mode,
        "timeout_s": _finite(session.query(prefix + "TIMeout:TIME?"), "timeout_s"),
        "cs_source": _source(session.query(prefix + "SS:SOURce?"), "cs_source"),
        "cs_polarity": _enum(session.query(prefix + "SS:POLarity?"), "cs_polarity", {"HIGH": "HIGH", "LOW": "LOW"}),
    }


def _query_rs232(session: Any, bus: int) -> dict[str, Any]:
    prefix = f":BUS{bus}:RS232:"
    return {
        "tx_source": _source(session.query(prefix + "TX?"), "tx_source", allow_off=True),
        "rx_source": _source(session.query(prefix + "RX?"), "rx_source", allow_off=True),
        "polarity": _enum(session.query(prefix + "POLarity?"), "polarity", {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE"}),
        "parity": _enum(session.query(prefix + "PARity?"), "parity", {"NONE": "NONE", "ODD": "ODD", "EVEN": "EVEN"}),
        "endian": _enum(session.query(prefix + "ENDian?"), "endian", {"MSB": "MSB", "LSB": "LSB"}),
        "baud": _integer(session.query(prefix + "BAUD?"), "baud", 1, 20_000_000),
        "data_bits": _enum(session.query(prefix + "DBITs?"), "data_bits", {str(n): str(n) for n in range(5, 10)}),
        "stop_bits": _enum(session.query(prefix + "SBITs?"), "stop_bits", {"1": "1", "1.0": "1", "1.5": "1.5", "2": "2", "2.0": "2"}),
    }


def _query_parallel(
    session: Any,
    bus: int,
    *,
    readback_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prefix = f":BUS{bus}:PARallel:"
    raw_endian = session.query(prefix + "ENDian?")
    endian_token = str(raw_endian).strip().upper()
    endian = _enum(
        raw_endian,
        "endian",
        {
            "POS": "POSITIVE",
            "POSITIVE": "POSITIVE",
            "NEG": "NEGATIVE",
            "NEGATIVE": "NEGATIVE",
            # Firmware 00.01.00 reports parallel bit order rather than the
            # manual's polarity-like POS/NEG tokens. Keep these raw tokens;
            # they are not synonyms for POSITIVE or NEGATIVE.
            "LSB": "LSB",
            "MSB": "MSB",
        },
    )
    if readback_metadata is not None and endian_token in {"LSB", "MSB"}:
        readback_metadata["manual_discrepancy"] = {
            "field": "endian",
            "raw_response": str(raw_endian).strip(),
            "message": (
                "The supplied parallel-bus manual documents NEG/POS, but the "
                f"instrument returned {str(raw_endian).strip()!r}; the raw "
                "bit-order token is preserved without conversion."
            ),
        }
    return {
        "bus_source": _parallel_bus_source(session.query(prefix + "BUS?")),
        "clock_source": _source(session.query(prefix + "CLK?"), "clock_source", allow_off=True),
        "slope": _enum(session.query(prefix + "SLOPe?"), "slope", {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE", "BOTH": "BOTH"}),
        "width": _integer(session.query(prefix + "WIDTh?"), "width", 1, 16),
        "bit": _integer(session.query(prefix + "BITX?"), "bit", 0, 15),
        "source": _source(session.query(prefix + "SOURce?"), "source"),
        "endian": endian,
        "polarity": _enum(session.query(prefix + "POLarity?"), "polarity", {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE"}),
    }


def _query_can(session: Any, bus: int) -> dict[str, Any]:
    prefix = f":BUS{bus}:CAN:"
    return {
        "source": _source(session.query(prefix + "SOURce?"), "source"),
        "signal_type": _enum(session.query(prefix + "STYPe?"), "signal_type", {"TX": "TX", "RX": "RX", "CANH": "CANH", "CANL": "CANL", "DIFF": "DIFFERENTIAL", "DIFFERENTIAL": "DIFFERENTIAL"}),
        "baud": _integer(session.query(prefix + "BAUD?"), "baud", 10_000, 5_000_000),
        "fd_baud": _integer(session.query(prefix + "FDBaud?"), "fd_baud", 1_000_000, 10_000_000),
        "sample_point": _integer(session.query(prefix + "SPOint?"), "sample_point", 10, 90),
        "fd_sample_point": _integer(session.query(prefix + "FDSPoint?"), "fd_sample_point", 10, 90),
    }


def _query_lin(session: Any, bus: int) -> dict[str, Any]:
    prefix = f":BUS{bus}:LIN:"
    return {
        "parity": _bool_response(session.query(prefix + "PARity?"), "parity"),
        "source": _source(session.query(prefix + "SOURce?"), "source"),
        "standard": _enum(session.query(prefix + "STANdard?"), "standard", {"V1X": "V1X", "V2X": "V2X", "MIX": "MIXED", "MIXED": "MIXED"}),
        "baud": _integer(session.query(prefix + "BAUD?"), "baud", 2_400, 20_000_000),
    }


def _query_iis(session: Any, bus: int) -> dict[str, Any]:
    prefix = f":BUS{bus}:IIS:"
    return {
        "clock_source": _source(session.query(prefix + "SOURce:CLOCk?"), "clock_source"),
        "data_source": _source(session.query(prefix + "SOURce:DATA?"), "data_source"),
        "ws_source": _source(session.query(prefix + "SOURce:WSELect?"), "ws_source"),
        "alignment": _enum(session.query(prefix + "ALIGnment?"), "alignment", {"IIS": "IIS", "RJ": "RJ", "LJ": "LJ"}),
        "clock_slope": _enum(session.query(prefix + "CLOCk:SLOPe?"), "clock_slope", {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE"}),
        "word_width": _integer(session.query(prefix + "RWIDth?"), "word_width", 4, 32),
        "receive_width": _integer(session.query(prefix + "RECewidth?"), "receive_width", 4, 32),
        "ws_low": _enum(session.query(prefix + "WSLow?"), "ws_low", {"LEFT": "LEFT", "RIGH": "RIGHT", "RIGHT": "RIGHT"}),
        "endian": _enum(session.query(prefix + "ENDian?"), "endian", {"MSB": "MSB", "LSB": "LSB", "ON": "MSB", "OFF": "LSB", "1": "MSB", "0": "LSB"}),
        "polarity": _enum(session.query(prefix + "POLarity?"), "polarity", {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE", "ON": "POSITIVE", "OFF": "NEGATIVE", "1": "POSITIVE", "0": "NEGATIVE"}),
    }


def _query_flexray(session: Any, bus: int) -> dict[str, Any]:
    prefix = f":BUS{bus}:FLEXray:"
    return {
        "baud": _enum(session.query(prefix + "BAUD?"), "baud", {"2500000": "2500000", "5000000": "5000000", "10000000": "10000000"}),
        "source": _source(session.query(prefix + "SOURce?"), "source"),
        "sample_point": _integer(session.query(prefix + "SPOint?"), "sample_point", 10, 90),
        "signal_type": _enum(session.query(prefix + "STYPe?"), "signal_type", {"BP": "BP", "BM": "BM", "RT": "RT"}),
        "channel": _enum(session.query(prefix + "CHANnel?"), "channel", {"A": "A", "B": "B"}),
    }


def _query_m1553(session: Any, bus: int) -> dict[str, Any]:
    return {"source": _source(session.query(f":BUS{bus}:M1553:SOURce?"), "source")}


def _query_protocol(
    session: Any,
    bus: int,
    protocol: str,
    *,
    readback_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if protocol == "I2C":
        return _query_i2c(session, bus)
    if protocol == "SPI":
        return _query_spi(session, bus)
    if protocol == "RS232":
        return _query_rs232(session, bus)
    if protocol == "PARALLEL":
        return _query_parallel(session, bus, readback_metadata=readback_metadata)
    if protocol == "CAN":
        return _query_can(session, bus)
    if protocol == "LIN":
        return _query_lin(session, bus)
    if protocol == "IIS":
        return _query_iis(session, bus)
    if protocol == "FLEXRAY":
        return _query_flexray(session, bus)
    if protocol == "M1553":
        return _query_m1553(session, bus)
    return {}


def _query_thresholds(session: Any, bus: int, protocol: str, settings: Mapping[str, Any]) -> dict[str, float]:
    """Read applicable threshold controls without querying disabled lines."""

    line_fields = {
        "I2C": {"SCL": "clock_source", "SDA": "data_source"},
        "SPI": {"CS": "cs_source", "CLK": "clock_source", "MISO": "miso_source", "MOSI": "mosi_source"},
        "RS232": {"TX": "tx_source", "RX": "rx_source"},
        "PARALLEL": {"PAL": "bus_source", "PALCLK": "clock_source"},
        "CAN": {"CAN": "source", "CANSUB1": "source"},
        "LIN": {"LIN": "source"},
        "IIS": {"I2SCLK": "clock_source", "DATA": "data_source", "WS": "ws_source"},
        "FLEXRAY": {"FLEX": "source"},
        "M1553": {"1553": "source"},
    }
    sources = ["CH1", "CH2", "CH3", "CH4"]
    for source, field in line_fields[protocol].items():
        if settings.get(field) != "OFF":
            sources.append(source)
    thresholds: dict[str, float] = {}
    for source in sources:
        thresholds[source] = _finite(
            session.query(f":BUS{bus}:THReshold? {source}"),
            f"thresholds.{source}",
        )
    return thresholds


def _decode_readback(session: Any, bus: int) -> dict[str, Any]:
    protocol, mode = _mode_protocol(session.query(f":BUS{bus}:MODE?"))
    common = _common(session, bus)
    result: dict[str, Any] = {"bus": bus, "protocol": protocol, "mode": mode, **common}
    if protocol not in SUPPORTED_PROTOCOLS:
        result.update(
            {
                "supported": False,
                "scope": {
                    "supported_protocols": list(SUPPORTED_PROTOCOLS),
                    "reason": "This documented BUS protocol is outside the decode tool scope; no protocol settings are claimed.",
                },
            }
        )
        return result
    result["supported"] = True
    readback_metadata: dict[str, Any] = {}
    settings = _query_protocol(session, bus, protocol, readback_metadata=readback_metadata)
    result.update(settings)
    if protocol not in {"I2C", "SPI", "RS232"}:
        result["details"] = dict(settings)
    if readback_metadata:
        result["metadata"] = readback_metadata
    result["thresholds"] = _query_thresholds(session, bus, protocol, settings)
    return result


def get_decode(session: Any, bus: int = 1) -> dict[str, Any]:
    """Return common BUS settings and the actual supported protocol readback."""

    return _decode_readback(session, _bus(bus))


def _validate_thresholds(value: Any, protocol: str | None) -> dict[str, float]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("thresholds must be an object mapping source names to numbers")
    if protocol not in SUPPORTED_PROTOCOLS:
        raise ValueError("thresholds require a supported selected protocol")
    result: dict[str, float] = {}
    allowed = _THRESHOLD_TYPES[protocol]
    for source, threshold in value.items():
        selected = _threshold_type(source)
        if selected not in allowed:
            raise ValueError(f"threshold {selected} is irrelevant for {protocol}")
        result[selected] = _finite(threshold, f"thresholds.{selected}")
    return result


def _source_for_threshold(protocol: str, settings: Mapping[str, Any], source: str) -> str | None:
    fields = {
        "I2C": {"SCL": "clock_source", "SDA": "data_source"},
        "SPI": {"CS": "cs_source", "CLK": "clock_source", "MISO": "miso_source", "MOSI": "mosi_source"},
        "RS232": {"TX": "tx_source", "RX": "rx_source"},
        "PARALLEL": {"PAL": "bus_source", "PALCLK": "clock_source"},
        "CAN": {"CAN": "source", "CANSUB1": "source"},
        "LIN": {"LIN": "source"},
        "IIS": {"I2SCLK": "clock_source", "DATA": "data_source", "WS": "ws_source"},
        "FLEXRAY": {"FLEX": "source"},
        "M1553": {"1553": "source"},
    }
    field = fields[protocol].get(source)
    if field is None:
        return "CHAN" + source[2:] if source.startswith("CH") else source
    return str(settings[field])


def _validate_threshold_ranges(session: Any, bus: int, protocol: str, thresholds: Mapping[str, float], settings: Mapping[str, Any]) -> None:
    for source, threshold in thresholds.items():
        selected_source = _source_for_threshold(protocol, settings, source)
        if selected_source == "OFF":
            if source in {"RX", "PALCLK"}:
                raise ValueError(f"{source} threshold requires an enabled source")
            continue
        if selected_source and selected_source.startswith("CHAN"):
            channel = selected_source[4:]
            scale = _finite(session.query(f":CHANnel{channel}:SCALe?"), f"CHAN{channel} scale")
            offset = _finite(session.query(f":CHANnel{channel}:OFFSet?"), f"CHAN{channel} offset")
            if scale <= 0:
                raise ValueError(f"invalid CHAN{channel} vertical scale from MHO98")
            low = -5.0 * scale - offset
            high = 5.0 * scale - offset
            if not low <= threshold <= high:
                raise ValueError(
                    f"thresholds.{source} {threshold:g} is outside the documented range {low:g}..{high:g}"
                )


def _validate_field_relevance(protocol: str, submitted: Mapping[str, Any]) -> None:
    protocol_fields = {
        "I2C": _I2C_FIELDS, "SPI": _SPI_FIELDS, "RS232": _RS232_FIELDS,
        "PARALLEL": _PARALLEL_FIELDS, "CAN": _CAN_FIELDS, "LIN": _LIN_FIELDS,
        "IIS": _IIS_FIELDS, "FLEXRAY": _FLEXRAY_FIELDS, "M1553": _M1553_FIELDS,
    }
    selected = protocol_fields.get(protocol)
    if selected is None:
        for field in submitted:
            if field not in _COMMON_FIELDS:
                raise ValueError(f"{field} cannot be configured for unsupported protocol {protocol}")
        return
    for field in submitted:
        if field not in selected and field not in _COMMON_FIELDS:
            raise ValueError(f"{field} is irrelevant for {protocol}")


def _validate_protocol_values(protocol: str, values: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if protocol == "I2C":
        if values.get("clock_source") is not None:
            result["clock_source"] = _source(values["clock_source"], "clock_source")
        if values.get("data_source") is not None:
            result["data_source"] = _source(values["data_source"], "data_source")
        if values.get("exchange") is not None:
            result["exchange"] = _bool_input(values["exchange"], "exchange")
        if values.get("address_bits") is not None:
            result["address_bits"] = _one_of_integers(values["address_bits"], "address_bits", {7, 8, 10})
    elif protocol == "SPI":
        if values.get("clock_source") is not None:
            result["clock_source"] = _source(values["clock_source"], "clock_source")
        if values.get("clock_slope") is not None:
            result["clock_slope"] = _enum(values["clock_slope"], "clock_slope", {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE"})
        for field in ("miso_source", "mosi_source"):
            if values.get(field) is not None:
                result[field] = _source(values[field], field, allow_off=True)
        for field in ("polarity", "miso_polarity", "mosi_polarity", "cs_polarity"):
            if values.get(field) is not None:
                result[field] = _enum(values[field], field, {"HIGH": "HIGH", "LOW": "LOW"})
        if values.get("data_bits") is not None:
            result["data_bits"] = _integer(values["data_bits"], "data_bits", 4, 32)
        if values.get("endian") is not None:
            result["endian"] = _enum(values["endian"], "endian", {"MSB": "MSB", "LSB": "LSB"})
        if values.get("frame_mode") is not None:
            result["frame_mode"] = _enum(values["frame_mode"], "frame_mode", {"CS": "CS", "TIMEOUT": "TIMEOUT", "TIM": "TIMEOUT"})
        if values.get("timeout_s") is not None:
            result["timeout_s"] = _finite(values["timeout_s"], "timeout_s")
            if result["timeout_s"] < 8e-9 or result["timeout_s"] > 10:
                raise ValueError("timeout_s must be from 8 ns through 10 s")
        if values.get("cs_source") is not None:
            result["cs_source"] = _source(values["cs_source"], "cs_source")
    elif protocol == "RS232":
        for field in ("tx_source", "rx_source"):
            if values.get(field) is not None:
                result[field] = _source(values[field], field, allow_off=True)
        if values.get("polarity") is not None:
            result["polarity"] = _enum(values["polarity"], "polarity", {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE"})
        if values.get("parity") is not None:
            result["parity"] = _enum(values["parity"], "parity", {"NONE": "NONE", "ODD": "ODD", "EVEN": "EVEN"})
        if values.get("endian") is not None:
            result["endian"] = _enum(values["endian"], "endian", {"MSB": "MSB", "LSB": "LSB"})
        if values.get("baud") is not None:
            result["baud"] = _integer(values["baud"], "baud", 1, 20_000_000)
        if values.get("data_bits") is not None:
            result["data_bits"] = _enum(values["data_bits"], "data_bits", {str(n): str(n) for n in range(5, 10)})
        if values.get("stop_bits") is not None:
            result["stop_bits"] = _enum(values["stop_bits"], "stop_bits", {"1": "1", "1.0": "1", "1.5": "1.5", "2": "2", "2.0": "2"})
    elif protocol == "PARALLEL":
        if values.get("bus_source") is not None:
            result["bus_source"] = _parallel_bus_source(values["bus_source"])
        if values.get("clock_source") is not None:
            result["clock_source"] = _source(values["clock_source"], "clock_source", allow_off=True)
        if values.get("slope") is not None:
            result["slope"] = _enum(values["slope"], "slope", {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE", "BOTH": "BOTH"})
        if values.get("width") is not None:
            result["width"] = _integer(values["width"], "width", 1, 16)
        if values.get("bit") is not None:
            result["bit"] = _integer(values["bit"], "bit", 0, 15)
        if values.get("source") is not None:
            result["source"] = _source(values["source"], "source")
        for field in ("endian", "polarity"):
            if values.get(field) is not None:
                result[field] = _enum(values[field], field, {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE"})
    elif protocol == "CAN":
        if values.get("source") is not None:
            result["source"] = _source(values["source"], "source")
        if values.get("signal_type") is not None:
            result["signal_type"] = _enum(values["signal_type"], "signal_type", {"TX": "TX", "RX": "RX", "CANH": "CANH", "CANL": "CANL", "DIFF": "DIFFERENTIAL", "DIFFERENTIAL": "DIFFERENTIAL"})
        if values.get("baud") is not None:
            result["baud"] = _integer(values["baud"], "baud", 10_000, 5_000_000)
        if values.get("fd_baud") is not None:
            result["fd_baud"] = _integer(values["fd_baud"], "fd_baud", 1_000_000, 10_000_000)
        for field in ("sample_point", "fd_sample_point"):
            if values.get(field) is not None:
                result[field] = _integer(values[field], field, 10, 90)
    elif protocol == "LIN":
        if values.get("parity") is not None:
            result["parity"] = _bool_input(values["parity"], "parity")
        if values.get("source") is not None:
            result["source"] = _source(values["source"], "source")
        if values.get("standard") is not None:
            result["standard"] = _enum(values["standard"], "standard", {"V1X": "V1X", "V2X": "V2X", "MIX": "MIXED", "MIXED": "MIXED"})
        if values.get("baud") is not None:
            result["baud"] = _integer(values["baud"], "baud", 2_400, 20_000_000)
    elif protocol == "IIS":
        for field in ("clock_source", "data_source", "ws_source"):
            if values.get(field) is not None:
                result[field] = _source(values[field], field)
        if values.get("alignment") is not None:
            result["alignment"] = _enum(values["alignment"], "alignment", {"IIS": "IIS", "RJ": "RJ", "LJ": "LJ"})
        if values.get("clock_slope") is not None:
            result["clock_slope"] = _enum(values["clock_slope"], "clock_slope", {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE"})
        for field in ("word_width", "receive_width"):
            if values.get(field) is not None:
                result[field] = _integer(values[field], field, 4, 32)
        if values.get("ws_low") is not None:
            result["ws_low"] = _enum(values["ws_low"], "ws_low", {"LEFT": "LEFT", "RIGH": "RIGHT", "RIGHT": "RIGHT"})
        if values.get("endian") is not None:
            result["endian"] = _enum(values["endian"], "endian", {"MSB": "MSB", "LSB": "LSB", "ON": "MSB", "OFF": "LSB", "1": "MSB", "0": "LSB"})
        if values.get("polarity") is not None:
            result["polarity"] = _enum(values["polarity"], "polarity", {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE", "ON": "POSITIVE", "OFF": "NEGATIVE", "1": "POSITIVE", "0": "NEGATIVE"})
    elif protocol == "FLEXRAY":
        if values.get("baud") is not None:
            result["baud"] = _enum(values["baud"], "baud", {"2500000": "2500000", "5000000": "5000000", "10000000": "10000000"})
        if values.get("source") is not None:
            result["source"] = _source(values["source"], "source")
        if values.get("sample_point") is not None:
            result["sample_point"] = _integer(values["sample_point"], "sample_point", 10, 90)
        if values.get("signal_type") is not None:
            result["signal_type"] = _enum(values["signal_type"], "signal_type", {"BP": "BP", "BM": "BM", "RT": "RT"})
        if values.get("channel") is not None:
            result["channel"] = _enum(values["channel"], "channel", {"A": "A", "B": "B"})
    elif protocol == "M1553":
        if values.get("source") is not None:
            result["source"] = _source(values["source"], "source")
    return result


_DETAIL_ALIASES = {
    "PARALLEL": {"bus_source": "bus_source", "bus": "bus_source", "clock_source": "clock_source", "clk_source": "clock_source", "slope": "slope", "width": "width", "bit": "bit", "source": "source", "bit_source": "source", "endian": "endian", "polarity": "polarity"},
    "CAN": {"source": "source", "signal_type": "signal_type", "type": "signal_type", "baud": "baud", "fd_baud": "fd_baud", "sample_point": "sample_point", "fd_sample_point": "fd_sample_point"},
    "LIN": {"parity": "parity", "source": "source", "standard": "standard", "version": "standard", "baud": "baud"},
    "IIS": {"clock_source": "clock_source", "data_source": "data_source", "ws_source": "ws_source", "wselect_source": "ws_source", "alignment": "alignment", "clock_slope": "clock_slope", "word_width": "word_width", "receive_width": "receive_width", "ws_low": "ws_low", "endian": "endian", "polarity": "polarity"},
    "FLEXRAY": {"baud": "baud", "source": "source", "sample_point": "sample_point", "signal_type": "signal_type", "type": "signal_type", "channel": "channel"},
    "M1553": {"source": "source"},
}


def _detail_values(protocol: str, details: Any) -> dict[str, Any]:
    if details is None:
        return {}
    if not isinstance(details, Mapping):
        raise ValueError("details must be an object containing named protocol fields")
    aliases = _DETAIL_ALIASES.get(protocol, {})
    result: dict[str, Any] = {}
    for key, value in details.items():
        if not isinstance(key, str):
            raise ValueError("details field names must be strings")
        canonical = aliases.get(key.strip().lower())
        if canonical is None:
            raise ValueError(f"{key} is not a documented field for {protocol}")
        if canonical in result:
            raise ValueError(f"details contains duplicate aliases for {canonical}")
        result[canonical] = value
    return result


def set_decode(
    session: Any,
    bus: int = 1,
    protocol: Any = None,
    *,
    display: Any = None,
    format: Any = None,
    event: Any = None,
    label: Any = None,
    position: Any = None,
    thresholds: Any = None,
    clock_source: Any = None,
    data_source: Any = None,
    exchange: Any = None,
    address_bits: Any = None,
    clock_slope: Any = None,
    miso_source: Any = None,
    mosi_source: Any = None,
    polarity: Any = None,
    miso_polarity: Any = None,
    mosi_polarity: Any = None,
    data_bits: Any = None,
    endian: Any = None,
    frame_mode: Any = None,
    timeout_s: Any = None,
    cs_source: Any = None,
    cs_polarity: Any = None,
    tx_source: Any = None,
    rx_source: Any = None,
    parity: Any = None,
    baud: Any = None,
    baud_rate: Any = None,
    stop_bits: Any = None,
    decode_mode: Any = None,
    spi_mode: Any = None,
    source: Any = None,
    bus_source: Any = None,
    slope: Any = None,
    width: Any = None,
    bit: Any = None,
    signal_type: Any = None,
    sample_point: Any = None,
    fd_baud: Any = None,
    fd_sample_point: Any = None,
    standard: Any = None,
    ws_source: Any = None,
    alignment: Any = None,
    word_width: Any = None,
    receive_width: Any = None,
    ws_low: Any = None,
    channel: Any = None,
    details: Any = None,
) -> dict[str, Any]:
    """Send only explicitly requested decoder fields.

    A single BUS mode selector query is used only when an omitted protocol is
    required to route protocol-specific fields or thresholds.  No BUS snapshot,
    source readback, or threshold preflight is performed.
    """

    selected_bus = _bus(bus)
    selected_protocol = None if protocol is None else _protocol(protocol)
    if selected_protocol == "IIC":
        selected_protocol = "I2C"
    if baud is not None and baud_rate is not None:
        raise ValueError("provide only one of baud and baud_rate")
    if baud is None:
        baud = baud_rate
    if decode_mode is not None and spi_mode is not None:
        raise ValueError("provide only one of decode_mode and spi_mode")
    if frame_mode is None:
        frame_mode = decode_mode if decode_mode is not None else spi_mode

    values = {
        "display": display,
        "format": format,
        "event": event,
        "label": label,
        "position": position,
        "thresholds": thresholds,
        "clock_source": clock_source,
        "data_source": data_source,
        "exchange": exchange,
        "address_bits": address_bits,
        "clock_slope": clock_slope,
        "miso_source": miso_source,
        "mosi_source": mosi_source,
        "polarity": polarity,
        "miso_polarity": miso_polarity,
        "mosi_polarity": mosi_polarity,
        "data_bits": data_bits,
        "endian": endian,
        "frame_mode": frame_mode,
        "timeout_s": timeout_s,
        "cs_source": cs_source,
        "cs_polarity": cs_polarity,
        "tx_source": tx_source,
        "rx_source": rx_source,
        "parity": parity,
        "baud": baud,
        "stop_bits": stop_bits,
        "source": source,
        "bus_source": bus_source,
        "slope": slope,
        "width": width,
        "bit": bit,
        "signal_type": signal_type,
        "sample_point": sample_point,
        "fd_baud": fd_baud,
        "fd_sample_point": fd_sample_point,
        "standard": standard,
        "ws_source": ws_source,
        "alignment": alignment,
        "word_width": word_width,
        "receive_width": receive_width,
        "ws_low": ws_low,
        "channel": channel,
    }
    if details is not None and not isinstance(details, Mapping):
        raise ValueError("details must be an object containing named protocol fields")
    if selected_protocol is None and details:
        # Details are protocol-routed; this is the same single selector query
        # permitted for omitted flat protocol fields.
        raw_mode = str(session.query(f":BUS{selected_bus}:MODE?")).strip().upper()
        selected_protocol, _selected_mode = _mode_protocol(raw_mode)
    detail_requested = _detail_values(selected_protocol, details)
    for key, value in detail_requested.items():
        if values.get(key) is not None:
            raise ValueError(f"provide {key} either as a flat field or in details, not both")
        values[key] = value
    submitted = {key for key, value in values.items() if value is not None}
    if selected_protocol is None and ((submitted - _COMMON_FIELDS) or thresholds is not None):
        # MODE? is a routing selector, not a configuration snapshot.  It is
        # intentionally the only query made by this setter when protocol is
        # omitted.
        raw_mode = str(session.query(f":BUS{selected_bus}:MODE?")).strip().upper()
        selected_protocol, _selected_mode = _mode_protocol(raw_mode)
    if selected_protocol is not None:
        _validate_field_relevance(selected_protocol, submitted)

    # Validate every scalar and enum before reading for dependent checks or writing.
    common_requested: dict[str, Any] = {}
    if display is not None:
        common_requested["display"] = _bool_input(display, "display")
    if format is not None:
        common_requested["format"] = _enum(format, "format", {"HEX": "HEX", "ASCII": "ASCII", "ASC": "ASCII", "DEC": "DEC", "BIN": "BIN"})
    if event is not None:
        common_requested["event"] = _bool_input(event, "event")
    if label is not None:
        common_requested["label"] = _bool_input(label, "label")
    if position is not None:
        common_requested["position"] = _integer(position, "position", -250, 250)
    protocol_requested = _validate_protocol_values(selected_protocol, values) if selected_protocol in SUPPORTED_PROTOCOLS else {}
    thresholds_requested = _validate_thresholds(thresholds, selected_protocol) if thresholds is not None else {}

    if selected_protocol == "SPI" and {protocol_requested.get("miso_source"), protocol_requested.get("mosi_source")} == {"OFF"}:
        raise ValueError("SPI MISO and MOSI cannot both be explicitly OFF")
    if selected_protocol == "RS232" and {protocol_requested.get("tx_source"), protocol_requested.get("rx_source")} == {"OFF"}:
        raise ValueError("RS232 TX and RX cannot both be explicitly OFF")
    if selected_protocol == "PARALLEL" and "bit" in protocol_requested and "width" in protocol_requested and protocol_requested["bit"] >= protocol_requested["width"]:
        raise ValueError("bit must be less than the explicitly requested parallel width")

    writes: list[str] = []
    if selected_protocol in _PROTOCOL_MODES:
        target_mode = _PROTOCOL_MODES[selected_protocol]
        writes.append(f":BUS{selected_bus}:MODE {target_mode}")

    if "display" in common_requested:
        writes.append(f":BUS{selected_bus}:DISPlay {int(common_requested['display'])}")
    if "format" in common_requested:
        token = "ASCii" if common_requested["format"] == "ASCII" else common_requested["format"]
        writes.append(f":BUS{selected_bus}:FORMat {token}")
    if "position" in common_requested:
        writes.append(f":BUS{selected_bus}:POSition {common_requested['position']}")
    if "event" in common_requested:
        writes.append(f":BUS{selected_bus}:EVENt {int(common_requested['event'])}")
    if "label" in common_requested:
        writes.append(f":BUS{selected_bus}:LABel {int(common_requested['label'])}")

    if selected_protocol not in SUPPORTED_PROTOCOLS:
        # Common commands are still sent when the explicit/selected mode is not
        # one this module has protocol field mappings for.
        for command in writes:
            session.write(command)
        return {"sent": bool(writes), "verified": False, "commands": writes, "bus": selected_bus, "requested": dict(common_requested), **common_requested}

    class _Writer:
        def write(self, command: str) -> None:
            writes.append(command)

    writer = _Writer()
    if selected_protocol == "I2C":
        _write_protocol_i2c(writer, selected_bus, {}, protocol_requested)
    elif selected_protocol == "SPI":
        _write_protocol_spi(writer, selected_bus, {}, protocol_requested, {})
    elif selected_protocol == "RS232":
        _write_protocol_rs232(writer, selected_bus, {}, protocol_requested, {})
    elif selected_protocol == "PARALLEL":
        _write_protocol_parallel(writer, selected_bus, {}, protocol_requested)
    elif selected_protocol == "CAN":
        _write_protocol_can(writer, selected_bus, {}, protocol_requested)
    elif selected_protocol == "LIN":
        _write_protocol_lin(writer, selected_bus, {}, protocol_requested)
    elif selected_protocol == "IIS":
        _write_protocol_iis(writer, selected_bus, {}, protocol_requested)
    elif selected_protocol == "FLEXRAY":
        _write_protocol_flexray(writer, selected_bus, {}, protocol_requested)
    elif selected_protocol == "M1553":
        _write_protocol_m1553(writer, selected_bus, {}, protocol_requested)
    for source, threshold in thresholds_requested.items():
        writes.append(f":BUS{selected_bus}:THReshold {_number_string(threshold)},{source}")

    for command in writes:
        session.write(command)
    requested = {**common_requested, **protocol_requested}
    if thresholds_requested:
        requested["thresholds"] = thresholds_requested
    return {"sent": bool(writes), "verified": False, "commands": writes, "bus": selected_bus, "protocol": selected_protocol, "requested": requested, **requested}


def _write_protocol_i2c(session: Any, bus: int, current: Mapping[str, Any], requested: Mapping[str, Any]) -> None:
    prefix = f":BUS{bus}:IIC:"
    for field, command in (("clock_source", "SCLK:SOURce"), ("data_source", "SDA:SOURce"), ("exchange", "EXCHange"), ("address_bits", "ADDBits")):
        if field in requested:
            value = int(requested[field]) if isinstance(requested[field], bool) else requested[field]
            session.write(f"{prefix}{command} {value}")


def _write_protocol_parallel(session: Any, bus: int, current: Mapping[str, Any], requested: Mapping[str, Any]) -> None:
    prefix = f":BUS{bus}:PARallel:"
    commands = {
        "bus_source": "BUS", "clock_source": "CLK", "slope": "SLOPe", "width": "WIDTh",
        "bit": "BITX", "source": "SOURce", "endian": "ENDian", "polarity": "POLarity",
    }
    order = ("bus_source", "clock_source", "slope", "width", "bit", "source", "endian", "polarity")
    for field in order:
        if field not in requested:
            continue
        value = requested[field]
        if field == "slope":
            value = {"POSITIVE": "POSitive", "NEGATIVE": "NEGative", "BOTH": "BOTH"}[value]
        elif field in {"endian", "polarity"}:
            value = {"POSITIVE": "POSitive", "NEGATIVE": "NEGative"}[value]
        session.write(f"{prefix}{commands[field]} {value}")


def _write_protocol_can(session: Any, bus: int, current: Mapping[str, Any], requested: Mapping[str, Any]) -> None:
    prefix = f":BUS{bus}:CAN:"
    commands = {"source": "SOURce", "signal_type": "STYPe", "baud": "BAUD", "fd_baud": "FDBaud", "sample_point": "SPOint", "fd_sample_point": "FDSPoint"}
    tokens = {"DIFFERENTIAL": "DIFFerential"}
    for field in ("source", "signal_type", "baud", "fd_baud", "sample_point", "fd_sample_point"):
        if field in requested:
            session.write(f"{prefix}{commands[field]} {tokens.get(requested[field], requested[field])}")


def _write_protocol_lin(session: Any, bus: int, current: Mapping[str, Any], requested: Mapping[str, Any]) -> None:
    prefix = f":BUS{bus}:LIN:"
    commands = {"parity": "PARity", "source": "SOURce", "standard": "STANdard", "baud": "BAUD"}
    tokens = {"MIXED": "MIXed"}
    for field in ("parity", "source", "standard", "baud"):
        if field in requested:
            value = int(requested[field]) if field == "parity" else tokens.get(requested[field], requested[field])
            session.write(f"{prefix}{commands[field]} {value}")


def _write_protocol_iis(session: Any, bus: int, current: Mapping[str, Any], requested: Mapping[str, Any]) -> None:
    prefix = f":BUS{bus}:IIS:"
    commands = {
        "clock_source": "SOURce:CLOCk", "data_source": "SOURce:DATA", "ws_source": "SOURce:WSELect",
        "alignment": "ALIGnment", "clock_slope": "CLOCk:SLOPe", "word_width": "RWIDth",
        "receive_width": "RECewidth", "ws_low": "WSLow", "endian": "ENDian", "polarity": "POLarity",
    }
    tokens = {"POSITIVE": "POSitive", "NEGATIVE": "NEGative", "RIGHT": "RIGHt"}
    for field in ("clock_source", "data_source", "ws_source", "alignment", "clock_slope", "word_width", "receive_width", "ws_low", "endian", "polarity"):
        if field in requested:
            session.write(f"{prefix}{commands[field]} {tokens.get(requested[field], requested[field])}")


def _write_protocol_flexray(session: Any, bus: int, current: Mapping[str, Any], requested: Mapping[str, Any]) -> None:
    prefix = f":BUS{bus}:FLEXray:"
    commands = {"baud": "BAUD", "source": "SOURce", "sample_point": "SPOint", "signal_type": "STYPe", "channel": "CHANnel"}
    for field in ("baud", "source", "sample_point", "signal_type", "channel"):
        if field in requested:
            session.write(f"{prefix}{commands[field]} {requested[field]}")


def _write_protocol_m1553(session: Any, bus: int, current: Mapping[str, Any], requested: Mapping[str, Any]) -> None:
    if "source" in requested:
        session.write(f":BUS{bus}:M1553:SOURce {requested['source']}")


def _write_protocol_spi(session: Any, bus: int, current: Mapping[str, Any], requested: Mapping[str, Any], final: Mapping[str, Any]) -> None:
    prefix = f":BUS{bus}:SPI:"
    commands = {
        "clock_source": "SCLK:SOURce",
        "clock_slope": "SCLK:SLOPe",
        "miso_source": "MISO:SOURce",
        "mosi_source": "MOSI:SOURce",
        "polarity": "POLarity",
        "miso_polarity": "MISO:POLarity",
        "mosi_polarity": "MOSI:POLarity",
        "data_bits": "DBITs",
        "endian": "ENDian",
        "frame_mode": "MODE",
        "timeout_s": "TIMeout:TIME",
        "cs_source": "SS:SOURce",
        "cs_polarity": "SS:POLarity",
    }
    # Turn on the other data line before turning one line OFF, avoiding a
    # transient state that violates the documented MISO/MOSI constraint.
    fields = list(requested)
    fields.sort(key=lambda field: 1 if field in {"miso_source", "mosi_source"} and requested[field] == "OFF" else 0)
    for field in fields:
        if field not in commands:
            continue
        session.write(f"{prefix}{commands[field]} {_spi_token(field, requested[field])}")


def _spi_token(field: str, value: Any) -> str:
    if field == "clock_slope":
        return {"POSITIVE": "POSitive", "NEGATIVE": "NEGative"}[value]
    if field == "frame_mode":
        return {"CS": "CS", "TIMEOUT": "TIMeout"}[value]
    return str(value)


def _write_protocol_rs232(session: Any, bus: int, current: Mapping[str, Any], requested: Mapping[str, Any], final: Mapping[str, Any]) -> None:
    prefix = f":BUS{bus}:RS232:"
    commands = {
        "tx_source": "TX",
        "rx_source": "RX",
        "polarity": "POLarity",
        "parity": "PARity",
        "endian": "ENDian",
        "baud": "BAUD",
        "data_bits": "DBITs",
        "stop_bits": "SBITs",
    }
    fields = list(requested)
    fields.sort(key=lambda field: 1 if field in {"tx_source", "rx_source"} and requested[field] == "OFF" else 0)
    for field in fields:
        if field not in commands:
            continue
        session.write(f"{prefix}{commands[field]} {_rs232_token(field, requested[field])}")


def _rs232_token(field: str, value: Any) -> str:
    if field == "polarity":
        return {"POSITIVE": "POSitive", "NEGATIVE": "NEGative"}[value]
    return str(value)


def _event_output_path(session: Any, filename: Any) -> Path:
    base = Path(session.output_dir).expanduser().resolve()
    base.mkdir(parents=True, exist_ok=True)
    if filename is None:
        path = base / f"mho98-bus-events-{uuid.uuid4().hex}.csv"
    else:
        if not isinstance(filename, str) or not filename.strip():
            raise ValueError("filename must be a non-empty path relative to output_dir")
        supplied = Path(filename)
        if supplied.is_absolute():
            raise ValueError("filename must be inside output_dir")
        path = (base / supplied).resolve()
        if path.suffix.lower() != ".csv":
            path = path.with_name(path.name + ".csv")
    try:
        path.relative_to(base)
    except ValueError:
        raise ValueError("filename must be inside output_dir") from None
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _max_rows(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 10_000:
        raise ValueError("max_rows must be an integer from 1 through 10000")
    return value


def read_decode_events(
    session: Any,
    bus: int = 1,
    max_rows: int = 100,
    include_raw: bool = False,
    filename: str | None = None,
) -> dict[str, Any]:
    """Read the existing BUS event table without enabling or changing it."""

    selected_bus = _bus(bus)
    limit = _max_rows(max_rows)
    raw_requested = _bool_input(include_raw, "include_raw")
    target = _event_output_path(session, filename) if filename is not None else None
    payload = session.binary_query(f":BUS{selected_bus}:DATA?")
    if isinstance(payload, bytes):
        text = payload.decode("utf-8", errors="replace")
    elif isinstance(payload, str):
        text = payload
    else:
        raise ValueError("BUS data response must be bytes or text")
    lines = text.splitlines()
    protocol_line = lines[0].strip() if lines else ""
    csv_text = "\n".join(lines[1:]) if len(lines) > 1 else ""
    reader = csv.reader(io.StringIO(csv_text))
    parsed = list(reader)
    columns = parsed[0] if parsed else []
    all_rows = parsed[1:] if parsed else []
    rows = all_rows[:limit]
    result: dict[str, Any] = {
        "bus": selected_bus,
        "protocol": protocol_line,
        "columns": columns,
        "rows": rows,
        "count": len(all_rows),
        "truncated": len(all_rows) > limit,
        "max_rows": limit,
        "prerequisites": {
            "display": "must already be enabled on the instrument",
            "event_table": "must already be enabled on the instrument",
            "checked": False,
        },
    }
    if raw_requested:
        result["raw_text"] = text
    if target is not None:
        created = False
        try:
            with target.open("x", newline="", encoding="utf-8") as handle:
                created = True
                writer = csv.writer(handle)
                if columns:
                    writer.writerow(columns)
                writer.writerows(all_rows)
        except Exception:
            if created and target.exists():
                target.unlink()
            raise
        result["path"] = str(target)
    return result


_COMMON_SCHEMA = {
    "display": {"type": "boolean"},
    "format": {"type": "string", "enum": ["HEX", "ASCII", "DEC", "BIN"]},
    "event": {"type": "boolean"},
    "label": {"type": "boolean"},
    "position": {"type": "integer", "minimum": -250, "maximum": 250},
    "thresholds": {"type": "object", "additionalProperties": {"type": "number"}},
}
_SET_SCHEMA = {
    "type": "object",
    "properties": {
        "bus": {"type": "integer", "minimum": 1, "maximum": 4},
        "protocol": {"type": "string", "enum": ["I2C", "IIC", "SPI", "RS232", "UART", "PARALLEL", "LIN", "CAN", "IIS", "I2S", "FLEXRAY", "M1553"]},
        **_COMMON_SCHEMA,
        "clock_source": {"type": "string"},
        "data_source": {"type": "string"},
        "exchange": {"type": "boolean"},
        "address_bits": {"type": "integer", "enum": [7, 8, 10]},
        "clock_slope": {"type": "string", "enum": ["POSITIVE", "NEGATIVE"]},
        "miso_source": {"type": "string"},
        "mosi_source": {"type": "string"},
        "polarity": {"type": "string"},
        "miso_polarity": {"type": "string", "enum": ["HIGH", "LOW"]},
        "mosi_polarity": {"type": "string", "enum": ["HIGH", "LOW"]},
        "data_bits": {"type": "integer"},
        "endian": {"type": "string"},
        "frame_mode": {"type": "string", "enum": ["CS", "TIMEOUT"]},
        "decode_mode": {"type": "string", "enum": ["CS", "TIMEOUT"]},
        "spi_mode": {"type": "string", "enum": ["CS", "TIMEOUT"]},
        "timeout_s": {"type": "number", "minimum": 8e-9, "maximum": 10},
        "cs_source": {"type": "string"},
        "cs_polarity": {"type": "string", "enum": ["HIGH", "LOW"]},
        "tx_source": {"type": "string"},
        "rx_source": {"type": "string"},
        "parity": {"type": "string", "enum": ["NONE", "ODD", "EVEN"]},
        "baud": {"type": "integer", "minimum": 1, "maximum": 20_000_000},
        "baud_rate": {"type": "integer", "minimum": 1, "maximum": 20_000_000},
        "stop_bits": {"type": "number", "enum": [1, 1.5, 2]},
        "source": {"type": "string"},
        "bus_source": {"type": "string"},
        "slope": {"type": "string", "enum": ["POSITIVE", "NEGATIVE", "BOTH"]},
        "width": {"type": "integer", "minimum": 1, "maximum": 16},
        "bit": {"type": "integer", "minimum": 0, "maximum": 15},
        "signal_type": {"type": "string"},
        "sample_point": {"type": "integer", "minimum": 10, "maximum": 90},
        "fd_baud": {"type": "integer", "minimum": 1_000_000, "maximum": 10_000_000},
        "fd_sample_point": {"type": "integer", "minimum": 10, "maximum": 90},
        "standard": {"type": "string", "enum": ["V1X", "V2X", "MIXED"]},
        "ws_source": {"type": "string"},
        "alignment": {"type": "string", "enum": ["IIS", "RJ", "LJ"]},
        "word_width": {"type": "integer", "minimum": 4, "maximum": 32},
        "receive_width": {"type": "integer", "minimum": 4, "maximum": 32},
        "ws_low": {"type": "string", "enum": ["LEFT", "RIGHT"]},
        "channel": {"type": "string", "enum": ["A", "B"]},
        "details": {"type": "object", "additionalProperties": True},
    },
    "required": [],
}

TOOLS = [
    ToolSpec(
        name="get_decode",
        description="Read MHO98 BUS common controls and one of the nine documented protocol decoder settings.",
        input_schema={"type": "object", "properties": {"bus": {"type": "integer", "minimum": 1, "maximum": 4}}, "required": []},
        handler=get_decode,
        read_only=True,
        needs_session=True,
    ),
    ToolSpec(
        name="set_decode",
        description="Send selected MHO98 BUS common and protocol commands; omitted fields are preserved and resulting state is not verified.",
        input_schema=_SET_SCHEMA,
        handler=set_decode,
        read_only=False,
        needs_session=True,
    ),
    ToolSpec(
        name="read_decode_events",
        description="Read an existing MHO98 BUS event table as protocol text plus variable CSV columns and string rows; never enables BUS display or events.",
        input_schema={
            "type": "object",
            "properties": {
                "bus": {"type": "integer", "minimum": 1, "maximum": 4},
                "max_rows": {"type": "integer", "minimum": 1, "maximum": 10_000, "default": 100},
                "include_raw": {"type": "boolean", "default": False},
                "filename": {"type": ["string", "null"]},
            },
            "required": [],
        },
        handler=read_decode_events,
        read_only=True,
        needs_session=True,
    ),
]
