from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

try:
    import psycopg  # type: ignore
except ImportError:
    psycopg = None

try:
    import psycopg2  # type: ignore
except ImportError:
    psycopg2 = None


_DATA_CREATION_DIR = Path(__file__).resolve().parent
DEFAULT_DBML_PATH = _DATA_CREATION_DIR / "schema.dbml"
DEFAULT_INPUT_ROOT = _DATA_CREATION_DIR / "data" / "cleaned"
DEFAULT_SCHEMA = "public"
DEFAULT_ENV_PATH = _DATA_CREATION_DIR.parent / ".env"
FALLBACK_ENV_PATH = _DATA_CREATION_DIR / ".env"
UTC = timezone.utc


@dataclass
class ColumnDef:
    name: str
    dbml_type: str
    nullable: bool


@dataclass
class TableDef:
    name: str
    columns: list[ColumnDef]


@dataclass
class ForeignKeyDef:
    from_table: str
    from_columns: list[str]
    to_table: str
    to_columns: list[str]

    @property
    def constraint_name(self) -> str:
        raw = (
            f"fk_{self.from_table}_{'_'.join(self.from_columns)}_"
            f"{self.to_table}_{'_'.join(self.to_columns)}"
        )
        sanitized = re.sub(r"[^A-Za-z0-9_]+", "_", raw).lower().strip("_")
        if not sanitized:
            sanitized = "fk_generated"
        # PostgreSQL identifier length limit: 63 bytes.
        return sanitized[:63]


def unique_constraint_name(table: str, columns: list[str]) -> str:
    raw = f"uq_{table}_{'_'.join(columns)}"
    sanitized = re.sub(r"[^A-Za-z0-9_]+", "_", raw).lower().strip("_")
    if not sanitized:
        sanitized = "uq_generated"
    return sanitized[:63]


@dataclass
class LoadStats:
    files_seen: int = 0
    rows_seen: int = 0
    rows_inserted: int = 0
    rows_conflicted: int = 0
    rows_skipped_invalid: int = 0
    rows_skipped_db_error: int = 0
    malformed_lines: int = 0


def load_env_file(path: Path) -> bool:
    if not path.exists():
        return False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Keep real environment overrides if already set.
        os.environ.setdefault(key, value)
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Load table-folder JSONL files into PostgreSQL using a predefined "
            "DBML schema and ON CONFLICT DO NOTHING."
        )
    )
    parser.add_argument("--dbml-path", type=Path, default=DEFAULT_DBML_PATH)
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--schema", default=DEFAULT_SCHEMA, help="Target PostgreSQL schema name.")
    parser.add_argument(
        "--reset-schema",
        action="store_true",
        help="Drop and recreate target schema before creating tables.",
    )
    parser.add_argument(
        "--skip-fk-checks",
        action="store_true",
        help="Disable FK checks in this session while loading data.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Commit interval (in accepted rows) during inserts.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_ENV_PATH,
        help="Path to .env file with PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD values.",
    )
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--db", default=None)
    parser.add_argument("--user", default=None)
    parser.add_argument("--password", default=None)
    args = parser.parse_args()

    requested_env = args.env_file.resolve()
    loaded = load_env_file(requested_env)
    if not loaded and requested_env == DEFAULT_ENV_PATH:
        # Backward-compatible fallback: many setups keep .env inside data_creation.
        load_env_file(FALLBACK_ENV_PATH.resolve())
    args.host = args.host or os.getenv("PGHOST", "localhost")
    args.port = args.port or int(os.getenv("PGPORT", "5432"))
    args.db = args.db or os.getenv("PGDATABASE")
    args.user = args.user or os.getenv("PGUSER")
    args.password = args.password or os.getenv("PGPASSWORD")
    return args


def require_postgres_driver() -> str:
    if psycopg is not None:
        return "psycopg"
    if psycopg2 is not None:
        return "psycopg2"
    raise RuntimeError(
        "Missing PostgreSQL driver. Install one of: `pip install psycopg` or "
        "`pip install psycopg2-binary`."
    )


def quote_ident(name: str) -> str:
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


def normalize_dbml_ident(raw: str) -> str:
    token = raw.strip()
    if token.startswith('"') and token.endswith('"'):
        return token[1:-1]
    return token


def split_columns_expr(expr: str) -> list[str]:
    text = expr.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    if not text.strip():
        return []
    return [normalize_dbml_ident(part.strip()) for part in text.split(",")]


