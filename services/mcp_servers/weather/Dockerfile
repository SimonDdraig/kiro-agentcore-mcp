# AgentCore MCP server container — Weather
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
COPY logging_config.py .

EXPOSE 8000

CMD ["python", "server.py"]
