"""Export the current LangGraph pipeline as Mermaid/Markdown."""
from __future__ import annotations

from html import escape
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.pipeline.graph import get_pipeline_graph


class Command(BaseCommand):
    help = "Export the compiled LangGraph pipeline graph to docs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default="docs",
            help="Directory to write graph files into (default: docs).",
        )
        parser.add_argument(
            "--basename",
            default="pipeline-graph",
            help="Output basename without extension (default: pipeline-graph).",
        )
        parser.add_argument(
            "--png",
            action="store_true",
            help="Also try to render a PNG. This may need extra render dependencies or network access.",
        )

    def handle(self, *args, **options):
        output_dir = Path(options["output_dir"])
        basename = options["basename"]
        output_dir.mkdir(parents=True, exist_ok=True)

        graph = get_pipeline_graph().get_graph()
        mermaid = graph.draw_mermaid()

        mermaid_path = output_dir / f"{basename}.mmd"
        markdown_path = output_dir / f"{basename}.md"
        svg_path = output_dir / f"{basename}.svg"
        mermaid_path.write_text(mermaid, encoding="utf-8")
        svg_path.write_text(_draw_static_svg(), encoding="utf-8")
        markdown_path.write_text(
            "# Current LangGraph Pipeline\n\n"
            "Mermaid source in [pipeline-graph.mmd](./pipeline-graph.mmd) is the canonical graph. "
            "The checked-in SVG is a static preview.\n\n"
            "![Current LangGraph Pipeline](./pipeline-graph.svg)\n\n"
            "```mermaid\n"
            f"{mermaid}\n"
            "```\n",
            encoding="utf-8",
        )

        self.stdout.write(self.style.SUCCESS(f"Mermaid:  {mermaid_path}"))
        self.stdout.write(self.style.SUCCESS(f"Markdown: {markdown_path}"))
        self.stdout.write(self.style.SUCCESS(f"SVG:      {svg_path}"))

        try:
            ascii_graph = graph.draw_ascii()
        except Exception as exc:
            self.stdout.write(f"ASCII skipped: {exc}")
        else:
            ascii_path = output_dir / f"{basename}.txt"
            ascii_path.write_text(ascii_graph, encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"ASCII:    {ascii_path}"))

        if options["png"]:
            png_path = output_dir / f"{basename}.png"
            try:
                png_path.write_bytes(graph.draw_mermaid_png())
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"PNG skipped: {exc}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"PNG:      {png_path}"))


def _draw_static_svg() -> str:
    """Render a lightweight static SVG fallback that needs no Mermaid support."""
    nodes = {
        "__start__": (60, 80, "START"),
        "coordinator": (210, 80, "Coordinator"),
        "research": (360, 80, "Research"),
        "outline": (520, 80, "Outline"),
        "image_research": (670, 80, "Image Search"),
        "writer": (820, 80, "Writer Plan"),
        "section_writer": (970, 80, "Section Writers"),
        "join_draft": (1130, 80, "Join Draft"),
        "editor": (1280, 80, "Editor"),
        "coordinator_router": (1430, 80, "Router"),
        "fact_checker": (1190, 230, "Fact Check"),
        "seo": (1350, 230, "SEO"),
        "qa": (1510, 230, "QA"),
        "__end__": (1670, 80, "END"),
    }
    solid_edges = [
        ("__start__", "coordinator"),
        ("coordinator", "research"),
        ("research", "outline"),
        ("outline", "image_research"),
        ("image_research", "writer"),
        ("section_writer", "join_draft"),
        ("join_draft", "editor"),
        ("editor", "coordinator_router"),
        ("fact_checker", "coordinator_router"),
        ("seo", "coordinator_router"),
        ("qa", "coordinator_router"),
    ]
    dashed_edges = [
        ("writer", "section_writer"),
        ("writer", "join_draft"),
        ("coordinator_router", "research"),
        ("coordinator_router", "outline"),
        ("coordinator_router", "writer"),
        ("coordinator_router", "editor"),
        ("coordinator_router", "fact_checker"),
        ("coordinator_router", "seo"),
        ("coordinator_router", "qa"),
        ("coordinator_router", "__end__"),
    ]

    def center(node_id: str) -> tuple[int, int]:
        x, y, _ = nodes[node_id]
        return x, y

    def edge(source: str, target: str, dashed: bool = False) -> str:
        sx, sy = center(source)
        tx, ty = center(target)
        style = ' stroke-dasharray="7 6"' if dashed else ""
        if source == "coordinator_router" and target in {"research", "outline", "writer", "editor"}:
            mid_y = 350
            return (
                f'<path d="M {sx} {sy+28} C {sx} {mid_y}, {tx} {mid_y}, {tx} {ty+30}" '
                f'class="edge dashed" marker-end="url(#arrow)" />'
            )
        return (
            f'<line x1="{sx+60}" y1="{sy}" x2="{tx-60}" y2="{ty}" '
            f'class="edge{" dashed" if dashed else ""}" marker-end="url(#arrow)"{style} />'
        )

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1760" height="420" viewBox="0 0 1760 420">',
        "<defs>",
        '<marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">',
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="#536170" />',
        "</marker>",
        "</defs>",
        "<style>",
        ".bg{fill:#f8fafc}.node{fill:#eef2ff;stroke:#6875f5;stroke-width:1.4}.terminal{fill:#ecfeff;stroke:#0891b2}.router{fill:#fff7ed;stroke:#ea580c}.edge{fill:none;stroke:#536170;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}.dashed{stroke:#748294;stroke-dasharray:7 6}.label{font:600 14px Arial,sans-serif;fill:#111827;text-anchor:middle;dominant-baseline:middle}.hint{font:12px Arial,sans-serif;fill:#64748b;text-anchor:middle}",
        "</style>",
        '<rect class="bg" width="1760" height="420" rx="18"/>',
        '<text x="880" y="28" class="hint">Solid lines are normal flow. Dashed lines are conditional router branches / fan-out.</text>',
    ]
    parts.extend(edge(s, t) for s, t in solid_edges)
    parts.extend(edge(s, t, dashed=True) for s, t in dashed_edges)

    for node_id, (x, y, label) in nodes.items():
        klass = "node"
        if node_id in {"__start__", "__end__"}:
            klass = "terminal"
        if node_id == "coordinator_router":
            klass = "router"
        parts.append(f'<rect x="{x-62}" y="{y-26}" width="124" height="52" rx="10" class="{klass}"/>')
        parts.append(f'<text x="{x}" y="{y}" class="label">{escape(label)}</text>')

    parts.append("</svg>")
    return "\n".join(parts)
