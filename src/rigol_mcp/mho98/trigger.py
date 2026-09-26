"""Bounded MHO98 common and named trigger-family controls."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from .api import ToolSpec


_MODES = (
    "EDGE", "PULSE", "SLOPE", "VIDEO", "PATTERN", "DURATION", "TIMEOUT",
    "RUNT", "WINDOW", "DELAY", "SETUP", "NEDGE", "RS232", "IIC", "SPI",
    "CAN", "LIN", "IIS", "FLEXRAY", "M1553",
)
_MODE_ALIASES = {
    "EDGE": "EDGE", "PULS": "PULSE", "PULSE": "PULSE", "SLOP": "SLOPE", "SLOPE": "SLOPE",
    "VID": "VIDEO", "VIDEO": "VIDEO", "PATT": "PATTERN", "PATTERN": "PATTERN",
    "DUR": "DURATION", "DURATION": "DURATION", "TIM": "TIMEOUT", "TIMEOUT": "TIMEOUT",
    "RUNT": "RUNT", "WIND": "WINDOW", "WINDOW": "WINDOW", "DEL": "DELAY", "DELAY": "DELAY",
    "SET": "SETUP", "SETUP": "SETUP", "NEDG": "NEDGE", "NEDGE": "NEDGE", "RS232": "RS232",
    "UART": "RS232", "IIC": "IIC", "I2C": "IIC", "SPI": "SPI", "CAN": "CAN", "LIN": "LIN",
    "IIS": "IIS", "I2S": "IIS", "FLEX": "FLEXRAY", "FLEXRAY": "FLEXRAY", "M1553": "M1553",
}
_MODE_SCPI = {
    "EDGE": "EDGE", "PULSE": "PULSe", "SLOPE": "SLOPe", "VIDEO": "VIDeo", "PATTERN": "PATTern",
    "DURATION": "DURation", "TIMEOUT": "TIMeout", "RUNT": "RUNT", "WINDOW": "WINDow", "DELAY": "DELay",
    "SETUP": "SETup", "NEDGE": "NEDGe", "RS232": "RS232", "IIC": "IIC", "SPI": "SPI", "CAN": "CAN",
    "LIN": "LIN", "IIS": "IIS", "FLEXRAY": "FLEXray", "M1553": "M1553",
}
_HOLDoff_EXCLUDED = frozenset({"VIDEO", "TIMEOUT", "NEDGE", "RS232", "IIC", "SPI", "CAN", "LIN", "IIS", "FLEXRAY", "M1553"})
_MODE_PROTOCOL = {
    "IIC": "I2C", "SPI": "SPI", "RS232": "RS232", "CAN": "CAN", "LIN": "LIN",
    "IIS": "I2S", "FLEXRAY": "FLEXRAY", "M1553": "M1553",
}
_MODE_PROTOCOL.update({
    "PULSE": "PULSE", "SLOPE": "SLOPE", "VIDEO": "VIDEO", "PATTERN": "PATTERN",
    "DURATION": "DURATION", "TIMEOUT": "TIMEOUT", "RUNT": "RUNT", "WINDOW": "WINDOW",
    "DELAY": "DELAY", "SETUP": "SETUP", "NEDGE": "NEDGE",
})
_SUPPORTED_PROTOCOLS = (
    "PULSE", "SLOPE", "VIDEO", "PATTERN", "DURATION", "TIMEOUT", "RUNT", "WINDOW", "DELAY", "SETUP", "NEDGE",
    "I2C", "SPI", "RS232", "CAN", "LIN", "I2S", "FLEXRAY", "M1553",
)

_DETAIL_FIELDS = {
    "I2C": frozenset({
        "scl_source", "scl_level", "sda_source", "sda_level", "condition",
        "address_width", "address", "direction", "data_bytes", "data",
        "current_bit", "bit_code",
    }),
    "SPI": frozenset({
        "clock_source", "clock_level", "clock_slope", "data_source", "data_level",
        "condition", "cs_source", "cs_level", "cs_mode", "timeout_s", "data_width",
        "data", "current_bit", "bit_code",
    }),
    "RS232": frozenset({
        "source", "level", "polarity", "condition", "data", "baud", "data_width",
        "stop_bits", "parity",
    }),
    "CAN": frozenset({
        "source", "level", "baud", "signal_type", "condition", "sample_point", "extended_id",
        "define", "data_width", "data", "current_bit", "bit_code",
    }),
    "LIN": frozenset({
        "source", "level", "standard", "baud", "sample_point", "condition", "error", "id",
        "data", "current_bit", "bit_code",
    }),
    "I2S": frozenset({
        "alignment", "clock_level", "frame_level", "data_level", "user_width", "width",
        "data_min_bit", "data_max_bit", "bit_code", "clock_slope", "clock_source", "data_source",
        "ws_source", "condition", "audio", "data",
    }),
    "FLEXRAY": frozenset({
        "baud", "position", "error", "symbol", "frame", "define", "id_comparison", "cycle_comparison",
        "max_cycle", "min_cycle", "max_id", "min_id", "channel", "source", "condition", "level",
    }),
    "M1553": frozenset({
        "source", "condition", "polarity", "window", "sync", "error", "data_comparison", "data_value",
        "data_min_bit", "data_max_bit", "remote_terminal_address", "data_bit", "bit_code", "level_a", "level_b",
    }),
    "PULSE": frozenset({"source", "polarity", "condition", "upper_width_s", "lower_width_s", "level"}),
    "SLOPE": frozenset({"source", "polarity", "condition", "upper_time_s", "lower_time_s", "window", "upper_level", "lower_level"}),
    "VIDEO": frozenset({"source", "polarity", "sync", "line", "standard", "level"}),
    "PATTERN": frozenset({"source", "pattern", "levels", "level"}),
    "DURATION": frozenset({"source", "pattern", "condition", "upper_time_s", "lower_time_s", "levels", "level"}),
    "TIMEOUT": frozenset({"source", "slope", "time_s", "level"}),
    "RUNT": frozenset({"source", "polarity", "condition", "upper_width_s", "lower_width_s", "upper_level", "lower_level"}),
    "WINDOW": frozenset({"source", "slope", "position", "time_s", "upper_level", "lower_level"}),
    "DELAY": frozenset({"source_a", "slope_a", "source_b", "slope_b", "condition", "upper_time_s", "lower_time_s", "level_a", "level_b"}),
    "SETUP": frozenset({"data_source", "clock_source", "slope", "pattern", "condition", "setup_time_s", "hold_time_s", "data_level", "clock_level"}),
    "NEDGE": frozenset({"source", "slope", "idle_time_s", "edge_count", "level"}),
}
_DETAIL_ALIASES = {
    "I2C": {
        "clock_source": "scl_source", "clock_level": "scl_level", "when": "condition",
        "address_bits": "address_width", "awidth": "address_width", "bytes": "data_bytes",
        "currbit": "current_bit", "code": "bit_code",
    },
    "SPI": {
        "clk_source": "clock_source", "scl_source": "clock_source", "scl_level": "clock_level",
        "clevel": "clock_level", "slope": "clock_slope", "miso_source": "data_source",
        "sda_source": "data_source", "dlevel": "data_level", "miso_level": "data_level",
        "sda_level": "data_level", "when": "condition", "slevel": "cs_level", "mode": "cs_mode",
        "timeout": "timeout_s", "width": "data_width", "currbit": "current_bit", "code": "bit_code",
    },
    "RS232": {
        "when": "condition", "baud_rate": "baud", "buser": "baud", "width": "data_width",
        "data_bits": "data_width", "stop": "stop_bits",
    },
    "CAN": {
        "when": "condition", "stype": "signal_type", "sample": "sample_point", "spoint": "sample_point",
        "extended": "extended_id", "define_type": "define", "bytes": "data_width", "currbit": "current_bit", "code": "bit_code",
    },
    "LIN": {
        "when": "condition", "std": "standard", "baud_rate": "baud", "sample": "sample_point", "spoint": "sample_point",
        "err": "error", "identifier": "id", "currbit": "current_bit", "code": "bit_code",
    },
    "I2S": {
        "ws_level": "frame_level", "slevel": "frame_level", "dlevel": "data_level", "uwidth": "user_width",
        "data_width": "width", "dmin": "data_min_bit", "dmax": "data_max_bit", "code": "bit_code",
        "slope": "clock_slope", "clk_source": "clock_source", "sda_source": "data_source", "wselect_source": "ws_source",
        "when": "condition", "operator": "condition", "audio_channel": "audio",
    },
    "FLEXRAY": {
        "when": "condition", "err": "error", "stype": "symbol", "frame_type": "frame", "idcomp": "id_comparison",
        "cyccomp": "cycle_comparison", "maxcy": "max_cycle", "mincy": "min_cycle", "maxid": "max_id", "minid": "min_id",
        "ch": "channel", "spoint": "position",
    },
    "M1553": {
        "when": "condition", "datacomp": "data_comparison", "datavalue": "data_value", "dmin": "data_min_bit",
        "dmax": "data_max_bit", "drta": "remote_terminal_address", "dbit": "data_bit", "code": "bit_code",
        "alevel": "level_a", "blevel": "level_b", "rta": "remote_terminal_address",
    },
    "PULSE": {"when": "condition", "upper_width": "upper_width_s", "lower_width": "lower_width_s"},
    "SLOPE": {"when": "condition", "upper_time": "upper_time_s", "lower_time": "lower_time_s", "upper": "upper_level", "lower": "lower_level"},
    "VIDEO": {"sync_type": "sync", "mode": "sync", "line_number": "line", "video_standard": "standard"},
    "PATTERN": {"channel_pattern": "pattern", "thresholds": "levels"},
    "DURATION": {"channel_pattern": "pattern", "when": "condition", "upper_time": "upper_time_s", "lower_time": "lower_time_s", "thresholds": "levels"},
    "TIMEOUT": {"time": "time_s"},
    "RUNT": {"when": "condition", "upper_width": "upper_width_s", "lower_width": "lower_width_s", "upper": "upper_level", "lower": "lower_level"},
    "WINDOW": {"time": "time_s", "threshold_upper": "upper_level", "threshold_lower": "lower_level"},
    "DELAY": {"type": "condition", "upper_time": "upper_time_s", "lower_time": "lower_time_s"},
    "SETUP": {"clock": "clock_source", "data_type": "pattern", "type": "condition", "setup_time": "setup_time_s", "hold_time": "hold_time_s"},
    "NEDGE": {"idle": "idle_time_s", "edge": "edge_count"},
}


def _mode(value: Any) -> str:
    if not isinstance(value, str) or value.strip().upper() not in _MODE_ALIASES:
        raise ValueError(f"mode must be one of the 20 documented MHO98 trigger modes: {_MODES}")
    return _MODE_ALIASES[value.strip().upper()]


def _sweep(value: Any) -> str:
    if not isinstance(value, str) or value.strip().upper() not in {"AUTO", "NORM", "NORMAL", "SING", "SINGLE"}:
        raise ValueError("sweep must be AUTO, NORM, or SING")
    token = value.strip().upper()
    return {"NORMAL": "NORM", "SINGLE": "SING"}.get(token, token)


def _coupling(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("coupling must be AC, DC, LFR, or HFR")
    token = value.strip().upper().replace("REJECT", "R")
    if token not in {"AC", "DC", "LFR", "HFR"}:
        raise ValueError("coupling must be AC, DC, LFR, or HFR")
    return token


def _bool(value: Any, name: str) -> bool:
    if isinstance(value, bool):
        return value
    token = str(value).strip().upper()
    if token in {"1", "ON", "TRUE"}:
        return True
    if token in {"0", "OFF", "FALSE"}:
        return False
    raise ValueError(f"{name} must be boolean")


def _bool_response(value: Any, name: str) -> bool:
    return _bool(value, name)


def _source(value: Any, name: str = "source") -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be CHAN1-CHAN4 or D0-D15")
    token = value.strip().upper().replace(" ", "")
    if token == "EXT":
        raise ValueError(f"{name} cannot be EXT on MHO98")
    if token.startswith("CHANNEL"):
        token = "CHAN" + token[7:]
    elif token.startswith("CH") and not token.startswith("CHAN"):
        token = "CHAN" + token[2:]
    if token.startswith("CHAN") and token[4:].isdigit() and 1 <= int(token[4:]) <= 4:
        return token
    if token.startswith("D") and token[1:].isdigit() and 0 <= int(token[1:]) <= 15:
        return token
    raise ValueError(f"{name} must be CHAN1-CHAN4 or D0-D15")


def _slope(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("slope must be POS, NEG, or RFAL")
    token = value.strip().upper()
    aliases = {"POS": "POS", "POSITIVE": "POS", "NEG": "NEG", "NEGATIVE": "NEG", "RFAL": "RFAL", "RISINGFALLING": "RFAL"}
    if token not in aliases:
        raise ValueError("slope must be POS, NEG, or RFAL")
    return aliases[token]


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be finite")
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be finite") from None
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _integer(value: Any, name: str, low: int, high: int) -> int:
    result = _finite(value, name)
    if not result.is_integer() or not low <= result <= high:
        raise ValueError(f"{name} must be an integer from {low} through {high}")
    return int(result)


def _enum(value: Any, name: str, aliases: Mapping[str, str]) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} has an unsupported value: {value!r}")
    token = value.strip().upper()
    selected = aliases.get(token)
    if selected is None:
        raise ValueError(f"{name} must be one of {', '.join(sorted(set(aliases.values())))}")
    return selected


def _holdoff(value: Any) -> float:
    result = _finite(value, "holdoff_s")
    if not 8e-9 <= result <= 10.0:
        raise ValueError("holdoff_s must be between 8 ns and 10 s")
    return result


def _mode_response(value: Any) -> str:
    return _mode(str(value))


def _query_global(session: Any) -> dict[str, Any]:
    mode = _mode_response(session.query(":TRIGger:MODE?"))
    result: dict[str, Any] = {
        "mode": mode,
        "sweep": _sweep(session.query(":TRIGger:SWEep?")),
        "status": str(session.query(":TRIGger:STATus?")).strip().upper(),
        "coupling": None,
        "holdoff_s": None,
        "noise_reject": None,
        "unavailable": [],
    }
    if mode == "EDGE":
        edge = _query_edge(session)
        result.update(edge)
        if edge["source"].startswith("CHAN"):
            result["coupling"] = _coupling(session.query(":TRIGger:COUPling?"))
            result["noise_reject"] = _bool_response(session.query(":TRIGger:NREJect?"), "noise_reject")
        else:
            result["unavailable"].extend(["coupling", "noise_reject"])
    else:
        result["unavailable"].extend(["coupling", "noise_reject"])
    if mode not in _HOLDoff_EXCLUDED:
        result["holdoff_s"] = _holdoff(session.query(":TRIGger:HOLDoff?"))
    else:
        result["unavailable"].append("holdoff_s")
    return result


def _query_edge(session: Any) -> dict[str, Any]:
    return {
        "source": _source(session.query(":TRIGger:EDGE:SOURce?"), "edge source"),
        "slope": _slope(session.query(":TRIGger:EDGE:SLOPe?")),
        "level": _finite(session.query(":TRIGger:EDGE:LEVel?"), "level"),
    }


def _query_i2c_details(session: Any) -> dict[str, Any]:
    prefix = ":TRIGger:IIC:"
    result = {
        "scl_source": _source(session.query(prefix + "SCL?"), "scl_source"),
        "scl_level": _finite(session.query(prefix + "CLEVel?"), "scl_level"),
        "sda_source": _source(session.query(prefix + "SDA?"), "sda_source"),
        "sda_level": _finite(session.query(prefix + "DLEVel?"), "sda_level"),
        "condition": _enum(session.query(prefix + "WHEN?"), "condition", {
            "STAR": "START", "START": "START", "REST": "RESTART", "RESTART": "RESTART",
            "STOP": "STOP", "NACK": "NACK", "NACKNOWLEDGE": "NACK", "ADDR": "ADDRESS",
            "ADDRESS": "ADDRESS", "DATA": "DATA", "ADAT": "ADDRESS_DATA", "ADATA": "ADDRESS_DATA",
        }),
    }
    if result["condition"] in {"ADDRESS", "ADDRESS_DATA"}:
        result["address_width"] = _integer(session.query(prefix + "AWIDth?"), "address_width", 7, 10)
        if result["address_width"] not in {7, 8, 10}:
            raise ValueError("address_width must be 7, 8, or 10")
        result["address"] = _integer(session.query(prefix + "ADDRess?"), "address", 0, (1 << result["address_width"]) - 1)
        if result["address_width"] != 8:
            result["direction"] = _enum(session.query(prefix + "DIRection?"), "direction", {
                "READ": "READ", "WRIT": "WRITE", "WRITE": "WRITE", "RWR": "READ_WRITE", "READWRITE": "READ_WRITE",
            })
    if result["condition"] in {"DATA", "ADDRESS_DATA"}:
        result["data_bytes"] = _integer(session.query(prefix + "DBYTes?"), "data_bytes", 1, 5)
        result["data"] = _integer(session.query(prefix + "DATA?"), "data", 0, (1 << (8 * result["data_bytes"])) - 1)
        result["current_bit"] = _integer(session.query(prefix + "CURRbit?"), "current_bit", 0, 39)
        result["bit_code"] = _integer(session.query(prefix + "CODE?"), "bit_code", 0, 255)
        if result["bit_code"] not in {0, 1, 255}:
            raise ValueError("bit_code must be 0, 1, or 255")
    return result


def _query_spi_details(session: Any) -> dict[str, Any]:
    prefix = ":TRIGger:SPI:"
    result = {
        "clock_source": _source(session.query(prefix + "CLK?"), "clock_source"),
        "clock_level": _finite(session.query(prefix + "CLEVel?"), "clock_level"),
        "clock_slope": _enum(session.query(prefix + "SLOPe?"), "clock_slope", {
            "POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE",
        }),
        "data_source": _source(session.query(prefix + "MISO?"), "data_source"),
        "data_level": _finite(session.query(prefix + "DLEVel?"), "data_level"),
        "condition": _enum(session.query(prefix + "WHEN?"), "condition", {
            "CS": "CS", "TIMEOUT": "TIMEOUT", "TIM": "TIMEOUT",
        }),
        "data_width": _integer(session.query(prefix + "WIDTh?"), "data_width", 4, 32),
        "data": _integer(session.query(prefix + "DATA?"), "data", 0, (1 << 32) - 1),
        "current_bit": _integer(session.query(prefix + "CURRbit?"), "current_bit", 0, 39),
        "bit_code": _integer(session.query(prefix + "CODE?"), "bit_code", 0, 255),
    }
    if result["bit_code"] not in {0, 1, 255}:
        raise ValueError("bit_code must be 0, 1, or 255")
    if result["condition"] == "CS":
        result.update({
            "cs_source": _source(session.query(prefix + "CS?"), "cs_source"),
            "cs_level": _finite(session.query(prefix + "SLEVel?"), "cs_level"),
            "cs_mode": _enum(session.query(prefix + "MODE?"), "cs_mode", {"HIGH": "HIGH", "LOW": "LOW"}),
        })
    else:
        result["timeout_s"] = _finite(session.query(prefix + "TIMeout?"), "timeout_s")
        if not 8e-9 <= result["timeout_s"] <= 10.0:
            raise ValueError("timeout_s must be between 8 ns and 10 s")
    return result


def _query_rs232_details(session: Any) -> dict[str, Any]:
    prefix = ":TRIGger:RS232:"
    result = {
        "source": _source(session.query(prefix + "SOURce?")),
        "level": _finite(session.query(prefix + "LEVel?"), "level"),
        "polarity": _enum(session.query(prefix + "POLarity?"), "polarity", {
            "POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE",
        }),
        "condition": _enum(session.query(prefix + "WHEN?"), "condition", {
            "STAR": "START", "START": "START", "ERR": "ERROR", "ERROR": "ERROR",
            "CERR": "CHECK_ERROR", "CHECKERROR": "CHECK_ERROR", "DATA": "DATA",
        }),
        "baud": _integer(session.query(prefix + "BAUD?"), "baud", 1, 20_000_000),
        "stop_bits": _stop_bits(session.query(prefix + "STOP?")),
        "parity": _enum(session.query(prefix + "PARity?"), "parity", {"EVEN": "EVEN", "ODD": "ODD", "NONE": "NONE"}),
    }
    if result["condition"] == "DATA":
        result["data_width"] = _integer(session.query(prefix + "WIDTh?"), "data_width", 5, 8)
        result["data"] = _integer(session.query(prefix + "DATA?"), "data", 0, (1 << result["data_width"]) - 1)
    return result


def _query_can_details(session: Any) -> dict[str, Any]:
    prefix = ":TRIGger:CAN:"
    result = {
        "source": _source(session.query(prefix + "SOURce?")),
        "level": _finite(session.query(prefix + "LEVel?"), "level"),
        "baud": _integer(session.query(prefix + "BAUD?"), "baud", 10_000, 5_000_000),
        "signal_type": _enum(session.query(prefix + "STYPe?"), "signal_type", {
            "H": "H", "L": "L", "RXTX": "RXTX", "DIFF": "DIFFERENTIAL", "DIFFERENTIAL": "DIFFERENTIAL",
        }),
        "condition": _enum(session.query(prefix + "WHEN?"), "condition", {
            "SOF": "SOF", "EOF": "EOF", "IDR": "ID_REMOTE", "IDREMOTE": "ID_REMOTE", "OVER": "OVERLOAD",
            "OVERLOAD": "OVERLOAD", "IDFR": "ID_FRAME", "IDFRAME": "ID_FRAME", "DAT": "DATA_FRAME",
            "DATAFRAME": "DATA_FRAME", "IDD": "ID_DATA", "IDDATA": "ID_DATA", "ERFR": "ERROR_FRAME",
            "ERFRAME": "ERROR_FRAME", "ERAN": "ERROR_ANSWER", "ERANSWER": "ERROR_ANSWER", "ERCH": "ERROR_CHECK",
            "ERCHECK": "ERROR_CHECK", "ERF": "ERROR_FORMAT", "ERFORMAT": "ERROR_FORMAT", "ERR": "ERROR_RANDOM",
            "ERRORRANDOM": "ERROR_RANDOM", "ERB": "ERROR_BIT", "ERRORBIT": "ERROR_BIT",
        }),
        "sample_point": _integer(session.query(prefix + "SPOint?"), "sample_point", 10, 90),
    }
    if result["condition"] in {"ID_REMOTE", "ID_FRAME"}:
        result["extended_id"] = _bool_response(session.query(prefix + "EXTended?"), "extended_id")
    if result["condition"] == "ID_DATA":
        result["define"] = _enum(session.query(prefix + "DEFine?"), "define", {
            "DATA": "DATA", "FALS": "DATA", "FALSE": "DATA", "ID": "ID", "TRUE": "ID",
        })
        result["data_width"] = _integer(session.query(prefix + "DWIDth?"), "data_width", 1, 8)
        result["data"] = _integer(session.query(prefix + "DATA?"), "data", 0, (1 << 64) - 1)
        result["current_bit"] = _integer(session.query(prefix + "CURRbit?"), "current_bit", 0, 39)
        result["bit_code"] = _bit_code(session.query(prefix + "CODE?"))
    elif result["condition"] == "DATA_FRAME":
        result["data_width"] = _integer(session.query(prefix + "DWIDth?"), "data_width", 1, 8)
        result["data"] = _integer(session.query(prefix + "DATA?"), "data", 0, (1 << 64) - 1)
        result["current_bit"] = _integer(session.query(prefix + "CURRbit?"), "current_bit", 0, 39)
        result["bit_code"] = _bit_code(session.query(prefix + "CODE?"))
    return result


def _query_lin_details(session: Any) -> dict[str, Any]:
    prefix = ":TRIGger:LIN:"
    result = {
        "source": _source(session.query(prefix + "SOURce?")),
        "level": _finite(session.query(prefix + "LEVel?"), "level"),
        "standard": _enum(session.query(prefix + "STANdard?"), "standard", {"1X": "1X", "2X": "2X", "BOTH": "BOTH"}),
        "baud": _integer(session.query(prefix + "BAUD?"), "baud", 1_000, 20_000_000),
        "sample_point": _integer(session.query(prefix + "SAMPlepoint?"), "sample_point", 10, 90),
        "condition": _enum(session.query(prefix + "WHEN?"), "condition", {
            "SYNC": "SYNC_BREAK", "SYNCBREAK": "SYNC_BREAK", "ID": "ID", "DATA": "DATA", "IDD": "ID_DATA",
            "IDDATA": "ID_DATA", "SLE": "SLEEP", "SLEEP": "SLEEP", "WAK": "WAKEUP", "WAKEUP": "WAKEUP",
            "ERR": "ERROR", "ERROR": "ERROR",
        }),
    }
    if result["condition"] == "ERROR":
        result["error"] = _enum(session.query(prefix + "ERRor?"), "error", {"SYNC": "SYNC", "ID": "ID", "CHEC": "CHECKSUM", "CHECK": "CHECKSUM"})
    if result["condition"] in {"ID", "ID_DATA"}:
        result["id"] = _integer(session.query(prefix + "ID?"), "id", 0, 63)
    if result["condition"] in {"DATA", "ID_DATA"}:
        result["data"] = _integer(session.query(prefix + "DATA?"), "data", 0, (1 << 64) - 1)
        result["current_bit"] = _integer(session.query(prefix + "CURRbit?"), "current_bit", 0, 39)
        result["bit_code"] = _bit_code(session.query(prefix + "CODE?"))
    return result


def _query_i2s_details(session: Any) -> dict[str, Any]:
    prefix = ":TRIGger:IIS:"
    result = {
        "alignment": _enum(session.query(prefix + "ALIGnment?"), "alignment", {"LJ": "LJ", "RJ": "RJ", "IIS": "IIS"}),
        "clock_source": _source(session.query(prefix + "SOURce:CLOCk?"), "clock_source"),
        "data_source": _source(session.query(prefix + "SOURce:DATA?"), "data_source"),
        "ws_source": _source(session.query(prefix + "SOURce:WSELect?"), "ws_source"),
        "clock_level": _finite(session.query(prefix + "CLEVel?"), "clock_level"),
        "frame_level": _finite(session.query(prefix + "SLEVel?"), "frame_level"),
        "data_level": _finite(session.query(prefix + "DLEVel?"), "data_level"),
        "width": _integer(session.query(prefix + "WIDTh?"), "width", 4, 32),
        "clock_slope": _enum(session.query(prefix + "CLOCk:SLOPe?"), "clock_slope", {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE"}),
        "condition": _enum(session.query(prefix + "WHEN?"), "condition", {
            "EQU": "EQUAL", "EQUAL": "EQUAL", "NOT": "NOT_EQUAL", "NOTEQUAL": "NOT_EQUAL", "LESS": "LESS_THAN",
            "LESSTHAN": "LESS_THAN", "GRE": "GREATER_THAN", "GREATERTHAN": "GREATER_THAN", "INR": "IN_RANGE",
            "INRANGE": "IN_RANGE", "OUTR": "OUT_RANGE", "OUTRANGE": "OUT_RANGE",
        }),
        "audio": _enum(session.query(prefix + "AUDio?"), "audio", {"RIGH": "RIGHT", "RIGHT": "RIGHT", "LEFT": "LEFT", "EITH": "EITHER", "EITHER": "EITHER"}),
    }
    result["user_width"] = _integer(session.query(prefix + "UWIDth?"), "user_width", 4, result["width"])
    if result["condition"] in {"EQUAL", "NOT_EQUAL"}:
        result["data"] = _integer(session.query(prefix + "DATA?"), "data", 0, (1 << 32) - 1)
    elif result["condition"] in {"IN_RANGE", "OUT_RANGE"}:
        result["data_min_bit"] = _integer(session.query(prefix + "DMIN?"), "data_min_bit", 0, 31)
        result["data_max_bit"] = _integer(session.query(prefix + "DMAX?"), "data_max_bit", 0, 31)
        result["bit_code"] = _bit_code(session.query(prefix + "CODE?"))
    return result


def _query_flexray_details(session: Any) -> dict[str, Any]:
    prefix = ":TRIGger:FLEXray:"
    result = {
        "source": _source(session.query(prefix + "SOURce?")),
        "level": _finite(session.query(prefix + "LEVel?"), "level"),
        "channel": _enum(session.query(prefix + "CH?"), "channel", {"A": "A", "B": "B"}),
        "baud": _integer(session.query(prefix + "BAUD?"), "baud", 2_500_000, 10_000_000),
        "condition": _enum(session.query(prefix + "WHEN?"), "condition", {"FRAM": "FRAME", "FRAME": "FRAME", "SYMBOL": "SYMBOL", "SYMB": "SYMBOL", "ERR": "ERROR", "ERROR": "ERROR", "TSS": "TSS"}),
    }
    if result["baud"] not in {2_500_000, 5_000_000, 10_000_000}:
        raise ValueError("baud must be 2500000, 5000000, or 10000000")
    if result["condition"] == "TSS":
        result["position"] = _enum(session.query(prefix + "POS?"), "position", {"TSS": "TSS", "FSS": "FSS", "FES": "FES", "DTS": "DTS"})
    elif result["condition"] == "ERROR":
        result["error"] = _enum(session.query(prefix + "ERRor?"), "error", {"HEAD": "HEADER", "TRA": "TRAILER", "TRAILER": "TRAILER", "DEC": "DECODE", "DECODE": "DECODE", "ANY": "ANY"})
    elif result["condition"] == "SYMBOL":
        result["symbol"] = _enum(session.query(prefix + "SYMBol?"), "symbol", {"CAS": "CAS", "WUS": "WUS"})
        result["id_comparison"] = _comparison(session.query(prefix + "IDCmp?"), "id_comparison")
        result["max_id"] = _integer(session.query(prefix + "MAXid?"), "max_id", 0, 1023)
        result["min_id"] = _integer(session.query(prefix + "MINid?"), "min_id", 0, 1023)
    elif result["condition"] == "FRAME":
        result["frame"] = _enum(session.query(prefix + "FRAMe?"), "frame", {"NULL": "NULL", "SYNC": "SYNC", "STAR": "STARTUP", "STARTUP": "STARTUP", "ANY": "ANY"})
        result["define"] = _enum(session.query(prefix + "DEFine?"), "define", {"CYCL": "CYCLE", "CYCLE": "CYCLE", "ID": "ID", "FALS": "ID", "FALSE": "ID", "TRUE": "CYCLE"})
        result["id_comparison"] = _comparison(session.query(prefix + "IDCmp?"), "id_comparison")
        if result["define"] == "CYCLE":
            result["cycle_comparison"] = _comparison(session.query(prefix + "CYCComp?"), "cycle_comparison")
            result["max_cycle"] = _integer(session.query(prefix + "MAXCy?"), "max_cycle", 0, 63)
            result["min_cycle"] = _integer(session.query(prefix + "MINCy?"), "min_cycle", 0, 63)
        else:
            result["max_id"] = _integer(session.query(prefix + "MAXid?"), "max_id", 0, 1023)
            result["min_id"] = _integer(session.query(prefix + "MINid?"), "min_id", 0, 1023)
    return result


def _query_m1553_details(session: Any) -> dict[str, Any]:
    prefix = ":TRIGger:M1553:"
    result = {
        "source": _source(session.query(prefix + "SOURce?")),
        "condition": _enum(session.query(prefix + "WHEN?"), "condition", {"SYNC": "SYNC_BREAK", "SYNCBREAK": "SYNC_BREAK", "DATA": "DATA", "CMD": "COMMAND", "COMMAND": "COMMAND", "STAT": "STATUS", "STATUS": "STATUS", "ERR": "ERROR", "ERROR": "ERROR"}),
        "polarity": _enum(session.query(prefix + "POLarity?"), "polarity", {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE"}),
        "window": _enum(session.query(prefix + "WINDow?"), "window", {"TA": "TA", "TB": "TB", "TAB": "TAB"}),
        "level_a": _finite(session.query(prefix + "ALEVel?"), "level_a"),
        "level_b": _finite(session.query(prefix + "BLEVel?"), "level_b"),
    }
    if result["condition"] == "SYNC_BREAK":
        result["sync"] = _enum(session.query(prefix + "SYNC?"), "sync", {"DATA": "DATA", "STAT": "STATUS", "STATUS": "STATUS", "ALL": "ALL"})
    elif result["condition"] == "ERROR":
        result["error"] = _enum(session.query(prefix + "ERRor?"), "error", {"SYNC": "SYNC", "ERR": "ERROR", "ERROR": "ERROR"})
    elif result["condition"] == "DATA":
        result["data_comparison"] = _comparison(session.query(prefix + "DATComp?"), "data_comparison")
        result["data_value"] = _integer(session.query(prefix + "DATValue?"), "data_value", 0, 65_535)
        result["data_min_bit"] = _integer(session.query(prefix + "DMIN?"), "data_min_bit", 0, 19)
        result["data_max_bit"] = _integer(session.query(prefix + "DMAX?"), "data_max_bit", 0, 19)
        result["bit_code"] = _bit_code(session.query(prefix + "CODE?"))
    elif result["condition"] == "COMMAND":
        result["remote_terminal_address"] = _integer(session.query(prefix + "DRTA?"), "remote_terminal_address", 0, 6)
    elif result["condition"] == "STATUS":
        result["remote_terminal_address"] = _integer(session.query(prefix + "DRTA?"), "remote_terminal_address", 0, 6)
        result["data_bit"] = _integer(session.query(prefix + "DBIT?"), "data_bit", 0, 13)
        result["bit_code"] = _bit_code(session.query(prefix + "CODE?"))
    return result


_VIDEO_LINES = {
    "PALSECAM": 625, "NTSC": 525, "480P": 525, "576P": 625,
    "720P60": 750, "720P50": 750, "720P30": 750, "720P25": 750, "720P24": 750,
    "1080P60": 1125, "1080P50": 1125, "1080P30": 1125, "1080P25": 1125, "1080P24": 1125,
    "1080I60": 1125, "1080I50": 1125,
}


def _trigger_time(value: Any, name: str, low: float = 1e-9) -> float:
    result = _finite(value, name)
    if not low <= result <= 10.0:
        raise ValueError(f"{name} must be between {low:g} s and 10 s")
    return result


def _analog_source(value: Any, name: str = "source") -> str:
    result = _source(value, name)
    if result.startswith("D"):
        raise ValueError(f"{name} must be an analog CHAN1-CHAN4 source")
    return result


def _pattern(value: Any, *, edges: bool, name: str = "pattern") -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object mapping CHAN1-CHAN4 to named states")
    allowed = {"H", "L", "X"} | ({"R", "F"} if edges else set())
    result: dict[str, str] = {}
    for raw_source, raw_state in value.items():
        source = _analog_source(raw_source, f"{name} source")
        if not isinstance(raw_state, str) or raw_state.strip().upper() not in allowed:
            raise ValueError(f"{name}.{source} must be one of {', '.join(sorted(allowed))}")
        result[source] = raw_state.strip().upper()
    if not result:
        raise ValueError(f"{name} must contain at least one named channel")
    edge_count = sum(value in {"R", "F"} for value in result.values())
    if edge_count > 1:
        raise ValueError(f"{name} may contain at most one edge state")
    return result


def _pattern_query(session: Any, command: str, *, edges: bool) -> dict[str, str]:
    parts = [part.strip().upper() for part in str(session.query(command)).split(",") if part.strip()]
    if len(parts) != 4:
        raise ValueError(f"{command} returned {len(parts)} states; expected four")
    return _pattern({f"CHAN{i}": state for i, state in enumerate(parts, 1)}, edges=edges)


def _query_level_map(session: Any, prefix: str, sources: list[str]) -> dict[str, float]:
    result: dict[str, float] = {}
    for source in dict.fromkeys(sources):
        result[source] = _finite(session.query(prefix + "LEVel? " + source), f"level for {source}")
    return result


def _query_pulse_details(session: Any) -> dict[str, Any]:
    prefix = ":TRIGger:PULSe:"
    result = {
        "source": _source(session.query(prefix + "SOURce?")),
        "polarity": _enum(session.query(prefix + "POLarity?"), "polarity", {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE"}),
        "condition": _enum(session.query(prefix + "WHEN?"), "condition", {"GRE": "GREATER", "GREATER": "GREATER", "LESS": "LESS", "GLES": "IN_RANGE", "GLESS": "IN_RANGE", "IN_RANGE": "IN_RANGE"}),
    }
    if result["condition"] in {"GREATER", "IN_RANGE"}:
        result["lower_width_s"] = _trigger_time(session.query(prefix + "LWIDth?"), "lower_width_s")
    if result["condition"] in {"LESS", "IN_RANGE"}:
        result["upper_width_s"] = _trigger_time(session.query(prefix + "UWIDth?"), "upper_width_s")
    result["level"] = _finite(session.query(prefix + "LEVel?"), "level")
    return result


def _query_slope_details(session: Any) -> dict[str, Any]:
    prefix = ":TRIGger:SLOPe:"
    result = {
        "source": _analog_source(session.query(prefix + "SOURce?")),
        "polarity": _enum(session.query(prefix + "POLarity?"), "polarity", {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE"}),
        "condition": _enum(session.query(prefix + "WHEN?"), "condition", {"GRE": "GREATER", "GREATER": "GREATER", "LESS": "LESS", "GLES": "IN_RANGE", "GLESS": "IN_RANGE", "IN_RANGE": "IN_RANGE"}),
        "window": _enum(session.query(prefix + "WINDow?"), "window", {"TA": "TA", "TB": "TB", "TAB": "TAB"}),
        "upper_level": _finite(session.query(prefix + "ALEVel?"), "upper_level"),
        "lower_level": _finite(session.query(prefix + "BLEVel?"), "lower_level"),
    }
    if result["condition"] in {"GREATER", "IN_RANGE"}:
        result["lower_time_s"] = _trigger_time(session.query(prefix + "TLOWer?"), "lower_time_s")
    if result["condition"] in {"LESS", "IN_RANGE"}:
        result["upper_time_s"] = _trigger_time(session.query(prefix + "TUPPer?"), "upper_time_s")
    return result


def _query_video_details(session: Any) -> dict[str, Any]:
    prefix = ":TRIGger:VIDeo:"
    result = {
        "source": _analog_source(session.query(prefix + "SOURce?")),
        "polarity": _enum(session.query(prefix + "POLarity?"), "polarity", {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE"}),
        "sync": _enum(session.query(prefix + "MODE?"), "sync", {"ODDF": "ODD", "ODD": "ODD", "EVEN": "EVEN", "EVENF": "EVEN", "LINE": "LINE", "ALIN": "ALL_LINES", "ALL": "ALL_LINES"}),
        "standard": _enum(session.query(prefix + "STANdard?"), "standard", {name: name for name in _VIDEO_LINES} | {"PALS": "PALSECAM"}),
        "level": _finite(session.query(prefix + "LEVel?"), "level"),
    }
    if result["sync"] == "LINE":
        result["line"] = _integer(session.query(prefix + "LINE?"), "line", 1, _VIDEO_LINES[result["standard"]])
    return result


def _query_pattern_details(session: Any, *, duration: bool) -> dict[str, Any]:
    prefix = ":TRIGger:" + ("DURation:" if duration else "PATTern:")
    result = {"source": _source(session.query(prefix + "SOURce?"))}
    result["pattern"] = _pattern_query(session, prefix + ("TYPE?" if duration else "PATTern?"), edges=not duration)
    if duration:
        result["condition"] = _enum(session.query(prefix + "WHEN?"), "condition", {"GRE": "GREATER", "GREATER": "GREATER", "LESS": "LESS", "GLES": "IN_RANGE", "GLESS": "IN_RANGE", "UNGL": "OUT_RANGE", "UNGLESS": "OUT_RANGE", "OUT_RANGE": "OUT_RANGE"})
        if result["condition"] in {"GREATER", "IN_RANGE", "OUT_RANGE"}:
            result["lower_time_s"] = _trigger_time(session.query(prefix + "TLOWer?"), "lower_time_s")
        if result["condition"] in {"LESS", "IN_RANGE", "OUT_RANGE"}:
            result["upper_time_s"] = _trigger_time(session.query(prefix + "TUPPer?"), "upper_time_s")
    sources = [source for source, state in result["pattern"].items() if state != "X"]
    sources.append(result["source"])
    result["levels"] = _query_level_map(session, prefix, sources)
    result["level"] = result["levels"].get(result["source"])
    return result


def _query_timeout_details(session: Any) -> dict[str, Any]:
    prefix = ":TRIGger:TIMeout:"
    return {
        "source": _source(session.query(prefix + "SOURce?")),
        "slope": _enum(session.query(prefix + "SLOPe?"), "slope", {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE", "RFAL": "BOTH", "RFALL": "BOTH", "BOTH": "BOTH"}),
        "time_s": _trigger_time(session.query(prefix + "TIME?"), "time_s"),
        "level": _finite(session.query(prefix + "LEVel?"), "level"),
    }


def _query_runt_details(session: Any) -> dict[str, Any]:
    prefix = ":TRIGger:RUNT:"
    result = {
        "source": _analog_source(session.query(prefix + "SOURce?")),
        "polarity": _enum(session.query(prefix + "POLarity?"), "polarity", {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE"}),
        "condition": _enum(session.query(prefix + "WHEN?"), "condition", {"NONE": "NONE", "GRE": "GREATER", "GREATER": "GREATER", "LESS": "LESS", "GLES": "IN_RANGE", "GLESS": "IN_RANGE", "IN_RANGE": "IN_RANGE"}),
        "upper_level": _finite(session.query(prefix + "ALEVel?"), "upper_level"),
        "lower_level": _finite(session.query(prefix + "BLEVel?"), "lower_level"),
    }
    if result["condition"] in {"GREATER", "IN_RANGE"}:
        result["lower_width_s"] = _trigger_time(session.query(prefix + "WLOWer?"), "lower_width_s")
    if result["condition"] in {"LESS", "IN_RANGE"}:
        result["upper_width_s"] = _trigger_time(session.query(prefix + "WUPPer?"), "upper_width_s")
    return result


def _query_window_details(session: Any) -> dict[str, Any]:
    prefix = ":TRIGger:WINDows:"
    return {
        "source": _analog_source(session.query(prefix + "SOURce?")),
        "slope": _enum(session.query(prefix + "SLOPe?"), "slope", {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE", "RFAL": "BOTH", "RFALL": "BOTH", "BOTH": "BOTH"}),
        "position": _enum(session.query(prefix + "POSition?"), "position", {"EXIT": "EXIT", "ENT": "ENTER", "ENTER": "ENTER", "TIME": "TIME"}),
        "time_s": _trigger_time(session.query(prefix + "TIME?"), "time_s"),
        "upper_level": _finite(session.query(prefix + "ALEVel?"), "upper_level"),
        "lower_level": _finite(session.query(prefix + "BLEVel?"), "lower_level"),
    }


def _query_delay_details(session: Any) -> dict[str, Any]:
    prefix = ":TRIGger:DELay:"
    result = {
        "source_a": _source(session.query(prefix + "SA?")),
        "slope_a": _enum(session.query(prefix + "ASLop?"), "slope_a", {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE"}),
        "source_b": _source(session.query(prefix + "SB?")),
        "slope_b": _enum(session.query(prefix + "BSLop?"), "slope_b", {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE"}),
        "condition": _enum(session.query(prefix + "TYPE?"), "condition", {"GRE": "GREATER", "GREATER": "GREATER", "LESS": "LESS", "GLES": "IN_RANGE", "GLESS": "IN_RANGE", "GOUT": "OUT_RANGE", "OUT_RANGE": "OUT_RANGE"}),
        "level_a": _finite(session.query(prefix + "ALEVel?"), "level_a"),
        "level_b": _finite(session.query(prefix + "BLEVel?"), "level_b"),
    }
    if result["condition"] in {"GREATER", "IN_RANGE", "OUT_RANGE"}:
        result["lower_time_s"] = _trigger_time(session.query(prefix + "TLOWer?"), "lower_time_s")
    if result["condition"] in {"LESS", "IN_RANGE", "OUT_RANGE"}:
        result["upper_time_s"] = _trigger_time(session.query(prefix + "TUPPer?"), "upper_time_s")
    return result


def _query_setup_details(session: Any) -> dict[str, Any]:
    prefix = ":TRIGger:SHOLd:"
    result = {
        "data_source": _source(session.query(prefix + "DSRC?")),
        "clock_source": _source(session.query(prefix + "CSRC?")),
        "slope": _enum(session.query(prefix + "SLOPe?"), "slope", {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE"}),
        "pattern": _enum(session.query(prefix + "PATTern?"), "pattern", {"H": "HIGH", "HIGH": "HIGH", "L": "LOW", "LOW": "LOW"}),
        "condition": _enum(session.query(prefix + "TYPE?"), "condition", {"SET": "SETUP", "SETUP": "SETUP", "HOLD": "HOLD", "SETH": "BOTH", "BOTH": "BOTH"}),
        "data_level": _finite(session.query(prefix + "DLEVel?"), "data_level"),
        "clock_level": _finite(session.query(prefix + "CLEVel?"), "clock_level"),
    }
    if result["condition"] in {"SETUP", "BOTH"}:
        result["setup_time_s"] = _trigger_time(session.query(prefix + "STIMe?"), "setup_time_s")
    if result["condition"] in {"HOLD", "BOTH"}:
        result["hold_time_s"] = _trigger_time(session.query(prefix + "HTIMe?"), "hold_time_s")
    return result


def _query_nedge_details(session: Any) -> dict[str, Any]:
    prefix = ":TRIGger:NEDGe:"
    return {
        "source": _source(session.query(prefix + "SOURce?")),
        "slope": _enum(session.query(prefix + "SLOPe?"), "slope", {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE"}),
        "idle_time_s": _trigger_time(session.query(prefix + "IDLE?"), "idle_time_s", 16e-9),
        "edge_count": _integer(session.query(prefix + "EDGE?"), "edge_count", 1, 65_535),
        "level": _finite(session.query(prefix + "LEVel?"), "level"),
    }


def _bit_code(value: Any) -> int:
    result = _integer(value, "bit_code", 0, 255)
    if result not in {0, 1, 255}:
        raise ValueError("bit_code must be 0, 1, or 255")
    return result


def _comparison(value: Any, name: str) -> str:
    return _enum(value, name, {
        "EQU": "EQUAL", "EQUAL": "EQUAL", "NOT": "NOT_EQUAL", "NOTEQUAL": "NOT_EQUAL",
        "GRE": "GREATER_THAN", "GREATER": "GREATER_THAN", "GREATERTHAN": "GREATER_THAN",
        "LESS": "LESS_THAN", "LESSTHAN": "LESS_THAN", "INR": "IN_RANGE", "INRANGE": "IN_RANGE", "IN_RANGE": "IN_RANGE",
        "OUTR": "OUT_RANGE", "OUTRANGE": "OUT_RANGE", "OUT_RANGE": "OUT_RANGE",
    })


def _stop_bits(value: Any) -> int | float:
    result = _finite(value, "stop_bits")
    if result not in {1.0, 1.5, 2.0}:
        raise ValueError("stop_bits must be 1, 1.5, or 2")
    return int(result) if result.is_integer() else result


def _query_protocol_details(session: Any, protocol: str) -> dict[str, Any]:
    if protocol == "I2C":
        return _query_i2c_details(session)
    if protocol == "SPI":
        return _query_spi_details(session)
    if protocol == "RS232":
        return _query_rs232_details(session)
    if protocol == "CAN":
        return _query_can_details(session)
    if protocol == "LIN":
        return _query_lin_details(session)
    if protocol == "I2S":
        return _query_i2s_details(session)
    if protocol == "FLEXRAY":
        return _query_flexray_details(session)
    if protocol == "M1553":
        return _query_m1553_details(session)
    if protocol == "PULSE":
        return _query_pulse_details(session)
    if protocol == "SLOPE":
        return _query_slope_details(session)
    if protocol == "VIDEO":
        return _query_video_details(session)
    if protocol == "PATTERN":
        return _query_pattern_details(session, duration=False)
    if protocol == "DURATION":
        return _query_pattern_details(session, duration=True)
    if protocol == "TIMEOUT":
        return _query_timeout_details(session)
    if protocol == "RUNT":
        return _query_runt_details(session)
    if protocol == "WINDOW":
        return _query_window_details(session)
    if protocol == "DELAY":
        return _query_delay_details(session)
    if protocol == "SETUP":
        return _query_setup_details(session)
    return _query_nedge_details(session)


def _scope(protocol: str | None = None, *, supported: bool) -> dict[str, Any]:
    result = {
        "supported_protocols": list(_SUPPORTED_PROTOCOLS),
        "aliases": {"IIC": "I2C", "I2C": "I2C", "UART": "RS232", "IIS": "I2S", "I2S": "I2S", "FLEX": "FLEXRAY"},
        "details_supported": supported,
    }
    if protocol is not None:
        result["protocol"] = protocol
    if not supported:
        result["reason"] = "No named detail schema is implemented for this trigger mode."
    return result


def get_trigger(session: Any) -> dict[str, Any]:
    """Read common fields plus condition-valid named communication details."""
    result = _query_global(session)
    if result["mode"] == "EDGE":
        # Keep the historical EDGE readback contract, including its fields.
        result.update(_query_edge(session))
        return result
    protocol = _MODE_PROTOCOL.get(result["mode"])
    if protocol is not None:
        result["protocol"] = protocol
        result["details"] = _query_protocol_details(session, protocol)
        result["scope"] = _scope(protocol, supported=True)
    else:
        result["scope"] = _scope(supported=False)
    return result


def _level_bounds(session: Any, source: str) -> tuple[float, float]:
    if source.startswith("D"):
        return -15.0, 15.0
    scale = _finite(session.query(f":CHANnel{source[-1]}:SCALe?"), "scale_v_div")
    offset = _finite(session.query(f":CHANnel{source[-1]}:OFFSet?"), "offset_v")
    return -4.5 * scale - offset, 4.5 * scale - offset


def _normalise_details(value: Any, protocol: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("details must be an object of named protocol fields; raw SCPI is unsupported")
    aliases = _DETAIL_ALIASES[protocol]
    result: dict[str, Any] = {}
    for raw_name, raw_value in value.items():
        if not isinstance(raw_name, str):
            raise ValueError("details field names must be strings")
        name = raw_name.strip().lower()
        canonical = aliases.get(name, name)
        if canonical not in _DETAIL_FIELDS[protocol]:
            raise ValueError(f"{raw_name} is not a supported {protocol} trigger detail")
        if canonical in result:
            raise ValueError(f"details contains duplicate aliases for {canonical}")
        result[canonical] = raw_value
    return result


def _validate_new_details(protocol: str, submitted: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if protocol == "CAN":
        if "source" in submitted: result["source"] = _source(submitted["source"], "details.source")
        if "level" in submitted: result["level"] = _finite(submitted["level"], "details.level")
        if "baud" in submitted: result["baud"] = _integer(submitted["baud"], "details.baud", 10_000, 5_000_000)
        if "signal_type" in submitted: result["signal_type"] = _enum(submitted["signal_type"], "details.signal_type", {"H": "H", "L": "L", "RXTX": "RXTX", "DIFF": "DIFFERENTIAL", "DIFFERENTIAL": "DIFFERENTIAL"})
        if "condition" in submitted: result["condition"] = _enum(submitted["condition"], "details.condition", {
            "SOF": "SOF", "EOF": "EOF", "ID_REMOTE": "ID_REMOTE", "IDR": "ID_REMOTE", "IDREMOTE": "ID_REMOTE", "OVERLOAD": "OVERLOAD", "OVER": "OVERLOAD", "ID_FRAME": "ID_FRAME", "IDFR": "ID_FRAME", "IDFRAME": "ID_FRAME", "DATA_FRAME": "DATA_FRAME", "DAT": "DATA_FRAME", "DATAFRAME": "DATA_FRAME", "ID_DATA": "ID_DATA", "IDD": "ID_DATA", "IDDATA": "ID_DATA", "ERROR_FRAME": "ERROR_FRAME", "ERFR": "ERROR_FRAME", "ERFRAME": "ERROR_FRAME", "ERROR_ANSWER": "ERROR_ANSWER", "ERAN": "ERROR_ANSWER", "ERROR_CHECK": "ERROR_CHECK", "ERCH": "ERROR_CHECK", "ERROR_FORMAT": "ERROR_FORMAT", "ERF": "ERROR_FORMAT", "ERROR_RANDOM": "ERROR_RANDOM", "ERR": "ERROR_RANDOM", "ERROR_BIT": "ERROR_BIT", "ERB": "ERROR_BIT",
        })
        if "sample_point" in submitted: result["sample_point"] = _integer(submitted["sample_point"], "details.sample_point", 10, 90)
        if "extended_id" in submitted: result["extended_id"] = _bool(submitted["extended_id"], "details.extended_id")
        if "define" in submitted: result["define"] = _enum(submitted["define"], "details.define", {"DATA": "DATA", "FALSE": "DATA", "ID": "ID", "TRUE": "ID"})
        if "data_width" in submitted: result["data_width"] = _integer(submitted["data_width"], "details.data_width", 1, 8)
        if "data" in submitted: result["data"] = _integer(submitted["data"], "details.data", 0, (1 << 64) - 1)
        if "current_bit" in submitted: result["current_bit"] = _integer(submitted["current_bit"], "details.current_bit", 0, 39)
        if "bit_code" in submitted: result["bit_code"] = _bit_code(submitted["bit_code"])
    elif protocol == "LIN":
        if "source" in submitted: result["source"] = _source(submitted["source"], "details.source")
        if "level" in submitted: result["level"] = _finite(submitted["level"], "details.level")
        if "standard" in submitted: result["standard"] = _enum(submitted["standard"], "details.standard", {"1X": "1X", "2X": "2X", "BOTH": "BOTH"})
        if "baud" in submitted: result["baud"] = _integer(submitted["baud"], "details.baud", 1_000, 20_000_000)
        if "sample_point" in submitted: result["sample_point"] = _integer(submitted["sample_point"], "details.sample_point", 10, 90)
        if "condition" in submitted: result["condition"] = _enum(submitted["condition"], "details.condition", {"SYNC_BREAK": "SYNC_BREAK", "SYNC": "SYNC_BREAK", "ID": "ID", "DATA": "DATA", "ID_DATA": "ID_DATA", "IDD": "ID_DATA", "SLEEP": "SLEEP", "SLE": "SLEEP", "WAKEUP": "WAKEUP", "WAK": "WAKEUP", "ERROR": "ERROR", "ERR": "ERROR"})
        if "error" in submitted: result["error"] = _enum(submitted["error"], "details.error", {"SYNC": "SYNC", "ID": "ID", "CHECKSUM": "CHECKSUM", "CHECK": "CHECKSUM"})
        if "id" in submitted: result["id"] = _integer(submitted["id"], "details.id", 0, 63)
        if "data" in submitted: result["data"] = _integer(submitted["data"], "details.data", 0, (1 << 64) - 1)
        if "current_bit" in submitted: result["current_bit"] = _integer(submitted["current_bit"], "details.current_bit", 0, 39)
        if "bit_code" in submitted: result["bit_code"] = _bit_code(submitted["bit_code"])
    elif protocol == "I2S":
        for field in ("clock_source", "data_source", "ws_source"):
            if field in submitted: result[field] = _source(submitted[field], f"details.{field}")
        for field in ("clock_level", "frame_level", "data_level"):
            if field in submitted: result[field] = _finite(submitted[field], f"details.{field}")
        enums = {
            "alignment": {"LJ": "LJ", "RJ": "RJ", "IIS": "IIS"}, "clock_slope": {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE"},
            "condition": {"EQUAL": "EQUAL", "EQU": "EQUAL", "NOT_EQUAL": "NOT_EQUAL", "NOT": "NOT_EQUAL", "LESS_THAN": "LESS_THAN", "LESS": "LESS_THAN", "GREATER_THAN": "GREATER_THAN", "GRE": "GREATER_THAN", "IN_RANGE": "IN_RANGE", "INR": "IN_RANGE", "OUT_RANGE": "OUT_RANGE", "OUTR": "OUT_RANGE"},
            "audio": {"RIGHT": "RIGHT", "RIGH": "RIGHT", "LEFT": "LEFT", "EITHER": "EITHER", "EITH": "EITHER"},
        }
        for field, aliases in enums.items():
            if field in submitted: result[field] = _enum(submitted[field], f"details.{field}", aliases)
        if "user_width" in submitted: result["user_width"] = _integer(submitted["user_width"], "details.user_width", 4, 32)
        if "width" in submitted: result["width"] = _integer(submitted["width"], "details.width", 4, 32)
        for field in ("data_min_bit", "data_max_bit"):
            if field in submitted: result[field] = _integer(submitted[field], f"details.{field}", 0, 31)
        if "bit_code" in submitted: result["bit_code"] = _bit_code(submitted["bit_code"])
        if "data" in submitted: result["data"] = _integer(submitted["data"], "details.data", 0, (1 << 32) - 1)
    elif protocol == "FLEXRAY":
        if "source" in submitted: result["source"] = _source(submitted["source"], "details.source")
        if "level" in submitted: result["level"] = _finite(submitted["level"], "details.level")
        if "baud" in submitted:
            result["baud"] = _integer(submitted["baud"], "details.baud", 2_500_000, 10_000_000)
            if result["baud"] not in {2_500_000, 5_000_000, 10_000_000}: raise ValueError("details.baud must be 2500000, 5000000, or 10000000")
        aliases = {
            "condition": {"FRAME": "FRAME", "FRAM": "FRAME", "SYMBOL": "SYMBOL", "SYMB": "SYMBOL", "ERROR": "ERROR", "ERR": "ERROR", "TSS": "TSS"}, "position": {"TSS": "TSS", "FSS": "FSS", "FES": "FES", "DTS": "DTS"}, "error": {"HEADER": "HEADER", "HEAD": "HEADER", "TRAILER": "TRAILER", "TRA": "TRAILER", "DECODE": "DECODE", "DEC": "DECODE", "ANY": "ANY"}, "symbol": {"CAS": "CAS", "WUS": "WUS"}, "frame": {"NULL": "NULL", "SYNC": "SYNC", "STARTUP": "STARTUP", "STAR": "STARTUP", "ANY": "ANY"}, "define": {"CYCLE": "CYCLE", "CYCL": "CYCLE", "ID": "ID", "FALSE": "ID", "TRUE": "CYCLE"}, "channel": {"A": "A", "B": "B"},
        }
        for field, field_aliases in aliases.items():
            if field in submitted: result[field] = _enum(submitted[field], f"details.{field}", field_aliases)
        for field in ("id_comparison", "cycle_comparison"):
            if field in submitted: result[field] = _comparison(submitted[field], f"details.{field}")
        for field, high in (("max_cycle", 63), ("min_cycle", 63), ("max_id", 1023), ("min_id", 1023)):
            if field in submitted: result[field] = _integer(submitted[field], f"details.{field}", 0, high)
    else:
        if "source" in submitted: result["source"] = _source(submitted["source"], "details.source")
        if "condition" in submitted: result["condition"] = _enum(submitted["condition"], "details.condition", {"SYNC_BREAK": "SYNC_BREAK", "SYNC": "SYNC_BREAK", "DATA": "DATA", "COMMAND": "COMMAND", "CMD": "COMMAND", "STATUS": "STATUS", "STAT": "STATUS", "ERROR": "ERROR", "ERR": "ERROR"})
        for field, aliases in {
            "polarity": {"POSITIVE": "POSITIVE", "POS": "POSITIVE", "NEGATIVE": "NEGATIVE", "NEG": "NEGATIVE"}, "window": {"TA": "TA", "TB": "TB", "TAB": "TAB"}, "sync": {"DATA": "DATA", "STATUS": "STATUS", "STAT": "STATUS", "ALL": "ALL"}, "error": {"SYNC": "SYNC", "ERROR": "ERROR", "ERR": "ERROR"},
        }.items():
            if field in submitted: result[field] = _enum(submitted[field], f"details.{field}", aliases)
        if "data_comparison" in submitted: result["data_comparison"] = _comparison(submitted["data_comparison"], "details.data_comparison")
        if "data_value" in submitted: result["data_value"] = _integer(submitted["data_value"], "details.data_value", 0, 65_535)
        for field in ("data_min_bit", "data_max_bit"): 
            if field in submitted: result[field] = _integer(submitted[field], f"details.{field}", 0, 19)
        if "remote_terminal_address" in submitted: result["remote_terminal_address"] = _integer(submitted["remote_terminal_address"], "details.remote_terminal_address", 0, 6)
        if "data_bit" in submitted: result["data_bit"] = _integer(submitted["data_bit"], "details.data_bit", 0, 13)
        if "bit_code" in submitted: result["bit_code"] = _bit_code(submitted["bit_code"])
        for field in ("level_a", "level_b"):
            if field in submitted: result[field] = _finite(submitted[field], f"details.{field}")
    return result


def _validate_nonserial_details(protocol: str, submitted: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if "source" in submitted:
        result["source"] = (_analog_source(submitted["source"], "details.source")
                             if protocol in {"SLOPE", "VIDEO", "RUNT", "WINDOW"}
                             else _source(submitted["source"], "details.source"))
    if protocol == "DELAY":
        for field in ("source_a", "source_b"):
            if field in submitted:
                result[field] = _source(submitted[field], f"details.{field}")
        for field in ("slope_a", "slope_b"):
            if field in submitted:
                result[field] = _enum(submitted[field], f"details.{field}", {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE"})
    if protocol == "SETUP":
        for field in ("data_source", "clock_source"):
            if field in submitted:
                result[field] = _source(submitted[field], f"details.{field}")
    if protocol not in {"VIDEO", "DELAY", "SETUP", "PATTERN", "DURATION"} and "polarity" in submitted:
        result["polarity"] = _enum(submitted["polarity"], "details.polarity", {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE"})
    if protocol in {"SLOPE", "TIMEOUT", "WINDOW", "NEDGE", "SETUP"} and "slope" in submitted:
        result["slope"] = _enum(submitted["slope"], "details.slope", {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE", "RFAL": "BOTH", "RFALL": "BOTH", "BOTH": "BOTH"})
    if protocol == "SETUP" and "pattern" in submitted:
        result["pattern"] = _enum(submitted["pattern"], "details.pattern", {"H": "HIGH", "HIGH": "HIGH", "L": "LOW", "LOW": "LOW"})
    elif "pattern" in submitted:
        result["pattern"] = _pattern(submitted["pattern"], edges=protocol == "PATTERN", name="details.pattern")
    if protocol in {"PULSE", "SLOPE", "DURATION", "RUNT", "DELAY"} and "condition" in submitted:
        aliases = {"GREATER": "GREATER", "GRE": "GREATER", "LESS": "LESS", "GLES": "IN_RANGE", "IN_RANGE": "IN_RANGE"}
        if protocol == "DURATION": aliases |= {"UNGL": "OUT_RANGE", "OUT_RANGE": "OUT_RANGE"}
        if protocol == "RUNT": aliases = {"NONE": "NONE", **aliases}
        if protocol == "DELAY": aliases |= {"GOUT": "OUT_RANGE", "OUT_RANGE": "OUT_RANGE"}
        result["condition"] = _enum(submitted["condition"], "details.condition", aliases)
    if protocol == "VIDEO":
        if "polarity" in submitted:
            result["polarity"] = _enum(submitted["polarity"], "details.polarity", {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE"})
        if "sync" in submitted:
            result["sync"] = _enum(submitted["sync"], "details.sync", {"ODD": "ODD", "ODDF": "ODD", "EVEN": "EVEN", "EVENF": "EVEN", "LINE": "LINE", "ALL": "ALL_LINES", "ALL_LINES": "ALL_LINES", "ALIN": "ALL_LINES"})
        if "standard" in submitted:
            result["standard"] = _enum(submitted["standard"], "details.standard", {name: name for name in _VIDEO_LINES} | {"PALS": "PALSECAM", "PALSECAM": "PALSECAM"})
    if protocol == "WINDOW" and "position" in submitted:
        result["position"] = _enum(submitted["position"], "details.position", {"EXIT": "EXIT", "ENTER": "ENTER", "ENT": "ENTER", "TIME": "TIME"})
    if protocol == "SETUP" and "condition" in submitted:
        result["condition"] = _enum(submitted["condition"], "details.condition", {"SETUP": "SETUP", "SET": "SETUP", "HOLD": "HOLD", "BOTH": "BOTH", "SETH": "BOTH", "SETHOLD": "BOTH"})
    if protocol == "VIDEO" and "line" in submitted:
        result["line"] = _integer(submitted["line"], "details.line", 1, 1125)
    for field in ("upper_width_s", "lower_width_s", "upper_time_s", "lower_time_s", "time_s", "setup_time_s", "hold_time_s"):
        if field in submitted:
            result[field] = _trigger_time(submitted[field], f"details.{field}")
    if "idle_time_s" in submitted:
        result["idle_time_s"] = _trigger_time(submitted["idle_time_s"], "details.idle_time_s", 16e-9)
    if "edge_count" in submitted:
        result["edge_count"] = _integer(submitted["edge_count"], "details.edge_count", 1, 65_535)
    for field in ("level", "upper_level", "lower_level", "data_level", "clock_level", "level_a", "level_b"):
        if field in submitted:
            result[field] = _finite(submitted[field], f"details.{field}")
    for field in ("levels",):
        if field in submitted:
            if not isinstance(submitted[field], Mapping):
                raise ValueError("details.levels must be an object mapping named sources to levels")
            values: dict[str, float] = {}
            for raw_source, raw_level in submitted[field].items():
                source = _source(raw_source, "details.levels source")
                values[source] = _finite(raw_level, f"details.levels.{source}")
            result[field] = values
    if protocol == "SLOPE" and "window" in submitted:
        result["window"] = _enum(submitted["window"], "details.window", {"TA": "TA", "TB": "TB", "TAB": "TAB"})
    return result


def _validate_details(protocol: str, submitted: Mapping[str, Any]) -> dict[str, Any]:
    if protocol in {"PULSE", "SLOPE", "VIDEO", "PATTERN", "DURATION", "TIMEOUT", "RUNT", "WINDOW", "DELAY", "SETUP", "NEDGE"}:
        return _validate_nonserial_details(protocol, submitted)
    if protocol in {"CAN", "LIN", "I2S", "FLEXRAY", "M1553"}:
        return _validate_new_details(protocol, submitted)
    result: dict[str, Any] = {}
    if protocol == "I2C":
        if "scl_source" in submitted:
            result["scl_source"] = _source(submitted["scl_source"], "details.scl_source")
        if "scl_level" in submitted:
            result["scl_level"] = _finite(submitted["scl_level"], "details.scl_level")
        if "sda_source" in submitted:
            result["sda_source"] = _source(submitted["sda_source"], "details.sda_source")
        if "sda_level" in submitted:
            result["sda_level"] = _finite(submitted["sda_level"], "details.sda_level")
        if "condition" in submitted:
            result["condition"] = _enum(submitted["condition"], "details.condition", {
                "START": "START", "STAR": "START", "RESTART": "RESTART", "REST": "RESTART",
                "STOP": "STOP", "NACK": "NACK", "NACKNOWLEDGE": "NACK", "ADDRESS": "ADDRESS", "ADDR": "ADDRESS",
                "DATA": "DATA", "ADDRESS_DATA": "ADDRESS_DATA", "ADAT": "ADDRESS_DATA", "ADATA": "ADDRESS_DATA",
            })
        if "address_width" in submitted:
            width = _integer(submitted["address_width"], "details.address_width", 7, 10)
            if width not in {7, 8, 10}:
                raise ValueError("details.address_width must be 7, 8, or 10")
            result["address_width"] = width
        if "address" in submitted:
            result["address"] = _integer(submitted["address"], "details.address", 0, (1 << 10) - 1)
        if "direction" in submitted:
            result["direction"] = _enum(submitted["direction"], "details.direction", {
                "READ": "READ", "WRITE": "WRITE", "WRIT": "WRITE", "READ_WRITE": "READ_WRITE", "RWRITE": "READ_WRITE", "RWR": "READ_WRITE",
            })
        if "data_bytes" in submitted:
            result["data_bytes"] = _integer(submitted["data_bytes"], "details.data_bytes", 1, 5)
        if "data" in submitted:
            result["data"] = _integer(submitted["data"], "details.data", 0, (1 << 40) - 1)
        if "current_bit" in submitted:
            result["current_bit"] = _integer(submitted["current_bit"], "details.current_bit", 0, 39)
        if "bit_code" in submitted:
            result["bit_code"] = _integer(submitted["bit_code"], "details.bit_code", 0, 255)
            if result["bit_code"] not in {0, 1, 255}:
                raise ValueError("details.bit_code must be 0, 1, or 255")
    elif protocol == "SPI":
        for field, name in (("clock_source", "clock_source"), ("data_source", "data_source"), ("cs_source", "cs_source")):
            if field in submitted:
                result[field] = _source(submitted[field], f"details.{name}")
        for field in ("clock_level", "data_level", "cs_level"):
            if field in submitted:
                result[field] = _finite(submitted[field], f"details.{field}")
        if "clock_slope" in submitted:
            result["clock_slope"] = _enum(submitted["clock_slope"], "details.clock_slope", {
                "POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE",
            })
        if "condition" in submitted:
            result["condition"] = _enum(submitted["condition"], "details.condition", {"CS": "CS", "TIMEOUT": "TIMEOUT", "TIM": "TIMEOUT"})
        if "cs_mode" in submitted:
            result["cs_mode"] = _enum(submitted["cs_mode"], "details.cs_mode", {"HIGH": "HIGH", "LOW": "LOW"})
        if "timeout_s" in submitted:
            result["timeout_s"] = _finite(submitted["timeout_s"], "details.timeout_s")
            if not 8e-9 <= result["timeout_s"] <= 10.0:
                raise ValueError("details.timeout_s must be between 8 ns and 10 s")
        if "data_width" in submitted:
            result["data_width"] = _integer(submitted["data_width"], "details.data_width", 4, 32)
        if "data" in submitted:
            result["data"] = _integer(submitted["data"], "details.data", 0, (1 << 32) - 1)
        if "current_bit" in submitted:
            result["current_bit"] = _integer(submitted["current_bit"], "details.current_bit", 0, 39)
        if "bit_code" in submitted:
            result["bit_code"] = _integer(submitted["bit_code"], "details.bit_code", 0, 255)
            if result["bit_code"] not in {0, 1, 255}:
                raise ValueError("details.bit_code must be 0, 1, or 255")
    else:
        if "source" in submitted:
            result["source"] = _source(submitted["source"], "details.source")
        if "level" in submitted:
            result["level"] = _finite(submitted["level"], "details.level")
        if "polarity" in submitted:
            result["polarity"] = _enum(submitted["polarity"], "details.polarity", {
                "POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE",
            })
        if "condition" in submitted:
            result["condition"] = _enum(submitted["condition"], "details.condition", {
                "START": "START", "STAR": "START", "ERROR": "ERROR", "ERR": "ERROR",
                "CHECK_ERROR": "CHECK_ERROR", "CHECKERROR": "CHECK_ERROR", "CERR": "CHECK_ERROR", "DATA": "DATA",
            })
        if "data" in submitted:
            result["data"] = _integer(submitted["data"], "details.data", 0, (1 << 8) - 1)
        if "baud" in submitted:
            result["baud"] = _integer(submitted["baud"], "details.baud", 1, 20_000_000)
        if "data_width" in submitted:
            result["data_width"] = _integer(submitted["data_width"], "details.data_width", 5, 8)
        if "stop_bits" in submitted:
            result["stop_bits"] = _stop_bits(submitted["stop_bits"])
        if "parity" in submitted:
            result["parity"] = _enum(submitted["parity"], "details.parity", {"EVEN": "EVEN", "ODD": "ODD", "NONE": "NONE"})
    return result


def _validate_new_relevance(protocol: str, requested: Mapping[str, Any], final: Mapping[str, Any]) -> None:
    condition = final.get("condition")
    if protocol == "CAN":
        if "extended_id" in requested and condition not in {"ID_REMOTE", "ID_FRAME"}: raise ValueError("CAN extended_id requires condition ID_REMOTE or ID_FRAME")
        if "define" in requested and condition != "ID_DATA": raise ValueError("CAN define requires condition ID_DATA")
        if requested.keys() & {"data_width", "data", "current_bit", "bit_code"} and condition not in {"DATA_FRAME", "ID_DATA"}: raise ValueError("CAN data details require condition DATA_FRAME or ID_DATA")
        if "data" in requested and final.get("define", "DATA") == "DATA" and requested["data"] > (1 << (8 * final.get("data_width", 1))) - 1: raise ValueError("CAN data exceeds the selected data_width")
    elif protocol == "LIN":
        if "error" in requested and condition != "ERROR": raise ValueError("LIN error requires condition ERROR")
        if "id" in requested and condition not in {"ID", "ID_DATA"}: raise ValueError("LIN id requires condition ID or ID_DATA")
        if requested.keys() & {"data", "current_bit", "bit_code"} and condition not in {"DATA", "ID_DATA"}: raise ValueError("LIN data details require condition DATA or ID_DATA")
    elif protocol == "I2S":
        if "data" in requested and condition not in {"EQUAL", "NOT_EQUAL"}: raise ValueError("I2S data requires condition EQUAL or NOT_EQUAL")
        if requested.keys() & {"data_min_bit", "data_max_bit", "bit_code"} and condition not in {"IN_RANGE", "OUT_RANGE"}: raise ValueError("I2S data min/max bit details require condition IN_RANGE or OUT_RANGE")
        width, user_width = final.get("width", 4), final.get("user_width", final.get("width", 4))
        if user_width > width: raise ValueError("I2S user_width cannot exceed width")
        if "data" in requested and requested["data"] > (1 << width) - 1: raise ValueError("I2S data exceeds the selected width")
        for field in ("data_min_bit", "data_max_bit"):
            if field in requested and requested[field] >= user_width: raise ValueError(f"I2S {field} must be below user_width")
    elif protocol == "FLEXRAY":
        if "position" in requested and condition != "TSS": raise ValueError("FlexRay position requires condition TSS")
        if "error" in requested and condition != "ERROR": raise ValueError("FlexRay error requires condition ERROR")
        if "symbol" in requested and condition != "SYMBOL": raise ValueError("FlexRay symbol requires condition SYMBOL")
        if requested.keys() & {"frame", "define", "cycle_comparison", "max_cycle", "min_cycle", "max_id", "min_id"} and condition != "FRAME": raise ValueError("FlexRay frame details require condition FRAME")
        if "id_comparison" in requested and condition not in {"FRAME", "SYMBOL"}: raise ValueError("FlexRay id_comparison requires condition FRAME or SYMBOL")
        if requested.keys() & {"cycle_comparison", "max_cycle", "min_cycle"} and final.get("define", "ID") != "CYCLE": raise ValueError("FlexRay cycle details require define CYCLE")
        if requested.keys() & {"max_id", "min_id"} and condition == "FRAME" and final.get("define", "ID") != "ID": raise ValueError("FlexRay ID range details require define ID")
        if "max_cycle" in final and "min_cycle" in final and final["max_cycle"] < final["min_cycle"]: raise ValueError("FlexRay max_cycle must be greater than or equal to min_cycle")
        if "max_id" in final and "min_id" in final and final["max_id"] < final["min_id"]: raise ValueError("FlexRay max_id must be greater than or equal to min_id")
    else:
        if "sync" in requested and condition != "SYNC_BREAK": raise ValueError("M1553 sync requires condition SYNC_BREAK")
        if "error" in requested and condition != "ERROR": raise ValueError("M1553 error requires condition ERROR")
        if requested.keys() & {"data_comparison", "data_value", "data_min_bit", "data_max_bit"} and condition != "DATA": raise ValueError("M1553 data details require condition DATA")
        if "remote_terminal_address" in requested and condition not in {"COMMAND", "STATUS"}: raise ValueError("M1553 remote_terminal_address requires condition COMMAND or STATUS")
        if "data_bit" in requested and condition != "STATUS": raise ValueError("M1553 data_bit requires condition STATUS")
        if "bit_code" in requested and condition not in {"DATA", "STATUS"}: raise ValueError("M1553 bit_code requires condition DATA or STATUS")
        if "level_a" in final and "level_b" in final and final["level_a"] < final["level_b"]: raise ValueError("M1553 level_a must be greater than or equal to level_b")


def _validate_detail_relevance(protocol: str, requested: Mapping[str, Any], final: Mapping[str, Any]) -> None:
    if protocol in {"PULSE", "SLOPE", "DURATION", "RUNT", "DELAY"}:
        condition = final.get("condition")
        if protocol == "RUNT" and condition == "NONE":
            if requested.keys() & {"upper_width_s", "lower_width_s"}:
                raise ValueError("RUNT width details require condition GREATER, LESS, or IN_RANGE")
        lower_fields = {"lower_width_s", "lower_time_s"}
        upper_fields = {"upper_width_s", "upper_time_s"}
        if "lower_width_s" in requested and condition not in {"GREATER", "IN_RANGE", "OUT_RANGE"}:
            raise ValueError(f"{protocol} lower_width_s is unavailable for condition {condition}")
        if "upper_width_s" in requested and condition not in {"LESS", "IN_RANGE", "OUT_RANGE"}:
            raise ValueError(f"{protocol} upper_width_s is unavailable for condition {condition}")
        if "lower_time_s" in requested and condition not in {"GREATER", "IN_RANGE", "OUT_RANGE"}:
            raise ValueError(f"{protocol} lower_time_s is unavailable for condition {condition}")
        if "upper_time_s" in requested and condition not in {"LESS", "IN_RANGE", "OUT_RANGE"}:
            raise ValueError(f"{protocol} upper_time_s is unavailable for condition {condition}")
        lower = final.get(next(iter(lower_fields & set(final)), None))
        upper = final.get(next(iter(upper_fields & set(final)), None))
        if lower is not None and upper is not None and lower > upper:
            raise ValueError(f"{protocol} lower limit must be less than or equal to upper limit")
        if protocol == "SLOPE":
            low_level, high_level = final.get("lower_level"), final.get("upper_level")
            if low_level is not None and high_level is not None and low_level > high_level:
                raise ValueError("SLOPE lower level must be less than or equal to upper level")
        return
    if protocol == "VIDEO":
        if "line" in requested and final.get("sync") != "LINE":
            raise ValueError("VIDEO line requires sync LINE")
        if "line" in final and "standard" in final and final["line"] > _VIDEO_LINES[final["standard"]]:
            raise ValueError("VIDEO line exceeds the selected standard")
        return
    if protocol in {"PATTERN", "DURATION"}:
        if "pattern" in requested:
            pattern = final["pattern"]
            if protocol == "PATTERN" and sum(state in {"R", "F"} for state in pattern.values()) > 1:
                raise ValueError("PATTERN may contain at most one edge state")
        if protocol == "DURATION":
            condition = final.get("condition")
            if "lower_time_s" in requested and condition not in {"GREATER", "IN_RANGE", "OUT_RANGE"}:
                raise ValueError("DURATION lower_time_s is unavailable for this condition")
            if "upper_time_s" in requested and condition not in {"LESS", "IN_RANGE", "OUT_RANGE"}:
                raise ValueError("DURATION upper_time_s is unavailable for this condition")
            lower, upper = final.get("lower_time_s"), final.get("upper_time_s")
            if lower is not None and upper is not None and lower > upper:
                raise ValueError("DURATION lower limit must be less than or equal to upper limit")
        return
    if protocol in {"SLOPE", "RUNT", "WINDOW"}:
        lower, upper = final.get("lower_level"), final.get("upper_level")
        if lower is not None and upper is not None and lower > upper:
            raise ValueError(f"{protocol} lower level must be less than or equal to upper level")
        return
    if protocol == "SETUP":
        condition = final.get("condition")
        if "setup_time_s" in requested and condition not in {"SETUP", "BOTH"}:
            raise ValueError("SETUP setup_time_s is unavailable for condition HOLD")
        if "hold_time_s" in requested and condition not in {"HOLD", "BOTH"}:
            raise ValueError("SETUP hold_time_s is unavailable for condition SETUP")
        return
    if protocol in {"CAN", "LIN", "I2S", "FLEXRAY", "M1553"}:
        _validate_new_relevance(protocol, requested, final)
        return
    condition = final.get("condition")
    if protocol == "I2C":
        address_fields = {"address_width", "address", "direction"}
        data_fields = {"data_bytes", "data", "current_bit", "bit_code"}
        if requested.keys() & address_fields and condition not in {"ADDRESS", "ADDRESS_DATA"}:
            raise ValueError("I2C address and direction details require condition ADDRESS or ADDRESS_DATA")
        if requested.keys() & data_fields and condition not in {"DATA", "ADDRESS_DATA"}:
            raise ValueError("I2C data details require condition DATA or ADDRESS_DATA")
        if "direction" in requested and final.get("address_width", 7) == 8:
            raise ValueError("I2C direction is unavailable when address_width is 8")
        if "address" in requested and requested["address"] > (1 << final.get("address_width", 7)) - 1:
            raise ValueError("I2C address exceeds the selected address_width")
        if "data" in requested and requested["data"] > (1 << (8 * final.get("data_bytes", 1))) - 1:
            raise ValueError("I2C data exceeds the selected data_bytes")
    elif protocol == "SPI":
        if requested.keys() & {"cs_source", "cs_level", "cs_mode"} and condition != "CS":
            raise ValueError("SPI CS details require condition CS")
        if "timeout_s" in requested and condition != "TIMEOUT":
            raise ValueError("SPI timeout_s requires condition TIMEOUT")
        if "data" in requested and requested["data"] > (1 << final.get("data_width", 8)) - 1:
            raise ValueError("SPI data exceeds the selected data_width")
    elif protocol == "RS232":
        if "data" in requested and requested["data"] > (1 << final.get("data_width", 8)) - 1:
            raise ValueError("RS232 data exceeds the selected data_width")
        if requested.keys() & {"data", "data_width"} and condition != "DATA":
            raise ValueError("RS232 data and data_width require condition DATA")


def _validate_detail_levels(session: Any, protocol: str, requested: Mapping[str, Any], final: Mapping[str, Any]) -> None:
    if protocol in {"PULSE", "VIDEO", "TIMEOUT", "NEDGE"}:
        fields = {"level": final.get("source", "CHAN1")}
    elif protocol in {"SLOPE", "RUNT", "WINDOW"}:
        fields = {"upper_level": final.get("source", "CHAN1"), "lower_level": final.get("source", "CHAN1")}
    elif protocol in {"PATTERN", "DURATION"}:
        fields = {"level": final.get("source", "CHAN1")}
    elif protocol == "DELAY":
        fields = {"level_a": final.get("source_a", "CHAN1"), "level_b": final.get("source_b", "CHAN2")}
    elif protocol == "SETUP":
        fields = {"data_level": final.get("data_source", "CHAN2"), "clock_level": final.get("clock_source", "CHAN1")}
    else:
        fields = None
    if fields is not None:
        for field, source in fields.items():
            if field in requested:
                low, high = _level_bounds(session, source)
                if not low <= requested[field] <= high:
                    raise ValueError(f"details.{field} {requested[field]:g} is outside the allowed range {low:g}..{high:g}")
        for field in ("levels",):
            if field in requested:
                for source, value in requested[field].items():
                    low, high = _level_bounds(session, source)
                    if not low <= value <= high:
                        raise ValueError(f"details.levels.{source} {value:g} is outside the allowed range {low:g}..{high:g}")
        return
    sources = {
        "I2C": {"scl_level": final.get("scl_source", "CHAN1"), "sda_level": final.get("sda_source", "CHAN2")},
        "SPI": {"clock_level": final.get("clock_source", "CHAN1"), "data_level": final.get("data_source", "CHAN2"), "cs_level": final.get("cs_source", "CHAN3")},
        "RS232": {"level": final.get("source", "CHAN1")},
        "CAN": {"level": final.get("source", "CHAN1")},
        "LIN": {"level": final.get("source", "CHAN1")},
        "I2S": {"clock_level": final.get("clock_source", "CHAN1"), "frame_level": final.get("ws_source", "CHAN2"), "data_level": final.get("data_source", "CHAN3")},
        "FLEXRAY": {"level": final.get("source", "CHAN1")},
        "M1553": {"level_a": final.get("source", "CHAN1"), "level_b": final.get("source", "CHAN1")},
    }[protocol]
    for field, source in sources.items():
        if field in requested:
            low, high = _level_bounds(session, source)
            if not low <= requested[field] <= high:
                raise ValueError(f"details.{field} {requested[field]:g} is outside the allowed range {low:g}..{high:g}")


def _detail_command(protocol: str, field: str) -> str:
    commands = {
        "I2C": {
            "scl_source": "SCL", "scl_level": "CLEVel", "sda_source": "SDA", "sda_level": "DLEVel",
            "condition": "WHEN", "address_width": "AWIDth", "address": "ADDRess", "direction": "DIRection",
            "data_bytes": "DBYTes", "data": "DATA", "current_bit": "CURRbit", "bit_code": "CODE",
        },
        "SPI": {
            "clock_source": "CLK", "clock_level": "CLEVel", "clock_slope": "SLOPe", "data_source": "MISO",
            "data_level": "DLEVel", "condition": "WHEN", "cs_source": "CS", "cs_level": "SLEVel", "cs_mode": "MODE",
            "timeout_s": "TIMeout", "data_width": "WIDTh", "data": "DATA", "current_bit": "CURRbit", "bit_code": "CODE",
        },
        "RS232": {
            "source": "SOURce", "level": "LEVel", "polarity": "POLarity", "condition": "WHEN", "data": "DATA",
            "baud": "BAUD", "data_width": "WIDTh", "stop_bits": "STOP", "parity": "PARity",
        },
        "CAN": {
            "source": "SOURce", "level": "LEVel", "baud": "BAUD", "signal_type": "STYPe", "condition": "WHEN",
            "sample_point": "SPOint", "extended_id": "EXTended", "define": "DEFine", "data_width": "DWIDth", "data": "DATA",
            "current_bit": "CURRbit", "bit_code": "CODE",
        },
        "LIN": {
            "source": "SOURce", "level": "LEVel", "standard": "STANdard", "baud": "BAUD", "sample_point": "SAMPlepoint",
            "condition": "WHEN", "error": "ERRor", "id": "ID", "data": "DATA", "current_bit": "CURRbit", "bit_code": "CODE",
        },
        "I2S": {
            "alignment": "ALIGnment", "clock_level": "CLEVel", "frame_level": "SLEVel", "data_level": "DLEVel", "user_width": "UWIDth",
            "width": "WIDTh", "data_min_bit": "DMIN", "data_max_bit": "DMAX", "bit_code": "CODE", "clock_slope": "CLOCk:SLOPe",
            "clock_source": "SOURce:CLOCk", "data_source": "SOURce:DATA", "ws_source": "SOURce:WSELect", "condition": "WHEN", "audio": "AUDio", "data": "DATA",
        },
        "FLEXRAY": {
            "baud": "BAUD", "position": "POS", "error": "ERRor", "symbol": "SYMBol", "frame": "FRAMe", "define": "DEFine",
            "id_comparison": "IDCmp", "cycle_comparison": "CYCComp", "max_cycle": "MAXCy", "min_cycle": "MINCy", "max_id": "MAXid", "min_id": "MINid",
            "channel": "CH", "source": "SOURce", "condition": "WHEN", "level": "LEVel",
        },
        "M1553": {
            "source": "SOURce", "condition": "WHEN", "polarity": "POLarity", "window": "WINDow", "sync": "SYNC", "error": "ERRor",
            "data_comparison": "DATComp", "data_value": "DATValue", "data_min_bit": "DMIN", "data_max_bit": "DMAX", "remote_terminal_address": "DRTA",
            "data_bit": "DBIT", "bit_code": "CODE", "level_a": "ALEVel", "level_b": "BLEVel",
        },
        "PULSE": {"source": "SOURce", "polarity": "POLarity", "condition": "WHEN", "upper_width_s": "UWIDth", "lower_width_s": "LWIDth", "level": "LEVel"},
        "SLOPE": {"source": "SOURce", "polarity": "POLarity", "condition": "WHEN", "upper_time_s": "TUPPer", "lower_time_s": "TLOWer", "window": "WINDow", "upper_level": "ALEVel", "lower_level": "BLEVel"},
        "VIDEO": {"source": "SOURce", "polarity": "POLarity", "sync": "MODE", "line": "LINE", "standard": "STANdard", "level": "LEVel"},
        "PATTERN": {"source": "SOURce", "pattern": "PATTern", "levels": "LEVel", "level": "LEVel"},
        "DURATION": {"source": "SOURce", "pattern": "TYPE", "condition": "WHEN", "upper_time_s": "TUPPer", "lower_time_s": "TLOWer", "levels": "LEVel", "level": "LEVel"},
        "TIMEOUT": {"source": "SOURce", "slope": "SLOPe", "time_s": "TIME", "level": "LEVel"},
        "RUNT": {"source": "SOURce", "polarity": "POLarity", "condition": "WHEN", "upper_width_s": "WUPPer", "lower_width_s": "WLOWer", "upper_level": "ALEVel", "lower_level": "BLEVel"},
        "WINDOW": {"source": "SOURce", "slope": "SLOPe", "position": "POSition", "time_s": "TIME", "upper_level": "ALEVel", "lower_level": "BLEVel"},
        "DELAY": {"source_a": "SA", "slope_a": "ASLop", "source_b": "SB", "slope_b": "BSLop", "condition": "TYPE", "upper_time_s": "TUPPer", "lower_time_s": "TLOWer", "level_a": "ALEVel", "level_b": "BLEVel"},
        "SETUP": {"data_source": "DSRC", "clock_source": "CSRC", "slope": "SLOPe", "pattern": "PATTern", "condition": "TYPE", "setup_time_s": "STIMe", "hold_time_s": "HTIMe", "data_level": "DLEVel", "clock_level": "CLEVel"},
        "NEDGE": {"source": "SOURce", "slope": "SLOPe", "idle_time_s": "IDLE", "edge_count": "EDGE", "level": "LEVel"},
    }
    return commands[protocol][field]


def _detail_scpi_value(protocol: str, field: str, value: Any) -> str:
    enums = {
        ("I2C", "condition"): {"START": "STARt", "RESTART": "RESTart", "STOP": "STOP", "NACK": "NACKnowledge", "ADDRESS": "ADDRess", "DATA": "DATA", "ADDRESS_DATA": "ADATa"},
        ("I2C", "direction"): {"READ": "READ", "WRITE": "WRITe", "READ_WRITE": "RWRite"},
        ("SPI", "clock_slope"): {"POSITIVE": "POSitive", "NEGATIVE": "NEGative"},
        ("SPI", "condition"): {"CS": "CS", "TIMEOUT": "TIMeout"},
        ("SPI", "cs_mode"): {"HIGH": "HIGH", "LOW": "LOW"},
        ("RS232", "polarity"): {"POSITIVE": "POSitive", "NEGATIVE": "NEGative"},
        ("RS232", "condition"): {"START": "STARt", "ERROR": "ERRor", "CHECK_ERROR": "CERRor", "DATA": "DATA"},
        ("CAN", "signal_type"): {"H": "H", "L": "L", "RXTX": "RXTX", "DIFFERENTIAL": "DIFFerential"},
        ("CAN", "condition"): {"SOF": "SOF", "EOF": "EOF", "ID_REMOTE": "IDRemote", "OVERLOAD": "OVERload", "ID_FRAME": "IDFRame", "DATA_FRAME": "DATaframe", "ID_DATA": "IDData", "ERROR_FRAME": "ERFRame", "ERROR_ANSWER": "ERANswer", "ERROR_CHECK": "ERCHeck", "ERROR_FORMAT": "ERFormat", "ERROR_RANDOM": "ERRandom", "ERROR_BIT": "ERBit"},
        ("CAN", "define"): {"DATA": "DATA", "ID": "ID"},
        ("LIN", "standard"): {"1X": "1X", "2X": "2X", "BOTH": "BOTH"},
        ("LIN", "condition"): {"SYNC_BREAK": "SYNCbreak", "ID": "ID", "DATA": "DATA", "ID_DATA": "IDData", "SLEEP": "SLEep", "WAKEUP": "WAKeup", "ERROR": "ERRor"},
        ("LIN", "error"): {"SYNC": "SYNC", "ID": "ID", "CHECKSUM": "CHECk"},
        ("I2S", "alignment"): {"LJ": "LJ", "RJ": "RJ", "IIS": "IIS"},
        ("I2S", "clock_slope"): {"POSITIVE": "POSitive", "NEGATIVE": "NEGative"},
        ("I2S", "condition"): {"EQUAL": "EQUal", "NOT_EQUAL": "NOTequal", "LESS_THAN": "LESSthan", "GREATER_THAN": "GREaterthan", "IN_RANGE": "INRange", "OUT_RANGE": "OUTRange"},
        ("I2S", "audio"): {"RIGHT": "RIGHt", "LEFT": "LEFT", "EITHER": "EITHer"},
        ("FLEXRAY", "position"): {"TSS": "TSS", "FSS": "FSS", "FES": "FES", "DTS": "DTS"},
        ("FLEXRAY", "error"): {"HEADER": "HEAD", "TRAILER": "TRAiler", "DECODE": "DECode", "ANY": "ANY"},
        ("FLEXRAY", "define"): {"CYCLE": "CYCLe", "ID": "ID"},
        ("FLEXRAY", "condition"): {"FRAME": "FRAMe", "SYMBOL": "SYMBol", "ERROR": "ERRor", "TSS": "TSS"},
        ("FLEXRAY", "frame"): {"NULL": "NULL", "SYNC": "SYNC", "STARTUP": "STAR", "ANY": "ANY"},
        ("M1553", "condition"): {"SYNC_BREAK": "SYNCbreak", "DATA": "DATA", "COMMAND": "CMD", "STATUS": "STATus", "ERROR": "ERRor"},
        ("M1553", "polarity"): {"POSITIVE": "POSitive", "NEGATIVE": "NEGative"},
        ("M1553", "sync"): {"DATA": "DATA", "STATUS": "STATus", "ALL": "ALL"},
        ("M1553", "error"): {"SYNC": "SYNC", "ERROR": "ERR"},
        ("PULSE", "polarity"): {"POSITIVE": "POSitive", "NEGATIVE": "NEGative"},
        ("PULSE", "condition"): {"GREATER": "GREater", "LESS": "LESS", "IN_RANGE": "GLESs"},
        ("SLOPE", "polarity"): {"POSITIVE": "POSitive", "NEGATIVE": "NEGative"},
        ("SLOPE", "condition"): {"GREATER": "GREater", "LESS": "LESS", "IN_RANGE": "GLESs"},
        ("SLOPE", "window"): {"TA": "TA", "TB": "TB", "TAB": "TAB"},
        ("VIDEO", "polarity"): {"POSITIVE": "POSitive", "NEGATIVE": "NEGative"},
        ("VIDEO", "sync"): {"ODD": "ODDField", "EVEN": "EVENfield", "LINE": "LINE", "ALL_LINES": "ALINes"},
        ("VIDEO", "standard"): {"PALSECAM": "PALSecam", **{name: name for name in _VIDEO_LINES if name != "PALSECAM"}},
        ("TIMEOUT", "slope"): {"POSITIVE": "POSitive", "NEGATIVE": "NEGative", "BOTH": "RFALl"},
        ("RUNT", "polarity"): {"POSITIVE": "POSitive", "NEGATIVE": "NEGative"},
        ("RUNT", "condition"): {"NONE": "NONE", "GREATER": "GREater", "LESS": "LESS", "IN_RANGE": "GLESs"},
        ("WINDOW", "slope"): {"POSITIVE": "POSitive", "NEGATIVE": "NEGative", "BOTH": "RFALl"},
        ("WINDOW", "position"): {"EXIT": "EXIT", "ENTER": "ENTer", "TIME": "TIME"},
        ("DELAY", "slope_a"): {"POSITIVE": "POSitive", "NEGATIVE": "NEGative"},
        ("DELAY", "slope_b"): {"POSITIVE": "POSitive", "NEGATIVE": "NEGative"},
        ("DELAY", "condition"): {"GREATER": "GREater", "LESS": "LESS", "IN_RANGE": "GLESs", "OUT_RANGE": "GOUT"},
        ("SETUP", "slope"): {"POSITIVE": "POSitive", "NEGATIVE": "NEGative"},
        ("SETUP", "pattern"): {"HIGH": "H", "LOW": "L"},
        ("SETUP", "condition"): {"SETUP": "SETup", "HOLD": "HOLD", "BOTH": "SETHold"},
        ("NEDGE", "slope"): {"POSITIVE": "POSitive", "NEGATIVE": "NEGative"},
    }
    if field == "extended_id":
        return "1" if value else "0"
    return str(enums.get((protocol, field), {}).get(value, value))


def _write_details(session: Any, protocol: str, current: Mapping[str, Any], requested: Mapping[str, Any]) -> None:
    order = {
        "I2C": ("scl_source", "scl_level", "sda_source", "sda_level", "condition", "address_width", "data_bytes", "address", "direction", "data", "current_bit", "bit_code"),
        "SPI": ("clock_source", "clock_level", "data_source", "data_level", "condition", "cs_source", "cs_level", "cs_mode", "timeout_s", "data_width", "data", "current_bit", "bit_code", "clock_slope"),
        "RS232": ("source", "level", "polarity", "condition", "data_width", "data", "baud", "stop_bits", "parity"),
        "CAN": ("source", "level", "baud", "signal_type", "condition", "sample_point", "extended_id", "define", "data_width", "data", "current_bit", "bit_code"),
        "LIN": ("source", "level", "standard", "baud", "sample_point", "condition", "error", "id", "data", "current_bit", "bit_code"),
        "I2S": ("clock_source", "data_source", "ws_source", "clock_level", "frame_level", "data_level", "width", "user_width", "clock_slope", "condition", "audio", "data_min_bit", "data_max_bit", "data", "bit_code"),
        "FLEXRAY": ("source", "level", "channel", "baud", "condition", "position", "error", "symbol", "frame", "define", "id_comparison", "cycle_comparison", "min_cycle", "max_cycle", "min_id", "max_id"),
        "M1553": ("source", "polarity", "window", "level_a", "level_b", "condition", "sync", "error", "data_comparison", "data_value", "data_min_bit", "data_max_bit", "remote_terminal_address", "data_bit", "bit_code"),
        "PULSE": ("source", "polarity", "condition", "lower_width_s", "upper_width_s", "level"),
        "SLOPE": ("source", "polarity", "condition", "window", "lower_time_s", "upper_time_s", "lower_level", "upper_level"),
        "VIDEO": ("source", "polarity", "standard", "sync", "line", "level"),
        "PATTERN": ("source", "pattern", "levels", "level"),
        "DURATION": ("source", "pattern", "condition", "lower_time_s", "upper_time_s", "levels", "level"),
        "TIMEOUT": ("source", "slope", "time_s", "level"),
        "RUNT": ("source", "polarity", "condition", "lower_width_s", "upper_width_s", "lower_level", "upper_level"),
        "WINDOW": ("source", "slope", "position", "time_s", "lower_level", "upper_level"),
        "DELAY": ("source_a", "slope_a", "source_b", "slope_b", "condition", "lower_time_s", "upper_time_s", "level_a", "level_b"),
        "SETUP": ("data_source", "clock_source", "slope", "pattern", "condition", "setup_time_s", "hold_time_s", "data_level", "clock_level"),
        "NEDGE": ("source", "slope", "idle_time_s", "edge_count", "level"),
    }[protocol]
    prefixes = {
        "I2C": ":TRIGger:IIC:", "SPI": ":TRIGger:SPI:", "RS232": ":TRIGger:RS232:", "CAN": ":TRIGger:CAN:",
        "LIN": ":TRIGger:LIN:", "I2S": ":TRIGger:IIS:", "FLEXRAY": ":TRIGger:FLEXray:", "M1553": ":TRIGger:M1553:",
        "PULSE": ":TRIGger:PULSe:", "SLOPE": ":TRIGger:SLOPe:", "VIDEO": ":TRIGger:VIDeo:", "PATTERN": ":TRIGger:PATTern:",
        "DURATION": ":TRIGger:DURation:", "TIMEOUT": ":TRIGger:TIMeout:", "RUNT": ":TRIGger:RUNT:", "WINDOW": ":TRIGger:WINDows:",
        "DELAY": ":TRIGger:DELay:", "SETUP": ":TRIGger:SHOLd:", "NEDGE": ":TRIGger:NEDGe:",
    }
    for field in order:
        if field not in requested:
            continue
        value = requested[field]
        if field == "pattern" and protocol in {"PATTERN", "DURATION"}:
            if set(value) != {f"CHAN{i}" for i in range(1, 5)}:
                raise ValueError("pattern updates require explicit CHAN1 through CHAN4 states")
            value = ",".join(value[f"CHAN{i}"] for i in range(1, 5))
        if field == "levels":
            for source, level in value.items():
                session.write(f"{prefixes[protocol]}{_detail_command(protocol, field)} {source},{level:.15g}")
            continue
        if field == "level" and protocol in {"PATTERN", "DURATION"}:
            source = requested.get("source")
            if source is None:
                raise ValueError("details.source is required when setting pattern trigger level")
            session.write(f"{prefixes[protocol]}{_detail_command(protocol, field)} {source},{value:.15g}")
            continue
        value = _detail_scpi_value(protocol, field, value)
        session.write(f"{prefixes[protocol]}{_detail_command(protocol, field)} {value}")


def set_trigger(
    session: Any,
    *,
    mode: Any = None,
    sweep: Any = None,
    coupling: Any = None,
    holdoff_s: Any = None,
    noise_reject: Any = None,
    source: Any = None,
    slope: Any = None,
    level: Any = None,
    details: Any = None,
) -> dict[str, Any]:
    """Send only explicitly requested trigger fields.

    When no mode is supplied, one ``MODE?`` selector query is used only if it is
    required to route untyped protocol details. EDGE fields have fixed headers.  No trigger snapshot or
    detail readback is performed.
    """
    requested_mode = None if mode is None else _mode(mode)
    requested_sweep = None if sweep is None else _sweep(sweep)
    requested_coupling = None if coupling is None else _coupling(coupling)
    requested_holdoff = None if holdoff_s is None else _holdoff(holdoff_s)
    requested_noise = None if noise_reject is None else _bool(noise_reject, "noise_reject")
    requested_source = None if source is None else _source(source, "edge source")
    requested_slope = None if slope is None else _slope(slope)
    requested_level = None if level is None else _finite(level, "level")
    if details is not None and not isinstance(details, Mapping):
        raise ValueError("details must be an object of named protocol fields; raw SCPI is unsupported")

    edge_fields = any(item is not None for item in (requested_source, requested_slope, requested_level))
    needs_mode_selector = requested_mode is None and (
        details is not None and bool(details)
    )
    if requested_mode is None and needs_mode_selector:
        # A single selector is essential to choose EDGE/protocol command routing;
        # do not replace it with the full get_trigger snapshot.
        final_mode = _mode_response(session.query(":TRIGger:MODE?"))
    else:
        final_mode = requested_mode or ("EDGE" if edge_fields else None)

    if final_mode is not None:
        if edge_fields and final_mode != "EDGE":
            raise ValueError("edge source, slope, and level require EDGE mode")
        if requested_coupling is not None and final_mode != "EDGE":
            raise ValueError("coupling is only configurable for EDGE analog triggers")
        if requested_holdoff is not None and final_mode in _HOLDoff_EXCLUDED:
            raise ValueError(f"holdoff_s is unavailable in {final_mode} trigger mode")
        if requested_source is not None and final_mode != "EDGE":
            raise ValueError("source is only configurable for EDGE triggers")
    if requested_coupling is not None and requested_source is not None and requested_source.startswith("D"):
        raise ValueError("coupling requires an analog EDGE source")
    if requested_noise is not None and requested_source is not None and requested_source.startswith("D"):
        raise ValueError("noise_reject requires an analog EDGE source")

    protocol = _MODE_PROTOCOL.get(final_mode) if final_mode is not None else None
    requested_details: dict[str, Any] = {}
    if details is not None:
        if protocol is None:
            raise ValueError("details are unsupported for the selected trigger mode")
        raw_details = _normalise_details(details, protocol)
        requested_details = _validate_details(protocol, raw_details)

    # Conditions or dependent settings omitted from this request remain on the
    # instrument.  Only scalar validation above is performed without inventing
    # those values or querying them.
    writes: list[str] = []
    if requested_mode is not None:
        writes.append(f":TRIGger:MODE {_MODE_SCPI[requested_mode]}")
    if requested_sweep is not None:
        writes.append(f":TRIGger:SWEep {requested_sweep}")
    if final_mode == "EDGE":
        if requested_source is not None:
            writes.append(f":TRIGger:EDGE:SOURce {requested_source}")
        if requested_slope is not None:
            writes.append(f":TRIGger:EDGE:SLOPe {requested_slope}")
        if requested_level is not None:
            writes.append(f":TRIGger:EDGE:LEVel {requested_level:.15g}")
    if protocol is not None and requested_details:
        class _Writer:
            def write(self, command: str) -> None:
                writes.append(command)

        _write_details(_Writer(), protocol, {}, requested_details)
    if requested_coupling is not None:
        writes.append(f":TRIGger:COUPling {requested_coupling}")
    if requested_holdoff is not None:
        writes.append(f":TRIGger:HOLDoff {requested_holdoff:.15g}")
    if requested_noise is not None:
        writes.append(f":TRIGger:NREJect {1 if requested_noise else 0}")

    for command in writes:
        session.write(command)
    requested = {
        key: value for key, value in {
            "mode": requested_mode, "sweep": requested_sweep, "coupling": requested_coupling,
            "holdoff_s": requested_holdoff, "noise_reject": requested_noise,
            "source": requested_source, "slope": requested_slope, "level": requested_level,
            "details": requested_details or None,
        }.items() if value is not None
    }
    return {"sent": bool(writes), "verified": False, "commands": writes, "requested": requested, **requested}


_DETAIL_SCHEMA_PROPERTIES = {
    "scl_source": {"type": "string", "description": "I2C SCL source: CHAN1-CHAN4 or D0-D15."}, "clock_source": {"type": "string"}, "clk_source": {"type": "string"},
    "scl_level": {"type": "number"}, "clock_level": {"type": "number"}, "clevel": {"type": "number"}, "sda_source": {"type": "string"}, "sda_level": {"type": "number"},
    "clock_slope": {"type": "string", "enum": ["POSITIVE", "NEGATIVE", "POS", "NEG"]}, "slope": {"type": "string"},
    "data_source": {"type": "string"}, "miso_source": {"type": "string"}, "data_level": {"type": "number"}, "dlevel": {"type": "number"}, "miso_level": {"type": "number"},
    "cs_source": {"type": "string"}, "cs_level": {"type": "number"}, "slevel": {"type": "number"}, "source": {"type": "string"}, "level": {"type": "number"},
    "condition": {"type": "string"}, "when": {"type": "string", "description": "Alias for condition."},
    "address_width": {"type": "integer", "enum": [7, 8, 10]}, "address_bits": {"type": "integer", "enum": [7, 8, 10]}, "awidth": {"type": "integer", "enum": [7, 8, 10]}, "address": {"type": "integer", "minimum": 0, "maximum": 1023},
    "direction": {"type": "string", "enum": ["READ", "WRITE", "READ_WRITE", "RWR"]}, "data_bytes": {"type": "integer", "minimum": 1, "maximum": 5}, "bytes": {"type": "integer", "minimum": 1, "maximum": 5},
    "data_width": {"type": "integer", "minimum": 1, "maximum": 32, "description": "Protocol-dependent documented data width; validated against the active mode."}, "data_bits": {"type": "integer"}, "width": {"type": "integer", "minimum": 4, "maximum": 32}, "data": {"type": "integer", "minimum": 0},
    "current_bit": {"type": "integer", "minimum": 0, "maximum": 39}, "currbit": {"type": "integer", "minimum": 0, "maximum": 39}, "bit_code": {"type": "integer", "enum": [0, 1, 255]}, "code": {"type": "integer", "enum": [0, 1, 255]},
    "cs_mode": {"type": "string", "enum": ["HIGH", "LOW"]}, "mode": {"type": "string"}, "timeout_s": {"type": "number", "minimum": 8e-9, "maximum": 10}, "timeout": {"type": "number", "minimum": 8e-9, "maximum": 10},
    "polarity": {"type": "string", "enum": ["POSITIVE", "NEGATIVE", "POS", "NEG"]}, "baud": {"type": "integer", "minimum": 1, "maximum": 20000000}, "baud_rate": {"type": "integer", "minimum": 1, "maximum": 20000000}, "buser": {"type": "integer", "minimum": 1, "maximum": 20000000},
    "stop_bits": {"type": "number", "enum": [1, 1.5, 2]}, "stop": {"type": "number", "enum": [1, 1.5, 2]}, "parity": {"type": "string", "enum": ["EVEN", "ODD", "NONE"]},
    "signal_type": {"type": "string", "enum": ["H", "L", "RXTX", "DIFFERENTIAL"]}, "sample_point": {"type": "integer", "minimum": 10, "maximum": 90}, "extended_id": {"type": "boolean"}, "standard": {"type": "string", "enum": ["1X", "2X", "BOTH"]}, "error": {"type": "string"}, "id": {"type": "integer", "minimum": 0},
    "alignment": {"type": "string", "enum": ["LJ", "RJ", "IIS"]}, "frame_level": {"type": "number"}, "user_width": {"type": "integer", "minimum": 4, "maximum": 32}, "width": {"type": "integer", "minimum": 4, "maximum": 32}, "data_min_bit": {"type": "integer", "minimum": 0, "maximum": 31}, "data_max_bit": {"type": "integer", "minimum": 0, "maximum": 31}, "ws_source": {"type": "string"}, "audio": {"type": "string", "enum": ["RIGHT", "LEFT", "EITHER"]},
    "position": {"type": "string", "enum": ["TSS", "FSS", "FES", "DTS"]}, "symbol": {"type": "string", "enum": ["CAS", "WUS"]}, "frame": {"type": "string", "enum": ["NULL", "SYNC", "STARTUP", "ANY"]}, "id_comparison": {"type": "string"}, "cycle_comparison": {"type": "string"}, "max_cycle": {"type": "integer", "minimum": 0, "maximum": 63}, "min_cycle": {"type": "integer", "minimum": 0, "maximum": 63}, "max_id": {"type": "integer", "minimum": 0, "maximum": 1023}, "min_id": {"type": "integer", "minimum": 0, "maximum": 1023}, "channel": {"type": "string", "enum": ["A", "B"]},
    "window": {"type": "string"}, "sync": {"type": "string"}, "data_comparison": {"type": "string"}, "data_value": {"type": "integer", "minimum": 0, "maximum": 65535}, "remote_terminal_address": {"type": "integer", "minimum": 0, "maximum": 6}, "data_bit": {"type": "integer", "minimum": 0, "maximum": 13}, "level_a": {"type": "number"}, "level_b": {"type": "number"},
    "polarity": {"type": "string"}, "upper_width_s": {"type": "number", "minimum": 1e-9, "maximum": 10}, "lower_width_s": {"type": "number", "minimum": 1e-9, "maximum": 10}, "upper_time_s": {"type": "number", "minimum": 1e-9, "maximum": 10}, "lower_time_s": {"type": "number", "minimum": 1e-9, "maximum": 10}, "time_s": {"type": "number", "minimum": 1e-9, "maximum": 10}, "idle_time_s": {"type": "number", "minimum": 16e-9, "maximum": 10}, "edge_count": {"type": "integer", "minimum": 1, "maximum": 65535}, "upper_level": {"type": "number"}, "lower_level": {"type": "number"}, "data_source": {"type": "string"}, "clock_source": {"type": "string"}, "slope_a": {"type": "string"}, "slope_b": {"type": "string"}, "setup_time_s": {"type": "number", "minimum": 1e-9, "maximum": 10}, "hold_time_s": {"type": "number", "minimum": 1e-9, "maximum": 10}, "levels": {"type": "object", "additionalProperties": {"type": "number"}}, "pattern": {"oneOf": [{"type": "object", "additionalProperties": {"type": "string"}}, {"type": "string", "enum": ["H", "L", "HIGH", "LOW"]}]}, "line": {"type": "integer", "minimum": 1, "maximum": 1125}, "standard": {"type": "string"}, "position": {"type": "string"}, "time": {"type": "number"},
    "sync_type": {"type": "string"}, "video_standard": {"type": "string"}, "line_number": {"type": "integer", "minimum": 1, "maximum": 1125}, "channel_pattern": {"type": "object", "additionalProperties": {"type": "string"}}, "thresholds": {"type": "object", "additionalProperties": {"type": "number"}}, "upper_width": {"type": "number"}, "lower_width": {"type": "number"}, "upper_time": {"type": "number"}, "lower_time": {"type": "number"}, "upper": {"type": "number"}, "lower": {"type": "number"}, "threshold_upper": {"type": "number"}, "threshold_lower": {"type": "number"}, "type": {"type": "string"}, "data_type": {"type": "string", "enum": ["H", "L", "HIGH", "LOW"]}, "clock": {"type": "string"}, "source_a": {"type": "string"}, "source_b": {"type": "string"}, "setup_time": {"type": "number"}, "hold_time": {"type": "number"}, "idle": {"type": "number"}, "edge": {"type": "integer"},
}


TOOLS = [
    ToolSpec(
        name="get_trigger",
        description="Read MHO98 common trigger fields and named, condition-valid details for all 20 documented trigger modes.",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=get_trigger,
        read_only=True,
        needs_session=True,
    ),
    ToolSpec(
        name="set_trigger",
        description="Send selected MHO98 trigger commands with explicit-input validation; omitted fields are preserved and resulting state is not verified.",
        input_schema={
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": [*_MODES, "I2C", "I2S", "UART", "FLEX"], "description": "The documented 20 trigger modes plus I2C/I2S/UART/FLEX input aliases."},
                "sweep": {"type": "string", "enum": ["AUTO", "NORM", "SING"]},
                "coupling": {"type": "string", "enum": ["AC", "DC", "LFR", "HFR"]},
                "holdoff_s": {"type": "number", "minimum": 8e-9, "maximum": 10},
                "noise_reject": {"type": "boolean"},
                "source": {"type": "string", "enum": [f"CH{i}" for i in range(1, 5)] + [f"D{i}" for i in range(16)]},
                "slope": {"type": "string", "enum": ["POS", "NEG", "RFAL"]}, "level": {"type": "number"},
                "details": {"type": "object", "additionalProperties": False, "properties": _DETAIL_SCHEMA_PROPERTIES, "description": "Named protocol fields only. Valid fields depend on the active protocol and condition; irrelevant fields are rejected before the first write. No raw SCPI command escape is exposed."},
            },
            "required": [],
        },
        handler=set_trigger,
        read_only=False,
        needs_session=True,
    ),
]
