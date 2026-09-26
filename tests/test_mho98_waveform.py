"""Offline waveform transfer tests for MHO98."""

import csv
from pathlib import Path

import pytest

from rigol_mcp.mho98 import waveform
from rigol_mcp.mho98.waveform import export_waveform_csv, get_waveform, screenshot


class FakeSession:
    def __init__(self, output_dir, *, status="STOP"):
        self.output_dir = Path(output_dir)
        self.status = status
        self.state = {
            "source": "CHAN1",
            "mode": "RAW",
            "format": "BYTE",
            "start": 20,
            "stop": 30,
            "points": 11,
        }
        self.queries = []
        self.writes = []
        self.png = b"\x89PNG\r\n\x1a\nrest"

    def query(self, command):
        self.queries.append(command)
        if command == ":WAVeform:SOURce?":
            return self.state["source"]
        if command == ":WAVeform:MODE?":
            return self.state["mode"]
        if command == ":WAVeform:FORMat?":
            return self.state["format"]
        if command == ":WAVeform:STARt?":
            return str(self.state["start"])
        if command == ":WAVeform:STOP?":
            return str(self.state["stop"])
        if command == ":WAVeform:POINts?":
            return str(self.state["points"])
        if command == ":TRIGger:STATus?":
            return self.status
        if command.startswith(":CHANnel") and command.endswith(":DISPlay?"):
            return "1"
        if command == ":WAVeform:PREamble?":
            return f"2,0,{self.state['points']},1,0.5,1.0,0,1,0,0"
        if command == ":WAVeform:DATA?":
            first = self.state["start"]
            return ",".join(str(first + i) for i in range(self.state["points"]))
        raise AssertionError(f"unexpected query: {command}")

    def write(self, command):
        self.writes.append(command)
        head, value = command.rsplit(" ", 1)
        if head == ":WAVeform:SOURce":
            self.state["source"] = value
        elif head == ":WAVeform:MODE":
            self.state["mode"] = value
        elif head == ":WAVeform:FORMat":
            self.state["format"] = value
        elif head == ":WAVeform:STARt":
            self.state["start"] = int(value)
        elif head == ":WAVeform:STOP":
            self.state["stop"] = int(value)
        elif head == ":WAVeform:POINts":
            self.state["points"] = int(value)

    def binary_query(self, command):
        self.queries.append(command)
        return self.png


def test_get_waveform_returns_exact_values_time_and_preamble_and_restores_state():
    session = FakeSession("/tmp/mho98-waveform-test")
    original = dict(session.state)

    result = get_waveform(session, source="CH1", start=2, points=3)

    assert result["values"] == [2.0, 3.0, 4.0]
    assert result["time"] == [1.5, 2.0, 2.5]
    assert result["preamble"]["points"] == 3
    assert session.state == original
    assert not any(command.startswith(":RUN") or command.startswith(":STOP") for command in session.writes)


