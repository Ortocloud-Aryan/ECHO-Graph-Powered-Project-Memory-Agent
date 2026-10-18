"""Stage 3 tests. Validation tests need no DB; everything marked `db` runs real Cypher on FalkorDB
using the `seeded` fixture's private prefix/dataset (cleanup removes only that dataset)."""
import uuid

import pytest

from echo.explain import format_history, format_memories
from echo.memory import (EntityNotFound, InvalidInput, get_decision_history, get_memories_about,
                         link_affects, link_depends_on, record_decision, record_memory,
                         supersede_decision)
from echo.queries import impact_analysis
from echo.seed import DEFAULT_DATASET, dataset_counts, delete_dataset, seed_graph
from echo.store import run


# ---------------- unit: input validation (raises before touching the DB) ----------------
@pytest.mark.parametrize("bad", [None, "", "   ", 5, "x" * 2001])
def test_record_memory_rejects_bad_content(bad):
    with pytest.raises(InvalidInput):
        record_memory(None, bad, "task-auth")


@pytest.mark.parametrize("kw", [
    dict(about_id=""), dict(about_id="a b"), dict(about_id=None),
    dict(about_id="t", recorded_by_id="bad id"), dict(about_id="t", kind="Bad Kind"),
    dict(about_id="t", memory_id="x;y"), dict(about_id="t", dataset="no spaces"),
    dict(about_id="t", source="s" * 300),
])
def test_record_memory_rejects_bad_params(kw):
    with pytest.raises(InvalidInput):
        record_memory(None, "ok text", **kw)


def test_record_decision_rejects_bad_params():
    for kw in (dict(decision_id="", title="t"), dict(decision_id="d", title=""),
               dict(decision_id="d", title="t", status="maybe"),
               dict(decision_id="d", title="t", project_id="bad id")):
        with pytest.raises(InvalidInput):
            record_decision(None, **kw)


def test_self_links_rejected_before_db():
    with pytest.raises(InvalidInput):
        supersede_decision(None, "d1", "d1")
    with pytest.raises(InvalidInput):
        link_depends_on(None, "t1", "t1")


def test_reads_report_invalid_input_without_db():
    assert get_memories_about(None, "").status == "invalid_input"
    assert get_memories_about(None, "ok", limit=0).status == "invalid_input"
    assert get_memories_about(None, "ok", kind="Bad Kind").status == "invalid_input"
    assert get_decision_history(None, "a b").status == "invalid_input"


# ---------------- db: memories ----------------

@pytest.mark.db
def test_record_and_retrieve_memory(seeded):
    g, p, ds = seeded
    out = record_memory(g, "Beta needs onboarding and push.", p + "task-beta", p + "agent-echo",
                        kind="risk", source="standup", dataset=ds)
    assert out["created"] is True
    res = get_memories_about(g, p + "task-beta")
    mine = [m for m in res.memories if m["id"] == out["id"]]
    assert res.status == "ok" and len(mine) == 1
    m = mine[0]
    assert (m["content"], m["kind"], m["source"]) == ("Beta needs onboarding and push.", "risk", "standup")
    assert m["about"] == {"id": p + "task-beta", "type": "Task"}
    assert m["recorded_by"][0]["id"] == p + "agent-echo" and m["recorded_by"][0]["type"] == "Agent"
    assert m["recorded_at"]
    assert "ABOUT" in format_memories(res)


@pytest.mark.db
def test_relationships_exist_in_graph(seeded):
    g, p, ds = seeded
    mid = record_memory(g, "Rel check text", p + "task-auth", p + "person-maya", dataset=ds)["id"]
    rows = run(g, "MATCH (m:Memory {id:$m}) OPTIONAL MATCH (m)-[a:ABOUT]->(s) OPTIONAL MATCH (m)-[r:RECORDED_BY]->(w) "
                  "RETURN s.id, labels(s)[0], w.id, labels(w)[0], count(a), count(r)", {"m": mid}).result_set[0]
    assert rows == [p + "task-auth", "Task", p + "person-maya", "Person", 1, 1]


