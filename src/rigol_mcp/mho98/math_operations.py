"""MHO98 non-FFT MATH operation controls.

The FFT subtree is intentionally owned by :mod:`rigol_mcp.mho98.fft`.  This
module selects FFT when requested, but does not read or configure FFT fields.
"""

from __future__ import annotations

import math
import re
from typing import Any

from .api import ToolSpec


_ARITHMETIC = frozenset({"ADD", "SUBT", "MULT", "DIV"})
_LOGIC = frozenset({"AND", "OR", "XOR", "NOT"})
_FUNCTION = frozenset({"INTG", "DIFF", "SQRT", "LG", "LN", "EXP", "ABS", "AXB"})
_FILTER = frozenset({"LPAS", "HPAS", "BPAS", "BST"})
_FFT = "FFT"
_OPERATORS = _ARITHMETIC | _LOGIC | _FUNCTION | _FILTER | {_FFT}
_OPERATOR_ALIASES = {
    "SUBTRACT": "SUBT", "MULTIPLY": "MULT", "DIVISION": "DIV",
    "LPASS": "LPAS", "HPASS": "HPAS", "BPASS": "BPAS", "BSTOP": "BST",
}
_GENERAL_SOURCE = re.compile(r"^(?:CH(?:AN)?([1-4])|REF(10|[1-9])|MATH([1-4]))$", re.I)
_LOGIC_SOURCE = re.compile(r"^(?:CH(?:AN)?([1-4])|D(\d|1[0-5]))$", re.I)
_MATH_PROPERTY = {
    "oneOf": [
        {"type": "integer", "enum": [1, 2, 3, 4]},
        {"type": "string", "enum": ["MATH1", "MATH2", "MATH3", "MATH4"]},
    ]
}


def _math_name(value: Any) -> str:
    if isinstance(value, bool):
        raise ValueError("math must be MATH1 through MATH4")
    text = str(value).strip().upper().replace(" ", "")
    if text.isdigit() and 1 <= int(text) <= 4:
        return f"MATH{int(text)}"
    if text in {"MATH1", "MATH2", "MATH3", "MATH4"}:
        return text
    raise ValueError("math must be MATH1 through MATH4")


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a finite number") from None
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    return result


def _integer(value: Any, name: str, low: int, high: int) -> int:
    result = _number(value, name)
    if not result.is_integer() or not low <= result <= high:
        raise ValueError(f"{name} must be an integer from {low} through {high}")
    return int(result)


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


def _string_response(value: Any) -> str:
    text = str(value)
    if len(text) >= 2 and text[0] == text[-1] == '"':
        return text[1:-1].replace('""', '"')
    return text


def _operator(value: Any) -> str:
    token = _OPERATOR_ALIASES.get(str(value).strip().upper(), str(value).strip().upper())
    if token not in _OPERATORS:
        raise ValueError(f"operator must be one of {', '.join(sorted(_OPERATORS))}")
    return token


def _operator_response(value: Any) -> str:
    token = str(value).strip().upper()
    # Responses are abbreviated by the instrument (for example SUBT and BST).
    return _operator(token)


def _enum(value: Any, name: str, values: set[str], aliases: dict[str, str] | None = None) -> str:
    token = str(value).strip().upper()
    token = (aliases or {}).get(token, token)
    if token not in values:
        raise ValueError(f"{name} must be one of {', '.join(sorted(values))}")
    return token


def _source(value: Any, math_name: str, name: str = "source") -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a documented CHAN, REF, or prior MATH source")
    token = value.strip().upper().replace(" ", "")
    match = _GENERAL_SOURCE.fullmatch(token)
    if match is None:
        raise ValueError(f"{name} must be CHAN1-CHAN4, REF1-REF10, or an earlier MATH output")
    channel, reference, prior_math = match.groups()
    if channel:
        return f"CHAN{channel}"
    if reference:
        return f"REF{reference}"
    index = int(prior_math)
    current_index = int(math_name[-1])
    if index >= current_index:
        raise ValueError(f"{name} may only refer to MATH outputs before {math_name}")
    return f"MATH{index}"


