FROM python:3.13-slim
WORKDIR /srv/relay
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY relay/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY relay/ .
RUN mkdir -p /data
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn app:production --factory --host 0.0.0.0 --port ${PORT:-8080} --no-access-log --limit-concurrency 32 --timeout-keep-alive 10"]
