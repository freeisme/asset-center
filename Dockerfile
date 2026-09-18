# 构建新版前端（Vue + Vite）。产物落到 /web/app，由运行阶段复制进镜像。
FROM node:22-alpine AS frontend

WORKDIR /frontend

RUN corepack enable

COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
COPY VERSION /VERSION
RUN pnpm build

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
COPY --from=frontend /web/app ./web/app
COPY VERSION ./

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MYSQL_BIN=/usr/bin/mysql \
    MYSQLDUMP_BIN=/usr/bin/mysqldump \
    BACKUP_DIR=/app/backups \
    SERVER_HOST=0.0.0.0 \
    SERVER_PORT=8000

EXPOSE 8000

CMD ["python", "server.py"]