def parse_table_column(line: str) -> ColumnDef | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("//"):
        return None
    if stripped == "}":
        return None
    match = re.match(r'^(".*?"|[A-Za-z_][A-Za-z0-9_]*)\s+([A-Za-z0-9_]+)\s*(.*)$', stripped)
    if not match:
        return None

    name = normalize_dbml_ident(match.group(1))
    dbml_type = match.group(2).lower()
    attrs = match.group(3)
    nullable = "[not null]" not in attrs
    return ColumnDef(name=name, dbml_type=dbml_type, nullable=nullable)


def parse_ref_line(ref_line: str) -> ForeignKeyDef:
    payload = ref_line[len("Ref:") :].strip()
    if ">" not in payload:
        raise ValueError(f"Invalid Ref syntax: {ref_line}")
    left_raw, right_raw = payload.split(">", 1)
    left = left_raw.strip()
    right = right_raw.strip()

    left_match = re.match(r'^(".*?"|[A-Za-z_][A-Za-z0-9_]*)\.(.+)$', left)
    right_match = re.match(r'^(".*?"|[A-Za-z_][A-Za-z0-9_]*)\.(.+)$', right)
    if not left_match or not right_match:
        raise ValueError(f"Invalid Ref relation: {ref_line}")

    from_table = normalize_dbml_ident(left_match.group(1))
    from_columns = split_columns_expr(left_match.group(2))
    to_table = normalize_dbml_ident(right_match.group(1))
    to_columns = split_columns_expr(right_match.group(2))

    if not from_columns or not to_columns or len(from_columns) != len(to_columns):
        raise ValueError(f"Invalid Ref columns: {ref_line}")

    return ForeignKeyDef(
        from_table=from_table,
        from_columns=from_columns,
        to_table=to_table,
        to_columns=to_columns,
    )


def parse_dbml(path: Path) -> tuple[dict[str, TableDef], list[ForeignKeyDef]]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    tables: dict[str, TableDef] = {}
    refs: list[ForeignKeyDef] = []

    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if not line or line.startswith("//"):
            idx += 1
            continue

        table_match = re.match(r'^Table\s+(".*?"|[A-Za-z_][A-Za-z0-9_]*)\s*\{$', line)
        if table_match:
            table_name = normalize_dbml_ident(table_match.group(1))
            columns: list[ColumnDef] = []
            idx += 1
            while idx < len(lines):
                current = lines[idx].strip()
                if current == "}":
                    break
                parsed_col = parse_table_column(lines[idx])
                if parsed_col is not None:
                    columns.append(parsed_col)
                idx += 1
            if idx >= len(lines) or lines[idx].strip() != "}":
                raise ValueError(f"Unclosed table block in DBML for table `{table_name}`.")
            tables[table_name] = TableDef(name=table_name, columns=columns)
            idx += 1
            continue

        if line.startswith("Ref:"):
            ref_buffer = [line]
            idx += 1
            while idx < len(lines):
                next_line = lines[idx].strip()
                if not next_line:
                    break
                if next_line.startswith("Ref:") or next_line.startswith("//") or next_line.startswith("Table "):
                    break
                ref_buffer.append(next_line)
                idx += 1
            collapsed_ref = " ".join(ref_buffer)
            refs.append(parse_ref_line(collapsed_ref))
            continue

        idx += 1

    return tables, refs


def dbml_to_postgres_type(dbml_type: str) -> str:
    mapping = {
        "bigint": "bigint",
        "int": "integer",
        "integer": "integer",
        "numeric": "numeric",
        "float": "double precision",
        "double": "double precision",
        "boolean": "boolean",
        "bool": "boolean",
        "text": "text",
        "timestamp": "timestamptz",
        "timestamptz": "timestamptz",
        "date": "date",
        "json": "jsonb",
    }
    if dbml_type not in mapping:
        raise ValueError(f"Unsupported DBML type `{dbml_type}`.")
    return mapping[dbml_type]


def open_connection(args: argparse.Namespace, driver: str) -> Any:
    if not args.db or not args.user:
        raise ValueError(
            "Database credentials are incomplete. Provide `--db` and `--user` "
            "(or set PGDATABASE/PGUSER)."
        )

    if driver == "psycopg":
        return psycopg.connect(  # type: ignore[union-attr]
            host=args.host,
            port=args.port,
            dbname=args.db,
            user=args.user,
            password=args.password,
            autocommit=False,
        )
    return psycopg2.connect(  # type: ignore[union-attr]
        host=args.host,
        port=args.port,
        dbname=args.db,
        user=args.user,
        password=args.password,
    )


