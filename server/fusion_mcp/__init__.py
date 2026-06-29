"""self-host-fusion360-mcp — the MCP server process.

This package is the external process that Claude (or any MCP client) talks to.
It forwards each tool call to the in-Fusion add-in bridge over HTTP. It can run
natively (stdio) or in a container (streamable-http), and a ``--mock`` mode lets
it run with no Fusion at all (for tests, CI, and demos).
"""

__version__ = "0.5.0"
