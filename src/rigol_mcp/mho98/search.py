"""MHO98 search-event and waveform-navigation controls.

The programming guide exposes search configuration, an indexed event-time
table, and navigation as separate SCPI subtrees.  This module keeps those
pieces together so that mode-dependent fields are queried and written only
when they apply.
"""

from __future__ import annotations

import math
import re
from numbers import Real
from typing import Any

from .api import ToolSpec


_MAX_EVENT_LIMIT = 1000
_MAX_EVENT_COUNT = 10_000_000
_WIDTH_MIN_S = 800e-12
_WIDTH_MAX_S = 10.0
_NUMBER_RE = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_VALUE_RE = re.compile(rf"^({_NUMBER_RE})\s*([A-Za-zµμ]*)$")

_MODE_WRITE = {"EDGE": "EDGE", "PULSE": "PULSe"}
_SLOPE_WRITE = {"POSITIVE": "POSitive", "NEGATIVE": "NEGative", "EITHER": "EITHer"}
_POLARITY_WRITE = {"POSITIVE": "POSitive", "NEGATIVE": "NEGative"}
_QUALIFIER_WRITE = {"GREATER": "GREater", "LESS": "LESS", "BETWEEN": "GLESs"}
_SPEED_WRITE = {"HIGH": "HIGH", "NORMAL": "NORMal", "LOW": "LOW"}


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
    number = _finite(value, name)
    if not number.is_integer() or not low <= number <= high:
        raise ValueError(f"{name} must be an integer from {low} through {high}")
    return int(number)


def _source(value: Any, name: str = "source") -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be CHAN1 through CHAN4")
    token = value.strip().upper().replace(" ", "")
    if token.startswith("CHANNEL"):
        token = "CHAN" + token[7:]
    elif token.startswith("CH") and not token.startswith("CHAN"):
        token = "CHAN" + token[2:]
    if token not in {"CHAN1", "CHAN2", "CHAN3", "CHAN4"}:
        raise ValueError(f"{name} must be CHAN1 through CHAN4")
    return token


def _mode(value: Any, name: str = "mode") -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be EDGE or PULSE")
    token = value.strip().upper()
    if token in {"EDGE", "EDGe".upper()}:
        return "EDGE"
    if token in {"PULSE", "PULS"}:
        return "PULSE"
    raise ValueError(f"{name} must be EDGE or PULSE")


