"""MHO98 function/arbitrary waveform generator controls.

The generator has a deliberately conditional readback surface.  Parameters that
the programming guide says are unavailable for the selected waveform or
modulation type are not queried.  ``set_generator`` validates the complete
requested end state before its first write and never changes output enable.
"""

from __future__ import annotations

import math
import re
from numbers import Real
from typing import Any, Mapping

from .api import ToolSpec


_WAVEFORMS = {
    "SIN": "SIN",
    "SINE": "SIN",
    "SINUSOID": "SIN",
    "SQU": "SQU",
    "SQUARE": "SQU",
    "RAMP": "RAMP",
    "NOIS": "NOIS",
    "NOISE": "NOIS",
    "DC": "DC",
    "ARB": "ARB",
    "EXPR": "EXPR",
    "EXPRISE": "EXPR",
    "EXPF": "EXPF",
    "EXPFALL": "EXPF",
    "ECG1": "ECG1",
    "GAUS": "GAUS",
    "GAUSSIAN": "GAUS",
    "LOR": "LOR",
    "LORENTZ": "LOR",
    "HAV": "HAV",
    "HAVERSINE": "HAV",
    "SINC": "SINC",
}
_WAVEFORM_SCPI = {
    "SIN": "SINusoid",
    "SQU": "SQUare",
    "RAMP": "RAMP",
    "NOIS": "NOISe",
    "DC": "DC",
    "ARB": "ARB",
    "EXPR": "EXPRise",
    "EXPF": "EXPFall",
    "ECG1": "ECG1",
    "GAUS": "GAUSsian",
    "LOR": "LORentz",
    "HAV": "HAVersine",
    "SINC": "SINC",
}
_MOD_WAVEFORMS = {
    "SIN": "SIN",
    "SINUSOID": "SIN",
    "SQU": "SQU",
    "SQUARE": "SQU",
    "TRI": "TRI",
    "TRIANGLE": "TRI",
    "UPR": "UPR",
    "UPRAMP": "UPR",
    "DNR": "DNR",
    "DNRAMP": "DNR",
    "NOIS": "NOIS",
    "NOISE": "NOIS",
}
_MOD_WAVEFORM_SCPI = {
    "SIN": "SINusoid",
    "SQU": "SQUare",
    "TRI": "TRIangle",
    "UPR": "UPRamp",
    "DNR": "DNRamp",
    "NOIS": "NOISe",
}
_MOD_TYPES = frozenset({"AM", "FM", "PM"})
_NO_FREQUENCY = frozenset({"DC", "NOIS"})
_FREQUENCY_LIMITS = {
    "SIN": 100e6,
    "SQU": 20e6,
    "RAMP": 2e6,
    "ARB": 20e6,
}
_MIN_FREQUENCY = 2e-3
_MIN_MOD_FREQUENCY = 2e-3
_MAX_MOD_FREQUENCY = 1e6
_PATH_RE = re.compile(r"^[CDcd]:[\\/].+")


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a finite number") from None
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    return result


def _scpi_number(value: float) -> str:
    return format(value, ".15g")


def _bool_response(value: Any, name: str) -> bool:
    token = str(value).strip().upper()
    if token in {"1", "ON", "TRUE"}:
        return True
    if token in {"0", "OFF", "FALSE"}:
        return False
    raise ValueError(f"invalid {name} response from MHO98: {value!r}")


def _strict_bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a real boolean (true or false), not a string or number")
    return value


