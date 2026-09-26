"""Read-only MHO98 measurement tools.

The MHO98 measurement query does not require a measurement to be registered or
displayed first.  These handlers therefore issue only the documented query and
leave acquisition, channel enable state, and measurement registration alone.
"""

from __future__ import annotations

import math
import re
from typing import Any

from .api import ToolSpec


# This is the complete MHO98 ``:MEASure:ITEM`` enumeration from the programming
# guide.  In particular, MHO98 has ACRMS and does not document VARIANCE.
SINGLE_SOURCE_ITEMS = frozenset(
    {
        "VMAX",
        "VMIN",
        "VPP",
        "VTOP",
        "VBASE",
        "VAMP",
        "VAVG",
        "VRMS",
        "OVERSHOOT",
        "PRESHOOT",
        "MAREA",
        "MPAREA",
        "PERIOD",
        "FREQUENCY",
        "RTIME",
        "FTIME",
        "PWIDTH",
        "NWIDTH",
        "PDUTY",
        "NDUTY",
        "TVMAX",
        "TVMIN",
        "PSLEWRATE",
        "NSLEWRATE",
        "VUPPER",
        "VMID",
        "VLOWER",
        "PVRMS",
        "PPULSES",
        "NPULSES",
        "PEDGES",
        "NEDGES",
        "ACRMS",
    }
)

TWO_SOURCE_ITEMS = frozenset(
    {
        "RRDELAY",
        "RFDELAY",
        "FRDELAY",
        "FFDELAY",
        "RRPHASE",
        "RFPHASE",
        "FRPHASE",
        "FFPHASE",
    }
)

ALL_ITEMS = frozenset(SINGLE_SOURCE_ITEMS | TWO_SOURCE_ITEMS)

# Familiar names used by older Rigol families.  They map to the homogeneous
# edge pair on MHO98, while the four native mixed-edge forms remain available.
TWO_SOURCE_ALIASES = {
    "RDELAY": "RRDELAY",
    "FDELAY": "FFDELAY",
    "RPHASE": "RRPHASE",
    "FPHASE": "FFPHASE",
}

STATISTICS = frozenset({"MAXIMUM", "MINIMUM", "CURRENT", "AVERAGES", "DEVIATION", "CNT"})

_SOURCE_RE = re.compile(r"^(?:CH(?:AN)?([1-4])|MATH([1-4])|D(?:([0-9])|1([0-5])))$", re.IGNORECASE)

# Units explicitly implied by the MHO98 measurement descriptions.  Voltage-like
# results depend on a channel's UNITS setting or on the MATH expression, so they
# are marked source-dependent rather than being mislabeled as volts.
_UNITS: dict[str, str | None] = {
    **{item: "source-dependent" for item in (
        "VMAX", "VMIN", "VPP", "VTOP", "VBASE", "VAMP", "VAVG", "VRMS",
        "VUPPER", "VMID", "VLOWER", "PVRMS", "ACRMS",
    )},
    **{item: "s" for item in (
        "PERIOD", "RTIME", "FTIME", "PWIDTH", "NWIDTH", "TVMAX", "TVMIN",
        "RRDELAY", "RFDELAY", "FRDELAY", "FFDELAY",
    )},
    **{item: "Hz" for item in ("FREQUENCY",)},
    **{item: "source-dependent/s" for item in ("PSLEWRATE", "NSLEWRATE")},
    **{item: "source-dependent*s" for item in ("MAREA", "MPAREA")},
    **{item: "deg" for item in ("RRPHASE", "RFPHASE", "FRPHASE", "FFPHASE")},
    **{item: "count" for item in ("PPULSES", "NPULSES", "PEDGES", "NEDGES")},
    "OVERSHOOT": None,
    "PRESHOOT": None,
    "PDUTY": None,
    "NDUTY": None,
}

_INVALID_SENTINEL = 9.0e37


def _normalize_source(source: str) -> str:
    """Validate a measurement source and return the SCPI short spelling."""
    if not isinstance(source, str):
        raise ValueError("source must be one of CH1-CH4, MATH1-MATH4, or D0-D15")
    token = source.strip().upper()
    match = _SOURCE_RE.fullmatch(token)
    if not match:
        raise ValueError(
            f"Invalid measurement source {source!r}; expected CH1-CH4, MATH1-MATH4, or D0-D15"
        )
    channel, math_channel, digital0, digital1 = match.groups()
    if channel:
        return f"CHAN{channel}"
    if math_channel:
        return f"MATH{math_channel}"
    if digital1:
        return f"D1{digital1}"
    return f"D{digital0}"


def _normalize_item(item: str, *, allow_two_source: bool) -> str:
    if not isinstance(item, str):
        raise ValueError("item must be an MHO98 measurement item")
    requested = item.strip().upper()
    canonical = TWO_SOURCE_ALIASES.get(requested, requested)
    valid = ALL_ITEMS if allow_two_source else SINGLE_SOURCE_ITEMS
    if canonical not in valid:
        if not allow_two_source and requested in TWO_SOURCE_ITEMS | set(TWO_SOURCE_ALIASES):
            raise ValueError(f"{item!r} requires two sources; use measure_between()")
        raise ValueError(f"Unknown MHO98 measurement item {item!r}")
    return canonical


def _normalize_statistic(statistic: str) -> str:
    if not isinstance(statistic, str):
        raise ValueError("statistic must be MAXIMUM, MINIMUM, CURRENT, AVERAGES, DEVIATION, or CNT")
    token = statistic.strip().upper()
    if token not in STATISTICS:
        raise ValueError(
            f"Unknown MHO98 measurement statistic {statistic!r}; "
            f"expected one of {sorted(STATISTICS)}"
        )
    return token


