# AgentCore MCP server container — Art Gallery
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
COPY logging_config.py .
COPY image_style_outback.jpg .
COPY image_style_bush.jpg .
COPY image_style_night.jpg .
COPY image_style_beach.jpg .
COPY image_style_river.jpg .
COPY image_style_billabong.jpg .
COPY image_style_city.jpg .
COPY image_style_town.jpg .

EXPOSE 8000

CMD ["python", "server.py"]
