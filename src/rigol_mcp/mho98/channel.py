"""Bounded MHO98 analog channel controls.

The handlers in this module deliberately cover only the everyday channel controls
needed by the first MHO98 integration step.  They use a small session protocol
(``query`` and ``write``) so they can be exercised without VISA or an instrument.
"""

from __future__ import annotations

import math
from numbers import Real
from typing import Any

from .api import ToolSpec


_CHANNELS = frozenset({"CHAN1", "CHAN2", "CHAN3", "CHAN4"})
def _channel(value: Any) -> str:
    """Normalize the public channel enum while accepting common SCPI aliases."""

    if isinstance(value, bool):
        raise ValueError("channel must be CHAN1 through CHAN4")
    if isinstance(value, Real) and float(value).is_integer():
        value = f"CHAN{int(value)}"
    text = str(value).strip().upper().replace(" ", "")
    if text.startswith("CHANNEL"):
        text = "CHAN" + text[7:]
    elif text.startswith("CH") and not text.startswith("CHAN"):
        text = "CHAN" + text[2:]
    if text not in _CHANNELS:
        raise ValueError("channel must be CHAN1 through CHAN4")
    return text


def _number(value: Any, name: str) -> float:
    """Return a finite real number; numeric strings are accepted by MCP schemas."""

    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    if isinstance(value, Real):
        result = float(value)
    elif isinstance(value, str):
        try:
            result = float(value.strip())
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be a finite number") from None
    else:
        raise ValueError(f"{name} must be a finite number")
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    return result


def _bool_response(value: str, name: str) -> bool:
    text = str(value).strip().upper()
    if text in {"1", "ON", "TRUE"}:
        return True
    if text in {"0", "OFF", "FALSE"}:
        return False
    raise ValueError(f"invalid {name} response from MHO98: {value!r}")


def _impedance_response(value: str) -> int:
    text = str(value).strip().upper().replace("OHM", "").replace("Ω", "")
    if text in {"FIFT", "FIFTY", "50", "50.0"}:
        return 50
    if text in {"OMEG", "OMEGA", "1M", "1MOHM", "1000000", "1000000.0"}:
        return 1_000_000
    try:
        numeric = float(text)
    except ValueError:
        numeric = math.nan
    if numeric == 50:
        return 50
    if numeric == 1_000_000:
        return 1_000_000
    raise ValueError(f"invalid impedance response from MHO98: {value!r}")


def _coupling(value: Any) -> str:
    text = str(value).strip().upper()
    if text not in {"AC", "DC", "GND"}:
        raise ValueError("coupling must be AC, DC, or GND")
    return text


def _bandwidth(value: Any) -> str:
    text = str(value).strip().upper()
    aliases = {"OFF": "OFF", "ON": "ON", "20M": "20M", "250M": "250M"}
    if text not in aliases:
        raise ValueError("bandwidth must be OFF, ON, 20M, or 250M")
    return aliases[text]


def _units(value: Any) -> str:
    text = str(value).strip().upper()
    aliases = {
        "VOLT": "VOLT",
        "VOLTAGE": "VOLT",
        "WATT": "WATT",
        "AMP": "AMP",
        "AMPERE": "AMP",
        "UNKN": "UNKN",
        "UNKNOWN": "UNKN",
    }
    if text not in aliases:
        raise ValueError("units must be VOLT, WATT, AMP, or UNKN")
    return aliases[text]


def _label_response(value: Any) -> str:
    text = str(value)
    if len(text) >= 2 and text[0] == text[-1] == '"':
        text = text[1:-1].replace('""', '"')
    return text


