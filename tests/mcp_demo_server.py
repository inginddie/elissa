"""A tiny MCP server for tests: one read-only tool and one that changes something."""
from mcp.server import MCPServer
from mcp.types import ToolAnnotations

server = MCPServer("Demo")
NOTES: list[str] = []


@server.tool(annotations=ToolAnnotations(read_only_hint=True))
def sumar(a: int, b: int) -> str:
    """Suma dos números."""
    return f"{a + b}"


@server.tool(annotations=ToolAnnotations(read_only_hint=False))
def guardar_nota(texto: str) -> str:
    """Guarda una nota."""
    NOTES.append(texto)
    return f"Nota guardada ({len(NOTES)} en total)"


if __name__ == "__main__":
    server.run()
