"""Entrypoint for python -m src.mcp."""
from src.mcp.server import run_stdio_server

if __name__ == "__main__":
    run_stdio_server()