@pytest.mark.db
def test_no_recorder_or_source_is_not_invented(seeded):
    g, p, ds = seeded
    mid = record_memory(g, "Anonymous note", p + "task-docs", dataset=ds)["id"]
    row = run(g, "MATCH (m:Memory {id:$m}) OPTIONAL MATCH (m)-[r:RECORDED_BY]->() RETURN m.source, count(r)",
              {"m": mid}).result_set[0]
    assert row == [None, 0]
    m = [x for x in get_memories_about(g, p + "task-docs").memories if x["id"] == mid][0]
    assert m["recorded_by"] == [] and m["source"] is None
    assert not any(e[0] == "RECORDED_BY" for e in m["evidence"])


@pytest.mark.db
def test_record_memory_is_idempotent(seeded):
    g, p, ds = seeded
    a = record_memory(g, "Same text twice", p + "task-landing", p + "agent-echo", dataset=ds)
    ts1 = run(g, "MATCH (m:Memory {id:$m}) RETURN m.recorded_at", {"m": a["id"]}).result_set[0][0]
    b = record_memory(g, "Same text twice", p + "task-landing", p + "agent-echo", dataset=ds)
    assert (a["id"], a["created"], b["created"]) == (b["id"], True, False)
    n = run(g, "MATCH (m:Memory {id:$m})-[r]->() RETURN count(DISTINCT m), count(r)", {"m": a["id"]}).result_set[0]
    assert n == [1, 2]  # one node; exactly one ABOUT + one RECORDED_BY
    assert run(g, "MATCH (m:Memory {id:$m}) RETURN m.recorded_at", {"m": a["id"]}).result_set[0][0] == ts1


@pytest.mark.db
def test_quotes_and_injection_text_roundtrip(seeded):
    g, p, ds = seeded
    nasty = "It's \"quoted\" \\ back\\slash `tick` }); MATCH (n) DETACH DELETE n //"
    mid = record_memory(g, nasty, p + "task-branding", dataset=ds)["id"]
    got = [m for m in get_memories_about(g, p + "task-branding").memories if m["id"] == mid][0]
    assert got["content"] == nasty
    assert dataset_counts(g, ds)["nodes"] > 20  # graph still intact


@pytest.mark.db
def test_missing_and_wrong_type_endpoints(seeded):
    g, p, ds = seeded
    with pytest.raises(EntityNotFound):
        record_memory(g, "x", p + "no-such-subject", dataset=ds)
    with pytest.raises(EntityNotFound):
        record_memory(g, "x", p + "task-auth", p + "no-such-agent", dataset=ds)
    with pytest.raises(InvalidInput):                      # recorder must be Agent/Person
        record_memory(g, "x", p + "task-auth", p + "task-beta", dataset=ds)
    with pytest.raises(InvalidInput):                      # memory id already used by another type
        record_memory(g, "x", p + "task-auth", memory_id=p + "task-beta", dataset=ds)
    assert run(g, "MATCH (m:Memory {content:'x'}) WHERE m.dataset = $ds RETURN count(m)", {"ds": ds}).result_set[0][0] == 0


@pytest.mark.db
def test_get_memories_statuses_and_ordering(seeded):
    g, p, ds = seeded
    assert get_memories_about(g, p + "nope").status == "not_found"
    assert get_memories_about(g, p + "task-push").memories[0]["id"] == p + "mem-002"   # seeded memory
    empty = get_memories_about(g, p + "person-raj")
    assert empty.status == "no_memories" and empty.memories == []
    for i, ts in enumerate(["2026-05-03", "2026-05-01", "2026-05-02"]):
        record_memory(g, f"ordered {i}", p + "proj-orion", memory_id=f"{p}ord-{i}", recorded_at=ts, kind="ordtest", dataset=ds)
    res = get_memories_about(g, p + "proj-orion", kind="ordtest")
    assert [m["recorded_at"] for m in res.memories] == ["2026-05-01", "2026-05-02", "2026-05-03"]
    assert len(get_memories_about(g, p + "proj-orion", kind="ordtest", limit=2).memories) == 2
    assert get_memories_about(g, p + "proj-orion", kind="nomatch").status == "no_memories"


