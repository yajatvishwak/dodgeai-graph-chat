# DodgeAI Graph Chat

An AI-powered chatbot for analyzing SAP Order-to-Cash (OTC) data through a Neo4j graph database. The system uses a planner-executor agentic architecture where a main orchestrator agent decomposes business questions into Cypher queries, dispatches them to a specialized sub-agent, and synthesizes answers grounded in real query results — all visualized as an interactive graph in the browser.

## Table of Contents

- [Development Journey](#development-journey)
- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Graph Model](#graph-model)
- [Agent Architecture](#agent-architecture)
- [Frontend Architecture](#frontend-architecture)
- [Backend Architecture](#backend-architecture)
- [Data Pipeline](#data-pipeline)
- [Project Structure](#project-structure)
- [Running the Project](#running-the-project)
- [Architectural Decisions](#architectural-decisions)
- [Known Issues](#known-issues)

---

## Development Journey

The project evolved through several iterations of data modeling and technology choices:

1. **Data Exploration** — Started by examining the raw SAP O2C JSONL exports to understand the shape of each table (billing documents, sales orders, deliveries, journal entries, customers, products, etc.).

2. **DBML Schema Generation** — Built `generate_dbml_schema.py` to auto-infer column types from the JSONL files and produce a DBML schema. This was plotted on [dbdiagram.io](https://dbdiagram.io) to visualize tables, primary keys, and foreign key relationships. The output lives in `data_creation/schema.dbml`.

3. **Relational Modeling (Postgres — abandoned)** — Initially loaded data into PostgreSQL to validate the relational model. This helped identify incorrect assumptions about relationships between tables (e.g., how delivery items reference sales order items via `referenceSdDocument` rather than a direct foreign key). Postgres is still defined in `docker-compose.yml` but is **not used at runtime** — it served purely as a validation step.

4. **Graph Model Design** — After understanding the OTC flow, the relational model was translated into a graph model. Claude was used as a brainstorming partner to propose connections between entities and validate the OTC traversal logic. The initial graph model based on DBML assumptions turned out to be wrong — relationships needed to be derived from item-level cross-references rather than assumed from table co-occurrence. This led to a second iteration where data was loaded directly into Neo4j without the Postgres intermediary.

5. **Iterative Schema Refinement** — Went back to the raw data, studied the SAP Order-to-Cash flow (Customer → Sales Order → Delivery → Billing Document → Journal Entry → Clearing Document), and redesigned the graph model to reflect actual document-level and item-level flows. The final model is documented in `agent/neo_4j.schema.md` and `data_creation/proposed_graph_model.md`.

6. **Agent Development** — Built the graph agent using LangChain's `create_agent` with DeepAgents middleware. The prompt went through many iterations — Claude was used to refine the prompt formatting and make the instructions more precise, though over-formalizing initially worsened results. Iterative tuning brought the quality back and beyond the original baseline.

7. **Frontend & Backend** — The SvelteKit frontend and FastAPI backend were built with the help of Cursor (AI-assisted coding). The graph visualization, chat interface, and API proxy were scaffolded by Cursor from high-level instructions.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Browser (SvelteKit :5173)                                               │
│  ┌─────────────────────┐  ┌─────────────────────────────────────────┐   │
│  │   GraphPanel         │  │   ChatPanel                             │   │
│  │   (vis-network)      │  │   (markdown + expandable Cypher)        │   │
│  └────────┬────────────┘  └────────────────┬────────────────────────┘   │
│           │                                 │                            │
│           │  GET /api/graph                  │  POST /api/chat            │
└───────────┼─────────────────────────────────┼────────────────────────────┘
            │                                 │
            │  SvelteKit server routes (proxy) │
            ▼                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  FastAPI Backend (:8000)                                                 │
│  ┌─────────────────┐  ┌──────────────────────────────────────────────┐  │
│  │  graph_service   │  │  agent_wrapper                               │  │
│  │  (Neo4j viz)     │  │  ┌────────────────────────────────────────┐ │  │
│  │                  │  │  │  Orchestrator Agent (planner)           │ │  │
│  │                  │  │  │  ┌──────────────────────────────────┐  │ │  │
│  │                  │  │  │  │  Cypher Sub-Agent (executor)     │  │ │  │
│  │                  │  │  │  │  → execute_cypher tool           │  │ │  │
│  │                  │  │  │  └──────────────┬───────────────────┘  │ │  │
│  │                  │  │  └─────────────────┼──────────────────────┘ │  │
│  └────────┬─────────┘  └───────────────────┼────────────────────────┘  │
│           │                                 │                            │
└───────────┼─────────────────────────────────┼────────────────────────────┘
            │                                 │
            ▼                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Neo4j (:7687)                                                           │
│  SAP Order-to-Cash Graph (12 node types, 17 relationship types)          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer           | Technology                                                     |
| --------------- | -------------------------------------------------------------- |
| Frontend        | SvelteKit 2, Svelte 5, TypeScript, vis-network, marked         |
| Backend         | FastAPI, Uvicorn, Python 3.13                                  |
| Agent Framework | LangChain `create_agent`, DeepAgents `SubAgentMiddleware`      |
| LLM Provider    | OpenRouter (default model: `xiaomi/mimo-v2-pro`)               |
| Database        | Neo4j 5 Community Edition (with APOC plugin)                   |
| Observability   | Langfuse (optional callback handler for tracing agent runs)    |
| Orchestration   | Docker Compose (Neo4j, Postgres, data-loader, backend, frontend) |
| Package Mgmt    | `uv` + `pyproject.toml` (Python), npm (frontend)              |

---

## Graph Model

The graph models the SAP Order-to-Cash lifecycle with 12 node types and 17 relationship types.

### Document-Level OTC Flow

```
Customer ─PLACED─► SalesOrder ─DELIVERED_VIA─► Delivery ─BILLED_IN─► BillingDocument ─RECORDED_AS─► JournalEntry ─CLEARED_BY─► ClearingDocument
```

### Item-Level Flow (for granular tracing)

```
SalesOrderItem ◄─FULFILLS─ DeliveryItem ◄─BILLS─ BillingDocumentItem
```

### Node Types

| Label               | Key Property                    | Source Data                          |
| ------------------- | ------------------------------- | ------------------------------------ |
| Customer            | `id`                            | business_partners + company/sales assignments |
| Address             | `id` (businessPartner:addressId)| business_partner_addresses           |
| Product             | `id`                            | products + product_descriptions      |
| Plant               | `id`                            | plants                               |
| SalesOrder          | `id`                            | sales_order_headers                  |
| SalesOrderItem      | `uid` (salesOrder:item)         | sales_order_items + schedule_lines   |
| Delivery            | `id`                            | outbound_delivery_headers            |
| DeliveryItem        | `uid` (deliveryDoc:item)        | outbound_delivery_items              |
| BillingDocument     | `id`                            | billing_document_headers + cancellations |
| BillingDocumentItem | `uid` (billingDoc:item)         | billing_document_items               |
| JournalEntry        | `id` (accountingDoc:fiscalYear) | journal_entry_items (aggregated)     |
| ClearingDocument    | `id` (clearingDoc:fiscalYear)   | clearing refs from journal entries + payments |

### Relationship Types

**Document-level flow:** `PLACED`, `DELIVERED_VIA`, `BILLED_IN`, `RECORDED_AS`, `CLEARED_BY`

**Customer links:** `BILLED_TO`, `FOR_CUSTOMER`, `HAS_ADDRESS`

**Item containment:** `HAS_ITEM` (SalesOrder→SalesOrderItem, Delivery→DeliveryItem, BillingDocument→BillingDocumentItem)

**Item-level flow:** `FULFILLS` (DeliveryItem→SalesOrderItem), `BILLS` (BillingDocumentItem→DeliveryItem)

**Master data:** `FOR_PRODUCT`, `FROM_PLANT`, `AVAILABLE_AT`, `STORED_AT`

**Cancellation:** `CANCELS` (BillingDocument→BillingDocument)

### Key Design Decisions

- **Composite UIDs** use `:` as separator (e.g., `740506:10`) — item numbers are normalized by stripping leading zeros.
- **Document-level relationships are derived**, not explicit in the source. For example, `SalesOrder -[:DELIVERED_VIA]-> Delivery` is derived from delivery items that reference a sales order via `referenceSdDocument`.
- **JournalEntry nodes are aggregated** from individual line items to document level, with `totalAmount` summed and `itemCount` tracked.
- **Stub nodes** are created for Products and Plants referenced by items but absent from master data tables.

---

## Agent Architecture

The chatbot uses a **planner-executor pattern** implemented with LangChain's `create_agent` and DeepAgents' `SubAgentMiddleware`. There is no explicit LangGraph state machine — the orchestration relies on LangChain's built-in agent loop with middleware extensions.

### Two-Agent System

```
┌─────────────────────────────────────────────────────────┐
│  Orchestrator (Main Agent)                               │
│                                                          │
│  System prompt: SAP OTC analyst                          │
│  Middleware: TodoListMiddleware + SubAgentMiddleware      │
│  Available tool: "cypher" (dispatches to sub-agent)      │
│                                                          │
│  Responsibilities:                                       │
│  1. Understand the user's business question               │
│  2. Resolve ambiguous IDs across node types               │
│  3. Plan a sequence of data retrieval steps               │
│  4. Call the cypher tool with natural language             │
│  5. Inspect results, decide if more queries needed        │
│  6. Synthesize a final answer as YAML                     │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Cypher Sub-Agent                                  │  │
│  │                                                    │  │
│  │  System prompt: Cypher query specialist             │  │
│  │  Available tool: execute_cypher                     │  │
│  │                                                    │  │
│  │  Responsibilities:                                  │  │
│  │  1. Receive natural language description             │  │
│  │  2. Map to graph schema                              │  │
│  │  3. Generate exactly ONE valid Cypher query           │  │
│  │  4. Execute via Neo4j driver                          │  │
│  │  5. Return CYPHER / RESULTS / REASONING               │  │
│  └────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Agentic Loop

1. The user sends a message via the chat UI.
2. The **orchestrator** receives the message along with recent conversation history (last 14 turns).
3. The orchestrator plans what data to retrieve and calls the `cypher` tool with a **natural language description** (not raw Cypher).
4. The **`SubAgentMiddleware`** intercepts this call and spins up the **Cypher sub-agent**, which translates the natural language into a valid Cypher query and executes it against Neo4j via the `execute_cypher` tool.
5. Results flow back to the orchestrator, which decides whether to issue more queries or synthesize a final answer.
6. The orchestrator emits a structured **YAML response** containing `message`, `cypher_queries`, `query_results`, `confidence`, and `confidence_rationale`.
7. The backend parses this YAML, re-runs the Cypher queries against Neo4j's graph result API for visualization, and returns both the text answer and graph data to the frontend.

### TodoListMiddleware

The `TodoListMiddleware` injects additional system instructions that force multi-step behavior — the agent must create a todo list for complex tasks, execute all steps, and not stop after a single tool call. This prevents the common failure mode where an agent makes one query and returns a partial answer.

### Prompt Engineering Notes

- The orchestrator prompt embeds the **full graph schema** (`neo_4j.schema.md`) so the LLM understands what nodes, relationships, and properties exist.
- The prompt includes an **OTC flow diagram** and a **traversal shortcut table** so the agent knows efficient paths through the graph.
- **Anti-hallucination rules** are strict: the `message` field must contain only values that appeared in Cypher query results. The agent must copy IDs, names, and numbers verbatim.
- The Cypher sub-agent prompt includes **common query patterns** (full OTC chain traversal, billing document tracing, broken flow detection) as few-shot examples.
- The orchestrator must use **natural language** when calling the cypher tool — it never writes raw Cypher itself. This separation of concerns lets each agent focus on its strength.

### YAML Output Contract

Every agent response is expected to be a YAML block:

```yaml
message: |
  <answer grounded in query results>
cypher_queries:
  - |
    MATCH (n:SalesOrder) RETURN count(n) AS total
query_results:
  - <raw result rows>
confidence: 0.85
confidence_rationale: <why this confidence level>
```

The backend extracts this via regex (```` ```yaml ... ``` ````) and `yaml.safe_load`, with a fallback that treats the entire response as the `message` if YAML parsing fails.

---

## Frontend Architecture

The frontend is a **SvelteKit 2** application with a single-page layout split into two panels:

### Layout

- **Left panel (65%)** — `GraphPanel`: Interactive graph visualization powered by **vis-network**. Loads an initial sample of the graph on mount and updates reactively when chat responses include graph data.
- **Right panel (35%)** — `ChatPanel`: Chat interface with markdown rendering (via **marked**), expandable Cypher query blocks, confidence indicators, and a typing animation during loading.

### Components

| Component          | Purpose                                                                 |
| ------------------ | ----------------------------------------------------------------------- |
| `+page.svelte`     | Root page: coordinates chat messages, graph data, and node selection     |
| `GraphPanel.svelte`| vis-network canvas with Barnes-Hut physics, node color palette by type, click-to-select |
| `ChatPanel.svelte` | Message list, markdown rendering, expandable Cypher blocks, input composer |
| `NodeOverlay.svelte`| Detail overlay when a graph node is clicked (properties, connection count) |

### State Management

State is managed via Svelte writable stores in `$lib/stores/chat.ts`:

- `messages` — Chat history (initialized with a welcome message)
- `loading` — Whether an agent request is in flight
- `graphData` — Current graph nodes and edges for visualization
- `selectedNodeId` — Currently selected node in the graph
- `minimized` — Whether the graph panel is collapsed
- `statusText` — Derived from `loading` (shows "analyzing" vs "awaiting instructions")

### API Proxy

SvelteKit server routes (`/api/chat/+server.ts`, `/api/graph/+server.ts`) proxy requests to the FastAPI backend. This avoids CORS issues and keeps the backend URL configurable via the `API_BACKEND_URL` environment variable.

### Graph Visualization Details

- Nodes are colored by their `group` (label) using a predefined palette (e.g., Customer=blue, SalesOrder=green, BillingDocument=pink).
- Physics simulation (Barnes-Hut) runs during stabilization and disables after settling for smooth interaction.
- Node labels display the most human-readable property available (fullName, productName, etc.), falling back to the element ID.

---

## Backend Architecture

### FastAPI Server (`web/server/main.py`)

Three API endpoints:

| Method | Route              | Purpose                                                     |
| ------ | ------------------ | ----------------------------------------------------------- |
| GET    | `/api/health`      | Health check                                                |
| GET    | `/api/graph`       | Returns a sample of the full graph for initial visualization |
| POST   | `/api/graph/query` | Executes a list of Cypher queries and returns graph data     |
| POST   | `/api/chat`        | Invokes the agent, parses YAML response, returns answer + graph |

### Graph Service (`web/server/graph_service.py`)

Two Neo4j code paths exist by design:

1. **Agent path** (`execute_cypher` in `cypher_subagent.py`) — Returns rows as Python dicts for the agent to reason over. This is the Q&A path.
2. **Visualization path** (`graph_service.py`) — Rewrites the final `RETURN` clause to `RETURN * LIMIT 60` so Neo4j's `result.graph()` API returns nodes and edges suitable for vis-network rendering. Results are serialized to `{nodes: [...], edges: [...]}` format.

The visualization path includes:
- **Graph merging** — multiple Cypher queries produce separate graph fragments that are merged by element ID.
- **Graph trimming** — caps at 220 nodes/edges for the chat response and 150/120 for the initial full-graph view, keeping only connected nodes.

### Agent Wrapper (`web/server/agent_wrapper.py`)

- Creates a **singleton agent** at module load time.
- Converts chat history to LangChain message format, trimming to the last **14 messages** (matching the frontend's `recentHistoryWindow`).
- Invokes the agent with a **Langfuse callback handler** for observability.
- Parses the YAML output and provides sensible defaults if parsing fails.

---

## Data Pipeline

### Stage 1: Preprocessing (`data_creation/preprocess.py`)

Reads raw JSONL files from `data_creation/sap-o2c-data/`, normalizes them, and writes cleaned output to `data/cleaned/`:

- Normalizes all timestamps to UTC ISO-8601 format
- Flattens nested timestamp objects (SAP's `{hours, minutes, seconds}` format)
- Generates a `preprocess_summary.md` report with per-table statistics

### Stage 2: DBML Schema Generation (`data_creation/generate_dbml_schema.py`)

Scans JSONL files, infers column types (bool, int, float, timestamp, text, json), and writes a `schema.dbml` file. This was used with dbdiagram.io to visualize the relational structure before designing the graph model.

### Stage 3: Neo4j Loading (`data_creation/load_neo.py`)

Loads cleaned JSONL directly into Neo4j:

1. **Wipes** the existing graph (optional `--no-wipe` flag)
2. **Creates uniqueness constraints** on all node key properties
3. **Loads nodes** in batches using `UNWIND` + `MERGE`:
   - Enriches Customer nodes by joining business_partners with company assignments and sales area assignments
   - Enriches Product nodes with English descriptions
   - Aggregates JournalEntry line items to document level
   - Extracts ClearingDocument references from journal entries and payments
   - Creates stub nodes for Products/Plants referenced but absent from master data
4. **Loads relationships** derived from cross-references in the data:
   - `DELIVERED_VIA` is derived from delivery items' `referenceSdDocument`
   - `BILLED_IN` is derived from billing items' `referenceSdDocument`
   - `FULFILLS` / `BILLS` link items via normalized composite UIDs
   - `RECORDED_AS` links billing documents to journal entries via `accountingDocument:fiscalYear`
5. **Verifies** node and relationship counts

### Docker Data Loader

The `data-loader` service in Docker Compose builds `data_creation/Dockerfile`, waits for Neo4j to be healthy, and runs `load_neo.py` as a one-shot container. The backend service depends on `data-loader` completing successfully before starting.

---

## Project Structure

```
dodge-assignment/
├── agent/                          # Graph agent (shared between CLI and web)
│   ├── main.py                     # CLI entry point (for testing)
│   ├── model.py                    # OpenRouter ChatOpenAI configuration
│   ├── system_prompt.py            # All prompts (orchestrator, cypher, todo middleware)
│   ├── neo_4j.schema.md            # Graph schema (embedded into prompts)
│   ├── subagent/
│   │   └── cypher_subagent.py      # Neo4j driver, execute_cypher tool, SubAgentMiddleware
│   └── pyproject.toml
│
├── web/
│   ├── server/                     # FastAPI backend
│   │   ├── main.py                 # API routes (/api/chat, /api/graph, /api/health)
│   │   ├── agent_wrapper.py        # Agent singleton, YAML parsing, history trimming
│   │   ├── graph_service.py        # Neo4j visualization queries, graph merging/trimming
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   │
│   └── frontend/                   # SvelteKit frontend
│       ├── src/
│       │   ├── routes/
│       │   │   ├── +page.svelte    # Main page (graph + chat layout)
│       │   │   └── api/            # Server routes (proxy to FastAPI)
│       │   └── lib/
│       │       ├── components/     # GraphPanel, ChatPanel, NodeOverlay
│       │       ├── stores/chat.ts  # Svelte stores (messages, graph, loading)
│       │       └── types.ts        # TypeScript interfaces
│       ├── Dockerfile
│       └── package.json
│
├── data_creation/                  # Data pipeline
│   ├── preprocess.py               # JSONL normalization (timestamps → UTC)
│   ├── generate_dbml_schema.py     # Auto-infer DBML from JSONL
│   ├── load_neo.py                 # JSONL → Neo4j loader (nodes + relationships)
│   ├── schema.dbml                 # Generated relational schema
│   ├── schema.dbdiagram            # dbdiagram.io companion file
│   ├── proposed_graph_model.md     # Graph model design document
│   ├── Dockerfile                  # One-shot data loader image
│   ├── sap-o2c-data/               # Raw JSONL source files
│   └── data/cleaned/               # Preprocessed JSONL (consumed by loader)
│
├── utils/
│   └── convert_schema_json_to_md/  # Neo4j schema JSON → Markdown converter
│
├── docker-compose.yml              # Full stack orchestration
└── .env.example                    # Environment variable template
```

---

## Running the Project

### Prerequisites

- Docker and Docker Compose
- An OpenRouter API key

### Setup

1. Copy the environment file and fill in your credentials:

```bash
cp .env.example .env
```

Required variables:

```
NEO4J_PASSWORD=<neo4j-password>
OPENROUTER_API_KEY=<your-openrouter-key>
OPENROUTER_MODEL=xiaomi/mimo-v2-pro    # optional, this is the default
```

Optional (for Langfuse tracing):

```
LANGFUSE_SECRET_KEY=
LANGFUSE_PUBLIC_KEY=
LANGFUSE_BASE_URL=
```

2. Start all services:

```bash
docker compose up --build
```

This will:
- Start Neo4j (ports 7474 for browser, 7687 for Bolt)
- Start Postgres (port 5433, currently unused at runtime)
- Run the data loader to populate Neo4j from JSONL files
- Start the FastAPI backend (port 8000)
- Start the SvelteKit frontend (port 5173)

3. Open http://localhost:5173 in your browser.

### Local Development (without Docker)

For the backend:

```bash
cd agent && uv sync
cd ../web/server && uv sync
uvicorn main:app --reload --port 8000
```

For the frontend:

```bash
cd web/frontend
npm install
npm run dev
```

Ensure Neo4j is running and environment variables are set.

---

## Architectural Decisions

### Why Neo4j over a relational database?

The SAP Order-to-Cash dataset is fundamentally about **relationships between documents** — sales orders connect to deliveries, which connect to billing documents, which connect to journal entries. These multi-hop traversals (e.g., "trace a sales order through to payment clearing") are natural graph queries. In a relational database, this requires multiple JOINs across many tables; in Neo4j, it's a single `MATCH` path pattern. Additionally, **Cypher** is nearly an industry standard for graph queries and is straightforward for an LLM to generate.

### Why a two-agent architecture instead of a single agent?

Separating the planner (orchestrator) from the executor (Cypher agent) follows the **separation of concerns** principle:

- The **orchestrator** reasons about the business domain — it understands SAP OTC flows, plans multi-step retrieval strategies, and synthesizes human-readable answers. It never writes raw Cypher.
- The **Cypher sub-agent** is a specialist — it translates natural language into syntactically valid Cypher, handles ID formats, and manages query patterns. It never needs to understand the broader business context.

This separation makes prompt engineering more tractable: each agent's prompt is focused on one skill, reducing confusion and improving output quality.

### Why OpenRouter?

OpenRouter provides a unified API to access multiple LLM providers (OpenAI, Anthropic, open-source models) through a single endpoint. The default model (`xiaomi/mimo-v2-pro`) was chosen for its good balance of cost and quality for structured output tasks. The model is easily swappable via the `OPENROUTER_MODEL` environment variable.

### Why DeepAgents SubAgentMiddleware instead of LangGraph?

LangGraph would work, but `SubAgentMiddleware` from the DeepAgents library provides a simpler abstraction for the specific pattern needed here: a named sub-agent with its own system prompt and tools that the main agent can call as a tool. This avoided the boilerplate of defining a full state graph when the interaction pattern is straightforward (main agent calls sub-agent, sub-agent returns results).

### Why SvelteKit for the frontend?

SvelteKit offers server-side route handlers (used for API proxying) and a reactive component model that maps well to the chat + graph visualization layout. Svelte's reactivity model makes state management straightforward without needing a separate state management library.

### Why vis-network for graph visualization?

vis-network is a mature, well-documented library for interactive network graphs. It handles physics-based layouts (Barnes-Hut algorithm), node interaction (click, hover, drag), and dynamic data updates — all needed for rendering Neo4j graph results that change with each chat response.

### Why YAML for agent output instead of JSON?

YAML is more LLM-friendly for structured output — it doesn't require escaping quotes or braces in string values, which is common when the `message` field contains formatted text with code snippets, IDs, or special characters. This reduces parsing failures compared to asking the LLM to produce valid JSON.

### Why a 14-message history window?

The conversation history sent to the agent is trimmed to the last 14 messages (7 user + 7 assistant turns). This balances context retention with token efficiency — enough to maintain conversational coherence without blowing up the context window, especially since each message may contain embedded Cypher queries and results.

### Why two separate Neo4j code paths?

The agent's `execute_cypher` returns **tabular rows** (Python dicts) for the LLM to reason over. The visualization layer needs **graph-structured data** (nodes and edges) from Neo4j's `result.graph()` API, which requires `RETURN *` instead of specific columns. Rather than forcing one format to serve both needs, the system runs the same Cypher queries through two different execution paths — rows for reasoning, graph for rendering.

---

## Known Issues

- **Graph does not re-render after queries** — After a chat query returns new graph data, the graph visualization does not update to show the query-relevant subgraph. The graph panel is currently broken and does not reflect the Cypher results returned by the agent.
- **Graph rendering delay** — Even when the graph does render (e.g., on initial load), vis-network may take a few seconds to stabilize, especially for large result sets. The physics stabilization runs 120 iterations before disabling, which can feel slow.
- **Postgres service is vestigial** — The Postgres container starts but is not used by any application code. It remains in `docker-compose.yml` from the earlier validation phase.
- **`load_jsonl_to_postgres.py` is a duplicate** — This file is byte-identical to `load_neo.py` despite its name suggesting a Postgres loader. It was never converted to actual Postgres loading code.
- **YAML parsing fragility** — If the LLM produces malformed YAML or omits the YAML code fence, the fallback treats the entire response as the `message` field, losing structured data (Cypher queries, confidence).
- **No streaming** — Chat responses wait for the full agent loop to complete before displaying. Long-running multi-step queries can feel unresponsive.
- **CORS is wide open** — The backend allows all origins (`allow_origins=["*"]`), which is fine for development but should be restricted in production.
