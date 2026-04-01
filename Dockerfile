FROM astral-sh/uv:trixie-slim

WORKDIR /opt/hermes

RUN apt-get update &&\
    apt-get install -y --no-install-recommends \
        build-essential git curl nodejs npm ripgrep ffmpeg gcc python3 python3-pip python3-dev libffi-dev &&\
    rm -rf /var/lib/apt/lists/*

RUN npx playwright install --with-deps chromium --only-shell  &&\
    rm -rf /var/lib/apt/lists/*

COPY package*.json ./
RUN npm ci --omit=dev --prefer-offline --no-audit &&\
    npm cache clean --force

COPY ./scripts/whatsapp-bridge/package*.json ./scripts/whatsapp-bridge
RUN cd /opt/hermes/scripts/whatsapp-bridge &&\
    npm ci --prefer-offline --no-audit &&\
    npm cache clean --force

COPY . .

RUN uv pip install --no-cache -e ".[all]" --system &&\
    chmod +x /opt/hermes/docker/entrypoint.sh

ENV HERMES_HOME=/opt/data
VOLUME [ "/opt/data" ]
ENTRYPOINT [ "/opt/hermes/docker/entrypoint.sh" ]
