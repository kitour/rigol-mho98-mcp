"""Instrument-side, non-image save/load controls for the MHO98.

Setter and save/load inputs are paths understood by the instrument (``C:/``
and ``D:/``), not paths on the host running MCP.  Storage readback is returned
in the instrument's native spelling, which may use a different path form.
Host transfers remain the job of ``download_binary``, ``restore_setup``, and
the waveform export tools.
"""

from __future__ import annotations

import re
from typing import Any

from .api import ToolSpec


_KINDS = frozenset({"setup", "waveform", "memory_waveform", "mask"})
_SAVE_ROOTS = frozenset({"C", "D"})
_LOAD_ROOTS = {
    "setup": frozenset({"C", "D"}),
    # The guide documents E:/ as an additional mask-load location.
    "mask": frozenset({"C", "D", "E"}),
}
_SUFFIXES = {
    "setup": frozenset({".stp"}),
    "waveform": frozenset({".bin", ".csv"}),
    "memory_waveform": frozenset({".bin", ".csv", ".wfm"}),
    "mask": frozenset({".pf"}),
}
_SAVE_COMMANDS = {
    "setup": ":SAVE:SETup",
    "waveform": ":SAVE:WAVeform",
    "memory_waveform": ":SAVE:MEMory:WAVeform",
    "mask": ":SAVE:MASK",
}
_LOAD_COMMANDS = {"setup": ":LOAD:SETup", "mask": ":LOAD:MASK"}
_COMPONENT = re.compile(r"^[A-Za-z0-9_.-]+$")
_ROOTED_PATH = re.compile(r"^([A-Za-z]):/(.*)$")


def _ascii_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty ASCII string")
    try:
        value.encode("ascii")
    except UnicodeEncodeError:
        raise ValueError(f"{name} must contain ASCII characters only") from None
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in value):
        raise ValueError(f"{name} must not contain control characters")
    return value


def _instrument_path(value: Any, name: str, roots: frozenset[str], *, file: bool) -> str:
    path = _ascii_text(value, name)
    match = _ROOTED_PATH.fullmatch(path)
    if match is None or match.group(1).upper() not in roots:
        roots_text = ", ".join(f"{root}:/" for root in sorted(roots))
        raise ValueError(f"{name} must be an instrument path below {roots_text}")
    remainder = match.group(2)
    if file and not remainder:
        raise ValueError(f"{name} must use slash-separated instrument path components")
    if remainder.startswith("/") or remainder.endswith("/"):
        raise ValueError(f"{name} must use slash-separated instrument path components")
    if not remainder:
        return path
    components = remainder.split("/")
    if any(component in {"", ".", ".."} for component in components):
        raise ValueError(f"{name} must not contain empty, '.', or '..' path components")
    if any(_COMPONENT.fullmatch(component) is None for component in components):
        raise ValueError(
            f"{name} contains an unsupported character; use ASCII letters, numbers, '_', '-', and '.'"
        )
    if file:
        filename = components[-1]
        if len(filename) > 26:
            raise ValueError(f"{name} filename must be at most 26 characters")
    return path


def _pathname(value: Any) -> str:
    """Validate the directory used by :SAVE:PATHname."""

    return _instrument_path(value, "pathname", _SAVE_ROOTS, file=False)


def _prefix(value: Any) -> str:
    prefix = _ascii_text(value, "prefix")
    if len(prefix) > 16:
        raise ValueError("prefix must be at most 16 characters")
    if "." in prefix or "/" in prefix or "\\" in prefix:
        raise ValueError("prefix must not contain a suffix or path separator")
    if _COMPONENT.fullmatch(prefix) is None:
        raise ValueError(
            "prefix contains an unsupported character; use ASCII letters, numbers, '_', and '-'")
    return prefix


def _kind(value: Any) -> str:
    if not isinstance(value, str) or value.strip().lower() not in _KINDS:
        raise ValueError("kind must be setup, waveform, memory_waveform, or mask")
    return value.strip().lower()


def _alias_kind(kind: Any, file_type: Any) -> str:
    if kind is not None and file_type is not None:
        raise ValueError("provide only one of kind and file_type")
    selected = kind if kind is not None else file_type
    return _kind(selected)


def _file_path(value: Any, kind: str, *, load: bool) -> str:
    roots = _LOAD_ROOTS[kind] if load else _SAVE_ROOTS
    path = _instrument_path(value, "path", roots, file=True)
    filename = path.rsplit("/", 1)[-1]
    actual_suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if actual_suffix not in _SUFFIXES[kind]:
        supported = ", ".join(sorted(_SUFFIXES[kind]))
        raise ValueError(f"{kind} path must end with one of: {supported}")
    return path


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


def _status(session: Any) -> tuple[int, str]:
    raw = str(session.query(":SAVE:STATus?")).strip().upper()
    if raw not in {"0", "1"}:
        raise ValueError(f"invalid save status response from MHO98: {raw!r}")
    code = int(raw)
    return code, "complete" if code else "pending"