def _read_result(
    session: Any,
    command: str,
    *,
    item: str,
    sources: tuple[str, ...],
    statistic: str | None = None,
) -> dict[str, Any]:
    raw = str(session.query(command)).strip()
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = None
        valid = False
        reason = "not a real measurement (non-numeric reply)"
    else:
        if not math.isfinite(value):
            value = None
            valid = False
            reason = "not a real measurement (non-finite reply)"
        elif abs(value) >= _INVALID_SENTINEL:
            valid = False
            reason = "not a real measurement (scope sentinel)"
        else:
            valid = True
            reason = None

    result: dict[str, Any] = {
        "valid": valid,
        "value": value,
        "raw": raw,
        "sources": list(sources),
        "item": item,
        "unit": _UNITS[item],
    }
    if len(sources) == 1:
        result["source"] = sources[0]
    if len(sources) == 2:
        result["source1"] = sources[0]
        result["source2"] = sources[1]
    if statistic is not None:
        result["statistic"] = statistic
        if statistic == "CNT":
            result["unit"] = "count"
    result["acquisition_type"] = str(session.query(":ACQuire:TYPE?")).strip()
    if result["unit"] and "source-dependent" in result["unit"] and sources[0].startswith("CHAN"):
        raw_unit = str(session.query(f":CHANnel{sources[0][4:]}:UNITs?")).strip().upper()
        unit = {"VOLT": "V", "VOLTAGE": "V", "AMP": "A", "AMPERE": "A", "WATT": "W", "UNKN": "unknown", "UNKNOWN": "unknown"}.get(raw_unit, raw_unit)
        result["source_unit_raw"] = raw_unit
        result["unit"] = result["unit"].replace("source-dependent", unit)
    if reason is not None:
        result["reason"] = reason
    return result


def measure(session: Any, channel: str, item: str) -> dict[str, Any]:
    """Read one MHO98 single-source measurement without changing scope state."""
    source = _normalize_source(channel)
    canonical_item = _normalize_item(item, allow_two_source=False)
    return _read_result(
        session,
        f":MEASure:ITEM? {canonical_item},{source}",
        item=canonical_item,
        sources=(source,),
    )


def measure_between(session: Any, source1: str, source2: str, item: str) -> dict[str, Any]:
    """Read one MHO98 two-source delay or phase measurement."""
    first = _normalize_source(source1)
    second = _normalize_source(source2)
    canonical_item = _normalize_item(item, allow_two_source=True)
    if canonical_item not in TWO_SOURCE_ITEMS:
        raise ValueError(f"{item!r} is a single-source item; use measure()")
    return _read_result(
        session,
        f":MEASure:ITEM? {canonical_item},{first},{second}",
        item=canonical_item,
        sources=(first, second),
    )


def measure_statistics(
    session: Any,
    channel: str,
    item: str,
    statistic: str,
    source2: str | None = None,
) -> dict[str, Any]:
    """Read one MHO98 measurement statistic without enabling statistics globally."""
    first = _normalize_source(channel)
    canonical_item = _normalize_item(item, allow_two_source=True)
    stat = _normalize_statistic(statistic)
    is_two_source = canonical_item in TWO_SOURCE_ITEMS
    if is_two_source and source2 is None:
        raise ValueError(f"{item!r} requires source2 for a two-source statistic")
    if not is_two_source and source2 is not None:
        raise ValueError(f"{item!r} is a single-source item and does not accept source2")

    sources = (first,)
    if source2 is not None:
        second = _normalize_source(source2)
        sources = (first, second)
    arguments = ",".join((stat, canonical_item, *sources))
    return _read_result(
        session,
        f":MEASure:STATistic:ITEM? {arguments}",
        item=canonical_item,
        sources=sources,
        statistic=stat,
    )


_SOURCE_ENUM = [f"CH{i}" for i in range(1, 5)] + [f"MATH{i}" for i in range(1, 5)] + [f"D{i}" for i in range(16)]
_ITEM_ENUM = sorted(ALL_ITEMS | set(TWO_SOURCE_ALIASES))

TOOLS = (
    ToolSpec(
        name="measure",
        description="Read one MHO98 single-source measurement without changing scope state.",
        input_schema={
            "type": "object",
            "properties": {
                "channel": {"type": "string", "enum": _SOURCE_ENUM},
                "item": {"type": "string", "enum": sorted(SINGLE_SOURCE_ITEMS)},
            },
            "required": ["channel", "item"],
        },
        handler=measure,
        read_only=True,
        needs_session=True,
    ),
    ToolSpec(
        name="measure_between",
        description="Read one MHO98 two-source delay or phase measurement without changing scope state.",
        input_schema={
            "type": "object",
            "properties": {
                "source1": {"type": "string", "enum": _SOURCE_ENUM},
                "source2": {"type": "string", "enum": _SOURCE_ENUM},
                "item": {"type": "string", "enum": sorted(TWO_SOURCE_ITEMS | set(TWO_SOURCE_ALIASES))},
            },
            "required": ["source1", "source2", "item"],
        },
        handler=measure_between,
        read_only=True,
        needs_session=True,
    ),
    ToolSpec(
        name="measure_statistics",
        description="Read one MHO98 measurement statistic without changing scope state.",
        input_schema={
            "type": "object",
            "properties": {
                "channel": {"type": "string", "enum": _SOURCE_ENUM},
                "item": {"type": "string", "enum": _ITEM_ENUM},
                "statistic": {"type": "string", "enum": sorted(STATISTICS)},
                "source2": {"type": ["string", "null"], "enum": _SOURCE_ENUM + [None]},
            },
            "required": ["channel", "item", "statistic"],
        },
        handler=measure_statistics,
        read_only=True,
        needs_session=True,
    ),
)
