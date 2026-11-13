"""Local stdio MCP adapter. Tool signatures derive from the application contract."""
from __future__ import annotations

import argparse
import inspect
from pathlib import Path
from typing import Annotated, get_type_hints

from scl.model import find_root
from scl.service import ModelService, OPERATIONS, READ_OPERATIONS, execute


def create_server(root: Path):
    try:
        from mcp.server import MCPServer
        from mcp.types import ToolAnnotations
        from pydantic import BaseModel, WithJsonSchema
    except ImportError as exc:
        raise RuntimeError("Install SCL's MCP extra: python -m pip install '.[mcp]' (MCP SDK 2.x).") from exc

    class Response(BaseModel):
        status: str
        model_revision: str | None
        findings: list[dict]
        retryable: bool
        data: dict

    server = MCPServer("SCL IOMR")
    for operation, description in OPERATIONS.items():
        method = getattr(ModelService, "_" + operation)
        hints = get_type_hints(method)
        signature = inspect.signature(method)
        from scl.contracts import input_schema
        schemas = input_schema(method)["properties"]
        parameters = [p.replace(annotation=Annotated[hints.get(p.name, dict), WithJsonSchema(schemas[p.name])])
                      for p in signature.parameters.values() if p.name != "self"]

        def make_handler(name, params):
            def handler(**kwargs):
                return Response(**execute(root, name, **kwargs))
            handler.__name__ = "scl_" + name
            handler.__doc__ = OPERATIONS[name]
            handler.__signature__ = inspect.Signature(params, return_annotation=Response)
            handler.__annotations__ = {p.name: p.annotation for p in params if p.annotation != inspect.Parameter.empty}
            handler.__annotations__["return"] = Response
            return handler

        server.add_tool(make_handler(operation, parameters), name="scl_" + operation, description=description,
                        annotations=ToolAnnotations(readOnlyHint=operation in READ_OPERATIONS,
                                                    destructiveHint=operation == "commit_change",
                                                    openWorldHint=False), structured_output=True)
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(prog="scl-mcp")
    parser.add_argument("--root", type=Path)
    args = parser.parse_args(argv)
    create_server(args.root.resolve() if args.root else find_root()).run(transport="stdio")


if __name__ == "__main__":
    main()
