"""MHO98-only MCP foundation.

The package deliberately has its own session and stdio server.  It does not
reuse the legacy server's cached connection, retry policy, or state clearing.
"""

from .api import TOOLS, ToolSpec
from .session import MHO98IdentityError, SCPIError, Session

__all__ = [
    "MHO98IdentityError",
    "SCPIError",
    "Session",
    "TOOLS",
    "ToolSpec",
]