# ---------------- db: decisions ----------------
@pytest.mark.db
def test_decision_chain_history_and_ordering(seeded):
    g, p, ds = seeded
    for i in (1, 2, 3):
        record_decision(g, f"{p}chain-{i}", f"Choice v{i}", decided_at=f"2026-06-0{i}", project_id=p + "proj-orion",
                        recorded_by_id=p + "agent-echo", dataset=ds)
    # supersede out of order on purpose
    assert supersede_decision(g, f"{p}chain-3", f"{p}chain-2")["created"] is True
    assert supersede_decision(g, f"{p}chain-2", f"{p}chain-1")["created"] is True
    for start in (1, 2, 3):                                  # same line from any starting point
        h = get_decision_history(g, f"{p}chain-{start}")
        assert h.status == "ok"
        assert [c["id"][len(p):] for c in h.chain] == ["chain-1", "chain-2", "chain-3"]
        assert [c["is_current"] for c in h.chain] == [False, False, True]
        assert [c["status"] for c in h.chain] == ["superseded", "superseded", "active"]
        assert h.edges == [(f"{p}chain-2", "SUPERSEDES", f"{p}chain-1"), (f"{p}chain-3", "SUPERSEDES", f"{p}chain-2")]
    assert "CURRENT" in format_history(get_decision_history(g, f"{p}chain-1"))
    # both old nodes preserved
    assert run(g, "MATCH (d:Decision) WHERE d.id STARTS WITH $x RETURN count(d)", {"x": p + "chain-"}).result_set[0][0] == 3


@pytest.mark.db
def test_supersede_duplicates_cycles_and_bad_endpoints(seeded):
    g, p, ds = seeded
    record_decision(g, p + "s-a", "A", dataset=ds)
    record_decision(g, p + "s-b", "B", dataset=ds)
    assert supersede_decision(g, p + "s-b", p + "s-a")["created"] is True
    assert supersede_decision(g, p + "s-b", p + "s-a")["created"] is False
    n = run(g, "MATCH (:Decision {id:$b})-[r:SUPERSEDES]->(:Decision {id:$a}) RETURN count(r)",
            {"a": p + "s-a", "b": p + "s-b"}).result_set[0][0]
    assert n == 1
    with pytest.raises(InvalidInput):                        # reverse would be a cycle
        supersede_decision(g, p + "s-a", p + "s-b")
    with pytest.raises(InvalidInput):                        # self
        supersede_decision(g, p + "s-a", p + "s-a")
    with pytest.raises(EntityNotFound):
        supersede_decision(g, p + "s-a", p + "ghost")
    with pytest.raises(InvalidInput):                        # not a decision
        supersede_decision(g, p + "s-a", p + "task-auth")
    assert get_decision_history(g, p + "s-a").edges == [(p + "s-b", "SUPERSEDES", p + "s-a")]  # unchanged


@pytest.mark.db
def test_history_statuses(seeded):
    g, p, ds = seeded
    record_decision(g, p + "lonely", "Standalone", dataset=ds)
    h = get_decision_history(g, p + "lonely")
    assert h.status == "no_history" and [c["id"] for c in h.chain] == [p + "lonely"] and h.edges == []
    assert get_decision_history(g, p + "ghost").status == "not_found"
    assert get_decision_history(g, p + "task-auth").status == "not_a_decision"
    seeded_h = get_decision_history(g, p + "dec-auth-v1")      # Stage 2 seed data is readable too
    assert [c["id"][len(p):] for c in seeded_h.chain][:2] == ["dec-auth-v1", "dec-auth-v2"]


@pytest.mark.db
def test_record_decision_idempotent_and_keeps_status(seeded):
    g, p, ds = seeded
    assert record_decision(g, p + "keep", "Keep status", dataset=ds)["created"] is True
    record_decision(g, p + "keep2", "Newer", dataset=ds)
    supersede_decision(g, p + "keep2", p + "keep")
    again = record_decision(g, p + "keep", "Keep status", dataset=ds)    # re-run must not un-supersede
    assert again["created"] is False
    assert run(g, "MATCH (d:Decision {id:$i}) RETURN d.status", {"i": p + "keep"}).result_set[0][0] == "superseded"
    with pytest.raises(InvalidInput):                                    # id used by a Task
        record_decision(g, p + "task-auth", "clash", dataset=ds)
    with pytest.raises(EntityNotFound):
        record_decision(g, p + "dx", "t", project_id=p + "no-proj", dataset=ds)


