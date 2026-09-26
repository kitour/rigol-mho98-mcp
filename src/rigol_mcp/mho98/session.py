"""MHO98 transport/session boundary.

This module owns connection lifetime and IEEE-488.2 definite-length reads.
Identity and SCPI error queries are explicit diagnostic operations only.  It intentionally does
not call the legacy ``get_scope`` helper because that helper clears instrument
state on connection setup.
"""

from __future__ import annotations

import contextlib
import fcntl
import math
import os
from pathlib import Path
import tempfile
import threading
from typing import Any, Iterator

import pyvisa


DEFAULT_TIMEOUT_MS: int | None = None
DEFAULT_BINARY_MAX_BYTES = 64 * 1024 * 1024
DEFAULT_TEXT_MAX_BYTES = 4 * 1024 * 1024
_IEEE_BLOCK_OVERHEAD = 2 + 9 + 2  # '#', digit count, up to 9 length digits, CRLF
_PROCESS_LOCK = threading.RLock()


class MHO98IdentityError(RuntimeError):
    """Raised when the connected instrument is not an MHO98."""


class SCPIError(RuntimeError):
    """Raised after a write when the instrument reports a SCPI error."""


class BinaryResponseError(ValueError):
    """Raised when an IEEE-488.2 response is malformed, oversized, or truncated."""


class _BinaryTransportReadError(BinaryResponseError):
    """Raised when the transport, rather than IEEE framing, failed."""


class _MessageResponseError(RuntimeError):
    """Raised when a bounded non-binary message cannot be received safely."""


_TRANSPORT_ERRORS = (
    pyvisa.errors.VisaIOError,
    OSError,
    TimeoutError,
    EOFError,
    UnicodeError,
)


