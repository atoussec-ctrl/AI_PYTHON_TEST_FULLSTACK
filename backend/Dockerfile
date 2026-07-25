FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PROMETHEUS_MULTIPROC_DIR=/tmp/mindsight-prometheus \
    PROMETHEUS_DISABLE_CREATED_SERIES=True

WORKDIR /app

RUN python -m venv /opt/venv

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

COPY migrations ./migrations
COPY run.py ./run.py
COPY gunicorn.conf.py ./gunicorn.conf.py

RUN mkdir -p /app/storage/uploads

EXPOSE 5000

CMD ["sh", "-c", "rm -rf /tmp/mindsight-prometheus && mkdir -p /tmp/mindsight-prometheus && exec gunicorn --preload --config gunicorn.conf.py --bind 0.0.0.0:5000 --workers 2 --timeout 60 run:app"]
