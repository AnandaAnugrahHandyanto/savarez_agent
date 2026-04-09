FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/sh hermes

COPY . .

RUN python -m pip install --no-cache-dir uv \
 && uv sync --locked --no-dev --extra api-server --extra pty \
 && chmod 755 /app/scripts/railway-start.sh \
 && mkdir -p /data \
 && chown -R hermes:hermes /app /data

USER hermes

ENV HERMES_HOME=/data/hermes

EXPOSE 8642

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD python -c "import os, sys, urllib.request; port = os.environ.get('PORT', '8642'); url = f'http://127.0.0.1:{port}/health'; sys.exit(0 if urllib.request.urlopen(url, timeout=5).status == 200 else 1)"

CMD ["./scripts/railway-start.sh"]
