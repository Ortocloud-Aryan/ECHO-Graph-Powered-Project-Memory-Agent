import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))
"""ECHO — Graph-Powered Project Memory Dashboard."""

import streamlit as st
import pandas as pd

from echo.db import get_graph, get_settings, health_check
from echo.queries import (
    list_projects,
    list_tasks,
    list_decisions,
    impact_analysis,
    get_dependencies,
)
from echo.memory import get_memories_about, get_decision_history
from echo.explain import format_path

st.set_page_config(
    page_title="ECHO | Project Intelligence",
    page_icon="🔗",
    layout="wide",
)

st.title("🔗 ECHO")
st.caption("Graph-powered project memory and dependency intelligence")

# Sidebar: connection details without exposing credentials.
with st.sidebar:
    st.header("Connection")
    try:
        settings = get_settings()
        st.write(f"**Host:** `{settings.host}`")
        st.write(f"**Port:** `{settings.port}`")
        st.write(f"**Graph:** `{settings.graph}`")
        if st.button("Check database connection", use_container_width=True):
            st.session_state["echo_health"] = health_check()
        health = st.session_state.get("echo_health")
        if health is not None:
            if health["ok"]:
                st.success(f"Connected · {health['latency_ms']} ms")
            else:
                st.error("Connection failed")
                st.caption(health.get("error") or "Unknown connection error")
    except Exception as exc:
        st.error("Could not load database settings")
        st.caption(str(exc))

    st.divider()
    page = st.radio(
        "Navigate",
        [
            "Overview",
            "Project Explorer",
            "Impact Analysis",
            "Memory & Decisions",
        ],
    )
    st.caption("Prototype · Uses your FalkorDB graph")

# Connect only when the page needs graph data.
@st.cache_resource
def connect_graph():
    return get_graph()


try:
    graph = connect_graph()
    graph.query("RETURN 1")
except Exception as exc:
    st.error("ECHO cannot connect to FalkorDB.")
    st.info(
        "Check your .env settings and confirm that your FalkorDB instance "
        "is running and reachable."
    )
    st.exception(exc)
    st.stop()


def graph_counts():
    nodes = graph.query("MATCH (n) RETURN count(n)").result_set[0][0]
    relationships = graph.query(
        "MATCH ()-[r]->() RETURN count(r)"
    ).result_set[0][0]
    return nodes, relationships


def show_table(rows):
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No records found.")


