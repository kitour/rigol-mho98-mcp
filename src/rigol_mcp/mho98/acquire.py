"""Read and configure MHO98 acquisition settings.

The handlers in this module never start or stop acquisition implicitly and never
enable a channel to satisfy a memory-depth request.  Configuration writes contain
only explicitly requested fields; setters do not query or verify resulting state.
"""

from __future__ import annotations

import math
from numbers import Real
from typing import Any

from .api import ToolSpec


_MODES = frozenset({"NORM", "PEAK", "AVER", "HRES"})
_MODE_ALIASES = {
    "NORM": "NORM",
    "NORMAL": "NORM",
    "PEAK": "PEAK",
    "AVER": "AVER",
    "AVERAGE": "AVER",
    "AVERAGES": "AVER",
    "HRES": "HRES",
    "HRESOLUTION": "HRES",
}
_AVERAGE_MIN = 2
_AVERAGE_MAX = 65536
_HRES_BITS = frozenset({14, 16})
_OTHER_BITS = 12

# MHO98 lists these as both engineering suffixes and equivalent integer/scientific
# spellings.  Internally they are compared by point count, while the transmitted
# token remains a documented discrete value.
_MEMORY_POINTS = frozenset(
    {
        1_000,
        10_000,
        100_000,
        1_000_000,
        10_000_000,
        25_000_000,
        50_000_000,
        100_000_000,
        125_000_000,
        200_000_000,
        250_000_000,
        500_000_000,
    }
)
_MEMORY_ALIASES = {
    "1K": ("1K", 1_000),
    "10K": ("10K", 10_000),
    "100K": ("100K", 100_000),
    "1M": ("1M", 1_000_000),
    "10M": ("10M", 10_000_000),
    "25M": ("25M", 25_000_000),
    "50M": ("50M", 50_000_000),
    "100M": ("100M", 100_000_000),
    "125M": ("125M", 125_000_000),
    "200M": ("200M", 200_000_000),
    "250M": ("250M", 250_000_000),
    "500M": ("500M", 500_000_000),
}


def _finite_number(value: Any, name: str) -> float:
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


def _integer(value: Any, name: str) -> int:
    result = _finite_number(value, name)
    if not result.is_integer():
        raise ValueError(f"{name} must be an integer")
    return int(result)


