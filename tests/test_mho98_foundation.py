"""Offline checks for the MHO98 session and stdio foundation."""

import asyncio
from types import SimpleNamespace

import mcp.types as types
import pytest
import pyvisa
from pyvisa import constants

from rigol_mcp.mho98 import MHO98IdentityError, SCPIError, Session
from rigol_mcp.mho98 import recovery as mho_recovery
from rigol_mcp.mho98 import server as mho_server


def block(payload: bytes, *, terminator: bytes = b"\n") -> bytes:
    return b"#2" + str(len(payload)).encode().zfill(2) + payload + terminator


class FakeTransport:
    def __init__(self, identity: str, *, errors=None, read_buffer=b""):
        self.identity = identity
        self.errors = list(errors or ["0,No error"])
        self.read_buffer = bytearray(read_buffer)
        self.queries = []
        self.writes = []
        self.raw_writes = []
        self.closed = False
        self.timeout = None
        self.read_termination = None
        self.write_termination = None

    def query(self, command):
        self.queries.append(command)
        if command == "*IDN?":
            return self.identity
        if command == ":SYSTem:ERRor?":
            return self.errors.pop(0) if self.errors else "0,No error"
        raise AssertionError(f"unexpected query: {command}")

    def write(self, command):
        self.writes.append(command)

    def write_raw(self, payload):
        self.raw_writes.append(bytes(payload))

    def read_bytes(self, count):
        data = bytes(self.read_buffer[:count])
        del self.read_buffer[:count]
        return data

    def read_raw(self):
        data = bytes(self.read_buffer)
        self.read_buffer.clear()
        return data

    def close(self):
        self.closed = True


class FakeVisaLibrary:
    """Minimal VISA-like reader that preserves data/status pairs and counts."""

    def __init__(self, reads):
        self.reads = list(reads)
        self.calls = []

    def read(self, session, count):
        self.calls.append((session, count))
        if not self.reads:
            raise AssertionError("unexpected VISA read")
        item = self.reads.pop(0)
        if isinstance(item, BaseException):
            raise item
        data, status = item
        assert len(data) <= count
        return data, status


class FakeUsbVisaTransport(FakeTransport):
    def __init__(self, reads):
        super().__init__("RIGOL TECHNOLOGIES,MHO98,serial,version")
        self.interface_type = constants.InterfaceType.usb
        self.resource_name = "USB0::6833::1106::serial::INSTR"
        self.session = 17
        self.visalib = FakeVisaLibrary(reads)
        self.interface = SimpleNamespace(timeout=pyvisa.constants.VI_TMO_INFINITE)
        self.visalib.sessions = {self.session: SimpleNamespace(interface=self.interface)}


def usb_session(binary_response: bytes, *, status=constants.StatusCode.success):
    transport = FakeUsbVisaTransport(
        [
            (b"RIGOL TECHNOLOGIES,MHO98,serial,version\n", constants.StatusCode.success),
            (binary_response, status),
        ]
    )
    session = Session(transport=transport)
    assert session.idn() == "RIGOL TECHNOLOGIES,MHO98,serial,version"
    transport.visalib.calls.clear()
    return session, transport


def test_identity_gate_rejects_non_mho98_without_mutation():
    transport = FakeTransport("RIGOL TECHNOLOGIES,DS1054Z,serial,version")
    session = Session(transport=transport)

    with pytest.raises(MHO98IdentityError):
        session.write(":RUN")

    assert transport.writes == []
    assert transport.closed is True


def test_identity_gate_rejects_mho98_prefix_collision():
    transport = FakeTransport("RIGOL TECHNOLOGIES,MHO980,serial,version")
    session = Session(transport=transport)

    with pytest.raises(MHO98IdentityError):
        session.idn()

    assert session.faulted is False
    assert session.closed is True


def test_timeout_defaults_to_infinite_and_explicit_override_is_applied():
    default_transport = FakeTransport("RIGOL TECHNOLOGIES,MHO98,serial,version")
    default_session = Session(transport=default_transport)
    assert default_session.timeout_ms is None
    assert default_transport.timeout is None

    finite_transport = FakeTransport("RIGOL TECHNOLOGIES,MHO98,serial,version")
    finite_session = Session(transport=finite_transport, timeout_ms=2750)
    assert finite_session.timeout_ms == 2750
    assert finite_transport.timeout == 2750

    for invalid in (True, 0, -1, 1.5, pyvisa.constants.VI_TMO_INFINITE):
        with pytest.raises(ValueError, match="timeout_ms"):
            Session(timeout_ms=invalid)


