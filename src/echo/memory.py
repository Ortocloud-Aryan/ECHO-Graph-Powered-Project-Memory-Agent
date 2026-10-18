"""Persistent project memory in FalkorDB: write API + recall queries.

Conventions (also in docs/GRAPH_MODEL.md):
  * SUPERSEDES direction:  (newer:Decision)-[:SUPERSEDES]->(older:Decision)
  * (Memory)-[:ABOUT]->(subject)         subject = any non-Memory node
  * (Memory|Decision)-[:RECORDED_BY]->(Agent|Person)   only when a recorder is supplied
  * (Task)-[:DEPENDS_ON]->(prerequisite Task);  (Decision)-[:AFFECTS]->(Task)
Writes validate input first (no DB touched on bad input), then check endpoints exist and have the
right type, then MERGE (idempotent). Writes raise InvalidInput / EntityNotFound; reads return a
result object whose `status` says what happened.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha1
from typing import Optional

from falkordb import Graph

from echo.queries import clean_id, get_entity
from echo.store import NODE_LABELS, run, upsert_nodes, upsert_rels

MAX_CONTENT = 2000
MAX_TITLE = 200
MAX_HISTORY_DEPTH = 20
DECISION_STATUSES = ("active", "superseded")
ABOUT_TYPES = tuple(l for l in NODE_LABELS if l != "Memory")
RECORDER_TYPES = ("Agent", "Person")
_KIND_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_DATASET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")


class EchoMemoryError(Exception):
    """Base class for memory-layer errors."""


class InvalidInput(EchoMemoryError, ValueError):
    """Input is malformed, or an entity has the wrong type, or the link would be illegal."""


class EntityNotFound(EchoMemoryError, LookupError):
    """A referenced entity id does not exist in the graph."""


# ---------- validation helpers (pure; run before any DB access) ----------
def _text(value, name: str, max_len: int, required: bool = True) -> Optional[str]:
    if value is None:
        if required:
            raise InvalidInput(f"{name} is required")
        return None
    if not isinstance(value, str) or (required and not value.strip()):
        raise InvalidInput(f"{name} must be a non-empty string" if required else f"{name} must be a string")
    value = value.strip()
    if not value and not required:
        return None
    if len(value) > max_len:
        raise InvalidInput(f"{name} is too long ({len(value)} > {max_len} chars)")
    return value


def _ident(value, name: str) -> str:
    cid = clean_id(value)
    if cid is None:
        raise InvalidInput(f"{name} must be 1-128 chars: letters, digits, _ . : - (got {value!r})")
    return cid


def _kind(value) -> str:
    if not isinstance(value, str) or not _KIND_RE.match(value):
        raise InvalidInput(f"kind must match {_KIND_RE.pattern} (got {value!r})")
    return value


def _dataset(value) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str) or not _DATASET_RE.match(value):
        raise InvalidInput(f"dataset must match {_DATASET_RE.pattern} (got {value!r})")
    return value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _require(graph: Graph, entity_id: str, types: tuple, name: str) -> dict:
    ent = get_entity(graph, entity_id)
    if ent is None:
        raise EntityNotFound(f"{name}: no entity with id {entity_id!r}")
    if ent["type"] not in types:
        raise InvalidInput(f"{name}: {entity_id!r} is a {ent['type']}, expected {' or '.join(types)}")
    return ent


def _rel_exists(graph: Graph, rel: str, src_label: str, dst_label: str, src: str, dst: str) -> bool:
    q = f"MATCH (a:{src_label} {{id: $s}})-[r:{rel}]->(b:{dst_label} {{id: $d}}) RETURN count(r)"
    return run(graph, q, {"s": src, "d": dst}).result_set[0][0] > 0


def _path_exists(graph: Graph, rel: str, label: str, start: str, end: str) -> bool:
    """True if `start` reaches `end` following `rel` edges (used to refuse cycles)."""
    q = (f"MATCH p = (a:{label} {{id: $a}})-[:{rel}*1..50]->(b:{label} {{id: $b}}) "
         "RETURN count(p) LIMIT 1")
    return run(graph, q, {"a": start, "b": end}).result_set[0][0] > 0


# ---------- writes ----------
def record_memory(graph: Graph, content: str, about_id: str, recorded_by_id: Optional[str] = None, *,
                  kind: str = "note", source: Optional[str] = None, memory_id: Optional[str] = None,
                  recorded_at: Optional[str] = None, dataset: Optional[str] = None) -> dict:
    """Store a Memory node ABOUT a subject; RECORDED_BY only if `recorded_by_id` is given.

    Without `memory_id` the id is derived from (about_id, kind, content), so recording the same
    memory twice is a no-op. `recorded_at` defaults to now (UTC) on first creation and is never
    overwritten. `source` is stored only if supplied. Returns {"id", "created", ...}.
    """
    content = _text(content, "content", MAX_CONTENT)
    about = _ident(about_id, "about_id")
    recorder = _ident(recorded_by_id, "recorded_by_id") if recorded_by_id is not None else None
    kind = _kind(kind)
    source = _text(source, "source", 200, required=False)
    recorded_at = _text(recorded_at, "recorded_at", 40, required=False)
    dataset = _dataset(dataset)
    mid = _ident(memory_id, "memory_id") if memory_id is not None else \
        "mem-" + sha1(f"{about}\x1f{kind}\x1f{content}".encode("utf-8")).hexdigest()[:12]

    subject = _require(graph, about, ABOUT_TYPES, "about_id")
    if recorder:
        rec = _require(graph, recorder, RECORDER_TYPES, "recorded_by_id")
    existing = get_entity(graph, mid)
    if existing is not None and existing["type"] != "Memory":
        raise InvalidInput(f"memory_id {mid!r} already used by a {existing['type']}")

    props = {"content": content, "kind": kind, "source": source, "dataset": dataset}
    upsert_nodes(graph, "Memory", [{"id": mid, **{k: v for k, v in props.items() if v is not None}}])
    run(graph, "MATCH (m:Memory {id: $id}) SET m.recorded_at = coalesce(m.recorded_at, $ts)",
        {"id": mid, "ts": recorded_at or _now()})
    upsert_rels(graph, "ABOUT", "Memory", subject["type"], [(mid, about)])
    if recorder:
        upsert_rels(graph, "RECORDED_BY", "Memory", rec["type"], [(mid, recorder)])
    return {"id": mid, "created": existing is None, "about": about, "recorded_by": recorder}


def record_decision(graph: Graph, decision_id: str, title: str, *, rationale: Optional[str] = None,
                    status: Optional[str] = None, decided_at: Optional[str] = None,
                    project_id: Optional[str] = None, recorded_by_id: Optional[str] = None,
                    dataset: Optional[str] = None) -> dict:
    """Create/update a Decision. `status` defaults to 'active' on creation and is left unchanged on
    re-record (so re-running a script never un-supersedes a decision)."""
    did = _ident(decision_id, "decision_id")
    title = _text(title, "title", MAX_TITLE)
    rationale = _text(rationale, "rationale", MAX_CONTENT, required=False)
    decided_at = _text(decided_at, "decided_at", 40, required=False)
    if status is not None and status not in DECISION_STATUSES:
        raise InvalidInput(f"status must be one of {DECISION_STATUSES} (got {status!r})")
    project = _ident(project_id, "project_id") if project_id is not None else None
    recorder = _ident(recorded_by_id, "recorded_by_id") if recorded_by_id is not None else None
    dataset = _dataset(dataset)

    if project:
        _require(graph, project, ("Project",), "project_id")
    if recorder:
        rec = _require(graph, recorder, RECORDER_TYPES, "recorded_by_id")
    existing = get_entity(graph, did)
    if existing is not None and existing["type"] != "Decision":
        raise InvalidInput(f"decision_id {did!r} already used by a {existing['type']}")

    props = {"title": title, "rationale": rationale, "decided_at": decided_at, "dataset": dataset}
    upsert_nodes(graph, "Decision", [{"id": did, **{k: v for k, v in props.items() if v is not None}}])
    run(graph, "MATCH (d:Decision {id: $id}) SET d.status = coalesce($st, d.status, 'active')",
        {"id": did, "st": status})
    if project:
        upsert_rels(graph, "PART_OF", "Decision", "Project", [(did, project)])
    if recorder:
        upsert_rels(graph, "RECORDED_BY", "Decision", rec["type"], [(did, recorder)])
    return {"id": did, "created": existing is None}


def _link(graph: Graph, rel: str, src_label: str, dst_label: str, src_id, dst_id,
          src_name: str, dst_name: str, forbid_cycle: bool = False) -> dict:
    src, dst = _ident(src_id, src_name), _ident(dst_id, dst_name)
    if src == dst:
        raise InvalidInput(f"{src_name} and {dst_name} must differ (got {src!r} twice)")
    _require(graph, src, (src_label,), src_name)
    _require(graph, dst, (dst_label,), dst_name)
    if forbid_cycle and _path_exists(graph, rel, src_label, dst, src):
        raise InvalidInput(f"{src!r} -[{rel}]-> {dst!r} would create a cycle ({dst!r} already reaches {src!r})")
    created = not _rel_exists(graph, rel, src_label, dst_label, src, dst)
    upsert_rels(graph, rel, src_label, dst_label, [(src, dst)])
    return {"rel": rel, "from": src, "to": dst, "created": created}


def link_depends_on(graph: Graph, task_id: str, depends_on_id: str) -> dict:
    """(task)-[:DEPENDS_ON]->(prerequisite). Both must be Tasks; cycles are refused."""
    return _link(graph, "DEPENDS_ON", "Task", "Task", task_id, depends_on_id,
                 "task_id", "depends_on_id", forbid_cycle=True)


def link_affects(graph: Graph, decision_id: str, task_id: str) -> dict:
    """(decision)-[:AFFECTS]->(task)."""
    return _link(graph, "AFFECTS", "Decision", "Task", decision_id, task_id, "decision_id", "task_id")


def supersede_decision(graph: Graph, new_id: str, old_id: str) -> dict:
    """(new)-[:SUPERSEDES]->(old); marks `old` as 'superseded'. Both nodes are kept.
    Refuses self-supersession and cycles. Re-running is a no-op."""
    res = _link(graph, "SUPERSEDES", "Decision", "Decision", new_id, old_id,
                "new_id", "old_id", forbid_cycle=True)
    run(graph, "MATCH (d:Decision {id: $id}) SET d.status = 'superseded'", {"id": res["to"]})
    return res


# ---------- reads ----------
@dataclass
class MemoryResult:
    status: str                        # ok | no_memories | not_found | invalid_input
    entity_id: str
    memories: list[dict] = field(default_factory=list)
    message: str = ""


@dataclass
class DecisionHistory:
    status: str                        # ok | no_history | not_found | invalid_input | not_a_decision
    decision_id: str
    chain: list[dict] = field(default_factory=list)    # oldest -> newest
    edges: list[tuple] = field(default_factory=list)   # (newer_id, 'SUPERSEDES', older_id)
    message: str = ""


def get_memories_about(graph: Graph, entity_id: str, *, kind: Optional[str] = None,
                       limit: int = 50) -> MemoryResult:
    """Memories ABOUT an entity, oldest first (recorded_at, id). Each carries its evidence edges."""
    eid = clean_id(entity_id)
    if eid is None:
        return MemoryResult("invalid_input", str(entity_id), message="Entity id is malformed.")
    if kind is not None and not (isinstance(kind, str) and _KIND_RE.match(kind)):
        return MemoryResult("invalid_input", eid, message=f"Invalid kind {kind!r}.")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
        return MemoryResult("invalid_input", eid, message="limit must be an integer 1-200.")
    subject = get_entity(graph, eid)
    if subject is None:
        return MemoryResult("not_found", eid, message=f"No entity with id {eid!r}.")
    where = "WHERE m.kind = $kind " if kind else ""
    rs = run(graph,
             f"MATCH (m:Memory)-[:ABOUT]->(s {{id: $id}}) {where}"
             "OPTIONAL MATCH (m)-[:RECORDED_BY]->(r) "
             "WITH m, s, collect(r) AS recs "
             "RETURN m.id, m.content, m.kind, m.recorded_at, m.source, m.dataset, "
             "[x IN recs | [x.id, labels(x)[0], coalesce(x.name, x.title)]] "
             "ORDER BY m.recorded_at, m.id LIMIT $limit",
             {"id": eid, "kind": kind, "limit": limit}).result_set
    mems = []
    for mid, content, mkind, at, source, dataset, recs in rs:
        recs = sorted(recs, key=lambda x: x[0])
        evidence = [("ABOUT", mid, eid)] + [("RECORDED_BY", mid, x[0]) for x in recs]
        mems.append(dict(id=mid, content=content, kind=mkind, recorded_at=at, source=source,
                         about=dict(id=eid, type=subject["type"]),
                         recorded_by=[dict(id=x[0], type=x[1], name=x[2]) for x in recs],
                         evidence=evidence))
    if not mems:
        return MemoryResult("no_memories", eid, message=f"{subject['type']} {eid!r} exists but has no memories.")
    return MemoryResult("ok", eid, mems)


def get_decision_history(graph: Graph, decision_id: str) -> DecisionHistory:
    """The supersession line through a decision: every older decision it (transitively) replaced and
    every newer one that replaced it, oldest first. Built from SUPERSEDES edges in the graph."""
    did = clean_id(decision_id)
    if did is None:
        return DecisionHistory("invalid_input", str(decision_id), message="Decision id is malformed.")
    ent = get_entity(graph, did)
    if ent is None:
        return DecisionHistory("not_found", did, message=f"No entity with id {did!r}.")
    if ent["type"] != "Decision":
        return DecisionHistory("not_a_decision", did, message=f"{did!r} is a {ent['type']}, not a Decision.")
    n = MAX_HISTORY_DEPTH
    older = run(graph, f"MATCH p = (:Decision {{id: $id}})-[:SUPERSEDES*1..{n}]->(o:Decision) "
                       "WITH o, min(length(p)) AS dist "
                       "RETURN o.id, o.title, o.status, o.decided_at, dist", {"id": did}).result_set
    newer = run(graph, f"MATCH p = (w:Decision)-[:SUPERSEDES*1..{n}]->(:Decision {{id: $id}}) "
                       "WITH w, min(length(p)) AS dist "
                       "RETURN w.id, w.title, w.status, w.decided_at, dist", {"id": did}).result_set
    rows = [(r, -r[4]) for r in older] + [((did, ent["title"], ent["status"], None, 0), 0)] \
        + [(r, r[4]) for r in newer]
    ids = [r[0] for r, _ in rows]
    # fill decided_at for the focus decision and mark tips (decisions nothing supersedes)
    meta = run(graph, "MATCH (d:Decision) WHERE d.id IN $ids OPTIONAL MATCH (x:Decision)-[:SUPERSEDES]->(d) "
                      "WITH d, count(x) AS replaced_by RETURN d.id, d.decided_at, replaced_by",
               {"ids": ids}).result_set
    info = {m[0]: (m[1], m[2] == 0) for m in meta}
    chain = []
    for (i, title, status, _dec, dist), pos in rows:
        decided_at, current = info[i]
        chain.append(dict(id=i, title=title, status=status, decided_at=decided_at, is_current=current,
                          relation="self" if pos == 0 else ("older" if pos < 0 else "newer"),
                          distance=abs(pos), _pos=pos))
    chain.sort(key=lambda c: (c["_pos"], c["decided_at"] or "", c["id"]))
    for c in chain:
        del c["_pos"]
    edges = [(a, "SUPERSEDES", b) for a, b in run(
        graph, "MATCH (a:Decision)-[:SUPERSEDES]->(b:Decision) WHERE a.id IN $ids AND b.id IN $ids "
               "RETURN a.id, b.id ORDER BY a.id, b.id", {"ids": ids}).result_set]
    if len(chain) == 1:
        return DecisionHistory("no_history", did, chain, edges, "Decision has no supersession relationships.")
    return DecisionHistory("ok", did, chain, edges)
