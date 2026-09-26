"""Offline tests for MHO98 common and edge trigger controls."""

import pytest

from rigol_mcp.mho98.trigger import get_trigger, set_trigger


class FakeSession:
    def __init__(self, *, mode="EDGE", source="CHAN1"):
        self.state = {
            "mode": mode,
            "sweep": "AUTO",
            "coupling": "DC",
            "status": "STOP",
            "holdoff": "1.0E-6",
            "noise": "0",
            "source": source,
            "slope": "POS",
            "level": "0",
            "scale": "1",
            "offset": "0",
        }
        self.queries = []
        self.writes = []

    def query(self, command):
        self.queries.append(command)
        values = {
            ":TRIGger:MODE?": self.state["mode"],
            ":TRIGger:SWEep?": self.state["sweep"],
            ":TRIGger:COUPling?": self.state["coupling"],
            ":TRIGger:STATus?": self.state["status"],
            ":TRIGger:HOLDoff?": self.state["holdoff"],
            ":TRIGger:NREJect?": self.state["noise"],
            ":TRIGger:EDGE:SOURce?": self.state["source"],
            ":TRIGger:EDGE:SLOPe?": self.state["slope"],
            ":TRIGger:EDGE:LEVel?": self.state["level"],
            ":TRIGger:PULSe:SOURce?": "CHAN1",
            ":TRIGger:PULSe:POLarity?": "POS",
            ":TRIGger:PULSe:WHEN?": "GRE",
            ":TRIGger:PULSe:LWIDth?": "1E-6",
            ":TRIGger:PULSe:LEVel?": "0",
            ":TRIGger:VIDeo:SOURce?": "CHAN1",
            ":TRIGger:VIDeo:POLarity?": "POS",
            ":TRIGger:VIDeo:MODE?": "ALIN",
            ":TRIGger:VIDeo:STANdard?": "NTSC",
            ":TRIGger:VIDeo:LEVel?": "0",
            ":CHANnel1:SCALe?": self.state["scale"],
            ":CHANnel1:OFFSet?": self.state["offset"],
        }
        if command not in values:
            raise AssertionError(f"unexpected query: {command}")
        return values[command]

    def write(self, command):
        self.writes.append(command)
        head, value = command.rsplit(" ", 1)
        updates = {
            ":TRIGger:MODE": "mode",
            ":TRIGger:SWEep": "sweep",
            ":TRIGger:COUPling": "coupling",
            ":TRIGger:HOLDoff": "holdoff",
            ":TRIGger:NREJect": "noise",
            ":TRIGger:EDGE:SOURce": "source",
            ":TRIGger:EDGE:SLOPe": "slope",
            ":TRIGger:EDGE:LEVel": "level",
        }
        if head in updates:
            self.state[updates[head]] = value


def test_get_trigger_reads_edge_fields_only_in_edge_mode():
    edge = FakeSession()
    result = get_trigger(edge)
    assert result["mode"] == "EDGE"
    assert result["source"] == "CHAN1"
    assert result["slope"] == "POS"
    assert result["level"] == 0.0

    advanced = FakeSession(mode="PULS")
    result = get_trigger(advanced)
    assert result["mode"] == "PULSE"
    assert result["protocol"] == "PULSE"
    assert result["details"]["condition"] == "GREATER"
    assert not any(":TRIGger:EDGE:" in query for query in advanced.queries)


def test_set_edge_validates_level_and_writes_in_dependency_order():
    session = FakeSession()

    result = set_trigger(session, source="CH1", slope="NEG", level=2, coupling="AC", noise_reject=True)

    assert result["source"] == "CHAN1"
    assert result["slope"] == "NEG"
    assert result["level"] == 2.0
    assert result["coupling"] == "AC"
    assert result["noise_reject"] is True
    assert session.writes == [
        ":TRIGger:EDGE:SLOPe NEG",
        ":TRIGger:EDGE:LEVel 2",
        ":TRIGger:COUPling AC",
        ":TRIGger:NREJect 1",
    ]


def test_advanced_mode_does_not_silently_become_edge():
    session = FakeSession(mode="PULS")

    with pytest.raises(ValueError, match="EDGE"):
        set_trigger(session, source="CH1")
    assert session.writes == []


def test_ext_source_is_rejected_before_device_access():
    session = FakeSession()
    with pytest.raises(ValueError, match="EXT"):
        set_trigger(session, source="EXT")
    assert session.queries == []
    assert session.writes == []


