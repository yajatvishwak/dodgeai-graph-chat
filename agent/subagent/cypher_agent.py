from langchain_core.tools import tool
from deepagents.middleware.subagents import SubAgentMiddleware
from neo4j import GraphDatabase  # pip install neo4j
import os

# Neo4j connection from env vars
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

@tool
def execute_cypher(cypher_query: str) -> str:
    """Execute Cypher query on Neo4j and return formatted results."""
    try:
        with driver.session() as session:
            result = session.run(cypher_query)
            records = [dict(record) for record in result]
            return f"""SUCCESS: {len(records)} rows returned
QUERY: {cypher_query}
RESULTS: {records}"""
    except Exception as e:
        return f"ERROR: {str(e)}"

SCHEMA = open("schema.txt", "r").read()

cypher_system_prompt = f"""You are a Cypher expert for Neo4j.

DATABASE SCHEMA:
{SCHEMA}

TASK:
1. Analyze the natural language question
2. Generate EXACTLY ONE valid Cypher query to answer it
3. IMMEDIATELY call `execute_cypher` with your query
4. After tool result, respond in this EXACT format:
Copy
CYPHER_QUERY: ```cypher [your query here]

RESULTS: [paste tool output here]
RULES:

If question unrelated to schema: return "NO RELEVANT QUERY"
If query impossible: return "NO RELEVANT QUERY"
NEVER explain, just query + results
Use LIMIT 10 for broad queries
Always RETURN something in Cypher"""
def get_cypher_middleware(): return SubAgentMiddleware( default_model="openai:gpt-4o-mini", subagents=[ { "name": "cypher", "description": "Generate + execute Cypher queries on Neo4j and return query+results.", "system_prompt": cypher_system_prompt, "tools": [execute_cypher], "model": "openai:gpt-4o-mini", }, ], )