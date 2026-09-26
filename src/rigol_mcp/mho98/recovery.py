"""Non-destructive MHO98 reconnect support for the server."""

from __future__ import annotations

import os
from pathlib import Path
import threading
from typing import Any, TYPE_CHECKING

from .api import ToolSpec

if TYPE_CHECKING:
    from .session import Session


_TARGET_USB_SERIAL = "MHO9A274501253"
_LAST_RECOVERY_LOCK = threading.Lock()
_LAST_RECOVERY: dict[str, Any] = {
    "attempted": False,
    "recovered": False,
    "stage": "not_attempted",
    "prior_command_state": "unknown",
}


def _set_last_recovery(value: dict[str, Any]) -> dict[str, Any]:
    value = dict(value)
    value.setdefault("prior_command_state", "unknown")
    with _LAST_RECOVERY_LOCK:
        _LAST_RECOVERY.clear()
        _LAST_RECOVERY.update(value)
    return value


def last_recovery() -> dict[str, Any]:
    with _LAST_RECOVERY_LOCK:
        return dict(_LAST_RECOVERY)


def prepare_libusb_backend() -> dict[str, Any] | None:
    """Preload and verify an explicitly selected libusb before legacy import."""

    configured = os.environ.get("RIGOL_LIBUSB_LIBRARY", "").strip()
    if not configured:
        return None
    path = Path(configured).expanduser()
    if not path.is_absolute():
        raise RuntimeError("RIGOL_LIBUSB_LIBRARY must be an absolute path")
    path = path.resolve()
    if not path.is_file():
        raise RuntimeError(f"RIGOL_LIBUSB_LIBRARY does not exist: {path}")

    import usb.backend.libusb1 as libusb1

    backend = libusb1.get_backend(find_library=lambda _name: str(path))
    if backend is None:
        raise RuntimeError(f"failed to load RIGOL_LIBUSB_LIBRARY: {path}")
    loaded_name = getattr(getattr(backend, "lib", None), "_name", None)
    if not loaded_name:
        raise RuntimeError("loaded libusb backend does not expose its library path")
    loaded = Path(str(loaded_name)).expanduser().resolve()
    try:
        same = loaded.samefile(path)
    except OSError:
        same = loaded == path
    if not same:
        raise RuntimeError(
            "libusb was already loaded from a different path; restart the MHO98 "
            f"server to use RIGOL_LIBUSB_LIBRARY (loaded={loaded}, requested={path})"
        )
    return {"configured": str(path), "loaded": str(loaded)}


def _target_idn(identity: str) -> bool:
    fields = [part.strip() for part in identity.split(",")]
    return (
        len(fields) >= 3
        and fields[1].upper() == "MHO98"
        and fields[2] == _TARGET_USB_SERIAL
    )


def _fresh_idn(template: Session) -> tuple[str | None, str | None]:
    """Open a new session and verify the known USB target's IDN."""

    from .session import Session

    probe = Session(
        output_dir=template.output_dir,
        lock_path=template.lock_path,
        timeout_ms=template.timeout_ms,
    )
    try:
        identity = probe.idn()
        if not _target_idn(identity):
            return None, f"target IDN mismatch: {identity or '(empty)'}"
        if probe._is_usb_resource(probe.transport):
            resource_name = str(
                getattr(probe.transport, "resource_name", "")
                or getattr(probe.transport, "_resource_name", "")
            )
            fields = resource_name.split("::")
            if len(fields) >= 4 and fields[3] != _TARGET_USB_SERIAL:
                return None, f"USB resource serial mismatch: {fields[3]}"
        return identity, None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    finally:
        probe.close()


def recover_connection(session: Session, **_: Any) -> dict[str, Any]:
    """Open a fresh connection and verify only the exact MHO98 target IDN.

    This function never resets a device, hub port, or power state and never
    replays the command associated with an earlier transport fault.
    """

    identity, error = _fresh_idn(session)
    if identity is not None:
        return _set_last_recovery(
            {
                "attempted": True,
                "recovered": True,
                "stage": "fresh_open",
                "identity": identity,
            }
        )

    stage = (
        "target_idn_mismatch"
        if error and error.startswith("target IDN")
        else "device_absent"
    )
    return _set_last_recovery(
        {
            "attempted": True,
            "recovered": False,
            "stage": stage,
            "error": error,
        }
    )


TOOLS = [
    ToolSpec(
        name="recover_connection",
        description=(
            "Open a fresh MHO98 connection and verify the exact target IDN. "
            "Never resets USB devices, hubs, or power and never replays the "
            "command that failed; its execution state remains unknown."
        ),
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=recover_connection,
        read_only=False,
        needs_session=True,
    )
]
