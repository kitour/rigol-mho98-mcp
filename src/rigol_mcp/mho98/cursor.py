"""MHO98 cursor configuration and cursor-result tools.

Cursor placement commands and cursor measurement-result queries are deliberately
kept separate.  ``CAX``/``CAY`` and their siblings are instrument cursor
positions; ``AXValue``/``AYValue`` and the delta queries are physical waveform
readings.  This module never enables the timebase, channels, or MATH outputs as
a side effect of selecting a cursor source.
"""

from __future__ import annotations

import math
from numbers import Real
from typing import Any

from .api import ToolSpec


_MODE_INPUT = {"OFF": "OFF", "MAN": "MANUAL", "MANUAL": "MANUAL", "TRAC": "TRACK", "TRACK": "TRACK", "XY": "XY"}
_MODE_RESPONSE = {"OFF": "OFF", "MAN": "MAN", "MANUAL": "MAN", "TRAC": "TRAC", "TRACK": "TRAC", "XY": "XY"}
_MODE_WRITE = {"OFF": "OFF", "MANUAL": "MANual", "TRACK": "TRACk", "XY": "XY"}
_SOURCE_NAMES = {"NONE"}
_SOURCE_NAMES.update(f"CHAN{i}" for i in range(1, 5))
_SOURCE_NAMES.update(f"MATH{i}" for i in range(1, 5))
_INVALID_SENTINEL = 9.0e37

_MANUAL_FIELDS = {
    "manual_type",
    "manual_source",
    "manual_tunit",
    "manual_vunit",
    "manual_cax",
    "manual_cay",
    "manual_cbx",
    "manual_cby",
}
_TRACK_FIELDS = {
    "track_source1",
    "track_source2",
    "track_axis",
    "track_cax",
    "track_cbx",
    "track_cay",
    "track_cby",
}
_XY_FIELDS = {"xy_ax", "xy_bx", "xy_ay", "xy_by"}


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


def _number_response(value: Any, name: str) -> float:
    return _finite(value, name)


def _scpi_number(value: float) -> str:
    return format(value, ".15g")


