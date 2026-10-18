#!/usr/bin/env python3
"""
Quick smoke-test: connects to the grok-studio bridge and lists available
tools.  Pass the bridge URL and token as arguments.

Usage:
    uv run scripts/test_client.py http://localhost:8787/mcp <BRIDGE_TOKEN>
    uv run scripts/test_client.py https://your-domain.ngrok-free.app/mcp <BRIDGE_TOKEN>
"""

import asyncio
import sys

from fastmcp import Client


async def main(url: str, token: str) -> None:
    # Normalise bare domains / missing scheme so the user doesn't have to
    # type the full URL every time.
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    if not url.endswith("/mcp"):
        url = url.rstrip("/") + "/mcp"

    print(f"Connecting to {url} ...")
    # fastmcp.Client wraps the string in BearerAuth, which adds "Bearer " prefix
    # automatically — pass the raw token, not "Bearer <token>".
    client = Client(url, auth=token)

    async with client:
        print("Connected!\n")

        tools = await client.list_tools()
        print(f"Tools ({len(tools)}):")
        for t in tools:
            desc = (t.description or "")[:80]
            print(f"  - {t.name}: {desc}")
        print()

        # Try to call list_roblox_studios if available
        studio_tool = next((t for t in tools if t.name == "list_roblox_studios"), None)
        if studio_tool:
            print("Calling list_roblox_studios ...")
            result = await client.call_tool("list_roblox_studios", {})
            print(f"Result: {result}")
        else:
            print("list_roblox_studios tool not found (Studio may not be connected yet)")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <URL> <TOKEN>")
        print(f"Example: {sys.argv[0]} http://localhost:8787/mcp my-secret-token")
        sys.exit(1)

    asyncio.run(main(sys.argv[1], sys.argv[2]))
