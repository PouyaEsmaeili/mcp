import asyncio
import sys
import logging
from contextlib import AsyncExitStack
from typing import Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("client")


class MCPClient:
    def __init__(self) -> None:
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()

    async def connect_to_server(self, server_script_path: str) -> None:
        if not server_script_path.endswith(".py"):
            raise ValueError("Server script must be a .py file")

        server_params = StdioServerParameters(
            command="python",
            args=[server_script_path],
            env=None,
        )

        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.stdio, self.write = stdio_transport

        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )
        initialize_response = await self.session.initialize()
        logger.info(f"Initialized response: {initialize_response}")

    async def list_tools(self) -> None:
        if not self.session:
            raise RuntimeError("Session is not initialized.")
        response = await self.session.list_tools()
        tools = response.tools
        logger.info(f"List of tools: {[tool.name for tool in tools]}")

    async def find_level(self, grade: int) -> None:
        response = await self.session.call_tool("FindLevel", {"grade": grade})
        logger.info(f"Find level response: {response}")

    async def cleanup(self) -> None:
        await self.exit_stack.aclose()


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)

    client = MCPClient()
    try:
        await client.connect_to_server(sys.argv[1])
        await client.list_tools()
        await client.find_level(86)
    except Exception as exc:
        print("Error:", exc)
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
