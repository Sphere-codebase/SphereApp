FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY alembic.ini /app/alembic.ini
COPY app /app/app
COPY docker/entrypoint.sh /app/docker/entrypoint.sh

RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir \
      "fastapi==0.115.6" \
      "uvicorn[standard]==0.30.6" \
      "pydantic==2.10.4" \
      "pydantic-settings==2.7.0" \
      "email-validator==2.2.0" \
      "httpx==0.27.2" \
      "python-jose[cryptography]==3.3.0" \
      "passlib[bcrypt]==1.7.4" \
      "sqlalchemy==2.0.36" \
      "alembic==1.14.0" \
      "psycopg[binary]==3.2.3" \
      "tenacity==9.0.0"

RUN chmod +x /app/docker/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
