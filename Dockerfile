# syntax=docker/dockerfile:1

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (minimal)
RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Install app
COPY pyproject.toml README.md /app/
COPY src /app/src

# Install with OpenAI extra so custom endpoint/OpenAI mode works in containers
RUN pip install --no-cache-dir -U pip \
  && pip install --no-cache-dir ".[openai]"

# Run as non-root
RUN useradd -m -u 10001 appuser
USER 10001

# Persist local config/tokens here (mount a volume in k8s)
VOLUME ["/data"]

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/healthz').read()" || exit 1

CMD ["prreviewbot", "serve", "--host", "0.0.0.0", "--port", "8765", "--no-open", "--data-dir", "/data"]


