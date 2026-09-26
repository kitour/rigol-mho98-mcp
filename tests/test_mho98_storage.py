import pytest

from rigol_mcp.mho98.storage import get_storage, load_file, save_file, set_storage


class FakeSession:
    def __init__(self, *, trigger="STOP", depth="10000", status="1", complete_save=True):
        self.state = {
            ":SAVE:PATHname": "C:/",
            ":SAVE:PREFix": "Rigol",
            ":SAVE:OVERlap": "0",
            ":SAVE:STATus": status,
            ":TRIGger:STATus": trigger,
            ":ACQuire:MDEPth": depth,
        }
        self.queries = []
        self.writes = []
        self.complete_save = complete_save

    def query(self, command):
        self.queries.append(command)
        key = command.removesuffix("?")
        if key not in self.state:
            raise AssertionError(f"unexpected query: {command}")
        return self.state[key]

    def write(self, command):
        self.writes.append(command)
        head, value = command.split(" ", 1)
        if head in {":SAVE:PATHname", ":SAVE:PREFix", ":SAVE:OVERlap"}:
            self.state[head] = value
        elif self.complete_save and head in {":SAVE:SETup", ":SAVE:WAVeform", ":SAVE:MEMory:WAVeform", ":SAVE:MASK"}:
            self.state[":SAVE:STATus"] = "1"


def test_get_and_set_storage_route_settings_and_query_status():
    session = FakeSession()

    assert get_storage(session) == {
        "pathname": "C:/",
        "prefix": "Rigol",
        "overwrite": False,
        "status": "complete",
        "status_code": 1,
    }
    result = set_storage(session, pathname="D:/captures", prefix="Run-1", overwrite=True)

    assert session.writes == [
        ":SAVE:PATHname D:/captures",
        ":SAVE:PREFix Run-1",
        ":SAVE:OVERlap 1",
    ]
    assert result["pathname"] == "D:/captures"
    assert result["prefix"] == "Run-1"
    assert result["overwrite"] is True


def test_native_path_readback_survives_unrelated_storage_change():
    session = FakeSession()
    session.state[":SAVE:PATHname"] = "/data/UserData"
    session.state[":SAVE:PREFix"] = "RigolDS"

    result = set_storage(session, overwrite=True)

    assert session.writes == [":SAVE:OVERlap 1"]
    assert result["pathname"] == "/data/UserData"
    assert result["prefix"] == "RigolDS"
    assert result["overwrite"] is True


def test_save_routes_each_non_image_kind_and_does_not_enable_overlap_implicitly():
    for kind, suffix, command in [
        ("setup", ".stp", ":SAVE:SETup"),
        ("waveform", ".csv", ":SAVE:WAVeform"),
        ("memory_waveform", ".wfm", ":SAVE:MEMory:WAVeform"),
        ("mask", ".pf", ":SAVE:MASK"),
    ]:
        session = FakeSession()
        result = save_file(session, kind, f"D:/run{suffix}")
        assert session.writes[-1] == f"{command} D:/run{suffix}"
        assert ":SAVE:OVERlap 1" not in session.writes
        assert result["status"] == "complete"


def test_memory_waveform_requires_stop_and_validates_memory_depth_before_write():
    running = FakeSession(trigger="RUN")
    with pytest.raises(ValueError, match="requires trigger status STOP"):
        save_file(running, "memory_waveform", "D:/memory.bin")
    assert running.writes == []

    invalid_depth = FakeSession(depth="not-a-depth")
    with pytest.raises(ValueError, match="invalid MHO98 memory depth"):
        save_file(invalid_depth, "memory_waveform", "D:/memory.bin")
    assert invalid_depth.writes == []


def test_pending_status_is_returned_without_claiming_completion():
    session = FakeSession(status="0", complete_save=False)
    result = save_file(session, "setup", "D:/pending.stp", overwrite=False)

    assert result["status"] == "pending"
    assert result["status_code"] == 0
    assert result["overwrite"] is False


def test_suffix_ascii_length_and_host_paths_are_rejected_before_write():
    session = FakeSession()
    bad_paths = [
        "/tmp/setup.stp",
        "D:/../setup.stp",
        "D:/setup.txt",
        "D:/é.stp",
        "D:/123456789012345678901234567.stp",
    ]
    for path in bad_paths:
        with pytest.raises(ValueError):
            save_file(session, "setup", path)
    assert session.writes == []


def test_load_only_supports_setup_and_mask_and_does_not_reset_or_upload():
    session = FakeSession()
    assert load_file(session, "setup", "C:/factory.stp") == {
        "kind": "setup", "path": "C:/factory.stp", "loaded": True,
    }
    assert load_file(session, "mask", "E:/limit.pf")["loaded"] is True
    with pytest.raises(ValueError, match="only setup and mask"):
        load_file(session, "waveform", "D:/wave.csv")
    assert session.writes == [":LOAD:SETup C:/factory.stp", ":LOAD:MASK E:/limit.pf"]
