# Loading envs with python-dotenv
_Exported on 3/27/2026 at 09:06:49 GMT+5:30 from Cursor (2.6.21)_

---

**User**

@agent/model.py @agent/subagent/cypher_subagent.py use python-dotenv to load envs in these files

---

**Cursor**

I’m going to update both files to initialize environment variables via `python-dotenv`, then I’ll quickly lint-check those files to ensure no import/order issues were introduced.

I found both files and will add `from dotenv import load_dotenv` with `load_dotenv()` near the top so existing `os.getenv`/`os.environ` reads pick up values from `.env`. I’ll apply the edits now.

Added `python-dotenv` loading in both requested files.

### Changes made
- Updated `agent/model.py`:
  - Added `from dotenv import load_dotenv`
  - Added `load_dotenv()` near the top before env variable access

- Updated `agent/subagent/cypher_subagent.py`:
  - Added `from dotenv import load_dotenv`
  - Added `load_dotenv()` near the top before reading `NEO4J_*` env vars

Also ran a lint check on both files; no linter issues were introduced.

If you want, I can also add a quick startup check that raises a clear error when required `NEO4J_*` vars are missing.

