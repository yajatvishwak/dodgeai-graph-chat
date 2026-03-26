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
        help="Path to output Markdown file (default: <input_stem>.md or .compact.md).",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Emit compact Markdown (table + ASCII relationships).",
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


def _sort_compact_attributes(node_name: str, attributes: list[str]) -> list[str]:
    if node_name == "Address":
        preferred = [
            "addressId",
            "street",
            "city",
            "region",
            "country",
            "postalCode",
            "validFrom",
            "validTo",
        ]
        seen = set(preferred)
        ordered = [a for a in preferred if a in attributes]
        ordered.extend(sorted(a for a in attributes if a not in seen))
        return ordered
    id_like = sorted(
        a for a in attributes if a.endswith("Id") or a.endswith("Uid")
    )
    rest = sorted(a for a in attributes if a not in id_like)
    return id_like + rest


def _normalized_edges(schema: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    edges: set[tuple[str, str, str]] = set()
    for entry in schema:
        node_name = str(entry.get("node", "UnknownNode"))
        for relation in entry.get("relations", []) or []:
            if not isinstance(relation, dict):
                continue
            rel_type = str(relation.get("relationship", "UNKNOWN"))
            direction = relation.get("direction", "out")
            targets = relation.get("target", [])
            if not isinstance(targets, list):
                targets = [targets]
            for target in targets:
                if target is None:
                    continue
                tgt = str(target)
                if direction == "out":
                    edges.add((node_name, rel_type, tgt))
                else:
                    edges.add((tgt, rel_type, node_name))
    return sorted(edges)


def generate_compact_markdown(schema: list[dict[str, Any]]) -> str:
    n = len(schema)
    rows: list[tuple[str, str]] = []
    for entry in sorted(schema, key=lambda e: str(e.get("node", ""))):
        name = str(entry.get("node", "UnknownNode"))
        attrs = entry.get("attributes", [])
        if not isinstance(attrs, list):
            attrs = [str(attrs)]
        attrs = [str(a) for a in attrs]
        attr_str = ", ".join(_sort_compact_attributes(name, attrs))
        rows.append((name, attr_str))

    lines: list[str] = [
        f"# Neo4j Schema ({n} Nodes)",
        "",
        "## Nodes & Attributes",
        "",
        "| Node | Attributes |",
        "|------|-----------|",
    ]
    for name, attr_str in rows:
        escaped = attr_str.replace("|", "\\|")
        lines.append(f"| `{name}` | {escaped} |")
    lines.extend(["", "## Relationships", "```"])

    edges = _normalized_edges(schema)
    if not edges:
        lines.append("(no relationships)")
    else:
        max_src = max(len(s) for s, _, _ in edges)
        left_segments = [f"{s:<{max_src}} -[:{r}]" for s, r, _ in edges]
        max_left = max(len(seg) for seg in left_segments)
        min_dashes = 3

        for (src, rel, tgt), left in zip(edges, left_segments):
            dashes = max(min_dashes, max_left - len(left) + min_dashes)
            lines.append(f"{left}{'-' * dashes}> {tgt}")

    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    input_path = Path(args.input_json)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if args.output:
        output_path = Path(args.output)
    elif args.compact:
        output_path = input_path.with_suffix(".compact.md")
    else:
        output_path = input_path.with_suffix(".md")

    with input_path.open("r", encoding="utf-8") as f:
        schema = json.load(f)

    if not isinstance(schema, list):
        raise ValueError("Schema JSON must be a list of node objects.")

    if args.compact:
        markdown = generate_compact_markdown(schema)
    else:
        title = f"Neo4j Schema Summary ({input_path.name})"
        markdown = generate_markdown(schema, title)

    output_path.write_text(markdown, encoding="utf-8")
    print(f"Wrote Markdown to: {output_path}")


if __name__ == "__main__":
    main()
