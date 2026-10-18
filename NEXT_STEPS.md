# NEXT_STEPS

## Current stage
Stage 1 (skeleton) - complete. Next: Stage 2.

## Completed (verified)
- Directory `echo/` created with all required files/dirs (see `ls`).
- `python3 -m py_compile` passes for app.py, src/echo/__init__.py, tests/test_skeleton.py.
- venv created; `pip install -r requirements.txt` succeeded (falkordb 1.8.0, streamlit 1.66.0, python-dotenv 1.2.4, pytest 9.1.1).
- `pytest -q` -> 1 passed (skeleton import test only).
- `import streamlit, falkordb` works.

## Unverified
- Any FalkorDB connection (no DB running; Docker not available in this sandbox).
- `streamlit run app.py` (not launched).
- Graph schema, queries, agent, LLM choice: not built.

## Commands executed
`mkdir/touch/cat` (file creation), `git init`, `python3 -m py_compile ...`, `pip install --dry-run` (blocked by PEP 668), `python3 -m venv .venv`, `pip install -r requirements.txt`, `pytest -q`, `python -c "import streamlit, falkordb"`.

## Known problems
- System pip is externally managed: always use `.venv`.
- No Docker here: FalkorDB must come from the user's machine (Docker) or FalkorDB Cloud.

## Exact next task (Stage 2)
1. Start FalkorDB (`docker run -p 6379:6379 --rm falkordb/falkordb`) or use FalkorDB Cloud; fill `.env`.
2. Add `src/echo/db.py` (connect via official client + env vars) and a `@pytest.mark.db` test that creates/queries/deletes a node in graph `echo_test`.
3. Add a minimal schema (Project, Component, Decision, Fact, Session) and `scripts/seed.py`.
4. Run tests, record results, update status files, commit.