def _logic_source(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be CHAN1-CHAN4 or D0-D15")
    match = _LOGIC_SOURCE.fullmatch(value.strip().upper().replace(" ", ""))
    if match is None:
        raise ValueError(f"{name} must be CHAN1-CHAN4 or D0-D15")
    channel, digital = match.groups()
    return f"CHAN{channel}" if channel else f"D{digital}"


def _source_response(value: Any, math_name: str) -> str:
    return _source(value, math_name)


def _logic_source_response(value: Any, name: str) -> str:
    return _logic_source(value, name)


def _scpi_number(value: float) -> str:
    return format(value, ".15g")


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=0.0)


def _query_common(session: Any, math_name: str, operator: str) -> dict[str, Any]:
    prefix = f":{math_name}:"
    result: dict[str, Any] = {
        "math": math_name,
        "operator": operator,
        "display": _bool_response(session.query(prefix + "DISPlay?"), "display"),
        "grid": _enum(session.query(prefix + "GRID?"), "grid", {"FULL", "HALF", "NONE"}),
        "expand": _enum(session.query(prefix + "EXPand?"), "expand", {"GND", "CENT"}, {"CENTER": "CENT"}),
        # The manual's heading has a duplicated ':MATH<n>:', but its explicit
        # query line is ':MATH<n>:WAVetype?'; use that documented query form.
        "waveform_type": _enum(session.query(prefix + "WAVetype?"), "waveform_type", {"MAIN", "ZOOM"}),
        "label_visible": _bool_response(session.query(prefix + "LABel:SHOW?"), "label_visible"),
        "title": _string_response(session.query(prefix + "WINDow:TITLe?")),
        "display_mode": _bool_response(session.query(prefix + "DISMode?"), "display_mode"),
    }
    return result


def _query_filter(session: Any, math_name: str, *, include_cutoff2: bool = True) -> dict[str, Any]:
    prefix = f":{math_name}:FILTer:"
    result = {
        "filter_type": _enum(session.query(prefix + "TYPE?"), "filter_type", _FILTER),
        "cutoff1_hz": _number(session.query(prefix + "W1?"), "cutoff1_hz"),
    }
    if include_cutoff2:
        result["cutoff2_hz"] = _number(session.query(prefix + "W2?"), "cutoff2_hz")
    return result


def _query_math(session: Any, math_name: str) -> dict[str, Any]:
    operator = _operator_response(session.query(f":{math_name}:OPERator?"))
    result = _query_common(session, math_name, operator)
    if operator == _FFT:
        result["fft_note"] = "Use get_fft/set_fft for FFT-specific settings."
        return result
    prefix = f":{math_name}:"
    if operator in _ARITHMETIC | _FUNCTION | _FILTER:
        result["source1"] = _source_response(session.query(prefix + "SOURce1?"), math_name)
    if operator in _ARITHMETIC:
        result["source2"] = _source_response(session.query(prefix + "SOURce2?"), math_name)
    if operator in _LOGIC:
        result["logic_source1"] = _logic_source_response(session.query(prefix + "LSOurce1?"), "logic_source1")
        if operator != "NOT":
            result["logic_source2"] = _logic_source_response(session.query(prefix + "LSOurce2?"), "logic_source2")
        result["sensitivity"] = _number(session.query(prefix + "SENSitivity?"), "sensitivity")
        for channel in range(1, 5):
            result[f"threshold{channel}_v"] = _number(
                session.query(prefix + f"THReshold{channel}?"), f"threshold{channel}_v"
            )
    if operator in _ARITHMETIC | _FUNCTION | _FILTER:
        result["scale"] = _number(session.query(prefix + "SCALe?"), "scale")
        result["offset"] = _number(session.query(prefix + "OFFSet?"), "offset")
        result["invert"] = _bool_response(session.query(prefix + "INVert?"), "invert")
    if operator == "DIFF":
        result["distance"] = _integer(session.query(prefix + "DISTance?"), "distance", 5, 10000)
    if operator in _FILTER:
        result.update(_query_filter(session, math_name, include_cutoff2=operator in {"BPAS", "BST"}))
    return result


