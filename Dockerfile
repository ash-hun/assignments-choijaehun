# API 서버, 배치(Ingest, 선정 실험, Eval), 테스트가 같은 의존성 잠금(uv.lock)을 쓰도록 한 이미지에서 갈라진다.
FROM ghcr.io/astral-sh/uv:0.8.13 AS uv

FROM python:3.12.12-slim-bookworm AS base
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /workspace
RUN groupadd --system app && useradd --system --gid app --home-dir /workspace app

FROM base AS runtime
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app ./app
USER app

FROM base AS dev
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project
COPY app ./app
COPY tests ./tests
USER app