def _bool_input(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _bool_response(value: Any, name: str) -> bool:
    token = str(value).strip().upper()
    if token in {"1", "ON", "TRUE"}:
        return True
    if token in {"0", "OFF", "FALSE"}:
        return False
    raise ValueError(f"invalid {name} response from MHO98: {value!r}")


def _mode(value: Any) -> str:
    token = str(value).strip().upper()
    try:
        return _MODE_INPUT[token]
    except KeyError:
        raise ValueError("mode must be OFF, MANUAL, TRACK, or XY") from None


def _mode_response(value: Any) -> str:
    token = str(value).strip().upper()
    try:
        return _MODE_INPUT[token]
    except KeyError:
        raise ValueError(f"invalid cursor mode response from MHO98: {value!r}") from None


def _source(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be CHAN1-CHAN4, MATH1-MATH4, or NONE")
    token = value.strip().upper().replace(" ", "")
    if token.startswith("CHANNEL"):
        token = "CHAN" + token[7:]
    elif token.startswith("CH") and not token.startswith("CHAN"):
        token = "CHAN" + token[2:]
    if token not in _SOURCE_NAMES:
        raise ValueError(f"{name} must be CHAN1-CHAN4, MATH1-MATH4, or NONE")
    return token


def _source_response(value: Any, name: str) -> str:
    return _source(str(value), name)


def _enum(value: Any, name: str, values: set[str], aliases: dict[str, str] | None = None) -> str:
    token = str(value).strip().upper()
    token = (aliases or {}).get(token, token)
    if token not in values:
        raise ValueError(f"{name} must be one of {', '.join(sorted(values))}")
    return token


def _manual_type(value: Any, name: str = "manual_type") -> str:
    return _enum(value, name, {"TIME", "AMPL"}, {"AMPLITUDE": "AMPL"})


def _manual_tunit(value: Any, name: str = "manual_tunit") -> str:
    return _enum(value, name, {"SEC", "SECOND", "SECONDS"}, {"SECOND": "SEC", "SECONDS": "SEC"})


def _manual_vunit(value: Any, name: str = "manual_vunit") -> str:
    return _enum(value, name, {"SOUR", "SOURCE"}, {"SOURCE": "SOUR"})


def _track_axis(value: Any, name: str = "track_axis") -> str:
    return _enum(value, name, {"X", "Y"})


def _query_mode(session: Any) -> str:
    return _mode_response(session.query(":CURSor:MODE?"))


def _query_indicator(session: Any) -> bool:
    return _bool_response(session.query(":CURSor:MEASure:INDicator?"), "cursor indicator")


def _require_xy_timebase(session: Any) -> None:
    # MODE? is the only prerequisite query.  In particular, do not enable XY
    # here: selecting a cursor mode must not change timebase state.
    timebase_mode = str(session.query(":TIMebase:MODE?")).strip().upper()
    if timebase_mode not in {"XY"}:
        raise ValueError("XY cursor mode requires the existing timebase mode to be XY")


def _query_config(session: Any, mode: str) -> dict[str, Any]:
    if mode == "MANUAL":
        return {
            "type": _manual_type(session.query(":CURSor:MANual:TYPE?"), "manual type response"),
            "source": _source_response(session.query(":CURSor:MANual:SOURce?"), "manual source response"),
            "tunit": _manual_tunit(session.query(":CURSor:MANual:TUNit?"), "manual tunit response"),
            "vunit": _manual_vunit(session.query(":CURSor:MANual:VUNit?"), "manual vunit response"),
            "screen_positions": {
                "a": {
                    "x_s": _number_response(session.query(":CURSor:MANual:CAX?"), "manual CAX"),
                    "y_v": _number_response(session.query(":CURSor:MANual:CAY?"), "manual CAY"),
                },
                "b": {
                    "x_s": _number_response(session.query(":CURSor:MANual:CBX?"), "manual CBX"),
                    "y_v": _number_response(session.query(":CURSor:MANual:CBY?"), "manual CBY"),
                },
            },
        }
    if mode == "TRACK":
        return {
            "source1": _source_response(session.query(":CURSor:TRACk:SOURce1?"), "track source1 response"),
            "source2": _source_response(session.query(":CURSor:TRACk:SOURce2?"), "track source2 response"),
            "axis": _track_axis(session.query(":CURSor:TRACk:MODE?"), "track axis response"),
            "screen_positions": {
                "a": {
                    "x_s": _number_response(session.query(":CURSor:TRACk:CAX?"), "track CAX"),
                    "y_v": _number_response(session.query(":CURSor:TRACk:CAY?"), "track CAY"),
                },
                "b": {
                    "x_s": _number_response(session.query(":CURSor:TRACk:CBX?"), "track CBX"),
                    "y_v": _number_response(session.query(":CURSor:TRACk:CBY?"), "track CBY"),
                },
            },
        }
    if mode == "XY":
        return {
            "screen_positions": {
                "a": {
                    "x_v": _number_response(session.query(":CURSor:XY:AX?"), "XY AX"),
                    "y_v": _number_response(session.query(":CURSor:XY:AY?"), "XY AY"),
                },
                "b": {
                    "x_v": _number_response(session.query(":CURSor:XY:BX?"), "XY BX"),
                    "y_v": _number_response(session.query(":CURSor:XY:BY?"), "XY BY"),
                },
            },
        }
    return {}


def _state(session: Any, *, mode: str | None = None, check_xy: bool = True) -> dict[str, Any]:
    selected = _query_mode(session) if mode is None else mode
    indicator = _query_indicator(session)
    result: dict[str, Any] = {"mode": _MODE_RESPONSE[selected], "indicator": indicator}
    if selected != "OFF":
        result[selected.lower()] = _query_config(session, selected)
    return result


def get_cursor(session: Any) -> dict[str, Any]:
    """Return global cursor state and only the active mode's configuration."""

    return _state(session)


def _position_updates(mode: str, requested: dict[str, Any], config: dict[str, Any]) -> list[tuple[str, str, Any, Any]]:
    if mode == "MANUAL":
        prefix = ":CURSor:MANual:"
        fields = [
            ("manual_type", "TYPE", requested.get("manual_type"), config["type"]),
            ("manual_source", "SOURce", requested.get("manual_source"), config["source"]),
            ("manual_tunit", "TUNit", requested.get("manual_tunit"), config["tunit"]),
            ("manual_vunit", "VUNit", requested.get("manual_vunit"), config["vunit"]),
            ("manual_cax", "CAX", requested.get("manual_cax"), config["screen_positions"]["a"]["x_s"]),
            ("manual_cay", "CAY", requested.get("manual_cay"), config["screen_positions"]["a"]["y_v"]),
            ("manual_cbx", "CBX", requested.get("manual_cbx"), config["screen_positions"]["b"]["x_s"]),
            ("manual_cby", "CBY", requested.get("manual_cby"), config["screen_positions"]["b"]["y_v"]),
        ]
    elif mode == "TRACK":
        prefix = ":CURSor:TRACk:"
        fields = [
            ("track_source1", "SOURce1", requested.get("track_source1"), config["source1"]),
            ("track_source2", "SOURce2", requested.get("track_source2"), config["source2"]),
            ("track_axis", "MODE", requested.get("track_axis"), config["axis"]),
            ("track_cax", "CAX", requested.get("track_cax"), config["screen_positions"]["a"]["x_s"]),
            ("track_cbx", "CBX", requested.get("track_cbx"), config["screen_positions"]["b"]["x_s"]),
            ("track_cay", "CAY", requested.get("track_cay"), config["screen_positions"]["a"]["y_v"]),
            ("track_cby", "CBY", requested.get("track_cby"), config["screen_positions"]["b"]["y_v"]),
        ]
    elif mode == "XY":
        prefix = ":CURSor:XY:"
        fields = [
            ("xy_ax", "AX", requested.get("xy_ax"), config["screen_positions"]["a"]["x_v"]),
            ("xy_bx", "BX", requested.get("xy_bx"), config["screen_positions"]["b"]["x_v"]),
            ("xy_ay", "AY", requested.get("xy_ay"), config["screen_positions"]["a"]["y_v"]),
            ("xy_by", "BY", requested.get("xy_by"), config["screen_positions"]["b"]["y_v"]),
        ]
    else:
        return []
    return [(name, prefix + command, value, old) for name, command, value, old in fields if value is not None]


def set_cursor(
    session: Any,
    *,
    mode: Any = None,
    indicator: Any = None,
    manual_type: Any = None,
    manual_source: Any = None,
    manual_tunit: Any = None,
    manual_vunit: Any = None,
    manual_cax: Any = None,
    manual_cay: Any = None,
    manual_cbx: Any = None,
    manual_cby: Any = None,
    track_source1: Any = None,
    track_source2: Any = None,
    track_axis: Any = None,
    track_cax: Any = None,
    track_cbx: Any = None,
    track_cay: Any = None,
    track_cby: Any = None,
    xy_ax: Any = None,
    xy_bx: Any = None,
    xy_ay: Any = None,
    xy_by: Any = None,
) -> dict[str, Any]:
    """Send only the explicitly requested cursor commands."""

    requested_mode = None if mode is None else _mode(mode)
    requested_indicator = None if indicator is None else _bool_input(indicator, "indicator")
    requested: dict[str, Any] = {
        "manual_type": None if manual_type is None else _manual_type(manual_type),
        "manual_source": None if manual_source is None else _source(manual_source, "manual_source"),
        "manual_tunit": None if manual_tunit is None else _manual_tunit(manual_tunit),
        "manual_vunit": None if manual_vunit is None else _manual_vunit(manual_vunit),
        "manual_cax": None if manual_cax is None else _finite(manual_cax, "manual_cax"),
        "manual_cay": None if manual_cay is None else _finite(manual_cay, "manual_cay"),
        "manual_cbx": None if manual_cbx is None else _finite(manual_cbx, "manual_cbx"),
        "manual_cby": None if manual_cby is None else _finite(manual_cby, "manual_cby"),
        "track_source1": None if track_source1 is None else _source(track_source1, "track_source1"),
        "track_source2": None if track_source2 is None else _source(track_source2, "track_source2"),
        "track_axis": None if track_axis is None else _track_axis(track_axis),
        "track_cax": None if track_cax is None else _finite(track_cax, "track_cax"),
        "track_cbx": None if track_cbx is None else _finite(track_cbx, "track_cbx"),
        "track_cay": None if track_cay is None else _finite(track_cay, "track_cay"),
        "track_cby": None if track_cby is None else _finite(track_cby, "track_cby"),
        "xy_ax": None if xy_ax is None else _finite(xy_ax, "xy_ax"),
        "xy_bx": None if xy_bx is None else _finite(xy_bx, "xy_bx"),
        "xy_ay": None if xy_ay is None else _finite(xy_ay, "xy_ay"),
        "xy_by": None if xy_by is None else _finite(xy_by, "xy_by"),
    }

    supplied_mode_fields = {name for name, value in requested.items() if value is not None}
    groups = [
        ("MANUAL", supplied_mode_fields & _MANUAL_FIELDS),
        ("TRACK", supplied_mode_fields & _TRACK_FIELDS),
        ("XY", supplied_mode_fields & _XY_FIELDS),
    ]
    active_groups = [(name, fields) for name, fields in groups if fields]
    if requested_mode is not None:
        allowed = {"MANUAL": _MANUAL_FIELDS, "TRACK": _TRACK_FIELDS, "XY": _XY_FIELDS, "OFF": set()}[requested_mode]
        invalid = supplied_mode_fields - allowed
        if invalid:
            raise ValueError(f"fields {sorted(invalid)} are not valid for final cursor mode {requested_mode}")
        final_mode = requested_mode
    else:
        if len(active_groups) > 1:
            raise ValueError("mode-specific cursor fields require one explicit mode group")
        final_mode = active_groups[0][0] if active_groups else None

    if final_mode == "OFF" and supplied_mode_fields:
        raise ValueError("mode=OFF cannot be combined with mode-specific cursor fields")

    writes: list[str] = []
    if requested_mode is not None:
        writes.append(":CURSor:MODE " + _MODE_WRITE[requested_mode])
    if requested_indicator is not None:
        writes.append(":CURSor:MEASure:INDicator " + ("1" if requested_indicator else "0"))
    field_commands = {
        "manual_type": ":CURSor:MANual:TYPE", "manual_source": ":CURSor:MANual:SOURce",
        "manual_tunit": ":CURSor:MANual:TUNit", "manual_vunit": ":CURSor:MANual:VUNit",
        "manual_cax": ":CURSor:MANual:CAX", "manual_cay": ":CURSor:MANual:CAY",
        "manual_cbx": ":CURSor:MANual:CBX", "manual_cby": ":CURSor:MANual:CBY",
        "track_source1": ":CURSor:TRACk:SOURce1", "track_source2": ":CURSor:TRACk:SOURce2",
        "track_axis": ":CURSor:TRACk:MODE", "track_cax": ":CURSor:TRACk:CAX",
        "track_cbx": ":CURSor:TRACk:CBX", "track_cay": ":CURSor:TRACk:CAY",
        "track_cby": ":CURSor:TRACk:CBY", "xy_ax": ":CURSor:XY:AX",
        "xy_bx": ":CURSor:XY:BX", "xy_ay": ":CURSor:XY:AY", "xy_by": ":CURSor:XY:BY",
    }
    for name, value in requested.items():
        if value is None:
            continue
        rendered = _scpi_number(value) if isinstance(value, float) else str(value)
        writes.append(f"{field_commands[name]} {rendered}")
    for command in writes:
        session.write(command)
    return {
        "requested": {key: value for key, value in {"mode": requested_mode, "indicator": requested_indicator, **requested}.items() if value is not None},
        "sent": bool(writes),
        "verified": False,
        "commands": writes,
    }


def _reading(session: Any, command: str, unit: str) -> dict[str, Any]:
    raw = str(session.query(command)).strip()
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return {"valid": False, "value": None, "unit": unit, "raw": raw, "reason": "non-numeric or unavailable cursor result"}
    if not math.isfinite(value):
        return {"valid": False, "value": None, "unit": unit, "raw": raw, "reason": "non-finite cursor result"}
    if abs(value) >= _INVALID_SENTINEL:
        return {"valid": False, "value": None, "unit": unit, "raw": raw, "reason": "MHO98 invalid cursor-result sentinel"}
    return {"valid": True, "value": value, "unit": unit, "raw": raw}


def _read_measurements(session: Any, mode: str, config: dict[str, Any]) -> dict[str, Any]:
    if mode == "MANUAL":
        prefix = ":CURSor:MANual:"
        entries = [
            ("ax", "AXValue?", "s"), ("ay", "AYValue?", "source"),
            ("bx", "BXValue?", "s"), ("by", "BYValue?", "source"),
            ("delta_x", "XDELta?", "s"), ("reciprocal_delta_x", "IXDelta?", "Hz"),
            ("delta_y", "YDELta?", "source"),
        ]
    elif mode == "TRACK":
        prefix = ":CURSor:TRACk:"
        entries = [
            ("ax", "AXValue?", "source"), ("ay", "AYValue?", "source"),
            ("bx", "BXValue?", "source"), ("by", "BYValue?", "source"),
            ("delta_x", "XDELta?", "s"), ("delta_y", "YDELta?", "source"),
            ("reciprocal_delta_x", "IXDelta?", "Hz"),
        ]
    elif mode == "XY":
        prefix = ":CURSor:XY:"
        entries = [
            ("ax", "AXValue?", "V"), ("ay", "AYValue?", "V"),
            ("bx", "BXValue?", "V"), ("by", "BYValue?", "V"),
            ("delta_x", "XDELta?", "V"), ("delta_y", "YDELta?", "V"),
        ]
    else:
        return {}
    del config  # Configuration is queried for units/source context before reading.
    return {name: _reading(session, prefix + command, unit) for name, command, unit in entries}


def read_cursor(session: Any) -> dict[str, Any]:
    """Read all documented physical cursor results for the active mode."""

    mode = _query_mode(session)
    context: dict[str, Any] = {}
    if mode == "MANUAL":
        context = {
            "type": _manual_type(session.query(":CURSor:MANual:TYPE?")),
            "source": _source_response(session.query(":CURSor:MANual:SOURce?"), "source"),
            "tunit": _manual_tunit(session.query(":CURSor:MANual:TUNit?")),
            "vunit": _manual_vunit(session.query(":CURSor:MANual:VUNit?")),
        }
    elif mode == "TRACK":
        context = {
            "source1": _source_response(session.query(":CURSor:TRACk:SOURce1?"), "source1"),
            "source2": _source_response(session.query(":CURSor:TRACk:SOURce2?"), "source2"),
            "axis": _track_axis(session.query(":CURSor:TRACk:MODE?")),
        }
    return {"mode": _MODE_RESPONSE[mode], "context": context,
            "readings": _read_measurements(session, mode, context)}


_SET_PROPERTIES = {
    "mode": {"type": "string", "enum": ["OFF", "MANUAL", "TRACK", "XY"], "description": "Cursor mode; XY requires an already-XY timebase."},
    "indicator": {"type": "boolean"},
    "manual_type": {"type": "string", "enum": ["TIME", "AMPLITUDE"]},
    "manual_source": {"type": "string", "enum": sorted(_SOURCE_NAMES)},
    "manual_tunit": {"type": "string", "enum": ["SECOND"]},
    "manual_vunit": {"type": "string", "enum": ["SOURCE"]},
    "manual_cax": {"type": "number", "description": "Manual Cursor A X screen position, seconds."},
    "manual_cay": {"type": "number", "description": "Manual Cursor A Y screen position, source amplitude units."},
    "manual_cbx": {"type": "number", "description": "Manual Cursor B X screen position, seconds."},
    "manual_cby": {"type": "number", "description": "Manual Cursor B Y screen position, source amplitude units."},
    "track_source1": {"type": "string", "enum": sorted(_SOURCE_NAMES)},
    "track_source2": {"type": "string", "enum": sorted(_SOURCE_NAMES)},
    "track_axis": {"type": "string", "enum": ["X", "Y"]},
    "track_cax": {"type": "number", "description": "Track Cursor A X screen position, seconds."},
    "track_cbx": {"type": "number", "description": "Track Cursor B X screen position, seconds."},
    "track_cay": {"type": "number", "description": "Track Cursor A Y screen position, source amplitude units."},
    "track_cby": {"type": "number", "description": "Track Cursor B Y screen position, source amplitude units."},
    "xy_ax": {"type": "number", "description": "XY Cursor A X screen position, volts."},
    "xy_bx": {"type": "number", "description": "XY Cursor B X screen position, volts."},
    "xy_ay": {"type": "number", "description": "XY Cursor A Y screen position, volts."},
    "xy_by": {"type": "number", "description": "XY Cursor B Y screen position, volts."},
}

TOOLS = [
    ToolSpec("get_cursor", "Read global MHO98 cursor state and only the active mode's settings.", {"type": "object", "properties": {}, "required": []}, get_cursor, read_only=True, needs_session=True),
    ToolSpec("set_cursor", "Send named MHO98 cursor fields with static mode-specific validation; omitted fields are untouched and resulting state is not queried.", {"type": "object", "properties": _SET_PROPERTIES, "additionalProperties": False, "required": []}, set_cursor, read_only=False, needs_session=True),
    ToolSpec("read_cursor", "Read all documented physical cursor amplitudes, deltas, and reciprocal delta for the active MHO98 cursor mode.", {"type": "object", "properties": {}, "required": []}, read_cursor, read_only=True, needs_session=True),
]
