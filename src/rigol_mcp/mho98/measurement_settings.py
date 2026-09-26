"""MHO98 measurement configuration and measurement actions.

The read-only value handlers live in :mod:`rigol_mcp.mho98.measure`.  This
module deliberately keeps registration/configuration separate from those
handlers: querying a value must not register a displayed measurement.
"""

from __future__ import annotations

import math
from enum import Enum
from numbers import Real
from typing import Any

from .api import ToolSpec
from .measure import (
    TWO_SOURCE_ITEMS,
    _ITEM_ENUM as _MEASURE_ITEM_ENUM,
    _SOURCE_ENUM as _MEASURE_SOURCE_ENUM,
    _normalize_item,
    _normalize_source,
    _normalize_statistic,
)


class MeasurementAction(str, Enum):
    """Actions exposed by :func:`measurement_action`."""

    REGISTER_ITEM = "register_item"
    REGISTER_STATISTIC_ITEM = "register_statistic_item"
    DELETE_ITEMS = "delete_items"
    RESET_STATISTICS = "reset_statistics"
    RESET_THRESHOLD_DEFAULTS = "reset_threshold_defaults"


_ACTION_ALIASES = {
    "REGISTER": MeasurementAction.REGISTER_ITEM,
    "DELETE": MeasurementAction.DELETE_ITEMS,
    "RESET_STATS": MeasurementAction.RESET_STATISTICS,
    "THRESHOLD_DEFAULTS": MeasurementAction.RESET_THRESHOLD_DEFAULTS,
}
_SOURCE_ENUM = list(_MEASURE_SOURCE_ENUM)
_COUNTER_SOURCE_ENUM = [f"CH{i}" for i in range(1, 5)] + [f"D{i}" for i in range(16)]
_ITEM_ENUM = list(_MEASURE_ITEM_ENUM)

_ALL_FIELDS = {
    "source",
    "all_measure_source",
    "threshold_source",
    "threshold_type",
    "threshold_min",
    "threshold_mid",
    "threshold_max",
    "phase_source_a",
    "phase_source_b",
    "delay_source_a",
    "delay_source_b",
    "area",
    "measurement_type",
    "cursor_a_s",
    "cursor_b_s",
    "cursor_linked",
    "indicator",
    "statistics_count",
    "statistics_display",
    "amplitude_method",
    "manual_top",
    "manual_base",
    "histogram_enable",
    "histogram_result",
    "category",
    "counter_enable",
    "counter_source",
    "counter_value",
}
def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    if isinstance(value, Real):
        result = float(value)
    elif isinstance(value, str):
        try:
            result = float(value.strip())
        except ValueError:
            raise ValueError(f"{name} must be a finite number") from None
    else:
        raise ValueError(f"{name} must be a finite number")
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    return result


def _integer(value: Any, name: str, low: int, high: int) -> int:
    number = _finite(value, name)
    if not number.is_integer() or not low <= number <= high:
        raise ValueError(f"{name} must be an integer from {low} through {high}")
    return int(number)


