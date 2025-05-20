# Model Context Protocol (MCP)

Model Context Protocol (MCP) is a protocol designed to establish a communication channel between large language models (LLMs) and external tools or data sources. It follows a client-server architecture and uses JSON-RPC 2.0 for messaging.
Although MCP was introduced only a few months ago by Anthropic, it has quickly gained significant attention in the AI community.
In the sections below, I’ll explain the MCP specification and provide some Python examples.

---

## MCP Server

An MCP server provides three key capabilities to the client:

| Capability | Description |
|------------|-------------|
| **Tool** | A function or service that performs logic (e.g., a calculator), triggers side effects (e.g., modifies the environment), or is CPU-bound. |
| **Resource** | Any type of data such as images, files, etc. |
| **Prompt** | A prompt template that can be used by the client. |

An MCP server can be implemented using either FastMCP or Low-Level APIs.
It supports communication via SSE over HTTP (Server-Sent Events) or stdin.
Use stdin for local communication and SSE for network-based communication. 
Type of communication is called Transport Layer in MCP specification.


**FastMCP**

Suppose we want to implement an MCP server for an English teaching application based on a LLM. 
This MCP server will provide an assessment quiz (Resource), a triage function to determine the learner's level (Tool), and a prompt template (Prompt).


```python
from mcp.server.fastmcp import FastMCP

# You can customize important parameters by passing them to FastMCP.
# In this example, all key parameters are set to their default values,
# but you can modify them according to your needs.
# sse_url = http://0.0.0.0:8000/sse
mcp = FastMCP(
    name="MCPServer",
    debug=True,
    host="0.0.0.0",
    port=8000,
    sse_path="/sse",
    message_path="/messages/",
    log_level="DEBUG",
)


@mcp.resource(
    uri="https://quiz.xyz",
    name="GetQuiz",
    description="Provides a link to an online English level assessment quiz.",
)
def get_quiz() -> str:
    return "Link to online quiz: https://quiz.xyz"


@mcp.tool(
    name="FindLevel",
    description="Determines the student's English level based on their quiz score.",
)
def find_level(grade: int) -> str:
    if grade < 50:
        return "Beginner"
    if grade < 75:
        return "Intermediate"
    return "Expert"


@mcp.prompt(
    name="GetPrompt",
    description="Generates a prompt to ask an LLM to teach English based on the student's level.",
)
def get_prompt(name: str, level: str) -> str:
    return f"Teach {name} English based on this level: {level}."
```

There are different ways to serve FastMCP over SSE: `sse_app`, `run_sse_async` or `run`.
In the first approach, you use a ASGI framework (e.x. Starlette).
The second approach utilizes Python's asyncio.
And the third approach is a mcp's instance built-in function which utilizes `run_sse_async` under the hood.

```python
from starlette.applications import Starlette
from starlette.routing import Mount
import uvicorn


if __name__ == "__main__":
    app = Starlette(debug=True, routes=[
        Mount("/", mcp.sse_app()),
    ])
    uvicorn.run(app)
```

```python
import asyncio

async def main():
    await mcp.run_sse_async()


if __name__ == "__main__":
    asyncio.run(main())
```
```python
# Pass transport=stdio for stdio server
if __name__ == "__main__":
    mcp.run(transport="sse")
```

**Low Level APIs**

Implementing a server using low level APIs takes much time. 
You have to instantiate `Server` class and implement a bunch of methods to list and call all the capabilities. 
There is a detailed guide on how to do this in mcp python-sdk's official repo [here](https://github.com/modelcontextprotocol/python-sdk/blob/main/src/mcp/server/lowlevel/server.py).

---

## MCP Client

Based on how server is exposed there two ways to implement client: `sdio-client` and `sse-client`.

**SSE Client**

Set transport to `sse` in `fastmcp-server.py`.

```python
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
```

**Stdio Client**

You have to pass server script to run stdio client (set transport to `stdio` in `fastmcp-server.py`):

```commandline
python stdio.py fastmcp-server.py
```

```python
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
```

--- 

## Protocol Specification

Three type of messages are exchanged between client and server. 
All messages are formatted using JSON-RPC 2.0 to enable remote procedure calls.

