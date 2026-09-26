# ─────────────────────────────────────────────
# Stage 1 — Builder: install dependencies (cached until requirements.txt changes)
# ─────────────────────────────────────────────
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip==26.0.1 && \
    pip install --no-cache-dir -r requirements.txt

# ─────────────────────────────────────────────
# Stage 2 — Runtime: app code only, non-root
# ─────────────────────────────────────────────
FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY app/ ./app/
RUN adduser --disabled-password --gecos "" appuser
USER appuser
EXPOSE 8003
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8003/health', timeout=4)"]
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003", "--loop", "asyncio"]
