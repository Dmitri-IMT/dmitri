from __future__ import annotations

import ast
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[2] / "src" / "agent"


def _forbidden_nodes(tree: ast.AST) -> list[str]:
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                if node.value.id == "socket" and node.attr in {
                    "bind",
                    "listen",
                    "create_server",
                }:
                    hits.append(f"socket.{node.attr}")
                if node.value.id == "asyncio" and node.attr == "start_server":
                    hits.append(f"asyncio.{node.attr}")
            if node.attr == "ModbusTcpServer":
                hits.append("ModbusTcpServer attribute")
        elif isinstance(node, ast.Name) and node.id == "ModbusTcpServer":
            hits.append("ModbusTcpServer name")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in {"socketserver", "uvicorn"}:
                    hits.append(f"import {alias.name}")
                if alias.name == "http.server":
                    hits.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            root = node.module.split(".")[0]
            if root in {"socketserver", "uvicorn"}:
                hits.append(f"from {node.module}")
            if node.module == "http.server":
                hits.append(f"from {node.module}")
            for alias in node.names:
                if alias.name == "ModbusTcpServer":
                    hits.append(f"from {node.module} import {alias.name}")
    return hits


def test_agent_tree_has_no_listening_socket_patterns() -> None:
    violations: list[str] = []
    for path in sorted(AGENT_SRC.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for hit in _forbidden_nodes(tree):
            violations.append(f"{path.relative_to(AGENT_SRC.parent.parent)}: {hit}")
    assert violations == []
