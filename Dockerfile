# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ENVIRONMENT=production

WORKDIR /app

# Layer 1: dependencies (cached against requirements.txt alone)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Layer 2: full source (README.md/LICENSE/pyproject.toml are present now,
# so building the project succeeds), then install qme itself --no-deps
# (deps are already in layer 1).
COPY . ./
RUN pip install --no-cache-dir --no-deps .

EXPOSE 8000

# Railway injects $PORT; exec-form sh -c expands it at runtime.
# Falls back to 8000 for local `docker run -p 8000:8000`.
CMD ["sh", "-c", "exec uvicorn qme.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
