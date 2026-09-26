import math

import pytest

from rigol_mcp.mho98.channel import get_channel, set_channel


class FakeSession:
    def __init__(self):
        self.state = {
            "display": "1",
            "bandwidth": "OFF",
            "invert": "0",
            "impedance": "OMEG",
            "coupling": "DC",
            "scale": "0.05",
            "offset": "0",
            "deskew": "0",
            "probe": "1",
            "units": "VOLT",
            "fine_scale": "0",
            "label_visible": "0",
            "label": "",
            "bias": "0",
        }
        self.writes = []

    def query(self, command):
        parts = command.split(":")
        key = parts[-1].removesuffix("?").upper()
        if len(parts) >= 2 and parts[-2].upper() == "LABEL":
            key = "LABEL:" + key
        return self.state[
            {
                "DISPLAY": "display",
                "BWLIMIT": "bandwidth",
                "INVERT": "invert",
                "IMPEDANCE": "impedance",
                "COUPLING": "coupling",
                "SCALE": "scale",
                "OFFSET": "offset",
                "TCALIBRATE": "deskew",
                "PROBE": "probe",
                "UNITS": "units",
                "VERNIER": "fine_scale",
                "LABEL:SHOW": "label_visible",
                "LABEL:CONTENT": "label",
                "POSITION": "bias",
            }[key]
        ]

    def write(self, command):
        self.writes.append(command)
        head, value = command.rsplit(" ", 1)
        parts = head.split(":")
        key = parts[-1].upper()
        if len(parts) >= 2 and parts[-2].upper() == "LABEL":
            key = "LABEL:" + key
        field = {
            "DISPLAY": "display",
            "BWLIMIT": "bandwidth",
            "INVERT": "invert",
            "IMPEDANCE": "impedance",
            "COUPLING": "coupling",
            "SCALE": "scale",
            "OFFSET": "offset",
            "TCALIBRATE": "deskew",
            "PROBE": "probe",
            "UNITS": "units",
            "VERNIER": "fine_scale",
            "LABEL:SHOW": "label_visible",
            "LABEL:CONTENT": "label",
            "POSITION": "bias",
        }[key]
        self.state[field] = value
        if key == "LABEL:CONTENT":
            self.state[field] = value
        if key == "IMPEDANCE" and value.upper() == "FIFTY":
            self.state["coupling"] = "DC"


def test_get_and_set_roundtrip_reads_normalized_effective_settings():
    session = FakeSession()

    result = set_channel(
        session,
        "ch1",
        display=False,
        bandwidth="20M",
        invert=True,
        impedance_ohms=50,
        coupling="dc",
        scale_v_div=0.02,
        offset_v=0.1,
        deskew_s=50e-9,
        probe=10,
        units="AMP",
        fine_scale=True,
        label_visible=True,
        label="test",
        bias_v=0.2,
    )

    assert result == {
        "channel": "CHAN1",
        "display": False,
        "bandwidth": "20M",
        "invert": True,
        "impedance_ohms": 50,
        "coupling": "DC",
        "scale_v_div": 0.02,
        "offset_v": 0.1,
        "deskew_s": 5e-08,
        "probe": 10.0,
        "units": "AMP",
        "fine_scale": True,
        "label_visible": True,
        "label": "test",
        "bias_v": 0.2,
    }
    assert [w.split(" ", 1)[0] for w in session.writes] == [
        ":CHANnel1:IMPedance",
        ":CHANnel1:UNITs",
        ":CHANnel1:PROBe",
        ":CHANnel1:BWLimit",
        ":CHANnel1:SCALe",
        ":CHANnel1:OFFSet",
        ":CHANnel1:TCALibrate",
        ":CHANnel1:POSition",
        ":CHANnel1:INVert",
        ":CHANnel1:VERNier",
        ":CHANnel1:LABel:SHOW",
        ":CHANnel1:LABel:CONTent",
        ":CHANnel1:DISPlay",
    ]
    assert get_channel(session, "CHANNEL1") == result


