FROM debian:13.4

# Install system dependencies in one layer, clear APT cache
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential nodejs npm python3 python3-pip ripgrep ffmpeg gcc python3-dev libffi-dev && \
    rm -rf /var/lib/apt/lists/*

COPY . /opt/hermes
WORKDIR /opt/hermes

# Install Python and Node dependencies in one layer, no cache.
# Avoid `.[all]` here: pip's resolver on Debian 13 / Python 3.13 backtracks
# too deeply on the self-referential extra graph (especially overlapping
# messaging/slack extras). Use a flattened extras list instead.
RUN pip install --no-cache-dir -e ".[modal,daytona,messaging,cron,cli,dev,tts-premium,pty,honcho,mcp,homeassistant,sms,acp,voice,dingtalk,feishu,mistral]" --break-system-packages && \
    npm install --prefer-offline --no-audit && \
    npx playwright install --with-deps chromium --only-shell && \
    cd /opt/hermes/scripts/whatsapp-bridge && \
    npm install --prefer-offline --no-audit && \
    npm cache clean --force

WORKDIR /opt/hermes
RUN chmod +x /opt/hermes/docker/entrypoint.sh

ENV HERMES_HOME=/opt/data
VOLUME [ "/opt/data" ]
ENTRYPOINT [ "/opt/hermes/docker/entrypoint.sh" ]