def _channel(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("channel must be 1 or 2")
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = -1
    if number not in {1, 2} or str(value).strip() not in {"1", "2"} and not (
        isinstance(value, Real) and float(value).is_integer() and number in {1, 2}
    ):
        raise ValueError("channel must be 1 or 2")
    return number


def _waveform(value: Any) -> str:
    token = str(value).strip().upper().replace(" ", "")
    try:
        return _WAVEFORMS[token]
    except KeyError:
        raise ValueError(
            "waveform must be one of SIN, SQU, RAMP, NOIS, DC, ARB, EXPR, "
            "EXPF, ECG1, GAUS, LOR, HAV, or SINC"
        ) from None


def _mod_type(value: Any) -> str:
    token = str(value).strip().upper()
    if token not in _MOD_TYPES:
        raise ValueError("modulation_type must be AM, FM, or PM")
    return token


def _mod_waveform(value: Any) -> str:
    token = str(value).strip().upper().replace(" ", "")
    try:
        return _MOD_WAVEFORMS[token]
    except KeyError:
        raise ValueError("modulation_waveform must be SIN, SQU, TRI, UPR, DNR, or NOIS") from None


def _load(value: Any) -> str:
    token = str(value).strip().upper().replace(" ", "")
    if token in {"HIGHZ", "OMEG", "OMEGA", "1M", "1MOHM", "1000000"}:
        return "HighZ"
    if token in {"50", "50OHM", "FIFT", "FIFTY", "LOAD"}:
        return "50ohm"
    raise ValueError("load must be HighZ or 50ohm")


def _load_response(value: Any) -> str:
    token = str(value).strip().upper().replace("OHM", "").replace("Ω", "")
    if token in {"OMEG", "OMEGA", "1M", "1000000"}:
        return "HighZ"
    if token in {"FIFT", "FIFTY", "50", "50.0"}:
        return "50ohm"
    raise ValueError(f"invalid generator load response from MHO98: {value!r}")


def _waveform_response(value: Any) -> str:
    token = str(value).strip().upper()
    for candidate, canonical in _WAVEFORMS.items():
        if token == candidate or token.startswith(candidate):
            return canonical
    raise ValueError(f"invalid generator waveform response from MHO98: {value!r}")


def _mod_waveform_response(value: Any) -> str:
    token = str(value).strip().upper()
    for candidate, canonical in _MOD_WAVEFORMS.items():
        if token == candidate or token.startswith(candidate):
            return canonical
    raise ValueError(f"invalid modulation waveform response from MHO98: {value!r}")


def _path(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("arbitrary_path must be a non-empty instrument path")
    result = value.strip().replace("\\", "/")
    if not _PATH_RE.fullmatch(result):
        raise ValueError("arbitrary_path must be an instrument path beginning C:/ or D:/; Mac uploads are unsupported")
    if any(ord(char) < 32 or ord(char) == 127 for char in result) or any(char in result for char in '";\r\n'):
        raise ValueError("arbitrary_path contains an invalid SCPI character")
    return result


def _response_number(value: Any, name: str) -> float:
    return _finite(value, f"{name} response")


_GENERATOR_OPTIONS = ("AFG100", "AFG50", "BND")


def _capability_fields(capability: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "dg_available": capability["dg_available"],
        "dg_status": capability["dg_status"],
        "generator_option_status": capability["generator_option_status"],
        "capability_source": capability["capability_source"],
        "capability_warning": capability.get("capability_warning"),
    }


def _generator_capability(session: Any) -> dict[str, Any]:
    """Determine generator access without hiding the instrument's DG status."""

    dg_status = str(session.query(":SYSTem:DGSTatus?")).strip()
    dg_available = _bool_response(dg_status, "DG availability")
    if dg_available:
        return {
            "dg_available": True,
            "dg_status": dg_status,
            "generator_option_status": None,
            "capability_source": "DG module status",
            "frequency_limit_hz": 100e6,
        }

    option_status: dict[str, str] = {}
    option_enabled: dict[str, bool] = {}
    for option in _GENERATOR_OPTIONS:
        raw_status = str(
            session.query(f":SYSTem:OPTion:STATus? {option}")
        ).strip()
        option_status[option] = raw_status
        option_enabled[option] = _bool_response(raw_status, f"{option} option status")

    if not any(option_enabled.values()):
        statuses = ", ".join(f"{name}={value}" for name, value in option_status.items())
        raise ValueError(
            "MHO98 generator is unavailable: SYSTem:DGSTatus? returned "
            f"{dg_status}, and documented option status is all-negative ({statuses})"
        )

    if option_enabled["AFG100"] or option_enabled["BND"]:
        frequency_limit_hz = 100e6
    else:
        frequency_limit_hz = 50e6
    positive = ", ".join(name for name, enabled in option_enabled.items() if enabled)
    return {
        "dg_available": False,
        "dg_status": dg_status,
        "generator_option_status": option_status,
        "capability_source": f"documented option status ({positive})",
        "capability_warning": (
            "SYSTem:DGSTatus? reported 0 despite positive documented generator "
            f"option status ({positive}); access is accepted only with successful "
            "functional source readback."
        ),
        "frequency_limit_hz": frequency_limit_hz,
    }


def _query_output(
    session: Any, channel: int, capability: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "channel": channel,
        "output_enabled": _bool_response(
            session.query(f":SOURce{channel}:OUTPut:STATe?"), "output state"
        ),
    }


def _query_generator(session: Any, channel: int) -> dict[str, Any]:
    prefix = f":SOURce{channel}"
    waveform = _waveform_response(session.query(prefix + ":FUNCtion?"))
    result: dict[str, Any] = {
        "channel": channel,
        "output_enabled": _bool_response(session.query(prefix + ":OUTPut:STATe?"), "output state"),
        "waveform": waveform,
        "frequency_hz": None,
        "period_s": None,
        "phase_deg": _response_number(session.query(prefix + ":PHASe?"), "phase_deg"),
        "square_duty_percent": None,
        "ramp_symmetry_percent": None,
        "amplitude_vpp": _response_number(session.query(prefix + ":VOLTage:AMPLitude?"), "amplitude_vpp"),
        "offset_v": _response_number(session.query(prefix + ":VOLTage:OFFSet?"), "offset_v"),
        "high_v": _response_number(session.query(prefix + ":VOLTage:HIGH?"), "high_v"),
        "low_v": _response_number(session.query(prefix + ":VOLTage:LOW?"), "low_v"),
        "load": _load_response(session.query(prefix + ":IMPedance?")),
        "arbitrary_path": None,
        "modulation_enabled": _bool_response(session.query(prefix + ":MOD:STATe?"), "modulation state"),
        "modulation_type": _mod_type(session.query(prefix + ":MOD:TYPe?")),
        "modulation_frequency_hz": None,
        "modulation_waveform": None,
        "am_depth_percent": None,
        "fm_deviation_hz": None,
        "pm_deviation_deg": None,
        "unavailable": [],
    }

    if waveform in _NO_FREQUENCY:
        result["unavailable"].extend(["frequency_hz", "period_s"])
    else:
        result["frequency_hz"] = _response_number(
            session.query(prefix + ":FREQuency?"), "frequency_hz"
        )
        result["period_s"] = _response_number(session.query(prefix + ":PERiod?"), "period_s")
    if waveform == "SQU":
        result["square_duty_percent"] = _response_number(
            session.query(prefix + ":FUNCtion:SQUare:DUTY?"), "square_duty_percent"
        )
    else:
        result["unavailable"].append("square_duty_percent")
    if waveform == "RAMP":
        result["ramp_symmetry_percent"] = _response_number(
            session.query(prefix + ":FUNCtion:RAMP:SYMMetry?"), "ramp_symmetry_percent"
        )
    else:
        result["unavailable"].append("ramp_symmetry_percent")
    if waveform == "ARB":
        result["arbitrary_path"] = str(session.query(prefix + ":LOAD:ARBitrary?")).strip()
    else:
        result["unavailable"].append("arbitrary_path")

    if not result["modulation_enabled"]:
        result["unavailable"].extend(
            ["modulation_frequency_hz", "modulation_waveform", "am_depth_percent", "fm_deviation_hz", "pm_deviation_deg"]
        )
    else:
        mod = result["modulation_type"]
        result["modulation_frequency_hz"] = _response_number(
            session.query(prefix + f":MOD:{mod}:INTernal:FREQuency?"), "modulation_frequency_hz"
        )
        result["modulation_waveform"] = _mod_waveform_response(
            session.query(prefix + f":MOD:{mod}:INTernal:FUNCtion?")
        )
        if mod == "AM":
            result["am_depth_percent"] = _response_number(
                session.query(prefix + ":MOD:AM:DEPTh?"), "am_depth_percent"
            )
            result["unavailable"].extend(["fm_deviation_hz", "pm_deviation_deg"])
        elif mod == "FM":
            result["fm_deviation_hz"] = _response_number(
                session.query(prefix + ":MOD:FM:DEViation?"), "fm_deviation_hz"
            )
            result["unavailable"].extend(["am_depth_percent", "pm_deviation_deg"])
        else:
            result["pm_deviation_deg"] = _response_number(
                session.query(prefix + ":MOD:PM:DEViation?"), "pm_deviation_deg"
            )
            result["unavailable"].extend(["am_depth_percent", "fm_deviation_hz"])
    return result


def get_generator(session: Any, channel: Any) -> dict[str, Any]:
    """Return effective settings for generator channel 1 or 2."""

    return _query_generator(session, _channel(channel))


def _coalesce(primary: Any, alias: Any, name: str) -> Any:
    if primary is not None and alias is not None:
        raise ValueError(f"specify only one of {name} and its alias")
    return primary if primary is not None else alias


def _frequency_limit(waveform: str, generator_limit_hz: float = 100e6) -> float:
    if waveform == "SIN":
        return min(_FREQUENCY_LIMITS[waveform], generator_limit_hz)
    return _FREQUENCY_LIMITS.get(waveform, 20e6)


def _validate_frequency(
    waveform: str, frequency: float, generator_limit_hz: float = 100e6
) -> None:
    if waveform in _NO_FREQUENCY:
        raise ValueError(f"{waveform} has no frequency or period parameter")
    maximum = _frequency_limit(waveform, generator_limit_hz)
    if not _MIN_FREQUENCY <= frequency <= maximum:
        raise ValueError(
            f"frequency_hz {frequency:g} is outside the documented {waveform} range "
            f"{_MIN_FREQUENCY:g}..{maximum:g} Hz"
        )


def _max_amplitude(load: str, frequency: float | None) -> float:
    # DC and noise have no frequency parameter in the MHO98 guide.  Their
    # frequency-dependent amplitude ceiling cannot be derived, so leave that
    # specific check to the instrument rather than inventing a limit.
    if frequency is None:
        return math.inf
    high_frequency = frequency > 50e6
    if load == "50ohm":
        return 5.0 if high_frequency else 10.0
    return 10.0 if high_frequency else 20.0


def _validate_voltage_state(load: str, frequency: float | None, amplitude: float, offset: float, high: float, low: float) -> None:
    if amplitude <= 0:
        raise ValueError("amplitude_vpp must be greater than zero")
    maximum = _max_amplitude(load, frequency)
    minimum = 0.001 if load == "50ohm" else 0.002
    if not minimum <= amplitude <= maximum:
        raise ValueError(
            f"amplitude_vpp {amplitude:g} is outside the documented {load} combined "
            f"frequency range {minimum:g}..{maximum:g} Vpp"
        )
    if math.isfinite(maximum) and abs(offset) > (maximum - amplitude) / 2 + 1e-12:
        raise ValueError(
            "offset_v is outside the documented amplitude/load/frequency range: "
            "abs(offset) must be no more than (maximum amplitude - amplitude)/2"
        )
    if math.isfinite(maximum):
        accuracy = 0.001 if load == "50ohm" else 0.002
        if not -maximum / 2 - 1e-12 <= low <= maximum / 2 + 1e-12:
            raise ValueError("low_v is outside the documented maximum-amplitude range")
        if not -maximum / 2 - 1e-12 <= high <= maximum / 2 + 1e-12:
            raise ValueError("high_v is outside the documented maximum-amplitude range")
        if high - low + 1e-12 < accuracy:
            raise ValueError(f"high_v and low_v must differ by at least {accuracy:g} V for {load}")


def _validate_modulation(
    mod_type: str,
    mod_frequency: float | None,
    mod_waveform: str | None,
    am_depth: float | None,
    fm_deviation: float | None,
    pm_deviation: float | None,
    carrier_frequency: float | None,
    carrier_limit: float | None,
) -> None:
    if mod_frequency is not None and not _MIN_MOD_FREQUENCY <= mod_frequency <= _MAX_MOD_FREQUENCY:
        raise ValueError("modulation_frequency_hz must be between 0.002 and 1000000 Hz")
    if mod_waveform is not None:
        _mod_waveform(mod_waveform)
    if mod_type == "AM" and am_depth is not None and not 0 <= am_depth <= 120:
        raise ValueError("am_depth_percent must be between 0 and 120")
    if mod_type == "FM" and fm_deviation is not None:
        if fm_deviation < _MIN_MOD_FREQUENCY:
            raise ValueError("fm_deviation_hz must be at least 0.002 Hz")
        if carrier_frequency is not None and fm_deviation > carrier_frequency:
            raise ValueError("fm_deviation_hz must not exceed the current carrier frequency")
        if carrier_limit is not None and carrier_frequency is not None and carrier_frequency + fm_deviation > carrier_limit:
            raise ValueError("carrier frequency plus fm_deviation_hz exceeds the documented carrier limit")
    if mod_type == "PM" and pm_deviation is not None and not 0 <= pm_deviation <= 360:
        raise ValueError("pm_deviation_deg must be between 0 and 360")


def set_generator(
    session: Any,
    channel: Any,
    *,
    waveform: Any = None,
    frequency_hz: Any = None,
    period_s: Any = None,
    phase_deg: Any = None,
    square_duty_percent: Any = None,
    ramp_symmetry_percent: Any = None,
    amplitude_vpp: Any = None,
    offset_v: Any = None,
    high_v: Any = None,
    low_v: Any = None,
    load: Any = None,
    modulation_enabled: Any = None,
    modulation_type: Any = None,
    modulation_frequency_hz: Any = None,
    modulation_waveform: Any = None,
    am_depth_percent: Any = None,
    fm_deviation_hz: Any = None,
    pm_deviation_deg: Any = None,
    phase_sync: Any = None,
    arbitrary_path: Any = None,
    # Small aliases make direct Python use convenient while the MCP schema keeps
    # the unit-bearing names above as the documented interface.
    frequency: Any = None,
    period: Any = None,
    phase: Any = None,
    amplitude: Any = None,
    duty: Any = None,
    symmetry: Any = None,
    high: Any = None,
    low: Any = None,
    offset: Any = None,
) -> dict[str, Any]:
    """Send only explicitly requested generator commands without readback."""

    ch = _channel(channel)
    requested_waveform = None if waveform is None else _waveform(waveform)
    requested_frequency = _coalesce(frequency_hz, frequency, "frequency_hz")
    requested_period = _coalesce(period_s, period, "period_s")
    requested_phase = _coalesce(phase_deg, phase, "phase_deg")
    requested_amplitude = _coalesce(amplitude_vpp, amplitude, "amplitude_vpp")
    requested_duty = _coalesce(square_duty_percent, duty, "square_duty_percent")
    requested_symmetry = _coalesce(ramp_symmetry_percent, symmetry, "ramp_symmetry_percent")
    requested_high = _coalesce(high_v, high, "high_v")
    requested_low = _coalesce(low_v, low, "low_v")
    requested_offset_value = _coalesce(offset_v, offset, "offset_v")

    if requested_frequency is not None and requested_period is not None:
        raise ValueError("specify only one of frequency_hz or period_s")
    if requested_high is not None or requested_low is not None:
        if requested_amplitude is not None or requested_offset_value is not None:
            raise ValueError("use amplitude_vpp/offset_v or high_v/low_v, not both voltage forms")
    if requested_amplitude is not None:
        requested_amplitude = _finite(requested_amplitude, "amplitude_vpp")
    requested_offset = None if requested_offset_value is None else _finite(requested_offset_value, "offset_v")
    requested_high = None if requested_high is None else _finite(requested_high, "high_v")
    requested_low = None if requested_low is None else _finite(requested_low, "low_v")
    requested_frequency = None if requested_frequency is None else _finite(requested_frequency, "frequency_hz")
    requested_period = None if requested_period is None else _finite(requested_period, "period_s")
    requested_phase = None if requested_phase is None else _finite(requested_phase, "phase_deg")
    requested_load = None if load is None else _load(load)
    requested_mod_enabled = None if modulation_enabled is None else _strict_bool(modulation_enabled, "modulation_enabled")
    requested_mod_type = None if modulation_type is None else _mod_type(modulation_type)
    requested_mod_frequency = None if modulation_frequency_hz is None else _finite(modulation_frequency_hz, "modulation_frequency_hz")
    requested_mod_waveform = None if modulation_waveform is None else _mod_waveform(modulation_waveform)
    requested_am_depth = None if am_depth_percent is None else _finite(am_depth_percent, "am_depth_percent")
    requested_fm_deviation = None if fm_deviation_hz is None else _finite(fm_deviation_hz, "fm_deviation_hz")
    requested_pm_deviation = None if pm_deviation_deg is None else _finite(pm_deviation_deg, "pm_deviation_deg")
    requested_phase_sync = None if phase_sync is None else _strict_bool(phase_sync, "phase_sync")
    requested_path = None if arbitrary_path is None else _path(arbitrary_path)

    if requested_duty is not None:
        requested_duty = _finite(requested_duty, "square_duty_percent")
        if requested_waveform is not None and requested_waveform != "SQU":
            raise ValueError("square_duty_percent is only applicable to the Square waveform")
        if not 1 <= requested_duty <= 99:
            raise ValueError("square_duty_percent must be between 1 and 99")
    if requested_symmetry is not None:
        requested_symmetry = _finite(requested_symmetry, "ramp_symmetry_percent")
        if requested_waveform is not None and requested_waveform != "RAMP":
            raise ValueError("ramp_symmetry_percent is only applicable to the Ramp waveform")
        if not 0 <= requested_symmetry <= 100:
            raise ValueError("ramp_symmetry_percent must be between 0 and 100")
    if requested_path is not None and requested_waveform is not None and requested_waveform != "ARB":
        raise ValueError("arbitrary_path is only applicable when waveform is ARB")
    if requested_frequency is not None:
        if requested_waveform in _NO_FREQUENCY:
            raise ValueError(f"{requested_waveform} has no frequency or period parameter")
        if requested_waveform is not None:
            _validate_frequency(requested_waveform, requested_frequency)
        elif requested_frequency < _MIN_FREQUENCY:
            raise ValueError("frequency_hz must be at least 0.002 Hz")
    if requested_period is not None and requested_period <= 0:
        raise ValueError("period_s must be greater than zero")
    if requested_period is not None and requested_waveform in _NO_FREQUENCY:
        raise ValueError(f"{requested_waveform} has no frequency or period parameter")
    if requested_phase is not None and not 0 <= requested_phase <= 360:
        raise ValueError("phase_deg must be between 0 and 360")
    if requested_amplitude is not None and requested_amplitude <= 0:
        raise ValueError("amplitude_vpp must be greater than zero")
    if requested_high is not None and requested_low is not None and requested_high <= requested_low:
        raise ValueError("high_v must be greater than low_v")

    mod_values_requested = any(value is not None for value in (
        requested_mod_frequency, requested_mod_waveform, requested_am_depth,
        requested_fm_deviation, requested_pm_deviation,
    ))
    final_mod_type = requested_mod_type
    if final_mod_type is None and mod_values_requested:
        # The modulation type is a command-path selector.  One query is needed
        # only for that selector; no generator snapshot is taken.
        final_mod_type = _mod_type(session.query(f":SOURce{ch}:MOD:TYPe?"))
    if requested_am_depth is not None and final_mod_type is not None and final_mod_type != "AM":
        raise ValueError("am_depth_percent requires modulation_type AM")
    if requested_fm_deviation is not None and final_mod_type is not None and final_mod_type != "FM":
        raise ValueError("fm_deviation_hz requires modulation_type FM")
    if requested_pm_deviation is not None and final_mod_type is not None and final_mod_type != "PM":
        raise ValueError("pm_deviation_deg requires modulation_type PM")
    if final_mod_type is not None:
        _validate_modulation(
            final_mod_type, requested_mod_frequency, requested_mod_waveform,
            requested_am_depth, requested_fm_deviation, requested_pm_deviation,
            requested_frequency,
            _frequency_limit(requested_waveform) if requested_waveform not in {None, *_NO_FREQUENCY} else None,
        )

    prefix = f":SOURce{ch}"
    writes: list[str] = []
    if requested_load is not None:
        writes.append(prefix + ":IMPedance " + ("FIFTy" if requested_load == "50ohm" else "OMEG"))
    if requested_waveform is not None:
        writes.append(prefix + ":FUNCtion " + _WAVEFORM_SCPI[requested_waveform])
    if requested_path is not None:
        writes.append(prefix + ":LOAD:ARBitrary " + requested_path)
    if requested_frequency is not None:
        writes.append(prefix + ":FREQuency " + _scpi_number(requested_frequency))
    elif requested_period is not None:
        writes.append(prefix + ":PERiod " + _scpi_number(requested_period))
    if requested_phase is not None:
        writes.append(prefix + ":PHASe " + _scpi_number(requested_phase))
    if requested_duty is not None:
        writes.append(prefix + ":FUNCtion:SQUare:DUTY " + _scpi_number(requested_duty))
    if requested_symmetry is not None:
        writes.append(prefix + ":FUNCtion:RAMP:SYMMetry " + _scpi_number(requested_symmetry))
    voltage_form_levels = requested_high is not None or requested_low is not None
    if voltage_form_levels:
        if requested_low is not None:
            writes.append(prefix + ":VOLTage:LOW " + _scpi_number(requested_low))
        if requested_high is not None:
            writes.append(prefix + ":VOLTage:HIGH " + _scpi_number(requested_high))
    else:
        if requested_amplitude is not None:
            writes.append(prefix + ":VOLTage:AMPLitude " + _scpi_number(requested_amplitude))
        if requested_offset is not None:
            writes.append(prefix + ":VOLTage:OFFSet " + _scpi_number(requested_offset))

    if requested_mod_type is not None:
        writes.append(prefix + ":MOD:TYPe " + requested_mod_type)
    if requested_mod_frequency is not None:
        writes.append(prefix + f":MOD:{final_mod_type}:INTernal:FREQuency " + _scpi_number(requested_mod_frequency))
    if requested_mod_waveform is not None:
        writes.append(prefix + f":MOD:{final_mod_type}:INTernal:FUNCtion " + _MOD_WAVEFORM_SCPI[requested_mod_waveform])
    if final_mod_type == "AM" and requested_am_depth is not None:
        writes.append(prefix + ":MOD:AM:DEPTh " + _scpi_number(requested_am_depth))
    if final_mod_type == "FM" and requested_fm_deviation is not None:
        writes.append(prefix + ":MOD:FM:DEViation " + _scpi_number(requested_fm_deviation))
    if final_mod_type == "PM" and requested_pm_deviation is not None:
        writes.append(prefix + ":MOD:PM:DEViation " + _scpi_number(requested_pm_deviation))
    if requested_mod_enabled is not None:
        writes.append(prefix + ":MOD:STATe " + ("1" if requested_mod_enabled else "0"))
    if requested_phase_sync:
        writes.append(prefix + ":PHASe:SYNChronize")

    for command in writes:
        session.write(command)
    requested = {
        key: value for key, value in {
            "channel": ch, "waveform": requested_waveform, "frequency_hz": requested_frequency,
            "period_s": requested_period, "phase_deg": requested_phase, "square_duty_percent": requested_duty,
            "ramp_symmetry_percent": requested_symmetry, "amplitude_vpp": requested_amplitude,
            "offset_v": requested_offset, "high_v": requested_high, "low_v": requested_low,
            "load": requested_load, "modulation_enabled": requested_mod_enabled,
            "modulation_type": requested_mod_type, "modulation_frequency_hz": requested_mod_frequency,
            "modulation_waveform": requested_mod_waveform, "am_depth_percent": requested_am_depth,
            "fm_deviation_hz": requested_fm_deviation, "pm_deviation_deg": requested_pm_deviation,
            "phase_sync": requested_phase_sync, "arbitrary_path": requested_path,
        }.items() if value is not None
    }
    return {"sent": bool(writes), "verified": False, "commands": writes, "requested": requested, **requested}


def set_generator_output(session: Any, channel: Any, enabled: Any) -> dict[str, Any]:
    """Change only the selected generator output enable state."""

    ch = _channel(channel)
    requested = _strict_bool(enabled, "enabled")
    command = f":SOURce{ch}:OUTPut:STATe " + ("1" if requested else "0")
    session.write(command)
    return {"sent": True, "verified": False, "commands": [command], "channel": ch, "enabled": requested}


_WAVEFORM_ENUM = ["SIN", "SQU", "RAMP", "NOIS", "DC", "ARB", "EXPR", "EXPF", "ECG1", "GAUS", "LOR", "HAV", "SINC"]
_GENERATOR_PROPERTIES = {
    "channel": {"type": "integer", "enum": [1, 2]},
    "waveform": {"type": "string", "enum": _WAVEFORM_ENUM},
    "frequency_hz": {"type": "number"},
    "period_s": {"type": "number", "exclusiveMinimum": 0},
    "phase_deg": {"type": "number", "minimum": 0, "maximum": 360},
    "square_duty_percent": {"type": "number", "minimum": 1, "maximum": 99},
    "ramp_symmetry_percent": {"type": "number", "minimum": 0, "maximum": 100},
    "amplitude_vpp": {"type": "number", "exclusiveMinimum": 0},
    "offset_v": {"type": "number"},
    "high_v": {"type": "number"},
    "low_v": {"type": "number"},
    "load": {"type": "string", "enum": ["HighZ", "50ohm"]},
    "modulation_enabled": {"type": "boolean"},
    "modulation_type": {"type": "string", "enum": ["AM", "FM", "PM"]},
    "modulation_frequency_hz": {"type": "number"},
    "modulation_waveform": {"type": "string", "enum": ["SIN", "SQU", "TRI", "UPR", "DNR", "NOIS"]},
    "am_depth_percent": {"type": "number", "minimum": 0, "maximum": 120},
    "fm_deviation_hz": {"type": "number"},
    "pm_deviation_deg": {"type": "number", "minimum": 0, "maximum": 360},
    "phase_sync": {"type": "boolean"},
    "arbitrary_path": {"type": "string", "description": "Instrument path beginning C:/ or D:/; no host upload is performed."},
}


TOOLS = [
    ToolSpec(
        name="get_generator",
        description="Read effective MHO98 generator settings for channel 1 or 2, omitting inapplicable DC/noise, waveform, and modulation parameters.",
        input_schema={"type": "object", "properties": {"channel": _GENERATOR_PROPERTIES["channel"]}, "required": ["channel"]},
        handler=get_generator,
        read_only=True,
        needs_session=True,
    ),
    ToolSpec(
        name="set_generator",
        description="Send selected MHO98 generator settings without changing output enable; resulting values are not verified.",
        input_schema={"type": "object", "properties": _GENERATOR_PROPERTIES, "required": ["channel"]},
        handler=set_generator,
        read_only=False,
        needs_session=True,
    ),
    ToolSpec(
        name="set_generator_output",
        description="Send only the MHO98 generator output-enable command; resulting state is not verified.",
        input_schema={
            "type": "object",
            "properties": {"channel": _GENERATOR_PROPERTIES["channel"], "enabled": {"type": "boolean"}},
            "required": ["channel", "enabled"],
        },
        handler=set_generator_output,
        read_only=False,
        needs_session=True,
    ),
]
