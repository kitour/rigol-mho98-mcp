"""Minimal MHO98-only MCP stdio server."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .api import TOOLS as API_TOOLS
from .api import ToolSpec
from .acquire import TOOLS as ACQUIRE_TOOLS
from .autoset import TOOLS as AUTOSET_TOOLS
from .binary import TOOLS as BINARY_TOOLS
from .bode import TOOLS as BODE_TOOLS
from .catalog import TOOLS as CATALOG_TOOLS
from .channel import TOOLS as CHANNEL_TOOLS
from .command import TOOLS as COMMAND_TOOLS
from .counter import TOOLS as COUNTER_TOOLS
from .cursor import TOOLS as CURSOR_TOOLS
from .decode import TOOLS as DECODE_TOOLS
from .display import TOOLS as DISPLAY_TOOLS
from .dvm import TOOLS as DVM_TOOLS
from .fft import TOOLS as FFT_TOOLS
from .generator import TOOLS as GENERATOR_TOOLS
from .histogram import TOOLS as HISTOGRAM_TOOLS
from .logic_analyzer import TOOLS as LOGIC_ANALYZER_TOOLS
from .mask import TOOLS as MASK_TOOLS
from .math_operations import TOOLS as MATH_TOOLS
from .measure import TOOLS as MEASURE_TOOLS
from .measurement_settings import TOOLS as MEASUREMENT_SETTINGS_TOOLS
from .record import TOOLS as RECORD_TOOLS
from .reference import TOOLS as REFERENCE_TOOLS
from .recovery import TOOLS as RECOVERY_TOOLS
from .search import TOOLS as SEARCH_TOOLS
from .session import Session
from .storage import TOOLS as STORAGE_TOOLS
from .system import TOOLS as SYSTEM_TOOLS
from .timebase import TOOLS as TIMEBASE_TOOLS
from .trigger import TOOLS as TRIGGER_TOOLS
from .waveform import TOOLS as WAVEFORM_TOOLS


# Keep feature registration explicit.  Later feature modules can be added here
# without changing the dispatch contract.
TOOLS: list[ToolSpec] = [
    *API_TOOLS,
    *BINARY_TOOLS,
    *CATALOG_TOOLS,
    *COMMAND_TOOLS,
    *COUNTER_TOOLS,
    *ACQUIRE_TOOLS,
    *CHANNEL_TOOLS,
    *MEASURE_TOOLS,
    *TIMEBASE_TOOLS,
    *TRIGGER_TOOLS,
    *WAVEFORM_TOOLS,
    *RECOVERY_TOOLS,
    *DECODE_TOOLS,
    *FFT_TOOLS,
    *GENERATOR_TOOLS,
    *LOGIC_ANALYZER_TOOLS,
    *BODE_TOOLS,
    *CURSOR_TOOLS,
    *DVM_TOOLS,
    *HISTOGRAM_TOOLS,
    *MASK_TOOLS,
    *MATH_TOOLS,
    *MEASUREMENT_SETTINGS_TOOLS,
    *RECORD_TOOLS,
    *REFERENCE_TOOLS,
    *SEARCH_TOOLS,
    *STORAGE_TOOLS,
    *AUTOSET_TOOLS,
    *DISPLAY_TOOLS,
    *SYSTEM_TOOLS,
]
_TOOL_LOCK = asyncio.Lock()
server = Server("rigol-mho98")


def _tool_map() -> dict[str, ToolSpec]:
    result: dict[str, ToolSpec] = {}
    for spec in TOOLS:
        if spec.name in result:
            raise RuntimeError(f"duplicate MHO98 tool name: {spec.name}")
        result[spec.name] = spec
    return result


def _content_result(result: Any) -> list[Any]:
    if isinstance(result, list) and all(
        hasattr(item, "type") and getattr(item, "type", None) in {"text", "image", "audio"}
        for item in result
    ):
        return result
    if isinstance(result, str):
        text = result
    elif isinstance(result, (dict, list, int, float, bool)) or result is None:
        text = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    else:
        raise TypeError(f"tool returned a non-JSON value: {type(result).__name__}")
    return [types.TextContent(type="text", text=text)]


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name=spec.name,
            description=spec.description,
            inputSchema=dict(spec.input_schema),
            annotations=types.ToolAnnotations(
                readOnlyHint=spec.read_only,
                destructiveHint=not spec.read_only,
                idempotentHint=False,
                openWorldHint=False,
            ),
        )
        for spec in TOOLS
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[Any]:
    spec = _tool_map().get(name)
    if spec is None:
        raise ValueError(f"Unknown MHO98 tool: {name}")

    # The async lock covers the complete synchronous handler.  The session's
    # transaction adds the process and interprocess lock for separate workers.
    async with _TOOL_LOCK:
        session = Session() if spec.needs_session else None
        try:
            if session is None:
                result = spec.handler(None, **(arguments or {}))
            else:
                with session.transaction():
                    result = spec.handler(session, **(arguments or {}))
            return _content_result(result)
        finally:
            if session is not None:
                session.close()


async def _run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
