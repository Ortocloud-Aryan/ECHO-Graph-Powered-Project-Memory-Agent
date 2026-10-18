# ECHO

Graph-powered AI project-memory agent, built for Graph Hacks 2026 (Track 01 + Track 02).
Stores project facts and decisions in **FalkorDB**, traverses relationships to find downstream impact, remembers across sessions, and explains answers with graph evidence.

> **Status: skeleton only.** Nothing here has been run against a database yet. See `BUILD_STATUS.md`.

## Setup (not yet verified end-to-end)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then edit; never commit .env
```

FalkorDB locally (needs Docker):
```bash
docker run -p 6379:6379 --rm falkordb/falkordb
```

## Run
```bash
pytest -q -m "not db"       # tests without a database
streamlit run app.py        # placeholder page for now
```

## Layout
- `app.py` - Streamlit entrypoint
- `src/echo/` - package (db, store, queries, agent)
- `tests/`, `scripts/`, `docs/`
- `CLAUDE.md` - project rules; `BUILD_STATUS.md`, `NEXT_STEPS.md` - progress/recovery
