# ECHO graph model (Stage 2)

All demo data is **SYNTHETIC** (fake project "Orion Habit Tracker", fake people). Every demo node has `synthetic=true` and `dataset='synthetic-demo'`.

## Nodes
Every node has a stable unique `id` (index + UNIQUE constraint per label), `created_at` (ms timestamp, set on first create only).

| Label | Key properties |
|---|---|
| Project | name, status, description |
| Task | title, status (`todo`/`in_progress`/`done`), priority |
| Decision | title, status (`active`/`superseded`), rationale, decided_at |
| Person | name, role |
| Agent | name, kind |
| Memory | content, kind, recorded_at |

## Relationships
| Type | Direction | Meaning |
|---|---|---|
| DEPENDS_ON | Task -> Task | A needs B finished first |
| AFFECTS | Decision -> Task | decision changes the scope/approach of the task |
| OWNS | Person -> Task / Decision | accountability |
| WORKED_ON | Person / Agent -> Task | contribution history |
| SUPERSEDES | Decision -> Decision | newer replaces older |
| RECORDED_BY | Decision / Memory -> Agent / Person | provenance |
| PART_OF | Task / Decision -> Project | membership (added) |
| ABOUT | Memory -> Decision / Task | what a memory refers to (added) |

No Component/Fact nodes: a "project fact" is modeled as a Decision (or a Memory `ABOUT` one).

## Impact analysis (src/echo/queries.py)
Changing a **Decision** or **Task** impacts every Task reachable by: `AFFECTS` (0-1 hops from a decision), then `DEPENDS_ON` traversed *backwards* (anything that depends on an affected task, transitively, up to `max_depth`, default 6, max 10).

```cypher
MATCH p = (s:Decision {id: $id})-[:AFFECTS*0..1]->(m)<-[:DEPENDS_ON*0..6]-(t:Task)
WHERE t.id <> s.id
WITH t, p, length(p) AS hops, reduce(k = '', n IN nodes(p) | k + '>' + n.id) AS pkey
ORDER BY hops, t.id, pkey
WITH t, collect(p) AS paths                      -- one row per task, shortest path first
OPTIONAL MATCH (o:Person)-[:OWNS]->(t)
WITH t, paths, collect(o.name) AS owners
RETURN t.id, t.title, t.status, t.priority, length(paths[0]) AS hops, size(paths) AS path_count, owners,
       [n IN nodes(paths[0]) | n.id], [r IN relationships(paths[0]) | [type(r), startNode(r).id, endNode(r).id]]
ORDER BY hops, id
```
(`Decision` is replaced by `Task` for task sources.) Result per affected task: id, type, title, status, priority, owners, `hops`, `path_count` (all distinct routes), and the shortest path with real edge directions. Ordering: `(hops, id)`; ties between equal paths are broken by path ids.

Statuses returned by `impact_analysis`: `ok`, `no_impact`, `not_found`, `invalid_input` (id must match `[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}`), `unsupported_type` (only Task/Decision). Other read queries: `list_projects`, `list_tasks`, `list_decisions`, `get_dependencies` (upstream prerequisites), `get_entity`.

Note: `get_entity` does an unlabeled id lookup (full scan) - fine at demo scale.

## Synthetic task graph
`A -> B` means A DEPENDS_ON B.
```
task-api-schema <- task-auth <- task-mobile-login <- task-onboarding <- task-beta <- task-analytics
                         ^                                                ^
                         '-- task-user-profile <- task-push --------------'
task-api-schema <- task-docs          task-branding <- task-landing   (separate branches)
dec-auth-v2 -AFFECTS-> task-auth   dec-postgres -> task-api-schema   dec-fcm -> task-push
dec-auth-v2 -SUPERSEDES-> dec-auth-v1
```
Counts: 23 nodes (1 Project, 11 Task, 4 Decision, 3 Person, 1 Agent, 3 Memory), 47 relationships.

## Demo: change decision `dec-auth-v2` (switch to OAuth2)
Expected affected tasks (documented ground truth, also `echo.demo.EXPECTED`):

| Task | hops | paths | shortest path |
|---|---|---|---|
| task-auth | 1 | 1 | dec-auth-v2 -> task-auth |
| task-mobile-login | 2 | 1 | ... task-auth <- task-mobile-login |
| task-user-profile | 2 | 1 | ... task-auth <- task-user-profile |
| task-onboarding | 3 | 1 | ... task-mobile-login <- task-onboarding |
| task-push | 3 | 1 | ... task-user-profile <- task-push |
| task-beta | 4 | 2 | via onboarding (alphabetical tie-break) |
| task-analytics | 5 | 2 | via onboarding -> beta |

NOT affected: task-api-schema, task-docs, task-branding, task-landing, other decisions.

Reproduce: `python scripts/seed.py` then `python scripts/demo_impact.py` (prints the explanation, the Cypher, and PASS/MISMATCH).
