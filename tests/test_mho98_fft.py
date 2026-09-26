"""Focused offline tests for MHO98 FFT configuration and peak tables."""

import pytest

from rigol_mcp.mho98.fft import get_fft, read_fft, set_fft


class FakeSession:
    def __init__(self, *, operator="FFT", display=True):
        self.state = {
            "operator": operator,
            "display": display,
            "source": "CHAN1",
            "window": "HANN",
            "unit": "DB",
            "mode": "NORM",
            "averages": 10,
            "scale": 2.0,
            "offset": 0.0,
            "center_hz": 1_000_000.0,
            "range_hz": 1_000_000.0,
            "start_hz": 1.0,
            "end_hz": 10_000_000.0,
            "search_enabled": False,
            "peak_count": 5,
            "threshold": -40.0,
            "excursion": 1.8,
            "order": "AMP",
        }
        self.raw_results = ""
        self.queries = []
        self.writes = []

    def query(self, command):
        self.queries.append(command)
        if command == ":MATH1:OPERator?":
            return self.state["operator"]
        if command == ":MATH1:DISPlay?":
            return "1" if self.state["display"] else "0"
        if command == ":MATH1:FFT:SEARch:RES?":
            return self.raw_results
        mapping = {
            ":MATH1:FFT:SOURce?": "source",
            ":MATH1:FFT:WINDow?": "window",
            ":MATH1:FFT:UNIT?": "unit",
            ":MATH1:FFT:MODE?": "mode",
            ":MATH1:FFT:AVCNt?": "averages",
            ":MATH1:FFT:SCALe?": "scale",
            ":MATH1:FFT:OFFSet?": "offset",
            ":MATH1:FFT:HCENter?": "center_hz",
            ":MATH1:FFT:HSCale?": "range_hz",
            ":MATH1:FFT:FREQuency:STARt?": "start_hz",
            ":MATH1:FFT:FREQuency:END?": "end_hz",
            ":MATH1:FFT:SEARch:ENABle?": "search_enabled",
            ":MATH1:FFT:SEARch:NUM?": "peak_count",
            ":MATH1:FFT:SEARch:THReshold?": "threshold",
            ":MATH1:FFT:SEARch:EXCursion?": "excursion",
            ":MATH1:FFT:SEARch:ORDer?": "order",
        }
        if command not in mapping:
            raise AssertionError(f"unexpected query: {command}")
        key = mapping[command]
        value = self.state[key]
        if key == "search_enabled":
            return "1" if value else "0"
        return str(value)

    def write(self, command):
        self.writes.append(command)
        head, value = command.rsplit(" ", 1)
        if head == ":MATH1:OPERator":
            self.state["operator"] = value
        elif head == ":MATH1:DISPlay":
            self.state["display"] = value == "1"
        else:
            mapping = {
                ":MATH1:FFT:SOURce": "source",
                ":MATH1:FFT:WINDow": "window",
                ":MATH1:FFT:UNIT": "unit",
                ":MATH1:FFT:MODE": "mode",
                ":MATH1:FFT:AVCNt": "averages",
                ":MATH1:FFT:SCALe": "scale",
                ":MATH1:FFT:OFFSet": "offset",
                ":MATH1:FFT:HCENter": "center_hz",
                ":MATH1:FFT:HSCale": "range_hz",
                ":MATH1:FFT:FREQuency:STARt": "start_hz",
                ":MATH1:FFT:FREQuency:END": "end_hz",
                ":MATH1:FFT:SEARch:ENABle": "search_enabled",
                ":MATH1:FFT:SEARch:NUM": "peak_count",
                ":MATH1:FFT:SEARch:THReshold": "threshold",
                ":MATH1:FFT:SEARch:EXCursion": "excursion",
                ":MATH1:FFT:SEARch:ORDer": "order",
            }
            key = mapping[head]
            self.state[key] = {"search_enabled": value == "1"}.get(key, value)
            if key in {"averages", "peak_count"}:
                self.state[key] = int(value)
            elif key not in {"source", "window", "unit", "mode", "order", "search_enabled"}:
                self.state[key] = float(value)


