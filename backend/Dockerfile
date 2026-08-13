FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /workspace

COPY backend/pyproject.toml /workspace/backend/pyproject.toml
COPY backend/app /workspace/backend/app
COPY data /workspace/data

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir /workspace/backend \
    && mkdir -p /workspace/runtime/chroma

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3)"

CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
