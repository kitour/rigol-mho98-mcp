"""MHO98 logic-analyzer display and digital-channel configuration."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from numbers import Real
from typing import Any

from .api import ToolSpec


_CHANNELS = tuple(f"D{index}" for index in range(16))
_CHANNEL_SET = frozenset(_CHANNELS)
_PODS = ("POD1", "POD2")
_SIZE_READBACK = {
    "SMAL": "SMALL",
    "SMALL": "SMALL",
    "MED": "MEDIUM",
    "MEDIUM": "MEDIUM",
    "LARG": "LARGE",
    "LARGE": "LARGE",
}
_LABEL_FORBIDDEN = re.compile(r"[\x00-\x1f\x7f\r\n;,\"]")


def _digital(value: Any, name: str = "channel") -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be D0 through D15")
    text = value.strip().upper().replace(" ", "")
    if text not in _CHANNEL_SET:
        raise ValueError(f"{name} must be D0 through D15")
    return text


def _bool_response(value: Any, name: str) -> bool:
    text = str(value).strip().upper()
    if text in {"1", "ON", "TRUE"}:
        return True
    if text in {"0", "OFF", "FALSE"}:
        return False
    raise ValueError(f"invalid {name} response from MHO98: {value!r}")


def _requested_bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a real boolean")
    return value


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


def _threshold(value: Any, name: str) -> float:
    result = _finite(value, name)
    if not -15.0 <= result <= 15.0:
        raise ValueError(f"{name} must be between -15 and 15 V")
    return result


def _label(value: Any, name: str = "label") -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    if any(ord(char) > 0x7E for char in value) or _LABEL_FORBIDDEN.search(value):
        raise ValueError(f"{name} must be printable ASCII without SCPI delimiters")
    return value


def _label_response(value: Any) -> str:
    text = str(value)
    if len(text) >= 2 and text[0] == text[-1] == '"':
        text = text[1:-1].replace('""', '"')
    return text


def _auto_sort(value: Any) -> str:
    text = str(value).strip().upper()
    if text not in {"D0D15", "D15D0"}:
        raise ValueError("auto_sort must be D0D15 or D15D0")
    return text


def _size(value: Any, name: str = "size") -> str:
    text = str(value).strip().upper()
    aliases = {
        "SMAL": "SMALL",
        "SMALL": "SMALL",
        "MED": "MEDIUM",
        "MEDIUM": "MEDIUM",
        "LARG": "LARGE",
        "LARGE": "LARGE",
    }
    if text not in aliases:
        raise ValueError(f"{name} must be SMALL, MEDIUM, or LARGE")
    return aliases[text]


def _number(value: float) -> str:
    return format(value, ".15g")


def _query_state(session: Any, channels: Sequence[str] | None = None) -> dict[str, Any]:
    selected = _CHANNELS if channels is None else tuple(channels)
    result: dict[str, Any] = {
        "enabled": _bool_response(session.query(":LA:ENABle?"), "enabled"),
        "active_channel": _digital(session.query(":LA:ACTive?"), "active_channel"),
        "auto_sort": _auto_sort(session.query(":LA:AUTosort?")),
        "size": _size(session.query(":LA:SIZE?")),
        "channels": {},
        "pods": {},
    }
    for channel in selected:
        result["channels"][channel] = {
            "enabled": _bool_response(
                session.query(f":LA:DIGital:ENABle? {channel}"), f"{channel}.enabled"
            ),
            "label": _label_response(session.query(f":LA:DIGital:LABel? {channel}")),
        }
    for pod in _PODS:
        result["pods"][pod] = {
            "display": _bool_response(session.query(f":LA:{pod}:DISPlay?"), f"{pod}.display"),
            "threshold_v": _finite(session.query(f":LA:{pod}:THReshold?"), f"{pod}.threshold_v"),
        }
    return result


def get_logic_analyzer(session: Any, channels: Any = None) -> dict[str, Any]:
    """Read LA state and POD thresholds, optionally limiting channel queries."""

    selected: tuple[str, ...] | None
    if channels is None:
        selected = None
    else:
        if isinstance(channels, (str, bytes)) or not isinstance(channels, Sequence):
            raise ValueError("channels must be a list of D0 through D15")
        normalized = [_digital(value, "channels item") for value in channels]
        if len(set(normalized)) != len(normalized):
            raise ValueError("channels must not contain duplicates")
        selected = tuple(normalized)
    return _query_state(session, selected)


def _channel_requests(
    channels: Any,
    labels: Any,
    channel_enables: Any,
) -> dict[str, dict[str, Any]]:
    requests: dict[str, dict[str, Any]] = {}

    def add(channel_value: Any, field: str, value: Any) -> None:
        channel = _digital(channel_value, "channel")
        entry = requests.setdefault(channel, {})
        if field == "enabled":
            entry[field] = _requested_bool(value, f"{channel}.enabled")
        else:
            entry[field] = _label(value, f"{channel}.label")

    if channels is not None:
        if not isinstance(channels, Mapping):
            raise ValueError("channels must be an object keyed by D0 through D15")
        for channel_value, settings in channels.items():
            if isinstance(settings, bool):
                add(channel_value, "enabled", settings)
                continue
            if not isinstance(settings, Mapping):
                raise ValueError(f"{channel_value} settings must be an object")
            unknown = set(settings) - {"enabled", "label"}
            if unknown:
                raise ValueError(f"unsupported channel fields: {sorted(unknown)!r}")
            if not settings:
                raise ValueError(f"{channel_value} settings cannot be empty")
            if "enabled" in settings:
                add(channel_value, "enabled", settings["enabled"])
            if "label" in settings:
                add(channel_value, "label", settings["label"])

    for field, values in (("label", labels), ("enabled", channel_enables)):
        if values is None:
            continue
        if not isinstance(values, Mapping):
            raise ValueError(f"{field}s must be an object keyed by D0 through D15")
        for channel_value, value in values.items():
            channel = _digital(channel_value, "channel")
            if field in requests.get(channel, {}) and requests[channel][field] != value:
                raise ValueError(f"conflicting {channel}.{field} requests")
            add(channel, field, value)
    return requests


def set_logic_analyzer(
    session: Any,
    *,
    enabled: Any = None,
    channels: Any = None,
    labels: Any = None,
    channel_enables: Any = None,
    pod1_display: Any = None,
    pod1_threshold_v: Any = None,
    pod2_display: Any = None,
    pod2_threshold_v: Any = None,
    active_channel: Any = None,
    auto_sort: Any = None,
    size: Any = None,
) -> dict[str, Any]:
    """Send only explicitly requested LA controls without readback."""

    requested_enabled = None if enabled is None else _requested_bool(enabled, "enabled")
    requested_channels = _channel_requests(channels, labels, channel_enables)
    requested_pod_display = {
        "POD1": None if pod1_display is None else _requested_bool(pod1_display, "pod1_display"),
        "POD2": None if pod2_display is None else _requested_bool(pod2_display, "pod2_display"),
    }
    requested_pod_threshold = {
        "POD1": None if pod1_threshold_v is None else _threshold(pod1_threshold_v, "pod1_threshold_v"),
        "POD2": None if pod2_threshold_v is None else _threshold(pod2_threshold_v, "pod2_threshold_v"),
    }
    requested_active = None if active_channel is None else _digital(active_channel, "active_channel")
    requested_sort = None if auto_sort is None else _auto_sort(auto_sort)
    requested_size = None if size is None else _size(size)

    if requested_active is not None and requested_channels.get(requested_active, {}).get("enabled") is False:
        raise ValueError("active_channel must be enabled in the final state")
    if requested_size == "LARGE" and sum(
        request.get("enabled") is True for request in requested_channels.values()
    ) > 8:
        raise ValueError("LARGE size requires no more than 8 enabled channels")

    writes: list[str] = []
    if requested_enabled is not None:
        writes.append(f":LA:ENABle {int(requested_enabled)}")

    # Explicit POD and digital enables precede an explicit active selection.
    for pod in _PODS:
        value = requested_pod_display[pod]
        if value is not None:
            writes.append(f":LA:{pod}:DISPlay {int(value)}")
    for channel in _CHANNELS:
        request = requested_channels.get(channel, {})
        if "enabled" in request:
            enable_value = request["enabled"]
            writes.append(f":LA:DIGital:ENABle {channel},{int(enable_value)}")
    for channel in _CHANNELS:
        request = requested_channels.get(channel, {})
        if "label" in request:
            writes.append(f":LA:DIGital:LABel {channel},{request['label']}")
    for pod in _PODS:
        value = requested_pod_threshold[pod]
        if value is not None:
            writes.append(f":LA:{pod}:THReshold {_number(value)}")
    if requested_sort is not None:
        writes.append(f":LA:AUTosort {requested_sort}")
    if requested_size is not None:
        writes.append(f":LA:SIZE {_SIZE_READBACK[requested_size]}")
    if requested_active is not None:
        writes.append(f":LA:ACTive {requested_active}")

    for command in writes:
        session.write(command)
    requested = {
        key: value for key, value in {
            "enabled": requested_enabled, "channels": requested_channels or None,
            "pod1_display": requested_pod_display["POD1"], "pod1_threshold_v": requested_pod_threshold["POD1"],
            "pod2_display": requested_pod_display["POD2"], "pod2_threshold_v": requested_pod_threshold["POD2"],
            "active_channel": requested_active, "auto_sort": requested_sort, "size": requested_size,
        }.items() if value is not None
    }
    return {"sent": bool(writes), "verified": False, "commands": writes, "requested": requested, **requested}


_CHANNEL_SETTING_SCHEMA = {
    "type": "object",
    "properties": {"enabled": {"type": "boolean"}, "label": {"type": "string"}},
    "additionalProperties": False,
    "minProperties": 1,
}

_GET_SCHEMA = {
    "type": "object",
    "properties": {
        "channels": {
            "type": "array",
            "items": {"type": "string", "pattern": "^D(?:[0-9]|1[0-5])$"},
            "uniqueItems": True,
        }
    },
    "required": [],
}

_SET_SCHEMA = {
    "type": "object",
    "properties": {
        "enabled": {"type": "boolean"},
        "channels": {
            "type": "object",
            "additionalProperties": {"oneOf": [{"type": "boolean"}, _CHANNEL_SETTING_SCHEMA]},
        },
        "labels": {"type": "object", "additionalProperties": {"type": "string"}},
        "channel_enables": {"type": "object", "additionalProperties": {"type": "boolean"}},
        "pod1_display": {"type": "boolean"},
        "pod1_threshold_v": {"type": "number", "minimum": -15, "maximum": 15},
        "pod2_display": {"type": "boolean"},
        "pod2_threshold_v": {"type": "number", "minimum": -15, "maximum": 15},
        "active_channel": {"type": "string", "pattern": "^D(?:[0-9]|1[0-5])$"},
        "auto_sort": {"type": "string", "enum": ["D0D15", "D15D0"]},
        "size": {"type": "string", "enum": ["SMALL", "MEDIUM", "LARGE"]},
    },
    "required": [],
}

TOOLS = [
    ToolSpec(
        name="get_logic_analyzer",
        description="Read MHO98 LA state, POD display/threshold settings, and selected digital-channel enable/label settings.",
        input_schema=_GET_SCHEMA,
        handler=get_logic_analyzer,
        read_only=True,
        needs_session=True,
    ),
    ToolSpec(
        name="set_logic_analyzer",
        description="Send selected MHO98 LA, digital-channel, POD, active-channel, auto-sort, and display-size commands; resulting state is not verified.",
        input_schema=_SET_SCHEMA,
        handler=set_logic_analyzer,
        read_only=False,
        needs_session=True,
    ),
]
