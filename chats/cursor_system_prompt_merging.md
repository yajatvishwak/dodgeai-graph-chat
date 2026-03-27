# System prompt merging
_Exported on 3/27/2026 at 09:09:07 GMT+5:30 from Cursor (2.6.21)_

---

**User**

@agent/system_prompt.py:6-188 merge into a single system prompt

---

**Cursor**

Reading the full file and searching for references to these prompts.



Merging the composer and orchestrator prompts into one `system_prompt`, removing the duplicate schema block, and updating `main.py` to import it.



Writing a unified prompt: composer as primary role; schema once; Cypher execution rules for delegated work and validation; subagent YAML format from the old orchestrator prompt integrated into the Tools / delegation section.



Here’s what changed.

### Single `system_prompt` in `agent/system_prompt.py`
- **Role** — Composer agent first, plus one line that any Cypher (delegated or direct) must stay schema-grounded (replaces the separate “you are a Cypher expert” opener).
- **Schema** — Still one block; same validation text as before.
- **Cypher execution rules** — Former orchestrator “Execution Rules” (no second schema section).
- **Scope → pipeline → tools → answer standards** — Same composer content, with headings normalized to sentence case for consistency.
- **Expected format from `cypher` subagents** — The old orchestrator YAML (`query` / `result` / `reasoning`) lives here so delegation expectations stay explicit without a second full agent role.
- **Your output format** — Renamed from “Output Format” so it’s clear this is the main agent’s YAML, not the subagent’s.

`orchestrator_system_prompt` is removed.

### `agent/main.py`
- Imports and passes `system_prompt` instead of `orchestrator_system_prompt`.

`cypher_system_prompt` is unchanged for `cypher_subagent.py`. If you want subagent prompts aligned with the new `query` / `result` / `reasoning` contract, that can be a follow-up edit.

