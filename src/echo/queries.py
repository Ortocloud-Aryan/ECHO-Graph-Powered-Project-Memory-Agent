"""Read-only graph queries (real Cypher). No user-facing text here; see explain.py."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from falkordb import Graph

from echo.store import run

MAX_DEPTH_LIMIT = 10
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
IMPACT_SOURCES = ("Task", "Decision")  # entities whose change can be traced


def clean_id(value) -> Optional[str]:
    """Return a trimmed id if it looks valid, else None."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if _ID_RE.match(value) else None


def list_projects(graph: Graph) -> list[dict]:
    rs = run(graph, "MATCH (p:Project) OPTIONAL MATCH (t:Task)-[:PART_OF]->(p) "
                    "RETURN p.id, p.name, p.status, count(t) ORDER BY p.id").result_set
    return [dict(id=r[0], name=r[1], status=r[2], task_count=r[3]) for r in rs]


def list_tasks(graph: Graph, project_id: str) -> list[dict]:
    rs = run(graph, "MATCH (t:Task)-[:PART_OF]->(:Project {id: $pid}) "
                    "OPTIONAL MATCH (o:Person)-[:OWNS]->(t) "
                    "WITH t, collect(o.name) AS owners "
                    "RETURN t.id, t.title, t.status, t.priority, owners ORDER BY t.id",
             {"pid": project_id}).result_set
    return [dict(id=r[0], title=r[1], status=r[2], priority=r[3], owners=sorted(r[4])) for r in rs]


def list_decisions(graph: Graph, status: Optional[str] = None) -> list[dict]:
    where = "WHERE d.status = $status" if status else ""
    rs = run(graph, f"MATCH (d:Decision) {where} "
                    "OPTIONAL MATCH (d)-[:AFFECTS]->(t:Task) "
                    "WITH d, collect(t.id) AS affects "
                    "RETURN d.id, d.title, d.status, d.decided_at, affects ORDER BY d.id",
             {"status": status} if status else {}).result_set
    return [dict(id=r[0], title=r[1], status=r[2], decided_at=r[3], affects=sorted(r[4])) for r in rs]


def get_entity(graph: Graph, entity_id: str) -> Optional[dict]:
    """Look up any node by id (unlabeled scan - fine at demo scale). None if missing/invalid."""
    eid = clean_id(entity_id)
    if eid is None:
        return None
    rs = run(graph, "MATCH (n {id: $id}) RETURN labels(n)[0], n.id, coalesce(n.title, n.name), n.status",
             {"id": eid}).result_set
    return dict(type=rs[0][0], id=rs[0][1], title=rs[0][2], status=rs[0][3]) if rs else None


def get_dependencies(graph: Graph, task_id: str, max_depth: int = 6) -> list[dict]:
    """Upstream prerequisites of a task (what it needs first), nearest first."""
    tid, depth = clean_id(task_id), _clamp(max_depth)
    if tid is None:
        return []
    rs = run(graph, f"MATCH p = (t:Task {{id: $id}})-[:DEPENDS_ON*1..{depth}]->(d:Task) "
                    "WITH d, min(length(p)) AS hops RETURN d.id, d.title, d.status, hops ORDER BY hops, d.id",
             {"id": tid}).result_set
    return [dict(id=r[0], title=r[1], status=r[2], hops=r[3]) for r in rs]


# Impact semantics (all in one Cypher pattern):
#   source -[:AFFECTS*0..1]-> m <-[:DEPENDS_ON*0..N]- t
#   i.e. a Decision first AFFECTS tasks; then anything that DEPENDS_ON an affected task
#   (transitively) is downstream. A Task source skips the AFFECTS hop (0 length).
#   One row per affected task: shortest path (ties broken by path ids) + count of all paths.
_IMPACT_CYPHER = """
MATCH p = (s:{label} {{id: $id}})-[:AFFECTS*0..1]->(m)<-[:DEPENDS_ON*0..{depth}]-(t:Task)
WHERE t.id <> s.id
WITH t, p, length(p) AS hops, reduce(k = '', n IN nodes(p) | k + '>' + n.id) AS pkey
ORDER BY hops, t.id, pkey
WITH t, collect(p) AS paths
OPTIONAL MATCH (o:Person)-[:OWNS]->(t)
WITH t, paths, collect(o.name) AS owners
RETURN t.id AS id, labels(t)[0] AS type, t.title AS title, t.status AS status, t.priority AS priority,
       length(paths[0]) AS hops, size(paths) AS path_count, owners,
       [n IN nodes(paths[0]) | n.id] AS node_ids,
       [r IN relationships(paths[0]) | [type(r), startNode(r).id, endNode(r).id]] AS rels
ORDER BY hops, id
"""


@dataclass
class ImpactResult:
    status: str                      # ok | no_impact | not_found | invalid_input | unsupported_type
    entity_id: str
    source: Optional[dict] = None
    affected: list[dict] = field(default_factory=list)
    max_depth: int = 6
    message: str = ""
    cypher: str = ""


def _clamp(depth) -> int:
    try:
        return max(1, min(int(depth), MAX_DEPTH_LIMIT))
    except (TypeError, ValueError):
        return 6


def impact_analysis(graph: Graph, entity_id, max_depth: int = 6) -> ImpactResult:
    """Downstream impact of changing a Task or Decision, computed by FalkorDB."""
    depth = _clamp(max_depth)
    eid = clean_id(entity_id)
    if eid is None:
        return ImpactResult("invalid_input", str(entity_id), max_depth=depth,
                            message="Entity id must be 1-128 chars: letters, digits, _ . : -")
    source = get_entity(graph, eid)
    if source is None:
        return ImpactResult("not_found", eid, max_depth=depth, message=f"No entity with id {eid!r}.")
    if source["type"] not in IMPACT_SOURCES:
        return ImpactResult("unsupported_type", eid, source, max_depth=depth,
                            message=f"Impact analysis supports {', '.join(IMPACT_SOURCES)}; got {source['type']}.")
    cypher = _IMPACT_CYPHER.format(label=source["type"], depth=depth)
    rs = run(graph, cypher, {"id": eid}).result_set
    affected = [dict(id=r[0], type=r[1], title=r[2], status=r[3], priority=r[4], hops=r[5],
                     path_count=r[6], owners=sorted(r[7]), node_ids=r[8],
                     rels=[tuple(x) for x in r[9]]) for r in rs]
    return ImpactResult("ok" if affected else "no_impact", eid, source, affected, depth,
                        "" if affected else "Nothing depends on or is affected by this entity.", cypher.strip())
