"""MHO98 histogram configuration, result, and export tools.

The programming guide documents histogram settings and one statistics result
query, but it does not document a histogram-bin query.  This module therefore
returns the instrument's structured statistics result only and never invents
bin data from the displayed range.
"""

from __future__ import annotations

import math
import re
from numbers import Real
from typing import Any

from .api import ToolSpec


_TYPE_WRITE = {"HOR": "HORizontal", "VERT": "VERTical"}
_TYPE_ALIASES = {
    "HOR": "HOR",
    "HORIZONTAL": "HOR",
    "VERT": "VERT",
    "VERTICAL": "VERT",
}
_SOURCE_RE = re.compile(r"^CH(?:AN(?:NEL)?)?([1-4])$", re.IGNORECASE)
_NUMBER_RE = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_STAT_VALUE_RE = re.compile(rf"^({_NUMBER_RE})\s*([A-Za-zµμΩ]*)$")
_SI_MULTIPLIERS = {
    "y": 1.0e-24,
    "z": 1.0e-21,
    "a": 1.0e-18,
    "f": 1.0e-15,
    "p": 1.0e-12,
    "n": 1.0e-9,
    "u": 1.0e-6,
    "µ": 1.0e-6,
    "μ": 1.0e-6,
    "m": 1.0e-3,
    "k": 1.0e3,
    "K": 1.0e3,
    "M": 1.0e6,
    "G": 1.0e9,
    "T": 1.0e12,
    "P": 1.0e15,
    "E": 1.0e18,
    "Z": 1.0e21,
    "Y": 1.0e24,
}
_STAT_BASE_UNITS = ("counts", "hits", "count", "Hz", "s", "V", "A", "W")
_STAT_KEYS = {
    "sum": "sum",
    "peaks": "peaks",
    "max": "max",
    "min": "min",
    "pkpk": "pk_pk",
    "mean": "mean",
    "median": "median",
    "mode": "mode",
    "binwidth": "bin_width",
    "sigma": "sigma",
    "siqma": "sigma",
    "meansigma": "mean_plus_sigma",
    "meanplussigma": "mean_plus_sigma",
    "meanplus2sigma": "mean_plus_2sigma",
    "meanplus3sigma": "mean_plus_3sigma",
}


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


def _type(value: Any, name: str = "type") -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be HOR or VERT")
    normalized = _TYPE_ALIASES.get(value.strip().upper())
    if normalized is None:
        raise ValueError(f"{name} must be HOR or VERT")
    return normalized


def _type_response(value: Any) -> str:
    try:
        return _type(value, "histogram type response")
    except ValueError:
        raise ValueError(f"invalid histogram type response from MHO98: {value!r}") from None


def _source(value: Any, name: str = "source") -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be CHAN1, CHAN2, CHAN3, or CHAN4")
    match = _SOURCE_RE.fullmatch(value.strip().replace(" ", ""))
    if match is None:
        raise ValueError(f"{name} must be CHAN1, CHAN2, CHAN3, or CHAN4")
    return f"CHAN{match.group(1)}"


def _source_response(value: Any) -> str:
    try:
        return _source(value, "histogram source response")
    except ValueError:
        raise ValueError(f"invalid histogram source response from MHO98: {value!r}") from None


def _scpi_number(value: float) -> str:
    return format(value, ".15g")


def _query_pair(session: Any, histogram_type: str) -> dict[str, float]:
    if histogram_type == "HOR":
        return {
            "left": _finite(session.query(":HISTogram:RANGe:LEFT?"), "histogram left"),
            "right": _finite(session.query(":HISTogram:RANGe:RIGHt?"), "histogram right"),
        }
    return {
        "top": _finite(session.query(":HISTogram:RANGe:TOP?"), "histogram top"),
        "bottom": _finite(session.query(":HISTogram:RANGe:BOTTom?"), "histogram bottom"),
    }


def _query_base(session: Any) -> dict[str, Any]:
    return {
        "enabled": _bool_response(session.query(":HISTogram:ENABle?"), "histogram enabled"),
        "type": _type_response(session.query(":HISTogram:TYPE?")),
        "source": _source_response(session.query(":HISTogram:SOURce?")),
        "height": _integer(session.query(":HISTogram:HEIGht?"), "histogram height", 1, 4),
    }


def _query_config(session: Any, *, known: dict[str, Any] | None = None, histogram_type: str | None = None) -> dict[str, Any]:
    result = dict(known or _query_base(session))
    selected_type = histogram_type or result["type"]
    result["range"] = _query_pair(session, selected_type)
    return result


def get_histogram(session: Any) -> dict[str, Any]:
    """Return the active histogram configuration and only its applicable range."""

    return _query_config(session)


