"""Small, independent controls for the MHO98 digital voltmeter."""

from __future__ import annotations

import math
import re
from typing import Any

from .api import ToolSpec


_SOURCES = frozenset({"CHAN1", "CHAN2", "CHAN3", "CHAN4"})
_MODES = {"ACRMS": "ACRMs", "DC": "DC", "DCRMS": "DCRMs"}
_MODE_RESPONSES = {
    "ACRM": "ACRMs",
    "ACRMS": "ACRMs",
    "DC": "DC",
    "DCRM": "DCRMs",
    "DCRMS": "DCRMs",
}
_INVALID_SENTINEL = 9.0e37
_NUMBER_PREFIX = re.compile(
    r"^[ \t]*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?)(?:[ \t]*(.*?))?[ \t]*$"
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


def _source(value: Any, name: str = "source") -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be CHAN1, CHAN2, CHAN3, or CHAN4")
    token = value.strip().upper()
    if token not in _SOURCES:
        raise ValueError(f"{name} must be CHAN1, CHAN2, CHAN3, or CHAN4")
    return token


def _mode(value: Any, name: str = "mode") -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be ACRMs, DC, or DCRMs")
    token = _MODES.get(value.strip().upper())
    if token is None:
        raise ValueError(f"{name} must be ACRMs, DC, or DCRMs")
    return token


def _source_response(value: Any) -> str:
    token = str(value).strip().upper()
    if token.startswith("CHANNEL"):
        token = "CHAN" + token[7:]
    if token not in _SOURCES:
        raise ValueError(f"invalid DVM source response from MHO98: {value!r}")
    return token


def _mode_response(value: Any) -> str:
    token = _MODE_RESPONSES.get(str(value).strip().upper())
    if token is None:
        raise ValueError(f"invalid DVM mode response from MHO98: {value!r}")
    return token


def _query_dvm(session: Any) -> dict[str, Any]:
    return {
        "enabled": _bool_response(session.query(":DVM:ENABle?"), "DVM enabled"),
        "source": _source_response(session.query(":DVM:SOURce?")),
        "mode": _mode_response(session.query(":DVM:MODE?")),
    }


def get_dvm(session: Any) -> dict[str, Any]:
    """Return DVM configuration without reading a measured value."""

    return _query_dvm(session)


def set_dvm(
    session: Any,
    *,
    enabled: Any = None,
    source: Any = None,
    mode: Any = None,
) -> dict[str, Any]:
    """Send only the explicitly requested DVM fields.

    DVM enablement is explicit.  This handler never changes analog channel or
    oscilloscope acquisition state.
    """

    # Normalize all caller input before writing the instrument.
    requested_enabled = None if enabled is None else _bool_input(enabled, "enabled")
    requested_source = None if source is None else _source(source)
    requested_mode = None if mode is None else _mode(mode)

    writes: list[str] = []
    if requested_enabled is not None:
        writes.append(":DVM:ENABle " + ("1" if requested_enabled else "0"))
    if requested_source is not None:
        writes.append(":DVM:SOURce " + requested_source)
    if requested_mode is not None:
        writes.append(":DVM:MODE " + requested_mode)
    for command in writes:
        session.write(command)
    return {
        "requested": {key: value for key, value in {
            "enabled": requested_enabled, "source": requested_source, "mode": requested_mode,
        }.items() if value is not None},
        "sent": bool(writes),
        "verified": False,
        "commands": writes,
    }


def _read_value(raw: str) -> dict[str, Any]:
    """Parse a DVM reply without discarding its raw spelling or unit suffix."""

    match = _NUMBER_PREFIX.match(raw)
    unit = "V"
    if match is None:
        return {
            "valid": False,
            "value": None,
            "unit": unit,
            "raw": raw,
            "reason": "not a numeric DVM reading",
        }

    numeric = float(match.group(1))
    suffix = (match.group(2) or "").strip()
    if suffix:
        unit = suffix
    if not math.isfinite(numeric):
        return {
            "valid": False,
            "value": None,
            "unit": unit,
            "raw": raw,
            "reason": "not a finite DVM reading",
        }
    if abs(numeric) >= _INVALID_SENTINEL:
        return {
            "valid": False,
            "value": None,
            "unit": unit,
            "raw": raw,
            "reason": "MHO98 invalid/overflow sentinel",
        }
    return {"valid": True, "value": numeric, "unit": unit, "raw": raw}


def read_dvm(session: Any) -> dict[str, Any]:
    """Read the DVM value and the source/mode needed to interpret it."""

    source = _source_response(session.query(":DVM:SOURce?"))
    mode = _mode_response(session.query(":DVM:MODE?"))
    result = _read_value(str(session.query(":DVM:CURRent?")).strip())
    result["source"] = source
    result["mode"] = mode
    return result


_DVM_SCHEMA = {
    "type": "object",
    "properties": {
        "enabled": {"type": "boolean"},
        "source": {"type": "string", "enum": sorted(_SOURCES)},
        "mode": {"type": "string", "enum": ["ACRMs", "DC", "DCRMs"]},
    },
    "required": [],
}

TOOLS = [
    ToolSpec(
        name="get_dvm",
        description="Read MHO98 DVM enable, analog source, and mode settings without reading a value.",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=get_dvm,
        read_only=True,
        needs_session=True,
    ),
    ToolSpec(
        name="set_dvm",
        description="Send explicit MHO98 DVM fields only; omitted fields are untouched and resulting state is not queried.",
        input_schema=_DVM_SCHEMA,
        handler=set_dvm,
        read_only=False,
        needs_session=True,
    ),
    ToolSpec(
        name="read_dvm",
        description="Read the MHO98 DVM voltage only when explicitly enabled; preserve raw and invalid instrument readings.",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=read_dvm,
        read_only=True,
        needs_session=True,
    ),
]
