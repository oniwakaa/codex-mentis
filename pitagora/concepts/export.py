"""Concept Graph Visual Exporter.

Exports the DAG of concepts into Mermaid.js flowchart diagrams and Obsidian Canvas JSON format.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from pitagora.concepts.graph import ConceptGraph


def re_sanitize_id(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def export_graph_to_mermaid(graph: ConceptGraph, mastery_dict: dict[str, float] | None = None) -> str:
    """Generates Mermaid flowchart TD markup with colored mastery classes."""
    mastery_dict = mastery_dict or {}
    lines = [
        "flowchart TD",
        "  %% Node Styles",
        "  classDef mastered fill:#2e7d32,stroke:#1b5e20,color:#fff,stroke-width:2px;",
        "  classDef in_progress fill:#f57f17,stroke:#bc5100,color:#fff,stroke-width:2px;",
        "  classDef unstarted fill:#37474f,stroke:#263238,color:#eceff1,stroke-width:1px;",
        "",
    ]

    # Generate Nodes
    for cid, details in graph.graph.items():
        name = details.get("name", cid)
        domain = details.get("domain", "STEM")
        mastery = mastery_dict.get(cid, mastery_dict.get(name, 0.0))

        safe_id = re_sanitize_id(cid)
        lines.append(f'  {safe_id}["{name}<br/><small>{domain} ({mastery*100:.0f}%)</small>"]')

    lines.append("")
    # Generate Edges
    for cid, details in graph.graph.items():
        safe_child = re_sanitize_id(cid)
        for prereq in details.get("prerequisites", []):
            safe_parent = re_sanitize_id(prereq)
            lines.append(f"  {safe_parent} --> {safe_child}")

    lines.append("")
    # Assign Classes
    for cid, details in graph.graph.items():
        name = details.get("name", cid)
        mastery = mastery_dict.get(cid, mastery_dict.get(name, 0.0))
        safe_id = re_sanitize_id(cid)
        if mastery >= 0.8:
            lines.append(f"  class {safe_id} mastered;")
        elif mastery > 0.0:
            lines.append(f"  class {safe_id} in_progress;")
        else:
            lines.append(f"  class {safe_id} unstarted;")

    return "\n".join(lines)


def export_graph_to_canvas(
    graph: ConceptGraph, output_path: str, mastery_dict: dict[str, float] | None = None
) -> int:
    """Exports the Concept Graph to an Obsidian Canvas JSON file."""
    output_path = os.path.expanduser(output_path)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    mastery_dict = mastery_dict or {}

    nodes = []
    edges = []
    col_width = 280
    row_height = 140
    spacing_x = 80
    spacing_y = 60

    # Group by domain for grid positioning
    domains: dict[str, list[str]] = {}
    for cid, details in graph.graph.items():
        dom = details.get("domain", "General")
        domains.setdefault(dom, []).append(cid)

    x_offset = 0
    node_coords: dict[str, tuple[int, int]] = {}

    for dom_idx, (dom_name, cids) in enumerate(domains.items()):
        for r_idx, cid in enumerate(cids):
            details = graph.graph[cid]
            name = details.get("name", cid)
            desc = details.get("description", "")
            mastery = mastery_dict.get(cid, 0.0)

            x = x_offset
            y = r_idx * (row_height + spacing_y)
            node_coords[cid] = (x, y)

            color = "4" if mastery >= 0.8 else "3" if mastery > 0.0 else "1"

            nodes.append({
                "id": cid,
                "type": "text",
                "text": f"## {name}\n**Domain:** {dom_name} | **Mastery:** {mastery*100:.0f}%\n\n{desc[:100]}",
                "x": x,
                "y": y,
                "width": col_width,
                "height": row_height,
                "color": color,
            })
        x_offset += col_width + spacing_x

    edge_id = 1
    for cid, details in graph.graph.items():
        for prereq in details.get("prerequisites", []):
            if prereq in node_coords:
                edges.append({
                    "id": f"edge-{edge_id}",
                    "fromNode": prereq,
                    "fromSide": "right",
                    "toNode": cid,
                    "toSide": "left",
                })
                edge_id += 1

    canvas_data = {"nodes": nodes, "edges": edges}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(canvas_data, f, indent=2)

    return len(nodes)
