import math

import pytest

from rigol_mcp.mho98.generator import (
    get_generator,
    set_generator,
    set_generator_output,
)


class FakeGeneratorSession:
    def __init__(self):
        self.state = {
            "dg": "1",
            "afg100": "0",
            "afg50": "0",
            "bnd": "0",
            "output": "1",
            "waveform": "SIN",
            "frequency": "1000",
            "period": "0.001",
            "phase": "0",
            "duty": "50",
            "symmetry": "50",
            "amplitude": "2",
            "offset": "0",
            "high": "1",
            "low": "-1",
            "load": "OMEG",
            "arbitrary_path": "D:/old.csv",
            "mod_state": "0",
            "mod_type": "AM",
            "mod_frequency": "100",
            "mod_waveform": "SIN",
            "am_depth": "100",
            "fm_deviation": "1000",
            "pm_deviation": "90",
        }
        self.writes = []

    def query(self, command):
        key = command.strip().upper()
        if key == ":SYSTEM:DGSTATUS?":
            return self.state["dg"]
        if key == ":SYSTEM:OPTION:STATUS? AFG100":
            return self.state["afg100"]
        if key == ":SYSTEM:OPTION:STATUS? AFG50":
            return self.state["afg50"]
        if key == ":SYSTEM:OPTION:STATUS? BND":
            return self.state["bnd"]
        if key.endswith(":OUTPUT:STATE?"):
            return self.state["output"]
        if ":MOD:" in key and key.endswith(":INTERNAL:FUNCTION?"):
            return self.state["mod_waveform"]
        if key.endswith(":FUNCTION?"):
            return self.state["waveform"]
        if key.endswith(":FREQUENCY?"):
            return self.state["frequency"]
        if key.endswith(":PERIOD?"):
            return self.state["period"]
        if key.endswith(":PHASE?"):
            return self.state["phase"]
        if key.endswith(":FUNCTION:SQUARE:DUTY?"):
            return self.state["duty"]
        if key.endswith(":FUNCTION:RAMP:SYMMETRY?"):
            return self.state["symmetry"]
        if key.endswith(":VOLTAGE:AMPLITUDE?"):
            return self.state["amplitude"]
        if key.endswith(":VOLTAGE:OFFSET?"):
            return self.state["offset"]
        if key.endswith(":VOLTAGE:HIGH?"):
            return self.state["high"]
        if key.endswith(":VOLTAGE:LOW?"):
            return self.state["low"]
        if key.endswith(":IMPEDANCE?"):
            return self.state["load"]
        if key.endswith(":LOAD:ARBITRARY?"):
            return self.state["arbitrary_path"]
        if key.endswith(":MOD:STATE?"):
            return self.state["mod_state"]
        if key.endswith(":MOD:TYPE?"):
            return self.state["mod_type"]
        if ":MOD:" in key and key.endswith(":INTERNAL:FREQUENCY?"):
            return self.state["mod_frequency"]
        if key.endswith(":MOD:AM:DEPTH?"):
            return self.state["am_depth"]
        if key.endswith(":MOD:FM:DEVIATION?"):
            return self.state["fm_deviation"]
        if key.endswith(":MOD:PM:DEVIATION?"):
            return self.state["pm_deviation"]
        raise AssertionError(f"unexpected query: {command}")

    def write(self, command):
        self.writes.append(command)
        if " " not in command:
            return
        head, value = command.rsplit(" ", 1)
        key = head.upper()
        if key.endswith(":OUTPUT:STATE"):
            self.state["output"] = value
        elif ":MOD:" in key and key.endswith(":INTERNAL:FUNCTION"):
            self.state["mod_waveform"] = value
        elif key.endswith(":FUNCTION"):
            self.state["waveform"] = {
                "SINUSOID": "SIN",
                "SQUARE": "SQU",
                "RAMP": "RAMP",
                "NOISE": "NOIS",
            }.get(value.upper(), value.upper())
        elif key.endswith(":FREQUENCY"):
            self.state["frequency"] = value
            self.state["period"] = str(1 / float(value))
        elif key.endswith(":PERIOD"):
            self.state["period"] = value
            self.state["frequency"] = str(1 / float(value))
        elif key.endswith(":PHASE"):
            self.state["phase"] = value
        elif key.endswith(":FUNCTION:SQUARE:DUTY"):
            self.state["duty"] = value
        elif key.endswith(":FUNCTION:RAMP:SYMMETRY"):
            self.state["symmetry"] = value
        elif key.endswith(":VOLTAGE:AMPLITUDE"):
            self.state["amplitude"] = value
            center = float(self.state["offset"])
            half = float(value) / 2
            self.state["low"], self.state["high"] = str(center - half), str(center + half)
        elif key.endswith(":VOLTAGE:OFFSET"):
            self.state["offset"] = value
            center = float(value)
            half = float(self.state["amplitude"]) / 2
            self.state["low"], self.state["high"] = str(center - half), str(center + half)
        elif key.endswith(":VOLTAGE:HIGH"):
            self.state["high"] = value
        elif key.endswith(":VOLTAGE:LOW"):
            self.state["low"] = value
        elif key.endswith(":IMPEDANCE"):
            self.state["load"] = value
        elif key.endswith(":LOAD:ARBITRARY"):
            self.state["arbitrary_path"] = value
        elif key.endswith(":MOD:TYPE"):
            self.state["mod_type"] = value
        elif ":MOD:" in key and key.endswith(":INTERNAL:FREQUENCY"):
            self.state["mod_frequency"] = value
        elif key.endswith(":MOD:AM:DEPTH"):
            self.state["am_depth"] = value
        elif key.endswith(":MOD:FM:DEVIATION"):
            self.state["fm_deviation"] = value
        elif key.endswith(":MOD:PM:DEVIATION"):
            self.state["pm_deviation"] = value
        elif key.endswith(":MOD:STATE"):
            self.state["mod_state"] = value
        elif key.endswith(":PHASE:SYNCHRONIZE"):
            pass
        else:
            raise AssertionError(f"unexpected write: {command}")


