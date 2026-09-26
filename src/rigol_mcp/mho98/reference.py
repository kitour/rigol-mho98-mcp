"""MHO98 reference waveform controls.

The reference command family has ten slots and nine documented command
entries.  ``get_reference`` reads only the fields that have documented query
forms; ``reference_action`` is the explicit path for CURRENT, SAVE, and
RESET, none of which has a documented query.
"""

from __future__ import annotations

import math
from numbers import Real
from typing import Any

from .api import ToolSpec


_SLOT_MIN = 1
_SLOT_MAX = 10
_COLORS = {
    "GRAY": "GRAY",
    "GREY": "GRAY",
    "GREEN": "GREen",
    "GRE": "GREen",
    "BLUE": "BLUE",
    "RED": "RED",
    "ORANGE": "ORANge",
    "ORAN": "ORANge",
}
_COLOR_RESPONSES = {
    "GRAY": "GRAY",
    "GREY": "GRAY",
    "GRE": "GRE",
    "GREEN": "GRE",
    "BLUE": "BLUE",
    "RED": "RED",
    "ORAN": "ORAN",
    "ORANGE": "ORAN",
}
_ACTION_COMMANDS = {
    "CURRENT": ":REFerence:CURRent",
    "SAVE": ":REFerence:SAVE",
    "RESET": ":REFerence:RESet",
}
_ACTION_EFFECTS = {
    "CURRENT": "select the reference slot as the current reference channel",
    "SAVE": "capture the selected source waveform into the reference slot",
    "RESET": "reset only the reference display scale and offset",
}


def _slot(value: Any, name: str = "reference") -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer from 1 through 10")
    if isinstance(value, Real):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value.strip())
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be an integer from 1 through 10") from None
    else:
        raise ValueError(f"{name} must be an integer from 1 through 10")
    if not math.isfinite(number) or not number.is_integer() or not _SLOT_MIN <= number <= _SLOT_MAX:
        raise ValueError(f"{name} must be an integer from 1 through 10")
    return int(number)


def _reference_arg(reference: Any, ref: Any) -> int:
    if ref is not None:
        # ``reference`` is retained as the canonical public name.  Accepting
        # ``ref`` keeps direct Python callers aligned with the SCPI spelling.
        if _slot(reference) != 1:
            raise ValueError("provide only one of reference and ref")
        reference = ref
    return _slot(reference)


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


def _positive(value: Any, name: str) -> float:
    result = _number(value, name)
    if result <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return result


def _scpi_number(value: float) -> str:
    return format(value, ".15g")


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=0.0)


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
        raise ValueError(f"{name} must be CHAN1-CHAN4, MATH1-MATH4, or D0-D15")
    token = value.strip().upper().replace(" ", "")
    if token.startswith("CHANNEL"):
        token = "CHAN" + token[7:]
    elif token.startswith("CH") and not token.startswith("CHAN"):
        token = "CHAN" + token[2:]
    if token.startswith("CHAN") and token[4:].isdigit() and 1 <= int(token[4:]) <= 4:
        return f"CHAN{int(token[4:])}"
    if token.startswith("MATH") and token[4:].isdigit() and 1 <= int(token[4:]) <= 4:
        return f"MATH{int(token[4:])}"
    if token.startswith("D") and token[1:].isdigit() and 0 <= int(token[1:]) <= 15:
        return f"D{int(token[1:])}"
    raise ValueError(f"{name} must be CHAN1-CHAN4, MATH1-MATH4, or D0-D15")


def _source_write(source: str) -> str:
    if source.startswith("CHAN"):
        return f"CHANnel{source[-1]}"
    return source


def _source_response(value: Any) -> str:
    return _source(str(value), "source response")


