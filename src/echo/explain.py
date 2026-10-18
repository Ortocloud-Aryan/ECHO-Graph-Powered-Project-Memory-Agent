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


def format_memories(result) -> str:
    """Text for a memory.MemoryResult (built only from the result data)."""
    if result.status != "ok":
        return f"{result.entity_id!r}: {result.message}"
    lines = [f"{len(result.memories)} memor{'y' if len(result.memories) == 1 else 'ies'} about {result.entity_id}:"]
    for m in result.memories:
        who = ", ".join(f"{r['name'] or r['id']} ({r['type']})" for r in m["recorded_by"]) or "no recorder stored"
        src = f", source: {m['source']}" if m["source"] else ""
        lines.append(f"  [{m['kind']}] {m['id']} @ {m['recorded_at']} - {m['content']}")
        lines.append(f"      recorded by: {who}{src}")
        lines.append("      evidence: " + "; ".join(f"{a} -[{t}]-> {b}" for t, a, b in m["evidence"]))
    return "\n".join(lines)


def format_history(history) -> str:
    """Text for a memory.DecisionHistory (built only from the result data)."""
    if history.status not in ("ok", "no_history"):
        return f"{history.decision_id!r}: {history.message}"
    lines = [f"Decision history around {history.decision_id} (oldest -> newest):"]
    for c in history.chain:
        tag = "CURRENT" if c["is_current"] else c["status"]
        lines.append(f"  {c['id']} [{tag}] {c['title']}" + (f" ({c['decided_at']})" if c["decided_at"] else ""))
    if history.edges:
        lines.append("  evidence: " + "; ".join(f"{a} -[{t}]-> {b}" for a, t, b in history.edges))
    else:
        lines.append(f"  {history.message}")
    return "\n".join(lines)
