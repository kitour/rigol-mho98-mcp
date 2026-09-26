import pytest

from rigol_mcp.mho98.dvm import get_dvm, read_dvm, set_dvm


class FakeSession:
    def __init__(self, state):
        self.state = dict(state)
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
        head, value = command.split(" ", 1)
        self.state[head] = value


def dvm_state(**overrides):
    state = {
        ":DVM:ENABle": "0",
        ":DVM:SOURce": "CHAN1",
        ":DVM:MODE": "ACRM",
        ":DVM:CURRent": "1.250 V",
    }
    state.update(overrides)
    return state


def test_set_and_get_dvm_return_canonical_configuration_readback():
    session = FakeSession(dvm_state())

    result = set_dvm(session, enabled=True, source="CHAN2", mode="DCRMs")

    assert session.writes == [
        ":DVM:ENABle 1",
        ":DVM:SOURce CHAN2",
        ":DVM:MODE DCRMs",
    ]
    assert result == {"enabled": True, "source": "CHAN2", "mode": "DCRMs"}
    assert get_dvm(session) == result


def test_read_dvm_preserves_value_unit_and_does_not_read_when_disabled():
    session = FakeSession(dvm_state())

    disabled = read_dvm(session)
    assert disabled["valid"] is False
    assert ":DVM:CURRent?" not in session.queries

    session = FakeSession(dvm_state(**{":DVM:ENABle": "1", ":DVM:CURRent": "1.250 mV"}))
    result = read_dvm(session)
    assert result == {
        "enabled": True,
        "valid": True,
        "value": 1.25,
        "unit": "mV",
        "raw": "1.250 mV",
    }

    session = FakeSession(dvm_state(**{":DVM:ENABle": "1", ":DVM:CURRent": "9.9E37 V"}))
    invalid = read_dvm(session)
    assert invalid["valid"] is False
    assert invalid["value"] is None
    assert invalid["raw"] == "9.9E37 V"
    assert invalid["unit"] == "V"


def test_invalid_source_is_rejected_before_any_query_or_write():
    session = FakeSession(dvm_state())

    with pytest.raises(ValueError, match="source"):
        set_dvm(session, source="MATH1")

    assert session.queries == []
    assert session.writes == []
