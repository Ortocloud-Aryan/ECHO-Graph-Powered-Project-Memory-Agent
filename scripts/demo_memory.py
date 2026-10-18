"""Stage 3 demo: persistent project memory + decision history in real FalkorDB (SYNTHETIC data).

Isolated: every id is prefixed `m3demo-` and tagged dataset='synthetic-memory-demo'. Safe to re-run;
never deletes anything and never touches the Stage 2 dataset. Exit code 0 = PASS, 1 = FAIL.
Usage: python scripts/demo_memory.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from echo.db import EchoDBError, get_graph, health_check  # noqa: E402
from echo.explain import format_history, format_memories  # noqa: E402
from echo.memory import (EchoMemoryError, get_decision_history, get_memories_about,  # noqa: E402
                         link_affects, record_decision, record_memory, supersede_decision)
from echo.schema import ensure_schema  # noqa: E402
from echo.seed import DEFAULT_DATASET, dataset_counts  # noqa: E402
from echo.store import upsert_nodes, upsert_rels  # noqa: E402

P, DS = "m3demo-", "synthetic-memory-demo"
PROJ, AGENT, TASK = P + "proj", P + "agent", P + "task-auth"
D1, D2, M1, M2 = P + "dec-password", P + "dec-oauth", P + "mem-project", P + "mem-oauth"
TEXT1 = "Launch scope is 'auth first': nothing else ships before sign-in works."
TEXT2 = 'Team chose OAuth2 after the security review flagged "plain" password storage.'
EXPECTED = {"nodes": 7, "relationships": 11}


def tag(**kw):
    return {**kw, "synthetic": True, "dataset": DS}


def write_phase(g) -> list:
    """All writes are MERGE-based, so running this twice changes nothing. Returns `created` flags."""
    upsert_nodes(g, "Project", [tag(id=PROJ, name="Memory demo project (SYNTHETIC)", status="active")])
    upsert_nodes(g, "Agent", [tag(id=AGENT, name="ECHO Memory Agent (synthetic)", kind="assistant")])
    upsert_nodes(g, "Task", [tag(id=TASK, title="Implement authentication", status="todo", priority="high")])
    upsert_rels(g, "PART_OF", "Task", "Project", [(TASK, PROJ)])
    created = [
        record_memory(g, TEXT1, PROJ, AGENT, kind="scope", memory_id=M1, recorded_at="2026-03-01T09:00:00+00:00",
                      source="demo-script", dataset=DS)["created"],
        record_decision(g, D1, "Use email+password auth", rationale="Simplest to build.", decided_at="2026-01-10",
                        project_id=PROJ, recorded_by_id=AGENT, dataset=DS)["created"],
        record_decision(g, D2, "Switch to OAuth2 sign-in", rationale="Security review.", decided_at="2026-02-05",
                        project_id=PROJ, recorded_by_id=AGENT, dataset=DS)["created"],
        link_affects(g, D2, TASK)["created"],
        supersede_decision(g, D2, D1)["created"],
        record_memory(g, TEXT2, D2, AGENT, kind="decision_rationale", memory_id=M2,
                      recorded_at="2026-02-05T10:00:00+00:00", dataset=DS)["created"],
    ]
    return created


def main() -> int:
    h = health_check()
    if not h["ok"]:
        print(f"FAILED health check: {h['error']}")
        return 1
    g = get_graph()
    print(f"[synthetic data] graph={h['graph']!r}, dataset={DS!r}\n")
    try:
        ensure_schema(g)
        stage2_before = dataset_counts(g, DEFAULT_DATASET)
        write_phase(g)
        after_first = dataset_counts(g, DS)
        second = write_phase(g)                      # idempotency: same writes again
        after_second = dataset_counts(g, DS)
        stage2_after = dataset_counts(g, DEFAULT_DATASET)

        mem_proj = get_memories_about(g, PROJ)
        mem_dec = get_memories_about(g, D2)
        hist = get_decision_history(g, D1)
        missing = get_memories_about(g, P + "no-such-entity")
    except (EchoDBError, EchoMemoryError) as exc:
        print(f"FAILED: {type(exc).__name__}: {exc}")
        return 1

    print(format_memories(mem_proj), "\n")
    print(format_memories(mem_dec), "\n")
    print(format_history(hist), "\n")
    print(f"Missing subject -> status={missing.status!r}: {missing.message}\n")

    chain_ids = [c["id"] for c in hist.chain]
    checks = [
        ("project memory retrieved with exact text", [m["content"] for m in mem_proj.memories] == [TEXT1]),
        ("memory ABOUT + RECORDED_BY evidence present",
         ("ABOUT", M1, PROJ) in mem_proj.memories[0]["evidence"] and ("RECORDED_BY", M1, AGENT) in mem_proj.memories[0]["evidence"]),
        ("decision memory retrieved with exact text", [m["content"] for m in mem_dec.memories] == [TEXT2]),
        ("history oldest->newest is [password, oauth]", chain_ids == [D1, D2]),
        ("newer SUPERSEDES older edge in graph", hist.edges == [(D2, "SUPERSEDES", D1)]),
        ("only newest decision is current", [c["id"] for c in hist.chain if c["is_current"]] == [D2]),
        ("superseded decision kept, status 'superseded'", hist.chain[0]["status"] == "superseded"),
        ("missing subject reported as not_found", missing.status == "not_found"),
        ("second write pass created nothing new", not any(second)),
        ("counts identical after re-run", after_first == after_second),
        (f"demo dataset has expected size {EXPECTED}",
         (after_second["nodes"], after_second["relationships"]) == (EXPECTED["nodes"], EXPECTED["relationships"])),
        ("Stage 2 dataset untouched", stage2_before == stage2_after),
    ]
    for name, ok in checks:
        print(f"  [{'ok' if ok else 'FAIL'}] {name}")
    print(f"\nStage 2 dataset counts: {stage2_after} (0 nodes just means scripts/seed.py was never run here)")
    if all(ok for _, ok in checks):
        print("\nPASS: Stage 3 persistent memory demo verified against real FalkorDB.")
        return 0
    print("\nFAIL: see [FAIL] lines above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
