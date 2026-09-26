import math

import pytest

from rigol_mcp.mho98.timebase import get_timebase, set_timebase


class FakeSession:
    def __init__(self):
        self.state = {
            "mode": "MAIN",
            "trigger_status": "STOP",
            "xy_enabled": "0",
            "main_scale": "0.001",
            "main_offset": "0",
            "zoom_enabled": "0",
            "zoom_scale": "0.0001",
            "zoom_offset": "0",
            "auto_roll": "0",
            "xy_x": "CHAN1",
            "xy_y": "CHAN2",
            "xy_grid": "FULL",
            "reference_mode": "CENT",
            "reference_position": "0",
            "fine_scale": "0",
        }
        self.writes = []
        self.queries = []

    @staticmethod
    def _key(command):
        parts = command.split(":")
        key = parts[-1].removesuffix("?").upper()
        if len(parts) >= 2 and parts[-2].upper() in {"MAIN", "DELAY", "XY", "HREFERENCE", "TRIGGER"}:
            key = parts[-2].upper() + ":" + key
        return key

    def query(self, command):
        self.queries.append(command)
        key = self._key(command)
        if key == "MODE":
            # MHO98 reports MAIN for MODE? while XY is enabled.
            return "MAIN" if self.state["xy_enabled"] in {"1", "ON"} else self.state["mode"]
        if key == "TRIGGER:STATUS":
            return self.state["trigger_status"]
        mapping = {
            "MAIN:SCALE": "main_scale",
            "MAIN:OFFSET": "main_offset",
            "DELAY:ENABLE": "zoom_enabled",
            "DELAY:SCALE": "zoom_scale",
            "DELAY:OFFSET": "zoom_offset",
            "ROLL": "auto_roll",
            "XY:ENABLE": "xy_enabled",
            "XY:X": "xy_x",
            "XY:Y": "xy_y",
            "XY:GRID": "xy_grid",
            "HREFERENCE:MODE": "reference_mode",
            "HREFERENCE:POSITION": "reference_position",
            "VERNIER": "fine_scale",
            "TRIGGER:STATUS": "trigger_status",
        }
        return self.state[mapping[key]]

    def write(self, command):
        self.writes.append(command)
        head, value = command.rsplit(" ", 1)
        key = self._key(head)
        mapping = {
            "MODE": "mode",
            "MAIN:SCALE": "main_scale",
            "MAIN:OFFSET": "main_offset",
            "DELAY:ENABLE": "zoom_enabled",
            "DELAY:SCALE": "zoom_scale",
            "DELAY:OFFSET": "zoom_offset",
            "ROLL": "auto_roll",
            "XY:ENABLE": "xy_enabled",
            "XY:X": "xy_x",
            "XY:Y": "xy_y",
            "XY:GRID": "xy_grid",
            "HREFERENCE:MODE": "reference_mode",
            "HREFERENCE:POSITION": "reference_position",
            "VERNIER": "fine_scale",
            "TRIGGER:STATUS": "trigger_status",
        }
        self.state[mapping[key]] = value


def test_get_and_set_timebase_roundtrip_includes_effective_xy_mode():
    session = FakeSession()
    result = set_timebase(
        session,
        scale_s_div=0.002,
        offset_s=0.0,
        mode="xy",
        zoom_enabled=True,
        zoom_scale_s_div=0.001,
        zoom_offset_s=0.005,
        auto_roll=True,
        xy_x="ch3",
        xy_y="CHANNEL4",
        xy_grid="half",
        reference_mode="user",
        reference_position=100,
        fine_scale=True,
    )
    assert result == {
        "scale_s_div": 0.002,
        "offset_s": 0.0,
        "mode": "XY",
        "xy_enabled": True,
        "zoom_enabled": True,
        "zoom_scale_s_div": 0.001,
        "zoom_offset_s": 0.005,
        "auto_roll": True,
        "xy_x": "CHAN3",
        "xy_y": "CHAN4",
        "xy_grid": "HALF",
        "reference_mode": "USER",
        "reference_position": 100,
        "fine_scale": True,
    }
    assert get_timebase(session) == result
    assert session.writes[:2] == [":TIMebase:MODE XY", ":TIMebase:XY:ENABle 1"]


def test_auto_roll_is_independent_from_active_mode():
    session = FakeSession()
    result = set_timebase(session, auto_roll=True)
    assert result["auto_roll"] is True
    assert result["mode"] == "MAIN"
    assert session.writes == [":TIMebase:ROLL 1"]


def test_run_main_offset_uses_final_scale_and_stop_skips_memory_bound():
    session = FakeSession()
    session.state["trigger_status"] = "RUN"
    set_timebase(session, scale_s_div=0.1, offset_s=9.0)
    assert ":TRIGger:STATus?" in session.queries

    session = FakeSession()
    session.state["trigger_status"] = "RUN"
    with pytest.raises(ValueError, match="RUN range"):
        set_timebase(session, scale_s_div=0.1, offset_s=10.1)
    assert session.writes == []

    session = FakeSession()
    session.state["trigger_status"] = "STOP"
    set_timebase(session, offset_s=10_000.0)
    assert ":TRIGger:STATus?" in session.queries


def test_offsetless_change_does_not_query_trigger_status():
    session = FakeSession()
    set_timebase(session, scale_s_div=0.002)
    assert ":TRIGger:STATus?" not in session.queries


def test_disabling_auto_roll_precedes_slow_scale_and_zoom_enable_follows_scale():
    session = FakeSession()
    session.state["auto_roll"] = "1"
    set_timebase(session, scale_s_div=0.05, auto_roll=False, zoom_enabled=True)
    assert session.writes == [
        ":TIMebase:ROLL 0",
        ":TIMebase:MAIN:SCALe 0.05",
        ":TIMebase:DELay:ENABle 1",
    ]


@pytest.mark.parametrize(
    "kwargs,pattern",
    [
        ({"scale_s_div": 0}, "positive"),
        ({"scale_s_div": math.inf}, "finite"),
        ({"zoom_scale_s_div": 0.002}, "cannot exceed"),
        ({"xy_x": "EXT"}, "xy_x"),
        ({"reference_position": 501}, "reference_position"),
    ],
)
def test_invalid_combination_is_rejected_before_write(kwargs, pattern):
    session = FakeSession()
    with pytest.raises(ValueError, match=pattern):
        set_timebase(session, **kwargs)
    assert session.writes == []


def test_roll_mode_disables_zoom_only_when_explicitly_requested():
    session = FakeSession()
    session.state["zoom_enabled"] = "1"
    with pytest.raises(ValueError, match="zoom must be disabled"):
        set_timebase(session, mode="ROLL")
    assert session.writes == []

    result = set_timebase(session, mode="ROLL", zoom_enabled=False)
    assert result["mode"] == "ROLL"
    assert result["zoom_enabled"] is False
    assert session.writes == [
        ":TIMebase:DELay:ENABle 0",
        ":TIMebase:MODE ROLL",
    ]
