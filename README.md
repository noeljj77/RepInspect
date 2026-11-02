# RepInspect

**Understand the code. Own the interview.**

RepInspect analyzes a GitHub repository (or an uploaded ZIP), maps its structure and
technologies, and answers questions about the implementation with references to the
exact files and lines. It then turns the codebase into interview preparation: a
project report, repository-specific questions and a mock interview with feedback.

> Status: early development. User accounts, GitHub import, static code analysis and
> AI explanations are in place: save a public repository, browse its files with an
> outline of every function and class, see its dependencies, frameworks and most
> important files, and get an overview and file explanations that quote the code they
> rely on. Chat and interview features are being built milestone by milestone (see
> [docs/architecture.md](docs/architecture.md)).

## Tech stack

| Layer | Tools |
|---|---|
| Frontend | React, TypeScript, Vite, Tailwind CSS, React Router, TanStack Query, Lucide |
| Backend | Python 3.11, FastAPI, Pydantic, SQLAlchemy 2, Alembic |
| Database | PostgreSQL 17 |
| AI | Google Gemini behind a swappable provider layer; Sentence Transformers and FAISS (planned) |
| Code analysis | Python `ast`, Tree-sitter (JavaScript, TypeScript, Java), GitHub REST API |
| Testing | Pytest, Vitest, React Testing Library |

## Project layout

```
backend/     FastAPI app, Alembic migrations, pytest suite
frontend/    React + Vite single-page app
docker/      Container init scripts (Postgres)
docs/        Architecture and design notes
```

## Getting started

### Requirements

- Python 3.11+
- Node.js 20+
- Docker (for PostgreSQL)

### 1. Start the database

```bash
docker compose up -d
```

This starts PostgreSQL on `localhost:5433` with two databases: `repinspect` for
development and `repinspect_test` for the test suite. Port 5433 is used so it does
not clash with a PostgreSQL already installed on your machine; change it with the
`POSTGRES_PORT` environment variable (and update `DATABASE_URL` to match).

### 2. Run the backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

`.env.example` ships with a development-only `JWT_SECRET` so the app runs locally
straight away. The app refuses to start in production (`APP_ENV=production`) with that
placeholder; generate a real key first:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

The API runs at http://localhost:8000. Interactive docs are at
http://localhost:8000/api/docs, and a health check is at `/api/health`.

### 3. Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The Vite dev server forwards `/api` requests to the backend,
so both run under one origin in the browser.

## Analyzing GitHub repositories

Log in, paste a public repository URL on the dashboard and press Analyze. The backend
reads the repository in the background and the page shows progress.

- GitHub allows **60 API requests per hour** without a token, shared by everyone on
  your network, and each analysis uses 4. When the limit is hit the page says when to
  try again. For regular use, create a token with no extra permissions at
  https://github.com/settings/tokens and set `GITHUB_TOKEN` in `backend/.env`.
- Only public repositories are supported. Private ones look the same as missing ones.
- Repository code is only ever read as text, never executed. Files such as `.env` and
  private keys are never stored, and secret-looking values in source files are
  replaced with `[REDACTED]`.
- Very large repositories are cut off at the limits in `.env.example` and flagged.

When the import finishes you get three views:

- **Overview**: language breakdown (by lines of code), statistics, the frameworks and
  libraries detected (each with the file and line that proves it), and the files most
  worth reading first, with the reason for each.
- **Files**: a file tree with search, a code viewer, an outline of the functions and
  classes in each file, and its imports. Imports of other files in the repository are
  links, and every file lists the files that import it.
- **Dependencies**: everything declared in `requirements.txt`, `pyproject.toml`,
  `package.json`, `pom.xml` and Gradle files, grouped by manifest and filterable.

Python is parsed with the standard library's `ast` module; JavaScript, TypeScript and
Java with Tree-sitter. Code is only parsed, never run.

## AI explanations

With an AI key configured, each analyzed repository gets three kinds of explanation,
generated on request:

- **How this project works** (Overview tab): ten short sections covering purpose,
  architecture, frontend, backend, data flow, important modules, how it runs and key
  decisions.
- **Technology explanations** (Overview tab): what each detected framework or library
  is, its strengths, alternatives and trade-offs. This is general knowledge and is shown
  apart from the evidence found in the code.
- **Explain this file** (Files tab): purpose, inputs and outputs, and the key functions
  and classes, each a link to its line.

The model only sees facts from the static analysis plus excerpts of the most important
files, never the whole repository. Every quote it gives is checked against the real
file before anything is shown. Claims backed by a confirmed quote are highlighted in
amber with a link to the lines; anything the code does not confirm is marked as
inference, and parts the analyzed files do not answer say so instead of guessing.

### Setting up a Gemini key

1. Create a free key at https://aistudio.google.com/apikey.
2. Add it to `backend/.env` as `GEMINI_API_KEY=...` and restart the backend.

Without a key everything else works and the AI buttons explain that AI is not set up.
The free tier has small daily quotas and is sometimes busy, so the server retries
temporary errors, and each user gets a daily allowance (40 requests by default) with at
most two running at once. These limits are in `.env.example`. On the free tier Google
may use the prompts to improve its products, so do not analyze code you are not allowed
to share.

## Running tests

```bash
# Backend (needs the database container running)
cd backend
pytest

# Frontend
cd frontend
npm test
npm run lint
npm run build
```

## Configuration

Backend settings are read from environment variables or `backend/.env` (found
relative to the code, so the server can be started from any directory). See
[`backend/.env.example`](backend/.env.example) for the available options. Secrets
(API keys, JWT secret, database password) live only in `.env`, which is git-ignored,
and are never exposed to the frontend.
