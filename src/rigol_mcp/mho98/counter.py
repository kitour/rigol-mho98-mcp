"""Dedicated MHO98 frequency, period, and totalize counter controls.

This module intentionally uses the instrument's ``:COUNter`` subtree.  It is
separate from the legacy ``:MEASure:COUNter`` settings in
``measurement_settings.py``.
"""

from __future__ import annotations

import math
from typing import Any

from .api import ToolSpec


_SOURCE_ENUM = [f"CHAN{i}" for i in range(1, 5)] + [f"D{i}" for i in range(16)]
_MODE_WRITE = {"FREQ": "FREQuency", "PER": "PERiod", "TOT": "TOTalize"}
_MODE_ALIASES = {
    "FREQ": "FREQ",
    "FREQUENCY": "FREQ",
    "FREQU": "FREQ",
    "PER": "PER",
    "PERIOD": "PER",
    "TOT": "TOT",
    "TOTALIZE": "TOT",
    "TOTAL": "TOT",
}
_INVALID_SENTINEL = 9.0e37


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


def _source(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("source must be CHAN1-CHAN4 or D0-D15")
    token = value.strip().upper().replace(" ", "")
    if token.startswith("CHANNEL"):
        token = "CHAN" + token[7:]
    elif token.startswith("CH") and not token.startswith("CHAN"):
        token = "CHAN" + token[2:]
    if token not in _SOURCE_ENUM:
        raise ValueError("source must be CHAN1-CHAN4 or D0-D15")
    return token


def _source_response(value: Any) -> str:
    try:
        return _source(str(value))
    except ValueError:
        raise ValueError(f"invalid counter source response from MHO98: {value!r}") from None


def _mode(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("mode must be FREQ, PER, or TOT")
    normalized = _MODE_ALIASES.get(value.strip().upper())
    if normalized is None:
        raise ValueError("mode must be FREQ, PER, or TOT")
    return normalized


def _mode_response(value: Any) -> str:
    try:
        return _mode(str(value))
    except ValueError:
        raise ValueError(f"invalid counter mode response from MHO98: {value!r}") from None


def _digits(value: Any, name: str = "digits") -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer from 3 through 6")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be an integer from 3 through 6") from None
    if not math.isfinite(number) or not number.is_integer() or not 3 <= number <= 6:
        raise ValueError(f"{name} must be an integer from 3 through 6")
    return int(number)


def _digits_response(value: Any) -> int:
    try:
        return _digits(value)
    except ValueError:
        raise ValueError(f"invalid counter digits response from MHO98: {value!r}") from None


def _query_settings(session: Any) -> dict[str, Any]:
    """Query the applicable counter settings without starting measurement."""

    enabled = _bool_response(session.query(":COUNter:ENABle?"), "counter enabled")
    source = _source_response(session.query(":COUNter:SOURce?"))
    mode = _mode_response(session.query(":COUNter:MODE?"))
    result: dict[str, Any] = {
        "enabled": enabled,
        "source": source,
        "mode": mode,
    }
    # The guide makes both fields unavailable in totalize.  Do not even query
    # them in that mode: some instruments reject those queries.
    if mode == "TOT":
        result["unavailable"] = ["digits", "statistics"]
    else:
        result["digits"] = _digits_response(session.query(":COUNter:NDIGits?"))
        result["statistics"] = _bool_response(
            session.query(":COUNter:TOTalize:ENABle?"), "counter statistics"
        )
    return result


def get_counter(session: Any) -> dict[str, Any]:
    """Return applicable dedicated counter settings."""

    return _query_settings(session)


def set_counter(
    session: Any,
    *,
    enabled: Any = None,
    source: Any = None,
    mode: Any = None,
    digits: Any = None,
    statistics: Any = None,
) -> dict[str, Any]:
    """Send only the explicitly requested counter fields."""

    requested_enabled = None if enabled is None else _bool_input(enabled, "enabled")
    requested_source = None if source is None else _source(source)
    requested_mode = None if mode is None else _mode(mode)
    requested_digits = None if digits is None else _digits(digits)
    requested_statistics = None if statistics is None else _bool_input(statistics, "statistics")

    if requested_mode == "TOT" and (requested_digits is not None or requested_statistics is not None):
        raise ValueError("digits and statistics are unavailable in TOT mode")

    writes: list[str] = []
    if requested_enabled is not None:
        writes.append(":COUNter:ENABle " + ("1" if requested_enabled else "0"))
    if requested_source is not None:
        writes.append(f":COUNter:SOURce {requested_source}")
    if requested_mode is not None:
        writes.append(f":COUNter:MODE {_MODE_WRITE[requested_mode]}")
    if requested_digits is not None:
        writes.append(f":COUNter:NDIGits {requested_digits}")
    if requested_statistics is not None:
        writes.append(
            ":COUNter:TOTalize:ENABle " + ("1" if requested_statistics else "0")
        )

    for command in writes:
        session.write(command)
    return {
        "requested": {key: value for key, value in {
            "enabled": requested_enabled, "source": requested_source, "mode": requested_mode,
            "digits": requested_digits, "statistics": requested_statistics,
        }.items() if value is not None},
        "sent": bool(writes),
        "verified": False,
        "commands": writes,
    }


def _value_result(raw: str, *, enabled: bool | None, mode: str) -> dict[str, Any]:
    unit = {"FREQ": "Hz", "PER": "s", "TOT": "count"}[mode]
    result: dict[str, Any] = {
        "mode": mode,
        "valid": False,
        "value": None,
        "unit": unit,
        "raw": raw,
    }
    if enabled is not None:
        result["enabled"] = enabled
    try:
        value = float(raw)
    except (TypeError, ValueError):
        result["reason"] = "not a numeric counter reading"
        return result
    if not math.isfinite(value):
        result["reason"] = "not a finite counter reading"
        return result
    if abs(value) >= _INVALID_SENTINEL:
        result["reason"] = "MHO98 invalid/overflow counter sentinel"
        return result
    result.update(valid=True, value=value)
    return result


def read_counter(session: Any) -> dict[str, Any]:
    """Read the counter value with mode/source context and no enable preflight."""

    mode = _mode_response(session.query(":COUNter:MODE?"))
    source = _source_response(session.query(":COUNter:SOURce?"))
    result = _value_result(str(session.query(":COUNter:CURRent?")).strip(), enabled=None, mode=mode)
    result["source"] = source
    return result


def counter_action(session: Any, *, action: Any) -> dict[str, Any]:
    """Send the explicit totalizer-clear command."""

    if not isinstance(action, str) or action.strip().upper() not in {"CLEAR", "TOTALIZE_CLEAR"}:
        raise ValueError("action must be CLEAR")
    command = ":COUNter:TOTalize:CLEar"
    session.write(command)
    return {"action": "clear", "sent": True, "verified": False, "commands": [command]}


_SET_PROPERTIES = {
    "enabled": {"type": "boolean"},
    "source": {"type": "string", "enum": _SOURCE_ENUM},
    "mode": {"type": "string", "enum": ["FREQ", "PER", "TOT"]},
    "digits": {"type": "integer", "minimum": 3, "maximum": 6},
    "statistics": {"type": "boolean"},
}

TOOLS = [
    ToolSpec(
        name="get_counter",
        description="Read applicable dedicated MHO98 frequency/period/totalize counter settings.",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=get_counter,
        read_only=True,
        needs_session=True,
    ),
    ToolSpec(
        name="set_counter",
        description="Send explicit dedicated MHO98 counter fields only; omitted fields are untouched and resulting state is not queried.",
        input_schema={"type": "object", "properties": _SET_PROPERTIES, "required": []},
        handler=set_counter,
        read_only=False,
        needs_session=True,
    ),
    ToolSpec(
        name="read_counter",
        description="Read the enabled dedicated MHO98 counter value with exact mode units and raw validity handling.",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=read_counter,
        read_only=True,
        needs_session=True,
    ),
    ToolSpec(
        name="counter_action",
        description="Send the explicit MHO98 totalizer-clear command; the instrument applies its own mode rules.",
        input_schema={
            "type": "object",
            "properties": {"action": {"type": "string", "enum": ["clear"]}},
            "required": ["action"],
        },
        handler=counter_action,
        read_only=False,
        needs_session=True,
    ),
]
