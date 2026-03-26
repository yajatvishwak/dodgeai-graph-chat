from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

_DATA_CREATION_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_ROOT = _DATA_CREATION_DIR / "data"
DEFAULT_OUTPUT_PATH = _DATA_CREATION_DIR / "schema.dbml"

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$"
)
SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass
class ColumnStats:
    present_rows: int = 0
    null_rows: int = 0
    saw_bool: bool = False
    saw_int: bool = False
    saw_float: bool = False
    saw_timestamp: bool = False
    saw_date: bool = False
    saw_text: bool = False
    saw_json: bool = False


@dataclass
class TableStats:
    name: str
    row_count: int = 0
    malformed_lines: int = 0
    columns: dict[str, ColumnStats] = field(default_factory=lambda: defaultdict(ColumnStats))


def infer_string_temporal_type(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None
    if DATE_RE.fullmatch(text):
        try:
            datetime.strptime(text, "%Y-%m-%d")
            return "date"
        except ValueError:
            return None
    if TIMESTAMP_RE.fullmatch(text):
        normalized = text.replace("Z", "+00:00")
        try:
            datetime.fromisoformat(normalized.replace("t", "T"))
            return "timestamp"
        except ValueError:
            return None
    return None


def json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "list"
    return "unknown"


def flatten_record(value: Any, prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}

    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(child, dict):
                if child:
                    flat.update(flatten_record(child, path))
                else:
                    flat[path] = {}
            elif isinstance(child, list):
                if not child:
                    flat[path] = []
                    continue

                scalar_items: list[Any] = []
                has_complex = False
                for item in child:
                    if isinstance(item, dict):
                        has_complex = True
                        flat.update(flatten_record(item, f"{path}[]"))
                    elif isinstance(item, list):
                        has_complex = True
                        flat[f"{path}[]"] = item
                    else:
                        scalar_items.append(item)

                if scalar_items:
                    flat[path] = scalar_items
                if has_complex and f"{path}[]" not in flat:
                    flat[f"{path}[]"] = child
            else:
                flat[path] = child
        return flat

    flat[prefix or "(root)"] = value
    return flat


def collect_value_stats(col_stats: ColumnStats, value: Any) -> None:
    col_stats.present_rows += 1
    if value is None:
        col_stats.null_rows += 1
        return

    value_kind = json_type(value)
    if value_kind in {"object", "list", "unknown"}:
        col_stats.saw_json = True
        return
    if value_kind == "bool":
        col_stats.saw_bool = True
        return
    if value_kind == "int":
        col_stats.saw_int = True
        return
    if value_kind == "float":
        col_stats.saw_float = True
        return
    if value_kind == "str":
        temporal = infer_string_temporal_type(value)
        if temporal == "timestamp":
            col_stats.saw_timestamp = True
        elif temporal == "date":
            col_stats.saw_date = True
        else:
            col_stats.saw_text = True


def resolve_dbml_type(col_stats: ColumnStats) -> str:
    if col_stats.saw_json:
        return "json"
    if col_stats.saw_text:
        return "text"

    saw_numeric = col_stats.saw_int or col_stats.saw_float
    saw_temporal = col_stats.saw_timestamp or col_stats.saw_date

    if saw_numeric and not (col_stats.saw_bool or saw_temporal):
        if col_stats.saw_float:
            return "float"
        return "int"
    if col_stats.saw_bool and not (saw_numeric or saw_temporal):
        return "boolean"
    if saw_temporal and not (col_stats.saw_bool or saw_numeric):
        if col_stats.saw_timestamp:
            return "timestamp"
        return "date"
    if col_stats.saw_bool and col_stats.saw_int and not (col_stats.saw_float or saw_temporal):
        return "int"
    return "text"


def is_nullable(col_stats: ColumnStats, table_rows: int) -> bool:
    return col_stats.null_rows > 0 or col_stats.present_rows < table_rows


def discover_jsonl_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.jsonl"))


def table_name_for_path(path: Path, input_root: Path) -> str:
    relative = path.relative_to(input_root)
    if not relative.parts:
        return path.stem
    if relative.parts[0] in {"cleaned", "raw"} and len(relative.parts) > 1:
        return relative.parts[1]
    return relative.parts[0]


def quote_identifier(identifier: str) -> str:
    if SAFE_IDENTIFIER_RE.fullmatch(identifier):
        return identifier
    escaped = identifier.replace('"', r"\"")
    return f'"{escaped}"'


def process_file(path: Path, table: TableStats) -> None:
    with path.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                table.malformed_lines += 1
                continue
            if not isinstance(parsed, dict):
                table.malformed_lines += 1
                continue

            flat = flatten_record(parsed)
            table.row_count += 1
            for key, value in flat.items():
                collect_value_stats(table.columns[key], value)


def render_dbml(tables: dict[str, TableStats]) -> str:
    lines: list[str] = []
    lines.append("// Generated by data_creation/generate_dbml_schema.py")
    lines.append("")
    for table_name in sorted(tables):
        table = tables[table_name]
        lines.append(f"Table {quote_identifier(table.name)} {{")
        for column_name in sorted(table.columns):
            stats = table.columns[column_name]
            col_type = resolve_dbml_type(stats)
            col_name = quote_identifier(column_name)
            notes = "[not null]" if not is_nullable(stats, table.row_count) else ""
            if notes:
                lines.append(f"  {col_name} {col_type} {notes}")
            else:
                lines.append(f"  {col_name} {col_type}")
        lines.append("}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_schema(input_root: Path) -> tuple[dict[str, TableStats], int]:
    files = discover_jsonl_files(input_root)
    tables: dict[str, TableStats] = {}

    for file_path in files:
        table_name = table_name_for_path(file_path, input_root)
        if table_name not in tables:
            tables[table_name] = TableStats(name=table_name)
        process_file(file_path, tables[table_name])

    return tables, len(files)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Infer DBML schema from JSONL files by flattening nested JSON."
    )
    parser.add_argument(
        "--input-root",
        type=Path,
        default=DEFAULT_INPUT_ROOT,
        help="Root folder to recursively scan for JSONL files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="DBML output file path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_root = args.input_root.resolve()
    output_path = args.output.resolve()

    if not input_root.exists():
        raise FileNotFoundError(f"Input root not found: {input_root}")

    tables, file_count = build_schema(input_root)
    dbml = render_dbml(tables)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(dbml, encoding="utf-8")

    total_columns = sum(len(table.columns) for table in tables.values())
    total_rows = sum(table.row_count for table in tables.values())
    total_malformed = sum(table.malformed_lines for table in tables.values())

    print(f"Input root: {input_root}")
    print(f"Output file: {output_path}")
    print(f"Files processed: {file_count}")
    print(f"Tables discovered: {len(tables)}")
    print(f"Rows processed: {total_rows}")
    print(f"Columns inferred: {total_columns}")
    print(f"Malformed lines skipped: {total_malformed}")


if __name__ == "__main__":
    main()
