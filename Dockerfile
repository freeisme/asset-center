FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends default-mysql-client \
    && rm -rf /var/lib/apt/lists/*

COPY server.py ./
COPY office_asset ./office_asset
COPY database/migrations ./database/migrations
COPY tools/migration_runner.py ./tools/migration_runner.py
COPY web ./web

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MYSQL_BIN=/usr/bin/mysql \
    MYSQLDUMP_BIN=/usr/bin/mysqldump \
    BACKUP_DIR=/app/backups \
    SERVER_HOST=0.0.0.0 \
    SERVER_PORT=8000

EXPOSE 8000

CMD ["python", "server.py"]