- **Request**: A request that expects a response ([JSONRPCRequest](https://github.com/modelcontextprotocol/python-sdk/blob/babb477dffa33f46cdc886bc885eb1d521151430/src/mcp/types.py#L118)).
- **Response**: A successful (non-error) response to a request ([JSONRPCResponse](https://github.com/modelcontextprotocol/python-sdk/blob/babb477dffa33f46cdc886bc885eb1d521151430/src/mcp/types.py#L134)).
- **Notification**: A notification which does not expect a response ([JSONRPCNotification](https://github.com/modelcontextprotocol/python-sdk/blob/babb477dffa33f46cdc886bc885eb1d521151430/src/mcp/types.py#L127C7-L127C26)).

**Standard JSON-RPC error codes:**

- PARSE_ERROR = -32700
- INVALID_REQUEST = -32600
- METHOD_NOT_FOUND = -32601
- INVALID_PARAMS = -32602
- INTERNAL_ERROR = -32603

### Initialization

Client should initialize a successful connection with the server before messaging.
1. The client sends initialization request ([InitializeRequest](https://github.com/modelcontextprotocol/python-sdk/blob/babb477dffa33f46cdc886bc885eb1d521151430/src/mcp/types.py#L283)).
2. The server responds with its protocol version and capabilities ([InitializeResult](https://github.com/modelcontextprotocol/python-sdk/blob/babb477dffa33f46cdc886bc885eb1d521151430/src/mcp/types.py#L293)).
3. The client sends an initialized notification to acknowledge ([InitializedNotification](https://github.com/modelcontextprotocol/python-sdk/blob/babb477dffa33f46cdc886bc885eb1d521151430/src/mcp/types.py#L304C7-L304C30)).
4. Connection is established.
 
### Discovery

Client can:
- List Tools: [ListToolsRequest](https://github.com/modelcontextprotocol/python-sdk/blob/babb477dffa33f46cdc886bc885eb1d521151430/src/mcp/types.py#L701C7-L701C23)/ [ListToolsResult](https://github.com/modelcontextprotocol/python-sdk/blob/babb477dffa33f46cdc886bc885eb1d521151430/src/mcp/types.py#L720C7-L720C22)
- List Resources: [ListResourcesRequest](https://github.com/modelcontextprotocol/python-sdk/blob/babb477dffa33f46cdc886bc885eb1d521151430/src/mcp/types.py#L356C7-L356C27)/ [ListResourcesResult](https://github.com/modelcontextprotocol/python-sdk/blob/babb477dffa33f46cdc886bc885eb1d521151430/src/mcp/types.py#L414C7-L414C26)
- List Prompts: [ListPromptsRequest](https://github.com/modelcontextprotocol/python-sdk/blob/babb477dffa33f46cdc886bc885eb1d521151430/src/mcp/types.py#L568C7-L568C25)/ [ListPromptsResult](https://github.com/modelcontextprotocol/python-sdk/blob/babb477dffa33f46cdc886bc885eb1d521151430/src/mcp/types.py#L601C7-L601C24)

### Invocation

Client can:

- Call a tool: [CallToolRequest](https://github.com/modelcontextprotocol/python-sdk/blob/babb477dffa33f46cdc886bc885eb1d521151430/src/mcp/types.py#L734)/ [CallToolResult](https://github.com/modelcontextprotocol/python-sdk/blob/babb477dffa33f46cdc886bc885eb1d521151430/src/mcp/types.py#L741C7-L741C21)
- Get a prompt: [GetPromptRequest](https://github.com/modelcontextprotocol/python-sdk/blob/babb477dffa33f46cdc886bc885eb1d521151430/src/mcp/types.py#L617C7-L617C23)/ [GetPromptResult](https://github.com/modelcontextprotocol/python-sdk/blob/babb477dffa33f46cdc886bc885eb1d521151430/src/mcp/types.py#L679)
- Read a resource: [ReadResourceRequest](https://github.com/modelcontextprotocol/python-sdk/blob/babb477dffa33f46cdc886bc885eb1d521151430/src/mcp/types.py#L446C7-L446C26) /[ReadResourceResult](https://github.com/modelcontextprotocol/python-sdk/blob/babb477dffa33f46cdc886bc885eb1d521151430/src/mcp/types.py#L482C7-L482C25)


---

## Gradio + MCP

Exposing an MCP server for your Gradio app is simple and seamless—one of my favorite MCP integrations.

1. Install Gradio with the MCP extra:  
   ```bash
   pip install "gradio[mcp]"
   ```
2. Launch your app with ```mcp_server=True```.
3. The MCP server address will be displayed in the console. You can access MCP documentation at the bottom of your app page.

- For full details, check out the [Gradio MCP server guide](https://www.gradio.app/guides/building-mcp-server-with-gradio).
- Try my demo [Space on Hugging Face](https://huggingface.co/spaces/Pouyae/mcp-gradio).

--- 

## References

0. [Introducing the Model Context Protocol](https://www.anthropic.com/news/model-context-protocol)
1. [MCP Python SDK/ Github](https://github.com/modelcontextprotocol/python-sdk)
2. [Model Context Protocol/ Github](https://github.com/modelcontextprotocol)
2. [Model Context Protocol Documentation](https://modelcontextprotocol.io/introduction)