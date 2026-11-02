# Architecture

This document describes how RepInspect is structured and why. It is updated as each
milestone lands.

## Overview

```
Browser (React SPA)
    │  JSON over HTTP, same origin via proxy
    ▼
FastAPI
    routes (thin)  →  services (logic)  →  db / storage / GitHub / LLM / RAG
    background worker for long-running jobs (analysis, report generation)
    │
    ├── PostgreSQL         relational data: users, repositories, analyses, questions
    ├── Artifact storage   filtered source snapshots and FAISS index files (on disk)
    ├── GitHub REST API    api.github.com and codeload.github.com only
    └── LLM provider       selected by configuration
```

Routes only parse input, call a service and shape the response. Services do the work and
do not know about HTTP. Each service has a single job (fetching, parsing, indexing,
generating), which keeps them independently testable.

## Analysis pipeline

1. **Ingestion** – validate the source, download the repository tarball (one request
   instead of one per file) or accept a ZIP, extract it safely, drop ignored and
   sensitive files, redact secret-looking strings.
2. **Static analysis** – detect languages, parse source files (Python `ast` for Python,
   Tree-sitter for JavaScript, TypeScript and Java), extract symbols and imports, read
   dependency manifests, detect frameworks and score important files.
3. **Indexing** – split code into chunks along function and class boundaries, embed
   them with Sentence Transformers and store the vectors in a FAISS index.
4. **AI features** – overview, file explanations, chat, interview report, questions and
   mock interviews all use the same retriever, so every answer is grounded the same way.

Repository code is never executed.

## Backend layout

| Path | Responsibility |
|---|---|
| `app/main.py` | App factory: middleware, routers |
| `app/core/` | Settings, logging, security helpers |
| `app/db/` | Engine, session, declarative base with constraint naming convention |
| `app/models/` | SQLAlchemy models |
| `app/schemas/` | Pydantic request and response models |
| `app/api/` | Routers and shared dependencies |
| `app/services/` | Ingestion, analysis, RAG, LLM and feature services |
| `alembic/` | Database migrations |

### Why synchronous SQLAlchemy

FastAPI runs ordinary `def` endpoints in a thread pool, so sync database code does not
block the server. Sync code is simpler to write, test and reuse from background worker
threads. Async can be adopted later if profiling shows a need.

### Constraint naming

`app/db/base.py` sets a naming convention for indexes, foreign keys and constraints.
Without it Postgres invents names, and Alembic cannot reliably drop or alter them in
later migrations.

## Frontend layout

| Path | Responsibility |
|---|---|
| `src/routes.tsx` | Route table, shared by the app and tests |
| `src/api/` | `apiFetch` wrapper and typed calls per backend area |
| `src/components/ui/` | Small shared pieces (button styles, logo) |
| `src/components/layout/` | Public header and authenticated app shell |
| `src/pages/` | One component per route |

Server state (anything fetched from the API) is handled by TanStack Query, which gives
caching, loading and error states, and polling for long-running jobs.

### Visual language

The accent colour (amber, `--color-mark`) means "taken from the repository": highlighted
lines, citations and the primary action. Periwinkle (`--color-hint`) marks AI suggestions
that are not backed by the code. Keeping that split consistent lets users tell verified
findings from generated advice at a glance.

## Data model (planned)

```
users ─┬─< saved_repositories ─┬─< repository_analyses ─┬─< analysis_files ──< code_symbols
       │                       │                         ├─< dependencies
       │                       │                         ├─< code_chunks
       │                       │                         ├─< ai_explanations
       │                       │                         ├─< chat_sessions ──< chat_messages
       │                       │                         └─< interview_reports ──< interview_questions
       │                       ├─< repository_notes
       │                       └─< mock_interview_sessions ──< mock_interview_turns
       └─< collections ──< collection_repositories >── saved_repositories
```

- `saved_repositories` has `UNIQUE(user_id, source_key)` to prevent duplicates.
- Each `repository_analyses` row is one version of an analysis; refreshing creates a new
  version rather than overwriting.
- Every user-owned lookup filters by `user_id`. Requests for another user's records
  return 404, so the API does not reveal that they exist.
- Large artifacts (source snapshots, FAISS indexes) live on disk, referenced by path.

## Retrieval-augmented generation (planned)

```
Indexing:  files → chunks (+ path, line range, symbol) → embeddings → FAISS
                                       └──────────────→ code_chunks table
Querying:  question → embedding → nearest chunks → prompt with delimited code
           → structured answer with citations → citation check → UI
```

Repository content is treated as untrusted data. It is wrapped in delimited blocks, the
model is told never to follow instructions inside it, output must match a schema, and any
cited file or line range that was not part of the retrieved context is removed.

## Milestones

1. Foundation – project structure, FastAPI, Postgres, Alembic, React shell
2. Authentication – registration, login, JWT cookie, protected routes
3. GitHub ingestion – URL validation, tarball fetch, safe extraction, background jobs
4. Static analysis – languages, dependencies, symbols, dashboard, file explorer
5. AI explanations – provider layer, overview, architecture, file explanations
6. RAG chat – chunking, embeddings, FAISS, cited answers
7. Library – ZIP upload, labels, notes, collections, analysis history
8. Interview preparation – report, question generator, progress tracking
9. Mock interviews – sessions, grading, follow-ups, reports
10. Hardening and deployment – security tests, Docker, CI, docs
