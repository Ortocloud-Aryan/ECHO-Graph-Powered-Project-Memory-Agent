
"""FalkorDB connection + health check (official `falkordb` client)."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from falkordb import FalkorDB, Graph

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 6379
DEFAULT_GRAPH = "echo"


class EchoDBError(RuntimeError):
    """Raised when FalkorDB cannot be reached or a query fails."""


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    graph: str
    username: Optional[str]
    password: Optional[str]


def get_settings() -> Settings:
    """Read settings from environment, .env, or Streamlit Cloud secrets."""
    load_dotenv()

    def setting(name: str) -> str:
        # Environment variables and local .env take priority.
        value = os.getenv(name, "").strip()
        if value:
            return value

        # Fall back to Streamlit Cloud Secrets when deployed.
        try:
            import streamlit as st

            value = st.secrets.get(name, "")
            return str(value).strip() if value is not None else ""
        except Exception:
            return ""

    raw_port = setting("FALKORDB_PORT") or str(DEFAULT_PORT)

    try:
        port = int(raw_port)
    except ValueError as exc:
        raise EchoDBError(
            f"FALKORDB_PORT must be an integer, got {raw_port!r}"
        ) from exc

    return Settings(
        host=setting("FALKORDB_HOST") or DEFAULT_HOST,
        port=port,
        graph=setting("FALKORDB_GRAPH") or DEFAULT_GRAPH,
        username=setting("FALKORDB_USERNAME") or None,
        password=setting("FALKORDB_PASSWORD") or None,
    )


def get_graph(
    graph_name: Optional[str] = None,
    settings: Optional[Settings] = None,
) -> Graph:
    """Return a Graph handle. Connection is lazy; use health_check() to verify it."""
    s = settings or get_settings()
    kwargs = {"host": s.host, "port": s.port}

    if s.username:
        kwargs["username"] = s.username
    if s.password:
        kwargs["password"] = s.password

    try:
        client = FalkorDB(**kwargs)
    except Exception as exc:
        raise EchoDBError(
            f"Could not create FalkorDB client for {s.host}:{s.port}: {exc}"
        ) from exc

    return client.select_graph(graph_name or s.graph)


def health_check(
    graph_name: Optional[str] = None,
    settings: Optional[Settings] = None,
) -> dict:
    """Run a real RETURN 1 query and report connection health."""
    s = settings or get_settings()
    name = graph_name or s.graph

    info = {
        "ok": False,
        "host": s.host,
        "port": s.port,
        "graph": name,
        "latency_ms": None,
        "error": None,
    }

    start = time.perf_counter()

    try:
        graph = get_graph(name, s)
        rows = graph.query("RETURN 1 AS ok").result_set

        if rows != [[1]]:
            info["error"] = f"Unexpected health-check result: {rows!r}"
            return info

        info["ok"] = True
        info["latency_ms"] = round(
            (time.perf_counter() - start) * 1000, 1
        )

    except Exception as exc:
        info["error"] = (
            f"Cannot reach FalkorDB at {s.host}:{s.port} "
            f"({type(exc).__name__}: {exc}). "
            "Check the server, credentials, and network access."
        )

    return info
