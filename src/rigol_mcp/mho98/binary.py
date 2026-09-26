"""Safe downloads for MHO98 binary query responses."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .api import ToolSpec


DEFAULT_MAX_BYTES = 16 * 1024 * 1024
MAX_ALLOWED_BYTES = 64 * 1024 * 1024
_KINDS = frozenset({"bus_data", "saved_image", "setup"})


def _kind(value: Any) -> str:
    if not isinstance(value, str) or value.strip().lower() not in _KINDS:
        raise ValueError("kind must be bus_data, saved_image, or setup")
    return value.strip().lower()


def _bus(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("bus must be an integer from 1 through 4")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError("bus must be an integer from 1 through 4") from None
    if number not in {1, 2, 3, 4} or str(value).strip() not in {str(number), f"{number}.0"}:
        raise ValueError("bus must be an integer from 1 through 4")
    return number


def _max_bytes(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("max_bytes must be a positive integer up to 64 MiB")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError("max_bytes must be a positive integer up to 64 MiB") from None
    if number <= 0 or number > MAX_ALLOWED_BYTES or str(value).strip() not in {str(number), f"{number}.0"}:
        raise ValueError("max_bytes must be a positive integer up to 64 MiB")
    return number


def _image_suffix(payload: bytes) -> str:
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if payload.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if payload.startswith(b"BM"):
        return ".bmp"
    return ".bin"


def _suffix(kind: str, payload: bytes) -> str:
    if kind == "bus_data":
        return ".bin"
    if kind == "setup":
        return ".stp"
    return _image_suffix(payload)


def _path(session: Any, filename: Any, suffix: str, kind: str) -> Path:
    base = Path(session.output_dir).expanduser().resolve()
    base.mkdir(parents=True, exist_ok=True)
    if filename is None:
        name = {"bus_data": "bus", "saved_image": "saved-image", "setup": "setup"}[kind]
        target = base / f"{name}{suffix}"
        if target.exists():
            target = base / f"{name}-{hashlib.sha256(str(target).encode()).hexdigest()[:12]}{suffix}"
    else:
        if not isinstance(filename, str) or not filename.strip():
            raise ValueError("filename must be a non-empty path relative to output_dir")
        provided = Path(filename)
        if provided.is_absolute():
            raise ValueError("filename must be inside output_dir")
        target = (base / provided).resolve()
        if target.suffix.lower() not in {".bin", ".stp", ".png", ".jpg", ".jpeg", ".bmp"}:
            target = target.with_name(target.name + suffix)
    try:
        target.relative_to(base)
    except ValueError:
        raise ValueError("filename must be inside output_dir") from None
    if target.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _validate_filename_scope(session: Any, filename: Any) -> None:
    if filename is None:
        return
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("filename must be a non-empty path relative to output_dir")
    supplied = Path(filename)
    if supplied.is_absolute():
        raise ValueError("filename must be inside output_dir")
    base = Path(session.output_dir).expanduser().resolve()
    target = (base / supplied).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise ValueError("filename must be inside output_dir") from None


def download_binary(
    session: Any,
    kind: str,
    bus: int = 1,
    filename: str | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> dict[str, Any]:
    """Download one documented binary response to a new file below output_dir."""
    selected = _kind(kind)
    selected_bus = _bus(bus)
    limit = _max_bytes(max_bytes)
    _validate_filename_scope(session, filename)
    commands = {
        "bus_data": f":BUS{selected_bus}:DATA?",
        "saved_image": ":SAVE:IMAGe:DATA?",
        "setup": ":SYSTem:SETup?",
    }
    payload = session.binary_query(commands[selected], max_bytes=limit)
    if not isinstance(payload, (bytes, bytearray)):
        raise ValueError("binary query returned a non-bytes payload")
    payload = bytes(payload)
    if len(payload) > limit:
        raise ValueError(f"binary response is {len(payload)} bytes, above max_bytes={limit}")
    suffix = _suffix(selected, payload)
    target = _path(session, filename, suffix, selected)
    created = False
    try:
        with target.open("xb") as handle:
            created = True
            handle.write(payload)
    except Exception:
        if created and target.exists():
            target.unlink()
        raise
    return {
        "reply_kind": selected,
        "path": str(target),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _setup_path(session: Any, filename: Any) -> Path:
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("filename must be a non-empty .stp path relative to output_dir")
    supplied = Path(filename)
    if supplied.is_absolute() or supplied.suffix.lower() != ".stp":
        raise ValueError("restore_setup requires an existing .stp file inside output_dir")
    base = Path(session.output_dir).expanduser().resolve()
    candidate = base / supplied
    if candidate.is_symlink():
        raise ValueError("restore_setup refuses symlink paths")
    path = candidate.resolve()
    try:
        path.relative_to(base)
    except ValueError:
        raise ValueError("filename must be inside output_dir") from None
    if not path.exists() or not path.is_file() or path.is_symlink():
        raise ValueError("restore_setup requires an existing regular .stp file")
    return path


def restore_setup(session: Any, filename: str) -> dict[str, Any]:
    """Replace the instrument setup from one bounded local .stp binary file."""
    path = _setup_path(session, filename)
    size = path.stat().st_size
    if size <= 0:
        raise ValueError("restore_setup refuses an empty setup file")
    if size > MAX_ALLOWED_BYTES:
        raise ValueError("setup file exceeds the 64 MiB upload limit")
    payload = path.read_bytes()
    if not payload:
        raise ValueError("restore_setup refuses an empty setup file")
    if len(payload) > MAX_ALLOWED_BYTES:
        raise ValueError("setup file exceeds the 64 MiB upload limit")
    session.write_binary(":SYSTem:SETup", payload, max_bytes=MAX_ALLOWED_BYTES)
    return {
        "sent": True,
        "verified": False,
        "source": str(path),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


TOOLS = [
    ToolSpec(
        name="download_binary",
        description="Download MHO98 BUS data, saved image data, or setup data into a new output file.",
        input_schema={
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["bus_data", "saved_image", "setup"]},
                "bus": {"type": "integer", "minimum": 1, "maximum": 4},
                "filename": {"type": ["string", "null"]},
                "max_bytes": {"type": "integer", "minimum": 1, "maximum": MAX_ALLOWED_BYTES},
            },
            "required": ["kind"],
        },
        handler=download_binary,
        read_only=True,
        needs_session=True,
    ),
    ToolSpec(
        name="restore_setup",
        description="Replace the complete MHO98 instrument setup from an existing bounded .stp file inside output_dir.",
        input_schema={
            "type": "object",
            "properties": {"filename": {"type": "string"}},
            "required": ["filename"],
        },
        handler=restore_setup,
        read_only=False,
        needs_session=True,
    ),
]
