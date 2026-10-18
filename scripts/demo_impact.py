"""Run the documented multi-hop impact demo against real FalkorDB. Usage: python scripts/demo_impact.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from echo.db import EchoDBError, get_graph, health_check  # noqa: E402
from echo.demo import DEMO_CHANGE, run_demo  # noqa: E402


def main() -> int:
    h = health_check()
    if not h["ok"]:
        print(f"FAILED health check: {h['error']}")
        return 1
    try:
        result, problems, text = run_demo(get_graph())
    except EchoDBError as exc:
        print(f"Query failed: {exc}")
        return 1
    print(f"[synthetic data] graph={h['graph']!r}\n")
    print(text)
    print("\nCypher used:\n" + result.cypher)
    if problems:
        print("\nMISMATCH vs documented expected result:")
        for p in problems:
            print("  -", p)
        print("(Did you run scripts/seed.py first?)")
        return 1
    print(f"\nPASS: live result for {DEMO_CHANGE} matches the documented expected result.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
