"""MHO98 non-image display and quick-key configuration.

This module deliberately excludes ``:DISPlay:DATA?`` screenshot transfer.  The
display action is only the documented waveform clear operation; it never starts
or stops acquisition.
"""

from __future__ import annotations

import math
from numbers import Real
from typing import Any

from .api import ToolSpec


_DISPLAY_TYPE_WRITE = {"VECT": "VECTors"}
_DISPLAY_TYPES = frozenset(_DISPLAY_TYPE_WRITE)
_PERSISTENCE_WRITE = {
    "MIN": "MIN",
    "0.1": "0.1",
    "0.2": "0.2",
    "0.5": "0.5",
    "1": "1",
    "2": "2",
    "5": "5",
    "10": "10",
    "INF": "INFinite",
}
_PERSISTENCE_TOKENS = frozenset(_PERSISTENCE_WRITE)
_GRID_TYPES = frozenset({"FULL", "HALF", "NONE"})
_QUICK_WRITE = {
    "SIM": "SIMage",
    "SWAV": "SWAVe",
    "SSET": "SSETup",
    "AME": "AMEasure",
    "SRES": "SRESet",
    "REC": "RECord",
    "SSAV": "SSAVe",
}
_QUICK_OPERATIONS = frozenset(_QUICK_WRITE)


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


