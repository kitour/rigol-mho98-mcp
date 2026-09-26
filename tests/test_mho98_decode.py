"""Focused offline tests for MHO98 decoder controls and event parsing."""

from pathlib import Path

import pytest

from rigol_mcp.mho98.decode import get_decode, read_decode_events, set_decode


class FakeSession:
    def __init__(self, output_dir="/tmp/mho98-decode-test", protocol="IIC"):
        self.output_dir = Path(output_dir)
        self.writes = []
        self.state = {
            "mode": protocol,
            "common": {"display": "0", "format": "HEX", "event": "0", "label": "1", "position": "0"},
            "thresholds": {"CH1": "0", "CH2": "0", "CH3": "0", "CH4": "0", "SCL": "0", "SDA": "0", "CS": "0", "CLK": "0", "MISO": "0", "MOSI": "0", "TX": "0", "RX": "0"},
            "i2c": {"clock": "CHAN1", "data": "CHAN2", "exchange": "0", "address": "7"},
            "spi": {
                "clock": "CHAN1", "slope": "POS", "miso": "CHAN2", "mosi": "OFF", "polarity": "HIGH",
                "miso_pol": "HIGH", "mosi_pol": "HIGH", "bits": "8", "endian": "MSB", "mode": "TIM",
                "timeout": "1e-6", "cs": "CHAN3", "cs_pol": "LOW",
            },
            "rs232": {"tx": "CHAN1", "rx": "OFF", "pol": "NEG", "parity": "NONE", "endian": "LSB", "baud": "9600", "bits": "8", "stop": "1"},
        }
        self.payload = b"SPI\nTime,Data,Flag,\n0.1us,AA,ok,\n0.2us,BB,yes,\n"

    def query(self, command):
        if command == ":BUS1:MODE?":
            return self.state["mode"]
        if command.startswith(":BUS1:") and (command.endswith("?") or "THReshold?" in command):
            key = command[6:-1].upper() if command.endswith("?") else command[6:].upper()
            common = {"DISPLAY": "display", "FORMAT": "format", "EVENT": "event", "LABEL": "label", "POSITION": "position"}
            if key in common:
                return self.state["common"][common[key]]
            if key.startswith("THRESHOLD?"):
                return self.state["thresholds"][key.split(" ", 1)[-1]]
            if ":IIC:" in command:
                return {"SCLK:SOURCE": self.state["i2c"]["clock"], "SDA:SOURCE": self.state["i2c"]["data"], "EXCHANGE": self.state["i2c"]["exchange"], "ADDBITS": self.state["i2c"]["address"]}[key.split("IIC:", 1)[-1]]
            if ":SPI:" in command:
                tail = key.split("SPI:", 1)[-1]
                return {"SCLK:SOURCE": self.state["spi"]["clock"], "SCLK:SLOPE": self.state["spi"]["slope"], "MISO:SOURCE": self.state["spi"]["miso"], "MOSI:SOURCE": self.state["spi"]["mosi"], "POLARITY": self.state["spi"]["polarity"], "MISO:POLARITY": self.state["spi"]["miso_pol"], "MOSI:POLARITY": self.state["spi"]["mosi_pol"], "DBITS": self.state["spi"]["bits"], "ENDIAN": self.state["spi"]["endian"], "MODE": self.state["spi"]["mode"], "TIMEOUT:TIME": self.state["spi"]["timeout"], "SS:SOURCE": self.state["spi"]["cs"], "SS:POLARITY": self.state["spi"]["cs_pol"]}[tail]
            if ":RS232:" in command:
                tail = key.split("RS232:", 1)[-1]
                return {"TX": self.state["rs232"]["tx"], "RX": self.state["rs232"]["rx"], "POLARITY": self.state["rs232"]["pol"], "PARITY": self.state["rs232"]["parity"], "ENDIAN": self.state["rs232"]["endian"], "BAUD": self.state["rs232"]["baud"], "DBITS": self.state["rs232"]["bits"], "SBITS": self.state["rs232"]["stop"]}[tail]
        raise AssertionError(f"unexpected query: {command}")

    def write(self, command):
        self.writes.append(command)

    def binary_query(self, command):
        assert command == ":BUS1:DATA?"
        return self.payload


