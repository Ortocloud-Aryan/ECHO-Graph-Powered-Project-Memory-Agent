"""Documented SYNTHETIC demo: change decision `dec-auth-v2`, expect a known downstream task list.

EXPECTED is the documented ground truth (also in docs/GRAPH_MODEL.md); the explanation text is
always generated from the live query result, then compared with EXPECTED.
"""
from __future__ import annotations

from echo.explain import format_impact
from echo.queries import ImpactResult, impact_analysis

DEMO_CHANGE = "dec-auth-v2"

# task id -> (hops, path_count, shortest path node ids)
EXPECTED = {
    "task-auth":         (1, 1, ["dec-auth-v2", "task-auth"]),
    "task-mobile-login": (2, 1, ["dec-auth-v2", "task-auth", "task-mobile-login"]),
    "task-user-profile": (2, 1, ["dec-auth-v2", "task-auth", "task-user-profile"]),
    "task-onboarding":   (3, 1, ["dec-auth-v2", "task-auth", "task-mobile-login", "task-onboarding"]),
    "task-push":         (3, 1, ["dec-auth-v2", "task-auth", "task-user-profile", "task-push"]),
    "task-beta":         (4, 2, ["dec-auth-v2", "task-auth", "task-mobile-login", "task-onboarding", "task-beta"]),
    "task-analytics":    (5, 2, ["dec-auth-v2", "task-auth", "task-mobile-login", "task-onboarding",
                                 "task-beta", "task-analytics"]),
}
EXPECTED_ORDER = list(EXPECTED)  # sorted by (hops, id)


def compare(result: ImpactResult, prefix: str = "") -> list[str]:
    """Return a list of mismatches between a live result and EXPECTED (empty list = match)."""
    problems = []
    if result.status != "ok":
        return [f"status is {result.status!r}, expected 'ok'"]
    want_ids = [prefix + k for k in EXPECTED_ORDER]
    got_ids = [a["id"] for a in result.affected]
    if got_ids != want_ids:
        problems.append(f"affected tasks/order differ: got {got_ids}, expected {want_ids}")
    by_id = {a["id"]: a for a in result.affected}
    for key, (hops, count, path) in EXPECTED.items():
        a = by_id.get(prefix + key)
        if a is None:
            continue
        if a["hops"] != hops:
            problems.append(f"{a['id']}: hops {a['hops']} != {hops}")
        if a["path_count"] != count:
            problems.append(f"{a['id']}: path_count {a['path_count']} != {count}")
        if a["node_ids"] != [prefix + p for p in path]:
            problems.append(f"{a['id']}: path {a['node_ids']} != {[prefix + p for p in path]}")
    return problems


def run_demo(graph, prefix: str = ""):
    """Run the real impact query and return (result, mismatches, explanation_text)."""
    result = impact_analysis(graph, prefix + DEMO_CHANGE)
    return result, compare(result, prefix), format_impact(result)