def _display_type(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("display_type must be VECTors or VECT")
    token = value.strip().upper()
    if token == "VECTORS":
        token = "VECT"
    if token not in _DISPLAY_TYPES:
        raise ValueError("display_type must be VECTors or VECT")
    return token


def _persistence(value: Any) -> str:
    """Validate a persistence token without converting numeric tokens to floats."""

    if isinstance(value, bool):
        raise ValueError("persistence_time must be MIN, 0.1, 0.2, 0.5, 1, 2, 5, 10, or INFinite")
    if isinstance(value, Real):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("persistence_time must be a documented persistence token")
        token = format(number, ".15g")
    elif isinstance(value, str):
        token = value.strip().upper()
    else:
        raise ValueError("persistence_time must be a documented persistence token")

    if token == "INFINITE":
        token = "INF"
    if token not in _PERSISTENCE_TOKENS:
        raise ValueError("persistence_time must be MIN, 0.1, 0.2, 0.5, 1, 2, 5, 10, or INFinite")
    # Numeric tokens intentionally remain strings so 1, 0.1, etc. are not
    # changed into a different representation in a readback or SCPI write.
    return token


def _grid(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("grid must be FULL, HALF, or NONE")
    token = value.strip().upper()
    if token not in _GRID_TYPES:
        raise ValueError("grid must be FULL, HALF, or NONE")
    return token


def _percentage(value: Any, name: str, *, minimum: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer from {minimum} through 100")
    if isinstance(value, Real):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            raise ValueError(f"{name} must be an integer from {minimum} through 100") from None
    else:
        raise ValueError(f"{name} must be an integer from {minimum} through 100")
    if not math.isfinite(number) or not number.is_integer() or not minimum <= number <= 100:
        raise ValueError(f"{name} must be an integer from {minimum} through 100")
    return int(number)


def _quick_operation(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("operation must be a documented quick-operation token")
    token = value.strip().upper()
    aliases = {
        "SIMAGE": "SIM",
        "SWAVE": "SWAV",
        "SSETUP": "SSET",
        "AMEASURE": "AME",
        "SRESET": "SRES",
        "RECORD": "REC",
        "SSAVE": "SSAV",
    }
    token = aliases.get(token, token)
    if token not in _QUICK_OPERATIONS:
        raise ValueError("operation must be SIMage, SWAVe, SSETup, AMEasure, SRESet, RECord, or SSAVe")
    return token


def _query_display(session: Any) -> dict[str, Any]:
    """Read every documented non-image display setting."""

    return {
        "display_type": _display_type(session.query(":DISPlay:TYPE?")),
        "persistence_time": _persistence(session.query(":DISPlay:GRADing:TIME?")),
        "waveform_brightness": _percentage(
            session.query(":DISPlay:WBRightness?"), "waveform_brightness", minimum=1
        ),
        "grid": _grid(session.query(":DISPlay:GRID?")),
        "grid_brightness": _percentage(
            session.query(":DISPlay:GBRightness?"), "grid_brightness", minimum=0
        ),
        "cursor_brightness": _percentage(
            session.query(":DISPlay:CBRightness?"), "cursor_brightness", minimum=0
        ),
        "rulers": _bool_response(session.query(":DISPlay:RULers?"), "rulers"),
        "ruler_tracking": _bool_response(session.query(":DISPlay:MOVE?"), "ruler_tracking"),
        "color": _bool_response(session.query(":DISPlay:COLor?"), "color"),
        "wavehold": _bool_response(session.query(":DISPlay:WHOLd?"), "wavehold"),
    }


def get_display(session: Any) -> dict[str, Any]:
    """Return the effective non-image display configuration."""

    return _query_display(session)


def set_display(
    session: Any,
    *,
    display_type: Any = None,
    persistence_time: Any = None,
    waveform_brightness: Any = None,
    grid: Any = None,
    grid_brightness: Any = None,
    cursor_brightness: Any = None,
    rulers: Any = None,
    ruler_tracking: Any = None,
    color: Any = None,
    wavehold: Any = None,
) -> dict[str, Any]:
    """Send only explicitly requested display fields without readback."""

    requested = {
        "display_type": None if display_type is None else _display_type(display_type),
        "persistence_time": None if persistence_time is None else _persistence(persistence_time),
        "waveform_brightness": (
            None
            if waveform_brightness is None
            else _percentage(waveform_brightness, "waveform_brightness", minimum=1)
        ),
        "grid": None if grid is None else _grid(grid),
        "grid_brightness": (
            None
            if grid_brightness is None
            else _percentage(grid_brightness, "grid_brightness", minimum=0)
        ),
        "cursor_brightness": (
            None
            if cursor_brightness is None
            else _percentage(cursor_brightness, "cursor_brightness", minimum=0)
        ),
        "rulers": None if rulers is None else _bool_input(rulers, "rulers"),
        "ruler_tracking": (
            None if ruler_tracking is None else _bool_input(ruler_tracking, "ruler_tracking")
        ),
        "color": None if color is None else _bool_input(color, "color"),
        "wavehold": None if wavehold is None else _bool_input(wavehold, "wavehold"),
    }

    writes: list[str] = []
    if requested["display_type"] is not None:
        writes.append(":DISPlay:TYPE " + _DISPLAY_TYPE_WRITE[requested["display_type"]])
    if requested["persistence_time"] is not None:
        writes.append(":DISPlay:GRADing:TIME " + _PERSISTENCE_WRITE[requested["persistence_time"]])
    if requested["grid"] is not None:
        writes.append(":DISPlay:GRID " + requested["grid"])
    for field, command in (
        ("waveform_brightness", ":DISPlay:WBRightness"),
        ("grid_brightness", ":DISPlay:GBRightness"),
        ("cursor_brightness", ":DISPlay:CBRightness"),
    ):
        if requested[field] is not None:
            writes.append(f"{command} {requested[field]}")
    for field, command in (
        ("rulers", ":DISPlay:RULers"),
        ("ruler_tracking", ":DISPlay:MOVE"),
        ("color", ":DISPlay:COLor"),
        ("wavehold", ":DISPlay:WHOLd"),
    ):
        if requested[field] is not None:
            writes.append(f"{command} {1 if requested[field] else 0}")

    for command in writes:
        session.write(command)
    sent = {key: value for key, value in requested.items() if value is not None}
    return {"sent": bool(writes), "verified": False, "commands": writes, "requested": sent, **sent}


def display_action(session: Any, *, action: Any) -> dict[str, Any]:
    """Send the explicit waveform-clear command without readback."""

    if not isinstance(action, str) or action.strip().upper() != "CLEAR":
        raise ValueError("action must be CLEAR")
    command = ":DISPlay:CLEar"
    session.write(command)
    return {"sent": True, "verified": False, "commands": [command], "action": "clear"}


def get_quick_action(session: Any) -> dict[str, str]:
    """Read the quick-key assignment without performing it."""

    return {"operation": _quick_operation(session.query(":QUICk:OPERation?"))}


def set_quick_action(session: Any, *, operation: Any = None) -> dict[str, Any]:
    """Set only the quick-key assignment; never invoke the assigned action."""

    requested = None if operation is None else _quick_operation(operation)
    commands = [] if requested is None else [":QUICk:OPERation " + _QUICK_WRITE[requested]]
    for command in commands:
        session.write(command)
    result = {"sent": bool(commands), "verified": False, "commands": commands}
    if requested is not None:
        result.update(operation=requested, requested={"operation": requested})
    else:
        result["requested"] = {}
    return result


_DISPLAY_PROPERTIES = {
    "display_type": {"type": "string", "enum": ["VECTors", "VECT"]},
    "persistence_time": {
        "type": ["string", "number"],
        "enum": [
            "MIN", "0.1", "0.2", "0.5", "1", "2", "5", "10", "INFinite", "INF",
            0.1, 0.2, 0.5, 1, 2, 5, 10,
        ],
    },
    "waveform_brightness": {"type": "integer", "minimum": 1, "maximum": 100},
    "grid": {"type": "string", "enum": sorted(_GRID_TYPES)},
    "grid_brightness": {"type": "integer", "minimum": 0, "maximum": 100},
    "cursor_brightness": {"type": "integer", "minimum": 0, "maximum": 100},
    "rulers": {"type": "boolean"},
    "ruler_tracking": {"type": "boolean"},
    "color": {"type": "boolean"},
    "wavehold": {"type": "boolean"},
}

_QUICK_PROPERTY = {
    "type": "string",
    "enum": ["SIMage", "SIM", "SWAVe", "SWAV", "SSETup", "SSET", "AMEasure", "AME", "SRESet", "SRES", "RECord", "REC", "SSAVe", "SSAV"],
}

TOOLS = [
    ToolSpec(
        "get_display",
        "Read MHO98 non-image waveform display settings, including persistence, grid, brightness, rulers, color grade, and wavehold.",
        {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        get_display,
        read_only=True,
        needs_session=True,
    ),
    ToolSpec(
        "set_display",
        "Send selected MHO98 non-image display commands; omitted settings and acquisition RUN/STOP state are preserved and resulting state is not verified.",
        {"type": "object", "properties": _DISPLAY_PROPERTIES, "required": [], "additionalProperties": False},
        set_display,
        read_only=False,
        needs_session=True,
    ),
    ToolSpec(
        "display_action",
        "Send the explicit MHO98 waveform-clear command; this never starts or stops acquisition.",
        {"type": "object", "properties": {"action": {"type": "string", "enum": ["CLEAR", "clear"]}}, "required": ["action"], "additionalProperties": False},
        display_action,
        read_only=False,
        needs_session=True,
    ),
    ToolSpec(
        "get_quick_action",
        "Read the MHO98 quick-key assignment without performing the assigned operation.",
        {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        get_quick_action,
        read_only=True,
        needs_session=True,
    ),
    ToolSpec(
        "set_quick_action",
        "Send only the MHO98 quick-key assignment; never perform the assigned quick operation or read it back.",
        {"type": "object", "properties": {"operation": _QUICK_PROPERTY}, "required": [], "additionalProperties": False},
        set_quick_action,
        read_only=False,
        needs_session=True,
    ),
]