if page == "Overview":
    st.header("Project Overview")
    projects = list_projects(graph)
    decisions = list_decisions(graph)
    nodes, relationships = graph_counts()

    task_count = sum(p["task_count"] for p in projects)
    active_decisions = sum(
        1 for d in decisions if d.get("status") == "active"
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Projects", len(projects))
    c2.metric("Tasks", task_count)
    c3.metric("Decisions", len(decisions))
    c4.metric("Graph Relationships", relationships)

    st.subheader("Projects")
    show_table(projects)

    left, right = st.columns(2)
    with left:
        st.subheader("Decision Status")
        st.metric("Active decisions", active_decisions)
        st.metric("Superseded decisions", len(decisions) - active_decisions)
        show_table(decisions)
    with right:
        st.subheader("Graph Health")
        st.metric("Total nodes", nodes)
        st.metric("Total relationships", relationships)
        st.caption(
            "Counts are queried live from FalkorDB. "
            "They describe the connected graph, not model-generated estimates."
        )


elif page == "Project Explorer":
    st.header("Project Explorer")
    projects = list_projects(graph)

    if not projects:
        st.info("No projects found in the selected graph.")
    else:
        project_labels = {
            f"{p['name']} ({p['id']})": p["id"] for p in projects
        }
        selected_label = st.selectbox(
            "Choose a project", list(project_labels.keys())
        )
        project_id = project_labels[selected_label]
        selected_project = next(
            p for p in projects if p["id"] == project_id
        )

        st.subheader(selected_project["name"])
        st.write(f"**Project ID:** `{project_id}`")
        st.write(f"**Status:** {selected_project['status']}")

        tasks = list_tasks(graph, project_id)
        st.subheader("Tasks")
        show_table(tasks)

        if tasks:
            task_labels = {
                f"{t['title']} ({t['id']})": t["id"] for t in tasks
            }
            task_label = st.selectbox(
                "Inspect task dependencies", list(task_labels.keys())
            )
            task_id = task_labels[task_label]
            dependencies = get_dependencies(graph, task_id)

            st.subheader("Prerequisites")
            if dependencies:
                show_table(dependencies)
            else:
                st.info("No upstream prerequisites found for this task.")


elif page == "Impact Analysis":
    st.header("Impact Analysis")
    st.write(
        "Trace downstream tasks affected by a Task or Decision, "
        "using relationships stored in FalkorDB."
    )

    tasks = graph.query(
        "MATCH (t:Task) RETURN t.id, t.title ORDER BY t.id"
    ).result_set
    decisions = graph.query(
        "MATCH (d:Decision) RETURN d.id, d.title ORDER BY d.id"
    ).result_set

    entities = [
        (f"Task · {title} ({entity_id})", entity_id)
        for entity_id, title in tasks
    ] + [
        (f"Decision · {title} ({entity_id})", entity_id)
        for entity_id, title in decisions
    ]

    if not entities:
        st.info("No tasks or decisions are available for analysis.")
    else:
        labels = {label: entity_id for label, entity_id in entities}
        chosen = st.selectbox("Select the item changing", list(labels.keys()))
        depth = st.slider("Dependency search depth", 1, 10, 6)

        if st.button("Analyze impact", type="primary"):
            with st.spinner("Querying the graph..."):
                result = impact_analysis(graph, labels[chosen], depth)
            st.session_state["echo_impact"] = result

        result = st.session_state.get("echo_impact")
        if result is not None:
            if result.status == "ok":
                st.success(f"{len(result.affected)} affected task(s) found")
                for item in result.affected:
                    with st.expander(
                        f"{item['title']} · {item['id']} · "
                        f"{item['hops']} hop(s)"
                    ):
                        st.write(f"**Status:** {item['status']}")
                        st.write(f"**Priority:** {item['priority']}")
                        st.write(
                            f"**Owners:** "
                            f"{', '.join(item['owners']) or 'Unassigned'}"
                        )
                        st.write(f"**Distinct paths:** {item['path_count']}")
                        st.write("**Evidence path:**")
                        st.code(
                            " → ".join(item["node_ids"]),
                            language="text",
                        )
                        st.write("**Relationships:**")
                        for rel in item["rels"]:
                            st.write(f"`{rel[1]}` — **{rel[0]}** → `{rel[2]}`")
            elif result.status == "no_impact":
                st.info(result.message)
            else:
                st.warning(result.message or result.status)

            with st.expander("Inspect generated Cypher"):
                st.code(result.cypher or "No query generated.", language="cypher")


elif page == "Memory & Decisions":
    st.header("Persistent Memory & Decision History")
    st.caption(
        "Inspect recorded memories and decision supersession chains. "
        "This page reads existing records; it does not create new ones."
    )

    decisions = list_decisions(graph)
    if decisions:
        decision_labels = {
            f"{d['title']} ({d['id']})": d["id"] for d in decisions
        }
        selected_decision_label = st.selectbox(
            "Select a decision", list(decision_labels.keys())
        )
        decision_id = decision_labels[selected_decision_label]

        if st.button("Show decision history"):
            st.session_state["echo_history"] = get_decision_history(
                graph, decision_id
            )

        history = st.session_state.get("echo_history")
        if history is not None:
            st.subheader("Decision history")
            if history.chain:
                show_table(history.chain)
            else:
                st.info(history.message or "No history available.")

    st.divider()
    st.subheader("Memories about an entity")
    entity_id = st.text_input(
        "Entity ID",
        placeholder="e.g. task-auth-v2",
        help="Enter the exact ID of a node in the graph.",
    )

    if st.button("Retrieve memories"):
        st.session_state["echo_memories"] = get_memories_about(
            graph, entity_id
        )

    memory_result = st.session_state.get("echo_memories")
    if memory_result is not None:
        if memory_result.memories:
            for memory in memory_result.memories:
                with st.expander(
                    f"{memory['kind']} · {memory['id']}"
                ):
                    st.write(memory["content"])
                    st.caption(
                        f"Recorded: {memory['recorded_at'] or 'Unknown'}"
                    )
                    if memory["source"]:
                        st.write(f"**Source:** {memory['source']}")
                    st.write("**Evidence links:**")
                    for rel in memory["evidence"]:
                        st.write(f"`{rel[1]}` — **{rel[0]}** → `{rel[2]}`")
        else:
            st.info(memory_result.message or memory_result.status)

st.divider()
st.caption(
    "ECHO is an early graph-powered prototype. Impact analysis and memory "
    "recall use graph queries; autonomous LLM reasoning is not implemented."
)
