import asyncio
import logging
from typing import Union
from urllib.parse import urlparse

from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

import mcp.types as types
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.shared.session import RequestResponder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("client")


async def message_handler(
    message: Union[
        RequestResponder[types.ServerRequest, types.ClientResult],
        types.ServerNotification,
        Exception,
    ],
) -> None:
    if isinstance(message, Exception):
        logger.error("Error: %s", message)
        return
    logger.info("Received message from server: %s", message)


async def run_session(
    read_stream: MemoryObjectReceiveStream,
    write_stream: MemoryObjectSendStream,
) -> None:
    async with ClientSession(
        read_stream,
        write_stream,
        message_handler=message_handler,
    ) as session:
        initialize_response = await session.initialize()
        logger.info(f"Initialized response: {initialize_response}")
        tools = await session.list_tools()
        tools = tools.tools
        logger.info(f"List of tools: {[tool.name for tool in tools]}")
        response = await session.call_tool("FindLevel", {"grade": 86})
        logger.info(f"Find level response: {response}")


async def main(command_or_url: str) -> None:
    if urlparse(command_or_url).scheme in ("http", "https"):
        async with sse_client(command_or_url) as streams:
            await run_session(*streams)


if __name__ == "__main__":
    sse_url = "http://0.0.0.0:8000/sse"  # change url
    asyncio.run(main(sse_url))
