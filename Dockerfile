# MCP server image. NOTE: Fusion 360 itself cannot run here — this containerizes
# ONLY the server. The Fusion add-in must run on the host; the container reaches
# it via host.docker.internal (see docker-compose.yml).

FROM python:3.12-slim

LABEL org.opencontainers.image.title="self-host-fusion360-mcp"
LABEL org.opencontainers.image.description="Self-hosted Fusion 360 MCP server (server layer only)."
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Install deps first for better layer caching.
COPY pyproject.toml README.md ./
COPY server ./server
RUN pip install --no-cache-dir ".[http]"

# HTTP transport defaults; the add-in lives on the host.
ENV FUSION_MCP_TRANSPORT=http \
    FUSION_MCP_HTTP_HOST=0.0.0.0 \
    FUSION_MCP_HTTP_PORT=8765 \
    FUSION_ADDIN_URL=http://host.docker.internal:9000 \
    PYTHONUNBUFFERED=1

EXPOSE 8765

ENTRYPOINT ["fusion-mcp"]
CMD ["run", "--transport", "http"]