def test_holdoff_excluded_mode_and_digital_coupling_are_rejected():
    session = FakeSession(mode="VIDEO")
    with pytest.raises(ValueError, match="unavailable"):
        set_trigger(session, holdoff_s=1e-6)
    assert session.writes == []

    digital = FakeSession(source="D0")
    with pytest.raises(ValueError, match="analog"):
        set_trigger(digital, coupling="AC")
    assert digital.writes == []


def test_digital_level_uses_minus15_to_plus15_limit_without_channel_query():
    session = FakeSession(source="D0")
    set_trigger(session, level=15)
    assert ":TRIGger:EDGE:LEVel 15" in session.writes
    assert not any(":CHANnel" in query for query in session.queries)


class ProtocolSession:
    """Small stateful fake for one representative trigger family."""

    def __init__(self, protocol):
        self.mode = {"I2C": "IIC", "SPI": "SPI", "RS232": "RS232"}[protocol]
        self.protocol = protocol
        self.writes = []
        self.queries = []
        self.state = {
            "I2C": {
                "SCL": "CHAN1", "CLEVel": "0", "SDA": "CHAN2", "DLEVel": "0", "WHEN": "STAR",
                "AWIDth": "7", "ADDRess": "0", "DIRection": "WRIT", "DBYTes": "1", "DATA": "0", "CURRbit": "0", "CODE": "255",
            },
            "SPI": {
                "CLK": "CHAN1", "CLEVel": "0", "SLOPe": "POS", "MISO": "CHAN2", "DLEVel": "0", "WHEN": "CS",
                "CS": "CHAN3", "SLEVel": "0", "MODE": "LOW", "TIMeout": "1E-6", "WIDTh": "8", "DATA": "0", "CURRbit": "0", "CODE": "255",
            },
            "RS232": {
                "SOURce": "CHAN1", "LEVel": "0", "POLarity": "POS", "WHEN": "STAR", "DATA": "0", "BAUD": "9600", "WIDTh": "8", "STOP": "1", "PARity": "NONE",
            },
        }[protocol]

    def query(self, command):
        self.queries.append(command)
        common = {
            ":TRIGger:MODE?": self.mode,
            ":TRIGger:SWEep?": "AUTO",
            ":TRIGger:STATus?": "STOP",
        }
        if command in common:
            return common[command]
        if command.startswith(":TRIGger:") and command.endswith("?"):
            family = command.split(":")[2]
            field = command.rsplit(":", 1)[-1][:-1]
            if family == "IIC":
                return self.state[field]
            if family in {"SPI", "RS232"}:
                return self.state[field]
        if command in {":CHANnel1:SCALe?", ":CHANnel2:SCALe?", ":CHANnel3:SCALe?", ":CHANnel4:SCALe?"}:
            return "1"
        if command in {":CHANnel1:OFFSet?", ":CHANnel2:OFFSet?", ":CHANnel3:OFFSet?", ":CHANnel4:OFFSet?"}:
            return "0"
        raise AssertionError(f"unexpected query: {command}")

    def write(self, command):
        self.writes.append(command)
        head, value = command.rsplit(" ", 1)
        if head == ":TRIGger:MODE":
            self.mode = value
            return
        family = head.split(":")[2]
        field = head.rsplit(":", 1)[-1]
        self.state[field] = value


def test_i2c_details_configure_and_read_back():
    session = ProtocolSession("I2C")

    result = set_trigger(
        session,
        mode="I2C",
        details={"when": "ADDRESS_DATA", "address_width": 10, "address": 0x155, "data_bytes": 2, "data": 0x1234},
    )

    assert result["protocol"] == "I2C"
    assert result["details"]["condition"] == "ADDRESS_DATA"
    assert result["details"]["address"] == 0x155
    assert result["details"]["data"] == 0x1234
    assert session.writes[:4] == [
        ":TRIGger:IIC:WHEN ADATa",
        ":TRIGger:IIC:AWIDth 10",
        ":TRIGger:IIC:DBYTes 2",
        ":TRIGger:IIC:ADDRess 341",
    ]


def test_spi_details_configure_and_read_back():
    session = ProtocolSession("SPI")

    result = set_trigger(session, details={"condition": "CS", "cs_source": "D3", "data_width": 12, "data": 0xABC})

    assert result["details"]["cs_source"] == "D3"
    assert result["details"]["data_width"] == 12
    assert result["details"]["data"] == 0xABC
    assert session.writes == [
        ":TRIGger:SPI:CS D3",
        ":TRIGger:SPI:WIDTh 12",
        ":TRIGger:SPI:DATA 2748",
    ]