def test_timeout_assignment_failure_is_not_silently_ignored():
    class RejectingTimeout:
        @property
        def timeout(self):
            return None

        @timeout.setter
        def timeout(self, _value):
            raise OSError("timeout attribute unavailable")

    with pytest.raises(RuntimeError, match="failed to configure MHO98 resource timeout"):
        Session(transport=RejectingTimeout())


def test_default_usb_policy_uses_libusb_infinite_only_during_io():
    transport = FakeUsbVisaTransport(
        [(b"RIGOL TECHNOLOGIES,MHO98,serial,version\n", constants.StatusCode.success)]
    )
    session = Session(transport=transport)

    with session._usb_io_timeout(transport):
        assert transport.interface.timeout == 0
    assert transport.interface.timeout == pyvisa.constants.VI_TMO_INFINITE

    finite = FakeUsbVisaTransport([])
    finite_session = Session(transport=finite, timeout_ms=2500)
    with finite_session._usb_io_timeout(finite):
        assert finite.interface.timeout == pyvisa.constants.VI_TMO_INFINITE


def test_write_checks_errors_without_retrying_mutation():
    transport = FakeTransport(
        "RIGOL TECHNOLOGIES,MHO98,serial,version",
        errors=["-222,Data out of range", "0,No error"],
    )
    session = Session(transport=transport)

    with pytest.raises(SCPIError):
        session.write(":CHANnel1:SCALe 999")

    assert transport.writes == [":CHANnel1:SCALe 999"]
    assert transport.writes.count(":CHANnel1:SCALe 999") == 1


def test_binary_query_validates_framing_and_payload_cap(tmp_path):
    payload = b"\x00\x01PNG"
    transport = FakeTransport("RIGOL TECHNOLOGIES,MHO98,serial,version", read_buffer=block(payload))
    session = Session(transport=transport, output_dir=tmp_path)
    assert session.binary_query(":DISPlay:DATA?", max_bytes=len(payload)) == payload
    assert transport.writes == [":DISPlay:DATA?"]

    truncated = FakeTransport(
        "RIGOL TECHNOLOGIES,MHO98,serial,version",
        read_buffer=b"#205abc\n",
    )
    with pytest.raises(ValueError, match="truncated"):
        Session(transport=truncated).binary_query(":WAVeform:DATA?")
    assert truncated.closed is True

    oversized = FakeTransport(
        "RIGOL TECHNOLOGIES,MHO98,serial,version",
        read_buffer=block(b"12345"),
    )
    with pytest.raises(ValueError, match="above max_bytes"):
        Session(transport=oversized).binary_query(":DISPlay:DATA?", max_bytes=2)


def test_usb_binary_receive_uses_one_bounded_visa_read():
    payload = b"PNG\nwith-embedded-LF"
    session, transport = usb_session(block(payload))

    assert session.binary_query(":DISPlay:DATA? PNG", max_bytes=len(payload)) == payload
    assert transport.visalib.calls == [(transport.session, len(payload) + 13)]
    assert transport.read_termination == "\n"
    assert transport.writes == ["*IDN?", ":DISPlay:DATA? PNG"]


def test_usb_binary_receive_accepts_complete_eom_without_lf():
    payload = b"no-terminator"
    session, transport = usb_session(block(payload, terminator=b""))

    assert session.binary_query(":WAVeform:DATA?", max_bytes=len(payload)) == payload
    assert len(transport.visalib.calls) == 1
    assert transport.read_termination == "\n"


@pytest.mark.parametrize(
    ("response", "max_bytes", "stage"),
    [
        (b"#205abc", 5, "payload"),
        (block(b"12345"), 2, "header"),
    ],
)
def test_usb_binary_receive_faults_closed_on_truncated_or_oversize(
    response, max_bytes, stage
):
    session, transport = usb_session(response)

    with pytest.raises(
        ValueError,
        match=rf"read_stage={stage}.*received_bytes=",
    ):
        session.binary_query(":DISPlay:DATA? PNG", max_bytes=max_bytes)

    assert session.faulted is True
    assert session.is_healthy is False
    assert transport.closed is True
    reads_after_fault = list(transport.visalib.calls)
    with pytest.raises(RuntimeError, match="faulted"):
        session.binary_query(":DISPlay:DATA? PNG", max_bytes=max_bytes)
    assert transport.visalib.calls == reads_after_fault


def test_transport_fault_marks_session_unhealthy_and_blocks_reopen():
    class BrokenTransport(FakeTransport):
        def query(self, command):
            if command == "*IDN?":
                raise OSError("link down")
            return super().query(command)

    transport = BrokenTransport("RIGOL TECHNOLOGIES,MHO98,serial,version")
    session = Session(transport=transport)
    with pytest.raises(OSError):
        session.idn()
    assert session.faulted is True
    assert session.is_healthy is False
    with pytest.raises(RuntimeError, match="faulted"):
        session.idn()


