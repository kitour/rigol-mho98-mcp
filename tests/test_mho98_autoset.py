import pytest

from rigol_mcp.mho98.autoset import get_autoset, run_autoset, set_autoset


class FakeAutoSession:
    def __init__(self, *, autoscale=True, lock=False, enabled=True, recording="STOP", playback="STOP"):
        self.state = {
            ":SYSTem:AUToscale": "1" if autoscale else "0",
            ":AUToset:PEAK": "1",
            ":AUToset:OPENch": "0",
            ":AUToset:OVERlap": "1",
            ":AUToset:KEEPcoup": "0",
            ":AUToset:LOCK": "1" if lock else "0",
            ":AUToset:ENAble": "1" if enabled else "0",
            ":RECord:WRECord:OPERate": recording,
            ":RECord:WREPlay:OPERate": playback,
        }
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
        if command == ":AUToset":
            return
        head, value = command.split(" ", 1)
        self.state[head] = value
        if head == ":AUToset:ENAble":
            self.state[":AUToset:LOCK"] = "0" if value == "1" else "1"
        elif head == ":AUToset:LOCK":
            self.state[":AUToset:ENAble"] = "0" if value == "1" else "1"


def test_get_and_set_preserve_omissions_and_return_readback():
    session = FakeAutoSession()

    assert get_autoset(session) == {
        "autoscale": True,
        "peak": True,
        "open_channels": False,
        "overlap": True,
        "keep_coupling": False,
        "lock": False,
        "enabled": True,
    }

    result = set_autoset(session, peak_priority=False, enabled_channels_only=True)

    assert result["peak"] is False
    assert result["open_channels"] is True
    assert result["keep_coupling"] is False
    assert session.writes == [":AUToset:PEAK 0", ":AUToset:OPENch 1"]


def test_lock_and_enabled_aliases_reject_contradictions_before_write():
    session = FakeAutoSession()

    with pytest.raises(ValueError, match="contradictory"):
        set_autoset(session, lock=True, enabled=True)

    assert session.writes == []


def test_run_checks_gate_and_recording_states_without_implicit_stop():
    session = FakeAutoSession(recording="RUN")

    with pytest.raises(ValueError, match="recording is running"):
        run_autoset(session)

    assert session.writes == []
    assert ":AUToset" not in session.writes
    assert "*OPC?" not in session.queries


def test_run_is_explicit_and_describes_display_state_changes():
    session = FakeAutoSession()

    result = run_autoset(session)

    assert session.writes == [":AUToset"]
    assert result["action"] == "run_autoset"
    assert result["command"] == ":AUToset"
    assert "channel" in result["effect"]
    assert "timebase" in result["effect"]
    assert "trigger" in result["effect"]
