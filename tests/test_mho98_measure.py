"""Offline contract tests for the MHO98 read-only measurement handlers."""

import math

import pytest

from rigol_mcp.mho98.measure import (
    measure,
    measure_between,
    measure_statistics,
)


class FakeSession:
    def __init__(self, responses):
        self.responses = dict(responses)
        self.queries = []
        self.writes = []

    def query(self, command):
        self.queries.append(command)
        for prefix, value in self.responses.items():
            if command == prefix or command.startswith(prefix):
                return value
        raise AssertionError(f"unexpected query: {command}")

    def write(self, command):
        self.writes.append(command)


def test_measure_returns_numeric_value_and_raw_reply_without_registration():
    session = FakeSession(
        {
            ":CHANnel1:DISPlay?": "1",
            ":MEASure:ITEM? VPP,CHAN1": "1.250000E+00\n",
        }
    )

    result = measure(session, "CH1", "VPP")

    assert result == {
        "valid": True,
        "value": 1.25,
        "raw": "1.250000E+00",
        "sources": ["CHAN1"],
        "source": "CHAN1",
        "item": "VPP",
        "unit": "source-dependent",
    }
    assert session.writes == []
    assert session.queries == [":CHANnel1:DISPlay?", ":MEASure:ITEM? VPP,CHAN1"]


def test_measure_sentinel_is_invalid_and_preserves_numeric_raw_value():
    session = FakeSession(
        {
            ":CHANnel2:DISPlay?": "1",
            ":MEASure:ITEM? FREQUENCY,CHAN2": "9.900000E+37",
        }
    )

    result = measure(session, "CHAN2", "FREQUENCY")

    assert result["valid"] is False
    assert result["value"] == 9.9e37
    assert result["raw"] == "9.900000E+37"
    assert "not a real measurement" in result["reason"]


def test_disabled_analog_source_is_rejected_before_measurement_query():
    session = FakeSession({":CHANnel3:DISPlay?": "0"})

    with pytest.raises(ValueError, match="disabled"):
        measure(session, "CH3", "VAVG")

    assert session.queries == [":CHANnel3:DISPlay?"]
    assert session.writes == []


def test_measure_between_maps_familiar_alias_and_keeps_two_sources():
    session = FakeSession(
        {
            ":CHANnel1:DISPlay?": "1",
            ":CHANnel2:DISPlay?": "1",
            ":MEASure:ITEM? RRDELAY,CHAN1,CHAN2": "2.5E-06",
        }
    )

    result = measure_between(session, "CH1", "CH2", "RDELAY")

    assert result["valid"] is True
    assert result["value"] == 2.5e-6
    assert result["item"] == "RRDELAY"
    assert result["unit"] == "s"
    assert result["sources"] == ["CHAN1", "CHAN2"]
    assert session.writes == []


def test_statistics_query_order_and_cnt_unit():
    session = FakeSession(
        {
            ":MEASure:STATistic:ITEM? CNT,RRDELAY,CHAN1,CHAN2": "12",
            ":CHANnel1:DISPlay?": "1",
            ":CHANnel2:DISPlay?": "1",
        }
    )

    result = measure_statistics(session, "CH1", "RRDELAY", "CNT", source2="CH2")

    assert result["valid"] is True
    assert result["value"] == 12.0
    assert result["statistic"] == "CNT"
    assert result["unit"] == "count"
    assert session.queries[-1] == ":MEASure:STATistic:ITEM? CNT,RRDELAY,CHAN1,CHAN2"
    assert session.writes == []


def test_invalid_item_is_rejected_before_any_session_query():
    session = FakeSession({})

    with pytest.raises(ValueError, match="Unknown MHO98 measurement item"):
        measure(session, "CH1", "VARIANCE")

    assert session.queries == []


def test_nonfinite_reply_is_invalid():
    session = FakeSession(
        {
            ":CHANnel1:DISPlay?": "1",
            ":MEASure:ITEM? VRMS,CHAN1": "nan",
        }
    )

    result = measure(session, "CH1", "VRMS")

    assert result["valid"] is False
    assert result["value"] is None or math.isnan(result["value"])
    assert "non-finite" in result["reason"]
