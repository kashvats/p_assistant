from __future__ import annotations

from typing import Any

from .base import Tool
from living_assistant.integrations.diagram_design import DiagramDesignAdapter


def build_diagram_tools(adapter: DiagramDesignAdapter) -> list[Tool]:
    """Build tool definitions for diagram-design capabilities."""

    def diagram_list_types() -> dict[str, Any]:
        """List all 41 supported diagram types, architectural responsibilities, and guidelines."""
        types = adapter.list_types()
        return {"ok": True, "count": len(types), "types": types}

    def diagram_parse_mermaid(source: str, as_json: bool = True) -> dict[str, Any]:
        """Extract a normalized intermediate representation (IR) from Mermaid text or file."""
        return adapter.extract_mermaid(source_or_path=source, as_json=as_json)

    def diagram_parse_drawio(file_path: str, page: str | None = None, as_json: bool = True) -> dict[str, Any]:
        """Extract a normalized intermediate representation (IR) from a draw.io diagram file."""
        return adapter.extract_drawio(file_path=file_path, page=page, as_json=as_json)

    def diagram_parse_excalidraw(file_path: str, as_json: bool = True) -> dict[str, Any]:
        """Extract a normalized intermediate representation (IR) from an Excalidraw diagram file."""
        return adapter.extract_excalidraw(file_path=file_path, as_json=as_json)

    def diagram_validate(html_or_path: str) -> dict[str, Any]:
        """Validate diagram HTML markup or file against single-file safety and accessibility rules."""
        return adapter.validate_diagram(html_or_path=html_or_path)

    def diagram_generate(
        title: str,
        svg_content: str,
        description: str = "",
        paper_color: str = "#f5f5f5",
        ink_color: str = "#2d3142",
        accent_color: str = "#eb6c36",
    ) -> dict[str, Any]:
        """Generate a compliant, standalone HTML diagram wrapping an accessible SVG with editorial tokens."""
        return adapter.generate_html(
            title=title,
            svg_content=svg_content,
            description=description,
            paper_color=paper_color,
            ink_color=ink_color,
            accent_color=accent_color,
        )

    def diagram_export_svg(html_or_path: str, output_path: str | None = None) -> dict[str, Any]:
        """Extract standalone SVG from a diagram HTML file or markup."""
        return adapter.export_svg(html_or_path=html_or_path, output_path=output_path)

    return [
        Tool(
            "diagram_list_types",
            "List all 41 supported diagram types, architectural patterns, and design references.",
            {"type": "object", "properties": {}},
            diagram_list_types,
        ),
        Tool(
            "diagram_parse_mermaid",
            "Extract a normalized intermediate representation (IR) from Mermaid code or markdown file.",
            {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "Mermaid text content or path to a .mmd/.md file",
                    },
                    "as_json": {
                        "type": "boolean",
                        "default": True,
                        "description": "Return structured JSON IR instead of text digest",
                    },
                },
                "required": ["source"],
            },
            diagram_parse_mermaid,
        ),
        Tool(
            "diagram_parse_drawio",
            "Extract a normalized intermediate representation (IR) from a draw.io diagram file.",
            {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the .drawio file",
                    },
                    "page": {
                        "type": "string",
                        "description": "Page index or page name to extract",
                    },
                    "as_json": {
                        "type": "boolean",
                        "default": True,
                        "description": "Return structured JSON IR instead of text digest",
                    },
                },
                "required": ["file_path"],
            },
            diagram_parse_drawio,
        ),
        Tool(
            "diagram_parse_excalidraw",
            "Extract a normalized intermediate representation (IR) from an Excalidraw scene file.",
            {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the .excalidraw file",
                    },
                    "as_json": {
                        "type": "boolean",
                        "default": True,
                        "description": "Return structured JSON IR instead of text digest",
                    },
                },
                "required": ["file_path"],
            },
            diagram_parse_excalidraw,
        ),
        Tool(
            "diagram_validate",
            "Validate diagram HTML against single-file safety and accessibility rules.",
            {
                "type": "object",
                "properties": {
                    "html_or_path": {
                        "type": "string",
                        "description": "HTML diagram markup or file path",
                    },
                },
                "required": ["html_or_path"],
            },
            diagram_validate,
        ),
        Tool(
            "diagram_generate",
            "Generate a compliant, standalone HTML diagram wrapping an accessible SVG with editorial tokens.",
            {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Title of the diagram"},
                    "svg_content": {"type": "string", "description": "Inner SVG markup or full SVG element"},
                    "description": {"type": "string", "description": "Accessible description of the diagram"},
                    "paper_color": {"type": "string", "default": "#f5f5f5", "description": "Background paper color"},
                    "ink_color": {"type": "string", "default": "#2d3142", "description": "Foreground ink color"},
                    "accent_color": {"type": "string", "default": "#eb6c36", "description": "Accent color for focal elements"},
                },
                "required": ["title", "svg_content"],
            },
            diagram_generate,
        ),
        Tool(
            "diagram_export_svg",
            "Extract standalone SVG from a diagram HTML file or markup.",
            {
                "type": "object",
                "properties": {
                    "html_or_path": {"type": "string", "description": "HTML markup or file path"},
                    "output_path": {"type": "string", "description": "Optional destination file path for .svg output"},
                },
                "required": ["html_or_path"],
            },
            diagram_export_svg,
        ),
    ]