def _normalize_mode(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("mode must be NORM, PEAK, AVER, or HRES")
    mode = _MODE_ALIASES.get(value.strip().upper())
    if mode is None:
        raise ValueError("mode must be NORM, PEAK, AVER, or HRES")
    return mode


def _mode_response(value: Any) -> str:
    try:
        return _normalize_mode(str(value))
    except ValueError:
        raise ValueError(f"invalid acquisition mode response from MHO98: {value!r}") from None


def _validate_averages(value: Any) -> int:
    count = _integer(value, "averages")
    if not _AVERAGE_MIN <= count <= _AVERAGE_MAX or count & (count - 1):
        raise ValueError("averages must be a power of two from 2 through 65536")
    return count


def _parse_memory(value: Any, *, for_input: bool) -> tuple[str | None, int | None]:
    """Return (SCPI token, point count), with AUTO represented by None points."""
    if isinstance(value, bool):
        raise ValueError("memory_depth must be AUTO or a documented point count")
    if isinstance(value, str):
        token = value.strip().upper().replace(" ", "")
        if token == "AUTO":
            return "AUTO", None
        if token in _MEMORY_ALIASES:
            return _MEMORY_ALIASES[token]
        try:
            numeric = float(token)
        except ValueError:
            raise ValueError("memory_depth must be AUTO or a documented point count") from None
    elif isinstance(value, Real):
        numeric = float(value)
    else:
        raise ValueError("memory_depth must be AUTO or a documented point count")
    if not math.isfinite(numeric) or not numeric.is_integer():
        raise ValueError("memory_depth must be a documented integer point count")
    points = int(numeric)
    if points not in _MEMORY_POINTS:
        raise ValueError("memory_depth is not a documented MHO98 point count")
    # Decimal integer spellings are accepted by the guide.  Preserve an input
    # spelling only when it is already a documented engineering suffix.
    return str(points), points


def _memory_response(value: Any) -> int | str:
    token = str(value).strip().upper().replace(" ", "")
    if token == "AUTO":
        return "AUTO"
    try:
        numeric = float(token)
    except ValueError:
        raise ValueError(f"invalid memory depth response from MHO98: {value!r}") from None
    if not math.isfinite(numeric) or not numeric.is_integer() or int(numeric) <= 0:
        raise ValueError(f"invalid memory depth response from MHO98: {value!r}")
    return int(numeric)


def _bits_response(value: Any) -> int:
    bits = _integer(value, "bits")
    if bits not in {12, 14, 16}:
        raise ValueError(f"invalid acquisition resolution response from MHO98: {value!r}")
    return bits


def _sample_rate_response(value: Any) -> float:
    rate = _finite_number(value, "sample_rate")
    if rate < 0:
        raise ValueError(f"invalid sample rate response from MHO98: {value!r}")
    return rate


def _query_acquisition(session: Any) -> dict[str, Any]:
    """Read all acquisition fields in one stable, documented snapshot."""
    return {
        "mode": _mode_response(session.query(":ACQuire:TYPE?")),
        "averages": _validate_averages(session.query(":ACQuire:AVERages?")),
        "memory_depth": _memory_response(session.query(":ACQuire:MDEPth?")),
        "bits": _bits_response(session.query(":ACQuire:BITS?")),
        "sample_rate": _sample_rate_response(session.query(":ACQuire:SRATe?")),
    }


def get_acquisition(session: Any) -> dict[str, Any]:
    """Return the current MHO98 acquisition settings and sample rate."""
    return _query_acquisition(session)


def set_acquisition(
    session: Any,
    *,
    mode: Any = None,
    averages: Any = None,
    memory_depth: Any = None,
    bits: Any = None,
) -> dict[str, Any]:
    """Send only the explicitly requested acquisition fields.

    ``mode`` accepts NORM, PEAK, AVER, and HRES (plus their documented long
    forms).  ``memory_depth`` accepts AUTO or any documented MHO98 point count.
    """
    requested_mode = None if mode is None else _normalize_mode(mode)
    requested_averages = None if averages is None else _validate_averages(averages)
    requested_bits = None if bits is None else _integer(bits, "bits")
    if requested_bits is not None and requested_bits not in {12, *_HRES_BITS}:
        raise ValueError("bits must be 12, 14, or 16")
    if requested_bits in _HRES_BITS and requested_mode is not None and requested_mode != "HRES":
        raise ValueError("bits 14 or 16 require explicit HRES mode")
    if requested_bits == _OTHER_BITS and requested_mode == "HRES":
        raise ValueError("bits 12 is contradictory with explicit HRES mode")
    requested_memory = None if memory_depth is None else _parse_memory(memory_depth, for_input=True)

    writes: list[str] = []
    # Apply mode first so dependent averages/resolution settings have the intended
    # interpretation.  Memory is last because it can change the sample rate.
    if requested_mode is not None:
        writes.append(f":ACQuire:TYPE {requested_mode}")
    if requested_averages is not None:
        writes.append(f":ACQuire:AVERages {requested_averages}")
    if requested_bits is not None:
        writes.append(f":ACQuire:BITS {requested_bits}")
    if requested_memory is not None:
        memory_token, _requested_points = requested_memory
        writes.append(f":ACQuire:MDEPth {memory_token}")

    for command in writes:
        session.write(command)
    requested = {
        key: value for key, value in {
            "mode": requested_mode,
            "averages": requested_averages,
            "memory_depth": requested_memory[0] if requested_memory is not None else None,
            "bits": requested_bits,
        }.items() if value is not None
    }
    return {"sent": bool(writes), "verified": False, "commands": writes, "requested": requested, **requested}


_CONTROL_COMMANDS = {
    "RUN": ":RUN",
    "STOP": ":STOP",
    "SINGLE": ":SINGle",
    "FORCE": ":TFORce",
    "TFORCE": ":TFORce",
}


def acquisition_control(session: Any, action: str) -> dict[str, Any]:
    """Perform exactly one explicit MHO98 acquisition control action."""
    if not isinstance(action, str) or action.strip().upper() not in _CONTROL_COMMANDS:
        raise ValueError("action must be RUN, STOP, SINGLE, or FORCE")
    normalized = action.strip().upper()
    if normalized == "TFORCE":
        normalized = "FORCE"
    command = _CONTROL_COMMANDS[normalized]
    session.write(command)
    return {"sent": True, "verified": False, "commands": [command], "action": normalized}


TOOLS = [
    ToolSpec(
        name="get_acquisition",
        description="Read MHO98 acquisition mode, averages, memory depth, resolution bits, and sample rate.",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=get_acquisition,
        read_only=True,
        needs_session=True,
    ),
    ToolSpec(
        name="set_acquisition",
        description="Send selected MHO98 acquisition commands without querying or changing channel enable state; resulting values are not verified.",
        input_schema={
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["NORM", "PEAK", "AVER", "HRES"]},
                "averages": {"type": "integer", "minimum": 2, "maximum": 65536},
                "memory_depth": {"type": ["string", "integer"]},
                "bits": {"type": "integer", "enum": [12, 14, 16]},
            },
            "required": [],
        },
        handler=set_acquisition,
        read_only=False,
        needs_session=True,
    ),
    ToolSpec(
        name="acquisition_control",
        description="Perform one explicit MHO98 RUN, STOP, SINGLE, or FORCE trigger action.",
        input_schema={
            "type": "object",
            "properties": {"action": {"type": "string", "enum": ["RUN", "STOP", "SINGLE", "FORCE"]}},
            "required": ["action"],
        },
        handler=acquisition_control,
        read_only=False,
        needs_session=True,
    ),
]
