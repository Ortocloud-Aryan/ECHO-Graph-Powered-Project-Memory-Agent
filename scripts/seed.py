"""Seed the SYNTHETIC demo dataset into FalkorDB (idempotent). Usage: python scripts/seed.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from echo.db import EchoDBError, get_graph, health_check  # noqa: E402
from echo.seed import expected_counts, seed_graph  # noqa: E402


def main() -> int:
    h = health_check()
    if not h["ok"]:
        print(f"FAILED health check: {h['error']}")
        return 1
    print(f"Connected to {h['host']}:{h['port']} graph={h['graph']!r} ({h['latency_ms']} ms)")
    try:
        counts = seed_graph(get_graph())
    except EchoDBError as exc:
        print(f"Seed failed: {exc}")
        return 1
    print(f"Seeded synthetic dataset: {counts}")
    print(f"Expected:                 {expected_counts()}")
    return 0 if (counts["nodes"], counts["relationships"]) == tuple(expected_counts().values()) else 1


if __name__ == "__main__":
    sys.exit(main())