def _slope(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("slope must be POSITIVE, NEGATIVE, or EITHER")
    token = value.strip().upper()
    aliases = {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE", "EITH": "EITHER", "EITHER": "EITHER"}
    if token not in aliases:
        raise ValueError("slope must be POSITIVE, NEGATIVE, or EITHER")
    return aliases[token]


def _polarity(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("polarity must be POSITIVE or NEGATIVE")
    token = value.strip().upper()
    aliases = {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE"}
    if token not in aliases:
        raise ValueError("polarity must be POSITIVE or NEGATIVE")
    return aliases[token]


def _qualifier(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("qualifier must be GREATER, LESS, or BETWEEN")
    token = value.strip().upper()
    aliases = {
        "GRE": "GREATER", "GREATER": "GREATER",
        "LESS": "LESS", "GLES": "BETWEEN", "BETWEEN": "BETWEEN",
    }
    if token not in aliases:
        raise ValueError("qualifier must be GREATER, LESS, or BETWEEN")
    return aliases[token]


def _speed(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("speed must be HIGH, NORMAL, or LOW")
    token = value.strip().upper()
    aliases = {"HIGH": "HIGH", "NORM": "NORMAL", "NORMAL": "NORMAL", "LOW": "LOW"}
    if token not in aliases:
        raise ValueError("speed must be HIGH, NORMAL, or LOW")
    return aliases[token]


def _count_response(value: Any) -> int:
    return _integer(value, "search event count", 0, _MAX_EVENT_COUNT)


def _selected_response(value: Any, count: int) -> int:
    return _integer(value, "selected event", 0, count)


def _response_enum(value: Any, aliases: dict[str, str], name: str) -> str:
    token = str(value).strip().upper()
    normalized = {key.upper(): result for key, result in aliases.items()}.get(token)
    if normalized is None:
        raise ValueError(f"invalid {name} response from MHO98: {value!r}")
    return normalized


def _scpi_number(value: float) -> str:
    return format(value, ".15g")


def _width(value: Any, name: str) -> float:
    result = _finite(value, name)
    if not _WIDTH_MIN_S <= result <= _WIDTH_MAX_S:
        raise ValueError(f"{name} must be between 800 ps and 10 s")
    return result


def _query_common(session: Any) -> dict[str, Any]:
    enabled = _bool_response(session.query(":SEARch:STATe?"), "search enabled")
    mode = _response_enum(session.query(":SEARch:MODE?"), {"EDGE": "EDGE", "EDG": "EDGE", "PULS": "PULSE", "PULSE": "PULSE"}, "search mode")
    count = _count_response(session.query(":SEARch:COUNt?"))
    selected = _selected_response(session.query(":SEARch:EVENt?"), count)
    return {"enabled": enabled, "mode": mode, "count": count, "selected_event": selected}


def _query_mode_fields(session: Any, mode: str) -> dict[str, Any]:
    if mode == "EDGE":
        return {
            "slope": _response_enum(session.query(":SEARch:EDGE:SLOPe?"), {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE", "EITH": "EITHER", "EITHER": "EITHER"}, "edge slope"),
            "source": _source(session.query(":SEARch:EDGE:SOURce?"), "edge source"),
            "threshold_v": _finite(session.query(":SEARch:EDGE:THReshold?"), "edge threshold"),
        }
    return {
        "polarity": _response_enum(session.query(":SEARch:PULSe:POLarity?"), {"POS": "POSITIVE", "POSITIVE": "POSITIVE", "NEG": "NEGATIVE", "NEGATIVE": "NEGATIVE"}, "pulse polarity"),
        "qualifier": _response_enum(session.query(":SEARch:PULSe:QUALifier?"), {"GRE": "GREATER", "GREATER": "GREATER", "LESS": "LESS", "GLES": "BETWEEN", "BETWEEN": "BETWEEN"}, "pulse qualifier"),
        "source": _source(session.query(":SEARch:PULSe:SOURce?"), "pulse source"),
        "upper_width_s": _width(session.query(":SEARch:PULSe:UWIDth?"), "upper pulse width"),
        "lower_width_s": _width(session.query(":SEARch:PULSe:LWIDth?"), "lower pulse width"),
        "threshold_v": _finite(session.query(":SEARch:PULSe:THReshold?"), "pulse threshold"),
    }


def _query_search(session: Any) -> dict[str, Any]:
    result = _query_common(session)
    result.update(_query_mode_fields(session, result["mode"]))
    return result


def get_search(session: Any) -> dict[str, Any]:
    """Read search configuration, event count, and selected event."""

    return _query_search(session)


def set_search(
    session: Any,
    *,
    enabled: Any = None,
    mode: Any = None,
    slope: Any = None,
    polarity: Any = None,
    qualifier: Any = None,
    source: Any = None,
    threshold_v: Any = None,
    lower_width_s: Any = None,
    upper_width_s: Any = None,
    selected_event: Any = None,
) -> dict[str, Any]:
    """Send only explicitly requested search fields.

    If a mode-dependent field is supplied without ``mode``, one mode selector
    query is used to choose EDGE or PULSE routing; no other setting is read.
    """

    requested_enabled = None if enabled is None else _bool_input(enabled, "enabled")
    requested_mode = None if mode is None else _mode(mode)
    requested_slope = None if slope is None else _slope(slope)
    requested_polarity = None if polarity is None else _polarity(polarity)
    requested_qualifier = None if qualifier is None else _qualifier(qualifier)
    requested_source = None if source is None else _source(source)
    requested_threshold = None if threshold_v is None else _finite(threshold_v, "threshold_v")
    requested_lower = None if lower_width_s is None else _width(lower_width_s, "lower_width_s")
    requested_upper = None if upper_width_s is None else _width(upper_width_s, "upper_width_s")

    pulse_fields = any(value is not None for value in (requested_polarity, requested_qualifier, requested_lower, requested_upper))
    edge_fields = requested_slope is not None
    if requested_mode == "EDGE" and pulse_fields:
        raise ValueError("polarity, qualifier, and pulse widths apply only to PULSE mode")
    if requested_mode == "PULSE" and edge_fields:
        raise ValueError("slope applies only to EDGE mode")
    if pulse_fields and edge_fields:
        raise ValueError("EDGE and PULSE fields cannot be combined without one mode")

    route_mode = requested_mode
    needs_mode_route = pulse_fields or edge_fields or requested_source is not None or requested_threshold is not None
    if route_mode is None and needs_mode_route:
        # This is the sole allowed selector query: it selects the command
        # subtree, without loading or validating the rest of search state.
        route_mode = _response_enum(session.query(":SEARch:MODE?"), {"EDGE": "EDGE", "EDG": "EDGE", "PULS": "PULSE", "PULSE": "PULSE"}, "search mode")
    if route_mode == "PULSE" and requested_qualifier == "BETWEEN" and requested_lower is not None and requested_upper is not None and requested_lower >= requested_upper:
        raise ValueError("lower_width_s must be smaller than upper_width_s for BETWEEN")

    requested_event = None if selected_event is None else _integer(selected_event, "selected_event", 0, _MAX_EVENT_COUNT)

    writes: list[str] = []
    if requested_mode is not None:
        writes.append(f":SEARch:MODE {_MODE_WRITE[requested_mode]}")

    if route_mode == "EDGE":
        if requested_slope is not None:
            writes.append(f":SEARch:EDGE:SLOPe {_SLOPE_WRITE[requested_slope]}")
        if requested_source is not None:
            writes.append(f":SEARch:EDGE:SOURce {requested_source}")
        if requested_threshold is not None:
            writes.append(f":SEARch:EDGE:THReshold {_scpi_number(requested_threshold)}")
    elif route_mode == "PULSE":
        if requested_polarity is not None:
            writes.append(f":SEARch:PULSe:POLarity {_POLARITY_WRITE[requested_polarity]}")
        if requested_qualifier is not None:
            writes.append(f":SEARch:PULSe:QUALifier {_QUALIFIER_WRITE[requested_qualifier]}")
        if requested_source is not None:
            writes.append(f":SEARch:PULSe:SOURce {requested_source}")
        if requested_upper is not None:
            writes.append(f":SEARch:PULSe:UWIDth {_scpi_number(requested_upper)}")
        if requested_lower is not None:
            writes.append(f":SEARch:PULSe:LWIDth {_scpi_number(requested_lower)}")
        if requested_threshold is not None:
            writes.append(f":SEARch:PULSe:THReshold {_scpi_number(requested_threshold)}")

    if requested_event is not None:
        writes.append(f":SEARch:EVENt {requested_event}")
    if requested_enabled is not None:
        writes.append(":SEARch:STATe " + ("1" if requested_enabled else "0"))

    for command in writes:
        session.write(command)
    return {
        "requested": {key: value for key, value in {
            "enabled": requested_enabled, "mode": requested_mode, "slope": requested_slope,
            "polarity": requested_polarity, "qualifier": requested_qualifier, "source": requested_source,
            "threshold_v": requested_threshold, "lower_width_s": requested_lower,
            "upper_width_s": requested_upper, "selected_event": requested_event,
        }.items() if value is not None},
        "sent": bool(writes),
        "verified": False,
        "commands": writes,
    }


def _event_value(raw: Any) -> dict[str, Any]:
    text = str(raw).strip()
    match = _VALUE_RE.fullmatch(text)
    if match is None:
        raise ValueError(f"invalid search event value from MHO98: {raw!r}")
    value = float(match.group(1))
    if not math.isfinite(value):
        raise ValueError(f"invalid search event value from MHO98: {raw!r}")
    # The guide specifies a time value.  Keep an instrument-supplied suffix as
    # written; an unsuffixed SCPI real is reported in seconds by this command.
    unit = match.group(2) or "s"
    return {"value": value, "unit": unit, "raw": text}


def read_search_events(session: Any, *, start: Any = 1, limit: Any = 100) -> dict[str, Any]:
    """Read a bounded 1-based slice of the actual search event-value table."""

    first = _integer(start, "start", 1, _MAX_EVENT_COUNT)
    requested_limit = _integer(limit, "limit", 1, _MAX_EVENT_LIMIT)
    count = _count_response(session.query(":SEARch:COUNt?"))
    result: dict[str, Any] = {
        "count": count,
        "start": first,
        "limit": requested_limit,
        "returned": 0,
        "events": [],
    }
    if count == 0:
        return result
    if first > count:
        raise ValueError(f"start must be from 1 through the current event count ({count})")
    stop = min(count, first + requested_limit - 1)
    events = []
    for index in range(first, stop + 1):
        event = _event_value(session.query(f":SEARch:VALue? {index}"))
        event["index"] = index
        events.append(event)
    mode = _response_enum(session.query(":SEARch:MODE?"), {"EDGE": "EDGE", "EDG": "EDGE", "PULS": "PULSE", "PULSE": "PULSE"}, "search mode")
    result["context"] = {"mode": mode, **_query_mode_fields(session, mode)}
    result["events"] = events
    result["returned"] = len(events)
    return result


def _query_navigation_base(session: Any) -> dict[str, Any]:
    return {
        "enabled": _bool_response(session.query(":NAVigate:ENABle?"), "navigation enabled"),
        "mode": _response_enum(session.query(":NAVigate:MODE?"), {"TIME": "TIME", "SEAR": "SEARCH", "SEARCH": "SEARCH"}, "navigation mode"),
    }


def _query_navigation(session: Any) -> dict[str, Any]:
    result = _query_navigation_base(session)
    if result["mode"] == "TIME":
        result["speed"] = _response_enum(session.query(":NAVigate:TIME:SPEed?"), {"HIGH": "HIGH", "NORM": "NORMAL", "NORMAL": "NORMAL", "LOW": "LOW"}, "navigation speed")
        result["play"] = _bool_response(session.query(":NAVigate:TIME:PLAY?"), "navigation play")
    return result


def get_navigation(session: Any) -> dict[str, Any]:
    """Read navigation settings; TIME-only playback fields are conditional."""

    return _query_navigation(session)


def set_navigation(
    session: Any,
    *,
    enabled: Any = None,
    mode: Any = None,
    speed: Any = None,
    play: Any = None,
) -> dict[str, Any]:
    """Send only explicitly requested navigation fields."""

    requested_enabled = None if enabled is None else _bool_input(enabled, "enabled")
    requested_mode = None if mode is None else _response_enum(mode, {"TIME": "TIME", "SEARCH": "SEARCH", "SEAR": "SEARCH"}, "navigation mode")
    requested_speed = None if speed is None else _speed(speed)
    requested_play = None if play is None else _bool_input(play, "play")

    if requested_mode == "SEARCH" and (requested_speed is not None or requested_play is not None):
        raise ValueError("speed and play apply only to TIME navigation")

    writes: list[str] = []
    if requested_mode is not None:
        navigation_mode = "SEARch" if requested_mode == "SEARCH" else "TIME"
        writes.append(f":NAVigate:MODE {navigation_mode}")
    if requested_speed is not None:
        writes.append(f":NAVigate:TIME:SPEed {_SPEED_WRITE[requested_speed]}")
    if requested_enabled is not None:
        writes.append(":NAVigate:ENABle " + ("1" if requested_enabled else "0"))
    if requested_play is not None:
        writes.append(":NAVigate:TIME:PLAY " + ("1" if requested_play else "0"))

    for command in writes:
        session.write(command)
    return {
        "requested": {key: value for key, value in {
            "enabled": requested_enabled, "mode": requested_mode, "speed": requested_speed, "play": requested_play,
        }.items() if value is not None},
        "sent": bool(writes),
        "verified": False,
        "commands": writes,
    }


def navigate(session: Any, *, mode: Any, action: Any) -> dict[str, Any]:
    """Perform one explicit first/last/next/back navigation action."""

    selected_mode = _response_enum(mode, {"TIME": "TIME", "SEARCH": "SEARCH", "SEAR": "SEARCH"}, "navigation mode")
    if not isinstance(action, str):
        raise ValueError("action must be FIRST, LAST, NEXT, or BACK")
    selected_action = action.strip().upper()
    actions = {"FIRST": "STARt", "START": "STARt", "LAST": "END", "END": "END", "NEXT": "NEXT", "BACK": "BACK"}
    command_action = actions.get(selected_action)
    if command_action is None:
        raise ValueError("action must be FIRST, LAST, NEXT, or BACK")
    navigation_mode = "SEARch" if selected_mode == "SEARCH" else "TIME"
    command = f":NAVigate:{navigation_mode}:{command_action}"
    session.write(command)
    return {"mode": selected_mode, "action": selected_action, "sent": True, "verified": False, "commands": [command]}


_SET_SEARCH_PROPERTIES = {
    "enabled": {"type": "boolean"},
    "mode": {"type": "string", "enum": ["EDGE", "PULSE"]},
    "slope": {"type": "string", "enum": ["POSITIVE", "NEGATIVE", "EITHER"]},
    "polarity": {"type": "string", "enum": ["POSITIVE", "NEGATIVE"]},
    "qualifier": {"type": "string", "enum": ["GREATER", "LESS", "BETWEEN"]},
    "source": {"type": "string", "enum": ["CHAN1", "CHAN2", "CHAN3", "CHAN4"]},
    "threshold_v": {"type": "number"},
    "lower_width_s": {"type": "number", "minimum": _WIDTH_MIN_S, "maximum": _WIDTH_MAX_S},
    "upper_width_s": {"type": "number", "minimum": _WIDTH_MIN_S, "maximum": _WIDTH_MAX_S},
    "selected_event": {"type": "integer", "minimum": 0},
}

TOOLS = [
    ToolSpec(
        name="get_search",
        description="Read MHO98 search settings, event count, and selected event with mode-conditional fields.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False, "required": []},
        handler=get_search,
        read_only=True,
        needs_session=True,
    ),
    ToolSpec(
        name="set_search",
        description="Send documented EDGE or PULSE search fields with static validation; omitted fields are untouched and state is not queried.",
        input_schema={"type": "object", "properties": _SET_SEARCH_PROPERTIES, "additionalProperties": False, "required": []},
        handler=set_search,
        read_only=False,
        needs_session=True,
    ),
    ToolSpec(
        name="read_search_events",
        description="Read a bounded 1-based slice of actual MHO98 search event times, retaining raw values and units.",
        input_schema={
            "type": "object",
            "properties": {"start": {"type": "integer", "minimum": 1}, "limit": {"type": "integer", "minimum": 1, "maximum": _MAX_EVENT_LIMIT}},
            "additionalProperties": False,
            "required": [],
        },
        handler=read_search_events,
        read_only=True,
        needs_session=True,
    ),
    ToolSpec(
        name="get_navigation",
        description="Read MHO98 navigation settings; TIME playback fields are conditional on TIME mode.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False, "required": []},
        handler=get_navigation,
        read_only=True,
        needs_session=True,
    ),
    ToolSpec(
        name="set_navigation",
        description="Send navigation enable/mode/speed/play fields without preflight or automatic acquisition changes.",
        input_schema={
            "type": "object",
            "properties": {"enabled": {"type": "boolean"}, "mode": {"type": "string", "enum": ["TIME", "SEARCH"]}, "speed": {"type": "string", "enum": ["HIGH", "NORMAL", "LOW"]}, "play": {"type": "boolean"}},
            "additionalProperties": False,
            "required": [],
        },
        handler=set_navigation,
        read_only=False,
        needs_session=True,
    ),
    ToolSpec(
        name="navigate",
        description="Perform one explicit MHO98 first/last/next/back action in TIME or SEARCH mode.",
        input_schema={
            "type": "object",
            "properties": {"mode": {"type": "string", "enum": ["TIME", "SEARCH"]}, "action": {"type": "string", "enum": ["FIRST", "LAST", "NEXT", "BACK"]}},
            "additionalProperties": False,
            "required": ["mode", "action"],
        },
        handler=navigate,
        read_only=False,
        needs_session=True,
    ),
]