def fk_exists(cursor: Any, schema_name: str, table_name: str, constraint_name: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE c.contype = 'f'
          AND n.nspname = %s
          AND t.relname = %s
          AND c.conname = %s
        LIMIT 1
        """,
        (schema_name, table_name, constraint_name),
    )
    return cursor.fetchone() is not None


def unique_exists(cursor: Any, schema_name: str, table_name: str, constraint_name: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE c.contype IN ('u', 'p')
          AND n.nspname = %s
          AND t.relname = %s
          AND c.conname = %s
        LIMIT 1
        """,
        (schema_name, table_name, constraint_name),
    )
    return cursor.fetchone() is not None


def reset_schema(cursor: Any, schema_name: str) -> None:
    cursor.execute(f"DROP SCHEMA IF EXISTS {quote_ident(schema_name)} CASCADE")
    cursor.execute(f"CREATE SCHEMA {quote_ident(schema_name)}")


def create_tables(cursor: Any, schema_name: str, tables: dict[str, TableDef]) -> None:
    for table_name in sorted(tables):
        table = tables[table_name]
        column_sql = []
        for col in table.columns:
            pg_type = dbml_to_postgres_type(col.dbml_type)
            nullability = "" if col.nullable else " NOT NULL"
            column_sql.append(f"{quote_ident(col.name)} {pg_type}{nullability}")
        ddl = (
            f"CREATE TABLE IF NOT EXISTS {quote_ident(schema_name)}.{quote_ident(table.name)} "
            f"({', '.join(column_sql)})"
        )
        cursor.execute(ddl)


def sync_table_nullability(cursor: Any, schema_name: str, table: TableDef) -> None:
    cursor.execute(
        """
        SELECT column_name, is_nullable
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        """,
        (schema_name, table.name),
    )
    db_nullability = {
        row[0]: (row[1] == "YES")
        for row in cursor.fetchall()
    }

    for col in table.columns:
        if col.name not in db_nullability:
            continue
        db_is_nullable = db_nullability[col.name]
        if db_is_nullable == col.nullable:
            continue
        if col.nullable:
            cursor.execute(
                f"ALTER TABLE {quote_ident(schema_name)}.{quote_ident(table.name)} "
                f"ALTER COLUMN {quote_ident(col.name)} DROP NOT NULL"
            )
        else:
            cursor.execute(
                f"ALTER TABLE {quote_ident(schema_name)}.{quote_ident(table.name)} "
                f"ALTER COLUMN {quote_ident(col.name)} SET NOT NULL"
            )


def sync_nullability(cursor: Any, schema_name: str, tables: dict[str, TableDef]) -> None:
    for table_name in sorted(tables):
        sync_table_nullability(cursor, schema_name, tables[table_name])


def ensure_referenced_uniques(
    cursor: Any, schema_name: str, tables: dict[str, TableDef], refs: list[ForeignKeyDef]
) -> None:
    unique_targets: set[tuple[str, tuple[str, ...]]] = set()
    for ref in refs:
        if ref.to_table not in tables:
            continue
        unique_targets.add((ref.to_table, tuple(ref.to_columns)))

    for table_name, columns in sorted(unique_targets):
        cols = list(columns)
        constraint_name = unique_constraint_name(table_name, cols)
        if unique_exists(cursor, schema_name, table_name, constraint_name):
            continue
        lhs = ", ".join(quote_ident(c) for c in cols)
        ddl = (
            f"ALTER TABLE {quote_ident(schema_name)}.{quote_ident(table_name)} "
            f"ADD CONSTRAINT {quote_ident(constraint_name)} UNIQUE ({lhs})"
        )
        cursor.execute(ddl)


def create_foreign_keys(
    cursor: Any, schema_name: str, tables: dict[str, TableDef], refs: list[ForeignKeyDef]
) -> None:
    for ref in refs:
        if ref.from_table not in tables or ref.to_table not in tables:
            continue
        constraint_name = ref.constraint_name
        if fk_exists(cursor, schema_name, ref.from_table, constraint_name):
            continue

        lhs = ", ".join(quote_ident(c) for c in ref.from_columns)
        rhs = ", ".join(quote_ident(c) for c in ref.to_columns)
        ddl = (
            f"ALTER TABLE {quote_ident(schema_name)}.{quote_ident(ref.from_table)} "
            f"ADD CONSTRAINT {quote_ident(constraint_name)} "
            f"FOREIGN KEY ({lhs}) "
            f"REFERENCES {quote_ident(schema_name)}.{quote_ident(ref.to_table)} ({rhs})"
        )
        cursor.execute(ddl)


