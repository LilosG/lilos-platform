FROM python:3.12.12-slim-bookworm

ARG UV_VERSION=0.9.28

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_FROZEN=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/lilos-venv \
    PATH="/opt/lilos-venv/bin:${PATH}"

RUN apt-get update \
    && apt-get install --no-install-recommends --yes ca-certificates tini \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --no-cache-dir "uv==${UV_VERSION}" \
    && groupadd --gid 10001 lilos \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin lilos

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY --chown=lilos:lilos alembic.ini ./
COPY --chown=lilos:lilos apps ./apps
COPY --chown=lilos:lilos migrations ./migrations
COPY --chown=lilos:lilos scripts ./scripts

USER lilos

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "uvicorn", "apps.api.app.main:app", "--host", "0.0.0.0", "--port", "10000"]
