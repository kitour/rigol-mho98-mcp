import pytest

from rigol_mcp.mho98.histogram import (
    get_histogram,
    histogram_action,
    read_histogram,
    set_histogram,
)


class FakeSession:
    def __init__(self, **overrides):
        self.state = {
            ":HISTogram:ENABle": "0",
            ":HISTogram:TYPE": "HOR",
            ":HISTogram:SOURce": "CHAN1",
            ":HISTogram:HEIGht": "2",
            ":HISTogram:RANGe:LEFT": "-0.004",
            ":HISTogram:RANGe:RIGHt": "0.004",
            ":HISTogram:RANGe:TOP": "3",
            ":HISTogram:RANGe:BOTTom": "-3",
            ":TIMebase:SCALe": "0.001",
            ":TIMebase:OFFSet": "0",
            ":CHANnel1:SCALe": "1",
            ":CHANnel1:OFFSet": "0",
            ":CHANnel2:SCALe": "2",
            ":CHANnel2:OFFSet": "1",
            ":HISTogram:STATistics:RESult": "[Sum:5.6khits,Peaks:14hits,Max:3.9us,Min:-4us,Pk_Pk:7.98us,Mean:-20ns,Median:-20ns,Mode:-4us,Bin width:20ns,Siqma:2.303us,meanPlusSigma:577.5,meanPlus2Sigma:1,meanPlus3Sigma:1]",
        }
        self.state.update(overrides)
        self.queries = []
        self.writes = []

    def query(self, command):
        self.queries.append(command)
        key = command.removesuffix("?")
        if key not in self.state:
            raise AssertionError(f"unexpected query: {command}")
        return self.state[key]

    def write(self, command):
        self.writes.append(command)
        head, value = command.split(" ", 1)
        self.state[head] = value


def test_configuration_is_conditional_and_readback_preserves_settings():
    session = FakeSession(**{":HISTogram:TYPE": "VERT"})

    result = get_histogram(session)

    assert result == {
        "enabled": False,
        "type": "VERT",
        "source": "CHAN1",
        "height": 2,
        "range": {"top": 3.0, "bottom": -3.0},
    }
    assert ":HISTogram:RANGe:LEFT?" not in session.queries
    assert ":HISTogram:RANGe:TOP?" in session.queries

    result = set_histogram(session, enabled=True, source="CH2", top=4, bottom=-2)

    assert session.writes == [
        ":HISTogram:SOURce CHAN2",
        ":HISTogram:RANGe:TOP 4",
        ":HISTogram:RANGe:BOTTom -2",
        ":HISTogram:ENABle 1",
    ]
    assert result["enabled"] is True
    assert result["source"] == "CHAN2"
    assert result["range"] == {"top": 4.0, "bottom": -2.0}


def test_range_pair_and_dynamic_limits_are_validated_before_writes():
    session = FakeSession()

    with pytest.raises(ValueError, match="left and right"):
        set_histogram(session, left=-0.001)
    assert session.writes == []

    with pytest.raises(ValueError, match="dynamic range"):
        set_histogram(session, left=-0.006, right=0.001)
    assert session.writes == []
    assert ":TIMebase:SCALe?" in session.queries

    with pytest.raises(ValueError, match="smaller"):
        set_histogram(session, left=0.002, right=0.001)
    assert session.writes == []


def test_statistics_parser_returns_structured_units_without_bin_query():
    session = FakeSession(**{":HISTogram:ENABle": "1"})

    result = read_histogram(session)
    statistics = result["statistics"]

    assert result["valid"] is True
    assert statistics["sum"] == {"value": 5600.0, "unit": "hits", "raw": "5.6khits"}
    assert statistics["max"] == {"value": 3.9e-6, "unit": "s", "raw": "3.9us"}
    assert statistics["sigma"]["unit"] == "s"
    assert statistics["mean_plus_2sigma"]["unit"] is None
    assert ":HISTogram:BINs?" not in session.queries


def test_csv_save_uses_instrument_storage_and_reset_is_fail_closed():
    session = FakeSession()

    result = histogram_action(session, action="save_csv", path="D:/histogram.csv")
    assert result == {"action": "save_csv", "path": "D:/histogram.csv", "saved": True}
    assert session.writes == [":HISTogram:SAVE:CSV D:/histogram.csv"]

    with pytest.raises(ValueError, match="C:/ or D:/"):
        histogram_action(session, action="save_csv", path="/tmp/histogram.csv")
    assert session.writes == [":HISTogram:SAVE:CSV D:/histogram.csv"]

    with pytest.raises(ValueError, match="ambiguous"):
        histogram_action(session, action="reset")
    assert session.writes == [":HISTogram:SAVE:CSV D:/histogram.csv"]
