"""Native MHO98 system, capability, and single-error-read tools.

Only the documented, non-reset system controls are exposed here. The option
queries are observations rather than claims that a physical feature is usable;
in particular, DG status and option status are intentionally reported
independently.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from datetime import date
from typing import Any

from .api import ToolSpec


_AUX_OUTPUTS = {"TOUT": "TOUT", "PFA": "PFA", "PFAIL": "PFA"}
_AUX_WRITES = {"TOUT": "TOUT", "PFA": "PFAil"}
_LANGUAGES = {
    "SCHINESE": ("SCH", "SCHinese"), "SCH": ("SCH", "SCHinese"),
    "TCHINESE": ("TCH", "TCHinese"), "TCH": ("TCH", "TCHinese"),
    "KOREAN": ("KOR", "KORean"), "KOR": ("KOR", "KORean"),
    "JAPANESE": ("JAP", "JAPanese"), "JAP": ("JAP", "JAPanese"),
    "ENGLISH": ("ENGL", "ENGLish"), "ENGL": ("ENGL", "ENGLish"),
    "GERMAN": ("GERM", "GERMan"), "GERM": ("GERM", "GERMan"),
    "PORTUGUESE": ("PORT", "PORTuguese"), "PORT": ("PORT", "PORTuguese"),
    "POLISH": ("POL", "POLish"), "POL": ("POL", "POLish"),
    "FRENCH": ("FREN", "FRENch"), "FREN": ("FREN", "FRENch"),
    "RUSSIAN": ("RUSS", "RUSSian"), "RUSS": ("RUSS", "RUSSian"),
    "SPANISH": ("SPAN", "SPAN"), "SPAN": ("SPAN", "SPAN"),
    "THAI": ("THAI", "THAI"),
    "INDONESIAN": ("IND", "INDonesian"), "IND": ("IND", "INDonesian"),
}
_POWER_ON = {
    "LATEST": ("LAT", "LATest"), "LAT": ("LAT", "LATest"),
    "DEFAULT": ("DEF", "DEFault"), "DEF": ("DEF", "DEFault"),
}
_POWER_STATUS = {
    "DEFAULT": ("DEF", "DEFault"), "DEF": ("DEF", "DEFault"),
    "OPEN": ("OPEN", "OPEN"),
}

_OPTION_ALIASES = {
    "BND": "BND", "AFG100": "AFG100", "AFG50": "AFG50",
    "AUDIO": "AUDio", "AUDIOA": "AUDio", "AUD": "AUDio",
    "CAN-FD": "CAN-FD", "CANFD": "CAN-FD", "AUTOA": "CAN-FD",
    "FLEX": "FLEX", "FLEXA": "FLEX", "AERO": "AERO", "AEROA": "AERO",
    "RLU-05": "RLU-05", "RLU05": "RLU-05",
    "BWU03T05": "BWU03T05", "BWU03T08": "BWU03T08", "BWU05T08": "BWU05T08",
}
_ALL_OPTIONS = (
    "BND", "AFG100", "AFG50", "AUDio", "CAN-FD", "FLEX", "AERO",
    "RLU-05", "BWU03T05", "BWU03T08", "BWU05T08",
)
_DEFAULT_OPTIONS = ("BND", "AFG100", "AFG50")
_LANGUAGE_SCHEMA_VALUES = [
    "SCHinese", "TCHinese", "KORean", "JAPanese", "ENGLish", "GERMan",
    "PORTuguese", "POLish", "FRENch", "RUSSian", "SPAN", "THAI", "INDonesian",
    "SCH", "TCH", "KOR", "JAP", "ENGL", "GERM", "PORT", "POL", "FREN", "RUSS", "IND",
]


def _bool_input(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _bool_response(value: Any, name: str) -> bool:
    token = str(value).strip().upper()
    if token in {"1", "ON", "TRUE"}:
        return True
    if token in {"0", "OFF", "FALSE"}:
        return False
    raise ValueError(f"invalid {name} response from MHO98: {value!r}")


def _low_power_response(value: Any) -> tuple[bool | None, str]:
    raw = str(value).strip()
    try:
        return _bool_response(raw, "low_power"), raw
    except ValueError:
        return None, raw


def _enum_input(value: Any, name: str, choices: Mapping[str, tuple[str, str]]) -> tuple[str, str]:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a documented discrete value")
    result = choices.get(value.strip().upper())
    if result is None:
        raise ValueError(f"{name} has an unsupported value: {value!r}")
    return result


def _enum_response(value: Any, name: str, choices: Mapping[str, tuple[str, str]]) -> str:
    token = str(value).strip().upper()
    for abbreviation, _write in choices.values():
        if token == abbreviation:
            return abbreviation
    raise ValueError(f"invalid {name} response from MHO98: {value!r}")


def _aux_input(value: Any) -> str:
    if not isinstance(value, str) or value.strip().upper() not in _AUX_OUTPUTS:
        raise ValueError("aux_output must be TOUT or PFAil")
    return _AUX_OUTPUTS[value.strip().upper()]


def _aux_response(value: Any) -> str:
    token = str(value).strip().upper()
    if token == "TOUT":
        return "TOUT"
    if token in {"PFA", "PFAIL"}:
        return "PFA"
    raise ValueError(f"invalid aux_output response from MHO98: {value!r}")


def _integer(value: Any, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer from {minimum} through {maximum}")
    return value


def _date_value(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ValueError("date must contain integer year, month, and day fields")
    try:
        year = _integer(value["year"], "date.year", 1900, 2100)
        month = _integer(value["month"], "date.month", 1, 12)
        day = _integer(value["day"], "date.day", 1, 31)
    except KeyError as exc:
        raise ValueError("date must contain integer year, month, and day fields") from exc
    try:
        date(year, month, day)
    except ValueError as exc:
        raise ValueError(f"date is not a real calendar date: {year:04d}-{month:02d}-{day:02d}") from exc
    return {"year": year, "month": month, "day": day}


def _time_value(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ValueError("time must contain integer hours, minutes, and seconds fields")
    try:
        hours = _integer(value["hours"], "time.hours", 0, 23)
        minutes = _integer(value["minutes"], "time.minutes", 0, 59)
        seconds = _integer(value["seconds"], "time.seconds", 0, 59)
    except KeyError as exc:
        raise ValueError("time must contain integer hours, minutes, and seconds fields") from exc
    return {"hours": hours, "minutes": minutes, "seconds": seconds}


def _triplet_response(
    value: Any,
    name: str,
    fields: tuple[str, str, str],
    minimums: tuple[int, int, int],
    maximums: tuple[int, int, int],
    delimiters: tuple[str, ...] = (",",),
) -> dict[str, int]:
    raw = str(value).strip()
    delimiter = next((candidate for candidate in delimiters if candidate in raw), delimiters[0])
    parts = [part.strip() for part in raw.split(delimiter)]
    if len(parts) != 3:
        raise ValueError(f"invalid {name} response from MHO98: {value!r}")
    try:
        numbers = [int(part) for part in parts]
    except ValueError:
        raise ValueError(f"invalid {name} response from MHO98: {value!r}") from None
    result = {
        field: _integer(number, f"{name}.{field}", minimum, maximum)
        for field, number, minimum, maximum in zip(fields, numbers, minimums, maximums)
    }
    if name == "date":
        try:
            date(result["year"], result["month"], result["day"])
        except ValueError as exc:
            raise ValueError(f"invalid date response from MHO98: {value!r}") from exc
    return result


def _coalesce(primary: Any, alias: Any, primary_name: str, alias_name: str) -> Any:
    if primary is not None and alias is not None:
        raise ValueError(f"provide only one of {primary_name} and {alias_name}")
    return primary if primary is not None else alias


def _query_system(session: Any) -> dict[str, Any]:
    low_power, low_power_raw = _low_power_response(session.query(":SYSTem:LOWPower?"))
    result = {
        "aux_output": _aux_response(session.query(":SYSTem:AOUTput?")),
        "language": _enum_response(session.query(":SYSTem:LANGuage?"), "language", _LANGUAGES),
        "beeper": _bool_response(session.query(":SYSTem:BEEPer?"), "beeper"),
        "date": _triplet_response(session.query(":SYSTem:DATE?"), "date", ("year", "month", "day"), (1900, 1, 1), (2100, 12, 31)),
        "time": _triplet_response(
            session.query(":SYSTem:TIME?"), "time", ("hours", "minutes", "seconds"),
            (0, 0, 0), (23, 59, 59), delimiters=(",", ":"),
        ),
        "show_time": _bool_response(session.query(":SYSTem:STIMe?"), "show_time"),
        "power_on": _enum_response(session.query(":SYSTem:PON?"), "power_on", _POWER_ON),
        "power_status": _enum_response(session.query(":SYSTem:PSTatus?"), "power_status", _POWER_STATUS),
        "locked": _bool_response(session.query(":SYSTem:LOCKed?"), "locked"),
        "low_power": low_power,
        "low_power_raw": low_power_raw,
        "autoscale": _bool_response(session.query(":SYSTem:AUToscale?"), "autoscale"),
        "unavailable": [],
        "warnings": [],
    }
    if low_power is None:
        result["unavailable"].append("low_power")
        result["warnings"].append(
            f"low_power state is unknown; MHO98 returned raw response {low_power_raw!r} "
            "and no power-mode meaning was inferred"
        )
    return result


def get_system(session: Any) -> dict[str, Any]:
    """Read ordinary documented system settings without consuming queue state."""

    return _query_system(session)


def set_system(
    session: Any,
    *,
    aux_output: Any = None,
    language: Any = None,
    beeper: Any = None,
    date: Any = None,
    time: Any = None,
    show_time: Any = None,
    clock_visibility: Any = None,
    power_on: Any = None,
    power_status: Any = None,
    locked: Any = None,
    front_panel_lock: Any = None,
    low_power: Any = None,
    autoscale: Any = None,
    auto_gate: Any = None,
) -> dict[str, Any]:
    """Send only explicitly supplied system fields without readback."""

    requested_show_time = _coalesce(show_time, clock_visibility, "show_time", "clock_visibility")
    requested_locked = _coalesce(locked, front_panel_lock, "locked", "front_panel_lock")
    requested_autoscale = _coalesce(autoscale, auto_gate, "autoscale", "auto_gate")
    normalized = {
        "aux_output": None if aux_output is None else _aux_input(aux_output),
        "language": None if language is None else _enum_input(language, "language", _LANGUAGES)[0],
        "beeper": None if beeper is None else _bool_input(beeper, "beeper"),
        "date": None if date is None else _date_value(date),
        "time": None if time is None else _time_value(time),
        "show_time": None if requested_show_time is None else _bool_input(requested_show_time, "show_time"),
        "power_on": None if power_on is None else _enum_input(power_on, "power_on", _POWER_ON)[0],
        "power_status": None if power_status is None else _enum_input(power_status, "power_status", _POWER_STATUS)[0],
        "locked": None if requested_locked is None else _bool_input(requested_locked, "locked"),
        "low_power": None if low_power is None else _bool_input(low_power, "low_power"),
        "autoscale": None if requested_autoscale is None else _bool_input(requested_autoscale, "autoscale"),
    }

    writes: list[str] = []
    if normalized["aux_output"] is not None:
        writes.append(f":SYSTem:AOUTput {_AUX_WRITES[normalized['aux_output']]}")
    if normalized["language"] is not None:
        writes.append(f":SYSTem:LANGuage {_LANGUAGES[normalized['language']][1]}")
    if normalized["beeper"] is not None:
        writes.append(f":SYSTem:BEEPer {1 if normalized['beeper'] else 0}")
    if normalized["date"] is not None:
        value = normalized["date"]
        writes.append(f":SYSTem:DATE {value['year']},{value['month']},{value['day']}")
    if normalized["time"] is not None:
        value = normalized["time"]
        writes.append(f":SYSTem:TIME {value['hours']},{value['minutes']},{value['seconds']}")
    if normalized["show_time"] is not None:
        writes.append(f":SYSTem:STIMe {1 if normalized['show_time'] else 0}")
    if normalized["power_on"] is not None:
        writes.append(f":SYSTem:PON {_POWER_ON[normalized['power_on']][1]}")
    if normalized["power_status"] is not None:
        writes.append(f":SYSTem:PSTatus {_POWER_STATUS[normalized['power_status']][1]}")
    if normalized["locked"] is not None:
        writes.append(f":SYSTem:LOCKed {1 if normalized['locked'] else 0}")
    if normalized["low_power"] is not None:
        writes.append(f":SYSTem:LOWPower {1 if normalized['low_power'] else 0}")
    if normalized["autoscale"] is not None:
        writes.append(f":SYSTem:AUToscale {1 if normalized['autoscale'] else 0}")

    for command in writes:
        session.write(command)
    requested = {key: value for key, value in normalized.items() if value is not None}
    return {"sent": bool(writes), "verified": False, "commands": writes, "requested": requested, **requested}


def _options(value: Any) -> list[str]:
    if value is None:
        return list(_DEFAULT_OPTIONS)
    if isinstance(value, str):
        if value.strip().upper() == "ALL":
            return list(_ALL_OPTIONS)
        values = [value]
    elif isinstance(value, (list, tuple)):
        values = list(value)
    else:
        raise ValueError("options must be 'all' or a list of documented option names")
    if not values:
        raise ValueError("options must not be empty")
    if any(isinstance(item, str) and item.strip().upper() == "ALL" for item in values):
        if len(values) != 1:
            raise ValueError("'all' cannot be combined with individual options")
        return list(_ALL_OPTIONS)
    result: list[str] = []
    for item in values:
        if not isinstance(item, str) or item.strip().upper() not in _OPTION_ALIASES:
            raise ValueError(f"unsupported documented option: {item!r}")
        canonical = _OPTION_ALIASES[item.strip().upper()]
        if canonical not in result:
            result.append(canonical)
    return result


def _flag(value: Any, name: str) -> str:
    raw = str(value).strip()
    if raw not in {"0", "1"}:
        raise ValueError(f"invalid {name} response from MHO98: {value!r}")
    return raw


def get_capabilities(session: Any, *, options: Any = None) -> dict[str, Any]:
    """Report raw identity/module evidence and requested documented options."""

    selected = _options(options)
    result: dict[str, Any] = {
        "idn": session.idn(),
        "module_flags_raw": str(session.query(":SYSTem:MODules?")).strip(),
    }
    module_flags = [part.strip() for part in result["module_flags_raw"].split(",")]
    if not module_flags or any(flag not in {"0", "1"} for flag in module_flags):
        raise ValueError(f"invalid module flags response from MHO98: {result['module_flags_raw']!r}")
    dg_status = _flag(session.query(":SYSTem:DGSTatus?"), "DG status")
    result.update(
        module_flags=module_flags,
        dg_status=dg_status,
        dg_available=dg_status == "1",
        analog_channel_count=int(str(session.query(":SYSTem:RAMount?")).strip()),
        grid_count=int(str(session.query(":SYSTem:GAMount?")).strip()),
        scpi_version=str(session.query(":SYSTem:VERSion?")).strip(),
        option_status={},
        option_valid={},
    )
    for option in selected:
        result["option_status"][option] = _flag(
            session.query(f":SYSTem:OPTion:STATus? {option}"), f"{option} option status"
        )
        result["option_valid"][option] = _flag(
            session.query(f":SYSTem:OPTion:VALid? {option}"), f"{option} option validity"
        )
    return result


def read_instrument_error(session: Any) -> dict[str, Any]:
    """Perform exactly one documented, destructive error-queue read."""

    raw = str(session.query(":SYSTem:ERRor?")).strip()
    try:
        fields = next(csv.reader([raw], skipinitialspace=True))
        if len(fields) != 2:
            raise ValueError
        code = int(fields[0].strip())
        message = fields[1]
    except (ValueError, StopIteration, csv.Error):
        raise ValueError(f"invalid instrument error response from MHO98: {raw!r}") from None
    return {"code": code, "message": message, "raw": raw}


_DATE_SCHEMA = {
    "type": "object",
    "properties": {
        "year": {"type": "integer", "minimum": 1900, "maximum": 2100},
        "month": {"type": "integer", "minimum": 1, "maximum": 12},
        "day": {"type": "integer", "minimum": 1, "maximum": 31},
    },
    "required": ["year", "month", "day"],
    "additionalProperties": False,
}
_TIME_SCHEMA = {
    "type": "object",
    "properties": {
        "hours": {"type": "integer", "minimum": 0, "maximum": 23},
        "minutes": {"type": "integer", "minimum": 0, "maximum": 59},
        "seconds": {"type": "integer", "minimum": 0, "maximum": 59},
    },
    "required": ["hours", "minutes", "seconds"],
    "additionalProperties": False,
}
_BOOL_PROPERTIES = {
    "beeper": {"type": "boolean"}, "show_time": {"type": "boolean"},
    "clock_visibility": {"type": "boolean"}, "locked": {"type": "boolean"},
    "front_panel_lock": {"type": "boolean"}, "low_power": {"type": "boolean"},
    "autoscale": {"type": "boolean"}, "auto_gate": {"type": "boolean"},
}
_OPTION_SCHEMA = {
    "oneOf": [
        {"type": "string", "enum": ["all", "ALL"]},
        {"type": "array", "items": {"type": "string", "enum": sorted(_OPTION_ALIASES)}, "minItems": 1},
    ]
}

TOOLS = [
    ToolSpec(
        "get_system",
        "Read documented ordinary MHO98 system settings without consuming the instrument error queue.",
        {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        get_system, read_only=True, needs_session=True,
    ),
    ToolSpec(
        "set_system",
        "Send only supplied MHO98 system commands, preserving omitted settings; resulting state is not verified and this does not reset or reboot the instrument.",
        {
            "type": "object",
            "properties": {
                "aux_output": {"type": "string", "enum": ["TOUT", "PFAil", "PFA"]},
                "language": {"type": "string", "enum": _LANGUAGE_SCHEMA_VALUES},
                **_BOOL_PROPERTIES,
                "date": _DATE_SCHEMA, "time": _TIME_SCHEMA,
                "power_on": {"type": "string", "enum": ["LATest", "LAT", "DEFault", "DEF"]},
                "power_status": {"type": "string", "enum": ["DEFault", "DEF", "OPEN"]},
            },
            "required": [], "additionalProperties": False,
        },
        set_system, read_only=False, needs_session=True,
    ),
    ToolSpec(
        "get_capabilities",
        "Read exact MHO98 identity, raw module flags, DG status, channel/grid counts, SCPI version, and documented option status/validity; positive option evidence does not guarantee working physical hardware.",
        {"type": "object", "properties": {"options": _OPTION_SCHEMA}, "required": [], "additionalProperties": False},
        get_capabilities, read_only=True, needs_session=True,
    ),
    ToolSpec(
        "read_instrument_error",
        "Read exactly one documented MHO98 error-queue entry; the instrument consumes that entry and this tool never drains or clears additional entries.",
        {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        read_instrument_error, read_only=False, needs_session=True,
    ),
]
