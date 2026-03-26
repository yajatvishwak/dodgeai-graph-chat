#!/usr/bin/env python3
"""Convert Neo4j schema JSON to a Markdown document."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert Neo4j schema JSON into a Markdown summary."
    )
    parser.add_argument(
        "input_json",
        nargs="?",
        default="neo_4j.schema.json",
        help="Path to input schema JSON file (default: neo_4j.schema.json).",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Path to output Markdown file (default: <input_stem>.md).",
    )
    return parser.parse_args()


def format_relation(relation: dict[str, Any], node_name: str) -> str:
    relationship = relation.get("relationship", "UNKNOWN_RELATION")
    direction = relation.get("direction", "out")
    targets = relation.get("target", [])

    if not isinstance(targets, list):
        targets = [str(targets)]
    targets = [str(target) for target in targets if target is not None] or ["UnknownTarget"]

    arrow = "-->" if direction == "out" else "<--"
    return f"`({node_name}) -[:{relationship}]- {arrow} ({', '.join(targets)})`"


def generate_markdown(schema: list[dict[str, Any]], title: str) -> str:
    lines: list[str] = [
        f"# {title}",
        "",
        f"Total nodes: **{len(schema)}**",
        "",
        "## Nodes",
        "",
    ]

    for entry in schema:
        node_name = str(entry.get("node", "UnknownNode"))
        attributes = entry.get("attributes", [])
        relations = entry.get("relations", [])

        if not isinstance(attributes, list):
            attributes = [str(attributes)]
        attributes = [str(attribute) for attribute in attributes]

        if not isinstance(relations, list):
            relations = []

        lines.append(f"### `{node_name}`")
        lines.append("")
        lines.append("**Attributes**")
        if attributes:
            lines.extend([f"- `{attribute}`" for attribute in attributes])
        else:
            lines.append("- _None_")
        lines.append("")

        lines.append("**Relations**")
        if relations:
            lines.extend([f"- {format_relation(relation, node_name)}" for relation in relations])
        else:
            lines.append("- _None_")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    args = parse_args()
    input_path = Path(args.input_json)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    output_path = Path(args.output) if args.output else input_path.with_suffix(".md")

    with input_path.open("r", encoding="utf-8") as f:
        schema = json.load(f)

    if not isinstance(schema, list):
        raise ValueError("Schema JSON must be a list of node objects.")

    title = f"Neo4j Schema Summary ({input_path.name})"
    markdown = generate_markdown(schema, title)

    output_path.write_text(markdown, encoding="utf-8")
    print(f"Wrote Markdown to: {output_path}")


if __name__ == "__main__":
    main()
