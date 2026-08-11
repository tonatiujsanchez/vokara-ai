# syntax=docker/dockerfile:1
#
# Imagen del backend: api y worker comparten la misma.
# El contexto de build es la raíz del repositorio (ver infra/docker-compose.yml).

# ── builder ───────────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    # El entorno vive fuera de /app para que el bind mount de desarrollo no lo
    # tape (infra/docker-compose.override.yml).
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /src

# Solo el manifiesto y el lock: esta capa se reaprovecha mientras no cambien.
COPY backend/pyproject.toml backend/uv.lock ./

# --frozen: el lock manda, se instala lo mismo en todas las máquinas (ADR-000).
# --no-install-project: el código va por PYTHONPATH, no como paquete instalado.
RUN uv sync --frozen --no-dev --no-install-project

# ── runtime ───────────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:${PATH}" \
    PYTHONPATH=/app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY backend/ /app/
COPY infra/docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Usuario sin privilegios. /data se crea aquí y con este dueño para que el
# volumen nombrado herede la propiedad al montarse: si no, el contenedor no
# podría escribir los CVs (ADR-007).
RUN useradd --create-home --uid 1000 vokara \
    && mkdir -p /data \
    && chown -R vokara:vokara /app /data

USER vokara

EXPOSE 8000

# El entrypoint aplica `alembic upgrade head` antes de arrancar lo que reciba:
# el usuario nunca ejecuta Alembic a mano (roadmap §11.1).
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
