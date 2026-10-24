FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 WICHTELN_DB=/data/wichteln.db
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY wichteln ./wichteln
COPY wsgi.py .

RUN useradd --system --uid 10001 wichteln && mkdir /data && chown wichteln /data
USER wichteln
VOLUME /data
EXPOSE 8000

# Kein Access-Log: die URLs enthalten die geheimen Tokens.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "wsgi:application"]
