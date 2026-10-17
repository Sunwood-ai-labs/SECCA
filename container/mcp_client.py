import argparse
import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def request(tool=None, arguments=None):
    server = StdioServerParameters(
        command="/opt/freecad-mcp/.venv/bin/freecad-mcp",
        args=["--host", "127.0.0.1", "--freecadcmd", "/usr/bin/freecadcmd"],
    )
    async with stdio_client(server) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            if tool is None:
                return (await session.list_tools()).model_dump(mode="json")
            return (await session.call_tool(tool, arguments or {})).model_dump(mode="json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["list", "call"])
    parser.add_argument("tool", nargs="?")
    parser.add_argument("--arguments", default="{}")
    args = parser.parse_args()
    if args.action == "call" and not args.tool:
        parser.error("call requires a tool name")
    payload = json.loads(args.arguments)
    if not isinstance(payload, dict):
        parser.error("arguments must be a JSON object")
    result = asyncio.run(request(args.tool if args.action == "call" else None, payload))
    print(json.dumps(result))
    return int(bool(result.get("isError", False)))


if __name__ == "__main__":
    raise SystemExit(main())

