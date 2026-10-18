"""Real Cypher health check. Usage: python scripts/health.py (exit 0 = healthy)"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from echo.db import health_check  # noqa: E402

h = health_check()
print(json.dumps(h, indent=2))
sys.exit(0 if h["ok"] else 1)
