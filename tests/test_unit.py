"""Unit tests: no database needed."""
import pytest

from echo import db
from echo.explain import format_impact, format_path
from echo.queries import ImpactResult, clean_id
from echo.seed import DEFAULT_DATASET, delete_dataset, expected_counts
from echo.store import upsert_nodes, upsert_rels


@pytest.fixture(autouse=True)
def no_dotenv(monkeypatch):
    monkeypatch.setattr(db, "load_dotenv", lambda: None)


def test_settings_defaults(monkeypatch):
    for k in ("FALKORDB_HOST", "FALKORDB_PORT", "FALKORDB_GRAPH", "FALKORDB_USERNAME", "FALKORDB_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    s = db.get_settings()
    assert (s.host, s.port, s.graph) == ("127.0.0.1", 6379, "echo")
    assert s.username is None and s.password is None


def test_settings_from_env_and_bad_port(monkeypatch):
    monkeypatch.setenv("FALKORDB_PORT", "6400")
    monkeypatch.setenv("FALKORDB_GRAPH", "mygraph")
    s = db.get_settings()
    assert (s.port, s.graph) == (6400, "mygraph")
    monkeypatch.setenv("FALKORDB_PORT", "abc")
    with pytest.raises(db.EchoDBError):
        db.get_settings()


def test_health_check_reports_unreachable_server():
    h = db.health_check(settings=db.Settings("127.0.0.1", 1, "echo", None, None))
    assert h["ok"] is False and "127.0.0.1:1" in h["error"]


@pytest.mark.parametrize("bad", [None, "", "   ", 5, "a b", "x;DROP", "-start", "a" * 200])
def test_clean_id_rejects_malformed(bad):
    assert clean_id(bad) is None


def test_clean_id_accepts_valid():
    assert clean_id("  task-auth ") == "task-auth"


def test_store_rejects_unknown_labels_before_querying():
    with pytest.raises(ValueError):
        upsert_nodes(None, "Task) DETACH DELETE (n", [{"id": "x"}])
    with pytest.raises(ValueError):
        upsert_rels(None, "HACKS", "Task", "Task", [("a", "b")])


def test_delete_dataset_refuses_demo_dataset():
    with pytest.raises(ValueError):
        delete_dataset(None, DEFAULT_DATASET)


def test_expected_counts_nonzero():
    c = expected_counts()
    assert c["nodes"] > 0 and c["relationships"] > 0


def test_format_path_uses_edge_direction():
    s = format_path(["d", "a", "b"], [("AFFECTS", "d", "a"), ("DEPENDS_ON", "b", "a")])
    assert s == "d -[AFFECTS]-> a <-[DEPENDS_ON]- b"


def test_format_impact_is_built_from_result_data():
    r = ImpactResult("ok", "x1", {"type": "Decision", "id": "x1", "title": "T"},
                     [dict(id="t9", title="Nine", status="todo", hops=1, path_count=1, owners=[],
                           node_ids=["x1", "t9"], rels=[("AFFECTS", "x1", "t9")])], 6)
    text = format_impact(r)
    assert "t9" in text and "unassigned" in text and "x1 -[AFFECTS]-> t9" in text


@pytest.mark.parametrize("status", ["not_found", "invalid_input", "unsupported_type"])
def test_format_impact_error_states(status):
    assert "Cannot analyze" in format_impact(ImpactResult(status, "zzz", message="m"))
