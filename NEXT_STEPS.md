# NEXT_STEPS

## Current stage
Stage 3 (persistent memory) - implemented and verified in the sandbox; UNCOMMITTED (by request). Next: re-verify on the user's Docker FalkorDB, commit, then Stage 4.

## Completed
- `src/echo/memory.py`: `record_memory`, `record_decision`, `supersede_decision`, `link_depends_on`, `link_affects`, `get_memories_about`, `get_decision_history` (+ `InvalidInput`, `EntityNotFound`, result dataclasses). Convention: `(newer)-[:SUPERSEDES]->(older)`; see docs/GRAPH_MODEL.md.
- `src/echo/explain.py`: added `format_memories`, `format_history` (existing functions untouched).
- `scripts/demo_memory.py` (isolated `m3demo-` ids, dataset `synthetic-memory-demo`, PASS/FAIL exit code), `tests/test_memory.py` (31 tests: 16 no-DB validation + 15 real-DB). README, BUILD_STATUS, docs/GRAPH_MODEL.md updated.

## Verified (actual runs, sandbox engine: falkordblite 0.10.0 FalkorDB module, Linux, Python 3.12, official falkordb 1.8.0 client)
- `pytest -q`: 63 passed (37 no-DB, 26 db). Baseline was 32. `pytest -q tests/test_memory.py -m db`: 15 passed.
- Mutation check: reversing ORDER BY, and reversing SUPERSEDES direction, made tests fail; code restored, tests green again.
- `python scripts/seed.py` x2 and `python scripts/demo_impact.py`: still 23 nodes / 47 rels, PASS (7 affected tasks).
- `python scripts/demo_memory.py` run twice on graph `echo`: both PASS (12/12 checks); dataset stays 7 nodes / 11 rels; Stage 2 dataset counts unchanged. `echo_test` has 0 leftover nodes.

## Unverified
- Everything on the user's Docker FalkorDB / Windows / Python 3.11 (user's repo is at commit f98bed1; this sandbox repo is a separate copy - diff before copying files over).
- `streamlit run app.py` (still placeholder).

## Commands to reproduce (PowerShell, venv active, FalkorDB running)
`pytest -q` ; `python scripts\seed.py` ; `python scripts\demo_impact.py` ; `python scripts\demo_memory.py`

## Known limits
- `get_entity` is an unlabeled id scan (fine at demo scale).
- History shows the single supersession line through a decision; branching lineages (one decision superseded by two) list all ancestors/descendants but are not drawn as a tree.
- A memory re-recorded with a different `about_id` and same `memory_id` gains a second ABOUT edge (multi-subject by design).
- Memory content max 2000 chars; no delete/update-memory API yet.

## Exact next task
1. Run the reproduce commands on your machine; report any failure, then `git add` + commit Stage 3.
2. Stage 4: `src/echo/tools.py` - agent-facing functions (`what_breaks_if_changed`, `recall`, `why_decision`) that call queries/memory and return {answer_text, evidence edges, raw rows}; tests; terminal demo. No LLM yet.
