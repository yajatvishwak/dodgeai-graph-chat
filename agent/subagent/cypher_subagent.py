from langchain_core.tools import tool
from deepagents.middleware.subagents import SubAgentMiddleware
from neo4j import GraphDatabase
import os
from pathlib import Path
from dotenv import load_dotenv
from model import build_openrouter_model
from system_prompt import cypher_system_prompt
load_dotenv()


NEO4J_URI = os.getenv("NEO4J_URI") 
NEO4J_USER = os.getenv("NEO4J_USER")
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

def get_cypher_middleware():
    return SubAgentMiddleware(
        default_model=build_openrouter_model(),
        subagents=[
            {
                "name": "cypher",
                "description": "Generate + execute Cypher queries on Neo4j and return query+results+reasoning.",
                "system_prompt": cypher_system_prompt,
                "tools": [execute_cypher],
            },
        ],
    )