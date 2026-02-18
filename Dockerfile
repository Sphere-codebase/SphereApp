FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SKIP_PDF_TESTS=1

WORKDIR /app

COPY alembic.ini /app/alembic.ini
COPY pyproject.toml /app/pyproject.toml
COPY app /app/app
COPY docker/entrypoint.sh /app/docker/entrypoint.sh
#COPY docs /app/docs

RUN python -m pip install --no-cache-dir --upgrade pip \
 && python -m pip install --no-cache-dir .


RUN chmod +x /app/docker/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
