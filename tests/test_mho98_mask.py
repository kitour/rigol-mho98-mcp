import pytest

from rigol_mcp.mho98.mask import get_mask, mask_action, read_mask, set_mask


class FakeSession:
    def __init__(self):
        self.state = {
            "enabled": "0",
            "source": "CHAN1",
            "operate": "STOP",
            "x": "0.24",
            "y": "0.48",
            "aux_enabled": "0",
            "aux_event": "FAIL",
            "aux_time": "1e-6",
            "failed": "0",
            "passed": "0",
            "total": "0",
            "mode": "MAIN",
            "zoom": "0",
            "record": "STOP",
            "play": "STOP",
        }
        self.writes = []
        self.queries = []

    def query(self, command):
        self.queries.append(command)
        mapping = {
            ":MASK:ENABle?": "enabled",
            ":MASK:SOURce?": "source",
            ":MASK:OPERate?": "operate",
            ":MASK:X?": "x",
            ":MASK:Y?": "y",
            ":MASK:OUTPut:ENABle?": "aux_enabled",
            ":MASK:OUTPut:EVENt?": "aux_event",
            ":MASK:OUTPut:TIME?": "aux_time",
            ":MASK:FAILed?": "failed",
            ":MASK:PASSed?": "passed",
            ":MASK:TOTal?": "total",
            ":TIMebase:MODE?": "mode",
            ":TIMebase:DELay:ENABle?": "zoom",
            ":RECord:WRECord:OPERate?": "record",
            ":RECord:WREPlay:OPERate?": "play",
        }
        return self.state[mapping[command]]

    def write(self, command):
        self.writes.append(command)
        if command == ":MASK:CREate":
            return
        if command == ":MASK:RESet":
            self.state.update(failed="0", passed="0", total="0")
            return
        head, value = command.rsplit(" ", 1)
        mapping = {
            ":MASK:ENABle": "enabled",
            ":MASK:SOURce": "source",
            ":MASK:X": "x",
            ":MASK:Y": "y",
            ":MASK:OUTPut:ENABle": "aux_enabled",
            ":MASK:OUTPut:EVENt": "aux_event",
            ":MASK:OUTPut:TIME": "aux_time",
            ":MASK:OPERate": "operate",
        }
        self.state[mapping[head]] = value


def test_set_get_config_and_explicit_source_effect():
    session = FakeSession()
    result = set_mask(
        session,
        enabled=True,
        source="CHAN2",
        x_div=0.5,
        y_div=0.75,
        aux_enabled=True,
        aux_event="PASS",
        aux_time_s=2e-6,
    )
    assert result["enabled"] is True
    assert result["source"] == "CHAN2"
    assert result["aux_enabled"] is True
    assert result["effects"]
    assert ":MASK:OPERate RUN" not in session.writes
    assert get_mask(session)["operate"] == "STOP"


def test_read_counts_and_zero_ratio():
    session = FakeSession()
    session.state.update(enabled="1", failed="2", passed="0", total="2")
    assert read_mask(session) == {
        "enabled": True,
        "operate": "STOP",
        "applicable": True,
        "failed": 2,
        "passed": 0,
        "total": 2,
        "pass_ratio": 0.0,
    }
    session.state.update(failed="0", passed="0", total="0")
    assert read_mask(session)["pass_ratio"] is None


def test_actions_create_start_stop_reset_and_full_readback():
    session = FakeSession()
    session.state["enabled"] = "1"
    session.state.update(failed="3", passed="4", total="7")

    assert mask_action(session, action="create")["action"] == "create"
    assert mask_action(session, action="start")["action"] == "start"
    assert session.state["operate"] == "RUN"
    assert mask_action(session, action="stop")["results"]["operate"] == "STOP"
    result = mask_action(session, action="reset")
    assert result["results"]["failed"] == 0
    assert result["results"]["passed"] == 0
    assert result["results"]["total"] == 0
    assert ":MASK:RESet" in session.writes


@pytest.mark.parametrize(
    "state_key,state_value,match",
    [
        ("mode", "ROLL", "ROLL"),
        ("zoom", "1", "Zoom"),
        ("record", "RUN", "recording"),
        ("play", "RUN", "playback"),
    ],
)
def test_incompatible_state_refuses_enable_before_writes(state_key, state_value, match):
    session = FakeSession()
    session.state[state_key] = state_value
    with pytest.raises(ValueError, match=match):
        set_mask(session, enabled=True)
    assert session.writes == []


def test_start_does_not_implicitly_enable():
    session = FakeSession()
    with pytest.raises(ValueError, match="enable it explicitly"):
        mask_action(session, action="start")
    assert session.writes == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"x_div": 0.009},
        {"y_div": 2.01},
        {"aux_time_s": 99e-9},
        {"aux_event": "OTHER"},
    ],
)
def test_invalid_values_are_rejected_before_writes(kwargs):
    session = FakeSession()
    with pytest.raises(ValueError):
        set_mask(session, **kwargs)
    assert session.writes == []
