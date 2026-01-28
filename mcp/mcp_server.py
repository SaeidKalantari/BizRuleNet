from mcp.server.fastmcp import FastMCP
from neo4j import GraphDatabase
import json

uri= "bolt://127.0.0.1:7687"
username= "neo4j"
password= "pass1234"

mcp = FastMCP("graph_search")

class Neo4jGraph:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def query(self, query, parameters=None, db=None):
        assert self.driver is not None, "Driver not initialized!"
        session = None
        try:
            session = self.driver.session(database=db) if db is not None else self.driver.session()
            return list(session.run(query, parameters))
        finally:
            if session is not None:
                session.close()

def _run(cypher: str, params=None):
    g = Neo4jGraph(uri, username, password)
    try:
        return g.query(cypher, params)
    finally:
        g.close()

@mcp.prompt()
def cypher_agent_prompt(user_question: str) -> str:
    return f"""
You are a Cypher query generator for a Neo4j knowledge graph.

Your job:
1) Convert the user's natural language question into a valid Cypher query.
2) Use tools to inspect the graph schema & stats if needed.
3) Call `query_runner` with the Cypher.
4) Answer the user in natural language using the query results.

USER QUESTION:
{user_question}

SCHEMA & STATS:
- Use `get_graph_schema` to obtain node labels, relationship types, and typical properties.
- Use `get_graph_stats` for counts.
- Use `sample_nodes(label)` when helpful to see real values.

RULES:
1. Use the exact node labels and relationship type names returned by `get_graph_schema`.
2. Use the `label` property for node names whenever it exists (e.g., n.label CONTAINS "..." for partial match).
3. Keep queries simple and efficient (LIMIT results; avoid Cartesian products).
4. For relationship queries, use: MATCH (a:Label)-[:REL]->(b:Label)
5. Use CONTAINS for partial text matching, = for exact matching.
6. If the user question is ambiguous, make reasonable assumptions and state them briefly.
7. Return ONLY Cypher in the query you pass to `query_runner` (no markdown in the tool call).
"""


@mcp.tool()
def get_graph_schema() -> str:
    """
    Returns graph schema info: node labels, relationship types, and common properties (best-effort).
    """
    labels = [r["label"] for r in _run("CALL db.labels() YIELD label RETURN label ORDER BY label")]
    rels = [r["relationshipType"] for r in _run(
        "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType ORDER BY relationshipType"
    )]

    # Optional: property keys (global)
    props = [r["propertyKey"] for r in _run(
        "CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey ORDER BY propertyKey"
    )]

    # Optional: per-label property sampling (best-effort)
    label_props = {}
    for lab in labels[:30]:  # avoid huge graphs
        recs = _run(
            f"""
            MATCH (n:`{lab}`)
            WITH n LIMIT 50
            UNWIND keys(n) AS k
            RETURN k, count(*) AS c
            ORDER BY c DESC
            """)
        label_props[lab] = [r["k"] for r in recs[:20]]

    out = {
        "labels": labels,
        "relationshipTypes": rels,
        "propertyKeys": props,
        "labelProperties": label_props,
        "namePropertyRule": "Use `label` property for node names (n.label CONTAINS '...') when present.",
    }
    return json.dumps(out, indent=2)

@mcp.tool()
def get_graph_stats() -> str:
    """Returns node/edge counts."""
    node_count = _run("MATCH (n) RETURN count(n) AS c")[0]["c"]
    edge_count = _run("MATCH ()-[r]->() RETURN count(r) AS c")[0]["c"]
    return json.dumps({"nodeCount": node_count, "edgeCount": edge_count}, indent=2)

@mcp.tool()
def sample_nodes(label: str, limit: int = 5) -> str:
    """Returns sample nodes for a given label."""
    recs = _run(
        f"""
        MATCH (n:`{label}`)
        RETURN n{{.*}} AS node
        LIMIT $limit
        """,
        {"limit": limit},
    )
    return json.dumps([r["node"] for r in recs], indent=2)

def _is_read_only(cypher: str) -> bool:
    bad = ["CREATE", "MERGE", "DELETE", "SET", "DROP", "CALL dbms", "LOAD CSV"]
    up = cypher.upper()
    return not any(b in up for b in bad)

@mcp.tool()
def query_runner(cypher_q: str) -> str:
    """Runs READ-ONLY Cypher and returns results."""
    if not _is_read_only(cypher_q):
        return "Refused: only read-only Cypher is allowed."

    if "LIMIT" not in cypher_q.upper():
        cypher_q = cypher_q.rstrip() + "\nLIMIT 25"

    results = _run(cypher_q)
    formatted = "\n".join([str(r.data()) for r in results])
    return formatted if formatted else "No results found."


# Kick off server if file is run 
if __name__ == "__main__":
    mcp.run(transport="stdio")