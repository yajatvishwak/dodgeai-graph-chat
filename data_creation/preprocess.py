from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

_DATA_CREATION_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _DATA_CREATION_DIR.parent

# Input: JSONL under data_creation/sap-o2c-data (cwd-independent).
INPUT_ROOT = _DATA_CREATION_DIR / "sap-o2c-data"
# Outputs live under repo data/ per project layout.
OUTPUT_ROOT = _REPO_ROOT / "data" / "cleaned"
REPORT_PATH = _REPO_ROOT / "data" / "preprocess_summary.md"
UTC = timezone.utc
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[Tt ].*)?$")


@dataclass
class TableStats:
    table_name: str
    file_count: int = 0
    record_count: int = 0
    malformed_lines: int = 0
    normalized_string_timestamps: int = 0
    flattened_nested_timestamp_objects: int = 0
    non_timestamp_nested_paths: Counter[str] = field(default_factory=Counter)
    column_types: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))


def infer_type_label(value: Any) -> str:
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
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    return "unknown"


def is_timestamp_object(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    keys = set(value.keys())
    return keys <= {"hours", "minutes", "seconds"} and bool(keys)


def parse_to_utc(value: str) -> datetime | None:
    text = value.strip()
    if not text or not ISO_DATE_RE.match(text):
        return None

    normalized = text.replace("Z", "+00:00")
    parsed: datetime | date
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            parsed = date.fromisoformat(normalized)
        except ValueError:
            return None

    if isinstance(parsed, date) and not isinstance(parsed, datetime):
        parsed = datetime(parsed.year, parsed.month, parsed.day, tzinfo=UTC)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    else:
        parsed = parsed.astimezone(UTC)
    return parsed


def format_utc(dt: datetime) -> str:
    return dt.astimezone(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def maybe_normalize_timestamp_string(value: Any, stats: TableStats) -> Any:
    if not isinstance(value, str):
        return value

    parsed = parse_to_utc(value)
    if parsed is None:
        return value

    stats.normalized_string_timestamps += 1
    return format_utc(parsed)


def timestamp_from_time_object(
    key: str, value: dict[str, Any], container: dict[str, Any]
) -> str | None:
    hours = int(value.get("hours", 0))
    minutes = int(value.get("minutes", 0))
    seconds = int(value.get("seconds", 0))

    date_candidates = []
    if key.endswith("Time"):
        date_candidates.append(f"{key[:-4]}Date")
        date_candidates.append(f"{key[:-4]}DateTime")
    date_candidates.extend([f"{key}Date", f"{key}DateTime"])

    source_date: datetime | None = None
    for candidate in date_candidates:
        candidate_value = container.get(candidate)
        if isinstance(candidate_value, str):
            parsed = parse_to_utc(candidate_value)
            if parsed is not None:
                source_date = parsed
                break

    if source_date is None:
        if any((hours, minutes, seconds)):
            source_date = datetime(1970, 1, 1, tzinfo=UTC)
        else:
            return None

    combined = datetime(
        source_date.year,
        source_date.month,
        source_date.day,
        hours,
        minutes,
        seconds,
        tzinfo=UTC,
    )
    return format_utc(combined)


def normalize_value(
    value: Any, key_path: str, stats: TableStats, container: dict[str, Any] | None, key: str
) -> Any:
    if is_timestamp_object(value):
        stats.flattened_nested_timestamp_objects += 1
        assert container is not None
        return timestamp_from_time_object(key, value, container)

    if isinstance(value, dict):
        stats.non_timestamp_nested_paths[key_path] += 1
        return normalize_dict(value, key_path, stats)

    if isinstance(value, list):
        stats.non_timestamp_nested_paths[f"{key_path}[]"] += 1
        normalized_items = []
        for item in value:
            if isinstance(item, dict):
                stats.non_timestamp_nested_paths[f"{key_path}[]"] += 1
                normalized_items.append(normalize_dict(item, f"{key_path}[]", stats))
            elif isinstance(item, list):
                stats.non_timestamp_nested_paths[f"{key_path}[][]"] += 1
                normalized_items.append(
                    normalize_value(item, f"{key_path}[]", stats, None, key)
                )
            else:
                normalized_items.append(maybe_normalize_timestamp_string(item, stats))
        return normalized_items

    return maybe_normalize_timestamp_string(value, stats)


def normalize_dict(record: dict[str, Any], parent_path: str, stats: TableStats) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in record.items():
        key_path = f"{parent_path}.{key}" if parent_path else key
        normalized[key] = normalize_value(value, key_path, stats, record, key)
    return normalized


def collect_leaf_types(value: Any, path_prefix: str, stats: TableStats) -> None:
    """Record scalar (and empty container) types at dot-paths; use `[]` for list branches."""
    if isinstance(value, dict):
        if not value:
            p = path_prefix or "(root)"
            stats.column_types[p].add("object")
            return
        for k, v in value.items():
            child = f"{path_prefix}.{k}" if path_prefix else k
            collect_leaf_types(v, child, stats)
        return

    if isinstance(value, list):
        list_path = f"{path_prefix}[]" if path_prefix else "[]"
        if not value:
            stats.column_types[list_path].add("list")
            return
        for item in value:
            if isinstance(item, dict):
                for k, v in item.items():
                    child = f"{list_path}.{k}"
                    collect_leaf_types(v, child, stats)
            elif isinstance(item, list):
                collect_leaf_types(item, list_path, stats)
            else:
                stats.column_types[list_path].add(infer_type_label(item))
        return

    p = path_prefix or "(root)"
    stats.column_types[p].add(infer_type_label(value))


def _path_is_under(path: Path, ancestor: Path) -> bool:
    try:
        path.resolve().relative_to(ancestor.resolve())
        return True
    except ValueError:
        return False


def discover_jsonl_files(root: Path, exclude_under: Path | None = None) -> list[Path]:
    paths = sorted(root.rglob("*.jsonl"))
    if exclude_under is None:
        return paths
    ex = exclude_under.resolve()
    return [p for p in paths if not _path_is_under(p.resolve(), ex)]


def process_file(path: Path, stats: TableStats, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("r", encoding="utf-8") as src, output_path.open("w", encoding="utf-8") as dst:
        for raw_line in src:
            line = raw_line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                stats.malformed_lines += 1
                continue

            if not isinstance(parsed, dict):
                stats.malformed_lines += 1
                continue

            normalized = normalize_dict(parsed, "", stats)
            collect_leaf_types(normalized, "", stats)
            dst.write(json.dumps(normalized, ensure_ascii=False) + "\n")
            stats.record_count += 1


def render_report(stats_by_table: dict[str, TableStats]) -> str:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    lines: list[str] = []
    lines.append("# Timestamp Normalization Report")
    lines.append("")
    lines.append("Leaf type paths use dot notation; list branches are named `path[]`. ")
    lines.append("Scalar elements inside a list share the path `parent[]` (union of observed types).")
    lines.append("")
    lines.append(f"- Generated at (UTC): `{generated_at}`")
    lines.append(f"- Input root: `{INPUT_ROOT.resolve()}`")
    lines.append(f"- Output root (cleaned JSONL): `{OUTPUT_ROOT.resolve()}`")
    lines.append(f"- Report path: `{REPORT_PATH.resolve()}`")
    lines.append("")
    lines.append("## Summary by Table")
    lines.append("")
    lines.append(
        "| table | file_count | record_count | malformed_lines | normalized_string_timestamps | "
        "flattened_nested_timestamp_objects | nested_path_keys_unique | "
        "nested_path_observations | unique_leaf_paths |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")

    for table_name in sorted(stats_by_table):
        stats = stats_by_table[table_name]
        leaf_n = len(stats.column_types)
        lines.append(
            f"| {table_name} | {stats.file_count} | {stats.record_count} | {stats.malformed_lines} | "
            f"{stats.normalized_string_timestamps} | {stats.flattened_nested_timestamp_objects} | "
            f"{len(stats.non_timestamp_nested_paths)} | {sum(stats.non_timestamp_nested_paths.values())} | "
            f"{leaf_n} |"
        )

    lines.append("")
    lines.append("## Per-Table Details")
    lines.append("")

    for table_name in sorted(stats_by_table):
        stats = stats_by_table[table_name]
        lines.append(f"### {table_name}")
        lines.append("")
        lines.append("#### Leaf Paths and Types")
        lines.append("")
        if stats.column_types:
            for path_key in sorted(stats.column_types):
                type_labels = sorted(stats.column_types[path_key])
                lines.append(f"- `{path_key}`: `{'|'.join(type_labels)}`")
        else:
            lines.append("- _No leaf paths recorded_")
        lines.append("")
        lines.append("#### Nested Structure Visits (non-timestamp dict/list during normalization)")
        lines.append("")
        if stats.non_timestamp_nested_paths:
            for path_key, count in sorted(stats.non_timestamp_nested_paths.items()):
                lines.append(f"- `{path_key}`: {count}")
        else:
            lines.append("- _No nested visits recorded_")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    if not INPUT_ROOT.exists():
        raise FileNotFoundError(f"Input root not found: {INPUT_ROOT}")

    files = discover_jsonl_files(INPUT_ROOT, exclude_under=OUTPUT_ROOT)
    stats_by_table: dict[str, TableStats] = defaultdict(lambda: TableStats(table_name=""))

    for source_file in files:
        relative = source_file.relative_to(INPUT_ROOT)
        table = relative.parts[0] if relative.parts else relative.name
        if not stats_by_table[table].table_name:
            stats_by_table[table].table_name = table
        stats_by_table[table].file_count += 1

        destination = OUTPUT_ROOT / relative
        process_file(source_file, stats_by_table[table], destination)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report = render_report(stats_by_table)
    REPORT_PATH.write_text(report, encoding="utf-8")

    print(f"Normalized files written under: {OUTPUT_ROOT.resolve()}")
    print(f"Report generated at: {REPORT_PATH.resolve()}")
    print(f"Tables processed: {len(stats_by_table)}")


if __name__ == "__main__":
    main()
