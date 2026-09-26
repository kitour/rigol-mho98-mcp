import pytest

from rigol_mcp.mho98.measurement_settings import (
    get_measurement_settings,
    measurement_action,
    set_measurement_settings,
)


class FakeSession:
    def __init__(self, state):
        self.state = dict(state)
        self.queries = []
        self.writes = []

    def query(self, command):
        self.queries.append(command)
        if command.endswith("?"):
            key = command[:-1]
            if key == ":MEASure:SETup:DSB":
                raise AssertionError("DSB? must not be queried")
            if key not in self.state:
                raise AssertionError(f"unexpected query: {command}")
            return self.state[key]
        raise AssertionError(f"unexpected query: {command}")

    def write(self, command):
        self.writes.append(command)
        if " " not in command:
            return
        head, value = command.split(" ", 1)
        self.state[head] = value


def threshold_state(**overrides):
    state = {
        ":MEASure:SETup:MIN": "10",
        ":MEASure:SETup:MID": "50",
        ":MEASure:SETup:MAX": "90",
        ":MEASure:THReshold:TYPE": "PERC",
    }
    state.update(overrides)
    return state


def test_threshold_update_validates_and_orders_before_first_write():
    session = FakeSession(threshold_state())

    result = set_measurement_settings(
        session,
        threshold_min=20,
        threshold_mid=40,
        threshold_max=80,
    )

    assert session.writes == [
        ":MEASure:SETup:MIN 20",
        ":MEASure:SETup:MID 40",
        ":MEASure:SETup:MAX 80",
    ]
    assert result["threshold_mid"] == 40.0

    session = FakeSession(threshold_state())
    with pytest.raises(ValueError, match="threshold_min"):
        set_measurement_settings(session, threshold_min=60, threshold_mid=50, threshold_max=80)
    assert session.writes == []


def test_region_readback_is_conditional_and_top_base_uses_manual_mode():
    state = {
        ":MEASure:AREA": "CURS",
        ":MEASure:CREGion:CAX": "-1e-3",
        ":MEASure:CREGion:CBX": "1e-3",
        ":MEASure:CREGion:CABX": "0",
        ":MEASure:AMP:TYPE": "MAN",
        ":MEASure:AMP:MANual:TOP": "HIST",
        ":MEASure:AMP:MANual:BASE": "MAXM",
    }
    result = set_measurement_settings(
        FakeSession(state),
        area="CURSOR",
        amplitude_method="MANUAL",
    )
    assert result["cursor_a_s"] == -1e-3
    assert result["manual_base"] == "MAXM"


def test_delay_source_b_readback_uses_documented_psb_query():
    state = {
        ":MEASure:SOURce": "CHAN1",
        ":MEASure:AMSource": "OFF",
        ":MEASure:THReshold:SOURce": "CHAN1",
        ":MEASure:THReshold:TYPE": "PERC",
        ":MEASure:SETup:MIN": "10",
        ":MEASure:SETup:MID": "50",
        ":MEASure:SETup:MAX": "90",
        ":MEASure:SETup:PSA": "CHAN1",
        ":MEASure:SETup:PSB": "CHAN2",
        ":MEASure:SETup:DSA": "CHAN1",
        ":MEASure:AREA": "MAIN",
        ":MEASure:TYPE": "THR",
        ":MEASure:INDicator": "OFF",
        ":MEASure:STATistic:COUNt": "2",
        ":MEASure:STATistic:DISPlay": "OFF",
        ":MEASure:AMP:TYPE": "AUTO",
        ":MEASure:HISTogram:ENABle": "OFF",
        ":MEASure:CATegory": "0",
        ":MEASure:COUNter:ENABle": "OFF",
        ":MEASure:COUNter:SOURce": "CHAN1",
    }
    session = FakeSession(state)

    result = get_measurement_settings(session)

    assert result["delay_source_b"] == "CHAN2"
    assert "unavailable" not in result
    assert session.queries.count(":MEASure:SETup:PSB?") == 1


def test_source_b_aliases_share_one_psb_write_and_reject_conflicts():
    session = FakeSession({":MEASure:SETup:PSB": "CHAN1"})
    with pytest.raises(ValueError, match="phase_source_b and delay_source_b"):
        set_measurement_settings(session, phase_source_b="CH1", delay_source_b="CH2")
    assert session.writes == []

    session = FakeSession({":MEASure:SETup:PSB": "CHAN1"})
    result = set_measurement_settings(session, phase_source_b="CH2", delay_source_b="CHAN2")
    assert session.writes == [":MEASure:SETup:PSB CHAN2"]
    assert session.queries.count(":MEASure:SETup:PSB?") == 1
    assert result["phase_source_b"] == result["delay_source_b"] == "CHAN2"


def test_item_and_statistics_actions_are_explicit():
    session = FakeSession({})
    assert measurement_action(session, action="register_item", item="VPP", source="CH1")["item"] == "VPP"
    assert session.writes == [":MEASure:ITEM VPP,CHAN1"]

    measurement_action(session, action="reset_statistics")
    measurement_action(session, action="delete_items")
    assert session.writes[-2:] == [":MEASure:STATistic:RESet", ":MEASure:DELete"]
