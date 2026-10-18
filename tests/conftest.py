"""Shared fixtures. DB tests skip (with the real reason) if FalkorDB is unreachable."""
import os
import uuid

import pytest

from echo.db import get_graph, health_check
from echo.seed import delete_dataset, seed_graph


def _test_graph_name() -> str:
    return os.getenv("ECHO_TEST_GRAPH", "").strip() or "echo_test"


@pytest.fixture(scope="module")
def graph():
    name = _test_graph_name()
    h = health_check(name)
    if not h["ok"]:
        pytest.skip(f"FalkorDB not reachable: {h['error']}")
    return get_graph(name)


@pytest.fixture(scope="module")
def seeded(graph):
    """Seed a private copy of the synthetic dataset (unique id prefix + dataset tag); remove only it afterwards."""
    run_id = uuid.uuid4().hex[:8]
    prefix, dataset = f"t{run_id}-", f"test-{run_id}"
    seed_graph(graph, prefix=prefix, dataset=dataset)
    yield graph, prefix, dataset
    delete_dataset(graph, dataset)
