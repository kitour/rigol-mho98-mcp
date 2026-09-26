"""MHO98 waveform recording and replay controls."""

from __future__ import annotations

import math
from numbers import Real
from typing import Any

from .api import ToolSpec

_RE = ":RECord:WRECord:"
_RP = ":RECord:WREPlay:"
_CMD = {
    "enabled": _RE + "ENABle",
    "record_operate": _RE + "OPERate",
    "frames": _RE + "FRAMes",
    "record_max": _RE + "FMAX",
    "record_interval": _RE + "FINTerval",
    "prompt": _RE + "PROMpt",
    "current_frame": _RP + "FCURrent",
    "current_time": _RP + "FCURrent:TIME",
    "start_frame": _RP + "FSTart",
    "end_frame": _RP + "FEND",
    "replay_max": _RP + "FMAX",
    "replay_interval": _RP + "FINTerval",
    "mode": _RP + "MODE",
    "direction": _RP + "DIRection",
    "replay_operate": _RP + "OPERate",
}
_MODE_INPUT = {"REP": "REP", "REPEAT": "REP", "SING": "SING", "SINGLE": "SING"}
_MODE_WRITE = {"REP": "REPeat", "SING": "SINGle"}
_DIRECTION_INPUT = {"FORW": "FORW", "FORWARD": "FORW", "BACK": "BACK", "BACKWARD": "BACK"}
_DIRECTION_WRITE = {"FORW": "FORWard", "BACK": "BACKward"}
_ACTION_ALIASES = {
    "RECORD_START": "record_start", "START_RECORD": "record_start", "RECORD_RUN": "record_start",
    "START_RECORDING": "record_start",
    "RECORD_STOP": "record_stop", "STOP_RECORD": "record_stop",
    "STOP_RECORDING": "record_stop",
    "REPLAY_START": "replay_start", "START_REPLAY": "replay_start",
    "START_PLAYBACK": "replay_start",
    "REPLAY_STOP": "replay_stop", "STOP_REPLAY": "replay_stop",
    "STOP_PLAYBACK": "replay_stop",
    "NEXT": "next", "BACK": "back", "PREVIOUS": "back",
    "REPLAY_NEXT": "next", "REPLAY_BACK": "back",
    "MAXFRAMES": "maxframes", "MAX_FRAMES": "maxframes", "RECORD_MAXFRAMES": "maxframes",
    "REPLAY_MAXFRAMES": "maxframes",
    "PLAY_FIRST": "play_first", "PLAY_START": "play_first", "PLAY_START_FRAME": "play_first",
    "PLAY_END": "play_end", "PLAY_END_FRAME": "play_end",
}
_ACTION_COMMAND = {
    "record_start": _CMD["record_operate"] + " RUN",
    "record_stop": _CMD["record_operate"] + " STOP",
    "replay_start": _CMD["replay_operate"] + " RUN",
    "replay_stop": _CMD["replay_operate"] + " STOP",
    "next": _RP + "NEXT", "back": _RP + "BACK",
    "maxframes": _CMD["frames"] + ":MAX",
    "play_first": _RP + "PLAY FFIRst", "play_end": _RP + "PLAY FEND",
}
_ACTION_EFFECT = {
    "record_start": "Starts waveform recording; acquisition and channels are unchanged.",
    "record_stop": "Stops waveform recording; acquisition and channels are unchanged.",
    "replay_start": "Starts waveform replay over the configured frame range.",
    "replay_stop": "Stops waveform replay; recorded frames are retained.",
    "next": "Displays the next recorded frame without starting replay.",
    "back": "Displays the previous recorded frame without starting replay.",
    "maxframes": "Sets the recording frame count to the instrument recording maximum.",
    "play_first": "Displays the configured replay start frame without starting replay.",
    "play_end": "Displays the configured replay end frame without starting replay.",
}


def _bool(value: Any, name: str) -> bool:
    if isinstance(value, bool):
        return value
    token = str(value).strip().upper()
    if token in {"1", "ON", "TRUE"}:
        return True
    if token in {"0", "OFF", "FALSE"}:
        return False
    raise ValueError(f"invalid {name} response from MHO98: {value!r}")


def _input_bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


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


def _int(value: Any, name: str, minimum: int = 1) -> int:
    result = _number(value, name)
    if not result.is_integer() or result < minimum:
        raise ValueError(f"{name} must be an integer from {minimum} upward")
    return int(result)


def _response_int(value: Any, name: str, minimum: int = 0) -> int:
    try:
        return _int(value, name, minimum)
    except ValueError:
        raise ValueError(f"invalid {name} response from MHO98: {value!r}") from None


