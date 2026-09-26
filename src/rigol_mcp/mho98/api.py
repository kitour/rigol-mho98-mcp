"""Small, typed MCP feature surface for the MHO98 server.

Feature modules export a ``TOOLS`` list containing :class:`ToolSpec` values.
Keeping the handler contract synchronous makes the session's transaction
boundary explicit and lets the stdio server serialize the complete call.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, TYPE_CHECKING

if TYPE_CHECKING:
    from .session import Session


JSONValue = dict[str, Any] | list[Any] | str | int | float | bool | None
HandlerResult = JSONValue | list[Any]
Handler = Callable[..., HandlerResult]


@dataclass(frozen=True)
class ToolSpec:
    """Description and implementation of one MHO98 MCP tool."""

    name: str
    description: str
    input_schema: Mapping[str, Any]
    handler: Callable[..., HandlerResult]
    read_only: bool = True
    needs_session: bool = True


def _idn(session: Session, **_: Any) -> dict[str, str]:
    """Return the validated MHO98 identity."""

    return {"idn": session.idn()}


TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="idn",
        description="Identify the connected instrument and require an MHO98 response.",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=_idn,
        read_only=True,
        needs_session=True,
    ),
]
