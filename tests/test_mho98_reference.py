import pytest

from rigol_mcp.mho98.reference import get_reference, reference_action, set_reference


class FakeReferenceSession:
    def __init__(self):
        self.state = {
            "source": "CHAN1",
            "scale": "2",
            "offset": "0.5",
            "color": "GRE",
            "label_enabled": "1",
            "label": "REF1",
            "channel_display": {1: "1", 2: "1", 3: "0", 4: "0"},
            "probe": {1: "1", 2: "1", 3: "1", 4: "1"},
            "impedance": {1: "OMEG", 2: "FIFT", 3: "OMEG", 4: "OMEG"},
            "math_display": {1: "1", 2: "0", 3: "0", 4: "0"},
            "digital_enable": {f"D{i}": "0" for i in range(16)},
        }
        self.state["digital_enable"]["D0"] = "1"
        self.writes = []
        self.queries = []
        self.saved = []

    def query(self, command):
        self.queries.append(command)
        values = {
            ":REFerence:SOURce? 1": self.state["source"],
            ":REFerence:VSCale? 1": self.state["scale"],
            ":REFerence:VOFFset? 1": self.state["offset"],
            ":REFerence:COLor? 1": self.state["color"],
            ":REFerence:LABel:ENABle?": self.state["label_enabled"],
            ":REFerence:LABel:CONTent? 1": self.state["label"],
            ":CHANnel1:DISPlay?": self.state["channel_display"][1],
            ":CHANnel2:DISPlay?": self.state["channel_display"][2],
            ":CHANnel3:DISPlay?": self.state["channel_display"][3],
            ":CHANnel1:PROBe?": self.state["probe"][1],
            ":CHANnel2:PROBe?": self.state["probe"][2],
            ":CHANnel1:IMPedance?": self.state["impedance"][1],
            ":CHANnel2:IMPedance?": self.state["impedance"][2],
            ":MATH1:DISPlay?": self.state["math_display"][1],
            ":LA:DIGital:ENABle? D0": self.state["digital_enable"]["D0"],
        }
        if command not in values:
            raise AssertionError(f"unexpected query: {command}")
        return values[command]

    def write(self, command):
        self.writes.append(command)
        if command.startswith(":REFerence:SOURce "):
            self.state["source"] = command.split(",", 1)[1].replace("CHANnel", "CHAN")
        elif command.startswith(":REFerence:VSCale "):
            self.state["scale"] = command.rsplit(",", 1)[1]
        elif command.startswith(":REFerence:VOFFset "):
            self.state["offset"] = command.rsplit(",", 1)[1]
        elif command.startswith(":REFerence:COLor "):
            self.state["color"] = command.rsplit(",", 1)[1]
        elif command.startswith(":REFerence:LABel:ENABle "):
            self.state["label_enabled"] = command.rsplit(" ", 1)[1]
        elif command.startswith(":REFerence:LABel:CONTent "):
            self.state["label"] = command.split(",", 1)[1][1:-1].replace('""', '"')
        elif command.startswith(":REFerence:SAVE "):
            self.saved.append(int(command.rsplit(" ", 1)[1]))
        elif command.startswith(":REFerence:RESet "):
            self.state["scale"] = "0.001"
            self.state["offset"] = "0"


def test_configuration_preserves_omissions_and_returns_actual_readback():
    session = FakeReferenceSession()

    result = set_reference(
        session,
        reference=1,
        source="CHAN2",
        scale_v_div=4,
        offset_v=1,
        color="orange",
        label_visible=False,
        label='R1 "saved"',
    )

    assert result == {
        "reference": 1,
        "source": "CHAN2",
        "scale_v_div": 4.0,
        "offset_v": 1.0,
        "color": "ORAN",
        "label_visible": False,
        "label": 'R1 "saved"',
    }
    assert session.writes == [
        ":REFerence:SOURce 1,CHANnel2",
        ":REFerence:VSCale 1,4",
        ":REFerence:VOFFset 1,1",
        ":REFerence:COLor 1,ORANge",
        ":REFerence:LABel:ENABle 0",
        ':REFerence:LABel:CONTent 1,"R1 ""saved"""',
    ]


@pytest.mark.parametrize(
    ("action", "command"),
    [
        ("current", ":REFerence:CURRent 1"),
        ("save", ":REFerence:SAVE 1"),
        ("reset", ":REFerence:RESet 1"),
    ],
)
def test_actions_route_to_explicit_documented_commands(action, command):
    session = FakeReferenceSession()

    result = reference_action(session, reference=1, action=action)

    assert session.writes == [command]
    assert result["action"] == action
    assert result["command"] == command
    assert not any("CURRent?" in query or "SAVE?" in query or "RESet?" in query for query in session.queries)


def test_invalid_slot_and_label_are_rejected_before_any_write():
    session = FakeReferenceSession()

    with pytest.raises(ValueError, match="1 through 10"):
        set_reference(session, reference=11, label="safe")
    with pytest.raises(ValueError, match="SCPI delimiters"):
        set_reference(session, reference=1, label="unsafe;write")
    with pytest.raises(ValueError, match="control characters"):
        set_reference(session, reference=1, label="unsafe\nwrite")

    assert session.writes == []


def test_disabled_source_is_rejected_before_write():
    session = FakeReferenceSession()
    with pytest.raises(ValueError, match="disabled"):
        set_reference(session, reference=1, source="CHAN3")
    assert session.writes == []
