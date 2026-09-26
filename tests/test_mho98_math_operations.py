import pytest

from rigol_mcp.mho98.math_operations import get_math, set_math


class FakeSession:
    def __init__(self, operator="ADD"):
        self.state = {
            "operator": operator, "display": "0", "grid": "FULL", "expand": "GND",
            "waveform": "MAIN", "label": "0", "title": "Math 1", "display_mode": "0",
            "source1": "CHAN1", "source2": "CHAN2", "logic1": "CHAN1", "logic2": "CHAN2",
            "scale": "1", "offset": "0", "invert": "0", "distance": "5", "sensitivity": "0.3",
            "threshold1": "0", "threshold2": "0", "threshold3": "0", "threshold4": "0",
            "filter_type": "LPAS", "w1": "100", "w2": "1000", "zoom": "0",
        }
        self.queries = []
        self.writes = []

    def query(self, command):
        self.queries.append(command)
        if command == ":TIMebase:DELay:ENABle?":
            return self.state["zoom"]
        if command.startswith(":CHANnel"):
            return "1" if command.endswith(":SCALe?") else "0"
        if command.endswith(":OPERator?"):
            return self.state["operator"]
        suffix = command.split(":MATH1:", 1)[-1]
        values = {
            "DISPlay?": "display", "GRID?": "grid", "EXPand?": "expand", "WAVetype?": "waveform",
            "LABel:SHOW?": "label", "WINDow:TITLe?": "title", "DISMode?": "display_mode",
            "SOURce1?": "source1", "SOURce2?": "source2", "LSOurce1?": "logic1", "LSOurce2?": "logic2",
            "SCALe?": "scale", "OFFSet?": "offset", "INVert?": "invert", "DISTance?": "distance",
            "SENSitivity?": "sensitivity", "THReshold1?": "threshold1", "THReshold2?": "threshold2",
            "THReshold3?": "threshold3", "THReshold4?": "threshold4", "FILTer:TYPE?": "filter_type",
            "FILTer:W1?": "w1", "FILTer:W2?": "w2",
        }
        if suffix in values:
            return self.state[values[suffix]]
        raise AssertionError(f"unexpected query: {command}")

    def write(self, command):
        self.writes.append(command)
        if command == ":MATH1:RESet":
            return
        head, value = command.rsplit(" ", 1)
        mapping = {
            ":MATH1:OPERator": "operator", ":MATH1:DISPlay": "display", ":MATH1:GRID": "grid",
            ":MATH1:EXPand": "expand", ":MATH1:WAVetype": "waveform", ":MATH1:LABel:SHOW": "label",
            ":MATH1:DISMode": "display_mode", ":MATH1:SOURce1": "source1", ":MATH1:SOURce2": "source2",
            ":MATH1:LSOurce1": "logic1", ":MATH1:LSOurce2": "logic2", ":MATH1:SCALe": "scale",
            ":MATH1:OFFSet": "offset", ":MATH1:INVert": "invert", ":MATH1:DISTance": "distance",
            ":MATH1:SENSitivity": "sensitivity", ":MATH1:THReshold1": "threshold1",
            ":MATH1:THReshold2": "threshold2", ":MATH1:THReshold3": "threshold3",
            ":MATH1:THReshold4": "threshold4", ":MATH1:FILTer:TYPE": "filter_type",
            ":MATH1:FILTer:W1": "w1", ":MATH1:FILTer:W2": "w2",
        }
        if head in mapping:
            self.state[mapping[head]] = value


def test_arithmetic_sources_and_effective_readback():
    session = FakeSession()
    result = set_math(session, math=1, operator="SUBTRACT", source1="CH1", source2="CHAN3", scale=2)

    assert result["operator"] == "SUBT"
    assert result["source1"] == "CHAN1"
    assert result["source2"] == "CHAN3"
    assert result["scale"] == 2.0
    assert session.writes == [
        ":MATH1:OPERator SUBT", ":MATH1:SOURce2 CHAN3", ":MATH1:SCALe 2",
    ]


def test_filter_pair_is_applied_in_a_safe_order():
    session = FakeSession()
    result = set_math(session, operator="BPAS", source1="CHAN2", cutoff1_hz=200, cutoff2_hz=800)

    assert result["filter_type"] == "BPAS"
    assert result["cutoff1_hz"] == 200.0
    assert result["cutoff2_hz"] == 800.0
    assert session.writes[-2:] == [":MATH1:FILTer:W1 200", ":MATH1:FILTer:W2 800"]


def test_function_and_logic_fields_are_operator_specific():
    function = FakeSession(operator="DIFF")
    function.state["distance"] = "9"
    result = set_math(function, distance=20, source1="CHAN4")
    assert result["operator"] == "DIFF"
    assert result["distance"] == 20
    assert "logic_source1" not in result

    logic = FakeSession(operator="AND")
    result = set_math(logic, logic_source1="D3", logic_source2="CHAN2", sensitivity=0.5, threshold1_v=1)
    assert result["logic_source1"] == "D3"
    assert result["logic_source2"] == "CHAN2"
    assert result["sensitivity"] == 0.5
    assert result["threshold1_v"] == 1.0
    assert "scale" not in result


def test_invalid_filter_pair_is_rejected_before_any_write():
    session = FakeSession()
    with pytest.raises(ValueError, match="cutoff1_hz.*cutoff2_hz"):
        set_math(session, operator="BPAS", cutoff1_hz=900, cutoff2_hz=100)
    assert session.writes == []
