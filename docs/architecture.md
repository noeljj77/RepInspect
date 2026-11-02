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
| `app/core/` | Settings, logging, password hashing and tokens (`security.py`) |
| `app/db/` | Engine, session, declarative base with constraint naming convention |
| `app/models/` | SQLAlchemy models |
| `app/schemas/` | Pydantic request and response models |
| `app/api/` | Routers and shared dependencies |
| `app/services/` | `ingestion/` (GitHub client, URL parsing, safe extraction, filtering, secret redaction, pipeline), `analysis/` (languages; parsers arrive in Milestone 4), `repositories.py` (the library), later RAG and LLM |
| `app/storage/` | Artifact storage for imported source snapshots |
| `app/worker/` | Background job runner |
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
| `src/hooks/` | Shared hooks, such as `useCurrentUser` |
| `src/components/auth/` | Route guards and the login/register page shell |
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

## Authentication

```
register / login ──► service checks credentials ──► JWT signed with JWT_SECRET
                                                     │
                     Set-Cookie: repinspect_session (HttpOnly, SameSite=Lax, Path=/api, Secure in production)
                                                     │
every later request ─► cookie ─► get_current_user dependency ─► User row, or 401
```

| Decision | Reason |
|---|---|
| Argon2id via `argon2-cffi` (library defaults) | Memory-hard, current OWASP and RFC 9106 recommendation. The hash string embeds its parameters and salt. Hashes are upgraded on login when the defaults get stronger. |
| Token in an `HttpOnly` cookie, not `localStorage` | JavaScript cannot read it, so an XSS bug cannot steal the session. |
| `SameSite=Lax`, JSON-only POSTs | Browsers do not send the cookie on cross-site POSTs, which blocks CSRF without extra tokens. |
| Cookie `Path=/api` | The cookie is only attached to API calls, never to requests for the web app itself. |
| JWT algorithm pinned to HS256, `exp` and `sub` required | Blocks `alg: none` and algorithm-confusion attacks. |
| Same 401 message and a dummy hash check for unknown emails | Login responses and timing do not reveal which emails are registered. |
| App refuses to start without a 32+ character `JWT_SECRET`, and rejects the development placeholder in production | A guessable signing key would let anyone forge logins. |
| Email lowercased on write, unique constraint in the database | `Ada@x.com` and `ada@x.com` are one account, and concurrent sign-ups cannot create duplicates. |

Known limits, to be addressed in the hardening milestone: logout clears the cookie but
a stolen token stays valid until it expires (tokens are stateless), and there is no
rate limiting on login yet.

On the frontend, `useCurrentUser` (TanStack Query) asks `/api/auth/me` once and shares
the answer. `RequireAuth` wraps the app shell and redirects guests to `/login`;
`GuestOnly` sends logged-in users away from the login and register pages. Logging in or
out clears the whole query cache so one account's data is never shown to the next.

## GitHub ingestion

```
POST /api/repositories {url}
  → parse_github_url         strict owner/repo extraction; the user's URL is never requested
  → saved_repositories       one row per user + source (unique constraint prevents duplicates)
  → repository_analyses      new version, status "queued"; job handed to the thread pool
        ↓ background job (services/ingestion/pipeline.py)
  fetching    GET /repos/{o}/{r}              details; private repos refused
              GET /repos/{o}/{r}/commits/{b}  full commit SHA (409 = empty repository)
              GET /repos/{o}/{r}/languages    best effort
              GET /repos/{o}/{r}/tarball/{sha} one download instead of one call per file
  extracting  safe extraction → filter → redact → write to artifacts/<analysis>/source
  completed   analysis_files rows + README + counts, or failed with a user-readable message
```

Four API calls per analysis keeps the unauthenticated limit (60 per hour) workable.

| Concern | How it is handled |
|---|---|
| SSRF | Requests only go to `api.github.com` and `codeload.github.com` over https. Redirects are followed by hand and every hop is checked, so a redirect to an internal address is never requested. The token is only sent to `api.github.com`. |
| Private code | Repositories that are not public are refused even if a configured token could read them. |
| Archive attacks | One extractor (`archive.py`) rejects `..`, absolute and drive-letter paths, never creates symlinks or special files, skips names unsafe on Windows, and counts bytes read to stop expansion bombs. It is written to be reused for ZIP uploads. |
| Resource limits | Download size, bytes scanned, file count, per-file size and total size are all capped. Hitting a cap ends the import and marks the analysis as truncated. |
| Secrets | Files such as `.env`, keys and credentials are never stored. Token formats and `password = "..."` style values in other files are replaced with `[REDACTED]` before writing, keeping line numbers intact. |
| Timeouts and failures | Every request has a timeout. Not found, rate limit (with reset time), empty repository, too large, GitHub down and unsafe archive each produce a specific message. Unexpected errors are logged and shown generically. |
| Jobs | Status lives in Postgres. Analyses left running by a previous server process are marked failed at startup. A user may run at most 3 at a time. |
| Storage | Postgres holds records; file bytes live under `artifacts/<analysis id>/source/` behind `storage/artifacts.py`. The snapshot is written to a temporary folder and renamed into place, so readers never see a partial import. |

Files are served only if they are recorded in `analysis_files` as stored, and the path
is also checked to stay inside the snapshot, so a crafted path never reaches the disk.

## Data model

Implemented so far: `users`, `saved_repositories`, `repository_analyses`,
`analysis_files`. The rest is planned.

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
