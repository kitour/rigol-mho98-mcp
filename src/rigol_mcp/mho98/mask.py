"""MHO98 pass/fail mask configuration, results, and explicit actions.

The mask interface is deliberately split into configuration (``get_mask`` and
``set_mask``), results (``read_mask``), and actions (``mask_action``).  In
particular, selecting ``enabled=True`` never starts the test: starting and
stopping are explicit actions.
"""

from __future__ import annotations

import math
from numbers import Real
from typing import Any

from .api import ToolSpec


_SOURCES = frozenset({f"CHAN{i}" for i in range(1, 5)})
_OPERATES = frozenset({"RUN", "STOP"})
_EVENTS = frozenset({"FAIL", "PASS"})
_ACTIONS = frozenset({"CREATE", "START", "STOP", "RESET"})
_EFFECT_SOURCE_ASSIGNMENT = (
    "Selecting a disabled analog channel as the mask source enables that "
    "channel automatically (MHO98 documented side effect)."
)


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


def _bounded(value: Any, name: str, low: float, high: float) -> float:
    result = _finite(value, name)
    if not low <= result <= high:
        raise ValueError(f"{name} must be in the documented range {low:g}..{high:g}")
    return result


def _integer_response(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"invalid {name} response from MHO98: {value!r}")
    text = str(value).strip()
    try:
        number = float(text)
    except ValueError:
        raise ValueError(f"invalid {name} response from MHO98: {value!r}") from None
    if not math.isfinite(number) or not number.is_integer() or number < 0:
        raise ValueError(f"invalid {name} response from MHO98: {value!r}")
    return int(number)


def _source(value: Any, name: str = "source") -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be CHAN1 through CHAN4")
    token = value.strip().upper().replace(" ", "")
    if token.startswith("CHANNEL"):
        token = "CHAN" + token[7:]
    elif token.startswith("CH") and not token.startswith("CHAN"):
        token = "CHAN" + token[2:]
    if token not in _SOURCES:
        raise ValueError(f"{name} must be CHAN1 through CHAN4")
    return token


def _enum(value: Any, name: str, choices: frozenset[str]) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be one of {', '.join(sorted(choices))}")
    token = value.strip().upper()
    if token not in choices:
        raise ValueError(f"{name} must be one of {', '.join(sorted(choices))}")
    return token


def _scpi_number(value: float) -> str:
    return format(value, ".15g")


def _query_settings(session: Any) -> dict[str, Any]:
    """Query all eight setting/status commands, without starting the test."""

    return {
        "enabled": _bool_response(session.query(":MASK:ENABle?"), "mask enabled"),
        "source": _source(session.query(":MASK:SOURce?"), "mask source response"),
        "operate": _enum(session.query(":MASK:OPERate?"), "mask operate response", _OPERATES),
        "x_div": _finite(session.query(":MASK:X?"), "mask x response"),
        "y_div": _finite(session.query(":MASK:Y?"), "mask y response"),
        "aux_enabled": _bool_response(
            session.query(":MASK:OUTPut:ENABle?"), "mask AUX output"
        ),
        "aux_event": _enum(
            session.query(":MASK:OUTPut:EVENt?"), "mask AUX event response", _EVENTS
        ),
        "aux_time_s": _finite(
            session.query(":MASK:OUTPut:TIME?"), "mask AUX time response"
        ),
    }


def get_mask(session: Any) -> dict[str, Any]:
    """Return the effective pass/fail mask settings and operating status."""

    return _query_settings(session)


def _alias(primary: Any, alternate: Any, primary_name: str, alternate_name: str) -> Any:
    if primary is not None and alternate is not None:
        raise ValueError(f"provide only one of {primary_name} and {alternate_name}")
    return primary if primary is not None else alternate


