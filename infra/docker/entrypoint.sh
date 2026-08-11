#!/bin/sh
# Aplica las migraciones y arranca lo que le pasen.
#
# El usuario nunca ejecuta un comando de Alembic, ni en la primera instalación
# ni al actualizar (roadmap §11.1, research R-20). Eso es lo que hace que
# `docker compose up` sea de verdad un solo comando.
set -eu

cd "${VOKARA_APP_DIR:-/app}"

# El worker comparte esta imagen y no debe migrar: dos procesos aplicando la
# misma migración a la vez es una carrera sin premio.
if [ "${VOKARA_APPLY_MIGRATIONS:-1}" = "1" ]; then
  attempt=1
  max_attempts="${VOKARA_MIGRATION_ATTEMPTS:-30}"

  until alembic upgrade head; do
    if [ "$attempt" -ge "$max_attempts" ]; then
      echo "La base de datos no está lista. Suele tardar unos segundos en el" >&2
      echo "primer arranque; si persiste, revisa que Docker esté corriendo." >&2
      exit 1
    fi
    echo "Esperando a la base de datos... (intento $attempt de $max_attempts)" >&2
    attempt=$((attempt + 1))
    sleep 2
  done
fi

exec "$@"
