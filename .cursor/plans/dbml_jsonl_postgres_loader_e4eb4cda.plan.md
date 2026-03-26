---
name: DBML JSONL Postgres Loader
overview: Build a Python loader that reads table-folder JSONL files, creates PostgreSQL tables/foreign keys from DBML, converts values to target column types with UTC timestamp handling, and inserts rows using ON CONFLICT DO NOTHING with optional schema reset and FK check bypass.
todos:
  - id: parse-dbml
    content: Implement DBML parser for tables, columns, and foreign key refs
    status: completed
  - id: ddl-flow
    content: Create Postgres DDL flow with optional schema reset
    status: completed
  - id: jsonl-loader
    content: Add JSONL discovery, per-column type conversion, and UTC timestamp normalization
    status: completed
  - id: insert-conflict
    content: Implement ON CONFLICT DO NOTHING inserts with batching and summary logs
    status: completed
  - id: fk-toggle
    content: Add session-level skip FK checks switch and safe restoration
    status: completed
  - id: validate
    content: Run validations for idempotency, FK behavior, and conversion correctness
    status: completed
isProject: false
---

# DBML-Based JSONL to Postgres Loader Plan

## Goal

Implement a new script at `[/Users/yajat/Documents/Code/dodge-assignment/data_creation/load_jsonl_to_postgres.py](/Users/yajat/Documents/Code/dodge-assignment/data_creation/load_jsonl_to_postgres.py)` that:

- reads JSONL files per table folder (default `data_creation/data/cleaned`)
- parses predefined schema + refs from `[/Users/yajat/Documents/Code/dodge-assignment/data_creation/schema.dbml](/Users/yajat/Documents/Code/dodge-assignment/data_creation/schema.dbml)`
- creates tables and FKs in Postgres
- converts JSON values into correct Postgres types (including UTC timestamps)
- inserts with `ON CONFLICT DO NOTHING`
- supports `--reset-schema` and `--skip-fk-checks`

## Implementation

- **DBML parsing layer**
  - Parse `Table` blocks, column names/types/nullability, and `Ref` definitions (including composite refs).
  - Map DBML types to Postgres (`bigint`, `numeric`, `boolean`, `text`, `timestamptz`, etc.).
  - Build an in-memory model: tables, ordered columns, nullable flags, and FK constraints.
- **Postgres DDL execution**
  - Add CLI options for connection (`--host`, `--port`, `--db`, `--user`, `--password` or env fallback).
  - On `--reset-schema`, drop/recreate target schema (default `public`) before table creation.
  - Create tables first, then add FK constraints from parsed refs.
  - Use idempotent DDL where possible (`CREATE TABLE IF NOT EXISTS`, guarded FK creation).
- **JSONL discovery and load order**
  - Discover files under input root by first-level folder name = table name.
  - Load only folders present in DBML table set; report skipped unknown folders.
  - Derive insert column list from DBML schema (ignore extra JSON keys; fill missing as `NULL`).
- **Type conversion and UTC handling**
  - Implement converters per target column type:
    - `bigint`/integer-like -> `int`
    - `numeric` -> `Decimal`
    - `boolean` -> strict bool normalization
    - `timestamptz` -> parse ISO strings, coerce naive values to UTC, convert aware values to UTC
    - `text` -> string cast
  - Keep `None` as SQL `NULL`.
  - For invalid values, log row + column errors and skip only the bad row (not whole file).
- **Insert strategy + FK-check toggle**
  - Generate per-table `INSERT ... VALUES (...) ON CONFLICT DO NOTHING`.
  - Wrap load in transaction chunks for reliability/perf.
  - `--skip-fk-checks`: disable FK enforcement for the session during load (e.g., `SET session_replication_role = replica`) and restore afterward.
- **Operational UX**
  - Add dry progress logs: tables seen, files processed, rows inserted/skipped/conflicted.
  - Exit with non-zero code on fatal setup/parsing/connection failures.
  - Print final summary for successful run.

## Validation

- Run script against current cleaned JSONL under `[/Users/yajat/Documents/Code/dodge-assignment/data_creation/data/cleaned](/Users/yajat/Documents/Code/dodge-assignment/data_creation/data/cleaned)`.
- Verify tables and FKs are created from `[/Users/yajat/Documents/Code/dodge-assignment/data_creation/schema.dbml](/Users/yajat/Documents/Code/dodge-assignment/data_creation/schema.dbml)`.
- Spot-check UTC normalization in `timestamptz` columns and numeric coercion.
- Re-run loader to confirm idempotency (`ON CONFLICT DO NOTHING` behavior).
- Run with and without `--skip-fk-checks`, and with `--reset-schema`, to validate control flags.