def set_mask(
    session: Any,
    *,
    enabled: Any = None,
    source: Any = None,
    x_div: Any = None,
    y_div: Any = None,
    aux_enabled: Any = None,
    aux_event: Any = None,
    aux_time_s: Any = None,
    x: Any = None,
    y: Any = None,
    output_enabled: Any = None,
    output_event: Any = None,
    output_time_s: Any = None,
) -> dict[str, Any]:
    """Send only the explicitly requested mask settings."""

    x_div = _alias(x_div, x, "x_div", "x")
    y_div = _alias(y_div, y, "y_div", "y")
    aux_enabled = _alias(aux_enabled, output_enabled, "aux_enabled", "output_enabled")
    aux_event = _alias(aux_event, output_event, "aux_event", "output_event")
    aux_time_s = _alias(aux_time_s, output_time_s, "aux_time_s", "output_time_s")

    requested = {
        "enabled": None if enabled is None else _bool_input(enabled, "enabled"),
        "source": None if source is None else _source(source),
        "x_div": None if x_div is None else _bounded(x_div, "x_div", 0.01, 2.0),
        "y_div": None if y_div is None else _bounded(y_div, "y_div", 0.04, 2.0),
        "aux_enabled": None if aux_enabled is None else _bool_input(aux_enabled, "aux_enabled"),
        "aux_event": None if aux_event is None else _enum(aux_event, "aux_event", _EVENTS),
        "aux_time_s": None if aux_time_s is None else _bounded(aux_time_s, "aux_time_s", 100e-9, 10e-3),
    }

    writes: list[str] = []
    if requested["source"] is not None:
        writes.append(":MASK:SOURce " + requested["source"])
    if requested["x_div"] is not None:
        writes.append(":MASK:X " + _scpi_number(requested["x_div"]))
    if requested["y_div"] is not None:
        writes.append(":MASK:Y " + _scpi_number(requested["y_div"]))
    if requested["aux_enabled"] is not None:
        writes.append(":MASK:OUTPut:ENABle " + ("1" if requested["aux_enabled"] else "0"))
    if requested["aux_event"] is not None:
        writes.append(":MASK:OUTPut:EVENt " + requested["aux_event"])
    if requested["aux_time_s"] is not None:
        writes.append(":MASK:OUTPut:TIME " + _scpi_number(requested["aux_time_s"]))
    if requested["enabled"] is not None:
        writes.append(":MASK:ENABle " + ("1" if requested["enabled"] else "0"))

    for command in writes:
        session.write(command)
    result: dict[str, Any] = {
        "requested": {key: value for key, value in requested.items() if value is not None},
        "sent": bool(writes),
        "verified": False,
        "commands": writes,
    }
    if requested["source"] is not None:
        result["effects"] = [_EFFECT_SOURCE_ASSIGNMENT]
    return result


def read_mask(session: Any) -> dict[str, Any]:
    """Read actual pass/fail counters without an enable preflight."""

    result: dict[str, Any] = {}
    failed = _integer_response(session.query(":MASK:FAILed?"), "failed count")
    passed = _integer_response(session.query(":MASK:PASSed?"), "passed count")
    total = _integer_response(session.query(":MASK:TOTal?"), "total count")
    result.update(
        {
            "failed": failed,
            "passed": passed,
            "total": total,
            "pass_ratio": None if total == 0 else passed / total,
        }
    )
    return result


def mask_action(session: Any, *, action: Any) -> dict[str, Any]:
    """Send one explicit mask action without state queries."""

    normalized = _enum(action, "action", _ACTIONS)
    if normalized == "CREATE":
        command = ":MASK:CREate"
    elif normalized == "START":
        command = ":MASK:OPERate RUN"
    elif normalized == "STOP":
        command = ":MASK:OPERate STOP"
    else:
        # RESET is deliberately only :MASK:RESet; it does not issue *RST or
        # alter any mask configuration.
        command = ":MASK:RESet"

    session.write(command)
    return {"action": normalized.lower(), "sent": True, "verified": False, "commands": [command]}


_SET_PROPERTIES = {
    "enabled": {"type": "boolean"},
    "source": {"type": "string", "enum": sorted(_SOURCES)},
    "x_div": {"type": "number", "minimum": 0.01, "maximum": 2.0},
    "y_div": {"type": "number", "minimum": 0.04, "maximum": 2.0},
    "aux_enabled": {"type": "boolean"},
    "aux_event": {"type": "string", "enum": sorted(_EVENTS)},
    "aux_time_s": {"type": "number", "minimum": 1e-7, "maximum": 1e-2},
    "x": {"type": "number", "minimum": 0.01, "maximum": 2.0},
    "y": {"type": "number", "minimum": 0.04, "maximum": 2.0},
    "output_enabled": {"type": "boolean"},
    "output_event": {"type": "string", "enum": sorted(_EVENTS)},
    "output_time_s": {"type": "number", "minimum": 1e-7, "maximum": 1e-2},
}

TOOLS = [
    ToolSpec(
        name="get_mask",
        description="Read MHO98 pass/fail mask settings and operating status without starting the test.",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=get_mask,
        read_only=True,
        needs_session=True,
    ),
    ToolSpec(
        name="set_mask",
        description="Set explicit MHO98 pass/fail mask settings; omitted fields are preserved and AUX output is never enabled by default.",
        input_schema={"type": "object", "properties": _SET_PROPERTIES, "required": []},
        handler=set_mask,
        read_only=False,
        needs_session=True,
    ),
    ToolSpec(
        name="read_mask",
        description="Read enabled MHO98 pass/fail counts and pass ratio without enabling or starting the test.",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=read_mask,
        read_only=True,
        needs_session=True,
    ),
    ToolSpec(
        name="mask_action",
        description="Explicitly create, start, stop, or reset only MHO98 pass/fail mask state and counters.",
        input_schema={
            "type": "object",
            "properties": {"action": {"type": "string", "enum": sorted(_ACTIONS)}},
            "required": ["action"],
        },
        handler=mask_action,
        read_only=False,
        needs_session=True,
    ),
]
