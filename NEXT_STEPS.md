# NEXT_STEPS

## Current stage
Stage 2 (graph data layer + impact analysis) - complete in the sandbox. Next: re-verify on the user's Docker FalkorDB, then Stage 3.

## Completed
- `src/echo/`: `db.py` (env config, health check), `store.py` (allowlisted MERGE upserts), `schema.py` (id indexes + UNIQUE constraints), `seed.py` (synthetic data, prefix/dataset namespacing), `queries.py` (Cypher reads + `impact_analysis`), `explain.py` (text from result data), `demo.py` (documented expected result).
- `scripts/`: `health.py`, `seed.py`, `demo_impact.py`. `docs/GRAPH_MODEL.md`. `.env.example` + README updated. `tests/`: `conftest.py`, `test_unit.py` (no DB), `test_graph_db.py` (marker `db`).

## Verified (actual runs)
- Engine used: FalkorDB module bundled in `falkordblite` 0.10.0 (redis-server + falkordb.so, Linux, Python 3.12) listening on 127.0.0.1:6379, accessed with the official `falkordb` 1.8.0 client. NOT the user's Docker container, NOT Python 3.11/Windows.
- `python scripts/health.py` -> ok, ~5 ms. With the port wrong the failure is reported accurately (unit test + manual).
- `python scripts/seed.py` run twice on graph `echo`: both 23 nodes / 47 rels (23 distinct ids, 0 duplicate ids, 0 duplicate rels).
- `python scripts/demo_impact.py` -> 7 affected tasks, 5 max hops, PASS vs documented expected. Independent plain-Cypher cross-check matched (6 dependents of task-auth + task-auth).
- `pytest -q -m "not db"` 21 passed; `pytest -q -m db` 11 passed; `pytest -q` 32 passed. DB tests skip with the real reason when the port is wrong. `echo_test` left with 0 test nodes; `echo` demo data untouched.
- Found and fixed during verification: my first EXPECTED had task-analytics path_count 1; the graph correctly gave 2.

## Unverified
- Everything above against the user's real Docker FalkorDB (version may differ) on Windows + Python 3.11.9.
- `streamlit run app.py` (still a placeholder).
- Behaviour of `get_entity` unlabeled scan on large graphs.

## Commands executed (sandbox)
`pip install falkordblite`; started `redis-server --loadmodule falkordb.so --port 6379`; `python scripts/health.py`; `python scripts/seed.py` (x2); `python scripts/demo_impact.py`; `pytest -q -m "not db"`; `pytest -q -m db`; `FALKORDB_PORT=1 pytest -q -m db -rs`; `pytest -q`; scratch-graph prototypes (deleted).

## Known problems / limits
- `falkordblite` is a sandbox-only tool, not in requirements.txt.
- Impact analysis traverses only AFFECTS + DEPENDS_ON from Task/Decision sources; Memory/Person/Agent sources are `unsupported_type`.
- Shortest path only (plus `path_count`); alternate paths are not returned.

## Exact next task
1. On your machine: `docker start echo-falkordb`, then `python scripts/health.py`, `python scripts/seed.py` (twice), `python scripts/demo_impact.py`, `pytest -q`. Report any failure.
2. Stage 3: add `src/echo/memory.py` write API (`record_decision`, `record_task`, `link_*`, `record_memory` with provenance via RECORDED_BY, supersede a decision) + recall queries (memories about an entity, decision history via SUPERSEDES). Tests: db-marked, prefix/dataset namespaced.
