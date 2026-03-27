# ID resolution strategy enhancement
_Exported on 3/27/2026 at 09:10:27 GMT+5:30 from Cursor (2.6.21)_

---

**User**

@agent/system_prompt.py:6-176 can you add another rule 
ID RESOLUTION STRATEGY:

If an ID is provided and node type is unclear:

1. Run:
   MATCH (n)
   WHERE any(v IN values(n) WHERE toString(v) = "<ID>")
   RETURN labels(n), keys(n) LIMIT 1

2. Identify the correct node label and ID field.

3. Construct the FINAL query using the best path.

4. You MUST execute the final query after detection. @agent/system_prompt.py:6-176 

---

**Cursor**

Updating `agent/system_prompt.py` to add a dedicated **ID resolution strategy** rule in the prompt, including the detection query and the requirement to always execute the final query after resolving node type. I’ll patch the prompt text now and then quickly check for lints.

Added the new rule to `agent/system_prompt.py` in a dedicated **ID resolution strategy** section right after the Cypher execution rules.

What it now enforces:
- When an ID is provided but node type is unknown, run the detection query first:
  - `MATCH (n) WHERE any(v IN values(n) WHERE toString(v) = "<ID>") RETURN labels(n), keys(n) LIMIT 1`
- Identify the correct label and ID field from that result.
- Build the final schema-valid query from that detection.
- **Must execute the final query after detection** (cannot stop at identification).

No linter issues were introduced.

---

**User**

update with MATCH (n)
WHERE any(k IN keys(n) WHERE toString(n[k]) = "91150187")
RETURN labels(n) AS labels, keys(n) AS props
LIMIT 1

---

**Cursor**

I’ll update the ID-resolution step to use exactly that multiline Cypher pattern (including aliased return fields), then save.

Updated `agent/system_prompt.py` with that exact multiline query in the ID resolution step:

- Uses `keys(n)` + `n[k]` matching
- Uses the concrete value `"91150187"`
- Returns aliased fields as `labels` and `props`
- Keeps `LIMIT 1` as requested

---

**User**

@/Users/yajat/Documents/Code/dodge-assignment/agent/main.py:9-23 move to system_prompt.py

---

**Cursor**

I’ll move that middleware instruction block out of `agent/main.py` into `agent/system_prompt.py`, then wire `main.py` to reference it so prompt text is centralized in one place.

I found both prompts already in `system_prompt.py`, so I’ll add a dedicated constant there for the todo middleware prompt and make `main.py` import/use it directly (removing the inline block).

Moved that middleware protocol from `agent/main.py` into `agent/system_prompt.py` and wired it cleanly.

### What changed
- Added `todo_middleware_system_prompt` in `agent/system_prompt.py`.
- Updated `agent/main.py` to import it:
  - `from system_prompt import system_prompt, todo_middleware_system_prompt`
- Removed the inline multiline prompt block from `main.py`.
- `create_agent(...)` now uses:
  - `TodoListMiddleware(system_prompt=todo_middleware_system_prompt)`

Also fixed the previous wiring issue while doing this: `main.py` was wrapping a `TodoListMiddleware` instance inside another `TodoListMiddleware`; it now correctly passes the prompt string once.

No lint issues in edited files.

