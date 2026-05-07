# AgentCore agent container — Bush Ranger AI
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY handler.py .
COPY logging_config.py .

EXPOSE 8080

# Set OTel resource attributes so traces are tagged with the agent service name
ENV OTEL_RESOURCE_ATTRIBUTES="service.name=bush_ranger_agent.DEFAULT"

# Launch with opentelemetry-instrument for automatic OTel tracing
CMD ["opentelemetry-instrument", "python", "handler.py"]