def test_basic_sine_settings_and_effective_readback():
    session = FakeGeneratorSession()

    result = set_generator(
        session,
        1,
        waveform="SIN",
        frequency_hz=2_000,
        phase_deg=30,
        amplitude_vpp=4,
        offset_v=0.5,
    )

    assert result["waveform"] == "SIN"
    assert result["frequency_hz"] == 2_000
    assert result["phase_deg"] == 30
    assert result["amplitude_vpp"] == 4
    assert result["offset_v"] == 0.5
    assert result["output_enabled"] is True
    assert not any("OUTPUT:STATE" in command.upper() for command in session.writes)


def test_square_duty_is_conditional_and_written_after_waveform():
    session = FakeGeneratorSession()

    result = set_generator(session, 1, waveform="SQU", square_duty_percent=25)

    assert result["waveform"] == "SQU"
    assert result["square_duty_percent"] == 25
    assert [command.split(" ", 1)[0] for command in session.writes] == [
        ":SOURce1:FUNCtion",
        ":SOURce1:FUNCtion:SQUare:DUTY",
    ]


def test_representative_fm_configuration():
    session = FakeGeneratorSession()

    result = set_generator(
        session,
        1,
        modulation_type="FM",
        modulation_enabled=True,
        modulation_frequency_hz=500,
        modulation_waveform="TRI",
        fm_deviation_hz=100,
    )

    assert result["modulation_enabled"] is True
    assert result["modulation_type"] == "FM"
    assert result["modulation_frequency_hz"] == 500
    assert result["modulation_waveform"] == "TRI"
    assert result["fm_deviation_hz"] == 100
    assert result["am_depth_percent"] is None
    assert any(":MOD:FM:DEViation" in command for command in session.writes)


def test_invalid_combined_voltage_frequency_is_rejected_before_writes():
    session = FakeGeneratorSession()
    with pytest.raises(ValueError, match="amplitude_vpp"):
        set_generator(session, 1, frequency_hz=60e6, amplitude_vpp=6, load="50ohm")
    assert session.writes == []


def test_output_tool_requires_real_bool_and_is_the_only_output_toggle():
    session = FakeGeneratorSession()
    with pytest.raises(ValueError, match="real boolean"):
        set_generator_output(session, 1, "true")
    assert session.writes == []

    set_generator(session, 1, amplitude_vpp=3)
    assert session.state["output"] == "1"
    assert not any("OUTPUT:STATE" in command.upper() for command in session.writes)
    result = set_generator_output(session, 1, False)
    assert result["output_enabled"] is False
    assert session.writes[-1] == ":SOURce1:OUTPut:STATe 0"


def test_get_skips_frequency_and_inapplicable_modulation_queries_for_dc():
    session = FakeGeneratorSession()
    session.state.update({"waveform": "DC", "mod_state": "0"})
    result = get_generator(session, 1)
    assert result["frequency_hz"] is None
    assert "frequency_hz" in result["unavailable"]
    assert result["modulation_frequency_hz"] is None


def test_dg_zero_afg50_license_allows_source_readback_and_limits_sine_frequency():
    session = FakeGeneratorSession()
    session.state.update({"dg": "0", "afg50": "1"})

    result = get_generator(session, 1)
    assert result["dg_available"] is False
    assert result["dg_status"] == "0"
    assert result["generator_option_status"] == {"AFG100": "0", "AFG50": "1", "BND": "0"}
    assert "DGSTatus? reported 0" in result["capability_warning"]
    assert result["output_enabled"] is True
    assert result["waveform"] == "SIN"
    assert result["generator_frequency_limit_hz"] == 50e6

    with pytest.raises(ValueError, match=r"5e\+07"):
        set_generator(session, 1, frequency_hz=50_000_001)
    assert session.writes == []

    result = set_generator(session, 1, frequency_hz=50e6)
    assert result["frequency_hz"] == 50e6
    assert result["dg_available"] is False


def test_dg_zero_with_no_generator_license_is_rejected():
    session = FakeGeneratorSession()
    session.state["dg"] = "0"
    with pytest.raises(ValueError, match="all-negative"):
        get_generator(session, 1)
    assert session.writes == []