def test_rs232_details_configure_and_read_back():
    session = ProtocolSession("RS232")

    result = set_trigger(
        session,
        mode="UART",
        details={"polarity": "NEGATIVE", "baud_rate": 115200, "parity": "EVEN", "stop_bits": 1.5},
    )

    assert result["protocol"] == "RS232"
    assert result["details"]["polarity"] == "NEGATIVE"
    assert result["details"]["baud"] == 115200
    assert result["details"]["parity"] == "EVEN"
    assert result["details"]["stop_bits"] == 1.5


def test_invalid_dependent_detail_is_rejected_without_writes():
    session = ProtocolSession("SPI")

    with pytest.raises(ValueError, match="timeout_s.*TIMEOUT"):
        set_trigger(session, details={"condition": "CS", "timeout_s": 1e-6})
    assert session.writes == []


class NonSerialSession:
    """Stateful fake for representative named non-serial trigger details."""

    def __init__(self, mode):
        self.mode = mode
        self.writes = []
        self.queries = []
        self.values = {
            ":TRIGger:MODE": mode, ":TRIGger:SWEep": "AUTO", ":TRIGger:STATus": "STOP", ":TRIGger:HOLDoff": "1E-6",
        }
        prefix = {
            "PULSE": ":TRIGger:PULSe:", "VIDEO": ":TRIGger:VIDeo:", "PATTERN": ":TRIGger:PATTern:",
            "WINDOW": ":TRIGger:WINDows:", "DELAY": ":TRIGger:DELay:", "SETUP": ":TRIGger:SHOLd:",
        }[mode]
        defaults = {
            "PULSE": {"SOURce": "CHAN1", "POLarity": "POS", "WHEN": "GRE", "LWIDth": "1E-6", "LEVel": "0"},
            "VIDEO": {"SOURce": "CHAN1", "POLarity": "POS", "MODE": "ALIN", "STANdard": "NTSC", "LEVel": "0"},
            "PATTERN": {"SOURce": "CHAN1", "PATTern": "H,X,L,X", "LEVel CHAN1": "0", "LEVel CHAN3": "0"},
            "WINDOW": {"SOURce": "CHAN1", "SLOPe": "POS", "POSition": "ENT", "TIME": "1E-6", "ALEVel": "1", "BLEVel": "-1"},
            "DELAY": {"SA": "CHAN1", "ASLop": "POS", "SB": "D0", "BSLop": "NEG", "TYPE": "GLES", "TLOWer": "1E-6", "TUPPer": "2E-6", "ALEVel": "0", "BLEVel": "0"},
            "SETUP": {"DSRC": "CHAN2", "CSRC": "CHAN1", "SLOPe": "POS", "PATTern": "H", "TYPE": "SETH", "STIMe": "2E-6", "HTIMe": "1E-6", "DLEVel": "0", "CLEVel": "0"},
        }[mode]
        for command, value in defaults.items():
            self.values[prefix + command] = value

    def query(self, command):
        self.queries.append(command)
        key = command.replace("?", "", 1)
        if key in self.values:
            return self.values[key]
        if command.startswith(":TRIGger:PATTern:LEVel?"):
            return "0"
        if command in {f":CHANnel{i}:SCALe?" for i in range(1, 5)}:
            return "1"
        if command in {f":CHANnel{i}:OFFSet?" for i in range(1, 5)}:
            return "0"
        raise AssertionError(f"unexpected query: {command}")

    def write(self, command):
        self.writes.append(command)
        head, value = command.rsplit(" ", 1)
        if head.endswith(":LEVel") and "," in value:
            source, level = value.split(",", 1)
            self.values[head + " " + source] = level
        else:
            self.values[head] = value


def test_nonserial_pulse_and_video_details_are_named_and_ordered():
    pulse = NonSerialSession("PULSE")
    result = set_trigger(pulse, details={"condition": "IN_RANGE", "lower_width_s": 2e-6, "upper_width_s": 5e-6, "level": 0.25})
    assert result["details"]["condition"] == "IN_RANGE"
    assert pulse.writes[:4] == [
        ":TRIGger:PULSe:WHEN GLESs", ":TRIGger:PULSe:LWIDth 2e-06", ":TRIGger:PULSe:UWIDth 5e-06", ":TRIGger:PULSe:LEVel 0.25",
    ]

    video = NonSerialSession("VIDEO")
    result = set_trigger(video, details={"standard": "720P60", "sync_type": "LINE", "line": 27, "level": 0.1})
    assert result["details"]["line"] == 27
    assert video.writes[:4] == [
        ":TRIGger:VIDeo:STANdard 720P60", ":TRIGger:VIDeo:MODE LINE", ":TRIGger:VIDeo:LINE 27", ":TRIGger:VIDeo:LEVel 0.1",
    ]


