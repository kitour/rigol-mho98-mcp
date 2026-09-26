"""MHO98 AUTO settings and the explicit waveform auto-setting action."""

from __future__ import annotations

from typing import Any

from .api import ToolSpec


_COMMANDS = {
    "autoscale": ":SYSTem:AUToscale",
    "peak": ":AUToset:PEAK",
    "open_channels": ":AUToset:OPENch",
    "overlap": ":AUToset:OVERlap",
    "keep_coupling": ":AUToset:KEEPcoup",
    "lock": ":AUToset:LOCK",
    "enabled": ":AUToset:ENAble",
}
_AUTO_EFFECT = (
    "Changes channel vertical scale, horizontal timebase, and trigger mode "
    "to optimize the displayed waveform."
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


def _one_alias(primary: Any, alias: Any, primary_name: str, alias_name: str) -> Any:
    if primary is not None and alias is not None:
        raise ValueError(f"provide only one of {primary_name} and {alias_name}")
    return primary if primary is not None else alias


def _query_autoset(session: Any) -> dict[str, bool]:
    """Read only the documented AUTO settings and system gate."""

    return {
        "autoscale": _bool_response(
            session.query(_COMMANDS["autoscale"] + "?"), "system autoscale gate"
        ),
        "peak": _bool_response(session.query(_COMMANDS["peak"] + "?"), "peak priority"),
        "open_channels": _bool_response(
            session.query(_COMMANDS["open_channels"] + "?"), "enabled channels only"
        ),
        "overlap": _bool_response(
            session.query(_COMMANDS["overlap"] + "?"), "waveform overlap"
        ),
        "keep_coupling": _bool_response(
            session.query(_COMMANDS["keep_coupling"] + "?"), "keep coupling"
        ),
        "lock": _bool_response(session.query(_COMMANDS["lock"] + "?"), "AUTO lock"),
        "enabled": _bool_response(
            session.query(_COMMANDS["enabled"] + "?"), "AUTO enabled"
        ),
    }


def get_autoset(session: Any) -> dict[str, bool]:
    """Return documented AUTO settings, including the system AUTO gate."""

    return _query_autoset(session)


def set_autoset(
    session: Any,
    *,
    autoscale: Any = None,
    auto_scale: Any = None,
    peak: Any = None,
    peak_priority: Any = None,
    open_channels: Any = None,
    enabled_channels_only: Any = None,
    overlap: Any = None,
    keep_coupling: Any = None,
    keepcoup: Any = None,
    lock: Any = None,
    enabled: Any = None,
    enable: Any = None,
) -> dict[str, Any]:
    """Send only explicitly requested AUTO settings.

    ``lock`` and ``enabled`` are inverse aliases for the same instrument
    capability.  A request may provide either one, or both when
    ``enabled == not lock``.  The canonical write is ``:AUToset:ENAble`` so
    both API spellings have identical behavior.
    """

    # Resolve API aliases before communicating, so malformed combinations cannot
    # result in a partial write.
    requested_autoscale = _one_alias(autoscale, auto_scale, "autoscale", "auto_scale")
    requested_peak = _one_alias(peak, peak_priority, "peak", "peak_priority")
    requested_open = _one_alias(
        open_channels,
        enabled_channels_only,
        "open_channels",
        "enabled_channels_only",
    )
    requested_keep = _one_alias(
        keep_coupling, keepcoup, "keep_coupling", "keepcoup"
    )
    requested_enabled = _one_alias(enabled, enable, "enabled", "enable")

    normalized: dict[str, bool | None] = {
        "autoscale": None
        if requested_autoscale is None
        else _bool_input(requested_autoscale, "autoscale"),
        "peak": None
        if requested_peak is None
        else _bool_input(requested_peak, "peak"),
        "open_channels": None
        if requested_open is None
        else _bool_input(requested_open, "open_channels"),
        "overlap": None
        if overlap is None
        else _bool_input(overlap, "overlap"),
        "keep_coupling": None
        if requested_keep is None
        else _bool_input(requested_keep, "keep_coupling"),
        "enabled": None
        if requested_enabled is None
        else _bool_input(requested_enabled, "enabled"),
        "lock": None if lock is None else _bool_input(lock, "lock"),
    }

    if normalized["lock"] is not None and normalized["enabled"] is not None:
        if normalized["enabled"] == normalized["lock"]:
            raise ValueError("lock and enabled are contradictory; enabled must equal not lock")

    writes: list[str] = []
    for field in ("autoscale", "peak", "open_channels", "overlap", "keep_coupling"):
        requested = normalized[field]
        if requested is not None:
            writes.append(f"{_COMMANDS[field]} {'1' if requested else '0'}")

    requested_enabled_value = normalized["enabled"]
    if normalized["lock"] is not None:
        requested_enabled_value = not normalized["lock"]
    if requested_enabled_value is not None:
        writes.append(f"{_COMMANDS['enabled']} {'1' if requested_enabled_value else '0'}")

    for command in writes:
        session.write(command)
    requested = {key: value for key, value in normalized.items() if value is not None}
    return {"sent": bool(writes), "verified": False, "commands": writes, "requested": requested, **requested}


def run_autoset(session: Any) -> dict[str, Any]:
    """Send the explicit AUTO action without gate or operation preflight."""

    command = ":AUToset"
    session.write(command)
    return {"sent": True, "verified": False, "commands": [command], "action": "run_autoset", "effect": _AUTO_EFFECT}


_SET_PROPERTIES = {
    "autoscale": {"type": "boolean"},
    "auto_scale": {"type": "boolean"},
    "peak": {"type": "boolean"},
    "peak_priority": {"type": "boolean"},
    "open_channels": {"type": "boolean"},
    "enabled_channels_only": {"type": "boolean"},
    "overlap": {"type": "boolean"},
    "keep_coupling": {"type": "boolean"},
    "keepcoup": {"type": "boolean"},
    "lock": {"type": "boolean"},
    "enabled": {"type": "boolean"},
    "enable": {"type": "boolean"},
}

TOOLS = [
    ToolSpec(
        name="get_autoset",
        description="Read documented MHO98 AUTO settings and the system AUTO gate.",
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        handler=get_autoset,
        read_only=True,
        needs_session=True,
    ),
    ToolSpec(
        name="set_autoset",
        description=(
            "Send selected documented MHO98 AUTO commands; omitted settings are preserved and resulting state is not verified."
        ),
        input_schema={
            "type": "object",
            "properties": _SET_PROPERTIES,
            "required": [],
            "additionalProperties": False,
        },
        handler=set_autoset,
        read_only=False,
        needs_session=True,
    ),
    ToolSpec(
        name="run_autoset",
        description=(
            "Send the explicit MHO98 AUTO action; it may change channel, timebase, and trigger settings."
        ),
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        handler=run_autoset,
        read_only=False,
        needs_session=True,
    ),
]