def discover_jsonl_files(root: Path) -> dict[str, list[Path]]:
    grouped: dict[str, list[Path]] = {}
    for jsonl in sorted(root.rglob("*.jsonl")):
        relative = jsonl.relative_to(root)
        if not relative.parts:
            continue
        table = relative.parts[0]
        grouped.setdefault(table, []).append(jsonl)
    return grouped


def table_load_order(tables: dict[str, TableDef], refs: list[ForeignKeyDef]) -> list[str]:
    """
    Compute parent-first table load order from FK refs.
    Edge direction: parent(to_table) -> child(from_table).
    """
    table_names = set(tables.keys())
    incoming: dict[str, int] = {name: 0 for name in table_names}
    outgoing: dict[str, set[str]] = {name: set() for name in table_names}

    for ref in refs:
        parent = ref.to_table
        child = ref.from_table
        if parent not in table_names or child not in table_names:
            continue
        if child not in outgoing[parent]:
            outgoing[parent].add(child)
            incoming[child] += 1

    ready = sorted([name for name, deg in incoming.items() if deg == 0])
    ordered: list[str] = []

    while ready:
        current = ready.pop(0)
        ordered.append(current)
        for child in sorted(outgoing[current]):
            incoming[child] -= 1
            if incoming[child] == 0:
                ready.append(child)
        ready.sort()

    if len(ordered) != len(table_names):
        # Cycle or unresolved graph: append remaining tables deterministically.
        remaining = sorted(table_names - set(ordered))
        ordered.extend(remaining)
    return ordered


def parse_timestamptz(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError("Empty timestamp string.")
        normalized = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
    else:
        raise ValueError(f"Unsupported timestamptz value type: {type(value).__name__}")

    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def parse_date(value: Any) -> datetime.date:
    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        if isinstance(value, datetime):
            return value.date()
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.strip()).date()
    raise ValueError(f"Unsupported date value type: {type(value).__name__}")


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value in (0, 1):
            return bool(value)
        raise ValueError(f"Invalid boolean integer `{value}`.")
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "t", "1", "yes", "y"}:
            return True
        if lowered in {"false", "f", "0", "no", "n"}:
            return False
    raise ValueError(f"Invalid boolean value `{value}`.")


def convert_value(value: Any, pg_type: str) -> Any:
    if isinstance(value, str) and not value.strip():
        value = None
    if value is None:
        return None

    if pg_type == "bigint" or pg_type == "integer":
        if isinstance(value, bool):
            raise ValueError("Boolean not allowed for integer columns.")
        return int(value)
    if pg_type == "numeric":
        if isinstance(value, bool):
            raise ValueError("Boolean not allowed for numeric columns.")
        try:
            return Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError(f"Invalid numeric value `{value}`.") from exc
    if pg_type == "double precision":
        if isinstance(value, bool):
            raise ValueError("Boolean not allowed for float columns.")
        return float(value)
    if pg_type == "boolean":
        return parse_bool(value)
    if pg_type == "timestamptz":
        return parse_timestamptz(value)
    if pg_type == "date":
        return parse_date(value)
    if pg_type == "jsonb":
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, str):
            json.loads(value)
            return value
        raise ValueError(f"Invalid JSON value `{value}`.")
    if pg_type == "text":
        return str(value)
    raise ValueError(f"Unsupported PostgreSQL type `{pg_type}`.")


def insert_sql(schema_name: str, table: TableDef) -> str:
    col_names = ", ".join(quote_ident(c.name) for c in table.columns)
    placeholders = ", ".join(["%s"] * len(table.columns))
    return (
        f"INSERT INTO {quote_ident(schema_name)}.{quote_ident(table.name)} "
        f"({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
    )


