FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# PyTorch is only used to run the small embedding model on the CPU. The CPU-only wheel is
# a few hundred MB instead of several GB, and installing it first means the next step sees
# torch already satisfied.
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

COPY pyproject.toml ./
COPY app ./app
RUN pip install .

COPY alembic.ini ./
COPY alembic ./alembic

# Imported source code and the embedding model live on volumes mounted at /data.
RUN useradd --system --create-home repinspect \
    && mkdir -p /data/artifacts /data/models \
    && chown -R repinspect /data
ENV ARTIFACT_DIR=/data/artifacts \
    MODEL_CACHE_DIR=/data/models \
    APP_ENV=production
USER repinspect

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=30s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"

# One process: analysis jobs run in threads of the API process, and the login limiter keeps
# its counts in memory. Migrations run first so a new version never meets an old schema.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
