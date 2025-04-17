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


if __name__ == "__main__":
    mcp.run(transport="sse")  # stdio/sse
