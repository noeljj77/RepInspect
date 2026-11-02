# RepInspect

**Understand the code. Own the interview.**

RepInspect analyzes a GitHub repository (or an uploaded ZIP), maps its structure and
technologies, and answers questions about the implementation with references to the
exact files and lines. It then turns the codebase into interview preparation: a
project report, repository-specific questions and a mock interview with feedback.

> Status: early development. The project foundation is in place; repository analysis,
> chat and interview features are being built milestone by milestone (see
> [docs/architecture.md](docs/architecture.md)).

## Tech stack

| Layer | Tools |
|---|---|
| Frontend | React, TypeScript, Vite, Tailwind CSS, React Router, TanStack Query, Lucide |
| Backend | Python 3.11, FastAPI, Pydantic, SQLAlchemy 2, Alembic |
| Database | PostgreSQL 17 |
| AI (planned) | Sentence Transformers, FAISS, configurable LLM provider |
| Code analysis (planned) | Python `ast`, Tree-sitter, GitHub REST API |
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

Backend settings are read from environment variables or `backend/.env`. See
[`backend/.env.example`](backend/.env.example) for the available options. Secrets
(API keys, JWT secret, database password) live only in `.env`, which is git-ignored,
and are never exposed to the frontend.