def test_export_raw_is_chunked_and_restores_transfer_state(tmp_path, monkeypatch):
    session = FakeSession(tmp_path, status="STOP")
    original = dict(session.state)
    monkeypatch.setattr(waveform, "_EXPORT_CHUNK_POINTS", 2)

    result = export_waveform_csv(session, source="CH1", mode="RAW", start=1, points=5, filename="wave.csv")

    path = Path(result["path"])
    assert path == tmp_path / "wave.csv"
    with path.open(newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == ["index", "time", "value"]
    assert len(rows) == 6
    assert rows[1][0] == "1"
    assert rows[-1][0] == "5"
    assert session.state == original


def test_raw_export_rejects_running_scope_without_stopping_it(tmp_path):
    session = FakeSession(tmp_path, status="RUN")

    with pytest.raises(ValueError, match="requires STOP"):
        export_waveform_csv(session, mode="RAW", points=2, filename="running.csv")

    assert session.writes == []
    assert not (tmp_path / "running.csv").exists()


def test_math_source_raw_is_rejected_without_mutation(tmp_path):
    session = FakeSession(tmp_path, status="STOP")

    with pytest.raises(ValueError, match="MATH.*NORM"):
        export_waveform_csv(session, source="MATH1", mode="RAW", points=2, filename="math.csv")

    assert session.writes == []


def test_screenshot_validates_png_and_uses_new_file(tmp_path):
    session = FakeSession(tmp_path)

    result = screenshot(session, filename="screen.png")

    assert result["mime_type"] == "image/png"
    assert Path(result["path"]).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    with pytest.raises(FileExistsError):
        screenshot(session, filename="screen.png")


def test_get_waveform_rejects_nonfinite_or_wrong_count(tmp_path):
    session = FakeSession(tmp_path)
    session.query = lambda command: "nan,nan" if command == ":WAVeform:DATA?" else FakeSession.query(session, command)

    with pytest.raises(ValueError, match="finite"):
        get_waveform(session, points=2)


class BinarySession(FakeSession):
    def __init__(self, output_dir, *, fmt="BYTE"):
        super().__init__(output_dir, status="STOP")
        self.state["format"] = fmt
        self.binary_calls = []

    def query(self, command):
        if command == ":ACQuire:MDEPth?":
            return "500000000"
        if command == ":WAVeform:PREamble?":
            code = {"BYTE": 0, "WORD": 1, "ASC": 2}[self.state["format"]]
            return f"{code},2,{self.state['points']},1,0.5,1.0,0,2,1,2"
        return super().query(command)

    def binary_query(self, command):
        self.binary_calls.append(command)
        if self.state["format"] == "BYTE":
            return bytes([10 + i for i in range(self.state["points"])])
        return b"".join((10 + i).to_bytes(2, "little") for i in range(self.state["points"]))


def test_binary_byte_and_declared_word_conversion_restore_exact_payload(tmp_path):
    byte_session = BinarySession(tmp_path / "byte", fmt="BYTE")
    original = dict(byte_session.state)
    byte_result = get_waveform(byte_session, mode="RAW", format="BYTE", points=2)

    assert byte_result["values"] == [14.0, 16.0]
    assert byte_result["raw_bytes_hex"] == "0a0b"
    assert byte_result["encoding"]["status"] == "verified"
    assert byte_session.state == original

    word_session = BinarySession(tmp_path / "word", fmt="WORD")
    with pytest.raises(ValueError, match="caller-declared"):
        get_waveform(word_session, mode="RAW", format="WORD", points=2)
    result = get_waveform(
        word_session, mode="RAW", format="WORD", points=2,
        encoding={"byte_order": "little", "signed": False},
    )
    assert result["values"] == [14.0, 16.0]
    assert result["raw_bytes_hex"] == "0a000b00"
    assert result["encoding"]["status"] == "caller_declared"


def test_max_uses_existing_run_stop_state_without_implicit_run_stop(tmp_path):
    running = FakeSession(tmp_path / "run", status="RUN")
    run_result = get_waveform(running, mode="MAX", points=2)
    assert run_result["mode"] == "MAX"
    assert not any(command in {":RUN", ":STOP"} for command in running.writes)

    stopped = FakeSession(tmp_path / "stop", status="STOP")
    stop_result = get_waveform(stopped, mode="MAX", points=2)
    assert stop_result["mode"] == "MAX"
    assert not any(command in {":RUN", ":STOP"} for command in stopped.writes)


def test_csv_stream_accepts_more_than_one_million_points_with_compact_fake(tmp_path, monkeypatch):
    session = FakeSession(tmp_path, status="STOP")
    calls = []
    monkeypatch.setattr(waveform, "_EXPORT_CHUNK_POINTS", 2_000_000)

    def compact_chunk(session_arg, current, selected, mode, fmt, start, chunk, encoding):
        calls.append(chunk)
        return ({"raw": "2,0,1,1,0.5,1,0,1,0,0", "format_code": 2,
                 "type_code": 0, "points": chunk, "count": 1,
                 "xincrement": 0.5, "xorigin": 1.0, "xreference": 0,
                 "yincrement": 1.0, "yorigin": 0.0, "yreference": 0.0}, [1.0], None)

    monkeypatch.setattr(waveform, "_read_chunk", compact_chunk)
    result = export_waveform_csv(session, mode="RAW", points=1_000_001, filename="large.csv")

    assert result["points"] == 1_000_001
    assert calls == [1_000_001]
    assert Path(result["path"]).read_text().count("\n") == 2