def get_math(session: Any, math: Any = 1) -> dict[str, Any]:
    """Return common MATH state and only fields applicable to its operator."""

    return _query_math(session, _math_name(math))


def _require_applicable(operator: str, fields: set[str]) -> None:
    common = {"display", "grid", "expand", "waveform_type", "label_visible", "display_mode", "operator"}
    unknown = fields - common
    if not unknown:
        return
    groups = {
        "source1": _ARITHMETIC | _FUNCTION | _FILTER,
        "source2": _ARITHMETIC,
        "logic_source1": _LOGIC,
        "logic_source2": _LOGIC - {"NOT"},
        "scale": _ARITHMETIC | _FUNCTION | _FILTER,
        "offset": _ARITHMETIC | _FUNCTION | _FILTER,
        "invert": _ARITHMETIC | _FUNCTION | _FILTER,
        "distance": {"DIFF"},
        "sensitivity": _LOGIC,
        "filter_type": _FILTER,
        "cutoff1_hz": _FILTER,
        "cutoff2_hz": {"BPAS", "BST"},
    }
    for field in unknown:
        if field.startswith("threshold"):
            allowed = _LOGIC
        else:
            allowed = groups.get(field)
        if allowed is None or operator not in allowed:
            raise ValueError(f"{field} is not applicable to MATH operator {operator}")


