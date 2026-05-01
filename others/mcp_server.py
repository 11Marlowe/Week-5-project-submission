"""
Lab 3.1 — mcp_server.py
========================
Your task: implement a minimal MCP server that exposes one tool and one
resource via stdio transport so the agent client can connect.

Why one tool?
-------------
The MCP server is the shared file layer in the Week 3 pipeline. The Coder
agent writes files using its own direct write_file and exec_python tools
(carried forward from Week 1). The QA agent needs to read those files without
importing the Coder's tools directly. read_file on this server is the bridge.

Tool to register
----------------
read_file
   - Reads a file from the project_files/ directory.
   - Input schema:  { "path": <string> }  e.g. "utils.py"
   - On success: return file contents as a TextContent block.
   - On error: return TextContent with text starting "ERROR:". Never raise.

Resource to expose
------------------
   URI:         file://project/listing
   Name:        Project Directory Listing
   MIME type:   text/plain
   Content:     newline-separated filenames in project_files/

Steps
-----
1. Create Server("lab3-mcp-server") and assign to `server`.
2. Register list_tools handler -- one Tool with a JSON Schema inputSchema.
3. Register call_tool handler -- dispatch to _read_file or return error.
4. Register list_resources handler -- return the directory listing resource.
5. Register read_resource handler -- return directory listing as a string.
6. Implement _read_file(path) with path traversal protection.

Do NOT change main() at the bottom.
"""

import asyncio
import pathlib
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server
from mcp.server.models import InitializationOptions

# ---------------------------------------------------------------------------
# Constants -- do not change this block
# ---------------------------------------------------------------------------
import os as _os
_here = pathlib.Path(__file__).resolve().parent
_candidate = _here / "project_files"
if not _candidate.exists():
    _candidate = _here.parent / "project_files"
PROJECT_DIR = pathlib.Path(_os.environ.get("LAB31_PROJECT_DIR", str(_candidate)))

# ---------------------------------------------------------------------------
# TODO 1 -- Server instance
# ---------------------------------------------------------------------------
# server = Server("lab3-mcp-server")
server = Server("lab3-mcp-server")


# ---------------------------------------------------------------------------
# TODO 2 -- list_tools handler
# ---------------------------------------------------------------------------
# @server.list_tools()
# async def list_tools() -> list[types.Tool]:
#     inputSchema must use JSON Schema, not Python types:
#     {"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}
@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="read_file",
            description="Reads a file from the project_files/ directory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                },
                "required": ["path"],
            },
        )
    ]


# ---------------------------------------------------------------------------
# TODO 3 -- call_tool handler
# ---------------------------------------------------------------------------
# @server.call_tool()
# async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    # Dispatch to read_file tool
    if name != "read_file":
        return [types.TextContent(type="text", text=f"ERROR: Unknown tool '{name}'")]

    # Validate arguments
    if not isinstance(arguments, dict):
        return [types.TextContent(type="text", text="ERROR: arguments must be an object")]

    path = arguments.get("path")
    if not isinstance(path, str) or not path:
        return [types.TextContent(type="text", text="ERROR: Missing or invalid 'path'")]

    # Delegate to helper (must never raise)
    return await _read_file(path)


# ---------------------------------------------------------------------------
# TODO 4 -- list_resources handler
# ---------------------------------------------------------------------------
# @server.list_resources()
# async def list_resources() -> list[types.Resource]:
#     uri="file://project/listing", mimeType="text/plain", ...
@server.list_resources()
async def list_resources() -> list[types.Resource]:
    return [
        types.Resource(
            uri="file://project/listing",
            name="Project Directory Listing",
            mimeType="text/plain",
            description="newline-separated filenames in project_files/",
        )
    ]


# ---------------------------------------------------------------------------
# TODO 5 -- read_resource handler
# ---------------------------------------------------------------------------
# @server.read_resource()
# async def read_resource(uri: types.AnyUrl) -> str:
@server.read_resource()
async def read_resource(uri: types.AnyUrl) -> str:
    if str(uri) != "file://project/listing":
        return f"ERROR: Unknown resource '{uri}'"

    try:
        if not PROJECT_DIR.exists() or not PROJECT_DIR.is_dir():
            return f"ERROR: Project directory not found: {PROJECT_DIR}"

        filenames = sorted(p.name for p in PROJECT_DIR.iterdir() if p.is_file())
        return "\n".join(filenames)
    except Exception as e:
        return f"ERROR: {e}"


# ---------------------------------------------------------------------------
# TODO 6 -- _read_file helper
# ---------------------------------------------------------------------------
async def _read_file(path: str) -> list[types.TextContent]:
    """Read a file from PROJECT_DIR with path traversal protection.

    - Reject paths with ".." or starting with "/".
    - Resolve and verify path stays inside PROJECT_DIR.
    - Return TextContent with file contents on success.
    - Return TextContent starting "ERROR:" on any error. Never raise.
    """
    try:
        if not isinstance(path, str) or not path:
            return [types.TextContent(type="text", text="ERROR: Invalid path")]

        # Basic path traversal checks requested by spec
        if path.startswith("/"):
            return [types.TextContent(type="text", text="ERROR: Absolute paths are not allowed")]
        if ".." in pathlib.PurePosixPath(path).parts or ".." in pathlib.PureWindowsPath(path).parts:
            return [types.TextContent(type="text", text="ERROR: Path traversal is not allowed")]

        base_dir = PROJECT_DIR.resolve()
        target = (PROJECT_DIR / path).resolve()

        # Ensure resolved path stays within PROJECT_DIR
        try:
            target.relative_to(base_dir)
        except ValueError:
            return [types.TextContent(type="text", text="ERROR: Path escapes project directory")]

        if not target.exists() or not target.is_file():
            return [types.TextContent(type="text", text=f"ERROR: File not found: {path}")]

        content = target.read_text(encoding="utf-8", errors="replace")
        return [types.TextContent(type="text", text=content)]

    except Exception as e:
        return [types.TextContent(type="text", text=f"ERROR: {e}")]


# ---------------------------------------------------------------------------
# Entry point -- do not modify
# ---------------------------------------------------------------------------
async def main() -> None:
    options = server.create_initialization_options()
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options)

if __name__ == "__main__":
    asyncio.run(main())