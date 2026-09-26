"""MHO98 FFT configuration, peak-search, and waveform-backed spectrum tools.

The guide documents the peak-search table, not a dedicated full-bin query.
The optional full-spectrum path therefore reads the actual FFT result exposed
as the selected MATH waveform and preserves its native waveform axis.  It does
not invent Hz bins from display limits.
"""

from __future__ import annotations

import csv
import math as _math
import re
from numbers import Real
from typing import Any

from .api import ToolSpec
from .waveform import get_waveform


_OPERATORS = frozenset(
    {
        "ADD", "SUBT", "MULT", "DIV", "AND", "OR", "XOR", "NOT", "FFT",
        "INTG", "DIFF", "SQRT", "LG", "LN", "EXP", "ABS", "LPAS", "HPAS",
        "BPAS", "BST", "AXB",
    }
)
_OPERATOR_ALIASES = {
    "SUBTRACT": "SUBT",
    "MULTIPLY": "MULT",
    "DIVISION": "DIV",
    "LPASS": "LPAS",
    "HPASS": "HPAS",
    "BPASS": "BPAS",
    "BSTOP": "BST",
}
_WINDOW_ALIASES = {
    "RECT": "RECT", "RECTANGLE": "RECT",
    "BLAC": "BLAC", "BLACKMAN": "BLAC", "BLACKMAN-HARRIS": "BLAC",
    "HANN": "HANN", "HANNING": "HANN",
    "HAMM": "HAMM", "HAMMING": "HAMM",
    "FLAT": "FLAT", "FLATTOP": "FLAT",
    "TRI": "TRI", "TRIANGLE": "TRI",
}
_UNIT_VALUES = frozenset({"VRMS", "DB"})
_MODE_ALIASES = {"NORM": "NORM", "NORMAL": "NORM", "AVER": "AVER", "AVERAGE": "AVER", "MAXH": "MAXH", "MAXHOLD": "MAXH"}
_ORDER_ALIASES = {"AMP": "AMP", "AMPORDER": "AMP", "FREQ": "FREQ", "FREQORDER": "FREQ"}
_SOURCE_RE = re.compile(r"^(?:CH(?:AN)?([1-4])|MATH([1-3]))$", re.IGNORECASE)
_NUMBER_RE = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_AMPLITUDE_RE = re.compile(rf"^\s*({_NUMBER_RE})\s*([A-Za-z]+)\s*$")
_FREQUENCY_RE = re.compile(rf"^\s*({_NUMBER_RE})\s*([A-Za-z]*)\s*$")
_FREQUENCY_MULTIPLIERS = {"": 1.0, "HZ": 1.0, "KHZ": 1.0e3, "MHZ": 1.0e6, "GHZ": 1.0e9}


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
    if not _math.isfinite(result):
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


def _math_name(value: Any) -> str:
    if isinstance(value, bool):
        raise ValueError("math must be MATH1 through MATH4")
    if isinstance(value, Real) or isinstance(value, str):
        text = str(value).strip().upper().replace(" ", "")
        if text.isdigit() and 1 <= int(text) <= 4:
            return f"MATH{int(text)}"
        if text in {"MATH1", "MATH2", "MATH3", "MATH4"}:
            return text
    raise ValueError("math must be MATH1 through MATH4")


