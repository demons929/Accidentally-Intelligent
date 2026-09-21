# HarryPort — dashboard image (lightweight: server + data, no ML training deps)
# Build:   docker compose build
# Run:     docker compose up -d   ->  http://localhost:8000
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Lightweight deps (verified enough for the dashboard).
# To also run pipeline / training in-container, switch to requirements.txt.
COPY requirements.lite.txt ./
RUN pip install --no-cache-dir -r requirements.lite.txt

# Full project (includes seeded harryport.db + resources bundle).
COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

# Bind 0.0.0.0 so the container port mapping works.
CMD ["python", "run_server.py", "--host", "0.0.0.0", "--port", "8000"]
