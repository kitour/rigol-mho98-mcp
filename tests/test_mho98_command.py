import pytest

from rigol_mcp.mho98.command import query_command, write_command


class FakeSession:
    def __init__(self, reply="OK"):
        self.reply = reply
        self.queries = []
        self.writes = []

    def query(self, command):
        self.queries.append(command)
        return self.reply

    def write(self, command):
        self.writes.append(command)


def test_channel_query_and_write_construct_canonical_indexed_syntax():
    session = FakeSession("OMEG")
    result = query_command(session, "channel-n-impedance-impedance-098", {"n": 2})
    assert session.queries == [":CHANnel2:IMPedance?"]
    assert result["value"] == "OMEG"
    assert result["conditions_checked"] == "syntax and static parameter constraints only"

    write_result = write_command(
        session,
        "channel-n-impedance-impedance-098",
        {"n": 2},
        ["FIFT"],
    )
    assert session.writes == [":CHANnel2:IMPedance FIFTy"]
    assert write_result["written"] is True


def test_representative_trigger_bus_math_and_repeated_measurement_arguments():
    session = FakeSession()
    write_command(session, "trigger-edge-source-source-488", arguments=["CH2"])
    write_command(session, "bus-n-mode-mode-030", {"n": 3}, ["CAN"])
    corrected = write_command(session, "math-n-math-n-wavetype-type-264", {"n": 1}, ["ZOOM"])
    query_command(session, "measure-item-item-src-src-295", arguments=["RRDelay", "CH1", "CHAN2"])

    assert session.writes == [
        ":TRIGger:EDGE:SOURce CHANnel2",
        ":BUS3:MODE CAN",
        ":MATH1:WAVetype ZOOM",
    ]
    assert corrected["corrections"][0]["corrected"] == ":MATH<n>:WAVetype <type>"
    assert session.queries == [":MEASure:ITEM? RRDelay,CHANnel1,CHANnel2"]


@pytest.mark.parametrize(
    "command_id,operation,indices,arguments,pattern",
    [
        ("channel-n-impedance-impedance-098", "write", {"n": 5}, ["OMEG"], "indices.n"),
        ("channel-n-impedance-impedance-098", "write", {"n": 1}, ["BAD"], "outside"),
        ("channel-n-impedance-impedance-098", "write", {"n": 1}, ["OMEG", "extra"], "arguments"),
        ("acquire-averages-count-001", "write", {}, [float("nan")], "integer"),
        ("measure-item-item-src-src-295", "query", {}, ["VPP", "CH1", "CH2", "CH3"], "arguments"),
    ],
)
def test_bad_index_enum_argument_count_or_nonfinite_is_rejected_before_io(
    command_id, operation, indices, arguments, pattern
):
    session = FakeSession()
    with pytest.raises(ValueError, match=pattern):
        (write_command if operation == "write" else query_command)(session, command_id, indices, arguments)
    assert session.writes == []
    assert session.queries == []


def test_optional_query_argument_and_safe_ascii_string():
    session = FakeSession()
    write_command(session, "source-n-load-arbitrary-path-172", {"n": 1}, ["C:/wave 1.arb"])
    assert session.writes == [':SOURce1:LOAD:ARBitrary "C:/wave 1.arb"']

    with pytest.raises(ValueError, match="control|separator"):
        write_command(session, "source-n-load-arbitrary-path-172", {"n": 1}, ["bad;:RUN"])
    assert session.writes == [':SOURce1:LOAD:ARBitrary "C:/wave 1.arb"']


def test_numeric_enum_and_thousands_ranges_are_validated_without_bool_coercion():
    session = FakeSession()
    write_command(session, "measure-statistic-count-val-298", arguments=[100_000])
    assert session.writes == [":MEASure:STATistic:COUNt 100000"]
    with pytest.raises(ValueError, match="outside"):
        write_command(session, "measure-statistic-count-val-298", arguments=[100_001])
    with pytest.raises(ValueError, match="outside"):
        write_command(session, "acquire-bits-bit-005", arguments=[15])
    with pytest.raises(ValueError, match="finite real"):
        write_command(session, "channel-n-offset-offset-096", {"n": 1}, [True])


def test_unvalidated_catalog_range_is_reported_in_result():
    session = FakeSession()
    result = write_command(session, "channel-n-bwlimit-val-092", {"n": 1}, ["ON"])
    assert result["static_constraints_unvalidated"]
    assert result["static_constraints_unvalidated"][0]["parameter"] == "<val>"


def test_source_and_iic_parameter_aliases_are_explicitly_corrected():
    session = FakeSession()
    pm = write_command(
        session,
        "source-n-mod-pm-internal-function-function-194",
        {"n": 1},
        ["SIN"],
    )
    iic = write_command(session, "trigger-iic-direction-direction-514", arguments=["READ"])

    assert session.writes == [
        ":SOURce1:MOD:PM:INTernal:FUNCtion SINusoid",
        ":TRIGger:IIC:DIRection READ",
    ]
    assert pm["corrections"][0]["kind"] == "metadata_parameter_alias"
    assert iic["corrections"][0]["corrected"] == "<dir>"
    assert iic["corrections"][0]["source"] == "commands/trigger/i2c.md:64-67"


def test_lin_level_uses_finite_real_without_inventing_missing_range():
    session = FakeSession()
    result = write_command(session, "trigger-lin-level-level-536", arguments=[0.25])

    assert session.writes == [":TRIGger:LIN:LEVel 0.25"]
    assert result["corrections"][0]["kind"] == "metadata_parameter_definition"
    assert result["static_constraints_unvalidated"] == [
        {"parameter": "<level>", "reason": "source documents the parameter semantics but no numeric range"}
    ]
    with pytest.raises(ValueError, match="finite real"):
        write_command(session, "trigger-lin-level-level-536", arguments=[float("inf")])
    assert session.writes == [":TRIGger:LIN:LEVel 0.25"]


@pytest.mark.parametrize(
    "command_id,operation,arguments,pattern",
    [
        ("histogram-reset-204", "query", [], "ambiguous action"),
        ("save-smb-password-password-394", "write", ["secret"], "password"),
        ("save-smb-password-password-394", "query", [], "password"),
        ("bus-n-data-035", "query", [], "binary"),
        ("save-image-data-382", "query", [], "binary"),
        ("system-setup-setup-data-434", "write", ["#10abc"], "binary"),
        ("waveform-data-645", "query", [], "binary"),
    ],
)
def test_unsafe_action_sensitive_and_binary_commands_are_explicitly_blocked(
    command_id, operation, arguments, pattern
):
    session = FakeSession()
    indices = {"n": 1} if command_id == "bus-n-data-035" else {}
    with pytest.raises(ValueError, match=pattern):
        (write_command if operation == "write" else query_command)(session, command_id, indices, arguments)
    assert session.writes == []
    assert session.queries == []