def test_set_fft_orders_dependencies_and_returns_actual_readback():
    session = FakeSession()

    result = set_fft(
        session,
        math=1,
        unit="VRMS",
        mode="AVER",
        averages=32,
        scale=0.25,
        offset=0.1,
        start_hz=2_000_000,
        end_hz=8_000_000,
        search_enabled=True,
        peak_count=3,
        threshold=0.02,
        excursion=0.5,
        order="FREQ",
    )

    assert result["operator"] == "FFT"
    assert result["unit"] == "VRMS"
    assert result["mode"] == "AVER"
    assert result["averages"] == 32
    assert result["start_hz"] == 2_000_000
    assert result["end_hz"] == 8_000_000
    assert result["order"] == "FREQ"
    assert session.writes.index(":MATH1:FFT:UNIT VRMS") < session.writes.index(":MATH1:FFT:SCALe 0.25")
    assert session.writes.index(":MATH1:FFT:MODE AVER") < session.writes.index(":MATH1:FFT:AVCNt 32")
    assert session.writes[-1] == ":MATH1:FFT:SEARch:ENABle 1"


def test_invalid_frequency_pair_is_rejected_before_any_write():
    session = FakeSession()

    with pytest.raises(ValueError, match="incompatible"):
        set_fft(session, math=1, center_hz=1_000, start_hz=0, end_hz=10_000)

    assert session.writes == []


def test_peak_table_preserves_units_and_parses_frequency():
    session = FakeSession()
    session.state["search_enabled"] = True
    session.raw_results = "1,2.50000MHz,-24.98dBV\n2,3kHz,-10.0dBm\n3,4Hz,-2DB"

    result = read_fft(session, math=1)

    assert result["scope"] == "peak_table_only"
    assert result["peaks"][0]["frequency_hz"] == 2_500_000
    assert result["peaks"][0]["amplitude"] == -24.98
    assert result["peaks"][0]["amplitude_unit"] == "dBV"
    assert result["peaks"][1]["amplitude_unit"] == "dBm"
    assert result["peaks"][2]["amplitude_unit"] == "DB"
    assert result["peaks"][0]["raw"] == "1,2.50000MHz,-24.98dBV"


def test_empty_peak_table_is_valid():
    session = FakeSession()
    session.state["search_enabled"] = True

    result = read_fft(session, math=1)

    assert result["count"] == 0
    assert result["peaks"] == []


def test_non_fft_operator_is_not_reported_as_fft():
    session = FakeSession(operator="ADD")

    result = get_fft(session, math=1)

    assert result["fft_configured"] is False
    assert result["applicable"] is False
    assert "source" not in result


class FullSpectrumSession(FakeSession):
    def __init__(self):
        super().__init__()
        self.waveform_state = {
            "source": "CHAN1", "mode": "RAW", "format": "BYTE",
            "start": 20, "stop": 30, "points": 11,
        }
        self.waveform_writes = []

    def query(self, command):
        wave_queries = {
            ":WAVeform:SOURce?": "source", ":WAVeform:MODE?": "mode",
            ":WAVeform:FORMat?": "format", ":WAVeform:STARt?": "start",
            ":WAVeform:STOP?": "stop", ":WAVeform:POINts?": "points",
        }
        if command in wave_queries:
            value = self.waveform_state[wave_queries[command]]
            return str(value)
        if command == ":WAVeform:PREamble?":
            return f"2,0,{self.waveform_state['points']},1,0.5,1.0,0,1,0,0"
        if command == ":WAVeform:DATA?":
            return ",".join(str(10 + i) for i in range(self.waveform_state["points"]))
        if command == ":ACQuire:MDEPth?":
            return "1000000"
        return super().query(command)

    def write(self, command):
        if command.startswith(":WAVeform:"):
            self.waveform_writes.append(command)
            head, value = command.rsplit(" ", 1)
            mapping = {
                ":WAVeform:SOURce": "source", ":WAVeform:MODE": "mode",
                ":WAVeform:FORMat": "format", ":WAVeform:STARt": "start",
                ":WAVeform:STOP": "stop", ":WAVeform:POINts": "points",
            }
            key = mapping[head]
            self.waveform_state[key] = int(value) if key in {"start", "stop", "points"} else value
            return
        super().write(command)


def test_full_fft_reads_math_waveform_and_does_not_guess_hz_axis():
    session = FullSpectrumSession()

    result = read_fft(session, math=1, full_spectrum=True, points=3)

    assert result["scope"] == "full_spectrum_from_math_waveform"
    assert result["spectrum"]["samples"] == [10.0, 11.0, 12.0]
    assert result["spectrum"]["native_axis"] == [1.0, 1.5, 2.0]
    assert result["spectrum"]["native_axis_unit"] is None
    assert result["spectrum"]["axis_encoding"]["status"] == "unresolved"
    assert "frequency_hz" not in result["spectrum"]
    assert result["spectrum"]["amplitude_unit"] == "DB"
    assert result["spectrum"]["preamble_raw"].startswith("2,0,3,")
    assert session.waveform_state == {
        "source": "CHAN1", "mode": "RAW", "format": "BYTE",
        "start": 20, "stop": 30, "points": 11,
    }