def load_table_jsonl(
    cursor: Any,
    schema_name: str,
    table: TableDef,
    files: list[Path],
    batch_size: int,
    stats: LoadStats,
) -> None:
    pg_types = [dbml_to_postgres_type(c.dbml_type) for c in table.columns]
    sql = insert_sql(schema_name, table)
    staged = 0

    for file_path in files:
        stats.files_seen += 1
        with file_path.open("r", encoding="utf-8") as fh:
            for line_no, raw_line in enumerate(fh, 1):
                payload = raw_line.strip()
                if not payload:
                    continue
                try:
                    row = json.loads(payload)
                except json.JSONDecodeError:
                    stats.malformed_lines += 1
                    continue
                if not isinstance(row, dict):
                    stats.malformed_lines += 1
                    continue

                stats.rows_seen += 1
                converted: list[Any] = []
                try:
                    for col, pg_type in zip(table.columns, pg_types, strict=True):
                        raw_value = row.get(col.name)
                        try:
                            converted.append(convert_value(raw_value, pg_type))
                        except Exception as exc:
                            raise ValueError(
                                f"column `{col.name}` ({pg_type}) value `{raw_value}`: {exc}"
                            ) from exc
                except Exception as exc:
                    stats.rows_skipped_invalid += 1
                    print(
                        f"Skipping invalid row in {file_path} line {line_no} "
                        f"for table {table.name}: {exc}"
                    )
                    continue

                try:
                    cursor.execute("SAVEPOINT row_insert_sp")
                    cursor.execute(sql, tuple(converted))
                    if cursor.rowcount == 1:
                        stats.rows_inserted += 1
                    else:
                        stats.rows_conflicted += 1
                    cursor.execute("RELEASE SAVEPOINT row_insert_sp")
                except Exception as exc:
                    stats.rows_skipped_db_error += 1
                    print(
                        f"Skipping DB-error row in {file_path} line {line_no} "
                        f"for table {table.name}: {exc}"
                    )
                    cursor.execute("ROLLBACK TO SAVEPOINT row_insert_sp")
                    cursor.execute("RELEASE SAVEPOINT row_insert_sp")
                    continue
                staged += 1
                if staged >= batch_size:
                    cursor.connection.commit()
                    staged = 0

    if staged:
        cursor.connection.commit()


def main() -> None:
    args = parse_args()
    dbml_path = args.dbml_path.resolve()
    input_root = args.input_root.resolve()

    if not dbml_path.exists():
        raise FileNotFoundError(f"DBML file not found: {dbml_path}")
    if not input_root.exists():
        raise FileNotFoundError(f"Input root not found: {input_root}")
    if args.batch_size <= 0:
        raise ValueError("--batch-size must be > 0")

    tables, refs = parse_dbml(dbml_path)
    if not tables:
        raise ValueError("No tables were parsed from DBML.")

    driver = require_postgres_driver()
    conn = open_connection(args, driver)
    cursor = conn.cursor()
    stats = LoadStats()

    try:
        if args.reset_schema:
            print(f"Resetting schema `{args.schema}` ...")
            reset_schema(cursor, args.schema)
            conn.commit()

        print("Creating tables ...")
        create_tables(cursor, args.schema, tables)
        conn.commit()

        print("Syncing nullability constraints ...")
        sync_nullability(cursor, args.schema, tables)
        conn.commit()

        print("Ensuring unique keys for referenced columns ...")
        ensure_referenced_uniques(cursor, args.schema, tables, refs)
        conn.commit()

        print("Creating foreign keys ...")
        create_foreign_keys(cursor, args.schema, tables, refs)
        conn.commit()

        if args.skip_fk_checks:
            print("Disabling FK checks for this session ...")
            cursor.execute("SET session_replication_role = replica")
            conn.commit()

        files_by_table = discover_jsonl_files(input_root)
        unknown = sorted(set(files_by_table) - set(tables))
        if unknown:
            print(f"Skipping unknown folders not in DBML: {', '.join(unknown)}")

        load_order = table_load_order(tables, refs)
        print(f"Load order: {', '.join(load_order)}")

        for table_name in load_order:
            files = files_by_table.get(table_name, [])
            if not files:
                continue
            print(f"Loading table `{table_name}` from {len(files)} files ...")
            load_table_jsonl(cursor, args.schema, tables[table_name], files, args.batch_size, stats)

        if args.skip_fk_checks:
            print("Restoring FK checks for this session ...")
            cursor.execute("SET session_replication_role = origin")
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        try:
            if args.skip_fk_checks:
                cursor.execute("SET session_replication_role = origin")
                conn.commit()
        except Exception:
            conn.rollback()
        cursor.close()
        conn.close()

    print("")
    print("Load complete.")
    print(f"DBML: {dbml_path}")
    print(f"Input root: {input_root}")
    print(f"Schema: {args.schema}")
    print(f"JSONL files processed: {stats.files_seen}")
    print(f"Rows seen: {stats.rows_seen}")
    print(f"Rows inserted: {stats.rows_inserted}")
    print(f"Rows conflicted: {stats.rows_conflicted}")
    print(f"Rows skipped (invalid conversion): {stats.rows_skipped_invalid}")
    print(f"Rows skipped (database errors): {stats.rows_skipped_db_error}")
    print(f"Malformed lines skipped: {stats.malformed_lines}")


if __name__ == "__main__":
    main()