def test_binary_write_frames_payload_and_rejects_queries():
    transport = FakeTransport("RIGOL TECHNOLOGIES,MHO98,serial,version")
    session = Session(transport=transport)
    session.write_binary(":SYSTem:SETup", b"abc")
    assert transport.raw_writes == [b":SYSTem:SETup #13abc\n"]

    with pytest.raises(ValueError, match="non-query"):
        session.write_binary(":SYSTem:SETup?", b"abc")
    assert transport.raw_writes == [b":SYSTem:SETup #13abc\n"]


def test_stdio_tool_schema_and_idn_dispatch(monkeypatch):
    listed = asyncio.run(mho_server.list_tools())
    names = {tool.name for tool in listed}
    assert {"idn", "search_commands", "describe_command"} <= names
    assert {"get_acquisition", "get_channel", "measure", "get_timebase", "get_trigger", "get_waveform"} <= names
    assert listed[0].inputSchema["type"] == "object"
    assert listed[0].inputSchema["required"] == []
    assert listed[0].annotations.readOnlyHint is True
    assert listed[1].annotations.readOnlyHint is True
    assert listed[1].annotations.idempotentHint is False

    transport = FakeTransport("RIGOL TECHNOLOGIES,MHO98,serial,version")
    monkeypatch.setattr(mho_server, "Session", lambda: Session(transport=transport))
    result = asyncio.run(mho_server.call_tool("idn", {}))
    assert result[0].text == '{"idn":"RIGOL TECHNOLOGIES,MHO98,serial,version"}'


def test_mcp_protocol_wraps_tool_exception_as_is_error():
    handler = mho_server.server.request_handlers[types.CallToolRequest]
    request = types.CallToolRequest(
        params=types.CallToolRequestParams(
            name="describe_command",
            arguments={"id": "missing-command"},
        )
    )
    response = asyncio.run(handler(request))
    assert response.root.isError is True
    assert "unknown MHO98 catalog command id" in response.root.content[0].text


def test_explicit_libusb_backend_is_absolute_and_verified(monkeypatch, tmp_path):
    import usb.backend.libusb1 as libusb1

    library = tmp_path / "libusb-1.0.dylib"
    library.write_bytes(b"test-double")
    requested = []

    def fake_get_backend(*, find_library):
        requested.append(find_library("usb-1.0"))
        return SimpleNamespace(lib=SimpleNamespace(_name=str(library)))

    monkeypatch.setenv("RIGOL_LIBUSB_LIBRARY", str(library))
    monkeypatch.setattr(libusb1, "get_backend", fake_get_backend)

    assert mho_recovery.prepare_libusb_backend() == {
        "configured": str(library),
        "loaded": str(library),
    }
    assert requested == [str(library)]


def test_binary_transport_fault_closes_without_reset_or_replay():
    timeout = pyvisa.errors.VisaIOError(constants.StatusCode.error_timeout)
    transport = FakeUsbVisaTransport(
        [
            (b"RIGOL TECHNOLOGIES,MHO98,serial,version\n", constants.StatusCode.success),
            timeout,
        ]
    )
    session = Session(transport=transport)

    with pytest.raises(ValueError, match="binary transport read failed"):
        session.binary_query(":DISPlay:DATA? PNG")

    assert transport.writes == ["*IDN?", ":DISPlay:DATA? PNG"]
    assert session.faulted is True
    assert transport.closed is True


def test_recover_connection_fresh_open_verifies_target_idn(monkeypatch, tmp_path):
    session = Session(output_dir=tmp_path)
    monkeypatch.setattr(
        mho_recovery,
        "_fresh_idn",
        lambda _session: ("RIGOL TECHNOLOGIES,MHO98,MHO9A274501253,version", None),
    )

    result = mho_recovery.recover_connection(session)

    assert result["recovered"] is True
    assert result["stage"] == "fresh_open"
    assert result["identity"].split(",")[2] == "MHO9A274501253"


def test_recover_connection_reports_absent_without_usb_reset(monkeypatch, tmp_path):
    session = Session(output_dir=tmp_path)
    monkeypatch.setattr(
        mho_recovery, "_fresh_idn", lambda _session: (None, "device absent")
    )

    result = mho_recovery.recover_connection(session)

    assert result["recovered"] is False
    assert result["stage"] == "device_absent"
    assert result["prior_command_state"] == "unknown"
