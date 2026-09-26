"""Bounded MHO98 horizontal time-base controls."""

from __future__ import annotations

import math
from numbers import Real
from typing import Any

from .api import ToolSpec


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


def _bool(value: Any, name: str) -> bool:
    text = str(value).strip().upper()
    if text in {"1", "ON", "TRUE"}:
        return True
    if text in {"0", "OFF", "FALSE"}:
        return False
    raise ValueError(f"invalid {name} response from MHO98: {value!r}")


def _mode(value: Any) -> str:
    text = str(value).strip().upper()
    if text not in {"MAIN", "XY", "ROLL"}:
        raise ValueError("mode must be MAIN, XY, or ROLL")
    return text


def _source(value: Any, name: str) -> str:
    text = str(value).strip().upper().replace(" ", "")
    if text.startswith("CHANNEL"):
        text = "CHAN" + text[7:]
    elif text.startswith("CH") and not text.startswith("CHAN"):
        text = "CHAN" + text[2:]
    if text not in {"CHAN1", "CHAN2", "CHAN3", "CHAN4"}:
        raise ValueError(f"{name} must be CHAN1 through CHAN4")
    return text


def _grid(value: Any) -> str:
    text = str(value).strip().upper()
    if text not in {"FULL", "HALF", "NONE"}:
        raise ValueError("xy_grid must be FULL, HALF, or NONE")
    return text


def _reference_mode(value: Any) -> str:
    text = str(value).strip().upper()
    aliases = {"CENTER": "CENTER", "CENT": "CENTER", "LB": "LB", "RB": "RB", "TRIG": "TRIG", "USER": "USER"}
    if text not in aliases:
        raise ValueError("reference_mode must be CENTER, LB, RB, TRIG, or USER")
    return aliases[text]


def _integer(value: Any, name: str, low: int, high: int) -> int:
    number = _finite(value, name)
    if not number.is_integer() or not low <= number <= high:
        raise ValueError(f"{name} must be an integer from {low} through {high}")
    return int(number)


def _scpi_number(value: float) -> str:
    return format(value, ".15g")


def _positive_response(value: Any, name: str) -> float:
    result = _finite(value, name)
    if result <= 0:
        raise ValueError(f"invalid {name} response from MHO98: {value!r}")
    return result


def _query_timebase(session: Any) -> dict[str, Any]:
    raw_mode = _mode(session.query(":TIMebase:MODE?"))
    xy_enabled = _bool(session.query(":TIMebase:XY:ENABle?"), "xy_enabled")
    # MHO98 reports MAIN for MODE? after XY has been enabled.  The explicit XY
    # enable query is therefore part of the effective mode readback.
    effective_mode = "XY" if xy_enabled else raw_mode
    return {
        "scale_s_div": _positive_response(session.query(":TIMebase:MAIN:SCALe?"), "scale_s_div"),
        "offset_s": _finite(session.query(":TIMebase:MAIN:OFFSet?"), "offset_s"),
        "mode": effective_mode,
        "xy_enabled": xy_enabled,
        "zoom_enabled": _bool(session.query(":TIMebase:DELay:ENABle?"), "zoom_enabled"),
        "zoom_scale_s_div": _positive_response(session.query(":TIMebase:DELay:SCALe?"), "zoom_scale_s_div"),
        "zoom_offset_s": _finite(session.query(":TIMebase:DELay:OFFSet?"), "zoom_offset_s"),
        "auto_roll": _bool(session.query(":TIMebase:ROLL?"), "auto_roll"),
        "xy_x": _source(session.query(":TIMebase:XY:X?"), "xy_x"),
        "xy_y": _source(session.query(":TIMebase:XY:Y?"), "xy_y"),
        "xy_grid": _grid(session.query(":TIMebase:XY:GRID?")),
        "reference_mode": _reference_mode(session.query(":TIMebase:HREFerence:MODE?")),
        "reference_position": _integer(session.query(":TIMebase:HREFerence:POSition?"), "reference_position", -500, 500),
        "fine_scale": _bool(session.query(":TIMebase:VERNier?"), "fine_scale"),
    }


def get_timebase(session: Any) -> dict[str, Any]:
    """Return effective MHO98 time-base settings, including XY readback state."""

    return _query_timebase(session)


