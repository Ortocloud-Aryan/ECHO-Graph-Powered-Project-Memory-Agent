# ECHO

Graph-powered AI project-memory agent, built for Graph Hacks 2026 (Track 01 + Track 02).
Stores project facts and decisions in **FalkorDB**, traverses relationships to find downstream impact, remembers across sessions, and explains answers with graph evidence.

> **Status: Stage 2 done** - FalkorDB data layer + multi-hop impact analysis (no agent/UI yet). See `BUILD_STATUS.md`. All demo data is synthetic.

## Setup (Windows PowerShell shown)
```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # defaults work for local Docker; never commit .env
docker start echo-falkordb  # or first time: docker run -d --name echo-falkordb -p 127.0.0.1:6379:6379 falkordb/falkordb
```
(Linux/macOS: `source .venv/bin/activate`, `cp .env.example .env`.)

## Run
```powershell
python scripts/health.py        # real Cypher health check (exit 0 = healthy)
python scripts/seed.py          # idempotent synthetic dataset; safe to re-run
python scripts/demo_impact.py   # multi-hop impact demo, checked against docs/GRAPH_MODEL.md
pytest -q -m "not db"           # unit tests, no database
pytest -q -m db                 # integration tests against real FalkorDB (graph ECHO_TEST_GRAPH, default echo_test)
pytest -q                       # everything
```
Details: `docs/GRAPH_MODEL.md`.

## Layout
- `app.py` - Streamlit entrypoint (placeholder)
- `src/echo/` - `db` (connection/health), `schema`, `store` (MERGE writes), `seed`, `queries` (Cypher), `explain` (text), `demo`
- `tests/`, `scripts/`, `docs/`
- `CLAUDE.md` - project rules; `BUILD_STATUS.md`, `NEXT_STEPS.md` - progress/recovery