def test_50_ohm_explicit_ac_rejected_before_first_write():
    session = FakeSession()
    with pytest.raises(ValueError, match="50 ohm"):
        set_channel(session, "CHAN1", impedance_ohms=50, coupling="AC")
    assert session.writes == []


def test_ac_is_rejected_when_current_impedance_is_50_ohms():
    session = FakeSession()
    session.state["impedance"] = "FIFT"
    with pytest.raises(ValueError, match="50 ohm"):
        set_channel(session, "CHAN1", coupling="AC")
    assert session.writes == []


def test_setting_50_ohm_alone_allows_instrument_forced_dc():
    session = FakeSession()
    session.state["coupling"] = "AC"
    result = set_channel(session, "CHAN1", impedance_ohms=50)
    assert result["impedance_ohms"] == 50
    assert result["coupling"] == "DC"
    assert session.writes == [":CHANnel1:IMPedance FIFTy"]


@pytest.mark.parametrize("field,value", [("scale_v_div", math.nan), ("offset_v", math.inf), ("probe", -math.inf)])
def test_non_finite_numeric_values_are_rejected_before_write(field, value):
    session = FakeSession()
    with pytest.raises(ValueError, match="finite"):
        set_channel(session, "CHAN1", **{field: value})
    assert session.writes == []


def test_invalid_probe_and_scale_range_are_rejected_before_write():
    session = FakeSession()
    result = set_channel(session, "CHAN1", probe=3)
    assert result["probe"] == 3.0
    assert session.writes == [":CHANnel1:PROBe 3"]

    with pytest.raises(ValueError, match="probe"):
        set_channel(session, "CHAN1", probe=0)
    assert session.writes == [":CHANnel1:PROBe 3"]

    with pytest.raises(ValueError, match="outside"):
        set_channel(session, "CHAN1", scale_v_div=0.0005)
    assert session.writes == [":CHANnel1:PROBe 3"]


def test_units_probe_and_bandwidth_constraints_are_checked_before_write():
    session = FakeSession()
    with pytest.raises(ValueError, match="probe <= 10"):
        set_channel(session, "CHAN1", units="AMP", probe=20)
    assert session.writes == []

    with pytest.raises(ValueError, match="20M"):
        set_channel(session, "CHAN1", impedance_ohms=50, scale_v_div=0.0002, bandwidth="ON")
    assert session.writes == []


def test_bandwidth_transition_orders_scale_before_bandwidth_when_scaling_up():
    session = FakeSession()
    session.state.update({"impedance": "FIFT", "scale": "0.0002", "bandwidth": "20M"})
    set_channel(session, "CHAN1", scale_v_div=0.001, bandwidth="OFF")
    assert session.writes == [":CHANnel1:SCALe 0.001", ":CHANnel1:BWLimit OFF"]


def test_probe_only_change_uses_current_physical_scale_for_bandwidth_check():
    session = FakeSession()
    session.state.update({"scale": "0.0005", "bandwidth": "ON"})
    result = set_channel(session, "CHAN1", probe=10)
    assert result["probe"] == 10.0
    assert session.writes == [":CHANnel1:PROBe 10"]


def test_amp_transition_lowers_probe_before_units():
    session = FakeSession()
    session.state.update({"probe": "100", "scale": "0.1"})
    set_channel(session, "CHAN1", units="AMP", probe=1)
    assert session.writes == [":CHANnel1:PROBe 1", ":CHANnel1:UNITs AMPere"]


def test_label_delimiters_and_deskew_range_are_rejected_before_write():
    session = FakeSession()
    with pytest.raises(ValueError, match="SCPI delimiters"):
        set_channel(session, "CHAN1", label="unsafe;write")
    with pytest.raises(ValueError, match="deskew_s"):
        set_channel(session, "CHAN1", deskew_s=101e-9)
    assert session.writes == []


def test_write_failure_returns_explicit_partial_failure_and_readback():
    session = FakeSession()
    session.state["scale"] = "0.001"

    def fail(command):
        session.writes.append(command)
        raise RuntimeError("SCPI error")

    session.write = fail
    with pytest.raises(RuntimeError, match="SCPI error"):
        set_channel(session, "CHAN1", scale_v_div=0.002)