def _validate_pair(histogram_type: str, pair: dict[str, float], low: float, high: float) -> None:
    if histogram_type == "HOR":
        first, second = pair["left"], pair["right"]
        names = ("left", "right")
    else:
        first, second = pair["bottom"], pair["top"]
        names = ("bottom", "top")
    if first >= second:
        raise ValueError(f"histogram {names[0]} must be smaller than {names[1]}")
    if not low <= first <= high or not low <= second <= high:
        raise ValueError(
            f"histogram {names[0]}/{names[1]} must be within the dynamic range {low:g}..{high:g}"
        )


def set_histogram(
    session: Any,
    *,
    enabled: Any = None,
    type: Any = None,
    source: Any = None,
    height: Any = None,
    left: Any = None,
    right: Any = None,
    top: Any = None,
    bottom: Any = None,
) -> dict[str, Any]:
    """Send only the explicitly requested histogram fields."""

    requested_enabled = None if enabled is None else _bool_input(enabled, "enabled")
    requested_type = None if type is None else _type(type)
    requested_source = None if source is None else _source(source)
    requested_height = None if height is None else _integer(height, "height", 1, 4)
    requested_left = None if left is None else _finite(left, "left")
    requested_right = None if right is None else _finite(right, "right")
    requested_top = None if top is None else _finite(top, "top")
    requested_bottom = None if bottom is None else _finite(bottom, "bottom")

    horizontal_submitted = requested_left is not None or requested_right is not None
    vertical_submitted = requested_top is not None or requested_bottom is not None
    if horizontal_submitted and vertical_submitted:
        raise ValueError("submit only one histogram range pair")

    if horizontal_submitted and requested_type == "VERT":
        raise ValueError("left/right are applicable only to HOR histogram type")
    if vertical_submitted and requested_type == "HOR":
        raise ValueError("top/bottom are applicable only to VERT histogram type")

    if horizontal_submitted and requested_left is not None and requested_right is not None:
        pair_type = "HOR" if horizontal_submitted else "VERT"
        _validate_pair(
            pair_type,
            {"left": requested_left, "right": requested_right},
            -math.inf,
            math.inf,
        )
    if vertical_submitted and requested_top is not None and requested_bottom is not None:
        _validate_pair(
            "VERT",
            {"top": requested_top, "bottom": requested_bottom},
            -math.inf,
            math.inf,
        )

    writes: list[str] = []
    if requested_type is not None:
        writes.append(f":HISTogram:TYPE {_TYPE_WRITE[requested_type]}")
    if requested_source is not None:
        writes.append(f":HISTogram:SOURce {requested_source}")
    if requested_height is not None:
        writes.append(f":HISTogram:HEIGht {requested_height}")
    if horizontal_submitted:
        if requested_left is not None:
            writes.append(":HISTogram:RANGe:LEFT " + _scpi_number(requested_left))
        if requested_right is not None:
            writes.append(":HISTogram:RANGe:RIGHt " + _scpi_number(requested_right))
    elif vertical_submitted:
        if requested_top is not None:
            writes.append(":HISTogram:RANGe:TOP " + _scpi_number(requested_top))
        if requested_bottom is not None:
            writes.append(":HISTogram:RANGe:BOTTom " + _scpi_number(requested_bottom))
    if requested_enabled is not None:
        writes.append(":HISTogram:ENABle " + ("1" if requested_enabled else "0"))

    for command in writes:
        session.write(command)
    return {
        "requested": {key: value for key, value in {
            "enabled": requested_enabled, "type": requested_type, "source": requested_source,
            "height": requested_height, "left": requested_left, "right": requested_right,
            "top": requested_top, "bottom": requested_bottom,
        }.items() if value is not None},
        "sent": bool(writes),
        "verified": False,
        "commands": writes,
    }


def _parse_stat_value(raw: str) -> dict[str, Any]:
    match = _STAT_VALUE_RE.fullmatch(raw.strip())
    if match is None:
        raise ValueError(f"invalid histogram statistic value: {raw!r}")
    numeric = float(match.group(1))
    if not math.isfinite(numeric):
        raise ValueError(f"invalid histogram statistic value: {raw!r}")
    reported_unit = match.group(2)
    unit = reported_unit or None
    value = numeric

    if reported_unit:
        for base in _STAT_BASE_UNITS:
            if reported_unit.endswith(base):
                prefix = reported_unit[: -len(base)]
                multiplier = 1.0 if not prefix else _SI_MULTIPLIERS.get(prefix)
                if multiplier is not None:
                    value = numeric * multiplier
                    unit = "hits" if base in {"hit", "hits", "count", "counts"} else base
                    break
    return {
        "value": value,
        "unit": unit,
        "raw": raw.strip(),
    }


def _stat_key(raw_key: str) -> str:
    normalized = re.sub(r"[^a-z0-9]", "", raw_key.lower())
    return _STAT_KEYS.get(normalized, normalized or "unknown")


