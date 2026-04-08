FROM debian:13.4

# Install system dependencies in one layer, clear APT cache
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential nodejs npm python3 python3-pip ripgrep ffmpeg gcc python3-dev libffi-dev && \
    rm -rf /var/lib/apt/lists/*

COPY . /opt/hermes
WORKDIR /opt/hermes

# Install Python and Node dependencies in one layer, no cache
RUN pip install --no-cache-dir -e ".[all]" --break-system-packages && \
    npm install --prefer-offline --no-audit && \
    npx playwright install --with-deps chromium --only-shell && \
    cd /opt/hermes/scripts/whatsapp-bridge && \
    npm install --prefer-offline --no-audit && \
    npm cache clean --force

WORKDIR /opt/hermes
RUN chmod +x /opt/hermes/docker/entrypoint.sh

# Run as non-root user for defense-in-depth
RUN groupadd -r hermes && useradd -r -g hermes -d /opt/data -s /bin/bash hermes && \
    mkdir -p /opt/data && chown -R hermes:hermes /opt/data /opt/hermes

ENV HERMES_HOME=/opt/data
VOLUME [ "/opt/data" ]
USER hermes
ENTRYPOINT [ "/opt/hermes/docker/entrypoint.sh" ]