def _bounded(value: Any, name: str, low: float, high: float) -> float:
    result = _number(value, name)
    if not low <= result <= high:
        raise ValueError(f"{name} must be in the documented range {low:g}..{high:g} seconds")
    return result


def _enum(value: Any, aliases: dict[str, str], name: str) -> str:
    if not isinstance(value, str) or value.strip().upper() not in aliases:
        raise ValueError(f"{name} has an invalid value")
    return aliases[value.strip().upper()]


def _operate(value: Any, name: str) -> str:
    result = str(value).strip().upper()
    if result not in {"RUN", "STOP"}:
        raise ValueError(f"invalid {name} response from MHO98: {value!r}")
    return result


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=0.0)


def _validate_frames(current: int | None, start: int | None, end: int | None, maximum: int) -> None:
    if maximum == 0:
        if any(value is not None for value in (current, start, end)):
            raise ValueError("replay frame settings require at least one recorded frame")
        return
    for name, value in (("current_frame", current), ("start_frame", start), ("end_frame", end)):
        if value is None or not 1 <= value <= maximum:
            raise ValueError(f"{name} must be from 1 through current replay maximum {maximum}")
    if start > end:
        raise ValueError("start_frame must be less than or equal to end_frame")


def _query(session: Any) -> dict[str, Any]:
    record_max = _response_int(session.query(_CMD["record_max"] + "?"), "recording maximum frames", 1)
    replay_max = _response_int(session.query(_CMD["replay_max"] + "?"), "replay maximum frames")
    result = {
        "enabled": _bool(session.query(_CMD["enabled"] + "?"), "recording enabled"),
        "record_operate": _operate(session.query(_CMD["record_operate"] + "?"), "recording operate"),
        "frames": _response_int(session.query(_CMD["frames"] + "?"), "recorded frame count", 1),
        "recording_max_frames": record_max,
        "record_interval_s": _bounded(session.query(_CMD["record_interval"] + "?"), "record interval", 10e-9, 1.0),
        "prompt": _bool(session.query(_CMD["prompt"] + "?"), "record prompt"),
        "replay_max_frames": replay_max,
        "replay_interval_s": _bounded(session.query(_CMD["replay_interval"] + "?"), "replay interval", 1e-3, 1.0),
        "mode": _enum(session.query(_CMD["mode"] + "?"), {"REP": "REP", "REPEAT": "REP", "SING": "SING", "SINGLE": "SING"}, "replay mode"),
        "direction": _enum(session.query(_CMD["direction"] + "?"), {"FORW": "FORW", "FORWARD": "FORW", "BACK": "BACK", "BACKWARD": "BACK"}, "replay direction"),
        "replay_operate": _operate(session.query(_CMD["replay_operate"] + "?"), "replay operate"),
    }
    if replay_max:
        result["current_frame"] = _response_int(session.query(_CMD["current_frame"] + "?"), "current frame", 1)
        result["current_time"] = str(session.query(_CMD["current_time"] + "?")).strip()
        result["start_frame"] = _response_int(session.query(_CMD["start_frame"] + "?"), "replay start frame", 1)
        result["end_frame"] = _response_int(session.query(_CMD["end_frame"] + "?"), "replay end frame", 1)
        _validate_frames(result["current_frame"], result["start_frame"], result["end_frame"], replay_max)
    else:
        result.update(current_frame=None, current_time=None, start_frame=None, end_frame=None)
    return result


def get_recording(session: Any) -> dict[str, Any]:
    """Return recording configuration and applicable replay state."""
    return _query(session)


def _alias(primary: Any, alternate: Any, first: str, second: str) -> Any:
    if primary is not None and alternate is not None:
        raise ValueError(f"provide only one of {first} and {second}")
    return primary if primary is not None else alternate


