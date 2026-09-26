"""Offline contract checks for the packaged MHO98 documentation catalog."""

from rigol_mcp.mho98.catalog import TOOLS, describe_command, search_commands


def test_catalog_retains_all_documented_leaf_entries_and_paginates():
    first = search_commands(limit=7)
    assert first["total"] == 654
    assert first["offset"] == 0
    assert len(first["commands"]) == 7
    assert first["commands"][0]["id"] == "acquire-averages-count-001"

    later = search_commands(offset=7, limit=7)
    assert later["commands"][0]["id"] != first["commands"][0]["id"]


def test_search_supports_family_and_command_text():
    bus = search_commands(family="bus", limit=100)
    assert bus["total"] > 0
    assert all(item["family"].startswith("bus") for item in bus["commands"])

    waveform = search_commands(query="PREamble", limit=20)
    assert waveform["total"] >= 1
    assert any(":WAVeform:PREamble?" in form for item in waveform["commands"] for form in item["syntax"])


def test_describe_retains_execution_facts_without_manual_text():
    found = search_commands(query="WAVetype", limit=5)
    assert found["total"] == 1
    entry = describe_command(found["commands"][0]["id"])
    assert entry["set_syntax"] == ":MATH<n>:MATH<n>:WAVetype <type>"
    assert entry["query_syntax"] == [":MATH<n>:WAVetype?"]
    assert entry["parameters"][0] == {"name": "<type>", "type": "Discrete", "range": "{MAIN|ZOOM}"}
    assert entry["errata"][0]["corrected"] == ":MATH<n>:WAVetype <type>"
    for offset in range(0, 654, 100):
        for item in search_commands(offset=offset, limit=100)["commands"]:
            record = describe_command(item["id"])
            assert set(record) == {"id", "command", "family", "set_syntax", "query_syntax", "syntax_forms", "parameters", "errata"}
            assert all(set(p) <= {"name", "type", "range"} for p in record["parameters"])


def test_catalog_tools_are_session_free():
    assert {tool.name for tool in TOOLS} == {"search_commands", "describe_command"}
    assert all(tool.needs_session is False and tool.read_only for tool in TOOLS)