def _validate_zoom_offset(offset: float, main_scale: float, main_offset: float, zoom_scale: float) -> None:
    # The guide defines a ten-division delayed sweep range around the main
    # window.  This is a documented dependency, unlike the STOP-state memory
    # range for main offset, which is intentionally left to the instrument.
    left_time = 5.0 * main_scale - main_offset
    right_time = 5.0 * main_scale + main_offset
    delay_range = 10.0 * zoom_scale
    low = -(left_time - delay_range / 2.0)
    high = right_time - delay_range / 2.0
    if not low <= offset <= high:
        raise ValueError(f"zoom_offset_s {offset:g} is outside the documented range {low:g}..{high:g}")


def _validate_main_offset_run(offset: float, scale: float, trigger_status: Any) -> None:
    """Apply the documented RUN limits; STOP limits depend on memory sampling."""

    status = str(trigger_status).strip().upper()
    if status == "STOP":
        return
    minimum = -5.0 * scale
    if scale <= 0.01:
        maximum = 1.0
    elif scale < 10.0:
        maximum = 100.0 * scale
    elif scale < 200.0:
        maximum = 1000.0
    else:
        maximum = 5.0 * scale
    if not minimum <= offset <= maximum:
        raise ValueError(
            f"offset_s {offset:g} is outside the RUN range {minimum:g}..{maximum:g} "
            f"for scale_s_div {scale:g}"
        )


def set_timebase(
    session: Any,
    *,
    scale_s_div: Any = None,
    offset_s: Any = None,
    mode: Any = None,
    zoom_enabled: Any = None,
    zoom_scale_s_div: Any = None,
    zoom_offset_s: Any = None,
    auto_roll: Any = None,
    xy_x: Any = None,
    xy_y: Any = None,
    xy_grid: Any = None,
    reference_mode: Any = None,
    reference_position: Any = None,
    fine_scale: Any = None,
) -> dict[str, Any]:
    """Send only explicitly requested time-base fields without readback."""

    requested_scale = None if scale_s_div is None else _finite(scale_s_div, "scale_s_div")
    if requested_scale is not None and requested_scale <= 0:
        raise ValueError("scale_s_div must be positive")
    requested_offset = None if offset_s is None else _finite(offset_s, "offset_s")
    requested_mode = None if mode is None else _mode(mode)
    requested_zoom_enabled = None if zoom_enabled is None else _bool(zoom_enabled, "zoom_enabled")
    requested_zoom_scale = None if zoom_scale_s_div is None else _finite(zoom_scale_s_div, "zoom_scale_s_div")
    if requested_zoom_scale is not None and requested_zoom_scale <= 0:
        raise ValueError("zoom_scale_s_div must be positive")
    requested_zoom_offset = None if zoom_offset_s is None else _finite(zoom_offset_s, "zoom_offset_s")
    requested_auto_roll = None if auto_roll is None else _bool(auto_roll, "auto_roll")
    requested_xy_x = None if xy_x is None else _source(xy_x, "xy_x")
    requested_xy_y = None if xy_y is None else _source(xy_y, "xy_y")
    requested_xy_grid = None if xy_grid is None else _grid(xy_grid)
    requested_reference_mode = None if reference_mode is None else _reference_mode(reference_mode)
    requested_reference_position = None if reference_position is None else _integer(reference_position, "reference_position", -500, 500)
    requested_fine_scale = None if fine_scale is None else _bool(fine_scale, "fine_scale")

    if requested_mode == "ROLL" and requested_zoom_enabled is True:
        raise ValueError("zoom must be disabled before using ROLL mode")
    if requested_zoom_scale is not None and requested_scale is not None and requested_zoom_scale > requested_scale:
        raise ValueError("zoom_scale_s_div cannot exceed main scale_s_div")
    if all(value is not None for value in (requested_zoom_offset, requested_scale, requested_offset, requested_zoom_scale)):
        _validate_zoom_offset(requested_zoom_offset, requested_scale, requested_offset, requested_zoom_scale)

    writes: list[str] = []
    main = ":TIMebase:MAIN:"
    delay = ":TIMebase:DELay:"
    xy = ":TIMebase:XY:"
    href = ":TIMebase:HREFerence:"
    # An explicit mode owns the XY enable command needed to route that mode.  No
    # current-mode or current-enable query is needed.
    if requested_mode is not None:
        if requested_mode == "XY":
            writes.extend((":TIMebase:MODE XY", xy + "ENABle 1"))
        else:
            writes.extend((xy + "ENABle 0", ":TIMebase:MODE " + requested_mode))

    if requested_scale is not None:
        writes.append(main + "SCALe " + _scpi_number(requested_scale))
    if requested_offset is not None:
        writes.append(main + "OFFSet " + _scpi_number(requested_offset))
    if requested_zoom_enabled is not None:
        writes.append(delay + "ENABle " + ("1" if requested_zoom_enabled else "0"))
    if requested_zoom_scale is not None:
        writes.append(delay + "SCALe " + _scpi_number(requested_zoom_scale))
    if requested_zoom_offset is not None:
        writes.append(delay + "OFFSet " + _scpi_number(requested_zoom_offset))
    if requested_auto_roll is not None:
        writes.append(":TIMebase:ROLL " + ("1" if requested_auto_roll else "0"))
    if requested_xy_x is not None:
        writes.append(xy + "X " + requested_xy_x)
    if requested_xy_y is not None:
        writes.append(xy + "Y " + requested_xy_y)
    if requested_xy_grid is not None:
        writes.append(xy + "GRID " + requested_xy_grid)
    if requested_reference_mode is not None:
        token = "CENTer" if requested_reference_mode == "CENTER" else requested_reference_mode
        writes.append(href + "MODE " + token)
    if requested_reference_position is not None:
        writes.append(href + "POSition " + str(requested_reference_position))
    if requested_fine_scale is not None:
        writes.append(":TIMebase:VERNier " + ("1" if requested_fine_scale else "0"))

    for command in writes:
        session.write(command)
    requested = {
        key: value for key, value in {
            "scale_s_div": requested_scale, "offset_s": requested_offset, "mode": requested_mode,
            "zoom_enabled": requested_zoom_enabled, "zoom_scale_s_div": requested_zoom_scale,
            "zoom_offset_s": requested_zoom_offset, "auto_roll": requested_auto_roll,
            "xy_x": requested_xy_x, "xy_y": requested_xy_y, "xy_grid": requested_xy_grid,
            "reference_mode": requested_reference_mode, "reference_position": requested_reference_position,
            "fine_scale": requested_fine_scale,
        }.items() if value is not None
    }
    return {"sent": bool(writes), "verified": False, "commands": writes, "requested": requested, **requested}