def _configured_output_dir(value: str | os.PathLike[str] | None) -> Path:
    if value is not None:
        return Path(value).expanduser().resolve()
    configured = os.environ.get("RIGOL_OUTPUT_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    # The environment variable is the deployment contract.  This fallback is
    # deterministic for an installed checkout and is only used in development.
    return Path(__file__).resolve().parents[3] / "output"


def _is_mho98(identity: str) -> bool:
    fields = [part.strip().upper() for part in identity.split(",")]
    return len(fields) >= 2 and fields[1] == "MHO98"


class Session:
    """One bounded MHO98 instrument session.

    ``transport`` is an optional pyvisa-like resource used by tests and by
    callers that already own a connection.  Production sessions open lazily,
    keeping instrument access out of MCP discovery and schema requests.
    """

    def __init__(
        self,
        transport: Any | None = None,
        *,
        output_dir: str | os.PathLike[str] | None = None,
        lock_path: str | os.PathLike[str] | None = None,
        timeout_ms: int | None = DEFAULT_TIMEOUT_MS,
        resource_manager: Any | None = None,
    ) -> None:
        if timeout_ms is not None and (
            isinstance(timeout_ms, bool)
            or not isinstance(timeout_ms, int)
            or timeout_ms <= 0
            or timeout_ms >= pyvisa.constants.VI_TMO_INFINITE
        ):
            raise ValueError(
                "timeout_ms must be None or a positive finite integer below "
                f"{pyvisa.constants.VI_TMO_INFINITE} ms"
            )
        self.output_dir = _configured_output_dir(output_dir)
        self.lock_path = Path(
            lock_path
            if lock_path is not None
            else os.environ.get(
                "RIGOL_MHO98_LOCK",
                str(Path(tempfile.gettempdir()) / "rigol-mcp-mho98.lock"),
            )
        ).expanduser().resolve()
        self.timeout_ms = timeout_ms
        self._resource = transport
        self._resource_manager = resource_manager
        self._identity: str | None = None
        self._lock_handle: Any | None = None
        self._faulted = False
        self._closed = False

        if transport is not None:
            self._configure_resource(transport)

    @property
    def transport(self) -> Any | None:
        """The underlying resource, primarily useful for diagnostics/tests."""

        return self._resource

    @property
    def faulted(self) -> bool:
        """True after a communication fault invalidated this session."""

        return self._faulted

    @property
    def closed(self) -> bool:
        """True after explicit/session-lifecycle close."""

        return self._closed

    @property
    def is_healthy(self) -> bool:
        """True only while this session is neither faulted nor closed."""

        return not self._faulted and not self._closed

    @contextlib.contextmanager
    def transaction(self) -> Iterator["Session"]:
        """Acquire the process and interprocess instrument transaction locks."""

        with _PROCESS_LOCK:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            with self.lock_path.open("a+") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                self._lock_handle = handle
                try:
                    yield self
                finally:
                    self._lock_handle = None
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _configure_resource(self, resource: Any) -> None:
        # ``None`` is PyVISA's portable spelling for VI_TMO_INFINITE.  Verify
        # the read-back: silently accepting a failed timeout assignment would
        # make a real transport unexpectedly finite (or immediate).
        requested_timeout = self.timeout_ms
        try:
            resource.timeout = requested_timeout
            actual_timeout = resource.timeout
        except Exception as exc:
            raise RuntimeError(
                f"failed to configure MHO98 resource timeout={requested_timeout!r}"
            ) from exc

        if requested_timeout is None:
            valid_timeout = actual_timeout is None or (
                isinstance(actual_timeout, (int, float))
                and math.isinf(actual_timeout)
            ) or actual_timeout == pyvisa.constants.VI_TMO_INFINITE
        else:
            valid_timeout = actual_timeout == requested_timeout
        if not valid_timeout:
            raise RuntimeError(
                "MHO98 resource rejected timeout configuration: "
                f"requested={requested_timeout!r}, actual={actual_timeout!r}"
            )

        # Terminations are convenience settings.  Some VISA-like test doubles
        # and alternate resources do not expose them, so retain best effort for
        # these non-safety-critical attributes.
        for attr, value in (("read_termination", "\n"), ("write_termination", "\n")):
            try:
                setattr(resource, attr, value)
            except Exception:
                pass

    @contextlib.contextmanager
    def _usb_io_timeout(self, resource: Any) -> Iterator[None]:
        """Use libusb's infinite timeout for one default-policy USB transfer.

        PyVISA-py represents VISA infinity as ``2**32 - 1`` before passing it
        to PyUSB.  Its libusb backend treats zero as infinite.  Change only the
        live pyvisa-py interface for the duration of this I/O, then restore the
        VISA value so ``resource.timeout`` continues to report infinity.  VISA
        backends without this pyvisa-py interface retain their own infinite
        timeout implementation.
        """

        if self.timeout_ms is not None or not self._is_usb_resource(resource):
            yield
            return

        try:
            visa_session = resource.visalib.sessions[resource.session]
            interface = visa_session.interface
            previous_timeout = interface.timeout
        except (AttributeError, KeyError, TypeError):
            yield
            return

        try:
            interface.timeout = 0
            if interface.timeout != 0:
                raise RuntimeError(
                    "pyvisa-py USB interface did not accept libusb infinite timeout=0"
                )
            yield
        finally:
            try:
                interface.timeout = previous_timeout
            except Exception as exc:
                raise RuntimeError(
                    "failed to restore pyvisa-py USB interface timeout after I/O"
                ) from exc

    def _open(self) -> Any:
        if self._faulted:
            raise RuntimeError("MHO98 session is faulted; create a new session")
        if self._closed:
            raise RuntimeError("MHO98 session is closed")
        if self._resource is not None:
            return self._resource

        # Import lazily: MCP discovery and no-session tools must work without
        # importing or probing VISA/USB.
        from .recovery import prepare_libusb_backend

        prepare_libusb_backend()
        from rigol_mcp import scope as legacy_scope

        try:
            if legacy_scope._usb_preferred():
                self._resource_manager, self._resource = legacy_scope._open_usb_scope()
            else:
                ip = os.environ.get("RIGOL_IP", "").strip()
                if not ip:
                    raise RuntimeError(
                        "Set RIGOL_USB=1 for USB or RIGOL_IP for an MHO98 LAN session"
                    )
                self._resource_manager = pyvisa.ResourceManager("@py")
                self._resource = self._resource_manager.open_resource(
                    f"TCPIP0::{ip}::5555::SOCKET"
                )
            self._configure_resource(self._resource)
            return self._resource
        except Exception:
            self._close_transport()
            raise

    def _close_transport(self) -> None:
        resource, manager = self._resource, self._resource_manager
        self._resource = None
        self._resource_manager = None
        self._identity = None
        for item in (resource, manager):
            if item is None:
                continue
            try:
                item.close()
            except Exception:
                pass

    def close(self) -> None:
        """Close the resource and VISA manager, ignoring cleanup failures."""

        self._closed = True
        self._close_transport()

    def __enter__(self) -> "Session":
        self._open()
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _transport_fault(self, exc: BaseException) -> None:
        # Do not retry: a write may have executed before the link failed, and a
        # partial binary response cannot safely be reused.
        self._faulted = True
        self._close_transport()
        if isinstance(exc, Exception):
            raise exc
        raise RuntimeError("MHO98 transport failed") from exc

    def _raw_query(self, command: str) -> str:
        resource = self._open()
        try:
            with self._usb_io_timeout(resource):
                if self._is_usb_resource(resource):
                    resource.write(command)
                    response = self._read_usb_text_message(
                        resource,
                        max_bytes=DEFAULT_TEXT_MAX_BYTES,
                    )
                else:
                    response = resource.query(command)
            if isinstance(response, bytes):
                response = response.decode("ascii")
            return str(response).strip()
        except _MessageResponseError as exc:
            self._transport_fault(exc)
        except _TRANSPORT_ERRORS as exc:
            self._transport_fault(exc)

    def idn(self) -> str:
        """Query and validate ``*IDN?`` without sending any setup command."""

        if self._identity is not None:
            return self._identity
        identity = self._raw_query("*IDN?")
        if not _is_mho98(identity):
            self._closed = True
            self._close_transport()
            raise MHO98IdentityError(
                f"MHO98 session refused instrument identity: {identity or '(empty)'}"
            )
        self._identity = identity
        return identity

    def _require_identity(self) -> None:
        self.idn()

    def query_error(self) -> str | None:
        """Drain the SCPI error queue and return its first non-zero response."""

        first_error: str | None = None
        for _ in range(16):
            response = self._raw_query(":SYSTem:ERRor?")
            if response == "0" or response.startswith("0,"):
                return first_error
            if first_error is None:
                first_error = response
        return first_error

    # Short alias for callers using the common SCPI vocabulary.
    error = query_error

    def query(self, command: str) -> str:
        """Run exactly the requested text query, without diagnostic queries."""

        if not isinstance(command, str) or not command.strip():
            raise ValueError("command must be a non-empty string")
        return self._raw_query(command)

    def write(self, command: str) -> None:
        """Send one command; transport failures propagate, with no SCPI readback."""

        if not isinstance(command, str) or not command.strip():
            raise ValueError("command must be a non-empty string")
        resource = self._open()
        try:
            with self._usb_io_timeout(resource):
                resource.write(command)
        except _TRANSPORT_ERRORS as exc:
            self._transport_fault(exc)

    @staticmethod
    def _is_usb_resource(resource: Any) -> bool:
        """Return whether a VISA resource is USB, without assuming one backend."""

        try:
            if resource.interface_type == pyvisa.constants.InterfaceType.usb:
                return True
        except Exception:
            pass
        for attr in ("resource_name", "_resource_name"):
            try:
                name = str(getattr(resource, attr, "")).upper()
            except Exception:
                continue
            if name.startswith("USB"):
                return True
        return False

    @staticmethod
    def _parse_block(raw: bytes, max_bytes: int) -> bytes:
        if len(raw) < 2 or raw[:1] != b"#" or raw[1:2] not in b"123456789":
            raise BinaryResponseError(f"invalid IEEE-488.2 block header: {raw[:8]!r}")
        digits = int(raw[1:2])
        if len(raw) < 2 + digits:
            raise BinaryResponseError("truncated IEEE-488.2 length field")
        length_field = raw[2 : 2 + digits]
        if not length_field.isdigit():
            raise BinaryResponseError(f"invalid IEEE-488.2 length field: {length_field!r}")
        length = int(length_field)
        if length > max_bytes:
            raise BinaryResponseError(
                f"binary response declares {length} bytes, above max_bytes={max_bytes}"
            )
        start = 2 + digits
        end = start + length
        if len(raw) < end:
            raise BinaryResponseError(
                f"truncated binary response: declared {length}, received {len(raw) - start}"
            )
        tail = raw[end:]
        if tail not in (b"", b"\n", b"\r\n"):
            raise BinaryResponseError(f"unexpected bytes after binary response: {tail[:8]!r}")
        return raw[start:end]

    @staticmethod
    def _block_body_end(raw: bytes, max_bytes: int) -> int | None:
        """Return the body end when enough of an IEEE block header is present."""

        if not raw:
            return None
        if raw[:1] != b"#":
            raise BinaryResponseError(f"invalid IEEE-488.2 block header: {raw[:8]!r}")
        if len(raw) < 2:
            return None
        if raw[1:2] not in b"123456789":
            raise BinaryResponseError(f"invalid IEEE-488.2 block header: {raw[:8]!r}")
        digits = int(raw[1:2])
        if len(raw) < 2 + digits:
            return None
        length_field = raw[2 : 2 + digits]
        if not length_field.isdigit():
            raise BinaryResponseError(f"invalid IEEE-488.2 length field: {length_field!r}")
        length = int(length_field)
        if length > max_bytes:
            raise BinaryResponseError(
                f"binary response declares {length} bytes, above max_bytes={max_bytes}"
            )
        return 2 + digits + length

    @staticmethod
    def _visa_read(resource: Any, count: int) -> tuple[bytes, Any | None]:
        """Read one bounded VISA chunk, retaining the low-level status.

        Calling the resource's ``read_bytes`` for an IEEE header is unsafe on
        USBTMC: the method can return more than the requested header bytes, so
        a caller that assumes an exact count can mis-frame the remaining data.
        A direct VISA read receives the bounded logical message at once while
        retaining both the returned byte count and completion status.
        """

        visalib = getattr(resource, "visalib", None)
        session = getattr(resource, "session", None)
        if visalib is not None and session is not None:
            chunk, status = visalib.read(session, count)
            return bytes(chunk), status

        # Small test doubles may only expose read_raw() without a size keyword.
        try:
            return bytes(resource.read_raw(size=count)), None
        except TypeError as exc:
            if "size" not in str(exc) and "positional" not in str(exc):
                raise
            return bytes(resource.read_raw()), None

    def _read_usb_text_message(self, resource: Any, max_bytes: int) -> bytes:
        """Read one bounded USB message while retaining the VISA completion status."""

        read_cap = max_bytes + 2  # allow CRLF outside the response payload limit
        try:
            raw, status = self._visa_read(resource, read_cap)
        except _TRANSPORT_ERRORS as exc:
            raise _MessageResponseError(
                "text transport read failed "
                f"(read_stage=text, received_bytes=0): {exc}"
            ) from exc
        complete_statuses = {
            None,
            pyvisa.constants.StatusCode.success,
            pyvisa.constants.StatusCode.success_termination_character_read,
        }
        if status not in complete_statuses:
            raise _MessageResponseError(
                "text VISA read did not complete the message "
                f"(status={status!r}, read_stage=text, received_bytes={len(raw)})"
            )
        if not raw:
            raise _MessageResponseError(
                "empty text response (read_stage=text, received_bytes=0)"
            )
        if len(raw) >= read_cap:
            raise _MessageResponseError(
                "text response reached bounded read limit "
                f"(read_stage=text, received_bytes={len(raw)}, max_bytes={max_bytes})"
            )
        return raw

    def _read_usb_binary_message(self, resource: Any, max_bytes: int) -> bytes:
        """Read one bounded USBTMC message in a single low-level VISA read."""

        read_cap = max_bytes + _IEEE_BLOCK_OVERHEAD
        try:
            raw, status = self._visa_read(resource, read_cap)
        except _TRANSPORT_ERRORS as exc:
            raise _BinaryTransportReadError(
                "binary transport read failed "
                f"(read_stage=message, received_bytes=0): {exc}"
            ) from exc
        complete_statuses = {
            None,
            pyvisa.constants.StatusCode.success,
            pyvisa.constants.StatusCode.success_termination_character_read,
        }
        if status not in complete_statuses:
            raise _BinaryTransportReadError(
                "binary VISA read did not complete the message "
                f"(status={status!r}, read_stage=message, received_bytes={len(raw)})"
            )
        if not raw:
            raise BinaryResponseError(
                "empty binary response (read_stage=header, received_bytes=0)"
            )
        if len(raw) >= read_cap:
            raise BinaryResponseError(
                "binary response reached bounded read limit "
                f"(read_stage=message, received_bytes={len(raw)}, max_bytes={max_bytes})"
            )
        return raw

    def _read_exact_binary_message(self, resource: Any, max_bytes: int) -> bytes:
        """Read a socket-style block by exact fields without a USB-sized cap read."""

        read_cap = max_bytes + _IEEE_BLOCK_OVERHEAD
        raw = bytearray()

        def read_more(count: int, stage: str) -> None:
            try:
                chunk = bytes(resource.read_bytes(count))
            except _TRANSPORT_ERRORS as exc:
                raise BinaryResponseError(
                    "binary transport read failed "
                    f"(read_stage={stage}, received_bytes={len(raw)}): {exc}"
                ) from exc
            if not chunk:
                raise BinaryResponseError(
                    "truncated binary response: empty read "
                    f"(read_stage={stage}, received_bytes={len(raw)})"
                )
            raw.extend(chunk)
            if len(raw) > read_cap:
                raise BinaryResponseError(
                    "binary response exceeded bounded read buffer "
                    f"(read_stage={stage}, received_bytes={len(raw)}, "
                    f"max_bytes={max_bytes})"
                )

        read_more(2, "header")
        if raw[:1] != b"#" or raw[1:2] not in b"123456789":
            return bytes(raw)
        digits = int(raw[1:2])
        if len(raw) < 2 + digits:
            read_more(2 + digits - len(raw), "header")
        body_end = self._block_body_end(bytes(raw), max_bytes)
        if body_end is None:
            return bytes(raw)
        if len(raw) < body_end:
            read_more(body_end - len(raw), "payload")
        if len(raw) == body_end:
            read_more(1, "terminator")
        if bytes(raw[body_end:]) == b"\r":
            read_more(1, "terminator")
        return bytes(raw)

    @classmethod
    def _binary_read_stage(cls, raw: bytes, max_bytes: int) -> str:
        try:
            body_end = cls._block_body_end(raw, max_bytes)
        except BinaryResponseError:
            return "header"
        if body_end is None:
            return "header"
        if len(raw) < body_end:
            return "payload"
        return "terminator"

    def _read_binary(self, max_bytes: int) -> bytes:
        resource = self._open()
        raw = b""
        try:
            saved_read_termination = getattr(resource, "read_termination", None)
            try:
                # Binary payloads may contain LF.  Disable VISA termchar handling
                # for this logical message and restore it before returning.
                if hasattr(resource, "read_termination"):
                    resource.read_termination = None
                with self._usb_io_timeout(resource):
                    if self._is_usb_resource(resource):
                        raw = self._read_usb_binary_message(resource, max_bytes)
                    else:
                        raw = self._read_exact_binary_message(resource, max_bytes)
            finally:
                if hasattr(resource, "read_termination"):
                    resource.read_termination = saved_read_termination
            try:
                return self._parse_block(raw, max_bytes)
            except BinaryResponseError as exc:
                raise BinaryResponseError(
                    f"{exc} (read_stage={self._binary_read_stage(raw, max_bytes)}, "
                    f"received_bytes={len(raw)})"
                ) from exc
        except _BinaryTransportReadError as exc:
            self._transport_fault(exc)
        except BinaryResponseError:
            # A malformed or partial binary response cannot safely be reused.
            self._faulted = True
            self._close_transport()
            raise

    def binary_query(
        self,
        command: str,
        max_bytes: int = DEFAULT_BINARY_MAX_BYTES,
    ) -> bytes:
        """Return one validated IEEE-488.2 definite-length payload."""

        if not isinstance(command, str) or not command.strip():
            raise ValueError("command must be a non-empty string")
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
            raise ValueError("max_bytes must be a positive integer")
        resource = self._open()
        try:
            with self._usb_io_timeout(resource):
                resource.write(command)
        except _TRANSPORT_ERRORS as exc:
            self._transport_fault(exc)
        return self._read_binary(max_bytes)

    def write_binary(
        self,
        command: str,
        payload: bytes,
        max_bytes: int = DEFAULT_BINARY_MAX_BYTES,
    ) -> None:
        """Upload one bounded IEEE-488.2 definite-length binary block.

        This is intentionally a separate API from :meth:`write`: the command
        header must be a single non-query SCPI command, and a transport fault
        after the write is never replayed.
        """

        if not isinstance(command, str) or not command.strip():
            raise ValueError("command must be a non-empty string")
        command = command.strip()
        if command.endswith("?") or any(char in command for char in "\r\n;"):
            raise ValueError("binary upload command must be one non-query SCPI header")
        try:
            command_bytes = command.encode("ascii")
        except UnicodeEncodeError:
            raise ValueError("binary upload command must contain ASCII SCPI characters") from None
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
            raise ValueError("max_bytes must be a positive integer")
        if not isinstance(payload, (bytes, bytearray, memoryview)):
            raise TypeError("payload must be bytes-like")
        data = bytes(payload)
        if len(data) > max_bytes:
            raise ValueError(
                f"binary payload is {len(data)} bytes, above max_bytes={max_bytes}"
            )
        digits = str(len(data)).encode("ascii")
        frame = command_bytes + b" " + b"#" + str(len(digits)).encode("ascii") + digits + data + b"\n"
        resource = self._open()
        try:
            with self._usb_io_timeout(resource):
                resource.write_raw(frame)
        except _TRANSPORT_ERRORS as exc:
            self._transport_fault(exc)
