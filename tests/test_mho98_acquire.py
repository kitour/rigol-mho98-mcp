"""Offline tests for MHO98 acquisition settings and explicit controls."""

import pytest

from rigol_mcp.mho98.acquire import (
    acquisition_control,
    get_acquisition,
    set_acquisition,
)


class FakeSession:
    def __init__(self, *, enabled=(True, False, False, False)):
        self.state = {
            "type": "NORM",
            "averages": "2",
            "mdepth": "10000",
            "bits": "12",
            "srate": "1.000000E+06",
        }
        self.enabled = list(enabled)
        self.queries = []
        self.writes = []

    def query(self, command):
        self.queries.append(command)
        if command == ":ACQuire:TYPE?":
            return self.state["type"]
        if command == ":ACQuire:AVERages?":
            return self.state["averages"]
        if command == ":ACQuire:MDEPth?":
            return self.state["mdepth"]
        if command == ":ACQuire:BITS?":
            return self.state["bits"]
        if command == ":ACQuire:SRATe?":
            return self.state["srate"]
        if command.startswith(":CHANnel") and command.endswith(":DISPlay?"):
            channel = int(command[len(":CHANnel")])
            return "1" if self.enabled[channel - 1] else "0"
        raise AssertionError(f"unexpected query: {command}")

    def write(self, command):
        self.writes.append(command)
        if command.startswith(":ACQuire:TYPE "):
            self.state["type"] = command.rsplit(" ", 1)[1]
        elif command.startswith(":ACQuire:AVERages "):
            self.state["averages"] = command.rsplit(" ", 1)[1]
        elif command.startswith(":ACQuire:BITS "):
            self.state["bits"] = command.rsplit(" ", 1)[1]
        elif command.startswith(":ACQuire:MDEPth "):
            token = command.rsplit(" ", 1)[1]
            if token == "AUTO":
                self.state["mdepth"] = token
            else:
                aliases = {"1M": 1_000_000, "500M": 500_000_000}
                points = aliases[token] if token in aliases else int(token)
                self.state["mdepth"] = str(points)


def test_get_acquisition_queries_all_documented_readbacks():
    session = FakeSession()

    assert get_acquisition(session) == {
        "mode": "NORM",
        "averages": 2,
        "memory_depth": 10000,
        "bits": 12,
        "sample_rate": 1_000_000.0,
    }
    assert session.writes == []


def test_set_acquisition_applies_dependent_fields_then_reads_back():
    session = FakeSession()

    result = set_acquisition(
        session,
        mode="HRES",
        averages=16,
        bits=16,
        memory_depth="1M",
    )

    assert result == {
        "mode": "HRES",
        "averages": 16,
        "memory_depth": 1_000_000,
        "bits": 16,
        "sample_rate": 1_000_000.0,
    }
    assert session.writes == [
        ":ACQuire:TYPE HRES",
        ":ACQuire:AVERages 16",
        ":ACQuire:BITS 16",
        ":ACQuire:MDEPth 1M",
    ]
    assert not any(command.startswith(":RUN") for command in session.writes)
    assert not any(command.startswith(":CHANnel") for command in session.writes)


def test_memory_limit_uses_current_enabled_channel_count_before_write():
    session = FakeSession(enabled=(True, True, False, False))

    with pytest.raises(ValueError, match="250000000 point limit"):
        set_acquisition(session, memory_depth="500M")

    assert session.writes == []
    assert session.queries.count(":CHANnel1:DISPlay?") == 1
    assert session.queries.count(":CHANnel2:DISPlay?") == 1


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"averages": 9}, "power of two"),
        ({"averages": 1}, "power of two"),
        ({"mode": "HRES", "bits": 12}, "14 or 16"),
        ({"mode": "NORM", "bits": 16}, "only be set in HRES"),
    ],
)
def test_invalid_acquisition_combinations_are_rejected_before_write(kwargs, message):
    session = FakeSession()

    with pytest.raises(ValueError, match=message):
        set_acquisition(session, **kwargs)

    assert session.writes == []


@pytest.mark.parametrize(
    ("action", "command"),
    [("RUN", ":RUN"), ("stop", ":STOP"), ("SINGLE", ":SINGle"), ("force", ":TFORce")],
)
def test_acquisition_control_only_performs_explicit_action(action, command):
    session = FakeSession()

    result = acquisition_control(session, action)

    assert result["action"] in {"RUN", "STOP", "SINGLE", "FORCE"}
    assert session.writes == [command]


def test_acquisition_control_rejects_implicit_or_unknown_actions():
    session = FakeSession()
    with pytest.raises(ValueError, match="RUN, STOP, SINGLE, or FORCE"):
        acquisition_control(session, "AUTO")
    assert session.writes == []