def _source(value: Any, math_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError("source must be CHAN1-CHAN4 or MATH1-MATH3")
    token = value.strip().upper().replace(" ", "")
    match = _SOURCE_RE.fullmatch(token)
    if not match:
        raise ValueError("source must be CHAN1-CHAN4 or MATH1-MATH3")
    channel, math_channel = match.groups()
    result = f"CHAN{channel}" if channel else f"MATH{math_channel}"
    if result == math_name:
        raise ValueError("FFT source cannot refer to its own math channel")
    return result


def _source_response(value: Any, math_name: str) -> str:
    return _source(value, math_name)


def _operator(value: Any) -> str:
    token = str(value).strip().upper()
    token = _OPERATOR_ALIASES.get(token, token)
    if token not in _OPERATORS:
        raise ValueError(f"invalid MHO98 math operator response: {value!r}")
    return token


def _window(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("window must be RECT, BLAC, HANN, HAMM, FLAT, or TRI")
    token = _WINDOW_ALIASES.get(value.strip().upper())
    if token is None:
        raise ValueError("window must be RECT, BLAC, HANN, HAMM, FLAT, or TRI")
    return token


def _unit(value: Any) -> str:
    token = str(value).strip().upper()
    if token not in _UNIT_VALUES:
        raise ValueError("unit must be VRMS or DB")
    return token


def _mode(value: Any) -> str:
    token = _MODE_ALIASES.get(str(value).strip().upper())
    if token is None:
        raise ValueError("mode must be NORM, AVER, or MAXH")
    return token


def _order(value: Any) -> str:
    token = _ORDER_ALIASES.get(str(value).strip().upper())
    if token is None:
        raise ValueError("order must be AMP or FREQ")
    return token


def _alias(primary: Any, alternate: Any, primary_name: str, alternate_name: str) -> Any:
    if primary is not None and alternate is not None:
        raise ValueError(f"provide only one of {primary_name} and {alternate_name}")
    return primary if primary is not None else alternate


def _number_response(value: Any, name: str) -> float:
    return _finite(value, name)


def _query_fft_settings(session: Any, math_name: str) -> dict[str, Any]:
    base = f":{math_name}:FFT:"
    search = base + "SEARch:"
    return {
        "source": _source_response(session.query(base + "SOURce?"), math_name),
        "window": _window(session.query(base + "WINDow?")),
        "unit": _unit(session.query(base + "UNIT?")),
        "mode": _mode(session.query(base + "MODE?")),
        "averages": _integer(session.query(base + "AVCNt?"), "averages", 2, 1000),
        "scale": _number_response(session.query(base + "SCALe?"), "scale"),
        "offset": _number_response(session.query(base + "OFFSet?"), "offset"),
        "center_hz": _number_response(session.query(base + "HCENter?"), "center_hz"),
        "range_hz": _number_response(session.query(base + "HSCale?"), "range_hz"),
        "start_hz": _number_response(session.query(base + "FREQuency:STARt?"), "start_hz"),
        "end_hz": _number_response(session.query(base + "FREQuency:END?"), "end_hz"),
        "search_enabled": _bool_response(session.query(search + "ENABle?"), "search_enabled"),
        "peak_count": _integer(session.query(search + "NUM?"), "peak_count", 1, 15),
        "threshold": _number_response(session.query(search + "THReshold?"), "threshold"),
        "excursion": _number_response(session.query(search + "EXCursion?"), "excursion"),
        "order": _order(session.query(search + "ORDer?")),
    }


def _read_state(session: Any, math_name: str, *, include_fft: bool = True) -> dict[str, Any]:
    operator = _operator(session.query(f":{math_name}:OPERator?"))
    display = _bool_response(session.query(f":{math_name}:DISPlay?"), "display")
    result: dict[str, Any] = {
        "math": math_name,
        "operator": operator,
        "display": display,
        "fft_configured": operator == "FFT",
        "applicable": operator == "FFT",
    }
    if operator != "FFT" or not include_fft:
        result["reason"] = "FFT fields are not applicable while the math operator is not FFT"
        return result
    settings = _query_fft_settings(session, math_name)
    result.update(settings)
    result["frequency"] = {
        "center_hz": settings["center_hz"],
        "range_hz": settings["range_hz"],
        "start_hz": settings["start_hz"],
        "end_hz": settings["end_hz"],
    }
    return result


def get_fft(session: Any, math: Any = 1) -> dict[str, Any]:
    """Return actual FFT settings when the selected MATH operator is FFT."""

    return _read_state(session, _math_name(math))


def _validate_frequency_pair(center: float | None, frequency_range: float | None, start: float | None, end: float | None) -> None:
    center_form = center is not None or frequency_range is not None
    endpoint_form = start is not None or end is not None
    if center_form and endpoint_form:
        raise ValueError("frequency forms are incompatible; choose center_hz/range_hz or start_hz/end_hz")
    if center is not None:
        if not 5.0 <= center < 2.0e9:
            raise ValueError("center_hz must be at least 5 Hz and less than 2 GHz")
    if frequency_range is not None and not 10.0 <= frequency_range <= 2.0e9:
        raise ValueError("range_hz must be from 10 Hz through 2 GHz")
    if start is not None:
        if not 0.0 <= start <= 2.0e9:
            raise ValueError("start_hz must be from 0 Hz through 2 GHz")
    if end is not None and not 10.0 <= end <= 2.0e9:
        raise ValueError("end_hz must be from 10 Hz through 2 GHz")
    if start is not None and end is not None and not start + 10.0 <= end:
        raise ValueError("end_hz must be at least start_hz + 10 Hz")


def _same_number(left: float, right: float) -> bool:
    return _math.isclose(left, right, rel_tol=1e-12, abs_tol=0.0)


def _scpi_number(value: float) -> str:
    return format(value, ".15g")


def _set_frequency_pair(session: Any, math_name: str, current: dict[str, Any], desired: dict[str, Any], writes: list[str]) -> None:
    base = f":{math_name}:FFT:"
    if desired["start_hz"] is not None:
        start, end = desired["start_hz"], desired["end_hz"]
        current_start, current_end = current["start_hz"], current["end_hz"]
        # Keep every intermediate endpoint inside the instrument's documented
        # ten-Hz separation.  Expanding the upper edge first is safe when the
        # requested end is above the current end; otherwise lower the start.
        if end > current_end:
            if not _same_number(end, current_end):
                writes.append(base + "FREQuency:END " + _scpi_number(end))
            if not _same_number(start, current_start):
                writes.append(base + "FREQuency:STARt " + _scpi_number(start))
        else:
            if not _same_number(start, current_start):
                writes.append(base + "FREQuency:STARt " + _scpi_number(start))
            if not _same_number(end, current_end):
                writes.append(base + "FREQuency:END " + _scpi_number(end))
    elif desired["center_hz"] is not None:
        if not _same_number(desired["range_hz"], current["range_hz"]):
            writes.append(base + "HSCale " + _scpi_number(desired["range_hz"]))
        if not _same_number(desired["center_hz"], current["center_hz"]):
            writes.append(base + "HCENter " + _scpi_number(desired["center_hz"]))


def set_fft(
    session: Any,
    math: Any = 1,
    *,
    source: Any = None,
    window: Any = None,
    unit: Any = None,
    mode: Any = None,
    averages: Any = None,
    average_count: Any = None,
    scale: Any = None,
    vertical_scale: Any = None,
    offset: Any = None,
    vertical_offset: Any = None,
    center_hz: Any = None,
    range_hz: Any = None,
    start_hz: Any = None,
    end_hz: Any = None,
    frequency_center_hz: Any = None,
    frequency_range_hz: Any = None,
    frequency_start_hz: Any = None,
    frequency_end_hz: Any = None,
    search_enabled: Any = None,
    search_enable: Any = None,
    peak_count: Any = None,
    search_count: Any = None,
    count: Any = None,
    threshold: Any = None,
    excursion: Any = None,
    order: Any = None,
    operator: Any = None,
    select_fft: Any = None,
    display: Any = None,
) -> dict[str, Any]:
    """Send only the explicitly requested FFT commands.

    Selecting FFT and enabling the MATH display are explicit.  No analog
    channel display command is issued by this handler.  When no selector is
    supplied alongside FFT fields, one operator query is used only to confirm
    that the existing MATH route is already FFT; no other setting is queried.
    """

    math_name = _math_name(math)
    # Normalize every submitted value before any device write.
    requested_source = None if source is None else _source(source, math_name)
    requested_window = None if window is None else _window(window)
    requested_unit = None if unit is None else _unit(unit)
    requested_mode = None if mode is None else _mode(mode)
    requested_averages = _alias(averages, average_count, "averages", "average_count")
    requested_averages = None if requested_averages is None else _integer(requested_averages, "averages", 2, 1000)
    requested_scale = _alias(scale, vertical_scale, "scale", "vertical_scale")
    requested_scale = None if requested_scale is None else _finite(requested_scale, "scale")
    requested_offset = _alias(offset, vertical_offset, "offset", "vertical_offset")
    requested_offset = None if requested_offset is None else _finite(requested_offset, "offset")
    requested_center = _alias(center_hz, frequency_center_hz, "center_hz", "frequency_center_hz")
    requested_range = _alias(range_hz, frequency_range_hz, "range_hz", "frequency_range_hz")
    requested_start = _alias(start_hz, frequency_start_hz, "start_hz", "frequency_start_hz")
    requested_end = _alias(end_hz, frequency_end_hz, "end_hz", "frequency_end_hz")
    requested_center = None if requested_center is None else _finite(requested_center, "center_hz")
    requested_range = None if requested_range is None else _finite(requested_range, "range_hz")
    requested_start = None if requested_start is None else _finite(requested_start, "start_hz")
    requested_end = None if requested_end is None else _finite(requested_end, "end_hz")
    _validate_frequency_pair(requested_center, requested_range, requested_start, requested_end)
    requested_search = _alias(search_enabled, search_enable, "search_enabled", "search_enable")
    requested_search = None if requested_search is None else _bool_input(requested_search, "search_enabled")
    requested_count = _alias(peak_count, search_count, "peak_count", "search_count")
    requested_count = _alias(requested_count, count, "peak_count/search_count", "count")
    requested_count = None if requested_count is None else _integer(requested_count, "peak_count", 1, 15)
    requested_threshold = None if threshold is None else _finite(threshold, "threshold")
    requested_excursion = None if excursion is None else _finite(excursion, "excursion")
    requested_order = None if order is None else _order(order)
    requested_operator = None if operator is None else str(operator).strip().upper()
    if requested_operator is not None and requested_operator != "FFT":
        raise ValueError("operator must be FFT; this tool does not configure another MATH operator")
    requested_select = None if select_fft is None else _bool_input(select_fft, "select_fft")
    if requested_select is True and requested_operator is False:
        raise ValueError("select_fft and operator cannot conflict")
    if requested_operator == "FFT":
        requested_select = True
    requested_display = None if display is None else _bool_input(display, "display")

    any_fft_field = any(
        value is not None
        for value in (
            requested_source, requested_window, requested_unit, requested_mode,
            requested_averages, requested_scale, requested_offset,
            requested_center, requested_range, requested_start, requested_end,
            requested_search, requested_count, requested_threshold,
            requested_excursion, requested_order,
        )
    )
    if requested_select is False and (any_fft_field or requested_operator == "FFT"):
        raise ValueError("select_fft=False conflicts with requested FFT fields or operator=FFT")
    if requested_averages is not None and requested_mode is not None and requested_mode != "AVER":
        raise ValueError("averages can only be set in explicit FFT AVER mode")
    if requested_scale is not None and not 1.0e-9 <= requested_scale <= 5.0e9:
        raise ValueError("scale must be from 1 nV/Vrms or dB through 5 GV/dB")
    if requested_offset is not None and not -1.0e9 <= requested_offset <= 1.0e9:
        raise ValueError("offset must be from -1 GV through +1 GV")
    if requested_excursion is not None:
        if requested_excursion < 0:
            raise ValueError("excursion must be non-negative")
        if requested_scale is not None and requested_excursion > 8.0 * requested_scale:
            raise ValueError("excursion must be from 0 through 8 times the requested FFT scale")

    writes: list[str] = []
    if requested_select or requested_operator == "FFT":
        writes.append(f":{math_name}:OPERator FFT")
    if requested_display is not None:
        writes.append(f":{math_name}:DISPlay {1 if requested_display else 0}")
    base = f":{math_name}:FFT:"
    if requested_source is not None:
        writes.append(base + "SOURce " + requested_source)
    if requested_window is not None:
        writes.append(base + "WINDow " + requested_window)
    if requested_unit is not None:
        writes.append(base + "UNIT " + requested_unit)
    if requested_mode is not None:
        writes.append(base + "MODE " + requested_mode)
    if requested_averages is not None:
        writes.append(base + "AVCNt " + str(requested_averages))
    if requested_scale is not None:
        writes.append(base + "SCALe " + _scpi_number(requested_scale))
    if requested_offset is not None:
        writes.append(base + "OFFSet " + _scpi_number(requested_offset))
    if requested_range is not None:
        writes.append(base + "HSCale " + _scpi_number(requested_range))
    if requested_center is not None:
        writes.append(base + "HCENter " + _scpi_number(requested_center))
    if requested_start is not None:
        writes.append(base + "FREQuency:STARt " + _scpi_number(requested_start))
    if requested_end is not None:
        writes.append(base + "FREQuency:END " + _scpi_number(requested_end))
    search_base = base + "SEARch:"
    if requested_count is not None:
        writes.append(search_base + "NUM " + str(requested_count))
    if requested_threshold is not None:
        writes.append(search_base + "THReshold " + _scpi_number(requested_threshold))
    if requested_excursion is not None:
        writes.append(search_base + "EXCursion " + _scpi_number(requested_excursion))
    if requested_order is not None:
        writes.append(search_base + "ORDer " + requested_order)
    if requested_search is not None:
        writes.append(search_base + "ENABle " + str(1 if requested_search else 0))

    for command in writes:
        session.write(command)
    return {
        "math": math_name,
        "requested": {key: value for key, value in {
            "source": requested_source, "window": requested_window, "unit": requested_unit,
            "mode": requested_mode, "averages": requested_averages, "scale": requested_scale,
            "offset": requested_offset, "center_hz": requested_center, "range_hz": requested_range,
            "start_hz": requested_start, "end_hz": requested_end, "search_enabled": requested_search,
            "peak_count": requested_count, "threshold": requested_threshold,
            "excursion": requested_excursion, "order": requested_order,
            "operator": requested_operator, "select_fft": requested_select, "display": requested_display,
        }.items() if value is not None},
        "sent": bool(writes),
        "verified": False,
        "commands": writes,
    }


def _parse_frequency(value: str) -> float:
    match = _FREQUENCY_RE.fullmatch(value)
    if match is None:
        raise ValueError(f"invalid FFT peak frequency: {value!r}")
    number, unit = match.groups()
    multiplier = _FREQUENCY_MULTIPLIERS.get(unit.upper())
    if multiplier is None:
        raise ValueError(f"unsupported FFT peak frequency unit: {unit!r}")
    result = float(number) * multiplier
    if not _math.isfinite(result):
        raise ValueError(f"invalid FFT peak frequency: {value!r}")
    return result


def _parse_peak_table(raw: Any) -> list[dict[str, Any]]:
    text = str(raw)
    if not text.strip():
        return []
    peaks: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = next(csv.reader([line]))
        if len(fields) != 3:
            raise ValueError(f"invalid FFT peak-search row: {line!r}")
        rank_raw, frequency_raw, amplitude_raw = (field.strip() for field in fields)
        try:
            rank = int(rank_raw)
        except ValueError:
            raise ValueError(f"invalid FFT peak rank: {rank_raw!r}") from None
        if rank < 1:
            raise ValueError(f"invalid FFT peak rank: {rank_raw!r}")
        amplitude_match = _AMPLITUDE_RE.fullmatch(amplitude_raw)
        if amplitude_match is None:
            raise ValueError(f"invalid FFT peak amplitude: {amplitude_raw!r}")
        amplitude = float(amplitude_match.group(1))
        if not _math.isfinite(amplitude):
            raise ValueError(f"invalid FFT peak amplitude: {amplitude_raw!r}")
        amplitude_unit = amplitude_match.group(2)
        peaks.append(
            {
                "rank": rank,
                "rank_raw": rank_raw,
                "frequency_hz": _parse_frequency(frequency_raw),
                "frequency_raw": frequency_raw,
                "amplitude": amplitude,
                "amplitude_unit": amplitude_unit,
                "amplitude_raw": amplitude_raw,
                "raw": line,
            }
        )
    return peaks


def _axis_encoding(value: Any) -> dict[str, Any]:
    """Validate an optional caller-supplied native-axis encoding.

    ``scale`` and ``offset`` are optional metadata.  When both are supplied,
    the caller declares ``encoded = offset + native * scale``.  No unit is
    inferred when this argument is omitted.
    """
    if value is None:
        return {
            "status": "unresolved",
            "unit": None,
            "native_coordinate": "waveform preamble xorigin + (index - xreference) * xincrement",
            "required": "caller-provided axis encoding is required to label native coordinates as frequency",
        }
    if isinstance(value, str):
        unit = value.strip()
        if not unit:
            raise ValueError("axis_encoding unit must be non-empty")
        return {"status": "caller_declared", "unit": unit, "scale": None, "offset": None}
    if not isinstance(value, dict):
        raise ValueError("axis_encoding must be a unit string or an object")
    unit = value.get("unit")
    if not isinstance(unit, str) or not unit.strip():
        raise ValueError("axis_encoding.unit must be a non-empty string")
    result: dict[str, Any] = {"status": "caller_declared", "unit": unit.strip()}
    for name in ("scale", "offset"):
        if name in value:
            result[name] = _finite(value[name], f"axis_encoding.{name}")
        else:
            result[name] = None
    if (result["scale"] is None) != (result["offset"] is None):
        raise ValueError("axis_encoding.scale and axis_encoding.offset must be supplied together")
    if result["scale"] is not None:
        result["formula"] = "encoded = offset + native * scale"
    return result


def _apply_axis_encoding(native: list[float], encoding: dict[str, Any]) -> list[float] | None:
    if encoding.get("scale") is None:
        return None
    return [encoding["offset"] + value * encoding["scale"] for value in native]


def _full_spectrum(session: Any, math_name: str, settings: dict[str, Any], points: Any, axis_encoding: Any) -> dict[str, Any]:
    count = _integer(points, "points", 1, 1000)
    declared_axis = _axis_encoding(axis_encoding)
    # MATH waveform sources are documented as NORM-only.  get_waveform also
    # keeps the caller's waveform transfer settings intact.
    waveform = get_waveform(
        session,
        source=math_name,
        mode="NORM",
        format="ASC",
        start=1,
        points=count,
    )
    native_axis = waveform["time"]
    encoded_axis = _apply_axis_encoding(native_axis, declared_axis)
    spectrum: dict[str, Any] = {
        "amplitude": waveform["values"],
        "samples": waveform["values"],
        "amplitude_unit": settings["unit"],
        "amplitude_unit_provenance": {
            "value": settings["unit"],
            "source": f":{math_name}:FFT:UNIT?",
            "status": "instrument_reported",
        },
        "native_axis": native_axis,
        "native_axis_unit": None,
        "axis_encoding": declared_axis,
        "preamble": waveform["preamble"],
        "preamble_raw": waveform["preamble"]["raw"],
    }
    if encoded_axis is not None:
        spectrum["encoded_axis"] = encoded_axis
        if declared_axis["unit"].strip().upper() == "HZ":
            spectrum["frequency_hz"] = encoded_axis
    return {
        "math": math_name,
        "operator": "FFT",
        "display": None,
        "search_enabled": None,
        "scope": "full_spectrum_from_math_waveform",
        "spectrum": spectrum,
        "limitation": (
            "The MHO98 guide documents FFT peak search but no full-bin frequency query. "
            "Samples are actual MATH waveform amplitudes; native x coordinates retain "
            "waveform preamble semantics and are not assumed to be Hz."
        ),
    }


def read_fft(
    session: Any,
    math: Any = 1,
    *,
    full_spectrum: bool = False,
    points: Any = 1000,
    axis_encoding: Any = None,
) -> dict[str, Any]:
    """Read the default peak table, or actual MATH waveform spectrum samples."""

    math_name = _math_name(math)
    actual_operator = _operator(session.query(f":{math_name}:OPERator?"))
    if actual_operator != "FFT":
        return {"valid": False, "math": math_name, "operator": actual_operator,
                "reason": "The active MATH operation is not FFT; no FFT measurement is available."}
    context = {
        "source": _source_response(session.query(f":{math_name}:FFT:SOURce?"), math_name),
        "window": _window(session.query(f":{math_name}:FFT:WINDow?")),
        "mode": _mode(session.query(f":{math_name}:FFT:MODE?")),
    }
    if full_spectrum:
        # Operator and amplitude unit describe the returned measurement.
        # Display and search-enable preflight queries are unnecessary.
        settings = {"unit": _unit(session.query(f":{math_name}:FFT:UNIT?"))}
        result = _full_spectrum(session, math_name, settings, points, axis_encoding)
        raw = str(session.query(f":{math_name}:FFT:SEARch:RES?"))
        result["peaks"] = _parse_peak_table(raw)
        result["context"] = context
        result["operator"] = actual_operator
        result["scope"] = "full_spectrum_from_math_waveform" if actual_operator == "FFT" else "math_waveform"
        return result
    raw = str(session.query(f":{math_name}:FFT:SEARch:RES?"))
    peaks = _parse_peak_table(raw)
    return {
        "math": math_name,
        "operator": "FFT",
        "display": None,
        "search_enabled": None,
        "scope": "peak_table_only",
        "context": context,
        "raw_text": raw,
        "count": len(peaks),
        "peaks": peaks,
        "axes": {"frequency": "Hz", "amplitude": "instrument-reported unit per peak"},
    }


_MATH_PROPERTY = {
    "oneOf": [
        {"type": "integer", "enum": [1, 2, 3, 4]},
        {"type": "string", "enum": ["MATH1", "MATH2", "MATH3", "MATH4"]},
    ]
}
_FFT_FIELDS = {
    "source": {"type": "string", "enum": ["CHAN1", "CHAN2", "CHAN3", "CHAN4", "MATH1", "MATH2", "MATH3"]},
    "window": {"type": "string", "enum": ["RECT", "BLAC", "HANN", "HAMM", "FLAT", "TRI"]},
    "unit": {"type": "string", "enum": ["VRMS", "DB"]},
    "mode": {"type": "string", "enum": ["NORM", "AVER", "MAXH"]},
    "averages": {"type": "integer", "minimum": 2, "maximum": 1000},
    "scale": {"type": "number", "minimum": 1e-9, "maximum": 5e9},
    "offset": {"type": "number", "minimum": -1e9, "maximum": 1e9},
    "center_hz": {"type": "number", "minimum": 5, "exclusiveMaximum": 2e9},
    "range_hz": {"type": "number", "minimum": 10, "maximum": 2e9},
    "start_hz": {"type": "number", "minimum": 0, "maximum": 2e9},
    "end_hz": {"type": "number", "minimum": 10, "maximum": 2e9},
    "search_enabled": {"type": "boolean"},
    "peak_count": {"type": "integer", "minimum": 1, "maximum": 15},
    "count": {"type": "integer", "minimum": 1, "maximum": 15},
    "threshold": {"type": "number"},
    "excursion": {"type": "number", "minimum": 0},
    "order": {"type": "string", "enum": ["AMP", "FREQ"]},
}


TOOLS = [
    ToolSpec(
        name="get_fft",
        description="Read MHO98 MATH FFT configuration when the selected math operator is FFT.",
        input_schema={"type": "object", "properties": {"math": _MATH_PROPERTY}, "required": ["math"]},
        handler=get_fft,
        read_only=True,
        needs_session=True,
    ),
    ToolSpec(
        name="set_fft",
        description="Send only requested MHO98 FFT fields; omitted fields are untouched and resulting state is not queried. Selecting FFT and MATH display is explicit.",
        input_schema={
            "type": "object",
            "properties": {
                "math": _MATH_PROPERTY,
                **_FFT_FIELDS,
                "operator": {"type": "string", "enum": ["FFT"]},
                "select_fft": {"type": "boolean"},
                "display": {"type": "boolean"},
            },
            "required": ["math"],
        },
        handler=set_fft,
        read_only=False,
        needs_session=True,
    ),
    ToolSpec(
        name="read_fft",
        description="Read the documented FFT peak table by default, or actual MATH waveform spectrum samples with native-axis provenance; no Hz axis is guessed.",
        input_schema={
            "type": "object",
            "properties": {
                "math": _MATH_PROPERTY,
                "full_spectrum": {"type": "boolean"},
                "points": {"type": "integer", "minimum": 1, "maximum": 1000},
                "axis_encoding": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "object", "properties": {"unit": {"type": "string"}, "scale": {"type": "number"}, "offset": {"type": "number"}}, "required": ["unit"]},
                    ]
                },
            },
            "required": ["math"],
        },
        handler=read_fft,
        read_only=True,
        needs_session=True,
    ),
]
