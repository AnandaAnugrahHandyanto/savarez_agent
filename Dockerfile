FROM ghcr.io/astral-sh/uv:python3.11-bookworm

WORKDIR /app

# Minimal system packages needed by Hermes + startup script
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy full repo into the image
COPY . /app

# Install THIS repo as Hermes (editable) and install the lightweight web wrapper deps
RUN uv pip install --system --no-cache-dir -e ".[all]" && \
    uv pip install --system --no-cache-dir \
      starlette \
      uvicorn

# Prepare persistent Hermes home
RUN mkdir -p /data/.hermes

# Ensure startup script can run
RUN chmod +x /app/start.sh

# Railway/runtime environment
ENV HOME=/data
ENV HERMES_HOME=/data/.hermes
ENV PORT=8080

EXPOSE 8080

CMD ["/app/start.sh"]
