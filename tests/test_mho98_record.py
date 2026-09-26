import pytest

from rigol_mcp.mho98.record import get_recording, recording_action, set_recording


class FakeRecordSession:
    def __init__(self, *, replay_max=40, enabled=False, record_operate="STOP", replay_operate="STOP"):
        self.state = {
            ":RECord:WRECord:ENABle": "1" if enabled else "0",
            ":RECord:WRECord:OPERate": record_operate,
            ":RECord:WRECord:FRAMes": "100",
            ":RECord:WRECord:FMAX": "1000",
            ":RECord:WRECord:FINTerval": "1.0E-3",
            ":RECord:WRECord:PROMpt": "1",
            ":RECord:WREPlay:FMAX": str(replay_max),
            ":RECord:WREPlay:FCURrent": "10",
            ":RECord:WREPlay:FCURrent:TIME": "12.5 ms",
            ":RECord:WREPlay:FSTart": "5",
            ":RECord:WREPlay:FEND": "30",
            ":RECord:WREPlay:FINTerval": "0.1",
            ":RECord:WREPlay:MODE": "SING",
            ":RECord:WREPlay:DIRection": "FORW",
            ":RECord:WREPlay:OPERate": replay_operate,
        }
        self.queries = []
        self.writes = []

    def query(self, command):
        self.queries.append(command)
        key = command.removesuffix("?")
        if key not in self.state:
            raise AssertionError(f"unexpected query: {command}")
        return self.state[key]

    def write(self, command):
        self.writes.append(command)
        if command == ":RECord:WRECord:FRAMes:MAX":
            self.state[":RECord:WRECord:FRAMes"] = self.state[":RECord:WRECord:FMAX"]
            return
        if command in {
            ":RECord:WREPlay:BACK",
            ":RECord:WREPlay:NEXT",
            ":RECord:WREPlay:PLAY FFIRst",
            ":RECord:WREPlay:PLAY FEND",
        }:
            return
        head, value = command.split(" ", 1)
        self.state[head] = value


def test_zero_recorded_frames_skip_invalid_replay_queries():
    session = FakeRecordSession(replay_max=0)

    result = get_recording(session)

    assert result["replay_max_frames"] == 0
    assert result["current_frame"] is None
    assert ":RECord:WREPlay:FCURrent?" not in session.queries


def test_configuration_preserves_omissions_and_never_operates():
    session = FakeRecordSession(enabled=True)

    result = set_recording(
        session,
        frames=200,
        record_interval_s=0.002,
        current_frame=20,
        start_frame=15,
        end_frame=35,
        replay_interval_s=0.2,
        mode="repeat",
        direction="backward",
    )

    assert result["frames"] == 200
    assert result["mode"] == "REP"
    assert result["direction"] == "BACK"
    assert not any("OPERate " in command for command in session.writes)
    assert session.writes == [
        ":RECord:WRECord:FRAMes 200",
        ":RECord:WRECord:FINTerval 0.002",
        ":RECord:WREPlay:FSTart 15",
        ":RECord:WREPlay:FEND 35",
        ":RECord:WREPlay:FCURrent 20",
        ":RECord:WREPlay:FINTerval 0.2",
        ":RECord:WREPlay:MODE REPeat",
        ":RECord:WREPlay:DIRection BACKward",
    ]


@pytest.mark.parametrize(
    ("action", "command"),
    [
        ("record_start", ":RECord:WRECord:OPERate RUN"),
        ("record_stop", ":RECord:WRECord:OPERate STOP"),
        ("replay_start", ":RECord:WREPlay:OPERate RUN"),
        ("replay_stop", ":RECord:WREPlay:OPERate STOP"),
        ("next", ":RECord:WREPlay:NEXT"),
        ("back", ":RECord:WREPlay:BACK"),
        ("maxframes", ":RECord:WRECord:FRAMes:MAX"),
    ],
)
def test_actions_are_explicit_and_describe_effect(action, command):
    session = FakeRecordSession(enabled=True)

    result = recording_action(session, action=action)

    assert session.writes == [command]
    assert result["action"] == action
    assert result["effect"]


def test_invalid_bounds_and_state_fail_before_writes():
    session = FakeRecordSession(enabled=True)
    with pytest.raises(ValueError, match="less than or equal"):
        set_recording(session, start_frame=31, end_frame=30)
    assert session.writes == []

    with pytest.raises(ValueError, match="current replay maximum"):
        set_recording(session, current_frame=41)
    assert session.writes == []

    session = FakeRecordSession(enabled=False)
    with pytest.raises(ValueError, match="requires recording enabled"):
        recording_action(session, action="record_start")
    assert session.writes == []


def test_aliases_use_one_canonical_command_path():
    session = FakeRecordSession(enabled=True)

    recording_action(session, action="START_RECORD")
    recording_action(session, action="MAX_FRAMES")

    assert session.writes == [
        ":RECord:WRECord:OPERate RUN",
        ":RECord:WRECord:FRAMes:MAX",
    ]