_TIMEBASE_SCHEMA = {
    "type": "object",
    "properties": {
        "scale_s_div": {"type": "number"},
        "offset_s": {"type": "number"},
        "mode": {"type": "string", "enum": ["MAIN", "XY", "ROLL"]},
        "zoom_enabled": {"type": "boolean"},
        "zoom_scale_s_div": {"type": "number"},
        "zoom_offset_s": {"type": "number"},
        "auto_roll": {"type": "boolean"},
        "xy_x": {"type": "string", "enum": ["CHAN1", "CHAN2", "CHAN3", "CHAN4"]},
        "xy_y": {"type": "string", "enum": ["CHAN1", "CHAN2", "CHAN3", "CHAN4"]},
        "xy_grid": {"type": "string", "enum": ["FULL", "HALF", "NONE"]},
        "reference_mode": {"type": "string", "enum": ["CENTER", "LB", "RB", "TRIG", "USER"]},
        "reference_position": {"type": "integer", "minimum": -500, "maximum": 500},
        "fine_scale": {"type": "boolean"},
    },
    "required": [],
}

TOOLS = [
    ToolSpec(
        name="get_timebase",
        description="Read effective MHO98 horizontal time-base, zoom, XY, roll, reference, and fine-scale settings.",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=get_timebase,
        read_only=True,
        needs_session=True,
    ),
    ToolSpec(
        name="set_timebase",
        description="Send selected MHO98 time-base commands with explicit-input validation; resulting values are not verified.",
        input_schema=_TIMEBASE_SCHEMA,
        handler=set_timebase,
        read_only=False,
        needs_session=True,
    ),
]
