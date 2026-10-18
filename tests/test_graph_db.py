"""Integration tests against a REAL FalkorDB (marker: db). Use only test-owned, uniquely tagged data."""
import uuid

import pytest

from echo import demo
from echo.db import health_check
from echo.queries import (get_dependencies, get_entity, impact_analysis, list_decisions,
                          list_projects, list_tasks)
from echo.seed import dataset_counts, delete_dataset, expected_counts, seed_graph
from echo.store import run

pytestmark = pytest.mark.db


def test_real_health_check(graph):
    h = health_check(graph.name)
    assert h["ok"] is True and h["error"] is None


def test_seed_is_idempotent(seeded):
    graph, prefix, dataset = seeded
    first = dataset_counts(graph, dataset)
    again = seed_graph(graph, prefix=prefix, dataset=dataset)
    exp = expected_counts()
    assert first == again
    assert again["nodes"] == again["distinct_node_ids"] == exp["nodes"]
    assert again["relationships"] == exp["relationships"]
    # no duplicate relationships between the same pair + type
    dup = run(graph, "MATCH (a {dataset:$ds})-[r]->(b {dataset:$ds}) "
                     "WITH a.id AS a, type(r) AS t, b.id AS b, count(r) AS c WHERE c > 1 RETURN count(*)",
              {"ds": dataset}).result_set[0][0]
    assert dup == 0


def test_demo_multi_hop_matches_documented_expected(seeded):
    graph, prefix, _ = seeded
    result, problems, text = demo.run_demo(graph, prefix)
    assert problems == []
    assert max(a["hops"] for a in result.affected) >= 3  # genuinely multi-hop
    assert f"{prefix}task-beta" in text  # explanation generated from live data


def test_results_unique_and_deterministically_ordered(seeded):
    graph, prefix, _ = seeded
    a = impact_analysis(graph, prefix + "dec-auth-v2")
    b = impact_analysis(graph, prefix + "dec-auth-v2")
    ids = [x["id"] for x in a.affected]
    assert len(ids) == len(set(ids))
    assert ids == [x["id"] for x in b.affected]
    assert [(x["hops"], x["id"]) for x in a.affected] == sorted((x["hops"], x["id"]) for x in a.affected)
    beta = next(x for x in a.affected if x["id"].endswith("task-beta"))
    assert beta["path_count"] == 2  # two routes, but only one row


def test_task_change_impact(seeded):
    graph, prefix, _ = seeded
    r = impact_analysis(graph, prefix + "task-auth")
    assert r.status == "ok" and r.source["type"] == "Task"
    assert [x["id"][len(prefix):] for x in r.affected] == [
        "task-mobile-login", "task-user-profile", "task-onboarding", "task-push", "task-beta", "task-analytics"]
    assert "task-api-schema" not in [x["id"][len(prefix):] for x in r.affected]  # upstream is not downstream


def test_unrelated_branch_not_affected(seeded):
    graph, prefix, _ = seeded
    r = impact_analysis(graph, prefix + "dec-postgres")
    got = {x["id"][len(prefix):] for x in r.affected}
    assert "task-docs" in got and "task-api-schema" in got
    assert "task-branding" not in got and "task-landing" not in got


def test_leaf_task_has_no_impact(seeded):
    graph, prefix, _ = seeded
    r = impact_analysis(graph, prefix + "task-analytics")
    assert r.status == "no_impact" and r.affected == []


def test_depth_limit(seeded):
    graph, prefix, _ = seeded
    r = impact_analysis(graph, prefix + "dec-auth-v2", max_depth=1)
    assert [x["id"][len(prefix):] for x in r.affected] == ["task-auth", "task-mobile-login", "task-user-profile"]


def test_missing_malformed_and_unsupported_inputs(seeded):
    graph, prefix, _ = seeded
    assert impact_analysis(graph, prefix + "does-not-exist").status == "not_found"
    for bad in (None, "", "x; MATCH (n) DETACH DELETE n", 42):
        assert impact_analysis(graph, bad).status == "invalid_input"
    assert impact_analysis(graph, prefix + "person-maya").status == "unsupported_type"
    assert impact_analysis(graph, prefix + "task-auth", max_depth="abc").status == "ok"  # falls back to default depth


def test_dependencies_and_listings(seeded):
    graph, prefix, _ = seeded
    deps = get_dependencies(graph, prefix + "task-beta")
    assert [d["id"][len(prefix):] for d in deps][:2] == ["task-onboarding", "task-push"]
    assert "task-api-schema" in [d["id"][len(prefix):] for d in deps]
    assert get_dependencies(graph, "no such id") == []
    assert get_entity(graph, prefix + "task-auth")["type"] == "Task"
    assert get_entity(graph, prefix + "nope") is None
    mine = [p for p in list_projects(graph) if p["id"] == prefix + "proj-orion"]
    assert mine and mine[0]["task_count"] == 11
    assert len(list_tasks(graph, prefix + "proj-orion")) == 11
    sup = [d["id"][len(prefix):] for d in list_decisions(graph, "superseded") if d["id"].startswith(prefix)]
    assert sup == ["dec-auth-v1"]


def test_cleanup_only_removes_test_owned_data(graph):
    run_id = uuid.uuid4().hex[:8]
    ds_a, ds_b = f"test-a-{run_id}", f"test-b-{run_id}"
    seed_graph(graph, prefix=f"a{run_id}-", dataset=ds_a)
    seed_graph(graph, prefix=f"b{run_id}-", dataset=ds_b)
    try:
        delete_dataset(graph, ds_a)
        assert dataset_counts(graph, ds_a)["nodes"] == 0
        assert dataset_counts(graph, ds_b)["nodes"] == expected_counts()["nodes"]
    finally:
        delete_dataset(graph, ds_b)
        delete_dataset(graph, ds_a)