def get_storage(session: Any) -> dict[str, Any]:
    """Read save path, filename prefix, overwrite policy, and save status."""

    pathname = str(session.query(":SAVE:PATHname?")).strip()
    prefix = str(session.query(":SAVE:PREFix?")).strip()
    overlap = _bool_response(session.query(":SAVE:OVERlap?"), "overwrite policy")
    status_code, status = _status(session)
    # Readback is native instrument state, not setter input.  In particular,
    # some firmware returns paths such as /data/UserData, which must not be
    # rejected or translated to the C:/ and D:/ write-path forms.
    return {
        "pathname": pathname,
        "prefix": prefix,
        "overwrite": overlap,
        "status": status,
        "status_code": status_code,
    }


def set_storage(
    session: Any,
    *,
    pathname: Any = None,
    prefix: Any = None,
    overwrite: Any = None,
) -> dict[str, Any]:
    """Send only explicitly requested instrument save settings."""

    if pathname is None and prefix is None and overwrite is None:
        raise ValueError("set_storage requires pathname, prefix, or overwrite")
    requested_pathname = None if pathname is None else _pathname(pathname)
    requested_prefix = None if prefix is None else _prefix(prefix)
    requested_overwrite = None if overwrite is None else _bool_input(overwrite, "overwrite")

    writes: list[str] = []
    if requested_pathname is not None:
        writes.append(f":SAVE:PATHname {requested_pathname}")
    if requested_prefix is not None:
        writes.append(f":SAVE:PREFix {requested_prefix}")
    if requested_overwrite is not None:
        writes.append(f":SAVE:OVERlap {1 if requested_overwrite else 0}")
    for command in writes:
        session.write(command)
    requested = {
        key: value for key, value in {
            "pathname": requested_pathname, "prefix": requested_prefix, "overwrite": requested_overwrite,
        }.items() if value is not None
    }
    return {"sent": bool(writes), "verified": False, "commands": writes, "requested": requested, **requested}


def save_file(
    session: Any,
    kind: Any = None,
    path: Any = None,
    *,
    overwrite: Any = None,
    file_type: Any = None,
) -> dict[str, Any]:
    """Send one documented non-image instrument-side save command."""

    selected = _alias_kind(kind, file_type)
    instrument_path = _file_path(path, selected, load=False)
    requested_overwrite = None if overwrite is None else _bool_input(overwrite, "overwrite")
    commands: list[str] = []
    if requested_overwrite is not None:
        commands.append(f":SAVE:OVERlap {1 if requested_overwrite else 0}")
    commands.append(f"{_SAVE_COMMANDS[selected]} {instrument_path}")
    for command in commands:
        session.write(command)
    requested = {"kind": selected, "path": instrument_path}
    if requested_overwrite is not None:
        requested["overwrite"] = requested_overwrite
    return {"sent": True, "verified": False, "commands": commands, "requested": requested, **requested}


def load_file(
    session: Any,
    kind: Any = None,
    path: Any = None,
    *,
    file_type: Any = None,
) -> dict[str, Any]:
    """Explicitly load a setup or mask from instrument storage.

    The corresponding instrument setup or mask is intentionally replaced by
    the load.  No automatic full reset or host-file upload is performed.
    """

    selected = _alias_kind(kind, file_type)
    if selected not in _LOAD_COMMANDS:
        raise ValueError("load_file supports only setup and mask")
    instrument_path = _file_path(path, selected, load=True)
    command = f"{_LOAD_COMMANDS[selected]} {instrument_path}"
    session.write(command)
    requested = {"kind": selected, "path": instrument_path}
    return {"sent": True, "verified": False, "commands": [command], "requested": requested, **requested}


_STORAGE_PROPERTIES = {
    "pathname": {"type": "string"},
    "prefix": {"type": "string", "maxLength": 16},
    "overwrite": {"type": "boolean"},
}
_FILE_KIND = {"type": "string", "enum": sorted(_KINDS)}


TOOLS = [
    ToolSpec(
        name="get_storage",
        description="Read MHO98 instrument save pathname, filename prefix, overwrite policy, and immediate save status.",
        input_schema={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        handler=get_storage,
        read_only=True,
        needs_session=True,
    ),
    ToolSpec(
        name="set_storage",
        description="Set MHO98 instrument save pathname, prefix, and explicit overlap policy; host paths and SMB are unsupported.",
        input_schema={"type": "object", "properties": _STORAGE_PROPERTIES, "required": [], "additionalProperties": False},
        handler=set_storage,
        read_only=False,
        needs_session=True,
    ),
    ToolSpec(
        name="save_file",
        description="Send a MHO98 setup, screen waveform, memory waveform, or mask save command to validated instrument C:/ or D:/ storage without querying status.",
        input_schema={
            "type": "object",
            "properties": {
                "kind": _FILE_KIND,
                "path": {"type": "string"},
                "overwrite": {"type": ["boolean", "null"]},
            },
            "required": ["kind", "path"],
            "additionalProperties": False,
        },
        handler=save_file,
        read_only=False,
        needs_session=True,
    ),
    ToolSpec(
        name="load_file",
        description="Send an explicit load command for a validated MHO98 setup or mask; resulting state is not verified and no full reset is performed.",
        input_schema={
            "type": "object",
            "properties": {"kind": {"type": "string", "enum": ["setup", "mask"]}, "path": {"type": "string"}},
            "required": ["kind", "path"],
            "additionalProperties": False,
        },
        handler=load_file,
        read_only=False,
        needs_session=True,
    ),
]