class FamilyFakeSession:
    """Small readback fake covering the documented remaining BUS families."""

    def __init__(self, protocol, *, parallel_endian="POS"):
        self.output_dir = Path("/tmp/mho98-decode-family-test")
        self.writes = []
        self.protocol = protocol
        self.common = {"DISPLAY": "0", "FORMAT": "HEX", "EVENT": "0", "LABEL": "1", "POSITION": "0"}
        self.thresholds = {name: "0" for name in ("CH1", "CH2", "CH3", "CH4", "PAL", "PALCLK", "CAN", "CANSUB1", "LIN", "I2SCLK", "DATA", "WS", "FLEX", "1553")}
        self.settings = {
            "PAR": {"BUS": "CHAN1", "CLK": "OFF", "SLOPE": "POS", "WIDTH": "1", "BITX": "0", "SOURCE": "CHAN1", "ENDIAN": parallel_endian, "POLARITY": "POS"},
            "CAN": {"SOURCE": "CHAN1", "STYPE": "CANH", "BAUD": "1000000", "FDBAUD": "1000000", "SPOINT": "80", "FDSPOINT": "80"},
            "LIN": {"PARITY": "0", "SOURCE": "CHAN1", "STANDARD": "MIX", "BAUD": "9600"},
            "IIS": {"SOURCE:CLOCK": "CHAN1", "SOURCE:DATA": "CHAN3", "SOURCE:WSELECT": "CHAN2", "ALIGNMENT": "IIS", "CLOCK:SLOPE": "POS", "RWIDTH": "4", "RECEWIDTH": "4", "WSLOW": "LEFT", "ENDIAN": "MSB", "POLARITY": "POS"},
            "FLEX": {"BAUD": "10000000", "SOURCE": "CHAN1", "SPOINT": "50", "STYPE": "BP", "CHANNEL": "A"},
            "M1553": {"SOURCE": "CHAN1"},
        }

    def query(self, command):
        upper = command.upper()
        if upper == ":BUS1:MODE?":
            return self.protocol
        if upper.startswith(":BUS1:THRESHOLD?"):
            return self.thresholds[upper.rsplit(" ", 1)[-1]]
        if upper.startswith(":CHANNEL") and upper.endswith((":SCALE?", ":OFFSET?")):
            return "1" if upper.endswith(":SCALE?") else "0"
        for name, key in (("DISPLAY", "DISPLAY"), ("FORMAT", "FORMAT"), ("EVENT", "EVENT"), ("LABEL", "LABEL"), ("POSITION", "POSITION")):
            if upper == f":BUS1:{name}?":
                return self.common[key]
        prefixes = {"PAR": ":BUS1:PARALLEL:", "CAN": ":BUS1:CAN:", "LIN": ":BUS1:LIN:", "IIS": ":BUS1:IIS:", "FLEX": ":BUS1:FLEXRAY:", "M1553": ":BUS1:M1553:"}
        family = next((name for name, prefix in prefixes.items() if upper.startswith(prefix)), None)
        if family is not None:
            tail = upper[len(prefixes[family]):].rstrip("?")
            tail = {"SOURCE:CLOCK": "SOURCE:CLOCK", "SOURCE:WSELECT": "SOURCE:WSELECT", "CLOCK:SLOPE": "CLOCK:SLOPE"}.get(tail, tail)
            return self.settings[family][tail]
        raise AssertionError(f"unexpected query: {command}")

    def write(self, command):
        self.writes.append(command)


def test_remaining_bus_families_set_representative_configs():
    cases = [
        ("PAR", {"bus_source": "USER", "clock_source": "D0", "slope": "BOTH", "width": 4, "bit": 2, "source": "D2", "endian": "POSITIVE", "polarity": "NEGATIVE"}, ":BUS1:PARallel:BUS USER"),
        ("CAN", {"source": "CHAN2", "signal_type": "CANH", "baud": 500000, "fd_baud": 2000000, "sample_point": 75, "fd_sample_point": 80}, ":BUS1:CAN:BAUD 500000"),
        ("LIN", {"source": "CHAN2", "standard": "V2X", "baud": 19200, "parity": True}, ":BUS1:LIN:STANdard V2X"),
        ("IIS", {"clock_source": "CHAN1", "data_source": "CHAN3", "ws_source": "CHAN2", "alignment": "RJ", "clock_slope": "NEGATIVE", "word_width": 16, "receive_width": 16, "ws_low": "RIGHT", "endian": "LSB", "polarity": "POSITIVE"}, ":BUS1:IIS:RWIDth 16"),
        ("FLEX", {"source": "CHAN2", "baud": 5000000, "sample_point": 60, "signal_type": "BM", "channel": "B"}, ":BUS1:FLEXray:CHANnel B"),
        ("M1553", {"source": "CHAN4"}, ":BUS1:M1553:SOURce CHAN4"),
    ]
    for protocol, details, expected_write in cases:
        session = FamilyFakeSession(protocol)
        result = set_decode(session, protocol=protocol, details=details)
        assert result["supported"] is True
        assert expected_write in session.writes


