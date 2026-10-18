# CLAUDE.md - ECHO project rules

Read this, BUILD_STATUS.md and NEXT_STEPS.md at the start of every session.

## Product scope
ECHO = graph-powered AI project-memory agent for Graph Hacks 2026 (Track 01: Agents That Act on Connected Data; Track 02: Agent Memory and Coordination).
It must:
1. Store project facts and decisions as nodes/relationships in FalkorDB.
2. Traverse relationships (Cypher) to compute downstream impact of a change.
3. Remember across sessions (memory lives in the graph, not in process state).
4. Explain every answer with actual graph evidence (the paths/nodes returned by the query).

Out of scope: auth, multi-user, cloud deploy, plugins, fancy graph visualization, anything not needed for the 4 points above.

## Architecture principles
- FalkorDB is the primary and only database. Use the official `falkordb` Python client.
- Real Cypher queries drive answers. A graph picture is optional decoration, never the feature.
- Simple layers, one-way dependencies: `app.py` -> `echo.agent` -> `echo.queries`/`echo.store` -> `echo.db`.
- All Cypher lives in `src/echo/` (store/queries). No Cypher in `app.py`.
- Always use parameterized Cypher (`graph.query(q, params)`); never f-string user input into queries.
- Config only via environment variables (`.env`, loaded with python-dotenv).
- LLM is only used for language (parse request, phrase answer). Facts and impact come from the graph.
- Every agent answer returns its evidence (query + rows/paths) alongside the text.

## Coding conventions
- Python 3.10+, type hints on public functions, short docstrings.
- Small functions, small files. No classes unless needed. No new dependencies without noting it in NEXT_STEPS.md.
- Package `src/echo/`; imports as `from echo import ...`.
- Do not add features, abstractions, or config "for later".

## Testing rules
- Unit tests need no database. DB tests are marked `@pytest.mark.db` and skip if FalkorDB is unreachable.
- Run: `pytest -q` (all) / `pytest -q -m "not db"` (no DB).
- Nothing is "working" until its test/command was actually run and passed. Record the command and result in NEXT_STEPS.md.
- Use a separate graph name for tests (e.g. `echo_test`) and clean it up.

## Security rules
- No API keys, passwords or tokens in source, docs, tests, logs or commits.
- `.env` is git-ignored; only `.env.example` (blank values) is committed.
- Before every commit run `git status` and `git diff --staged`; check for secrets.
- If a secret is committed: rotate it first, then clean history.

## Recovery protocol
At the end of every stage:
1. Run the stage's checks; record exact commands + results.
2. Update BUILD_STATUS.md (tick only what was verified) and NEXT_STEPS.md (current stage, done, unverified, commands, known problems, exact next task).
3. Commit only working, tested milestones (`git commit -m "stage N: ..."`). Never label broken code as a milestone.
4. Give the user a copyable continuation prompt.
If a session starts cold: read the three status files, run `git log --oneline -5` and `git status`, run `pytest -q -m "not db"`, then continue from "Exact next task".
