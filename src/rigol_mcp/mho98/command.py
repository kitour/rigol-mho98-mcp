"""Validated execution of one cataloged MHO98 SCPI command."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from numbers import Real
from typing import Any

from .api import ToolSpec
from .catalog import describe_command


_CONDITIONS = "syntax and static parameter constraints only"
_BINARY_MARKERS = (
    ":DISPlay:DATA",
    ":SAVE:IMAGe:DATA",
    ":SYSTem:SETup",
    ":WAVeform:DATA",
)
_SENSITIVE_MARKERS = (":SAVe:SMB:PASSword",)

# The catalog is intentionally left immutable.  These three entries have a
# source-level metadata mismatch that is safe to correct locally: two source
# Param rows use an abbreviated name while the syntax uses the full name, and
# LIN documents the level semantics but omits its Param row altogether.
_METADATA_EXCEPTIONS: dict[str, dict[str, Any]] = {
    "source-n-mod-pm-internal-function-function-194": {
        "aliases": {"function": "func"},
        "reason": (
            "MHO98_SCPI_AI/commands/generator.md:210-213 uses syntax <function> "
            "and Param <func> with the same discrete waveform range."
        ),
        "source": "commands/generator.md:210-213",
    },
    "trigger-iic-direction-direction-514": {
        "aliases": {"direction": "dir"},
        "reason": (
            "MHO98_SCPI_AI/commands/trigger/i2c.md:64-67 uses syntax "
            "<direction> and Param <dir> with the same READ/WRITe/RWRite range."
        ),
        "source": "commands/trigger/i2c.md:64-67",
    },
    "trigger-lin-level-level-536": {
        "missing_real": "level",
        "reason": (
            "MHO98_SCPI_AI/commands/trigger/lin.md:16-20 defines <level> "
            "as a trigger level in the current amplitude units but has no Param "
            "row or documented numeric range; only finite-real validation is applied."
        ),
        "source": "commands/trigger/lin.md:16-20",
    },
}


def _reject_unsafe_syntax(syntax: str) -> None:
    if ";" in syntax or any(ord(char) < 32 or ord(char) == 127 for char in syntax):
        raise ValueError("catalog syntax contains a command separator or control character")


def _command_kind_guard(entry: dict[str, Any], syntax: str, operation: str) -> None:
    upper = syntax.upper()
    command = str(entry.get("command", "")).upper()
    combined = upper + " " + command
    if any(marker.upper() in combined for marker in _SENSITIVE_MARKERS):
        raise ValueError("SMB password commands are disabled to protect credentials")
    if "HISTOGRAM:RESET" in combined or "HIST:RESET" in combined:
        raise ValueError("HISTogram:RESet is an ambiguous action and cannot be executed")
    binary_bus_data = re.search(r":BUS(?:<N>|\d+):DATA\?", combined) is not None
    if binary_bus_data or any(marker.upper() in combined for marker in _BINARY_MARKERS):
        if ":SYSTEM:SETUP" in combined and operation == "write":
            raise ValueError("SYSTem:SETup binary upload is not supported by this text executor")
        raise ValueError("binary query requires the dedicated binary acquisition path")


def _corrected_syntax(entry: dict[str, Any], syntax: str) -> tuple[str, list[dict[str, Any]]]:
    corrections: list[dict[str, Any]] = []
    for erratum in entry.get("errata", []) or []:
        if not isinstance(erratum, dict):
            continue
        if erratum.get("original") == syntax and isinstance(erratum.get("corrected"), str):
            syntax = erratum["corrected"]
            corrections.append(dict(erratum))
    # Optional command headers such as :TIMebase[:MAIN]:SCALe are emitted in
    # their canonical, explicit form.  Argument optional groups are handled by
    # the syntax parser below.
    syntax = re.sub(r"\[:([A-Za-z][A-Za-z0-9]*)\]", r":\1", syntax)
    return syntax, corrections


def _metadata_corrections(entry: dict[str, Any]) -> list[dict[str, str]]:
    exception = _METADATA_EXCEPTIONS.get(str(entry.get("id", "")))
    if not exception:
        return []
    corrections: list[dict[str, str]] = []
    for syntax_name, catalog_name in (exception.get("aliases", {}) or {}).items():
        corrections.append(
            {
                "kind": "metadata_parameter_alias",
                "original": f"<{syntax_name}>",
                "corrected": f"<{catalog_name}>",
                "reason": str(exception["reason"]),
                "source": str(exception["source"]),
            }
        )
    if exception.get("missing_real"):
        name = str(exception["missing_real"])
        corrections.append(
            {
                "kind": "metadata_parameter_definition",
                "original": f"<{name}>",
                "corrected": "finite Real (range not documented)",
                "reason": str(exception["reason"]),
                "source": str(exception["source"]),
            }
        )
    return corrections


def _parameter_map(entry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    parameters: dict[str, dict[str, Any]] = {}
    for parameter in entry.get("parameters", []) or []:
        name = str(parameter.get("name", "")).strip().strip("<>")
        if name:
            parameters.setdefault(name, parameter)
    exception = _METADATA_EXCEPTIONS.get(str(entry.get("id", "")))
    if exception:
        for syntax_name, catalog_name in (exception.get("aliases", {}) or {}).items():
            if syntax_name not in parameters and catalog_name in parameters:
                parameter = dict(parameters[catalog_name])
                parameter["name"] = f"<{syntax_name}>"
                parameters[syntax_name] = parameter
        missing_name = exception.get("missing_real")
        if missing_name and missing_name not in parameters:
            parameters[str(missing_name)] = {
                "name": f"<{missing_name}>",
                "type": "Real",
                "range": "",
                "_range_missing": True,
            }
    return parameters


def _select_syntax(entry: dict[str, Any], operation: str) -> str:
    if operation == "query":
        query_forms = entry.get("query_syntax") or []
        if isinstance(query_forms, str):
            query_forms = [query_forms]
        if query_forms:
            return query_forms[0]
        # A few catalog entries are query-only and retain their query in the
        # set_syntax field because the source has no separate setter block.
        set_syntax = entry.get("set_syntax")
        if isinstance(set_syntax, str) and "?" in set_syntax.split(" ", 1)[0]:
            return set_syntax
        raise ValueError("catalog entry has no query syntax")
    if operation == "write":
        set_syntax = entry.get("set_syntax")
        if not isinstance(set_syntax, str) or not set_syntax.strip():
            raise ValueError("catalog entry has no setter syntax")
        if "?" in set_syntax.split(" ", 1)[0]:
            raise ValueError("catalog entry is query-only")
        return set_syntax
    raise ValueError(f"unknown command operation: {operation}")


def _index_limit(syntax: str) -> tuple[int, int] | None:
    upper = syntax.upper()
    if "CHAN" in upper or ":BUS" in upper or "MATH" in upper:
        return 1, 4
    if "SOURCE" in upper:
        return 1, 2
    if "REFERENCE" in upper:
        return 1, 10
    if ":LA" in upper and "POD" in upper:
        return 1, 2
    return None


def _substitute_indices(syntax: str, indices: Any) -> tuple[str, dict[str, int]]:
    if indices is None:
        indices = {}
    if not isinstance(indices, dict):
        raise ValueError("indices must be an object")
    placeholders = re.findall(r"<([^>]+)>", syntax)
    index_names = [name for name in placeholders if name == "n"]
    extra = set(indices) - set(index_names)
    if extra:
        raise ValueError(f"unknown index key(s): {sorted(extra)}")
    if index_names:
        if "n" not in indices:
            raise ValueError("syntax requires indices.n")
        value = indices["n"]
        if isinstance(value, bool):
            raise ValueError("indices.n must be an integer")
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            raise ValueError("indices.n must be an integer") from None
        if not math.isfinite(numeric) or not numeric.is_integer():
            raise ValueError("indices.n must be an integer")
        number = int(numeric)
        bounds = _index_limit(syntax)
        if bounds is None:
            raise ValueError("catalog index <n> has no known safe range")
        if not bounds[0] <= number <= bounds[1]:
            raise ValueError(f"indices.n must be from {bounds[0]} through {bounds[1]}")
        syntax = syntax.replace("<n>", str(number))
        return syntax, {"n": number}
    if indices:
        raise ValueError("indices were supplied but this command has no indexed header")
    return syntax, {}


@dataclass(frozen=True)
class _Node:
    kind: str
    value: Any


def _parse_syntax(syntax: str) -> list[_Node]:
    """Parse literal text, placeholders, and nested optional groups."""

    def parse_at(position: int, closing: str | None = None) -> tuple[list[_Node], int]:
        nodes: list[_Node] = []
        literal: list[str] = []
        while position < len(syntax):
            char = syntax[position]
            if closing and char == closing:
                if literal:
                    nodes.append(_Node("text", "".join(literal)))
                return nodes, position + 1
            if char == "[":
                if literal:
                    nodes.append(_Node("text", "".join(literal)))
                    literal = []
                group, position = parse_at(position + 1, "]")
                nodes.append(_Node("group", group))
                continue
            if char == "]":
                raise ValueError("unbalanced optional syntax in catalog entry")
            if char == "<":
                end = syntax.find(">", position + 1)
                if end < 0:
                    raise ValueError("unterminated parameter placeholder in catalog entry")
                if literal:
                    nodes.append(_Node("text", "".join(literal)))
                    literal = []
                name = syntax[position + 1 : end].strip()
                if not name or any(c in name for c in "[]<>;"):
                    raise ValueError(f"invalid parameter placeholder <{name}>")
                nodes.append(_Node("placeholder", name))
                position = end + 1
                continue
            literal.append(char)
            position += 1
        if closing:
            raise ValueError("unbalanced optional syntax in catalog entry")
        if literal:
            nodes.append(_Node("text", "".join(literal)))
        return nodes, position

    nodes, end = parse_at(0)
    if end != len(syntax):
        raise ValueError("could not parse catalog syntax")
    return nodes


def _placeholder_counts(nodes: list[_Node]) -> tuple[int, int]:
    required = total = 0
    for node in nodes:
        if node.kind == "placeholder":
            required += 1
            total += 1
        elif node.kind == "group":
            _group_required, group_total = _placeholder_counts(node.value)
            total += group_total
    return required, total


def _split_top_level(text: str, separator: str = "|") -> list[str]:
    result: list[str] = []
    depth = 0
    start = 0
    for position, char in enumerate(text):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif char == separator and depth == 0:
            result.append(text[start:position])
            start = position + 1
    result.append(text[start:])
    return [part.strip() for part in result if part.strip()]


def _discrete_choices(range_text: str) -> list[str]:
    text = str(range_text).strip()
    if not text.startswith("{") or not text.endswith("}"):
        return []
    body = text[1:-1]
    choices: list[str] = []
    for part in _split_top_level(body):
        match = re.fullmatch(r"([A-Za-z]+)\{(\d+)\.\.(\d+)\}", part)
        if match:
            prefix, first, last = match.group(1), int(match.group(2)), int(match.group(3))
            choices.extend(prefix + str(number) for number in range(first, last + 1))
        else:
            choices.append(part)
    return choices


def _short_form(token: str) -> str:
    match = re.match(r"[A-Z0-9]+", token)
    return match.group(0) if match else token


def _canonical_discrete(value: Any, parameter: dict[str, Any]) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, Real)):
        raise ValueError(f"{parameter['name']} must be a discrete value")
    supplied = str(value).strip()
    if any(ord(char) < 32 or ord(char) == 127 for char in supplied) or ";" in supplied or "," in supplied:
        raise ValueError("discrete argument contains a control character or separator")
    choices = _discrete_choices(parameter.get("range", ""))
    if not choices:
        if str(parameter.get("range", "")).strip().casefold() in {"notes", "notes." , ""}:
            return supplied
        raise ValueError(f"no static discrete range is available for {parameter['name']}")
    for choice in choices:
        if supplied.casefold() in {choice.casefold(), _short_form(choice).casefold()}:
            return choice
        choice_match = re.fullmatch(r"([A-Za-z]+)(\d+)", choice)
        supplied_match = re.fullmatch(r"([A-Za-z]+)(\d+)", supplied)
        if choice_match and supplied_match:
            choice_prefix, choice_number = choice_match.groups()
            supplied_prefix, supplied_number = supplied_match.groups()
            if choice_number == supplied_number:
                canonical_prefix = choice_prefix.upper()
                short_prefix = _short_form(choice_prefix).upper()
                aliases = {canonical_prefix, short_prefix}
                if canonical_prefix.startswith("CHAN"):
                    aliases.update({"CH", "CHANNEL"})
                if supplied_prefix.upper() in aliases:
                    return choice
    raise ValueError(f"{supplied!r} is outside the documented range for {parameter['name']}")


_UNIT_SCALE = {
    "": 1.0,
    "V": 1.0,
    "MV": 1e-3,
    "UV": 1e-6,
    "ΜV": 1e-6,
    "HZ": 1.0,
    "KHZ": 1e3,
    "MHZ": 1e6,
    "S": 1.0,
    "MS": 1e-3,
    "US": 1e-6,
    "NS": 1e-9,
    "A": 1.0,
    "MA": 1e-3,
    "BPS": 1.0,
    "KBPS": 1e3,
    "MBPS": 1e6,
}


def _scalar_from_text(text: str) -> float | None:
    match = re.fullmatch(r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?)\s*([A-Za-zΜμΩ]*)\s*", text)
    if not match:
        return None
    unit = match.group(2).upper().replace("Μ", "Μ").replace("Μ", "Μ")
    multiplier = _UNIT_SCALE.get(unit)
    if multiplier is None:
        return None
    return float(match.group(1)) * multiplier


def _range_bounds(range_text: str) -> tuple[float | None, float | None]:
    # Parse only a complete simple range.  Partial extraction from a dynamic
    # phrase (or from a thousands-separated value) would create a false limit.
    text = str(range_text).strip().replace(",", "")
    while len(text) >= 2 and text[0] == "(" and text[-1] == ")":
        text = text[1:-1].strip()
    match = re.fullmatch(
        r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)\s*[A-Za-zΜμΩ/]*)\s+to\s+"
        r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)\s*[A-Za-zΜμΩ/]*)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None, None
    return _scalar_from_text(match.group(1)), _scalar_from_text(match.group(2))


def _format_argument(value: Any, parameter: dict[str, Any]) -> str:
    type_name = str(parameter.get("type", "")).casefold()
    name = str(parameter.get("name", "<arg>"))
    if "binary" in type_name:
        raise ValueError("binary parameters require a dedicated binary transfer path")
    if "ascii" in type_name or "string" in type_name:
        if not isinstance(value, str):
            raise ValueError(f"{name} must be an ASCII string")
        if any(ord(char) < 32 or ord(char) == 127 for char in value) or ";" in value or "\r" in value or "\n" in value:
            raise ValueError("ASCII string contains a control character or SCPI separator")
        try:
            value.encode("ascii")
        except UnicodeEncodeError:
            raise ValueError("ASCII string must contain ASCII characters only") from None
        return '"' + value.replace('"', '""') + '"'
    if "bool" in type_name:
        if isinstance(value, bool):
            return "1" if value else "0"
        text = str(value).strip().upper()
        if text in {"1", "ON", "TRUE"}:
            return "1"
        if text in {"0", "OFF", "FALSE"}:
            return "0"
        raise ValueError(f"{name} must be a boolean")
    if "integer" in type_name:
        if isinstance(value, bool):
            raise ValueError(f"{name} must be an integer")
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be an integer") from None
        if not math.isfinite(number) or not number.is_integer():
            raise ValueError(f"{name} must be an integer")
        choices = _discrete_choices(parameter.get("range", ""))
        numeric_choices: list[int] = []
        if choices:
            try:
                numeric_choices = [int(choice) for choice in choices]
            except ValueError:
                numeric_choices = []
        if numeric_choices and int(number) not in numeric_choices:
            raise ValueError(f"{name} is outside its documented range")
        low, high = _range_bounds(parameter.get("range", ""))
        if low is not None and (number < low or (high is not None and number > high)):
            raise ValueError(f"{name} is outside its documented range")
        return str(int(number))
    if "real" in type_name:
        if isinstance(value, bool):
            raise ValueError(f"{name} must be a finite real")
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be a finite real") from None
        if not math.isfinite(number):
            raise ValueError(f"{name} must be a finite real")
        low, high = _range_bounds(parameter.get("range", ""))
        if low is not None and number < low or high is not None and number > high:
            raise ValueError(f"{name} is outside its documented range")
        return format(number, ".15g")
    if "discrete" in type_name:
        return _canonical_discrete(value, parameter)
    raise ValueError(f"unsupported catalog parameter type for {name}: {parameter.get('type')!r}")


def _render_nodes(nodes: list[_Node], arguments: list[Any], parameters: dict[str, dict[str, Any]], position: int = 0, optional: bool = False) -> tuple[str, int]:
    output: list[str] = []
    for node in nodes:
        if node.kind == "text":
            output.append(node.value)
        elif node.kind == "placeholder":
            if position >= len(arguments):
                if optional:
                    return "".join(output), position
                raise ValueError("not enough arguments for selected syntax")
            parameter = parameters.get(node.value)
            if parameter is None:
                raise ValueError(f"syntax parameter <{node.value}> is not described by the catalog")
            output.append(_format_argument(arguments[position], parameter))
            position += 1
        elif node.kind == "group":
            if position < len(arguments):
                rendered, position = _render_nodes(node.value, arguments, parameters, position, optional=True)
                output.append(rendered)
        else:
            raise ValueError("unknown syntax node")
    return "".join(output), position


def _unvalidated_constraints(entry: dict[str, Any], syntax: str) -> list[dict[str, str]]:
    parameters = _parameter_map(entry)
    notes: list[dict[str, str]] = []
    seen: set[str] = set()
    for name in re.findall(r"<([^>]+)>", syntax):
        parameter = parameters.get(name)
        if parameter is None or name in seen:
            continue
        seen.add(name)
        type_name = str(parameter.get("type", "")).casefold()
        range_text = str(parameter.get("range", "")).strip()
        if "discrete" in type_name and not _discrete_choices(range_text):
            notes.append({"parameter": f"<{name}>", "reason": "catalog discrete range is Notes or otherwise unspecified"})
        elif parameter.get("_range_missing"):
            notes.append({"parameter": f"<{name}>", "reason": "source documents the parameter semantics but no numeric range"})
        elif ("integer" in type_name or "real" in type_name) and range_text and _range_bounds(range_text) == (None, None):
            if not _discrete_choices(range_text):
                notes.append({"parameter": f"<{name}>", "reason": "catalog range is dynamic or not statically parseable"})
    return notes


def _build_command(entry: dict[str, Any], syntax: str, indices: Any, arguments: Any, operation: str) -> tuple[str, dict[str, int], list[dict[str, Any]], list[dict[str, str]]]:
    if not isinstance(arguments, list):
        raise ValueError("arguments must be an ordered list")
    syntax, corrections = _corrected_syntax(entry, syntax)
    _reject_unsafe_syntax(syntax)
    syntax, used_indices = _substitute_indices(syntax, indices)
    # Reject binary, sensitive, and ambiguous actions before argument rendering
    # so they cannot reach a generic text-parameter path.
    _command_kind_guard(entry, syntax, operation)
    unvalidated = _unvalidated_constraints(entry, syntax)
    nodes = _parse_syntax(syntax)
    required, maximum = _placeholder_counts(nodes)
    if not required <= len(arguments) <= maximum:
        raise ValueError(f"expected {required} to {maximum} arguments, received {len(arguments)}")
    parameters = _parameter_map(entry)
    corrections.extend(_metadata_corrections(entry))
    command, consumed = _render_nodes(nodes, arguments, parameters)
    command = command.strip()
    if consumed != len(arguments):
        raise ValueError("too many arguments for selected syntax")
    if "?" not in command.split(" ", 1)[0] and operation == "query":
        raise ValueError("selected query syntax does not contain a query header")
    if ";" in command or any(ord(char) < 32 or ord(char) == 127 for char in command):
        raise ValueError("generated command contains a separator or control character")
    _command_kind_guard(entry, command, operation)
    return command, used_indices, corrections, unvalidated


def _execute(session: Any, command_id: str, indices: Any, arguments: Any, operation: str) -> dict[str, Any]:
    entry = describe_command(command_id)
    syntax = _select_syntax(entry, operation)
    command, used_indices, corrections, unvalidated = _build_command(entry, syntax, indices, arguments, operation)
    if operation == "query":
        value = session.query(command)
        result: dict[str, Any] = {"id": entry["id"], "operation": "query", "command": command, "value": value}
    else:
        header = command.split(" ", 1)[0].upper()
        if re.fullmatch(r":CHAN(?:NEL)?[1-4]:(?:IMP(?:EDANCE)?|UNIT(?:S)?|PROB(?:E)?)", header):
            raise ValueError(
                "Impedance, measurement units and probe ratio are human-owned. "
                "Use set_channel_input only on an explicit human instruction."
            )
        if re.match(r":CHAN(?:NEL)?[1-4]:", header):
            raise ValueError("Channel writes require the complete set_channel packet; partial catalog channel writes are disabled")
        session.write(command)
        result = {"id": entry["id"], "operation": "write", "command": command, "written": True, "verified": False}
    result["indices"] = used_indices
    result["corrections"] = corrections
    result["static_constraints_unvalidated"] = unvalidated
    result["conditions_checked"] = _CONDITIONS
    return result


def query_command(session: Any, id: str, indices: dict[str, Any] | None = None, arguments: list[Any] | None = None) -> dict[str, Any]:
    return _execute(session, id, {} if indices is None else indices, [] if arguments is None else arguments, "query")


def write_command(session: Any, id: str, indices: dict[str, Any] | None = None, arguments: list[Any] | None = None) -> dict[str, Any]:
    return _execute(session, id, {} if indices is None else indices, [] if arguments is None else arguments, "write")


_COMMAND_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "indices": {"type": "object"},
        "arguments": {"type": "array"},
    },
    "required": ["id"],
}

TOOLS = [
    ToolSpec(
        name="query_command",
        description="Execute one cataloged MHO98 query after syntax and static parameter validation.",
        input_schema=_COMMAND_SCHEMA,
        handler=query_command,
        read_only=False,
        needs_session=True,
    ),
    ToolSpec(
        name="write_command",
        description="Execute one cataloged MHO98 write after local validation. Partial channel writes are blocked: use the complete set_channel packet. Use set_channel_input for impedance/unit/probe only on an explicit human instruction.",
        input_schema=_COMMAND_SCHEMA,
        handler=write_command,
        read_only=False,
        needs_session=True,
    ),
]