def _bool_input(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _bool_response(value: Any, name: str) -> bool:
    text = str(value).strip().upper()
    if text in {"1", "ON", "TRUE"}:
        return True
    if text in {"0", "OFF", "FALSE"}:
        return False
    raise ValueError(f"invalid {name} response from MHO98: {value!r}")


def _scpi_number(value: float) -> str:
    return format(value, ".15g")


def _enum(value: Any, name: str, aliases: dict[str, str]) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be one of {sorted(set(aliases.values()))}")
    token = aliases.get(value.strip().upper())
    if token is None:
        raise ValueError(f"invalid {name}: {value!r}")
    return token


def _source(value: Any, name: str = "source") -> str:
    try:
        return _normalize_source(value)
    except ValueError as exc:
        raise ValueError(f"{name}: {exc}") from None


def _threshold_source(value: Any) -> str:
    source = _source(value, "threshold_source")
    if source.startswith("D"):
        raise ValueError("threshold_source must be CH1-CH4 or MATH1-MATH4")
    return source


def _all_measure_source(value: Any) -> str:
    if isinstance(value, str) and value.strip().upper() == "OFF":
        return "OFF"
    source = _source(value, "all_measure_source")
    if not source.startswith("CHAN"):
        raise ValueError("all_measure_source must be CH1-CH4 or OFF")
    return source


def _counter_source(value: Any) -> str:
    source = _source(value, "counter_source")
    if source.startswith("MATH"):
        raise ValueError("counter_source must be CH1-CH4 or D0-D15")
    return source


def _response_number(value: Any, name: str) -> float:
    return _finite(value, name)


def _response_enum(value: Any, name: str, aliases: dict[str, str]) -> str:
    text = str(value).strip().upper()
    return _enum(text, name, aliases)


_AREA = {"MAIN": "MAIN", "ZOOM": "ZOOM", "CURSOR": "CURS", "CURS": "CURS"}
_MEASUREMENT_TYPE = {
    "THRESHOLD": "THR", "THR": "THR", "RANGE": "RANG", "RANG": "RANG",
    "AMPLITUDE": "AMPM", "AMPLITUDE_METHOD": "AMPM", "AMPM": "AMPM",
}
_THRESHOLD_TYPE = {"PERCENT": "PERC", "PERCENTAGE": "PERC", "PERC": "PERC", "ABSOLUTE": "ABS", "ABS": "ABS"}
_AMPLITUDE_METHOD = {"AUTO": "AUTO", "MANUAL": "MAN", "MAN": "MAN"}
_AMP_LEVEL = {"HISTOGRAM": "HIST", "HIST": "HIST", "MAXMIN": "MAXM", "MAX-MIN": "MAXM", "MAXM": "MAXM"}
_STATISTICS = {"MAXIMUM": "MAXIMUM", "MINIMUM": "MINIMUM", "CURRENT": "CURRENT", "AVERAGES": "AVERAGES", "DEVIATION": "DEVIATION", "CNT": "CNT"}


def _threshold_order(current: dict[str, float], requested: dict[str, float], threshold_type: str) -> list[tuple[str, float]]:
    """Validate final threshold bounds and find a safe transition order."""

    final = {**current, **requested}
    if not final["threshold_min"] < final["threshold_mid"] < final["threshold_max"]:
        raise ValueError("threshold_min < threshold_mid < threshold_max is required")
    if threshold_type == "PERC":
        if not 0 <= final["threshold_min"] <= 100 or not 0 <= final["threshold_mid"] <= 100 or not 0 <= final["threshold_max"] <= 100:
            raise ValueError("percentage thresholds must be between 0 and 100")
        if final["threshold_mid"] - final["threshold_min"] < 1 or final["threshold_max"] - final["threshold_mid"] < 1:
            raise ValueError("percentage thresholds require at least 1 percentage point around MID")

    pending = [name for name in ("threshold_min", "threshold_mid", "threshold_max") if name in requested and not math.isclose(requested[name], current[name], rel_tol=0, abs_tol=0)]
    state = dict(current)
    result: list[tuple[str, float]] = []
    command_name = {"threshold_min": "MIN", "threshold_mid": "MID", "threshold_max": "MAX"}
    while pending:
        for name in pending:
            value = requested[name]
            if name == "threshold_min" and value < state["threshold_mid"]:
                valid = True
            elif name == "threshold_mid" and state["threshold_min"] < value < state["threshold_max"]:
                valid = True
            elif name == "threshold_max" and value > state["threshold_mid"]:
                valid = True
            else:
                valid = False
            if valid:
                result.append((command_name[name], value))
                state[name] = value
                pending.remove(name)
                break
        else:  # A valid strictly ordered final state should always have a path.
            raise ValueError("threshold bounds cannot be transitioned without violating MIN/MID/MAX ordering")
    return result


def _query_threshold(session: Any) -> dict[str, float]:
    return {
        "threshold_min": _response_number(session.query(":MEASure:SETup:MIN?"), "threshold_min"),
        "threshold_mid": _response_number(session.query(":MEASure:SETup:MID?"), "threshold_mid"),
        "threshold_max": _response_number(session.query(":MEASure:SETup:MAX?"), "threshold_max"),
    }


def _query_result(session: Any) -> dict[str, Any]:
    raw = str(session.query(":MEASure:COUNter:VALue?")).strip()
    try:
        value = float(raw)
    except ValueError:
        value = None
    return {"value": value, "raw": raw, "valid": value is not None and math.isfinite(value)}


def _read_settings(session: Any, fields: set[str] | None = None) -> dict[str, Any]:
    requested = _ALL_FIELDS if fields is None else set(fields)
    result: dict[str, Any] = {}

    def wants(*names: str) -> bool:
        return fields is None or bool(requested.intersection(names))

    if wants("source"):
        result["source"] = _source(session.query(":MEASure:SOURce?"))
    if wants("all_measure_source"):
        value = str(session.query(":MEASure:AMSource?")).strip().upper()
        result["all_measure_source"] = "OFF" if value == "OFF" else _source(value, "all_measure_source")
    if wants("threshold_source"):
        result["threshold_source"] = _threshold_source(session.query(":MEASure:THReshold:SOURce?"))
    if wants("threshold_type"):
        result["threshold_type"] = _response_enum(session.query(":MEASure:THReshold:TYPE?"), "threshold_type", _THRESHOLD_TYPE)
    for name, command in (("threshold_min", "MIN"), ("threshold_mid", "MID"), ("threshold_max", "MAX")):
        if wants(name):
            result[name] = _response_number(session.query(f":MEASure:SETup:{command}?"), name)

    if wants("phase_source_a"):
        result["phase_source_a"] = _source(session.query(":MEASure:SETup:PSA?"), "phase_source_a")
    if wants("phase_source_b", "delay_source_b"):
        source_b = _source(session.query(":MEASure:SETup:PSB?"), "phase_source_b")
        if wants("phase_source_b"):
            result["phase_source_b"] = source_b
        if wants("delay_source_b"):
            result["delay_source_b"] = source_b
    if wants("delay_source_a"):
        result["delay_source_a"] = _source(session.query(":MEASure:SETup:DSA?"), "delay_source_a")

    area = None
    if wants("area") or (fields is None and "area" in requested):
        area = _response_enum(session.query(":MEASure:AREA?"), "area", _AREA)
        result["area"] = area
    if wants("measurement_type"):
        result["measurement_type"] = _response_enum(session.query(":MEASure:TYPE?"), "measurement_type", _MEASUREMENT_TYPE)
    cursor_requested = wants("cursor_a_s", "cursor_b_s", "cursor_linked")
    if cursor_requested and (fields is not None or area == "CURS"):
        if wants("cursor_a_s"):
            result["cursor_a_s"] = _response_number(session.query(":MEASure:CREGion:CAX?"), "cursor_a_s")
        if wants("cursor_b_s"):
            result["cursor_b_s"] = _response_number(session.query(":MEASure:CREGion:CBX?"), "cursor_b_s")
        if wants("cursor_linked"):
            result["cursor_linked"] = _bool_response(session.query(":MEASure:CREGion:CABX?"), "cursor_linked")

    if wants("indicator"):
        result["indicator"] = _bool_response(session.query(":MEASure:INDicator?"), "indicator")
    if wants("statistics_count"):
        result["statistics_count"] = _integer(session.query(":MEASure:STATistic:COUNt?"), "statistics_count", 2, 100000)
    if wants("statistics_display"):
        result["statistics_display"] = _bool_response(session.query(":MEASure:STATistic:DISPlay?"), "statistics_display")

    amplitude_method = None
    if wants("amplitude_method"):
        amplitude_method = _response_enum(session.query(":MEASure:AMP:TYPE?"), "amplitude_method", _AMPLITUDE_METHOD)
        result["amplitude_method"] = amplitude_method
    if wants("manual_top", "manual_base") and (fields is not None or amplitude_method == "MAN"):
        if wants("manual_top"):
            result["manual_top"] = _response_enum(session.query(":MEASure:AMP:MANual:TOP?"), "manual_top", _AMP_LEVEL)
        if wants("manual_base"):
            result["manual_base"] = _response_enum(session.query(":MEASure:AMP:MANual:BASE?"), "manual_base", _AMP_LEVEL)

    histogram_enabled = None
    if wants("histogram_enable"):
        histogram_enabled = _bool_response(session.query(":MEASure:HISTogram:ENABle?"), "histogram_enable")
        result["histogram_enable"] = histogram_enabled
    if wants("histogram_result") and (fields is not None or histogram_enabled):
        result["histogram_result"] = str(session.query(":MEASure:HISTogram:STATistics:RESult?")).strip()

    if wants("category"):
        result["category"] = _integer(session.query(":MEASure:CATegory?"), "category", 0, 2)
    counter_enabled = None
    if wants("counter_enable"):
        counter_enabled = _bool_response(session.query(":MEASure:COUNter:ENABle?"), "counter_enable")
        result["counter_enable"] = counter_enabled
    if wants("counter_source"):
        result["counter_source"] = _counter_source(session.query(":MEASure:COUNter:SOURce?"))
    if wants("counter_value") and (fields is not None or counter_enabled):
        result["counter_value"] = _query_result(session)

    return result


def get_measurement_settings(session: Any) -> dict[str, Any]:
    """Return applicable MHO98 measurement settings and conditional results."""

    return _read_settings(session)


def set_measurement_settings(
    session: Any,
    *,
    source: str | None = None,
    all_measure_source: str | None = None,
    threshold_source: str | None = None,
    threshold_type: str | None = None,
    threshold_min: Any = None,
    threshold_mid: Any = None,
    threshold_max: Any = None,
    phase_source_a: str | None = None,
    phase_source_b: str | None = None,
    delay_source_a: str | None = None,
    delay_source_b: str | None = None,
    area: str | None = None,
    measurement_type: str | None = None,
    cursor_a_s: Any = None,
    cursor_b_s: Any = None,
    cursor_linked: bool | None = None,
    indicator: bool | None = None,
    statistics_count: Any = None,
    statistics_display: bool | None = None,
    amplitude_method: str | None = None,
    manual_top: str | None = None,
    manual_base: str | None = None,
    histogram_enable: bool | None = None,
    category: Any = None,
    counter_enable: bool | None = None,
    counter_source: str | None = None,
) -> dict[str, Any]:
    """Send only the explicitly requested measurement-setting commands."""

    requested: dict[str, Any] = {}
    if source is not None:
        requested["source"] = _source(source)
    if all_measure_source is not None:
        requested["all_measure_source"] = _all_measure_source(all_measure_source)
    if threshold_source is not None:
        requested["threshold_source"] = _threshold_source(threshold_source)
    if threshold_type is not None:
        requested["threshold_type"] = _enum(threshold_type, "threshold_type", _THRESHOLD_TYPE)
    threshold_values = {name: _finite(value, name) for name, value in (("threshold_min", threshold_min), ("threshold_mid", threshold_mid), ("threshold_max", threshold_max)) if value is not None}
    requested.update(threshold_values)
    for name, value in (("phase_source_a", phase_source_a), ("phase_source_b", phase_source_b), ("delay_source_a", delay_source_a), ("delay_source_b", delay_source_b)):
        if value is not None:
            requested[name] = _source(value, name)
    source_b_fields = {name for name in ("phase_source_b", "delay_source_b") if name in requested}
    if len(source_b_fields) == 2 and requested["phase_source_b"] != requested["delay_source_b"]:
        raise ValueError("phase_source_b and delay_source_b must match when both are supplied")
    if source_b_fields:
        if "phase_source_b" not in requested:
            requested["phase_source_b"] = requested["delay_source_b"]
        requested.pop("delay_source_b", None)
    if area is not None:
        requested["area"] = _enum(area, "area", _AREA)
    if measurement_type is not None:
        requested["measurement_type"] = _enum(measurement_type, "measurement_type", _MEASUREMENT_TYPE)
    for name, value in (("cursor_a_s", cursor_a_s), ("cursor_b_s", cursor_b_s)):
        if value is not None:
            requested[name] = _finite(value, name)
    if cursor_linked is not None:
        requested["cursor_linked"] = _bool_input(cursor_linked, "cursor_linked")
    if indicator is not None:
        requested["indicator"] = _bool_input(indicator, "indicator")
    if statistics_count is not None:
        requested["statistics_count"] = _integer(statistics_count, "statistics_count", 2, 100000)
    if statistics_display is not None:
        requested["statistics_display"] = _bool_input(statistics_display, "statistics_display")
    if amplitude_method is not None:
        requested["amplitude_method"] = _enum(amplitude_method, "amplitude_method", _AMPLITUDE_METHOD)
    for name, value in (("manual_top", manual_top), ("manual_base", manual_base)):
        if value is not None:
            requested[name] = _enum(value, name, _AMP_LEVEL)
    if histogram_enable is not None:
        requested["histogram_enable"] = _bool_input(histogram_enable, "histogram_enable")
    if category is not None:
        requested["category"] = _integer(category, "category", 0, 2)
    if counter_enable is not None:
        requested["counter_enable"] = _bool_input(counter_enable, "counter_enable")
    if counter_source is not None:
        requested["counter_source"] = _counter_source(counter_source)
    if not requested:
        return {"requested": {}, "sent": False, "verified": False, "commands": []}

    # Validate only values supplied by the caller.  Omitted threshold values
    # remain instrument-owned and are deliberately not queried.
    threshold_plan: list[tuple[str, float]] = []
    if threshold_values:
        current_type = requested.get("threshold_type")
        if len(threshold_values) == 3:
            values = [threshold_values[name] for name in ("threshold_min", "threshold_mid", "threshold_max")]
            if not values[0] < values[1] < values[2]:
                raise ValueError("threshold_min < threshold_mid < threshold_max is required")
        if current_type == "PERC":
            if any(not 0 <= value <= 100 for value in threshold_values.values()):
                raise ValueError("percentage thresholds must be between 0 and 100")
        threshold_plan = [
            (name.removeprefix("threshold_").upper(), value)
            for name, value in threshold_values.items()
        ]

    if manual_top is not None or manual_base is not None:
        if requested.get("amplitude_method") is not None and requested["amplitude_method"] != "MAN":
            raise ValueError("manual_top/manual_base require amplitude_method=MANUAL")

    writes: list[str] = []
    simple_commands = {
        "source": ":MEASure:SOURce",
        "all_measure_source": ":MEASure:AMSource",
        "threshold_source": ":MEASure:THReshold:SOURce",
        "phase_source_a": ":MEASure:SETup:PSA",
        "phase_source_b": ":MEASure:SETup:PSB",
        "delay_source_a": ":MEASure:SETup:DSA",
        "area": ":MEASure:AREA",
        "measurement_type": ":MEASure:TYPE",
        "cursor_a_s": ":MEASure:CREGion:CAX",
        "cursor_b_s": ":MEASure:CREGion:CBX",
        "indicator": ":MEASure:INDicator",
        "statistics_count": ":MEASure:STATistic:COUNt",
        "statistics_display": ":MEASure:STATistic:DISPlay",
        "amplitude_method": ":MEASure:AMP:TYPE",
        "manual_top": ":MEASure:AMP:MANual:TOP",
        "manual_base": ":MEASure:AMP:MANual:BASE",
        "histogram_enable": ":MEASure:HISTogram:ENABle",
        "category": ":MEASure:CATegory",
        "counter_enable": ":MEASure:COUNter:ENABle",
        "counter_source": ":MEASure:COUNter:SOURce",
    }
    ordered = ["source", "all_measure_source", "threshold_source", "phase_source_a", "phase_source_b", "delay_source_a", "area", "measurement_type", "cursor_a_s", "cursor_b_s", "cursor_linked", "indicator", "statistics_count", "statistics_display", "amplitude_method", "manual_top", "manual_base", "histogram_enable", "category", "counter_enable", "counter_source"]
    if "threshold_type" in requested:
        writes.append(f":MEASure:THReshold:TYPE {requested['threshold_type']}")
    for command, value in threshold_plan:
        writes.append(f":MEASure:SETup:{command} {_scpi_number(value)}")
    for name in ordered:
        if name not in requested:
            continue
        value = requested[name]
        if name == "cursor_linked" or name in {"indicator", "statistics_display", "histogram_enable", "counter_enable"}:
            rendered = "ON" if value else "OFF"
        elif name in {"cursor_a_s", "cursor_b_s"} or name == "category" or name == "statistics_count":
            rendered = _scpi_number(float(value)) if name in {"cursor_a_s", "cursor_b_s"} else str(value)
        else:
            rendered = str(value)
        if name == "cursor_linked":
            writes.append(f":MEASure:CREGion:CABX {rendered}")
        else:
            writes.append(f"{simple_commands[name]} {rendered}")
    for command in writes:
        session.write(command)

    return {
        "requested": requested,
        "sent": bool(writes),
        "verified": False,
        "commands": writes,
    }


def measurement_action(
    session: Any,
    *,
    action: MeasurementAction | str,
    item: str | None = None,
    source: str | None = None,
    source2: str | None = None,
    statistic: str | None = None,
) -> dict[str, Any]:
    """Perform one documented measurement registration/delete/reset action."""

    if isinstance(action, MeasurementAction):
        selected = action
    elif isinstance(action, str):
        token = action.strip().upper()
        selected = _ACTION_ALIASES.get(token)
        if selected is None:
            try:
                selected = MeasurementAction(action.strip().lower())
            except ValueError:
                raise ValueError(f"unknown measurement action {action!r}") from None
    else:
        raise ValueError("action must be a MeasurementAction")

    if selected is MeasurementAction.DELETE_ITEMS:
        command = ":MEASure:DELete"
        session.write(command)
        return {"action": selected.value, "deleted": "all_measurement_items", "sent": True, "verified": False, "commands": [command]}
    if selected is MeasurementAction.RESET_STATISTICS:
        command = ":MEASure:STATistic:RESet"
        session.write(command)
        return {"action": selected.value, "reset": "measurement_statistics", "sent": True, "verified": False, "commands": [command]}
    if selected is MeasurementAction.RESET_THRESHOLD_DEFAULTS:
        command = ":MEASure:THReshold:DEFault"
        session.write(command)
        return {"action": selected.value, "sent": True, "verified": False, "commands": [command]}

    if item is None:
        raise ValueError(f"{selected.value} requires item")
    allow_two = selected is MeasurementAction.REGISTER_STATISTIC_ITEM or source2 is not None
    canonical_item = _normalize_item(item, allow_two_source=allow_two)
    is_two = canonical_item in TWO_SOURCE_ITEMS
    if is_two and source2 is None:
        raise ValueError(f"{item!r} requires source2")
    if not is_two and source2 is not None:
        raise ValueError(f"{item!r} is a single-source item and does not accept source2")
    sources = []
    if source is not None:
        sources.append(_source(source))
    if source2 is not None:
        if source is None:
            raise ValueError("source is required when source2 is supplied")
        sources.append(_source(source2, "source2"))
    arguments = ",".join((canonical_item, *sources))
    if selected is MeasurementAction.REGISTER_ITEM:
        command = f":MEASure:ITEM {arguments}"
    else:
        # STATistic:ITEM has no statistic argument on set; statistic is only a
        # query selector for measure_statistics().
        if statistic is not None:
            _normalize_statistic(statistic)
        command = f":MEASure:STATistic:ITEM {arguments}"
    session.write(command)
    result: dict[str, Any] = {"action": selected.value, "item": canonical_item, "sources": sources, "sent": True, "verified": False, "commands": [command]}
    if statistic is not None:
        result["statistic"] = _normalize_statistic(statistic)
    return result


_SET_PROPERTIES = {
    "source": {"type": "string", "enum": _SOURCE_ENUM},
    "all_measure_source": {"type": "string", "enum": ["OFF", *[f"CH{i}" for i in range(1, 5)]]},
    "threshold_source": {"type": "string", "enum": [f"CH{i}" for i in range(1, 5)] + [f"MATH{i}" for i in range(1, 5)]},
    "threshold_type": {"type": "string", "enum": ["PERCENT", "ABSOLUTE"]},
    "threshold_min": {"type": "number"}, "threshold_mid": {"type": "number"}, "threshold_max": {"type": "number"},
    "phase_source_a": {"type": "string", "enum": _SOURCE_ENUM}, "phase_source_b": {"type": "string", "enum": _SOURCE_ENUM},
    "delay_source_a": {"type": "string", "enum": _SOURCE_ENUM}, "delay_source_b": {"type": "string", "enum": _SOURCE_ENUM},
    "area": {"type": "string", "enum": ["MAIN", "ZOOM", "CURSOR"]}, "measurement_type": {"type": "string", "enum": ["THRESHOLD", "RANGE", "AMPLITUDE_METHOD"]},
    "cursor_a_s": {"type": "number"}, "cursor_b_s": {"type": "number"}, "cursor_linked": {"type": "boolean"}, "indicator": {"type": "boolean"},
    "statistics_count": {"type": "integer", "minimum": 2, "maximum": 100000}, "statistics_display": {"type": "boolean"},
    "amplitude_method": {"type": "string", "enum": ["AUTO", "MANUAL"]}, "manual_top": {"type": "string", "enum": ["HISTOGRAM", "MAXMIN"]}, "manual_base": {"type": "string", "enum": ["HISTOGRAM", "MAXMIN"]},
    "histogram_enable": {"type": "boolean"}, "category": {"type": "integer", "minimum": 0, "maximum": 2},
    "counter_enable": {"type": "boolean"}, "counter_source": {"type": "string", "enum": _COUNTER_SOURCE_ENUM},
}

TOOLS = (
    ToolSpec("get_measurement_settings", "Read applicable MHO98 measurement settings.", {"type": "object", "properties": {}, "required": []}, get_measurement_settings, read_only=True, needs_session=True),
    ToolSpec("set_measurement_settings", "Send named MHO98 measurement settings only; omitted fields are untouched and resulting state is not queried.", {"type": "object", "properties": _SET_PROPERTIES, "required": []}, set_measurement_settings, read_only=False, needs_session=True),
    ToolSpec(
        "measurement_action",
        "Register/delete displayed measurements or reset documented measurement statistics/threshold defaults.",
        {"type": "object", "properties": {"action": {"type": "string", "enum": [item.value for item in MeasurementAction]}, "item": {"type": "string", "enum": _ITEM_ENUM}, "source": {"type": "string", "enum": _SOURCE_ENUM}, "source2": {"type": "string", "enum": _SOURCE_ENUM}, "statistic": {"type": "string", "enum": sorted(_STATISTICS)}}, "required": ["action"]},
        measurement_action,
        read_only=False,
        needs_session=True,
    ),
)
