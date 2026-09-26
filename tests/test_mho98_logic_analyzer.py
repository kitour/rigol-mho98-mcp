import pytest

from rigol_mcp.mho98.logic_analyzer import get_logic_analyzer, set_logic_analyzer


class FakeSession:
    def __init__(self, enabled_count=2):
        self.state = {
            "enabled": "0",
            "active": "D0",
            "sort": "D15D0",
            "size": "MED",
            "channels": {
                f"D{i}": {"enabled": "1" if i < enabled_count else "0", "label": f"D{i}"}
                for i in range(16)
            },
            "pods": {
                "POD1": {"display": "1", "threshold": "0"},
                "POD2": {"display": "0", "threshold": "1.25"},
            },
        }
        self.writes = []

    def query(self, command):
        if command == ":LA:ENABle?":
            return self.state["enabled"]
        if command == ":LA:ACTive?":
            return self.state["active"]
        if command == ":LA:AUTosort?":
            return self.state["sort"]
        if command == ":LA:SIZE?":
            return self.state["size"]
        for channel in self.state["channels"]:
            if command == f":LA:DIGital:ENABle? {channel}":
                return self.state["channels"][channel]["enabled"]
            if command == f":LA:DIGital:LABel? {channel}":
                return self.state["channels"][channel]["label"]
        for pod in self.state["pods"]:
            if command == f":LA:{pod}:DISPlay?":
                return self.state["pods"][pod]["display"]
            if command == f":LA:{pod}:THReshold?":
                return self.state["pods"][pod]["threshold"]
        raise AssertionError(f"unexpected query: {command}")

    def write(self, command):
        self.writes.append(command)
        head, value = command.rsplit(" ", 1)
        if head == ":LA:ENABle":
            self.state["enabled"] = value
        elif head == ":LA:ACTive":
            self.state["active"] = value
        elif head == ":LA:AUTosort":
            self.state["sort"] = value
        elif head == ":LA:SIZE":
            self.state["size"] = {"SMALl": "SMAL", "MEDium": "MED", "LARGe": "LARG"}.get(value, value)
        elif head.startswith(":LA:POD") and head.endswith(":DISPlay"):
            self.state["pods"][head.split(":")[2]]["display"] = value
        elif head.startswith(":LA:POD") and head.endswith(":THReshold"):
            self.state["pods"][head.split(":")[2]]["threshold"] = value
        elif head == ":LA:DIGital:ENABle":
            channel, enabled = value.split(",", 1)
            self.state["channels"][channel]["enabled"] = enabled
        elif head == ":LA:DIGital:LABel":
            channel, label = value.split(",", 1)
            self.state["channels"][channel]["label"] = label
        else:
            raise AssertionError(f"unexpected write: {command}")


def test_get_subset_and_set_representative_channel_pod_configuration():
    session = FakeSession()
    subset = get_logic_analyzer(session, channels=["D3"])
    assert set(subset["channels"]) == {"D3"}
    assert subset["pods"]["POD2"]["threshold_v"] == 1.25

    result = set_logic_analyzer(
        session,
        enabled=True,
        channels={"D3": {"enabled": True, "label": "CLK"}},
        pod2_display=True,
        pod2_threshold_v=1.8,
        active_channel="D3",
        auto_sort="D0D15",
        size="LARGE",
    )
    assert result["enabled"] is True
    assert result["channels"]["D3"] == {"enabled": True, "label": "CLK"}
    assert result["pods"]["POD2"] == {"display": True, "threshold_v": 1.8}
    assert result["active_channel"] == "D3"
    assert session.writes.index(":LA:DIGital:ENABle D3,1") < session.writes.index(":LA:ACTive D3")


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"active_channel": "D7"}, "active_channel"),
        ({"pod1_threshold_v": 15.01}, "pod1_threshold_v"),
        ({"size": "LARGE"}, "LARGE"),
    ],
)
def test_invalid_final_state_is_rejected_before_writes(kwargs, message):
    session = FakeSession(enabled_count=9 if kwargs.get("size") else 2)
    with pytest.raises(ValueError, match=message):
        set_logic_analyzer(session, **kwargs)
    assert session.writes == []


def test_invalid_label_and_non_boolean_are_rejected_before_writes():
    session = FakeSession()
    with pytest.raises(ValueError, match="SCPI"):
        set_logic_analyzer(session, channels={"D1": {"label": "bad;:LA:ENABle 0"}})
    with pytest.raises(ValueError, match="real boolean"):
        set_logic_analyzer(session, enabled="true")
    assert session.writes == []
