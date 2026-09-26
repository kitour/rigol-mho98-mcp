"""MHO98 waveform transfer and screenshot tools.

Waveform reads preserve the caller's transfer state on a healthy connection.
Large reads are performed in bounded chunks; binary reads use the session's
validated definite-length-block API and never return an unbounded MCP value.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
import uuid
from typing import Any

from .api import ToolSpec


_SOURCE_VALUES = tuple([f"CHAN{i}" for i in range(1, 5)] + [f"MATH{i}" for i in range(1, 5)])
_MODE_VALUES = frozenset({"NORM", "MAX", "RAW"})
_FORMAT_VALUES = frozenset({"WORD", "BYTE", "ASC"})
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_NORM_MAX_POINTS = 1_000
_MAX_MEMORY_POINTS = 500_000_000
_INLINE_MAX_POINTS = 100_000
_EXPORT_CHUNK_POINTS = 10_000
_BINARY_CHUNK_POINTS = 10_000


def _source(source: Any) -> str:
    if not isinstance(source, str):
        raise ValueError("source must be CH1-CH4 or MATH1-MATH4")
    token = source.strip().upper().replace(" ", "")
    if token.startswith("CHANNEL"):
        token = "CHAN" + token[7:]
    elif token.startswith("CH") and not token.startswith("CHAN"):
        token = "CHAN" + token[2:]
    if token not in _SOURCE_VALUES:
        raise ValueError("source must be CH1-CH4 or MATH1-MATH4")
    return token


def _mode(mode: Any) -> str:
    if not isinstance(mode, str):
        raise ValueError("mode must be NORM, MAX, or RAW")
    token = mode.strip().upper()
    aliases = {"NORMAL": "NORM", "MAXIMUM": "MAX", "RAW": "RAW", "NORM": "NORM", "MAX": "MAX"}
    if token not in aliases:
        raise ValueError("mode must be NORM, MAX, or RAW")
    return aliases[token]


def _points(value: Any, name: str = "points") -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a positive integer")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a positive integer") from None
    if not math.isfinite(number) or not number.is_integer() or number < 1:
        raise ValueError(f"{name} must be a positive integer")
    return int(number)


def _response_int(value: Any, name: str) -> int:
    return _points(value, name)


def _finite(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be finite numeric data") from None
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite numeric data")
    return result


def _format_response(value: Any) -> str:
    token = str(value).strip().upper()
    if token == "ASCII":
        token = "ASC"
    if token not in _FORMAT_VALUES:
        raise ValueError(f"invalid waveform format response from MHO98: {value!r}")
    return token


def _format(value: Any) -> str:
    token = str(value).strip().upper()
    if token in {"ASCII", "ASC"}:
        return "ASC"
    if token in {"BYTE", "WORD"}:
        return token
    raise ValueError("format must be ASC, BYTE, or WORD")


def _state(session: Any) -> dict[str, Any]:
    return {
        "source": _source(session.query(":WAVeform:SOURce?")),
        "mode": _mode(session.query(":WAVeform:MODE?")),
        "format": _format_response(session.query(":WAVeform:FORMat?")),
        "start": _response_int(session.query(":WAVeform:STARt?"), "start"),
        "stop": _response_int(session.query(":WAVeform:STOP?"), "stop"),
        "points": _response_int(session.query(":WAVeform:POINts?"), "points"),
    }


def _validate_range(start: int, points: int, mode: str) -> int:
    end = start + points - 1
    if mode == "NORM" and end > _NORM_MAX_POINTS:
        raise ValueError("NORM waveform range must stay within points 1 through 1000")
    return end


def _encoding_descriptor(
    fmt: str,
    encoding: Any = None,
    word_encoding: Any = None,
    *,
    allow_raw: bool = False,
) -> dict[str, Any]:
    if encoding is not None and word_encoding is not None:
        raise ValueError("provide only one of encoding and word_encoding")
    declared = word_encoding if word_encoding is not None else encoding
    if fmt == "ASC":
        if declared is not None:
            raise ValueError("encoding applies only to BYTE or WORD waveform data")
        return {"format": "ASC", "status": "verified", "interpretation": "ASCII voltage values"}
    if fmt == "BYTE":
        if declared is not None:
            raise ValueError("BYTE waveform data has documented one-byte samples; do not supply WORD encoding")
        return {
            "format": "BYTE",
            "status": "verified",
            "interpretation": "(sample - yorigin - yreference) * yincrement",
        }
    if declared is None:
        if allow_raw:
            return {
                "format": "WORD",
                "status": "raw_only",
                "byte_order": None,
                "signed": None,
                "interpretation": None,
            }
        raise ValueError(
            "interpreting WORD samples requires caller-declared encoding; "
            "provide encoding with byte_order and signedness"
        )
    byte_order: str | None = None
    signed: bool | None = None
    if isinstance(declared, dict):
        byte_order = str(declared.get("byte_order", "")).strip().lower().replace("_", "-")
        signed = declared.get("signed")
        if not isinstance(signed, bool):
            raise ValueError("WORD encoding.signed must be boolean")
    elif isinstance(declared, str):
        token = declared.strip().lower().replace("_", "-").replace(" ", "")
        aliases = {
            "big-endian-unsigned": ("big", False),
            "little-endian-unsigned": ("little", False),
            "big-endian-signed": ("big", True),
            "little-endian-signed": ("little", True),
            ">u2": ("big", False), "<u2": ("little", False),
            ">i2": ("big", True), "<i2": ("little", True),
        }
        if token in aliases:
            byte_order, signed = aliases[token]
    if byte_order in {"be", "bigendian", "big-endian"}:
        byte_order = "big"
    elif byte_order in {"le", "littleendian", "little-endian"}:
        byte_order = "little"
    if byte_order not in {"big", "little"} or not isinstance(signed, bool):
        raise ValueError(
            "WORD encoding must declare byte_order ('big' or 'little') and signed (true or false)"
        )
    return {
        "format": "WORD",
        "status": "caller_declared",
        "byte_order": byte_order,
        "signed": signed,
        "interpretation": "(sample - yorigin - yreference) * yincrement",
        "verified_format": False,
    }


def _parse_preamble(reply: Any) -> dict[str, Any]:
    raw = str(reply).strip()
    fields = [field.strip() for field in raw.split(",")]
    if len(fields) != 10:
        raise ValueError(f"MHO98 waveform preamble must contain 10 fields, got {len(fields)}")
    try:
        format_code = int(fields[0])
        type_code = int(fields[1])
        point_count = int(fields[2])
        average_count = int(fields[3])
    except ValueError:
        raise ValueError(f"invalid integer field in waveform preamble: {reply!r}") from None
    if point_count < 1 or average_count < 1:
        raise ValueError("waveform preamble has invalid point or average count")
    result = {
        "raw": raw,
        "format_code": format_code,
        "type_code": type_code,
        "points": point_count,
        "count": average_count,
        "xincrement": _finite(fields[4], "xincrement"),
        "xorigin": _finite(fields[5], "xorigin"),
        "xreference": _finite(fields[6], "xreference"),
        "yincrement": _finite(fields[7], "yincrement"),
        "yorigin": _finite(fields[8], "yorigin"),
        "yreference": _finite(fields[9], "yreference"),
    }
    return result


def _verify_preamble_format(preamble: dict[str, Any], fmt: str) -> None:
    expected = {"BYTE": 0, "WORD": 1, "ASC": 2}[fmt]
    if preamble["format_code"] != expected:
        raise ValueError(
            f"MHO98 preamble reports format code {preamble['format_code']}; expected {expected} for {fmt}"
        )


def _decode_binary(payload: Any, count: int, fmt: str, preamble: dict[str, Any], encoding: dict[str, Any]) -> tuple[list[int], bytes]:
    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise TypeError("MHO98 binary waveform response must be bytes-like")
    raw = bytes(payload)
    width = 1 if fmt == "BYTE" else 2
    expected_bytes = count * width
    if len(raw) != expected_bytes:
        raise ValueError(
            f"MHO98 returned {len(raw)} waveform bytes; expected exactly {expected_bytes}"
        )
    if fmt == "BYTE":
        samples = list(raw)
    elif encoding.get("byte_order") is None:
        # Raw-file mode validates and preserves the bytes without assigning an
        # undocumented WORD interpretation.
        samples = []
    else:
        samples = [
            int.from_bytes(raw[offset:offset + 2], encoding["byte_order"], signed=encoding["signed"])
            for offset in range(0, len(raw), 2)
        ]
    return samples, raw


def _amplitudes(samples: list[int], preamble: dict[str, Any]) -> list[float]:
    increment = preamble["yincrement"]
    origin = preamble["yorigin"]
    reference = preamble["yreference"]
    return [(sample - origin - reference) * increment for sample in samples]


def _read_chunk(
    session: Any,
    current: dict[str, Any],
    selected: str,
    mode: str,
    fmt: str,
    chunk_start: int,
    chunk: int,
    encoding: dict[str, Any],
) -> tuple[dict[str, Any], list[float], bytes | None]:
    chunk_stop = chunk_start + chunk - 1
    _restore_range(
        session,
        current,
        {**current, "source": selected, "mode": mode, "format": fmt,
         "start": chunk_start, "stop": chunk_stop, "points": chunk},
    )
    preamble = _parse_preamble(session.query(":WAVeform:PREamble?"))
    _verify_preamble_format(preamble, fmt)
    if fmt == "ASC":
        values = _parse_ascii(session.query(":WAVeform:DATA?"), chunk)
        return preamble, values, None
    payload = session.binary_query(":WAVeform:DATA?")
    samples, raw = _decode_binary(payload, chunk, fmt, preamble, encoding)
    return preamble, _amplitudes(samples, preamble), raw


def _parse_ascii(reply: Any, expected: int) -> list[float]:
    text = str(reply).strip()
    if not text:
        raise ValueError("MHO98 returned no ASCII waveform values")
    values = [_finite(item, "waveform value") for item in text.split(",") if item.strip()]
    if len(values) != expected:
        raise ValueError(f"MHO98 returned {len(values)} waveform values; expected {expected}")
    return values


def _times(preamble: dict[str, Any], start: int, count: int) -> list[float]:
    increment = preamble["xincrement"]
    origin = preamble["xorigin"]
    reference = preamble["xreference"]
    return [origin + (start - 1 + index - reference) * increment for index in range(count)]


def _output_path(session: Any, filename: Any, suffix: str) -> Path:
    base = Path(session.output_dir).expanduser().resolve()
    base.mkdir(parents=True, exist_ok=True)
    if filename is None:
        path = base / f"mho98-{suffix}-{uuid.uuid4().hex}{suffix}"
    else:
        if not isinstance(filename, str) or not filename.strip():
            raise ValueError("filename must be a non-empty path relative to output_dir")
        supplied = Path(filename)
        if supplied.is_absolute():
            raise ValueError("filename must be inside output_dir")
        path = (base / supplied).resolve()
        if path.suffix.lower() != suffix:
            path = path.with_name(path.name + suffix)
    try:
        path.relative_to(base)
    except ValueError:
        raise ValueError("filename must be inside output_dir") from None
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _healthy_for_restore(session: Any) -> bool:
    explicit = getattr(session, "is_healthy", None)
    if explicit is not None:
        return bool(explicit() if callable(explicit) else explicit)
    explicit = getattr(session, "healthy", None)
    if explicit is False:
        return False
    transport = getattr(session, "transport", None)
    # A real Session closes and clears transport after a transport fault.  Test
    # doubles without a transport property are treated as healthy.
    if explicit is None and hasattr(session, "transport") and transport is None:
        return False
    return True


def _restore_state(session: Any, saved: dict[str, Any], current: dict[str, Any]) -> None:
    target_source = saved["source"]
    target_mode = saved["mode"]

    # MATH accepts NORM only.  Enter NORM before returning to a MATH source;
    # conversely leave a MATH source before selecting RAW/MAX.
    if target_source.startswith("MATH") and target_mode != "NORM":
        raise ValueError("saved MHO98 state is invalid: MATH source requires NORM mode")
    if target_source.startswith("MATH") and current["mode"] != "NORM":
        session.write(":WAVeform:MODE NORM")
        current["mode"] = "NORM"
    if current["source"].startswith("MATH") and target_mode != "NORM":
        if current["source"] != target_source:
            session.write(f":WAVeform:SOURce {target_source}")
            current["source"] = target_source
    elif current["source"] != target_source and target_mode == "NORM":
        session.write(f":WAVeform:SOURce {target_source}")
        current["source"] = target_source

    if current["mode"] != target_mode:
        session.write(f":WAVeform:MODE {target_mode}")
        current["mode"] = target_mode
    if current["source"] != target_source:
        session.write(f":WAVeform:SOURce {target_source}")
        current["source"] = target_source
    if current["format"] != saved["format"]:
        session.write(f":WAVeform:FORMat {saved['format']}")

    _restore_range(session, current, saved)


def _restore_range(session: Any, current: dict[str, Any], target: dict[str, Any]) -> None:
    if current["points"] != target["points"]:
        session.write(f":WAVeform:POINts {target['points']}")
        current["points"] = target["points"]

    target_start, target_stop = target["start"], target["stop"]
    if target_start > current["stop"]:
        if current["stop"] != target_stop:
            session.write(f":WAVeform:STOP {target_stop}")
        if current["start"] != target_start:
            session.write(f":WAVeform:STARt {target_start}")
    else:
        if current["start"] != target_start:
            session.write(f":WAVeform:STARt {target_start}")
        if current["stop"] != target_stop:
            session.write(f":WAVeform:STOP {target_stop}")
    current["start"] = target_start
    current["stop"] = target_stop


def _set_transfer(session: Any, current: dict[str, Any], target: dict[str, Any]) -> None:
    desired_source, desired_mode = target["source"], target["mode"]
    if desired_source.startswith("MATH") and desired_mode != "NORM":
        raise ValueError("MATH waveform source supports NORM mode only")

    if desired_source.startswith("MATH") and current["mode"] != "NORM":
        session.write(":WAVeform:MODE NORM")
        current["mode"] = "NORM"
    if current["source"].startswith("MATH") and desired_mode != "NORM":
        if current["source"] != desired_source:
            session.write(f":WAVeform:SOURce {desired_source}")
            current["source"] = desired_source
    elif current["source"] != desired_source and desired_mode == "NORM":
        session.write(f":WAVeform:SOURce {desired_source}")
        current["source"] = desired_source
    if current["mode"] != desired_mode:
        session.write(f":WAVeform:MODE {desired_mode}")
        current["mode"] = desired_mode
    if current["source"] != desired_source:
        session.write(f":WAVeform:SOURce {desired_source}")
        current["source"] = desired_source
    if current["format"] != target["format"]:
        session.write(f":WAVeform:FORMat {target['format']}")
        current["format"] = target["format"]
    _restore_range(session, current, target)


def _run_with_restore(session: Any, operation):
    saved = _state(session)
    current = dict(saved)
    primary_error = None
    result = None
    try:
        result = operation(current)
    except Exception as exc:
        primary_error = exc

    restore_error = None
    if _healthy_for_restore(session):
        try:
            _restore_state(session, saved, current)
        except Exception as exc:
            restore_error = exc
    elif primary_error is None:
        restore_error = RuntimeError("waveform transfer state could not be restored: session is unhealthy")

    if primary_error is not None:
        if restore_error is not None:
            raise RuntimeError(f"waveform operation failed ({primary_error}); state restore failed ({restore_error})") from primary_error
        raise primary_error
    if restore_error is not None:
        raise RuntimeError(f"waveform operation succeeded but state restore failed: {restore_error}") from restore_error
    return result


def get_waveform(
    session: Any,
    source: str = "CH1",
    start: int = 1,
    points: int = 1000,
    mode: str = "NORM",
    format: str = "ASC",
    encoding: Any = None,
    word_encoding: Any = None,
    word_byte_order: Any = None,
    word_signed: Any = None,
    filename: str | None = None,
) -> dict[str, Any]:
    """Read a bounded waveform or stream it to a CSV/raw binary file.

    WORD interpretation is intentionally caller-declared because the guide
    specifies its width but not byte order or signedness.
    """
    selected = _source(source)
    selected_mode = _mode(mode)
    selected_format = _format(format)
    first = _points(start, "start")
    count = _points(points)
    if count > _MAX_MEMORY_POINTS:
        raise ValueError("points must not exceed the documented 500000000-point memory limit")
    if word_byte_order is not None or word_signed is not None:
        if word_encoding is not None or encoding is not None:
            raise ValueError("provide one WORD encoding form")
        if word_byte_order is None or word_signed is None:
            raise ValueError("word_byte_order and word_signed must be provided together")
        word_encoding = {"byte_order": word_byte_order, "signed": word_signed}
    encoding_info = _encoding_descriptor(
        selected_format, encoding, word_encoding, allow_raw=filename is not None
    )
    if selected.startswith("MATH") and selected_mode != "NORM":
        raise ValueError("MATH waveform source supports NORM mode only")
    if filename is None and count > _INLINE_MAX_POINTS:
        raise ValueError(
            f"{count} waveform points exceed the inline limit of {_INLINE_MAX_POINTS}; provide filename for streaming"
        )
    output = None
    created = False
    if filename is not None:
        output = _output_path(session, filename, ".csv" if selected_format == "ASC" else ".bin")

    def operation(current):
        nonlocal created
        _validate_range(first, count, selected_mode)
        chunk_size = min(_BINARY_CHUNK_POINTS if selected_format != "ASC" else _EXPORT_CHUNK_POINTS, count)
        target = {
            **current, "source": selected, "mode": selected_mode, "format": selected_format,
            "start": first, "stop": first + chunk_size - 1, "points": chunk_size,
        }
        _set_transfer(session, current, target)

        if output is not None:
            with output.open("xb" if selected_format != "ASC" else "x", newline="" if selected_format == "ASC" else None, encoding=None if selected_format != "ASC" else "utf-8") as handle:
                created = True
                if selected_format == "ASC":
                    writer = csv.writer(handle)
                    writer.writerow(["index", "time", "value"])
                written = 0
                first_preamble = None
                while written < count:
                    chunk = min(chunk_size, count - written)
                    preamble, values, raw = _read_chunk(
                        session, current, selected, selected_mode, selected_format,
                        first + written, chunk, encoding_info,
                    )
                    if first_preamble is None:
                        first_preamble = preamble
                    if selected_format == "ASC":
                        for offset, (time_value, value) in enumerate(
                            zip(_times(preamble, first + written, chunk), values)
                        ):
                            writer.writerow([first + written + offset, f"{time_value:.17g}", f"{value:.17g}"])
                    else:
                        handle.write(raw)
                    written += chunk
            return {
                "path": str(output), "source": selected, "mode": selected_mode,
                "format": selected_format, "start": first, "points": count,
                "bytes": count * (1 if selected_format == "BYTE" else 2) if selected_format != "ASC" else None,
                "preamble": first_preamble,
                "encoding": {**encoding_info, "raw_bytes": selected_format != "ASC"},
            }

        preamble, values, raw = _read_chunk(
            session, current, selected, selected_mode, selected_format, first, count, encoding_info
        )
        result: dict[str, Any] = {
            "source": selected, "mode": selected_mode, "format": selected_format,
            "values": values, "time": _times(preamble, first, count),
            "preamble": preamble, "encoding": encoding_info,
        }
        if raw is not None:
            result["raw_bytes_hex"] = raw.hex()
        return result

    try:
        return _run_with_restore(session, operation)
    except Exception:
        if created and output is not None and output.exists():
            output.unlink()
        raise


def export_waveform_csv(
    session: Any,
    source: str = "CH1",
    mode: str = "NORM",
    start: int = 1,
    points: int = 1000,
    filename: str | None = None,
) -> dict[str, Any]:
    """Stream ASC waveform chunks to a new CSV below ``session.output_dir``."""
    selected = _source(source)
    selected_mode = _mode(mode)
    first = _points(start, "start")
    total = _points(points)
    if total > _MAX_MEMORY_POINTS:
        raise ValueError("points must not exceed the documented 500000000-point memory limit")
    output = _output_path(session, filename, ".csv")
    if selected.startswith("MATH") and selected_mode != "NORM":
        raise ValueError("MATH waveform source supports NORM mode only")
    created = False

    def operation(current):
        nonlocal created
        _validate_range(first, total, selected_mode)
        target = {**current, "source": selected, "mode": selected_mode, "format": "ASC", "start": first, "stop": first + min(total, _EXPORT_CHUNK_POINTS) - 1, "points": min(total, _EXPORT_CHUNK_POINTS)}
        _set_transfer(session, current, target)
        written = 0
        first_preamble = None
        with output.open("x", newline="", encoding="utf-8") as handle:
            created = True
            writer = csv.writer(handle)
            writer.writerow(["index", "time", "value"])
            while written < total:
                chunk = min(_EXPORT_CHUNK_POINTS, total - written)
                chunk_start = first + written
                preamble, values, _ = _read_chunk(
                    session, current, selected, selected_mode, "ASC", chunk_start, chunk,
                    {"format": "ASC", "status": "verified", "interpretation": "ASCII voltage values"},
                )
                if first_preamble is None:
                    first_preamble = preamble
                times = _times(preamble, chunk_start, chunk)
                for offset, (time_value, value) in enumerate(zip(times, values)):
                    writer.writerow([chunk_start + offset, f"{time_value:.17g}", f"{value:.17g}"])
                written += chunk
        return {
            "path": str(output), "source": selected, "mode": selected_mode,
            "start": first, "points": total, "preamble": first_preamble,
            "streamed": total > _EXPORT_CHUNK_POINTS,
        }

    try:
        return _run_with_restore(session, operation)
    except Exception:
        if created and output.exists():
            output.unlink()
        raise


def screenshot(session: Any, filename: str | None = None) -> dict[str, Any]:
    """Save one validated MHO98 PNG screenshot to a new output file."""
    output = _output_path(session, filename, ".png")
    created = False
    try:
        payload = session.binary_query(":DISPlay:DATA? PNG")
        if not isinstance(payload, (bytes, bytearray)) or not bytes(payload).startswith(_PNG_SIGNATURE):
            raise ValueError("MHO98 screenshot response is not a PNG")
        with output.open("xb") as handle:
            created = True
            handle.write(bytes(payload))
    except Exception:
        if created and output.exists():
            output.unlink()
        raise
    return {"path": str(output), "mime_type": "image/png", "bytes": len(payload)}


TOOLS = [
    ToolSpec(
        name="get_waveform",
        description="Read MHO98 NORM/MAX/RAW waveform data as ASC, BYTE, or caller-encoded WORD; large reads stream to a file and transfer settings are restored.",
        input_schema={
            "type": "object",
            "properties": {
                "source": {"type": "string", "enum": [f"CH{i}" for i in range(1, 5)] + [f"MATH{i}" for i in range(1, 5)]},
                "start": {"type": "integer", "minimum": 1},
                "points": {"type": "integer", "minimum": 1, "maximum": _MAX_MEMORY_POINTS},
                "mode": {"type": "string", "enum": ["NORM", "MAX", "RAW"]},
                "format": {"type": "string", "enum": ["ASC", "BYTE", "WORD"]},
                "encoding": {
                    "oneOf": [
                        {"type": "string", "enum": ["big-endian-unsigned", "little-endian-unsigned", "big-endian-signed", "little-endian-signed", ">u2", "<u2", ">i2", "<i2"]},
                        {"type": "object", "properties": {"byte_order": {"type": "string", "enum": ["big", "little"]}, "signed": {"type": "boolean"}}, "required": ["byte_order", "signed"]},
                    ]
                },
                "word_encoding": {"type": "object"},
                "word_byte_order": {"type": "string", "enum": ["big", "little"]},
                "word_signed": {"type": "boolean"},
                "filename": {"type": ["string", "null"]},
            },
            "required": [],
        },
        handler=get_waveform,
        read_only=False,
        needs_session=True,
    ),
    ToolSpec(
        name="export_waveform_csv",
        description="Stream MHO98 ASC waveform data from NORM, MAX, or RAW mode to a new CSV below the output directory; supports the current documented memory depth up to 500M points.",
        input_schema={
            "type": "object",
            "properties": {
                "source": {"type": "string", "enum": [f"CH{i}" for i in range(1, 5)] + [f"MATH{i}" for i in range(1, 5)]},
                "mode": {"type": "string", "enum": ["NORM", "MAX", "RAW"]},
                "start": {"type": "integer", "minimum": 1},
                "points": {"type": "integer", "minimum": 1, "maximum": _MAX_MEMORY_POINTS},
                "filename": {"type": ["string", "null"]},
            },
            "required": [],
        },
        handler=export_waveform_csv,
        read_only=False,
        needs_session=True,
    ),
    ToolSpec(
        name="screenshot",
        description="Save a validated PNG screenshot from MHO98 to a new output file.",
        input_schema={"type": "object", "properties": {"filename": {"type": ["string", "null"]}}, "required": []},
        handler=screenshot,
        read_only=True,
        needs_session=True,
    ),
]
