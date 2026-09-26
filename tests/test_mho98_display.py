import pytest

from rigol_mcp.mho98.display import (
    TOOLS,
    display_action,
    get_display,
    get_quick_action,
    set_display,
    set_quick_action,
)


class FakeSession:
    def __init__(self):
        self.state = {
            ":DISPlay:TYPE": "VECT",
            ":DISPlay:GRADing:TIME": "MIN",
            ":DISPlay:WBRightness": "50",
            ":DISPlay:GRID": "FULL",
            ":DISPlay:GBRightness": "50",
            ":DISPlay:CBRightness": "80",
            ":DISPlay:RULers": "1",
            ":DISPlay:MOVE": "0",
            ":DISPlay:COLor": "0",
            ":DISPlay:WHOLd": "0",
            ":QUICk:OPERation": "SIM",
        }
        self.queries = []
        self.writes = []

    def query(self, command):
        self.queries.append(command)
        key = command[:-1] if command.endswith("?") else command
        if key not in self.state:
            raise AssertionError(f"unexpected query: {command}")
        return self.state[key]

    def write(self, command):
        self.writes.append(command)
        if " " in command:
            head, value = command.split(" ", 1)
            self.state[head] = value
        elif command == ":DISPlay:CLEar":
            self.state[":DISPlay:TYPE"] = self.state[":DISPlay:TYPE"]


def test_get_display_normalizes_short_and_preserves_numeric_persistence_token():
    session = FakeSession()
    session.state[":DISPlay:GRADing:TIME"] = "0.1"

    assert get_display(session) == {
        "display_type": "VECT",
        "persistence_time": "0.1",
        "waveform_brightness": 50,
        "grid": "FULL",
        "grid_brightness": 50,
        "cursor_brightness": 80,
        "rulers": True,
        "ruler_tracking": False,
        "color": False,
        "wavehold": False,
    }
    assert session.writes == []


def test_set_display_accepts_long_enums_preserves_omitted_settings_and_reads_back():
    session = FakeSession()

    result = set_display(
        session,
        display_type="VECTors",
        persistence_time="INFinite",
        waveform_brightness=75,
        grid="HALF",
        rulers=False,
        ruler_tracking=True,
        color=True,
        wavehold=True,
    )

    assert session.writes == [
        ":DISPlay:GRADing:TIME INFinite",
        ":DISPlay:GRID HALF",
        ":DISPlay:WBRightness 75",
        ":DISPlay:RULers 0",
        ":DISPlay:MOVE 1",
        ":DISPlay:COLor 1",
        ":DISPlay:WHOLd 1",
    ]
    assert result["display_type"] == "VECT"
    assert result["persistence_time"] == "INF"
    assert result["grid_brightness"] == 50
    assert result["cursor_brightness"] == 80
    assert not any(command in {":RUN", ":STOP"} for command in session.writes)


def test_display_action_is_explicit_clear_only_and_returns_readback():
    session = FakeSession()

    result = display_action(session, action="clear")

    assert session.writes == [":DISPlay:CLEar"]
    assert result["action"] == "clear"
    assert result["display_type"] == "VECT"
    assert ":RUN" not in session.writes and ":STOP" not in session.writes


def test_invalid_display_input_is_rejected_before_any_write():
    session = FakeSession()

    with pytest.raises(ValueError, match="grid_brightness"):
        set_display(session, grid_brightness=101, wavehold=True)

    assert session.writes == []


def test_quick_assignment_accepts_long_and_short_tokens_but_never_runs_action():
    session = FakeSession()

    assert set_quick_action(session, operation="SRESet") == {"operation": "SRES"}
    assert session.writes == [":QUICk:OPERation SRESet"]
    assert get_quick_action(session) == {"operation": "SRES"}
    assert all(command not in {":RUN", ":STOP", ":QUICk:OPERation?"} for command in session.writes)


def test_tool_metadata_marks_only_getters_read_only():
    metadata = {spec.name: spec for spec in TOOLS}

    assert metadata["get_display"].read_only is True
    assert metadata["get_quick_action"].read_only is True
    for name in ("set_display", "display_action", "set_quick_action"):
        assert metadata[name].read_only is False
