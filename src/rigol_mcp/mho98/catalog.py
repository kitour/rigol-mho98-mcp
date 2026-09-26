"""Local SCPI execution index: syntax, argument types and static constraints."""

from __future__ import annotations

from copy import deepcopy
import importlib.resources
import json
from typing import Any

from .api import ToolSpec


_DATA_PACKAGE = "rigol_mcp.mho98.data"
_CATALOG_RESOURCE = "catalog.json"
_CATALOG: dict[str, Any] | None = None
_BY_ID: dict[str, dict[str, Any]] | None = None


def _load() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    global _CATALOG, _BY_ID
    if _CATALOG is None or _BY_ID is None:
        resource = importlib.resources.files(_DATA_PACKAGE).joinpath(_CATALOG_RESOURCE)
        loaded = json.loads(resource.read_text(encoding="utf-8"))
        entries = loaded.get("entries")
        if not isinstance(entries, list) or len(entries) != 654:
            raise RuntimeError("MHO98 catalog must contain exactly 654 entries")
        by_id: dict[str, dict[str, Any]] = {}
        for entry in entries:
            command_id = entry.get("id")
            if not isinstance(command_id, str) or not command_id:
                raise RuntimeError("MHO98 catalog entry has no stable id")
            if command_id in by_id:
                raise RuntimeError(f"duplicate MHO98 catalog id: {command_id}")
            by_id[command_id] = entry
        _CATALOG, _BY_ID = loaded, by_id
    return _CATALOG, _BY_ID


def _validate_page(offset: int, limit: int) -> tuple[int, int]:
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError("offset must be a non-negative integer")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer from 1 through 100")
    return offset, limit


def search_commands(
    query: str = "",
    family: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> dict[str, Any]:
    """Find command syntax by text or family.

    ``family`` accepts a top-level family such as ``bus`` as well as a
    sub-family such as ``bus/can``. Use :func:`describe_command` for argument types.
    """

    if not isinstance(query, str):
        raise ValueError("query must be a string")
    if family is not None and not isinstance(family, str):
        raise ValueError("family must be a string or null")
    offset, limit = _validate_page(offset, limit)
    catalog, _ = _load()
    query_folded = query.strip().casefold()
    family_folded = family.strip().casefold() if family is not None else None

    matched: list[dict[str, Any]] = []
    for entry in catalog["entries"]:
        entry_family = str(entry["family"]).casefold()
        if family_folded and not (
            entry_family == family_folded or entry_family.startswith(family_folded + "/")
        ):
            continue
        if query_folded:
            haystack = json.dumps(entry, ensure_ascii=False).casefold()
            if query_folded not in haystack:
                continue
        matched.append(entry)

    page = matched[offset : offset + limit]
    commands = [
        {
            "id": entry["id"],
            "command": entry["command"],
            "syntax": list(entry["syntax_forms"]),
            "family": entry["family"],
            "summary": entry["command"],
        }
        for entry in page
    ]
    return {
        "query": query,
        "family": family,
        "offset": offset,
        "limit": limit,
        "total": len(matched),
        "commands": commands,
    }


def describe_command(command_id: str) -> dict[str, Any]:
    """Return syntax and execution constraints for one command ID."""

    if not isinstance(command_id, str) or not command_id.strip():
        raise ValueError("id must be a non-empty catalog command id")
    catalog, by_id = _load()
    try:
        result = deepcopy(by_id[command_id.strip()])
    except KeyError:
        raise KeyError(f"unknown MHO98 catalog command id: {command_id}") from None
    return result


def _search_tool(_session: None, **arguments: Any) -> dict[str, Any]:
    return search_commands(
        query=arguments.get("query", ""),
        family=arguments.get("family"),
        offset=arguments.get("offset", 0),
        limit=arguments.get("limit", 20),
    )


def _describe_tool(_session: None, **arguments: Any) -> dict[str, Any]:
    command_id = arguments.get("id", arguments.get("command_id"))
    return describe_command(command_id)


TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="search_commands",
        description="Search MHO98 SCPI syntax and families without opening USB.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "default": ""},
                "family": {"type": ["string", "null"], "default": None},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            },
            "required": [],
        },
        handler=_search_tool,
        read_only=True,
        needs_session=False,
    ),
    ToolSpec(
        name="describe_command",
        description="Return MHO98 command syntax, argument types, static ranges and syntax corrections.",
        input_schema={
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
        handler=_describe_tool,
        read_only=True,
        needs_session=False,
    ),
]
