import pytest

from rigol_mcp.mho98.system import get_capabilities, get_system, read_instrument_error, set_system


class FakeSession:
    def __init__(self, responses, identity="RIGOL TECHNOLOGIES,MHO98,SN,FW"):
        self.responses = dict(responses)
        self.identity = identity
        self.queries = []
        self.writes = []

    def idn(self):
        self.queries.append("*IDN?")
        return self.identity

    def query(self, command):
        self.queries.append(command)
        if command not in self.responses:
            raise AssertionError(f"unexpected query: {command}")
        return self.responses[command]

    def write(self, command):
        self.writes.append(command)


def system_responses():
    return {
        ":SYSTem:AOUTput?": "TOUT",
        ":SYSTem:LANGuage?": "ENGL",
        ":SYSTem:BEEPer?": "0",
        ":SYSTem:DATE?": "2024,2,29",
        ":SYSTem:TIME?": "12,34,56",
        ":SYSTem:STIMe?": "1",
        ":SYSTem:PON?": "DEF",
        ":SYSTem:PSTatus?": "OPEN",
        ":SYSTem:LOCKed?": "0",
        ":SYSTem:LOWPower?": "0",
        ":SYSTem:AUToscale?": "1",
    }


def test_get_system_reads_settings_without_consuming_error_queue():
    session = FakeSession(system_responses() | {":SYSTem:ERRor?": '0,"No error"'})

    result = get_system(session)

    assert result["language"] == "ENGL"
    assert result["date"] == {"year": 2024, "month": 2, "day": 29}
    assert ":SYSTem:ERRor?" not in session.queries


def test_get_system_accepts_colon_delimited_time_response():
    session = FakeSession(system_responses() | {":SYSTem:TIME?": "05:42:51"})

    result = get_system(session)

    assert result["time"] == {"hours": 5, "minutes": 42, "seconds": 51}


def test_get_system_preserves_unknown_low_power_response():
    session = FakeSession(system_responses() | {":SYSTem:LOWPower?": "255"})

    result = get_system(session)

    assert result["low_power"] is None
    assert result["low_power_raw"] == "255"
    assert result["unavailable"] == ["low_power"]
    assert len(result["warnings"]) == 1
    assert "255" in result["warnings"][0]


def test_set_system_unrelated_field_preserves_unknown_low_power():
    session = FakeSession(system_responses() | {":SYSTem:LOWPower?": "255"})

    result = set_system(session, show_time=False)

    assert session.writes == [":SYSTem:STIMe 0"]
    assert result["low_power"] is None
    assert result["low_power_raw"] == "255"


def test_set_system_rejects_explicit_low_power_when_readback_is_unknown_before_writes():
    session = FakeSession(system_responses() | {":SYSTem:LOWPower?": "255"})

    with pytest.raises(ValueError, match="low_power.*unknown.*refusing"):
        set_system(session, low_power=True)

    assert session.writes == []


def test_set_system_validates_real_dates_and_writes_only_requested_fields():
    session = FakeSession(system_responses())
    result = set_system(
        session,
        date={"year": 2024, "month": 3, "day": 1},
        low_power=True,
        auto_gate=False,
    )
    assert session.writes == [
        ":SYSTem:DATE 2024,3,1",
        ":SYSTem:LOWPower 1",
        ":SYSTem:AUToscale 0",
    ]
    assert result["date"] == {"year": 2024, "month": 2, "day": 29}

    invalid = FakeSession(system_responses())
    with pytest.raises(ValueError, match="real calendar date"):
        set_system(invalid, date={"year": 2023, "month": 2, "day": 29}, low_power=True)
    assert invalid.writes == []
    assert invalid.queries == []


def test_capabilities_preserve_dg_option_disagreement_and_support_all():
    responses = {
        ":SYSTem:MODules?": "1,0,0,0,0",
        ":SYSTem:DGSTatus?": "0",
        ":SYSTem:RAMount?": "4",
        ":SYSTem:GAMount?": "10",
        ":SYSTem:VERSion?": "3.24",
    }
    options = ("BND", "AFG100", "AFG50", "AUDio", "CAN-FD", "FLEX", "AERO", "RLU-05", "BWU03T05", "BWU03T08", "BWU05T08")
    for option in options:
        responses[f":SYSTem:OPTion:STATus? {option}"] = "1" if option == "AFG50" else "0"
        responses[f":SYSTem:OPTion:VALid? {option}"] = "1" if option == "AFG50" else "0"

    result = get_capabilities(FakeSession(responses), options="all")
    assert result["idn"].startswith("RIGOL TECHNOLOGIES,MHO98")
    assert result["module_flags_raw"] == "1,0,0,0,0"
    assert result["dg_status"] == "0"
    assert result["option_status"]["AFG50"] == "1"
    assert len(result["option_status"]) == 11


def test_error_read_is_one_destructive_query_and_keeps_raw_reply():
    raw = '-113,"Undefined header; command cannot be found"'
    session = FakeSession({":SYSTem:ERRor?": raw})
    assert read_instrument_error(session) == {
        "code": -113,
        "message": "Undefined header; command cannot be found",
        "raw": raw,
    }
    assert session.queries == [":SYSTem:ERRor?"]
    assert session.writes == []
