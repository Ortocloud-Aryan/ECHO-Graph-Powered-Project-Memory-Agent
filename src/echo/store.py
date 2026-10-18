"""Write helpers: idempotent MERGE upserts. Labels/rel types are allowlisted (cannot be parameterized in Cypher)."""
from __future__ import annotations

from typing import Iterable

from falkordb import Graph

from echo.db import EchoDBError

NODE_LABELS = ("Project", "Task", "Decision", "Person", "Agent", "Memory")
REL_TYPES = ("DEPENDS_ON", "AFFECTS", "OWNS", "WORKED_ON", "SUPERSEDES",
             "RECORDED_BY", "PART_OF", "ABOUT")


def run(graph: Graph, cypher: str, params: dict | None = None):
    """Execute Cypher, converting driver errors into EchoDBError."""
    try:
        return graph.query(cypher, params or {})
    except Exception as exc:
        raise EchoDBError(f"Cypher failed ({type(exc).__name__}): {exc}") from exc


def upsert_nodes(graph: Graph, label: str, rows: Iterable[dict]) -> int:
    """MERGE nodes by `id`; set/refresh other props; created_at only on first create."""
    if label not in NODE_LABELS:
        raise ValueError(f"Unknown node label: {label!r}")
    payload = [{"id": r["id"], "props": {k: v for k, v in r.items() if k != "id"}} for r in rows]
    if not payload:
        return 0
    res = run(graph,
              f"UNWIND $rows AS row MERGE (n:{label} {{id: row.id}}) "
              "ON CREATE SET n.created_at = timestamp() "
              "SET n += row.props RETURN count(n)", {"rows": payload})
    return res.result_set[0][0]


def upsert_rels(graph: Graph, rel_type: str, src_label: str, dst_label: str,
                pairs: Iterable[tuple[str, str]]) -> int:
    """MERGE relationships by (src id, type, dst id). Raises if an endpoint is missing."""
    if rel_type not in REL_TYPES:
        raise ValueError(f"Unknown relationship type: {rel_type!r}")
    if src_label not in NODE_LABELS or dst_label not in NODE_LABELS:
        raise ValueError(f"Unknown label in ({src_label!r}, {dst_label!r})")
    rows = [{"src": s, "dst": d} for s, d in pairs]
    if not rows:
        return 0
    res = run(graph,
              f"UNWIND $rows AS row MATCH (a:{src_label} {{id: row.src}}), (b:{dst_label} {{id: row.dst}}) "
              f"MERGE (a)-[r:{rel_type}]->(b) RETURN count(r)", {"rows": rows})
    n = res.result_set[0][0]
    if n != len(rows):
        raise EchoDBError(f"{rel_type}: {len(rows) - n} endpoint(s) missing among {src_label}->{dst_label} pairs")
    return n