def test_parallel_user_fields_require_user_bus_and_write_nothing_on_failure():
    session = FamilyFakeSession("PAR")
    with pytest.raises(ValueError, match="require bus_source=USER"):
        set_decode(session, protocol="PARALLEL", width=8)
    assert session.writes == []


@pytest.mark.parametrize(
    ("raw_endian", "expected_endian", "has_discrepancy"),
    [("LSB", "LSB", True), ("MSB", "MSB", True), ("NEG", "NEGATIVE", False), ("POS", "POSITIVE", False)],
)
def test_get_parallel_preserves_firmware_bit_order_and_documented_tokens(
    raw_endian, expected_endian, has_discrepancy
):
    session = FamilyFakeSession("PAR", parallel_endian=raw_endian)

    result = get_decode(session)

    assert result["endian"] == expected_endian
    if has_discrepancy:
        assert result["metadata"]["manual_discrepancy"]["raw_response"] == raw_endian
        assert "without conversion" in result["metadata"]["manual_discrepancy"]["message"]
    else:
        assert "metadata" not in result


def test_parallel_setter_does_not_adopt_readback_only_bit_order_tokens():
    session = FamilyFakeSession("PAR", parallel_endian="LSB")

    with pytest.raises(ValueError, match="endian"):
        set_decode(session, protocol="PARALLEL", endian="LSB")
    assert session.writes == []


def test_set_i2c_validates_and_writes_named_settings():
    session = FakeSession(protocol="IIC")
    result = set_decode(session, protocol="I2C", clock_source="CH3", address_bits=10, display=True)
    assert result["supported"] is True
    assert ":BUS1:IIC:SCLK:SOURce CHAN3" in session.writes
    assert ":BUS1:IIC:ADDBits 10" in session.writes
    assert session.writes.index(":BUS1:DISPlay 1") < session.writes.index(":BUS1:IIC:SCLK:SOURce CHAN3")
    assert result["thresholds"]["CH1"] == 0.0


def test_set_spi_and_rs232_reject_irrelevant_fields_before_writes():
    spi = FakeSession(protocol="SPI")
    with pytest.raises(ValueError, match="irrelevant"):
        set_decode(spi, protocol="SPI", baud=115200)
    assert spi.writes == []
    with pytest.raises(ValueError, match="endian"):
        set_decode(spi, protocol="SPI", endian="network")
    assert spi.writes == []
    set_decode(
        spi,
        protocol="SPI",
        clock_source="CHAN1",
        miso_source="CHAN2",
        mosi_source="CHAN3",
        frame_mode="CS",
        cs_source="CHAN4",
        data_bits=16,
        endian="LSB",
    )
    assert ":BUS1:SPI:MODE CS" in spi.writes
    assert ":BUS1:SPI:MOSI:SOURce CHAN3" in spi.writes

    uart = FakeSession(protocol="RS232")
    result = set_decode(uart, protocol="UART", baud=115200, data_bits=7, parity="EVEN")
    assert result["protocol"] == "RS232"
    assert ":BUS1:RS232:BAUD 115200" in uart.writes


def test_event_reader_returns_variable_csv_cells_and_bounded_rows(tmp_path):
    session = FakeSession(output_dir=tmp_path)
    result = read_decode_events(session, max_rows=1, include_raw=True, filename="events.csv")
    assert result["protocol"] == "SPI"
    assert result["columns"] == ["Time", "Data", "Flag", ""]
    assert result["rows"] == [["0.1us", "AA", "ok", ""]]
    assert result["count"] == 2
    assert result["truncated"] is True
    assert "SPI\n" in result["raw_text"]
    assert Path(result["path"]).read_text(encoding="utf-8").startswith("Time,Data,Flag,\n")


def test_event_reader_handles_empty_payload_without_inventing_rows():
    session = FakeSession()
    session.payload = b""
    result = read_decode_events(session)
    assert result["protocol"] == ""
    assert result["columns"] == []
    assert result["rows"] == []
    assert result["count"] == 0
    assert result["truncated"] is False
