import pytest

from rigol_mcp.mho98.bode import bode_action, get_bode, set_bode


class FakeBodeSession:
    def __init__(self, *, running=False):
        self.state = {
            "dg": "1",
            "afg100": "1",
            "afg50": "0",
            "bnd": "0",
            "enabled": "0",
            "running": "1" if running else "0",
            "sweep_type": "LOG",
            "input": "CHAN1",
            "output": "CHAN1",
            "start": "100",
            "stop": "1000000",
            "points": "10",
            "amplitude": {"ALL": "0.2", "1K": "0.3"},
            "gain": "1",
            "phase": "1",
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
        if key == ":BODEPLOT:ENABLE?":
            return self.state["enabled"]
        if key == ":BODEPLOT:RUNSTOP?":
            return self.state["running"]
        if key == ":BODEPLOT:SWEEPTYPE?":
            return self.state["sweep_type"]
        if key == ":BODEPLOT:REF:IN?":
            return self.state["input"]
        if key == ":BODEPLOT:REF:OUT?":
            return self.state["output"]
        if key == ":BODEPLOT:START?":
            return self.state["start"]
        if key == ":BODEPLOT:STOP?":
            return self.state["stop"]
        if key == ":BODEPLOT:POINTS?":
            return self.state["points"]
        if key.startswith(":BODEPLOT:VOLTAGE? "):
            return self.state["amplitude"].get(key.rsplit(" ", 1)[1], self.state["amplitude"]["ALL"])
        if key == ":BODEPLOT:GAinCURVE:ENABLE?".upper():
            return self.state["gain"]
        if key == ":BODEPLOT:PHASECURVE:ENABLE?":
            return self.state["phase"]
        raise AssertionError(f"unexpected query: {command}")

    def write(self, command):
        self.writes.append(command)
        head, value = command.split(" ", 1)
        key = head.upper()
        value = value.strip()
        if key.endswith(":ENABLE"):
            self.state["enabled"] = value
        elif key.endswith(":RUNSTOP"):
            self.state["running"] = value
        elif key.endswith(":SWEEPTYPE"):
            self.state["sweep_type"] = value
        elif key.endswith(":REF:IN"):
            self.state["input"] = "CHAN" + value.upper().rsplit("CHAN", 1)[1]
        elif key.endswith(":REF:OUT"):
            self.state["output"] = "CHAN" + value.upper().rsplit("CHAN", 1)[1]
        elif key.endswith(":START"):
            self.state["start"] = value
        elif key.endswith(":STOP"):
            self.state["stop"] = value
        elif key.endswith(":POINTS"):
            self.state["points"] = value
        elif key.endswith(":VOLTAGE"):
            amplitude_range, amplitude = value.split(",", 1)
            self.state["amplitude"][amplitude_range.upper()] = amplitude
        elif key.endswith(":GAINCURVE:ENABLE"):
            self.state["gain"] = value
        elif key.endswith(":PHASECURVE:ENABLE"):
            self.state["phase"] = value
        else:
            raise AssertionError(f"unexpected write: {command}")


def test_config_readback_preserves_omitted_fields_and_writes_no_runstop():
    session = FakeBodeSession()

    result = set_bode(session, enabled=True, start_hz=200, stop_hz=20_000, amplitude_v=0.5)

    assert result["enabled"] is True
    assert result["start_hz"] == 200
    assert result["stop_hz"] == 20_000
    assert result["amplitude_v"] == 0.5
    assert result["points_per_decade"] == 10
    assert not any("RUNSTOP" in command.upper() for command in session.writes)


def test_invalid_frequency_pair_and_running_gain_setting_refuse_before_writes():
    session = FakeBodeSession(running=True)
    with pytest.raises(ValueError, match="stop_hz / 10"):
        set_bode(session, start_hz=2_000, stop_hz=10_000)
    assert session.writes == []

    with pytest.raises(ValueError, match="require Bode operating status STOP"):
        set_bode(session, gain_enabled=False)
    assert session.writes == []


def test_start_and_stop_are_explicit_actions():
    session = FakeBodeSession()

    result = bode_action(session, action="START")
    assert result["action"] == "START"
    assert result["running"] is True
    assert result["warning"].startswith("START may drive")
    assert session.writes == [":BODeplot:RUNStop 1"]

    bode_action(session, action="STOP")
    assert session.writes[-1] == ":BODeplot:RUNStop 0"


def test_dg_zero_afg50_license_allows_bode_readback_with_discrepancy():
    session = FakeBodeSession()
    session.state.update({"dg": "0", "afg100": "0", "afg50": "1"})
    result = get_bode(session)
    assert result["dg_available"] is False
    assert result["dg_status"] == "0"
    assert result["bode_option_status"] == {"AFG100": "0", "AFG50": "1"}
    assert "DGSTatus? reported 0" in result["capability_warning"]
    assert result["enabled"] is False
    assert result["running"] is False
    assert session.writes == []


def test_dg_zero_with_no_bode_license_is_rejected():
    session = FakeBodeSession()
    session.state.update({"dg": "0", "afg100": "0", "afg50": "0", "bnd": "0"})
    with pytest.raises(ValueError, match="all-negative"):
        get_bode(session)
    assert session.writes == []