def set_recording(
    session: Any,
    *,
    enabled: Any = None,
    frames: Any = None,
    record_interval_s: Any = None,
    prompt: Any = None,
    current_frame: Any = None,
    start_frame: Any = None,
    end_frame: Any = None,
    replay_interval_s: Any = None,
    mode: Any = None,
    direction: Any = None,
    recording_interval: Any = None,
    replay_interval: Any = None,
) -> dict[str, Any]:
    """Send only the explicitly requested recording/replay fields."""
    record_interval_s = _alias(record_interval_s, recording_interval, "record_interval_s", "recording_interval")
    replay_interval_s = _alias(replay_interval_s, replay_interval, "replay_interval_s", "replay_interval")
    req = {
        "enabled": None if enabled is None else _input_bool(enabled, "enabled"),
        "frames": None if frames is None else _int(frames, "frames"),
        "record_interval": None if record_interval_s is None else _bounded(record_interval_s, "record_interval_s", 10e-9, 1.0),
        "prompt": None if prompt is None else _input_bool(prompt, "prompt"),
        "current": None if current_frame is None else _int(current_frame, "current_frame"),
        "start": None if start_frame is None else _int(start_frame, "start_frame"),
        "end": None if end_frame is None else _int(end_frame, "end_frame"),
        "replay_interval": None if replay_interval_s is None else _bounded(replay_interval_s, "replay_interval_s", 1e-3, 1.0),
        "mode": None if mode is None else _enum(mode, _MODE_INPUT, "mode"),
        "direction": None if direction is None else _enum(direction, _DIRECTION_INPUT, "direction"),
    }
    if req["start"] is not None and req["end"] is not None and req["start"] > req["end"]:
        raise ValueError("start_frame must be less than or equal to end_frame")

    writes: list[str] = []
    if req["frames"] is not None:
        writes.append(f"{_CMD['frames']} {req['frames']}")
    if req["record_interval"] is not None:
        writes.append(f"{_CMD['record_interval']} {req['record_interval']:.15g}")
    if req["prompt"] is not None:
        writes.append(f"{_CMD['prompt']} {'1' if req['prompt'] else '0'}")
    if req["start"] is not None:
        writes.append(f"{_CMD['start_frame']} {req['start']}")
    if req["end"] is not None:
        writes.append(f"{_CMD['end_frame']} {req['end']}")
    if req["current"] is not None:
        writes.append(f"{_CMD['current_frame']} {req['current']}")
    if req["replay_interval"] is not None:
        writes.append(f"{_CMD['replay_interval']} {req['replay_interval']:.15g}")
    if req["mode"] is not None:
        writes.append(f"{_CMD['mode']} {_MODE_WRITE[req['mode']]}")
    if req["direction"] is not None:
        writes.append(f"{_CMD['direction']} {_DIRECTION_WRITE[req['direction']]}")
    if req["enabled"] is not None:
        writes.append(f"{_CMD['enabled']} {'1' if req['enabled'] else '0'}")
    for command in writes:
        session.write(command)
    return {
        "requested": {key: value for key, value in req.items() if value is not None},
        "sent": bool(writes),
        "verified": False,
        "commands": writes,
    }


def recording_action(session: Any, *, action: Any) -> dict[str, Any]:
    """Send one explicit record/replay action without preflight or readback."""
    if not isinstance(action, str):
        raise ValueError("action must be an explicit record/replay action")
    normalized = _ACTION_ALIASES.get(action.strip().upper().replace("-", "_"))
    if normalized is None:
        raise ValueError("unknown record/replay action")
    command = _ACTION_COMMAND[normalized]
    session.write(command)
    return {"action": normalized, "command": command, "effect": _ACTION_EFFECT[normalized], "sent": True, "verified": False, "commands": [command]}


_SET_PROPERTIES = {
    "enabled": {"type": "boolean"}, "frames": {"type": "integer", "minimum": 1},
    "record_interval_s": {"type": "number", "minimum": 1e-8, "maximum": 1.0},
    "prompt": {"type": "boolean"}, "current_frame": {"type": "integer", "minimum": 1},
    "start_frame": {"type": "integer", "minimum": 1}, "end_frame": {"type": "integer", "minimum": 1},
    "replay_interval_s": {"type": "number", "minimum": 1e-3, "maximum": 1.0},
    "mode": {"type": "string", "enum": ["REP", "SING"]}, "direction": {"type": "string", "enum": ["FORW", "BACK"]},
}

TOOLS = [
    ToolSpec("get_recording", "Read documented MHO98 waveform recording and applicable replay state.", {"type": "object", "properties": {}, "required": [], "additionalProperties": False}, get_recording, read_only=True, needs_session=True),
    ToolSpec("set_recording", "Send documented MHO98 recording/replay fields only; omitted fields are untouched and operate state is not queried.", {"type": "object", "properties": _SET_PROPERTIES, "required": [], "additionalProperties": False}, set_recording, read_only=False, needs_session=True),
    ToolSpec("recording_action", "Explicitly start/stop record or replay, step frames, select maximum frames, or jump to replay bounds.", {"type": "object", "properties": {"action": {"type": "string", "enum": sorted(_ACTION_COMMAND)}}, "required": ["action"], "additionalProperties": False}, recording_action, read_only=False, needs_session=True),
]