def set_math(
    session: Any,
    math: Any = 1,
    *,
    operator: Any = None,
    display: Any = None,
    source1: Any = None,
    source2: Any = None,
    logic_source1: Any = None,
    logic_source2: Any = None,
    scale: Any = None,
    offset: Any = None,
    invert: Any = None,
    grid: Any = None,
    expand: Any = None,
    waveform_type: Any = None,
    distance: Any = None,
    sensitivity: Any = None,
    threshold1_v: Any = None,
    threshold2_v: Any = None,
    threshold3_v: Any = None,
    threshold4_v: Any = None,
    filter_type: Any = None,
    cutoff1_hz: Any = None,
    cutoff2_hz: Any = None,
    label_visible: Any = None,
    display_mode: Any = None,
) -> dict[str, Any]:
    """Set selected non-FFT MATH fields after complete local validation."""

    math_name = _math_name(math)
    requested_operator = None if operator is None else _operator(operator)
    final_operator = requested_operator
    submitted = {
        name: value for name, value in {
            "operator": requested_operator, "display": display, "source1": source1,
            "source2": source2, "logic_source1": logic_source1, "logic_source2": logic_source2,
            "scale": scale, "offset": offset, "invert": invert, "grid": grid,
            "expand": expand, "waveform_type": waveform_type, "distance": distance,
            "sensitivity": sensitivity, "threshold1_v": threshold1_v, "threshold2_v": threshold2_v,
            "threshold3_v": threshold3_v, "threshold4_v": threshold4_v, "filter_type": filter_type,
            "cutoff1_hz": cutoff1_hz, "cutoff2_hz": cutoff2_hz, "label_visible": label_visible,
            "display_mode": display_mode,
        }.items() if value is not None
    }
    if final_operator is not None:
        _require_applicable(final_operator, set(submitted))

    # Normalize all arguments before the first write.
    normalized: dict[str, Any] = {}
    if display is not None:
        normalized["display"] = _bool_input(display, "display")
    if label_visible is not None:
        normalized["label_visible"] = _bool_input(label_visible, "label_visible")
    if display_mode is not None:
        normalized["display_mode"] = _bool_input(display_mode, "display_mode")
    if source1 is not None:
        normalized["source1"] = _source(source1, math_name, "source1")
    if source2 is not None:
        normalized["source2"] = _source(source2, math_name, "source2")
    if logic_source1 is not None:
        normalized["logic_source1"] = _logic_source(logic_source1, "logic_source1")
    if logic_source2 is not None:
        normalized["logic_source2"] = _logic_source(logic_source2, "logic_source2")
    if scale is not None:
        normalized["scale"] = _number(scale, "scale")
        if normalized["scale"] <= 0:
            raise ValueError("scale must be positive")
    if offset is not None:
        normalized["offset"] = _number(offset, "offset")
        if not -1e9 <= normalized["offset"] <= 1e9:
            raise ValueError("offset must be from -1 GV through +1 GV")
    if invert is not None:
        normalized["invert"] = _bool_input(invert, "invert")
    if grid is not None:
        normalized["grid"] = _enum(grid, "grid", {"FULL", "HALF", "NONE"})
    if expand is not None:
        normalized["expand"] = _enum(expand, "expand", {"GND", "CENT"}, {"CENTER": "CENT"})
    if waveform_type is not None:
        normalized["waveform_type"] = _enum(waveform_type, "waveform_type", {"MAIN", "ZOOM"})
        if normalized["waveform_type"] == "ZOOM":
            if final_operator == _FFT:
                raise ValueError("ZOOM waveform type is not supported for FFT")
    if distance is not None:
        normalized["distance"] = _integer(distance, "distance", 5, 10000)
    if sensitivity is not None:
        normalized["sensitivity"] = _number(sensitivity, "sensitivity")
        if not 0.1 <= normalized["sensitivity"] <= 1.0:
            raise ValueError("sensitivity must be from 0.1 through 1.0 div")
    threshold_values: dict[int, float] = {}
    for channel, value in enumerate((threshold1_v, threshold2_v, threshold3_v, threshold4_v), 1):
        if value is not None:
            threshold_values[channel] = _number(value, f"threshold{channel}_v")
            normalized[f"threshold{channel}_v"] = threshold_values[channel]
    if filter_type is not None:
        normalized["filter_type"] = _enum(filter_type, "filter_type", _FILTER)
    if cutoff1_hz is not None:
        normalized["cutoff1_hz"] = _number(cutoff1_hz, "cutoff1_hz")
        if normalized["cutoff1_hz"] <= 0:
            raise ValueError("cutoff1_hz must be positive")
    if cutoff2_hz is not None:
        normalized["cutoff2_hz"] = _number(cutoff2_hz, "cutoff2_hz")
        if normalized["cutoff2_hz"] <= 0:
            raise ValueError("cutoff2_hz must be positive")

    # The operator and filter-type selectors describe the same four filter
    # modes.  Validate an explicitly supplied filter type against an explicitly
    # supplied filter operator, but do not synthesize the omitted field.
    final_filter = normalized.get("filter_type", final_operator if final_operator in _FILTER else None)
    if final_operator in _FILTER and final_filter != final_operator:
        raise ValueError("filter_type must match the selected filter operator")
    if final_operator in _FILTER and final_filter in {"BPAS", "BST"}:
        if "cutoff1_hz" in normalized and "cutoff2_hz" in normalized and not normalized["cutoff1_hz"] < normalized["cutoff2_hz"]:
            raise ValueError("cutoff1_hz must be lower than cutoff2_hz")
        if "cutoff1_hz" in normalized and "cutoff2_hz" in normalized and not normalized["cutoff1_hz"] < normalized["cutoff2_hz"]:
            raise ValueError("cutoff1_hz must be lower than cutoff2_hz")

    writes: list[str] = []
    prefix = f":{math_name}:"
    if requested_operator is not None:
        writes.append(prefix + "OPERator " + requested_operator)
    common_commands = {
        "display": ("DISPlay", lambda value: "1" if value else "0"),
        "grid": ("GRID", str),
        "expand": ("EXPand", str),
        "waveform_type": ("WAVetype", str),
        "label_visible": ("LABel:SHOW", lambda value: "1" if value else "0"),
        "display_mode": ("DISMode", lambda value: "1" if value else "0"),
    }
    for field, (command, formatter) in common_commands.items():
        if field in normalized:
            writes.append(prefix + command + " " + formatter(normalized[field]))
    field_commands = {
        "source1": "SOURce1", "source2": "SOURce2", "logic_source1": "LSOurce1",
        "logic_source2": "LSOurce2", "scale": "SCALe", "offset": "OFFSet", "invert": "INVert",
        "distance": "DISTance", "sensitivity": "SENSitivity", "filter_type": "FILTer:TYPE",
        "cutoff1_hz": "FILTer:W1", "cutoff2_hz": "FILTer:W2",
        "threshold1_v": "THReshold1", "threshold2_v": "THReshold2",
        "threshold3_v": "THReshold3", "threshold4_v": "THReshold4",
    }
    for field, command in field_commands.items():
        if field not in normalized:
            continue
        new = normalized[field]
        value = ("1" if new else "0") if isinstance(new, bool) else _scpi_number(new) if isinstance(new, float) else str(new)
        writes.append(prefix + command + " " + value)

    for command in writes:
        session.write(command)
    return {
        "math": math_name,
        "requested": {**normalized, **({"operator": requested_operator} if requested_operator is not None else {})},
        "sent": bool(writes),
        "verified": False,
        "commands": writes,
    }


