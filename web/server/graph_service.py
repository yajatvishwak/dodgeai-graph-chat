import os
import re
from typing import Any

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
)


def _node_to_dict(node: Any) -> dict[str, Any]:
    labels = sorted(list(node.labels))
    return {
        "id": node.element_id,
        "label": labels[0] if labels else "Node",
        "labels": labels,
        "group": labels[0] if labels else "Node",
        "properties": dict(node.items()),
    }


def _edge_to_dict(rel: Any) -> dict[str, Any]:
    return {
        "id": rel.element_id,
        "from": rel.start_node.element_id,
        "to": rel.end_node.element_id,
        "label": rel.type,
        "type": rel.type,
        "properties": dict(rel.items()),
    }


def _serialize_result_graph(result: Any) -> dict[str, list[dict[str, Any]]]:
    graph = result.graph()
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}

    for node in graph.nodes:
        node_dict = _node_to_dict(node)
        nodes[node_dict["id"]] = node_dict

    for rel in graph.relationships:
        edge_dict = _edge_to_dict(rel)
        edges[edge_dict["id"]] = edge_dict

    return {"nodes": list(nodes.values()), "edges": list(edges.values())}


def _merge_graphs(graphs: list[dict[str, list[dict[str, Any]]]]) -> dict[str, list[dict[str, Any]]]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    for graph in graphs:
        for node in graph["nodes"]:
            nodes[node["id"]] = node
        for edge in graph["edges"]:
            edges[edge["id"]] = edge
    return {"nodes": list(nodes.values()), "edges": list(edges.values())}


def _trim_graph(
    graph: dict[str, list[dict[str, Any]]], max_nodes: int, max_edges: int
) -> dict[str, list[dict[str, Any]]]:
    edges = graph["edges"][:max_edges]
    connected_node_ids: set[str] = set()
    for edge in edges:
        connected_node_ids.add(edge["from"])
        connected_node_ids.add(edge["to"])

    nodes: list[dict[str, Any]] = []
    for node in graph["nodes"]:
        if node["id"] in connected_node_ids:
            nodes.append(node)
        if len(nodes) >= max_nodes:
            break

    allowed_ids = {node["id"] for node in nodes}
    edges = [edge for edge in edges if edge["from"] in allowed_ids and edge["to"] in allowed_ids]
    return {"nodes": nodes, "edges": edges}


def get_full_graph(limit: int = 120) -> dict[str, list[dict[str, Any]]]:
    query = """
    MATCH (n)-[r]->(m)
    RETURN n, r, m
    LIMIT $limit
    """
    with driver.session() as session:
        result = session.run(query, limit=limit)
        graph = _serialize_result_graph(result)
        return _trim_graph(graph, max_nodes=150, max_edges=120)


_RETURN_RE = re.compile(
    r"""
    \bRETURN\b          # last RETURN keyword
    (?!.*\bRETURN\b)    # negative lookahead: no more RETURNs after this one
    .*$                 # everything after it
    """,
    re.IGNORECASE | re.DOTALL | re.VERBOSE,
)


def _rewrite_for_graph(query: str) -> str:
    """Replace the final RETURN clause with RETURN * so result.graph() captures nodes."""
    rewritten = _RETURN_RE.sub("RETURN * LIMIT 60", query)
    return rewritten


def get_graph_from_queries(queries: list[str]) -> dict[str, list[dict[str, Any]]]:
    graphs: list[dict[str, list[dict[str, Any]]]] = []
    with driver.session() as session:
        for query in queries:
            if not query.strip():
                continue
            graph_query = _rewrite_for_graph(query)
            try:
                result = session.run(graph_query)
                graph_payload = _serialize_result_graph(result)
            except Exception:
                result = session.run(query)
                graph_payload = _serialize_result_graph(result)
            if graph_payload["nodes"]:
                graphs.append(graph_payload)
    if not graphs:
        return {"nodes": [], "edges": []}
    return _trim_graph(_merge_graphs(graphs), max_nodes=220, max_edges=220)