def test_nonserial_pattern_and_window_use_structured_fields():
    pattern = NonSerialSession("PATTERN")
    result = set_trigger(pattern, details={"channel_pattern": {"CHAN1": "R", "CHAN2": "L", "CHAN3": "X", "CHAN4": "H"}, "level": 0.2})
    assert result["details"]["pattern"] == {"CHAN1": "R", "CHAN2": "L", "CHAN3": "X", "CHAN4": "H"}
    assert ":TRIGger:PATTern:PATTern R,L,X,H" in pattern.writes

    window = NonSerialSession("WINDOW")
    result = set_trigger(window, details={"slope": "BOTH", "position": "TIME", "time_s": 3e-6, "lower_level": -0.5, "upper_level": 0.5})
    assert result["details"]["position"] == "TIME"
    assert ":TRIGger:WINDows:POSition TIME" in window.writes


def test_nonserial_timing_and_setup_details_and_invalid_bound():
    delay = NonSerialSession("DELAY")
    result = set_trigger(delay, details={"condition": "OUT_RANGE", "lower_time_s": 2e-6, "upper_time_s": 4e-6, "source_b": "D2"})
    assert result["details"]["source_b"] == "D2"
    assert delay.writes.index(":TRIGger:DELay:SB D2") < delay.writes.index(":TRIGger:DELay:TYPE GOUT")

    setup = NonSerialSession("SETUP")
    result = set_trigger(setup, details={"condition": "SETUP", "setup_time_s": 3e-6, "data_type": "LOW"})
    assert result["details"]["pattern"] == "LOW"
    assert ":TRIGger:SHOLd:TYPE SETup" in setup.writes

    invalid = NonSerialSession("PULSE")
    with pytest.raises(ValueError, match="lower limit"):
        set_trigger(invalid, details={"condition": "IN_RANGE", "lower_width_s": 5e-6, "upper_width_s": 1e-6})
    assert invalid.writes == []


class CommunicationFamilySession:
    """Query/write fake covering one documented state for each new family."""

    def __init__(self, mode):
        self.mode = mode
        self.writes = []
        self.queries = []
        self.values = {
            ":TRIGger:MODE": mode,
            ":TRIGger:SWEep": "AUTO",
            ":TRIGger:STATus": "STOP",
            ":TRIGger:CAN:SOURce": "CHAN1", ":TRIGger:CAN:LEVel": "0", ":TRIGger:CAN:BAUD": "500000",
            ":TRIGger:CAN:STYPe": "H", ":TRIGger:CAN:WHEN": "DATaframe", ":TRIGger:CAN:SPOint": "50",
            ":TRIGger:CAN:DWIDth": "1", ":TRIGger:CAN:DATA": "0", ":TRIGger:CAN:CURRbit": "0", ":TRIGger:CAN:CODE": "255",
            ":TRIGger:LIN:SOURce": "CHAN1", ":TRIGger:LIN:LEVel": "0", ":TRIGger:LIN:STANdard": "BOTH", ":TRIGger:LIN:BAUD": "9600",
            ":TRIGger:LIN:SAMPlepoint": "50", ":TRIGger:LIN:WHEN": "IDData", ":TRIGger:LIN:ID": "0", ":TRIGger:LIN:DATA": "0",
            ":TRIGger:LIN:CURRbit": "0", ":TRIGger:LIN:CODE": "255",
            ":TRIGger:IIS:ALIGnment": "IIS", ":TRIGger:IIS:SOURce:CLOCk": "CHAN1", ":TRIGger:IIS:SOURce:DATA": "CHAN3", ":TRIGger:IIS:SOURce:WSELect": "CHAN2",
            ":TRIGger:IIS:CLEVel": "0", ":TRIGger:IIS:SLEVel": "0", ":TRIGger:IIS:DLEVel": "0", ":TRIGger:IIS:WIDTh": "16", ":TRIGger:IIS:UWIDth": "8",
            ":TRIGger:IIS:CLOCk:SLOPe": "POS", ":TRIGger:IIS:WHEN": "EQUal", ":TRIGger:IIS:AUDio": "LEFT", ":TRIGger:IIS:DATA": "0",
            ":TRIGger:FLEXray:SOURce": "CHAN1", ":TRIGger:FLEXray:LEVel": "0", ":TRIGger:FLEXray:CH": "A", ":TRIGger:FLEXray:BAUD": "10000000",
            ":TRIGger:FLEXray:WHEN": "FRAMe", ":TRIGger:FLEXray:FRAMe": "ANY", ":TRIGger:FLEXray:DEFine": "CYCLe", ":TRIGger:FLEXray:IDCmp": "EQU",
            ":TRIGger:FLEXray:CYCComp": "EQU", ":TRIGger:FLEXray:MINCy": "0", ":TRIGger:FLEXray:MAXCy": "0",
            ":TRIGger:M1553:SOURce": "CHAN1", ":TRIGger:M1553:WHEN": "DATA", ":TRIGger:M1553:POLarity": "POS", ":TRIGger:M1553:WINDow": "TA",
            ":TRIGger:M1553:ALEVel": "1", ":TRIGger:M1553:BLEVel": "0", ":TRIGger:M1553:DATComp": "EQU", ":TRIGger:M1553:DATValue": "0",
            ":TRIGger:M1553:DMIN": "0", ":TRIGger:M1553:DMAX": "0", ":TRIGger:M1553:CODE": "255",
        }

    def query(self, command):
        self.queries.append(command)
        key = command[:-1] if command.endswith("?") else command
        if key in {":TRIGger:MODE", ":TRIGger:SWEep", ":TRIGger:STATus"}:
            return self.values[key]
        if command in {f":CHANnel{i}:SCALe?" for i in range(1, 5)}:
            return "1"
        if command in {f":CHANnel{i}:OFFSet?" for i in range(1, 5)}:
            return "0"
        if key not in self.values:
            raise AssertionError(f"unexpected query: {command}")
        return self.values[key]

    def write(self, command):
        self.writes.append(command)
        head, value = command.rsplit(" ", 1)
        self.values[head] = value


