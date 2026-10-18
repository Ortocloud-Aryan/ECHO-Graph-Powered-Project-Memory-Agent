"""Idempotent SYNTHETIC demo dataset: 'Orion Habit Tracker' (all data is fake).

Nothing runs on import. Call seed_graph(graph) (see scripts/seed.py).
`prefix` namespaces ids and `dataset` tags every node, so tests can seed and
remove only their own data.
"""
from __future__ import annotations

from falkordb import Graph

from echo.schema import ensure_schema
from echo.store import upsert_nodes, upsert_rels, run

DEFAULT_DATASET = "synthetic-demo"
PROJECT = "proj-orion"

NODES = {
    "Project": [
        dict(id=PROJECT, name="Orion Habit Tracker (SYNTHETIC)", status="active",
             description="Fake mobile-app project used for ECHO demos."),
    ],
    "Task": [
        dict(id="task-api-schema", title="Define REST API schema", status="done", priority="high"),
        dict(id="task-auth", title="Implement authentication service", status="in_progress", priority="high"),
        dict(id="task-user-profile", title="Build user profile endpoints", status="todo", priority="medium"),
        dict(id="task-mobile-login", title="Build mobile login screen", status="todo", priority="high"),
        dict(id="task-push", title="Push notifications", status="todo", priority="medium"),
        dict(id="task-onboarding", title="Onboarding flow", status="todo", priority="medium"),
        dict(id="task-beta", title="Beta release", status="todo", priority="high"),
        dict(id="task-analytics", title="Analytics dashboard", status="todo", priority="low"),
        dict(id="task-docs", title="Write API docs", status="in_progress", priority="low"),
        dict(id="task-branding", title="Brand assets", status="done", priority="low"),
        dict(id="task-landing", title="Landing page", status="todo", priority="low"),
    ],
    "Decision": [
        dict(id="dec-auth-v1", title="Use email+password auth", status="superseded",
             rationale="Simplest to build.", decided_at="2026-01-10"),
        dict(id="dec-auth-v2", title="Switch to OAuth2 sign-in (Google/Apple)", status="active",
             rationale="Security review flagged password storage risk.", decided_at="2026-02-05"),
        dict(id="dec-postgres", title="Use PostgreSQL for storage", status="active",
             rationale="Relational data, team experience.", decided_at="2026-01-12"),
        dict(id="dec-fcm", title="Use FCM for push delivery", status="active",
             rationale="Cross-platform, free tier.", decided_at="2026-02-20"),
    ],
    "Person": [
        dict(id="person-maya", name="Maya Chen (synthetic)", role="Engineering Lead"),
        dict(id="person-raj", name="Raj Patel (synthetic)", role="Mobile Developer"),
        dict(id="person-lena", name="Lena Ortiz (synthetic)", role="Backend Developer"),
    ],
    "Agent": [
        dict(id="agent-echo", name="ECHO Memory Agent (synthetic)", kind="assistant"),
    ],
    "Memory": [
        dict(id="mem-001", kind="decision_rationale", recorded_at="2026-02-05",
             content="Team chose OAuth2 after the security review flagged password storage risk."),
        dict(id="mem-002", kind="note", recorded_at="2026-02-20",
             content="Push delivery depends on profile endpoints exposing device tokens."),
        dict(id="mem-003", kind="note", recorded_at="2026-03-01",
             content="Beta cannot ship until onboarding and push are both done."),
    ],
}

# (rel_type, src_label, dst_label, [(src_id, dst_id), ...])  -- src_id/dst_id are un-prefixed
T = "Task"
RELS = [
    ("PART_OF", "Task", "Project", [(t["id"], PROJECT) for t in NODES["Task"]]),
    ("PART_OF", "Decision", "Project", [(d["id"], PROJECT) for d in NODES["Decision"]]),
    # A DEPENDS_ON B  =>  A needs B first
    ("DEPENDS_ON", T, T, [
        ("task-auth", "task-api-schema"), ("task-docs", "task-api-schema"),
        ("task-user-profile", "task-auth"), ("task-mobile-login", "task-auth"),
        ("task-push", "task-user-profile"), ("task-onboarding", "task-mobile-login"),
        ("task-beta", "task-onboarding"), ("task-beta", "task-push"),
        ("task-analytics", "task-beta"), ("task-landing", "task-branding"),
    ]),
    ("AFFECTS", "Decision", T, [
        ("dec-auth-v2", "task-auth"), ("dec-postgres", "task-api-schema"), ("dec-fcm", "task-push"),
    ]),
    ("SUPERSEDES", "Decision", "Decision", [("dec-auth-v2", "dec-auth-v1")]),
    ("OWNS", "Person", T, [
        ("person-maya", "task-auth"), ("person-maya", "task-beta"),
        ("person-raj", "task-mobile-login"), ("person-raj", "task-onboarding"),
        ("person-lena", "task-api-schema"), ("person-lena", "task-user-profile"),
        ("person-lena", "task-push"),
    ]),
    ("OWNS", "Person", "Decision", [("person-maya", "dec-auth-v2")]),
    ("WORKED_ON", "Person", T, [("person-raj", "task-mobile-login"), ("person-lena", "task-api-schema")]),
    ("WORKED_ON", "Agent", T, [("agent-echo", "task-api-schema")]),
    ("RECORDED_BY", "Decision", "Agent", [("dec-auth-v2", "agent-echo")]),
    ("RECORDED_BY", "Memory", "Agent", [("mem-001", "agent-echo"), ("mem-002", "agent-echo")]),
    ("RECORDED_BY", "Memory", "Person", [("mem-003", "person-maya")]),
    ("ABOUT", "Memory", "Decision", [("mem-001", "dec-auth-v2")]),
    ("ABOUT", "Memory", T, [("mem-002", "task-push"), ("mem-003", "task-beta")]),
]


def expected_counts() -> dict:
    """Node/relationship counts a complete seed must produce (derived from the data above)."""
    return {"nodes": sum(len(v) for v in NODES.values()),
            "relationships": sum(len(pairs) for *_, pairs in RELS)}


def seed_graph(graph: Graph, prefix: str = "", dataset: str = DEFAULT_DATASET) -> dict:
    """MERGE the synthetic dataset. Re-running changes nothing. Returns counts in this dataset."""
    ensure_schema(graph)
    for label, rows in NODES.items():
        tagged = [{**r, "id": prefix + r["id"], "synthetic": True, "dataset": dataset} for r in rows]
        upsert_nodes(graph, label, tagged)
    for rel_type, src_label, dst_label, pairs in RELS:
        upsert_rels(graph, rel_type, src_label, dst_label, [(prefix + s, prefix + d) for s, d in pairs])
    return dataset_counts(graph, dataset)


def dataset_counts(graph: Graph, dataset: str = DEFAULT_DATASET) -> dict:
    n = run(graph, "MATCH (n {dataset: $ds}) RETURN count(n), count(DISTINCT n.id)", {"ds": dataset}).result_set[0]
    r = run(graph, "MATCH (a {dataset: $ds})-[r]->(b {dataset: $ds}) RETURN count(r)", {"ds": dataset}).result_set[0][0]
    return {"nodes": n[0], "distinct_node_ids": n[1], "relationships": r}


def delete_dataset(graph: Graph, dataset: str) -> None:
    """Delete ONLY nodes tagged with this dataset (never the whole graph). Refuses the demo dataset."""
    if dataset == DEFAULT_DATASET:
        raise ValueError("Refusing to delete the demo dataset via delete_dataset()")
    run(graph, "MATCH (n {dataset: $ds}) DETACH DELETE n", {"ds": dataset})
