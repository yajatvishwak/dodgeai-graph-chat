from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent_wrapper import invoke_agent
from graph_service import get_full_graph, get_graph_from_queries


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)


class GraphQueryRequest(BaseModel):
    queries: list[str] = Field(default_factory=list)


app = FastAPI(title="Graph Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/graph")
def graph(limit: int = Query(default=120, ge=20, le=300)) -> dict[str, list[dict[str, Any]]]:
    return get_full_graph(limit=limit)


@app.post("/api/graph/query")
def graph_query(payload: GraphQueryRequest) -> dict[str, list[dict[str, Any]]]:
    return get_graph_from_queries(payload.queries)


@app.post("/api/chat")
async def chat(payload: ChatRequest) -> dict[str, Any]:
    history = [item.model_dump() for item in payload.history]
    agent_result = await invoke_agent(payload.message, history)
    parsed = agent_result["parsed"]
    cypher_queries = parsed.get("cypher_queries") or []
    graph_data = get_graph_from_queries(cypher_queries) if cypher_queries else {"nodes": [], "edges": []}
    return {
        "raw": agent_result["raw"],
        "response": parsed,
        "graph": graph_data,
    }
