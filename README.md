# ECHO — Graph-Powered Project Memory Prototype

Built with Python and FalkorDB for Graph Hacks 2026.

ECHO represents software-project entities, dependencies, decisions, and memories as a graph. It uses Cypher queries to identify downstream tasks affected by a decision, retrieve stored project context, and trace decision history through graph relationships.

> **Current status:** Stage 3 prototype. Graph-based impact analysis, persistent memory operations, and decision-history queries are implemented. The current prototype does not yet include an LLM-powered agent or a functional user interface. Explanations are generated from graph-query results and evidence paths. All demo data is synthetic.

## Prerequisites

- Python 3.10 or newer.
- Docker Desktop, with Docker running.
- FalkorDB running locally on `127.0.0.1:6379`.
- Git to clone the repository.

The local Docker setup is the verified development approach. Connecting to a remote FalkorDB deployment or using TLS has not been verified.

## Setup (Windows PowerShell)

Clone the repository and enter its directory:

```powershell
git clone https://github.com/aarjavjain7/ECHO-Graph-Powered-Project-Memory-Agent.git
cd ECHO-Graph-Powered-Project-Memory-Agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

If PowerShell blocks virtual-environment activation, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Start the existing FalkorDB container:

```powershell
docker start echo-falkordb
```

If the container does not exist yet, create and start it:

```powershell
docker run -d --name echo-falkordb -p 127.0.0.1:6379:6379 falkordb/falkordb
```

For Linux/macOS, activate the environment with `source .venv/bin/activate` and copy the environment template with `cp .env.example .env`. Docker and a reachable FalkorDB instance are still required.

## Run the demos

Run these commands from the repository root with the virtual environment activated and FalkorDB running:

```powershell
python scripts/health.py
python scripts/seed.py
python scripts/demo_impact.py
python scripts/demo_memory.py
```

- `health.py` checks database connectivity with Cypher.
- `seed.py` creates the synthetic project graph.
- `demo_impact.py` demonstrates graph-based downstream impact analysis and evidence paths.
- `demo_memory.py` demonstrates memory retrieval, decision history, and supersession relationships using isolated demo data.

## Tests

```powershell
pytest -q -m "not db"
pytest -q -m db
pytest -q
```

- `pytest -q -m "not db"` runs tests not marked as database integration tests.
- `pytest -q -m db` runs integration tests against FalkorDB, using the `ECHO_TEST_GRAPH` environment variable (default: `echo_test`).
- `pytest -q` runs the full test suite and requires the dependencies and database needed by the configured tests.

## Graph model and Cypher

See [`docs/GRAPH_MODEL.md`](docs/GRAPH_MODEL.md) for the graph schema, relationship types, and representative Cypher queries.

FalkorDB is the primary graph database and is central to the prototype's functionality. ECHO traverses graph relationships to identify potentially impacted tasks and retrieves graph evidence to explain the result. The memory layer stores project context and decision records, while decision-history relationships preserve links between newer and superseded decisions.

## Current limitations

- The project is a prototype, not a production-ready autonomous agent.
- No LLM-powered reasoning or functional Streamlit UI is currently implemented; `app.py` is a placeholder.
- Demonstrations use synthetic data rather than a real software team's project data.
- Impact analysis is limited to the graph relationships and query logic implemented in this prototype; results are not a guarantee that every real-world consequence of a change will be found.
- The current local Docker setup is the verified development path. Remote hosting, TLS configuration, and production deployment have not been verified.

## Repository layout

- `app.py` — Streamlit placeholder.
- `src/echo/` — database connection, schema, graph writes, Cypher queries, memory operations, and evidence formatting.
- `scripts/` — health check, graph seeding, impact-analysis demo, and memory demo.
- `tests/` — automated tests.
- `docs/GRAPH_MODEL.md` — graph schema and Cypher examples.
- `CLAUDE.md`, `BUILD_STATUS.md`, `NEXT_STEPS.md` — development and project notes.
