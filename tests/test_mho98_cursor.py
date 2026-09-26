import pytest

from rigol_mcp.mho98.cursor import get_cursor, read_cursor, set_cursor


class FakeSession:
    def __init__(self, mode="OFF", timebase="MAIN"):
        self.state = {
            ":CURSor:MODE": mode,
            ":CURSor:MEASure:INDicator": "0",
            ":TIMebase:MODE": timebase,
            ":CURSor:MANual:TYPE": "TIME",
            ":CURSor:MANual:SOURce": "CHAN1",
            ":CURSor:MANual:TUNit": "SEC",
            ":CURSor:MANual:VUNit": "SOUR",
            ":CURSor:MANual:CAX": "-1e-3",
            ":CURSor:MANual:CAY": "0.1",
            ":CURSor:MANual:CBX": "1e-3",
            ":CURSor:MANual:CBY": "0.2",
            ":CURSor:TRACk:SOURce1": "CHAN1",
            ":CURSor:TRACk:SOURce2": "CHAN2",
            ":CURSor:TRACk:MODE": "X",
            ":CURSor:TRACk:CAX": "-2e-3",
            ":CURSor:TRACk:CAY": "0.2",
            ":CURSor:TRACk:CBX": "2e-3",
            ":CURSor:TRACk:CBY": "0.3",
            ":CURSor:XY:AX": "-1.0",
            ":CURSor:XY:AY": "-2.0",
            ":CURSor:XY:BX": "1.0",
            ":CURSor:XY:BY": "2.0",
            ":CHANnel1:DISPlay": "1",
            ":CHANnel2:DISPlay": "1",
            ":MATH1:DISPlay": "1",
        }
        self.results = {}
        self.queries = []
        self.writes = []

    def query(self, command):
        self.queries.append(command)
        if command == ":CURSor:MODE?":
            return self.state[":CURSor:MODE"]
        key = command.removesuffix("?")
        if key in self.results:
            return self.results[key]
        if key not in self.state:
            raise AssertionError(f"unexpected query: {command}")
        return self.state[key]

    def write(self, command):
        self.writes.append(command)
        head, value = command.split(" ", 1)
        if head == ":CURSor:MODE":
            self.state[head] = {"MANual": "MAN", "TRACk": "TRAC", "OFF": "OFF", "XY": "XY"}[value]
        else:
            self.state[head] = value


def test_manual_positions_are_distinct_from_physical_results():
    session = FakeSession()
    session.results.update(
        {
            ":CURSor:MANual:AXValue": "1.25e-3",
            ":CURSor:MANual:AYValue": "0.75",
            ":CURSor:MANual:BXValue": "2.25e-3",
            ":CURSor:MANual:BYValue": "1.25",
            ":CURSor:MANual:XDELta": "1e-3",
            ":CURSor:MANual:IXDelta": "1e3",
            ":CURSor:MANual:YDELta": "0.5",
        }
    )

    configured = set_cursor(session, mode="MANUAL", manual_cax=0.0015)
    assert configured["manual"]["screen_positions"]["a"]["x_s"] == 0.0015
    assert session.writes == [":CURSor:MODE MANual", ":CURSor:MANual:CAX 0.0015"]

    result = read_cursor(session)
    assert result["readings"]["ax"] == {"valid": True, "value": 0.00125, "unit": "s", "raw": "1.25e-3"}
    assert result["readings"]["delta_y"]["unit"] == "source"


def test_track_reads_all_track_results_without_querying_other_modes():
    session = FakeSession(mode="TRAC")
    session.results.update(
        {
            ":CURSor:TRACk:AXValue": "0.1",
            ":CURSor:TRACk:AYValue": "0.2",
            ":CURSor:TRACk:BXValue": "0.3",
            ":CURSor:TRACk:BYValue": "0.4",
            ":CURSor:TRACk:XDELta": "0.2",
            ":CURSor:TRACk:YDELta": "0.2",
            ":CURSor:TRACk:IXDelta": "5",
        }
    )

    result = read_cursor(session)
    assert set(result["readings"]) == {"ax", "ay", "bx", "by", "delta_x", "delta_y", "reciprocal_delta_x"}
    assert ":CURSor:MANual:TYPE?" not in session.queries
    assert result["readings"]["reciprocal_delta_x"]["unit"] == "Hz"


def test_xy_requires_existing_xy_timebase_and_preserves_voltage_units():
    session = FakeSession(mode="XY", timebase="XY")
    session.results.update(
        {
            ":CURSor:XY:AXValue": "-0.5",
            ":CURSor:XY:AYValue": "-1.5",
            ":CURSor:XY:BXValue": "0.5",
            ":CURSor:XY:BYValue": "1.5",
            ":CURSor:XY:XDELta": "1",
            ":CURSor:XY:YDELta": "3",
        }
    )

    result = set_cursor(session, xy_ax=-0.75)
    assert result["xy"]["screen_positions"]["a"]["x_v"] == -0.75
    assert read_cursor(session)["readings"]["delta_x"]["unit"] == "V"
    assert ":TIMebase:MODE?" in session.queries


def test_mode_specific_field_is_rejected_before_any_write():
    session = FakeSession(mode="MAN")
    with pytest.raises(ValueError, match="track_cax"):
        set_cursor(session, track_cax=1.0)
    assert session.writes == []
