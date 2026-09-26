import pytest

from rigol_mcp.mho98.counter import counter_action, get_counter, read_counter, set_counter


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
        if " " not in command:
            return
        head, value = command.split(" ", 1)
        self.state[head] = value


def counter_state(**overrides):
    state = {
        ":COUNter:ENABle": "0",
        ":COUNter:SOURce": "CHAN1",
        ":COUNter:MODE": "FREQ",
        ":COUNter:NDIGits": "4",
        ":COUNter:TOTalize:ENABle": "0",
        ":COUNter:CURRent": "1.000000E+03",
    }
    state.update(overrides)
    return state


def test_set_get_and_read_counter_preserve_config_and_use_exact_units():
    session = FakeSession(counter_state(**{":COUNter:ENABle": "1"}))

    result = set_counter(session, source="D3", mode="PER", digits=6, statistics=True)

    assert session.writes == [
        ":COUNter:SOURce D3",
        ":COUNter:MODE PERiod",
        ":COUNter:NDIGits 6",
        ":COUNter:TOTalize:ENABle 1",
    ]
    assert result == {
        "enabled": True,
        "source": "D3",
        "mode": "PER",
        "digits": 6,
        "statistics": True,
    }
    session.state[":COUNter:CURRent"] = "2.500000E-04"
    assert read_counter(session) == {
        "enabled": True,
        "mode": "PER",
        "valid": True,
        "value": 2.5e-4,
        "unit": "s",
        "raw": "2.500000E-04",
    }


def test_totalize_skips_unavailable_fields_and_clear_only_clears_totalizer():
    session = FakeSession(
        counter_state(**{":COUNter:MODE": "TOT", ":COUNter:ENABle": "1", ":COUNter:CURRent": "12"})
    )

    assert get_counter(session) == {
        "enabled": True,
        "source": "CHAN1",
        "mode": "TOT",
        "unavailable": ["digits", "statistics"],
    }
    assert ":COUNter:NDIGits?" not in session.queries
    assert ":COUNter:TOTalize:ENABle?" not in session.queries

    result = set_counter(session, mode="TOT")
    assert result["unavailable"] == ["digits", "statistics"]
    counter_action(session, action="clear")
    assert session.writes[-1] == ":COUNter:TOTalize:CLEar"


@pytest.mark.parametrize("field", ["digits", "statistics"])
def test_totalize_rejects_dependent_field_before_writes(field):
    session = FakeSession(counter_state(**{":COUNter:MODE": "TOT"}))

    with pytest.raises(ValueError, match="unavailable"):
        set_counter(session, **{field: 5 if field == "digits" else True})

    assert session.writes == []


def test_invalid_counter_value_preserves_raw_reply_and_unit():
    session = FakeSession(
        counter_state(**{":COUNter:ENABle": "1", ":COUNter:MODE": "FREQ", ":COUNter:CURRent": "9.9E37"})
    )

    result = read_counter(session)

    assert result["valid"] is False
    assert result["value"] is None
    assert result["raw"] == "9.9E37"
    assert result["unit"] == "Hz"
    assert session.writes == []