def _label_value(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("label must be a string")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("label must not contain control characters")
    if ";" in value or "\r" in value or "\n" in value:
        raise ValueError("label must not contain SCPI delimiters")
    # SCPI quoted strings escape a literal quote by doubling it.
    return '"' + value.replace('"', '""') + '"'


def _scpi_number(value: float) -> str:
    return format(value, ".15g")


def _query_channel(session: Any, channel: str) -> dict[str, Any]:
    prefix = f":CHANnel{channel[-1]}:"
    return {
        "channel": channel,
        "display": _bool_response(session.query(prefix + "DISPlay?"), "display"),
        "bandwidth": _bandwidth(session.query(prefix + "BWLimit?")),
        "invert": _bool_response(session.query(prefix + "INVert?"), "invert"),
        "impedance_ohms": _impedance_response(session.query(prefix + "IMPedance?")),
        "coupling": _coupling(session.query(prefix + "COUPling?")),
        "scale_v_div": _number(session.query(prefix + "SCALe?"), "scale_v_div"),
        "offset_v": _number(session.query(prefix + "OFFSet?"), "offset_v"),
        "deskew_s": _number(session.query(prefix + "TCALibrate?"), "deskew_s"),
        "probe": _number(session.query(prefix + "PROBe?"), "probe"),
        "units": _units(session.query(prefix + "UNITs?")),
        "fine_scale": _bool_response(session.query(prefix + "VERNier?"), "fine_scale"),
        "label_visible": _bool_response(session.query(prefix + "LABel:SHOW?"), "label_visible"),
        "label": _label_response(session.query(prefix + "LABel:CONTent?")),
        "bias_v": _number(session.query(prefix + "POSition?"), "bias_v"),
    }


def get_channel(session: Any, channel: Any) -> dict[str, Any]:
    """Return the effective settings for one MHO98 analog channel."""

    return _query_channel(session, _channel(channel))


def _scale_bounds(impedance: int, probe: float) -> tuple[float, float]:
    # SCALe is the displayed V/div.  The guide's 1X limits therefore scale with
    # the probe ratio; the physical input scale is SCALe / PROBe.
    if impedance == 50:
        return 2e-4 * probe, 1.0 * probe
    return 1e-3 * probe, 10.0 * probe


def _validate_scale(scale: float, impedance: int, probe: float) -> None:
    low, high = _scale_bounds(impedance, probe)
    if not low <= scale <= high:
        raise ValueError(
            f"scale_v_div {scale:g} is outside the {impedance} ohm range "
            f"{low:g}..{high:g} V/div for probe {probe:g}"
        )


def _validate_offset(offset: float, impedance: int, scale: float, probe: float) -> None:
    # The guide gives offset limits against the current displayed scale and
    # impedance, while probe attenuation changes the physical input scale.  It
    # does not define the conversion between a requested display offset and that
    # physical limit.  The finite-value check is performed by _number(); leave
    # range enforcement to the instrument when dependent settings are omitted.
    del offset, impedance, scale, probe


def _send_channel(
    session: Any,
    channel: Any,
    *,
    display: Any = None,
    bandwidth: Any = None,
    invert: Any = None,
    impedance_ohms: Any = None,
    coupling: Any = None,
    scale_v_div: Any = None,
    offset_v: Any = None,
    deskew_s: Any = None,
    probe: Any = None,
    units: Any = None,
    fine_scale: Any = None,
    label_visible: Any = None,
    label: Any = None,
    bias_v: Any = None,
) -> dict[str, Any]:
    """Send only the explicitly requested channel commands.

    No channel snapshot is taken: omitted fields are left to the instrument and
    the response reports transmission, not resulting hardware state.
    """

    ch = _channel(channel)
    requested_display = None if display is None else _bool_response(str(display), "display")
    if isinstance(display, bool):
        requested_display = display
    requested_bandwidth = None if bandwidth is None else _bandwidth(bandwidth)
    requested_invert = None if invert is None else _bool_response(str(invert), "invert")
    if isinstance(invert, bool):
        requested_invert = invert

    requested_impedance = None
    if impedance_ohms is not None:
        impedance_value = _number(impedance_ohms, "impedance_ohms")
        if impedance_value not in {50.0, 1_000_000.0}:
            raise ValueError("impedance_ohms must be 50 or 1000000")
        requested_impedance = int(impedance_value)

    requested_coupling = None if coupling is None else _coupling(coupling)
    requested_probe = None if probe is None else _number(probe, "probe")
    if requested_probe is not None and not 0.001 <= requested_probe <= 50_000:
        raise ValueError("probe must be between 0.001 and 50000")
    requested_scale = None if scale_v_div is None else _number(scale_v_div, "scale_v_div")
    requested_offset = None if offset_v is None else _number(offset_v, "offset_v")
    requested_deskew = None if deskew_s is None else _number(deskew_s, "deskew_s")
    if requested_deskew is not None and not -100e-9 <= requested_deskew <= 100e-9:
        raise ValueError("deskew_s must be between -1e-7 and 1e-7 seconds")
    requested_units = None if units is None else _units(units)
    requested_fine_scale = None if fine_scale is None else _bool_response(str(fine_scale), "fine_scale")
    if isinstance(fine_scale, bool):
        requested_fine_scale = fine_scale
    requested_label_visible = None if label_visible is None else _bool_response(str(label_visible), "label_visible")
    if isinstance(label_visible, bool):
        requested_label_visible = label_visible
    requested_label = None if label is None else _label_value(label)
    requested_bias = None if bias_v is None else _number(bias_v, "bias_v")

    if requested_impedance == 50 and requested_coupling in {"AC", "GND"}:
        raise ValueError("50 ohm input impedance only supports DC coupling on MHO98")
    if requested_units == "AMP" and requested_probe is not None and requested_probe > 10:
        raise ValueError("AMP units require probe <= 10")
    # Range checks that depend on another setting are made only when every input
    # needed for that check was explicitly supplied.  The instrument remains the
    # authority when an omitted dependency is involved.
    if requested_scale is not None and requested_impedance is not None and requested_probe is not None:
        _validate_scale(requested_scale, requested_impedance, requested_probe)
    if requested_scale is not None and requested_bandwidth is not None and requested_probe is not None:
        physical_scale = requested_scale / requested_probe
        if physical_scale <= 200e-6 and requested_bandwidth != "20M":
            raise ValueError("physical scale <= 200 uV/div requires 20M bandwidth")
        if physical_scale <= 500e-6 and requested_bandwidth == "OFF":
            raise ValueError("bandwidth OFF is unavailable at physical scale <= 500 uV/div")

    writes: list[str] = []
    prefix = f":CHANnel{ch[-1]}:"
    # Hardware ignores scale while a channel is disabled.  An explicit ON is the
    # only enable this tool may send, and it must precede all other settings.
    if requested_display is True:
        writes.append(prefix + "DISPlay 1")

    impedance_command = None
    if requested_impedance is not None:
        token = "FIFTy" if requested_impedance == 50 else "OMEG"
        impedance_command = prefix + "IMPedance " + token
    units_command = None
    if requested_units is not None:
        token = {"VOLT": "VOLTage", "WATT": "WATT", "AMP": "AMPere", "UNKN": "UNKNown"}[requested_units]
        units_command = prefix + "UNITs " + token
    probe_command = None
    if requested_probe is not None:
        probe_command = prefix + "PROBe " + _scpi_number(requested_probe)
    if impedance_command is not None:
        writes.append(impedance_command)
    # Use only explicit values for this dependency ordering.  If the request
    # enters AMP with a large probe, lower the probe first; when leaving AMP,
    # change units first.  No current unit/probe query is used.
    if units_command is not None and probe_command is not None:
        if requested_units == "AMP" and requested_probe is not None and requested_probe <= 10:
            writes.extend((probe_command, units_command))
        else:
            writes.extend((units_command, probe_command))
    elif units_command is not None:
        writes.append(units_command)
    elif probe_command is not None:
        writes.append(probe_command)

    scale_command = None if requested_scale is None else prefix + "SCALe " + _scpi_number(requested_scale)
    bandwidth_command = None if requested_bandwidth is None else prefix + "BWLimit " + requested_bandwidth
    # This order is derived only from explicitly requested scale/probe values.
    if scale_command is not None and bandwidth_command is not None:
        physical_scale = requested_scale / requested_probe if requested_probe is not None else None
        if physical_scale is not None and physical_scale > 500e-6:
            writes.extend((scale_command, bandwidth_command))
        else:
            writes.extend((bandwidth_command, scale_command))
    elif scale_command is not None:
        writes.append(scale_command)
    elif bandwidth_command is not None:
        writes.append(bandwidth_command)
    if requested_offset is not None:
        writes.append(prefix + "OFFSet " + _scpi_number(requested_offset))
    if requested_deskew is not None:
        writes.append(prefix + "TCALibrate " + _scpi_number(requested_deskew))
    if requested_bias is not None:
        writes.append(prefix + "POSition " + _scpi_number(requested_bias))
    if requested_coupling is not None:
        writes.append(prefix + "COUPling " + requested_coupling)
    if requested_invert is not None:
        writes.append(prefix + "INVert " + ("1" if requested_invert else "0"))
    if requested_fine_scale is not None:
        writes.append(prefix + "VERNier " + ("1" if requested_fine_scale else "0"))
    if requested_label_visible is not None:
        writes.append(prefix + "LABel:SHOW " + ("1" if requested_label_visible else "0"))
    if requested_label is not None:
        writes.append(prefix + "LABel:CONTent " + requested_label)
    if requested_display is False:
        writes.append(prefix + "DISPlay 0")

    for command in writes:
        session.write(command)
    requested = {
        key: value for key, value in {
            "channel": ch, "display": requested_display, "bandwidth": requested_bandwidth,
            "invert": requested_invert, "impedance_ohms": requested_impedance,
            "coupling": requested_coupling, "scale_v_div": requested_scale,
            "offset_v": requested_offset, "deskew_s": requested_deskew,
            "probe": requested_probe, "units": requested_units, "fine_scale": requested_fine_scale,
            "label_visible": requested_label_visible, "label": label, "bias_v": requested_bias,
        }.items() if value is not None
    }
    return {"sent": bool(writes), "verified": False, "commands": writes, "requested": requested, **requested}


HUMAN_INPUT_FIELDS = frozenset({"impedance_ohms", "units", "probe"})
CHANNEL_SETTING_FIELDS = (
    "display", "bandwidth", "invert", "coupling", "scale_v_div", "offset_v",
    "deskew_s", "fine_scale", "label_visible", "label", "bias_v",
)


def set_channel(session: Any, channel: Any, **settings: Any) -> dict[str, Any]:
    """Send a complete ordinary-channel settings packet; input hardware is human-owned."""
    forbidden = HUMAN_INPUT_FIELDS.intersection(settings)
    if forbidden:
        raise ValueError(
            "Human-owned input settings cannot be changed by set_channel: "
            + ", ".join(sorted(forbidden))
            + ". Use set_channel_input only when the human explicitly requests those changes."
        )
    missing = [name for name in CHANNEL_SETTING_FIELDS if settings.get(name) is None]
    if missing:
        raise ValueError("Complete channel settings required; missing: " + ", ".join(missing))
    unknown = set(settings) - set(CHANNEL_SETTING_FIELDS)
    if unknown:
        raise ValueError("Unknown channel settings: " + ", ".join(sorted(unknown)))
    return _send_channel(session, channel, **settings)


def set_channel_input(
    session: Any, channel: Any, *, impedance_ohms: Any = None,
    units: Any = None, probe: Any = None,
) -> dict[str, Any]:
    """Send input settings only on an explicit human instruction; never infer them."""
    if all(value is None for value in (impedance_ohms, units, probe)):
        raise ValueError("Specify at least one input setting explicitly requested by the human")
    return _send_channel(session, channel, impedance_ohms=impedance_ohms, units=units, probe=probe)


_CHANNEL_SCHEMA = {
    "type": "object",
    "properties": {
        "channel": {"type": "string", "enum": ["CHAN1", "CHAN2", "CHAN3", "CHAN4"]},
        "display": {"type": "boolean"},
        "bandwidth": {"type": "string", "enum": ["OFF", "ON", "20M", "250M"]},
        "invert": {"type": "boolean"},
        "impedance_ohms": {"type": "number", "enum": [50, 1000000]},
        "coupling": {"type": "string", "enum": ["AC", "DC", "GND"]},
        "scale_v_div": {"type": "number"},
        "offset_v": {"type": "number"},
        "deskew_s": {"type": "number"},
        "probe": {"type": "number"},
        "units": {"type": "string", "enum": ["VOLT", "WATT", "AMP", "UNKN"]},
        "fine_scale": {"type": "boolean"},
        "label_visible": {"type": "boolean"},
        "label": {"type": "string"},
        "bias_v": {"type": "number"},
    },
    "required": ["channel"],
}

_INPUT_SCHEMA = {
    "type": "object",
    "properties": {name: _CHANNEL_SCHEMA["properties"][name]
                   for name in ("channel", "impedance_ohms", "units", "probe")},
    "required": ["channel"],
    "anyOf": [{"required": [name]} for name in sorted(HUMAN_INPUT_FIELDS)],
    "additionalProperties": False,
}
_CHANNEL_SCHEMA = {
    **_CHANNEL_SCHEMA,
    "properties": {name: field for name, field in _CHANNEL_SCHEMA["properties"].items()
                   if name not in HUMAN_INPUT_FIELDS},
    "required": ["channel", *CHANNEL_SETTING_FIELDS],
    "additionalProperties": False,
}

TOOLS = [
    ToolSpec(
        name="get_channel",
        description="Read effective display, impedance, coupling, scale, offset, and probe settings for MHO98 CHAN1-CHAN4.",
        input_schema={"type": "object", "properties": {"channel": _CHANNEL_SCHEMA["properties"]["channel"]}, "required": ["channel"]},
        handler=get_channel,
        read_only=True,
        needs_session=True,
    ),
    ToolSpec(
        name="set_channel",
        description="Send ALL 11 ordinary MHO98 channel settings in one call; every field is required and none is inherited from prior state. Always explicitly choose bandwidth, invert, coupling, scale, offset, deskew, fine scale, label visibility/text, bias, and display. No pre-read or readback. Impedance, measurement units and probe ratio remain human-owned: never infer or change them from AC/scale requests. If a known human-owned setting conflicts (e.g. 50 ohm with AC), report the conflict rather than silently changing it. Scale/offset use the existing human-selected unit despite legacy _v argument names.",
        input_schema=_CHANNEL_SCHEMA,
        handler=set_channel,
        read_only=False,
        needs_session=True,
    ),
    ToolSpec(
        name="set_channel_input",
        description="Change channel impedance, measurement units, or probe ratio ONLY when the human explicitly instructs those changes. These depend on physical wiring/probes. Never infer them from requested coupling, scale, measurement goals, or defaults; never call this automatically to make another setting succeed. Send only the human-specified fields, without readback.",
        input_schema=_INPUT_SCHEMA,
        handler=set_channel_input,
        read_only=False,
        needs_session=True,
    ),
]