# ---------------- db: links ----------------
@pytest.mark.db
def test_link_depends_on_and_affects_feed_impact_analysis(seeded):
    g, p, ds = seeded
    record_decision(g, p + "dec-new", "New landing decision", dataset=ds)
    r1 = link_depends_on(g, p + "task-landing", p + "task-docs")      # landing now needs docs
    assert r1 == {"rel": "DEPENDS_ON", "from": p + "task-landing", "to": p + "task-docs", "created": True}
    assert link_depends_on(g, p + "task-landing", p + "task-docs")["created"] is False
    assert link_affects(g, p + "dec-new", p + "task-docs")["created"] is True
    assert link_affects(g, p + "dec-new", p + "task-docs")["created"] is False
    for rel, a, b in (("DEPENDS_ON", "task-landing", "task-docs"), ("AFFECTS", "dec-new", "task-docs")):
        assert run(g, f"MATCH (:{'Task' if rel == 'DEPENDS_ON' else 'Decision'} {{id:$a}})-[r:{rel}]->(:Task {{id:$b}}) RETURN count(r)",
                   {"a": p + a, "b": p + b}).result_set[0][0] == 1
    ids = [x["id"][len(p):] for x in impact_analysis(g, p + "dec-new").affected]   # Stage 2 query sees Stage 3 writes
    assert ids == ["task-docs", "task-landing"]


@pytest.mark.db
def test_link_validation_errors(seeded):
    g, p, ds = seeded
    with pytest.raises(EntityNotFound):
        link_depends_on(g, p + "task-auth", p + "ghost")
    with pytest.raises(InvalidInput):
        link_depends_on(g, p + "task-auth", p + "dec-auth-v1")        # wrong type
    with pytest.raises(InvalidInput):                                 # api-schema -> beta would close a cycle
        link_depends_on(g, p + "task-api-schema", p + "task-beta")
    with pytest.raises(InvalidInput):
        link_affects(g, p + "task-auth", p + "task-beta")             # source must be a Decision
    with pytest.raises(EntityNotFound):
        link_affects(g, p + "ghost", p + "task-beta")


# ---------------- db: isolation & cleanup ----------------
@pytest.mark.db
def test_stage2_demo_dataset_untouched(graph):
    run_id = uuid.uuid4().hex[:8]
    p, ds = f"iso{run_id}-", f"test-iso-{run_id}"
    before = dataset_counts(graph, DEFAULT_DATASET)
    seed_graph(graph, prefix=p, dataset=ds)
    try:
        record_memory(graph, "isolation", p + "task-auth", p + "agent-echo", dataset=ds)
        supersede_decision(graph, p + "dec-auth-v2", p + "dec-auth-v1")
        assert dataset_counts(graph, DEFAULT_DATASET) == before
        # memories about an un-prefixed id never leak in prefixed test data
        assert all(m["id"].startswith("mem-") or m["id"].startswith(p) for m in get_memories_about(graph, p + "task-auth").memories)
    finally:
        delete_dataset(graph, ds)
    assert dataset_counts(graph, ds)["nodes"] == 0
    assert dataset_counts(graph, DEFAULT_DATASET) == before


@pytest.mark.db
def test_memory_nodes_are_cleaned_by_dataset_only(graph):
    run_id = uuid.uuid4().hex[:8]
    pa, pb, da, db_ = f"a{run_id}-", f"b{run_id}-", f"test-a-{run_id}", f"test-b-{run_id}"
    seed_graph(graph, prefix=pa, dataset=da)
    seed_graph(graph, prefix=pb, dataset=db_)
    try:
        record_memory(graph, "A mem", pa + "task-auth", dataset=da)
        record_memory(graph, "B mem", pb + "task-auth", dataset=db_)
        delete_dataset(graph, da)
        assert get_memories_about(graph, pa + "task-auth").status == "not_found"
        assert [m["content"] for m in get_memories_about(graph, pb + "task-auth").memories] == ["B mem"]
    finally:
        delete_dataset(graph, db_)
        delete_dataset(graph, da)
