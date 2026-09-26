"""MHO98 Bode-plot configuration and explicit sweep controls.

This module implements only the commands documented by the MHO98 Bode-plot
guide.  The guide documents configuration queries, but no trace/result query;
there is consequently no result-download handler here.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

from .api import ToolSpec


_SWEEP_TYPES = frozenset({"LOG", "LINE"})
_AMPLITUDE_RANGES = {
    "ALL": "ALL",
    "10": "10",
    "100": "100",
    "1K": "1K",
    "1000": "1K",
    "10K": "10K",
    "10000": "10K",
    "100K": "100K",
    "100000": "100K",
    "1M": "1M",
    "1000000": "1M",
    "10M": "10M",
    "10000000": "10M",
    "25M": "25M",
    "25000000": "25M",
    "1E1": "10",
    "1E2": "100",
    "1E3": "1K",
    "1E4": "10K",
    "1E5": "100K",
    "1E6": "1M",
    "1E7": "10M",
    "2.5E7": "25M",
}
_AMPLITUDE_RANGE_ENUM = ["ALL", "10", "100", "1K", "10K", "100K", "1M", "10M", "25M"]


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a finite number") from None
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    return result


def _scpi_number(value: float) -> str:
    return format(value, ".15g")


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


def _integer_response(value: Any, name: str) -> int:
    number = _finite(value, name)
    if not number.is_integer():
        raise ValueError(f"invalid {name} response from MHO98: {value!r}")
    return int(number)


def _channel(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be CHAN1 through CHAN4")
    token = str(value).strip().upper().replace(" ", "")
    for prefix in ("CHANNEL", "CHANN", "CHAN", "CH"):
        if token.startswith(prefix):
            token = token[len(prefix):]
            break
    if token not in {"1", "2", "3", "4"}:
        raise ValueError(f"{name} must be CHAN1 through CHAN4")
    return int(token)


def _channel_response(value: Any, name: str) -> int:
    return _channel(value, name + " response")


def _sweep_type(value: Any, name: str = "sweep_type") -> str:
    token = str(value).strip().upper()
    if token not in _SWEEP_TYPES:
        raise ValueError(f"{name} must be LOG or LINE")
    return token


def _sweep_type_response(value: Any) -> str:
    return _sweep_type(value, "sweep_type response")


def _amplitude_range(value: Any, name: str = "amplitude_range") -> str:
    token = str(value).strip().upper().replace(" ", "")
    try:
        return _AMPLITUDE_RANGES[token]
    except KeyError:
        raise ValueError(
            f"{name} must be one of {', '.join(_AMPLITUDE_RANGE_ENUM)}"
        ) from None


def _bode_capability_fields(capability: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "dg_available": capability["dg_available"],
        "dg_status": capability["dg_status"],
        "bode_option_status": capability["bode_option_status"],
        "capability_source": capability["capability_source"],
        "capability_warning": capability.get("capability_warning"),
    }


def _require_bode_option(session: Any) -> dict[str, Any]:
    """Fail closed unless documented DG/AFG evidence supports Bode access."""

    dg_status = str(session.query(":SYSTem:DGSTatus?")).strip()
    dg_available = _bool_response(dg_status, "DG availability")
    statuses: dict[str, str] = {}
    enabled: dict[str, bool] = {}
    for option in ("AFG100", "AFG50"):
        raw_status = str(
            session.query(f":SYSTem:OPTion:STATus? {option}")
        ).strip()
        statuses[option] = raw_status
        enabled[option] = _bool_response(raw_status, f"{option} option status")
        if enabled[option]:
            break

    if not enabled.get("AFG100", False) and not enabled.get("AFG50", False):
        raw_status = str(session.query(":SYSTem:OPTion:STATus? BND")).strip()
        statuses["BND"] = raw_status
        enabled["BND"] = _bool_response(raw_status, "BND option status")

    if not any(enabled.values()):
        rendered = ", ".join(f"{name}={value}" for name, value in statuses.items())
        raise ValueError(
            "Bode plot is unavailable: SYSTem:DGSTatus? returned "
            f"{dg_status}, and documented AFG100/AFG50/BND option status is "
            f"all-negative ({rendered})"
        )

    positive = ", ".join(name for name, is_enabled in enabled.items() if is_enabled)
    capability: dict[str, Any] = {
        "dg_available": dg_available,
        "dg_status": dg_status,
        "bode_option_status": statuses,
        "capability_source": (
            "DG module status" if dg_available else f"documented option status ({positive})"
        ),
    }
    if not dg_available:
        capability["capability_warning"] = (
            "SYSTem:DGSTatus? reported 0 despite positive documented Bode/generator "
            f"option status ({positive}); access is accepted only with successful "
            "functional Bode readback."
        )
    return capability


def _query_bode(session: Any, amplitude_range: str = "ALL") -> dict[str, Any]:
    amplitude_range = _amplitude_range(amplitude_range)
    prefix = ":BODeplot:"
    result = {
        "enabled": _bool_response(session.query(prefix + "ENABle?"), "Bode enabled"),
        "running": _bool_response(session.query(prefix + "RUNStop?"), "Bode running"),
        "sweep_type": _sweep_type_response(session.query(prefix + "SWEeptype?")),
        "input_channel": _channel_response(session.query(prefix + "REF:IN?"), "input channel"),
        "output_channel": _channel_response(session.query(prefix + "REF:OUT?"), "output channel"),
        "start_hz": _finite(session.query(prefix + "STARt?"), "start_hz response"),
        "stop_hz": _finite(session.query(prefix + "STOP?"), "stop_hz response"),
        "points_per_decade": _integer_response(
            session.query(prefix + "POINts?"), "points_per_decade response"
        ),
        "amplitude_range": amplitude_range,
        "amplitude_v": _finite(
            session.query(prefix + "VOLTage? " + amplitude_range), "amplitude_v response"
        ),
        "gain_enabled": _bool_response(
            session.query(prefix + "GAINcurve:ENABle?"), "gain display"
        ),
        "phase_enabled": _bool_response(
            session.query(prefix + "PHASEcurve:ENABle?"), "phase display"
        ),
    }
    return result


def get_bode(session: Any, *, amplitude_range: Any = "ALL") -> dict[str, Any]:
    """Read the documented Bode-plot configuration and one voltage range."""

    return _query_bode(session, _amplitude_range(amplitude_range))


def _validate_frequency_pair(start_hz: float, stop_hz: float) -> None:
    if not 10 <= start_hz <= 3e6:
        raise ValueError("start_hz must be between 10 Hz and 3 MHz")
    if not 100 <= stop_hz <= 30e6:
        raise ValueError("stop_hz must be between 100 Hz and 30 MHz")
    if start_hz > stop_hz / 10:
        raise ValueError("start_hz must be no greater than stop_hz / 10")


def set_bode(
    session: Any,
    *,
    enabled: Any = None,
    sweep_type: Any = None,
    input_channel: Any = None,
    output_channel: Any = None,
    start_hz: Any = None,
    stop_hz: Any = None,
    amplitude_range: Any = None,
    amplitude_v: Any = None,
    points_per_decade: Any = None,
    gain_enabled: Any = None,
    phase_enabled: Any = None,
) -> dict[str, Any]:
    """Send only explicitly requested Bode fields without readback.

    ``RUNStop`` is intentionally not written here.  Use ``bode_action`` for
    the explicit START/STOP operation; this setter never starts or stops a
    sweep implicitly.
    """

    requested_enabled = None if enabled is None else _bool_input(enabled, "enabled")
    requested_type = None if sweep_type is None else _sweep_type(sweep_type)
    requested_input = None if input_channel is None else _channel(input_channel, "input_channel")
    requested_output = None if output_channel is None else _channel(output_channel, "output_channel")
    requested_start = None if start_hz is None else _finite(start_hz, "start_hz")
    requested_stop = None if stop_hz is None else _finite(stop_hz, "stop_hz")
    requested_range = None if amplitude_range is None else _amplitude_range(amplitude_range)
    requested_amplitude = None if amplitude_v is None else _finite(amplitude_v, "amplitude_v")
    requested_points = None if points_per_decade is None else _finite(points_per_decade, "points_per_decade")
    requested_gain = None if gain_enabled is None else _bool_input(gain_enabled, "gain_enabled")
    requested_phase = None if phase_enabled is None else _bool_input(phase_enabled, "phase_enabled")

    if requested_amplitude is not None and not 0.02 <= requested_amplitude <= 10:
        raise ValueError("amplitude_v must be between 0.02 V and 10 V")
    if requested_points is not None and (
        not requested_points.is_integer() or not 10 <= requested_points <= 100
    ):
        raise ValueError("points_per_decade must be an integer from 10 through 100")

    read_range = requested_range or "ALL"
    if requested_start is not None and not 10 <= requested_start <= 3e6:
        raise ValueError("start_hz must be between 10 Hz and 3 MHz")
    if requested_stop is not None and not 100 <= requested_stop <= 30e6:
        raise ValueError("stop_hz must be between 100 Hz and 30 MHz")
    if requested_start is not None and requested_stop is not None:
        _validate_frequency_pair(requested_start, requested_stop)

    prefix = ":BODeplot:"
    writes: list[str] = []
    if requested_start is not None:
        writes.append(prefix + "STARt " + _scpi_number(requested_start))
    if requested_stop is not None:
        writes.append(prefix + "STOP " + _scpi_number(requested_stop))
    if requested_type is not None:
        writes.append(prefix + "SWEeptype " + requested_type)
    if requested_input is not None:
        writes.append(prefix + "REF:IN CHANnel" + str(requested_input))
    if requested_output is not None:
        writes.append(prefix + "REF:OUT CHANnel" + str(requested_output))
    if requested_points is not None:
        writes.append(prefix + "POINts " + str(int(requested_points)))
    if requested_amplitude is not None:
        writes.append(prefix + "VOLTage " + read_range + "," + _scpi_number(requested_amplitude))
    if requested_gain is not None:
        writes.append(prefix + "GAINcurve:ENABle " + ("1" if requested_gain else "0"))
    if requested_phase is not None:
        writes.append(prefix + "PHASEcurve:ENABle " + ("1" if requested_phase else "0"))
    if requested_enabled is not None:
        writes.append(prefix + "ENABle " + ("1" if requested_enabled else "0"))

    for command in writes:
        session.write(command)
    requested = {
        key: value for key, value in {
            "enabled": requested_enabled, "sweep_type": requested_type, "input_channel": requested_input,
            "output_channel": requested_output, "start_hz": requested_start, "stop_hz": requested_stop,
            "amplitude_range": read_range if requested_amplitude is not None else requested_range,
            "amplitude_v": requested_amplitude, "points_per_decade": int(requested_points) if requested_points is not None else None,
            "gain_enabled": requested_gain, "phase_enabled": requested_phase,
        }.items() if value is not None
    }
    return {"sent": bool(writes), "verified": False, "commands": writes, "requested": requested, **requested}


def bode_action(session: Any, *, action: Any) -> dict[str, Any]:
    """Send one explicit Bode START or STOP command without readback."""

    if not isinstance(action, str) or action.strip().upper() not in {"START", "STOP"}:
        raise ValueError("action must be START or STOP")
    action_name = action.strip().upper()
    desired = action_name == "START"
    command = ":BODeplot:RUNStop " + ("1" if desired else "0")
    session.write(command)
    result = {"sent": True, "verified": False, "commands": [command], "action": action_name}
    if action_name == "START":
        result["warning"] = "START may drive the built-in generator output into the circuit under test."
    return result


_BOOL = {"type": "boolean"}
_CHANNEL = {"type": "integer", "enum": [1, 2, 3, 4]}
_SET_PROPERTIES = {
    "enabled": _BOOL,
    "sweep_type": {"type": "string", "enum": ["LOG", "LINE"]},
    "input_channel": _CHANNEL,
    "output_channel": _CHANNEL,
    "start_hz": {"type": "number", "minimum": 10, "maximum": 3e6},
    "stop_hz": {"type": "number", "minimum": 100, "maximum": 30e6},
    "amplitude_range": {"type": "string", "enum": _AMPLITUDE_RANGE_ENUM},
    "amplitude_v": {"type": "number", "minimum": 0.02, "maximum": 10},
    "points_per_decade": {"type": "integer", "minimum": 10, "maximum": 100},
    "gain_enabled": _BOOL,
    "phase_enabled": _BOOL,
}


TOOLS = [
    ToolSpec(
        name="get_bode",
        description="Read MHO98 Bode configuration and one voltage amplitude range without option preflight.",
        input_schema={
            "type": "object",
            "properties": {"amplitude_range": {"type": "string", "enum": _AMPLITUDE_RANGE_ENUM}},
            "required": [],
            "additionalProperties": False,
        },
        handler=get_bode,
        read_only=True,
        needs_session=True,
    ),
    ToolSpec(
        name="set_bode",
        description="Send selected documented MHO98 Bode commands without a post-command query; never starts or stops a sweep implicitly.",
        input_schema={"type": "object", "properties": _SET_PROPERTIES, "required": [], "additionalProperties": False},
        handler=set_bode,
        read_only=False,
        needs_session=True,
    ),
    ToolSpec(
        name="bode_action",
        description="Explicitly START or STOP the MHO98 Bode sweep. START may drive built-in generator outputs.",
        input_schema={
            "type": "object",
            "properties": {"action": {"type": "string", "enum": ["START", "STOP"]}},
            "required": ["action"],
            "additionalProperties": False,
        },
        handler=bode_action,
        read_only=False,
        needs_session=True,
    ),
]