def _color(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("color must be GRAY, GREEN, BLUE, RED, or ORANGE")
    token = value.strip().upper()
    if token not in _COLORS:
        raise ValueError("color must be GRAY, GREEN, BLUE, RED, or ORANGE")
    return _COLORS[token]


def _color_response(value: Any) -> str:
    token = str(value).strip().upper()
    if token not in _COLOR_RESPONSES:
        raise ValueError(f"invalid color response from MHO98: {value!r}")
    return _COLOR_RESPONSES[token]


def _label_value(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("label must be a string")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("label must not contain control characters")
    if ";" in value or "\r" in value or "\n" in value:
        raise ValueError("label must not contain SCPI delimiters")
    return '"' + value.replace('"', '""') + '"'


def _label_response(value: Any) -> str:
    text = str(value)
    if len(text) >= 2 and text[0] == text[-1] == '"':
        return text[1:-1].replace('""', '"')
    return text


def _query_reference(session: Any, reference: int) -> dict[str, Any]:
    prefix = ":REFerence:"
    return {
        "reference": reference,
        "source": _source_response(session.query(prefix + f"SOURce? {reference}")),
        "scale_v_div": _positive(session.query(prefix + f"VSCale? {reference}"), "scale_v_div"),
        "offset_v": _number(session.query(prefix + f"VOFFset? {reference}"), "offset_v"),
        "color": _color_response(session.query(prefix + f"COLor? {reference}")),
        "label_visible": _bool_response(session.query(prefix + "LABel:ENABle?"), "label_visible"),
        "label": _label_response(session.query(prefix + f"LABel:CONTent? {reference}")),
    }


def get_reference(session: Any, reference: Any = 1, *, ref: Any = None) -> dict[str, Any]:
    """Return the documented, queryable state of one reference slot."""

    return _query_reference(session, _reference_arg(reference, ref))


def _impedance_response(value: Any) -> int:
    token = str(value).strip().upper().replace("OHM", "").replace("Ω", "")
    if token in {"FIFT", "FIFTY", "50", "50.0"}:
        return 50
    if token in {"OMEG", "OMEGA", "1M", "1MOHM", "1000000", "1000000.0"}:
        return 1_000_000
    try:
        number = float(token)
    except ValueError:
        number = math.nan
    if number in {50, 1_000_000}:
        return int(number)
    raise ValueError(f"invalid channel impedance response from MHO98: {value!r}")


def _validate_offset(offset: float, scale: float) -> None:
    low, high = -10.0 * scale, 10.0 * scale
    if not low <= offset <= high:
        raise ValueError(f"offset_v {offset:g} is outside the documented range {low:g}..{high:g} V")


def set_reference(
    session: Any,
    reference: Any = 1,
    *,
    ref: Any = None,
    source: Any = None,
    scale_v_div: Any = None,
    offset_v: Any = None,
    color: Any = None,
    label_visible: Any = None,
    label: Any = None,
) -> dict[str, Any]:
    """Send only the explicitly requested reference fields.

    Setting configuration never captures a waveform.  Use ``reference_action``
    with ``action="SAVE"`` for that explicit, slot-specific operation.
    """

    slot = _reference_arg(reference, ref)
    requested_source = None if source is None else _source(source)
    requested_scale = None if scale_v_div is None else _positive(scale_v_div, "scale_v_div")
    requested_offset = None if offset_v is None else _number(offset_v, "offset_v")
    requested_color = None if color is None else _color(color)
    requested_label_visible = None if label_visible is None else _bool_input(label_visible, "label_visible")
    requested_label = None if label is None else _label_value(label)

    if requested_scale is not None and requested_offset is not None:
        _validate_offset(requested_offset, requested_scale)

    writes: list[str] = []
    prefix = ":REFerence:"
    if requested_source is not None:
        writes.append(prefix + f"SOURce {slot},{_source_write(requested_source)}")
    if requested_scale is not None:
        writes.append(prefix + f"VSCale {slot},{_scpi_number(requested_scale)}")
    if requested_offset is not None:
        writes.append(prefix + f"VOFFset {slot},{_scpi_number(requested_offset)}")
    if requested_color is not None:
        writes.append(prefix + f"COLor {slot},{requested_color}")
    if requested_label_visible is not None:
        writes.append(prefix + f"LABel:ENABle {'1' if requested_label_visible else '0'}")
    if requested_label is not None:
        writes.append(prefix + f"LABel:CONTent {slot},{requested_label}")

    for command in writes:
        session.write(command)
    return {
        "reference": slot,
        "requested": {key: value for key, value in {
            "source": requested_source, "scale_v_div": requested_scale, "offset_v": requested_offset,
            "color": requested_color, "label_visible": requested_label_visible, "label": label,
        }.items() if value is not None},
        "sent": bool(writes),
        "verified": False,
        "commands": writes,
    }


def reference_action(
    session: Any,
    reference: Any = 1,
    *,
    ref: Any = None,
    action: Any,
) -> dict[str, Any]:
    """Perform one explicit CURRENT, SAVE, or reference-display RESET action."""

    slot = _reference_arg(reference, ref)
    if not isinstance(action, str):
        raise ValueError("action must be CURRENT, SAVE, or RESET")
    normalized = action.strip().upper().replace("-", "_")
    aliases = {"CURRENT": "CURRENT", "SAVE": "SAVE", "RESET": "RESET"}
    normalized = aliases.get(normalized)
    if normalized is None:
        raise ValueError("action must be CURRENT, SAVE, or RESET")

    command = f"{_ACTION_COMMANDS[normalized]} {slot}"
    session.write(command)
    return {"reference": slot, "action": normalized.lower(), "command": command, "effect": _ACTION_EFFECTS[normalized], "sent": True, "verified": False, "commands": [command]}


_SLOT_PROPERTY = {"type": "integer", "minimum": 1, "maximum": 10}
_SOURCE_PROPERTY = {"type": "string", "pattern": r"^(?:CH(?:AN(?:nel)?)?[1-4]|MATH[1-4]|D(?:[0-9]|1[0-5]))$"}
_SET_PROPERTIES = {
    "reference": _SLOT_PROPERTY,
    "source": _SOURCE_PROPERTY,
    "scale_v_div": {"type": "number", "exclusiveMinimum": 0},
    "offset_v": {"type": "number"},
    "color": {"type": "string", "enum": ["GRAY", "GREEN", "BLUE", "RED", "ORANGE"]},
    "label_visible": {"type": "boolean"},
    "label": {"type": "string"},
}


TOOLS = [
    ToolSpec(
        "get_reference",
        "Read one documented MHO98 reference slot and global reference-label visibility.",
        {"type": "object", "properties": {"reference": _SLOT_PROPERTY}, "required": ["reference"], "additionalProperties": False},
        get_reference,
        read_only=True,
        needs_session=True,
    ),
    ToolSpec(
        "set_reference",
        "Send documented MHO98 reference source, display, color, and label fields only; omitted fields are untouched and no waveform is captured.",
        {"type": "object", "properties": _SET_PROPERTIES, "required": ["reference"], "additionalProperties": False},
        set_reference,
        read_only=False,
        needs_session=True,
    ),
    ToolSpec(
        "reference_action",
        "Explicitly make a reference current, save the selected source into its slot, or reset only that slot's display scale and offset.",
        {"type": "object", "properties": {"reference": _SLOT_PROPERTY, "action": {"type": "string", "enum": ["CURRENT", "SAVE", "RESET"]}}, "required": ["reference", "action"], "additionalProperties": False},
        reference_action,
        read_only=False,
        needs_session=True,
    ),
]