def math_action(session: Any, math: Any = 1, *, action: Any = "RESET") -> dict[str, Any]:
    """Perform an explicit documented MATH action; currently only RESET exists."""

    math_name = _math_name(math)
    if str(action).strip().upper() != "RESET":
        raise ValueError("action must be RESET")
    session.write(f":{math_name}:RESet")
    command = f":{math_name}:RESet"
    return {"math": math_name, "action": "reset", "sent": True, "verified": False, "commands": [command]}


_SCHEMA = {
    "type": "object",
    "properties": {
        "math": _MATH_PROPERTY,
        "operator": {"type": "string", "enum": sorted(_OPERATORS)},
        "display": {"type": "boolean"}, "source1": {"type": "string"}, "source2": {"type": "string"},
        "logic_source1": {"type": "string"}, "logic_source2": {"type": "string"},
        "scale": {"type": "number", "exclusiveMinimum": 0}, "offset": {"type": "number", "minimum": -1e9, "maximum": 1e9},
        "invert": {"type": "boolean"}, "grid": {"type": "string", "enum": ["FULL", "HALF", "NONE"]},
        "expand": {"type": "string", "enum": ["GND", "CENT"]}, "waveform_type": {"type": "string", "enum": ["MAIN", "ZOOM"]},
        "distance": {"type": "integer", "minimum": 5, "maximum": 10000}, "sensitivity": {"type": "number", "minimum": 0.1, "maximum": 1.0},
        "threshold1_v": {"type": "number"}, "threshold2_v": {"type": "number"}, "threshold3_v": {"type": "number"}, "threshold4_v": {"type": "number"},
        "filter_type": {"type": "string", "enum": sorted(_FILTER)}, "cutoff1_hz": {"type": "number", "exclusiveMinimum": 0}, "cutoff2_hz": {"type": "number", "exclusiveMinimum": 0},
        "label_visible": {"type": "boolean"}, "display_mode": {"type": "boolean"},
    },
    "required": ["math"],
}


TOOLS = [
    ToolSpec(
        name="get_math", description="Read effective MHO98 non-FFT MATH settings and only applicable operator-specific fields.",
        input_schema={"type": "object", "properties": {"math": _MATH_PROPERTY}, "required": ["math"]},
        handler=get_math, read_only=True, needs_session=True,
    ),
    ToolSpec(
        name="set_math", description="Set validated MHO98 non-FFT MATH fields, preserving omitted mode-specific state; FFT fields belong to get_fft/set_fft.",
        input_schema=_SCHEMA, handler=set_math, read_only=False, needs_session=True,
    ),
    ToolSpec(
        name="math_action", description="Perform an explicit documented MHO98 MATH action, currently RESET only.",
        input_schema={"type": "object", "properties": {"math": _MATH_PROPERTY, "action": {"type": "string", "enum": ["RESET"]}}, "required": ["math", "action"]},
        handler=math_action, read_only=False, needs_session=True,
    ),
]
