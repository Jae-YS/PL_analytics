# Python 3.14 to match the local venv (python:3.14-slim exists on Docker Hub).
FROM python:3.14-slim

# No .pyc files, and logs go straight to stdout so Cloud Run can collect them.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first. This layer is rebuilt only when requirements.txt
# changes, not on every code edit.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Only the code the API imports. Data, evals, tests and scripts stay out.
COPY pl_agent/ pl_agent/
COPY src/ src/

# Run as a normal user, not root.
RUN useradd --create-home app
USER app

# Cloud Run sends requests to $PORT (default 8080) and requires the server to
# listen on 0.0.0.0, not 127.0.0.1.
ENV PORT=8080
EXPOSE 8080

# "exec" makes uvicorn the main process so it receives shutdown signals.
# One worker: sessions live in memory, so workers would not share them.
CMD ["sh", "-c", "exec uvicorn src.api:app --host 0.0.0.0 --port ${PORT:-8080}"]