def test_can_details_cover_data_width_and_bit_fields():
    session = CommunicationFamilySession("CAN")
    result = set_trigger(session, details={"condition": "DATA_FRAME", "data_width": 2, "data": 0x1234, "current_bit": 7, "bit_code": 1})
    assert result["protocol"] == "CAN"
    assert result["details"]["data"] == 0x1234
    assert session.writes[:4] == [
        ":TRIGger:CAN:DWIDth 2", ":TRIGger:CAN:DATA 4660", ":TRIGger:CAN:CURRbit 7", ":TRIGger:CAN:CODE 1",
    ]


def test_lin_details_cover_id_data_condition():
    session = CommunicationFamilySession("LIN")
    result = set_trigger(session, details={"condition": "ID_DATA", "id": 21, "data": 0xAB})
    assert result["details"]["condition"] == "ID_DATA"
    assert result["details"]["id"] == 21
    assert ":TRIGger:LIN:ID 21" in session.writes


def test_i2s_details_cover_sources_width_and_audio():
    session = CommunicationFamilySession("IIS")
    result = set_trigger(session, details={"condition": "EQUAL", "width": 12, "user_width": 10, "data": 0x3FF, "audio": "RIGHT"})
    assert result["protocol"] == "I2S"
    assert result["details"]["width"] == 12
    assert result["details"]["audio"] == "RIGHT"


def test_flexray_details_cover_cycle_selection():
    session = CommunicationFamilySession("FLEXRAY")
    result = set_trigger(session, details={"condition": "FRAME", "define": "CYCLE", "cycle_comparison": "IN_RANGE", "min_cycle": 2, "max_cycle": 9})
    assert result["details"]["define"] == "CYCLE"
    assert result["details"]["max_cycle"] == 9
    assert session.writes.index(":TRIGger:FLEXray:MINCy 2") < session.writes.index(":TRIGger:FLEXray:MAXCy 9")


def test_m1553_details_cover_data_word_and_per_bit_fields():
    session = CommunicationFamilySession("M1553")
    result = set_trigger(session, details={"condition": "DATA", "data_value": 0x1234, "data_min_bit": 3, "data_max_bit": 5, "bit_code": 1})
    assert result["details"]["data_value"] == 0x1234
    assert result["details"]["data_max_bit"] == 5
    assert ":TRIGger:M1553:CODE 1" in session.writes


def test_flexray_rejects_invalid_combined_cycle_range_without_writes():
    session = CommunicationFamilySession("FLEXRAY")
    with pytest.raises(ValueError, match="max_cycle"):
        set_trigger(session, details={"condition": "FRAME", "define": "CYCLE", "min_cycle": 20, "max_cycle": 10})
    assert session.writes == []
