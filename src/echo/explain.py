"""Turns query results into text. Pure functions of the result data - no DB access, no hardcoded answers."""
from __future__ import annotations

from echo.queries import ImpactResult


def format_path(node_ids: list[str], rels: list[tuple]) -> str:
    """Render a path with real edge directions, e.g. A -[AFFECTS]-> B <-[DEPENDS_ON]- C."""
    out = [node_ids[0]]
    for left, right, (rtype, start, _end) in zip(node_ids, node_ids[1:], rels):
        out.append(f"-[{rtype}]-> {right}" if start == left else f"<-[{rtype}]- {right}")
    return " ".join(out)


def format_impact(result: ImpactResult) -> str:
    if result.status in ("invalid_input", "not_found", "unsupported_type"):
        return f"Cannot analyze {result.entity_id!r}: {result.message}"
    src = result.source
    head = f"Change to {src['type']} {src['id']} ({src['title']})"
    if result.status == "no_impact":
        return f"{head}: no downstream impact found."
    lines = [f"{head} impacts {len(result.affected)} task(s) (max depth {result.max_depth}):"]
    for a in result.affected:
        owners = ", ".join(a["owners"]) or "unassigned"
        extra = f", {a['path_count']} paths" if a["path_count"] > 1 else ""
        lines.append(f"  [{a['hops']} hop{'s' if a['hops'] != 1 else ''}{extra}] {a['id']} - {a['title']} "
                     f"(status: {a['status']}, owner: {owners})")
        lines.append(f"      evidence: {format_path(a['node_ids'], a['rels'])}")
    return "\n".join(lines)
