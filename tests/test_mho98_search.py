import pytest

from rigol_mcp.mho98.search import (
    navigate,
    read_search_events,
    set_navigation,
    set_search,
)


class FakeSession:
    def __init__(self, **overrides):
        self.state = {
            ":SEARch:STATe": "0",
            ":SEARch:MODE": "EDGE",
            ":SEARch:COUNt": "0",
            ":SEARch:EVENt": "0",
            ":SEARch:EDGE:SLOPe": "POS",
            ":SEARch:EDGE:SOURce": "CHAN1",
            ":SEARch:EDGE:THReshold": "0",
            ":SEARch:PULSe:POLarity": "POS",
            ":SEARch:PULSe:QUALifier": "GRE",
            ":SEARch:PULSe:SOURce": "CHAN1",
            ":SEARch:PULSe:UWIDth": "2e-6",
            ":SEARch:PULSe:LWIDth": "1e-6",
            ":SEARch:PULSe:THReshold": "0",
            ":CHANnel1:SCALe": "1",
            ":CHANnel1:OFFSet": "0",
            ":NAVigate:ENABle": "0",
            ":NAVigate:MODE": "TIME",
            ":NAVigate:TIME:SPEed": "NORM",
            ":NAVigate:TIME:PLAY": "0",
            ":TRIGger:STATus": "STOP",
        }
        self.state.update(overrides)
        self.queries = []
        self.writes = []

    def query(self, command):
        self.queries.append(command)
        if command.startswith(":SEARch:VALue?"):
            return self.state[command]
        key = command.removesuffix("?")
        if key not in self.state:
            raise AssertionError(f"unexpected query: {command}")
        return self.state[key]

    def write(self, command):
        self.writes.append(command)
        if command.startswith(":NAVigate:TIME:STARt") or command.startswith(":NAVigate:TIME:END") or command.startswith(":NAVigate:TIME:NEXT") or command.startswith(":NAVigate:TIME:BACK") or command.startswith(":NAVigate:SEARch:"):
            return
        head, value = command.split(" ", 1)
        self.state[head] = value


def test_edge_configuration_and_bounded_event_read_preserve_raw_time():
    session = FakeSession(
        **{
            ":SEARch:STATe": "1",
            ":SEARch:COUNt": "2",
            ":SEARch:VALue? 1": "1.25ms",
            ":SEARch:VALue? 2": "-2.5ms",
        }
    )

    configured = set_search(session, source="CHAN1", threshold_v=0.5, enabled=True)
    assert configured["enabled"] is True
    assert configured["source"] == "CHAN1"
    assert configured["threshold_v"] == 0.5

    result = read_search_events(session, start=1, limit=2)
    assert result["count"] == 2
    assert result["returned"] == 2
    assert result["events"] == [
        {"value": 1.25, "unit": "ms", "raw": "1.25ms", "index": 1},
        {"value": -2.5, "unit": "ms", "raw": "-2.5ms", "index": 2},
    ]
    assert ":SEARch:STATe 1" not in session.writes


def test_pulse_between_widths_are_prevalidated_before_writes():
    session = FakeSession(**{":SEARch:MODE": "PULS"})

    with pytest.raises(ValueError, match="smaller than upper"):
        set_search(session, qualifier="BETWEEN", lower_width_s=3e-6, upper_width_s=2e-6)

    assert session.writes == []


def test_search_navigation_requires_existing_stop_and_never_sends_stop():
    running = FakeSession(**{":TRIGger:STATus": "RUN"})
    with pytest.raises(ValueError, match="requires STOP"):
        set_navigation(running, mode="SEARCH", enabled=True)
    assert running.writes == []
    assert ":STOP" not in running.writes

    session = FakeSession()
    set_navigation(session, mode="SEARCH", enabled=True)
    assert session.writes == [":NAVigate:MODE SEARch", ":NAVigate:ENABle 1"]


def test_navigation_actions_route_only_to_documented_subtree():
    session = FakeSession()

    assert navigate(session, mode="TIME", action="first")["navigated"] is True
    assert navigate(session, mode="TIME", action="last")["navigated"] is True
    assert navigate(session, mode="SEARCH", action="next")["navigated"] is True
    assert session.writes == [
        ":NAVigate:TIME:STARt",
        ":NAVigate:TIME:END",
        ":NAVigate:SEARch:NEXT",
    ]
