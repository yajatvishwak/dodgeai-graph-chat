---
name: JSONL to DBML schema
overview: Add a standalone Python script in data_creation that scans JSONL files under data_creation/data, flattens nested records into dot-path columns, infers stable DBML column types, and marks columns nullable based on observed null/missing values.
todos:
  - id: add-script
    content: Create generate_dbml_schema.py with JSONL discovery, flattening, and per-column stats collection
    status: completed
  - id: type-null-inference
    content: Implement robust DBML type resolution and nullable detection rules
    status: completed
  - id: dbml-emission
    content: Render deterministic DBML tables/columns and write schema output file
    status: completed
  - id: verify-run
    content: Execute script on current data and verify output plus diagnostics
    status: completed
isProject: false
---

# JSONL to DBML Generator Plan

## Scope

Implement a new script at `[/Users/yajat/Documents/Code/dodge-assignment/data_creation/generate_dbml_schema.py](/Users/yajat/Documents/Code/dodge-assignment/data_creation/generate_dbml_schema.py)` that:

- Recursively reads `.jsonl` files under `[/Users/yajat/Documents/Code/dodge-assignment/data_creation/data](/Users/yajat/Documents/Code/dodge-assignment/data_creation/data)`
- Treats each first-level folder under the input root as one DB table
- Flattens nested objects/lists into dot-key columns
- Infers per-column type (`boolean`, `int`, `float`, `timestamp`, `date`, `text`, `json` fallback)
- Detects nullability from both explicit `null` and missing keys across rows
- Writes DBML to an output file in `data_creation`

## Implementation Details

- Reuse patterns from existing traversal in `[/Users/yajat/Documents/Code/dodge-assignment/data_creation/preprocess.py](/Users/yajat/Documents/Code/dodge-assignment/data_creation/preprocess.py)`, especially recursive walking and robust JSONL parsing.
- Add a recursive flattener:
  - Dicts -> `parent.child`
  - Lists of scalars -> keep as JSON/text-compatible aggregated field
  - Lists of objects -> flatten to `parent[].child` paths so nested structures are still represented
- Track per table + column stats:
  - `seen_rows`, `present_rows`, `null_rows`
  - observed raw value categories (`bool`, `int`, `float`, `str`, `date-like`, `timestamp-like`, `object`, `list`)
- Type resolution strategy (deterministic precedence):
  - If structural (`object`/`list`) observed -> `json`
  - Else if only numeric -> `int` or `float`
  - Else if boolean-only -> `boolean`
  - Else if all parse as timestamp/date -> `timestamp` or `date`
  - Mixed/ambiguous -> `text`
- Nullable rule:
  - Column is nullable if `null_rows > 0` OR `present_rows < seen_rows`
  - Render as `[not null]` only when always present and never null
- Emit DBML:
  - `Table table_name { ... }`
  - Quote/sanitize invalid identifiers conservatively to avoid DBML parse issues
  - Stable ordering: tables alphabetically, columns alphabetically
- CLI ergonomics:
  - `--input-root` default to `data_creation/data`
  - `--output` default to `data_creation/schema.dbml`
  - Print summary counts after generation

## Validation

- Run the script against current dataset under `[/Users/yajat/Documents/Code/dodge-assignment/data_creation/data](/Users/yajat/Documents/Code/dodge-assignment/data_creation/data)`.
- Verify generated DBML exists and contains expected tables/columns from known samples (e.g. billing documents).
- Spot-check nullable and type inference on timestamp-like and numeric-string fields.
- Run lint diagnostics on the new file and fix any introduced issues.
