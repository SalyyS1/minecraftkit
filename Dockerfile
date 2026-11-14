FROM python:3.12-slim

WORKDIR /app

COPY SKILL.md README.md NOTICE.md manifest.json ./
COPY data/ ./data/
COPY scripts/ ./scripts/
COPY skill-wrappers/ ./skill-wrappers/
COPY references/ ./references/

ENTRYPOINT ["python3", "-B", "scripts/mcp_server.py"]