def _parse_statistics(raw: Any) -> dict[str, dict[str, Any]]:
    text = str(raw).strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    # The guide's example wraps long field names across lines; whitespace is
    # presentation-only in this response format.
    text = re.sub(r"\s+", "", text)
    if not text:
        raise ValueError("MHO98 returned an empty histogram statistics result")
    result: dict[str, dict[str, Any]] = {}
    for field in text.split(","):
        if ":" not in field:
            raise ValueError(f"invalid histogram statistics field: {field!r}")
        raw_key, raw_value = field.split(":", 1)
        key = _stat_key(raw_key)
        if key in result:
            raise ValueError(f"duplicate histogram statistic: {raw_key!r}")
        result[key] = _parse_stat_value(raw_value)
    return result


def read_histogram(session: Any) -> dict[str, Any]:
    """Read and parse the actual histogram statistics response."""

    raw = str(session.query(":HISTogram:STATistics:RESult?")).strip()
    statistics = _parse_statistics(raw)
    context = {
        "type": _type_response(session.query(":HISTogram:TYPE?")),
        "source": _source_response(session.query(":HISTogram:SOURce?")),
    }
    context["range"] = _query_pair(session, context["type"])
    return {"valid": True, "statistics": statistics, "raw": raw, "context": context}


def _instrument_csv_path(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("path must be an instrument path under C:/ or D:/")
    if value != value.strip() or any(ord(char) < 32 or ord(char) > 127 for char in value):
        raise ValueError("path must be printable ASCII without surrounding whitespace")
    if ";" in value or '"' in value:
        raise ValueError("path must not contain SCPI delimiters or quotes")
    match = re.fullmatch(r"([CD]):/(.+)", value, re.IGNORECASE)
    if match is None:
        raise ValueError("path must use the instrument's C:/ or D:/ storage location")
    relative = match.group(2)
    components = relative.split("/")
    filename = components[-1]
    if not filename or any(part in {".", ".."} for part in components):
        raise ValueError("path must include a filename and must not contain . or .. components")
    if len(filename) > 26:
        raise ValueError("histogram CSV filename must not exceed 26 characters")
    if not filename.lower().endswith(".csv"):
        raise ValueError("histogram CSV path must have a .csv suffix")
    return value


def histogram_action(session: Any, *, action: Any, path: Any = None) -> dict[str, Any]:
    """Perform documented histogram save; reject the guide's ambiguous reset syntax."""

    if not isinstance(action, str):
        raise ValueError("action must be reset or save_csv")
    selected = action.strip().lower()
    if selected == "reset":
        raise ValueError(
            "histogram reset is unsupported: the guide documents ':HISTogram:RESet?' "
            "but the syntax is ambiguous between an action and a query; no command was sent"
        )
    if selected != "save_csv":
        raise ValueError("action must be reset or save_csv")
    instrument_path = _instrument_csv_path(path)
    session.write(f":HISTogram:SAVE:CSV {instrument_path}")
    return {"action": "save_csv", "path": instrument_path, "sent": True, "verified": False, "commands": [f":HISTogram:SAVE:CSV {instrument_path}"]}


_RANGE_PROPERTIES = {
    "left": {"type": "number"},
    "right": {"type": "number"},
    "top": {"type": "number"},
    "bottom": {"type": "number"},
}
_SET_PROPERTIES = {
    "enabled": {"type": "boolean"},
    "type": {"type": "string", "enum": ["HOR", "VERT"]},
    "source": {"type": "string", "enum": ["CHAN1", "CHAN2", "CHAN3", "CHAN4"]},
    "height": {"type": "integer", "minimum": 1, "maximum": 4},
    **_RANGE_PROPERTIES,
}

TOOLS = [
    ToolSpec(
        name="get_histogram",
        description="Read MHO98 histogram settings and only the range pair applicable to its type.",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=get_histogram,
        read_only=True,
        needs_session=True,
    ),
    ToolSpec(
        name="set_histogram",
        description="Send documented MHO98 histogram fields with static validation; omitted fields are untouched and resulting state is not queried.",
        input_schema={"type": "object", "properties": _SET_PROPERTIES, "additionalProperties": False, "required": []},
        handler=set_histogram,
        read_only=False,
        needs_session=True,
    ),
    ToolSpec(
        name="read_histogram",
        description="Read the documented MHO98 histogram statistics result with parsed values, units, and raw text; no bins are invented.",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=read_histogram,
        read_only=True,
        needs_session=True,
    ),
    ToolSpec(
        name="histogram_action",
        description="Save MHO98 histogram CSV data to instrument C:/ or D:/ storage; reset remains unsupported because its documented syntax is ambiguous.",
        input_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["reset", "save_csv"]},
                "path": {"type": ["string", "null"]},
            },
            "required": ["action"],
        },
        handler=histogram_action,
        read_only=False,
        needs_session=True,
    ),
]
