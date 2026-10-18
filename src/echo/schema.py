"""Indexes + unique constraints on `id` for every node label. Safe to re-run."""
from __future__ import annotations

from falkordb import Graph

from echo.store import NODE_LABELS


def ensure_schema(graph: Graph) -> None:
    for label in NODE_LABELS:
        try:
            graph.create_node_range_index(label, "id")
        except Exception as exc:
            if "already indexed" not in str(exc).lower():
                raise
        try:
            graph.create_node_unique_constraint(label, "id")
        except Exception as exc:
            if "already" not in str(exc).lower():
                raise
