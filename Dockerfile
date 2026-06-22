FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=8787
ENV FINANCE_AGENT_DATA_DIR=/app/data
ENV FINANCE_AGENT_UPLOADS_DIR=/app/uploads

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY finance_agent ./finance_agent
COPY static ./static
COPY README.md pyproject.toml ./

RUN mkdir -p /app/data /app/uploads

EXPOSE 8787

CMD ["python", "-m", "finance_agent.server"]
