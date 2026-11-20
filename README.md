# Repo Onboarding Agent

> Point it at any GitHub repository. It explores the codebase on its own and explains it to you, like a senior engineer giving a day-one walkthrough.

Repo Onboarding Agent is an **agent-first** codebase comprehension tool. Instead of embedding a repo and doing a single vector-retrieval pass (the usual RAG approach), a LangGraph state machine decides its next exploration step based on what it has already discovered. This allows multi-hop reasoning across files and dependencies.

The goal is **comprehension, not code generation**, which sets it apart from tools like Copilot or Cursor.

---

## Why agent-first instead of RAG-first?

| Single-pass RAG | Repo Onboarding Agent |
|---|---|
| Limited by context window | Explores iteratively, pulling in only what it needs |
| No strategy for where to look | Planner decides the next action from current findings |
| One retrieval, one answer | Multi-hop reasoning across files and dependencies |
| Opaque answers | Streams its reasoning trace in real time |
| Struggles at scale | Confidence check decides when it knows enough |

If a repository's README is empty or missing, the agent works from the code itself: it explores the repo and explains it.

---

## How it works

```
POST /repos  ->  clone -> parse -> embed -> index (Qdrant)  ->  ready
POST /ask    ->  Planner -> Explorer -> Confidence Check -> Synthesizer
                     ^____________|  (loops until confident)
```

**Ingestion pipeline** (runs as a background task):

1. **Clone**: shallow clone via GitPython into `workspace/{repo_id}/`
2. **Parse**: walk the repo, filter by extension and ignored directories, and produce `CodeChunk` objects (tree-sitter syntax-aware chunking is planned)
3. **Embed**: local `sentence-transformers` model `all-MiniLM-L6-v2` (384-dim), with no paid embedding API
4. **Index**: store vectors in Qdrant

**Agent loop** (LangGraph state machine):

- **Planner** picks the next exploration action
- **Explorer** runs tools to read files and search the index
- **Confidence Check** decides whether to keep exploring or answer
- **Synthesizer** writes the final walkthrough

---

## Tech stack

| Layer | Choice |
|---|---|
| API | FastAPI + Server-Sent Events (SSE) |
| Agent orchestration | LangGraph |
| Reasoning LLM | Google Gemini (`gemini-3.5-flash-lite`) via its OpenAI-compatible endpoint, called with the OpenAI SDK |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`), local |
| Vector store | Qdrant (Docker Compose) |
| Repo access | GitPython |
| Config / validation | pydantic, pydantic-settings |
| Server | uvicorn |

The LLM is wrapped behind `app/llm/client.py`, so graph code does not depend on a specific provider or SDK and the provider stays swappable.

---

## API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/repos` | Submit a GitHub repo URL; starts background ingestion |
| `GET` | `/repos/{id}/status` | Ingestion status: `cloning`, `parsing`, `indexing`, `ready` |
| `POST` | `/ask` | Ask a question about an indexed repo; starts an agent session |
| `GET` | `/ask/{session_id}` | Stream the agent's reasoning and answer (SSE) |

---

## Getting started

### Prerequisites

- Python 3.11+
- Docker (for Qdrant)
- A Gemini API key

### 1. Start Qdrant

```powershell
docker compose up -d
```

### 2. Set up the backend

All backend commands run from `backend/`. The virtual environment also lives in `backend/`, not in `app/`.

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -e .
```

### 3. Configure environment

Create a `.env` file in `backend/` (settings are loaded by `pydantic-settings` in `app/config.py`):

```env
GEMINI_API_KEY=your_key_here
QDRANT_URL=http://localhost:6333
```

Check `app/config.py` for the exact variable names.

### 4. Run the server

```powershell
uvicorn app.main:app --reload --reload-dir app
```

Interactive docs are at `http://localhost:8000/docs`.

### Try it

```powershell
# Submit a repository
curl -X POST http://localhost:8000/repos -H "Content-Type: application/json" `
  -d '{\"url\": \"https://github.com/pallets/flask\"}'

# Poll until status is "ready"
curl http://localhost:8000/repos/<repo_id>/status
```

---

## Project structure

```
.
├── docker-compose.yml        # Qdrant
├── backend/
│   ├── pyproject.toml
│   └── app/
│       ├── main.py           # FastAPI app, CORS, /health
│       ├── config.py         # pydantic-settings config
│       ├── store.py          # in-memory repo/session records
│       ├── api/
│       │   ├── schemas.py    # request/response models
│       │   └── routes_repo.py
│       ├── ingestion/
│       │   ├── cloner.py     # shallow git clone
│       │   └── parser.py     # file walking + CodeChunk creation
│       └── llm/
│           └── client.py     # provider-agnostic LLM client
└── frontend/                 # in progress on feature/frontend
```

The tree shows the main files; the agent, embedding and vector-store modules sit alongside them under `app/`.

---

## Status

**Working:** clone, parse, embed and index into Qdrant; the LangGraph agent (planner, explorer, confidence check, synthesizer); repo and ask endpoints with SSE streaming.

**In progress:** frontend, with a dark chat-style UI and a repo tree map, on the `feature/frontend` branch.

**Known limitations:**

- Repo and session records are held in memory (no persistence across restarts)
- Parser currently produces whole-file chunks

---

## Roadmap

- [ ] **Git-history-aware reasoning** (top priority differentiator): answer "why" questions using commits and blame
- [ ] **Agent vs. RAG benchmark** with a formal evaluation pipeline
- [ ] **Live exploration graph** visualization in the frontend
- [ ] **MCP tool server** (Python MCP SDK) replacing plain Python tool functions
- [ ] **LangSmith** tracing and observability
- [ ] tree-sitter syntax-aware chunking

---

## Troubleshooting

- **`ModuleNotFoundError: app`**: make sure `pyproject.toml` includes `[tool.setuptools.packages.find]` with `include = ["app*"]`, then reinstall with `pip install -e .`
- **uvicorn `--reload-exclude` errors on PowerShell**: wildcard expansion breaks it; use `--reload-dir app` instead
- **uvicorn can't find the app**: run it from `backend/`, not the project root

---

## Author

**Arpit**: [arpit.itsfolio.tech](https://arpit.itsfolio.tech) · [GitHub](https://github.com/arpitrajawat62)

Built as a minor project at ITM University, Gwalior.
