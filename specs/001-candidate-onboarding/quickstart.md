# Quickstart — validación de la feature 001

**Feature**: 001-candidate-onboarding · **Fecha**: 2026-08-10

Guía para levantar el entorno y **verificar** que la feature cumple lo que la spec exige. No contiene implementación: los detalles de modelo están en [data-model.md](./data-model.md), los de API en [contracts/openapi.yaml](./contracts/openapi.yaml) y las decisiones en [research.md](./research.md).

---

## 0. Requisitos previos

| Requisito | Comprobación |
|---|---|
| Docker + Docker Compose | `docker compose version` |
| uv (gestor de Python) | `uv --version` |
| Node 20 LTS (vía `.nvmrc`) | `node --version` |
| En Windows: trabajar dentro de **WSL2**, con el repo en el FS de WSL (ADR-000) | `pwd` no empieza por `/mnt/c` |
| `git config --global core.autocrlf false` en ambas máquinas | `git config core.autocrlf` |
| Clave de API de Google Gemini | `GOOGLE_API_KEY` en `.env` |
| **ADR-007 ratificado** (object storage y cifrado) | Ver [plan.md](./plan.md) §Decisiones abiertas. Sin él, el adapter de storage no debe implementarse |

```bash
cp infra/.env.example .env      # rellenar con valores reales del gestor de contraseñas
```

Variables mínimas: `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `DOCUMENT_ENCRYPTION_KEY`, `GOOGLE_API_KEY`, `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `PRIVACY_POLICY_VERSION`.

Al añadir una variable nueva, actualizar `.env.example` **en el mismo commit**: es la única forma de que la otra máquina se entere (ADR-000).

---

## 1. Levantar el entorno

```bash
docker compose -f infra/compose/docker-compose.yml up -d   # postgres, redis, minio
cd backend && uv sync --frozen && uv run alembic upgrade head
uv run uvicorn app.main:app --reload                       # API en :8000
uv run celery -A app.workers.celery_app worker -l info     # worker, otra terminal
cd ../frontend && npm ci && npm run dev                    # SPA en :5173
```

**Verificación de que el entorno está sano:**

```bash
curl -s localhost:8000/health                 # {"status":"ok"}
docker compose exec postgres psql -U vokara -c "\dx"   # citext y vector presentes
```

---

## 2. Contrato tipado extremo a extremo (art. I)

```bash
cd backend && uv run python -m app.openapi_export > ../frontend/openapi.json
cd ../frontend && npm run generate:api        # openapi-typescript → src/api/schema.d.ts
git diff --exit-code frontend/openapi.json frontend/src/api/schema.d.ts
```

**Esperado**: sin diferencias. Un diff aquí significa que alguien cambió la API sin regenerar el cliente; CI falla por lo mismo.

**Prueba negativa (hazla una vez, para creerte el mecanismo)**: renombra un campo de un esquema Pydantic del backend, regenera y ejecuta `npm run build`. El build de TypeScript debe **fallar**. Si compila, el art. I no está realmente aplicado.

---

## 3. Recorrido manual del camino feliz

Con la SPA en `localhost:5173`:

| # | Acción | Resultado esperado | Requisito |
|---|---|---|---|
| 1 | Registrarse e iniciar sesión | Access token en memoria; cookie de refresh `httpOnly` visible en DevTools → Application → Cookies, **no** en localStorage | ADR-001 |
| 2 | Intentar subir un CV sin aceptar el aviso | Rechazo con `CONSENT_REQUIRED` y enlace al aviso | FR-030 |
| 3 | Aceptar el aviso y subir `golden_set/cv_es_basico.pdf` | Respuesta inmediata con indicador de progreso; el estado avanza `queued → running → succeeded` | FR-004, US1 AC1 |
| 4 | Esperar a que termine | Entradas agrupadas por tipo, **todas** con origen `cv_seed`; perfil en `draft` | FR-009, FR-011, FR-014 |
| 5 | Recargar la página a media revisión | Vuelve al mismo punto del flujo con los cambios guardados | FR-019, US2 AC5 |
| 6 | Editar una entrada `cv_seed` | Mismo `id`, origen ahora `user_edited` | FR-010, FR-016, US2 AC1 |
| 7 | Guardar una entrada sin cambiar nada | El origen **no** cambia | research R-09 |
| 8 | Crear una entrada nueva | Origen `user_added` | FR-018 |
| 9 | Eliminar una entrada | Desaparece y no reaparece al recargar | FR-017 |
| 10 | Poner salario mínimo > máximo | Rechazo con mensaje en español | FR-021, US3 AC2 |
| 11 | Intentar confirmar con el cuestionario incompleto | Bloqueado, con la lista exacta de lo que falta | FR-024, US3 AC3 |
| 12 | Completar objetivos y confirmar | Perfil `complete`, versión 1 creada con marca de tiempo | FR-023, FR-025, US4 AC1 |
| 13 | Editar una entrada tras confirmar | Perfil **sigue** `complete`; aparece aviso visible de cambios sin confirmar y su detalle | FR-027, FR-029, US4 AC4/AC7 |
| 14 | Consultar la versión 1 en el historial | Contenido íntegro del momento de la confirmación, **sin** los cambios posteriores | FR-026, FR-028, US4 AC5 |
| 15 | Confirmar los cambios pendientes | Versión 2 creada y vigente; ya no hay cambios pendientes | FR-025, US4 AC6 |

---

## 4. Recorridos de rechazo y salidas alternativas

| Archivo del golden set | Resultado esperado | Requisito |
|---|---|---|
| `cv_escaneado.pdf` (sin capa de texto) | Falla con `PDF_WITHOUT_TEXT_LAYER`, explica que v1 no procesa escaneos y ofrece **captura manual guiada**. Cero entradas creadas | FR-006, SC-009 |
| `factura.pdf` | Falla con `DOCUMENT_NOT_A_RESUME`. Cero entradas, perfil intacto | FR-005, SC-008 |
| `cv_corrupto.pdf` | Rechazo **síncrono** con `DOCUMENT_CORRUPT`; no se crea documento | FR-002 |
| `imagen.png` renombrada a `.pdf` | Rechazo con `UNSUPPORTED_FILE_TYPE` (detección por firma de bytes, no por extensión) | FR-002, research R-01 |
| Archivo de 12 MB | Rechazo con `FILE_TOO_LARGE` antes de leer el cuerpo completo | FR-001 |
| `cv_dos_columnas.pdf` | Entradas sin contenido intercalado entre columnas; lo que no se pudo estructurar llega marcado como incompleto | US1 AC5 |
| `cv_en_ingles.pdf` | Contenido en inglés sin traducir, `content_language = "en"`; la interfaz sigue en español | FR-012, US1 AC4 |
| `cv_minimo.pdf` | `DOCUMENT_TOO_SPARSE` con oferta de construir el perfil manualmente | Edge case |

**Captura manual guiada completa (SC-010)**: partiendo de un `PDF_WITHOUT_TEXT_LAYER`, crear entradas a mano, completar objetivos y confirmar. Debe llegarse a `complete` sin haber sembrado nada desde archivo (FR-007).

**Reintento (FR-008)**: forzar un fallo de proveedor (`GOOGLE_API_KEY` inválida), verificar `EXTRACTION_FAILED` con opción de reintentar; crear una entrada a mano; restaurar la clave y reintentar. La entrada manual **sigue ahí** y las sembradas se añaden sin duplicar.

**Un solo procesamiento activo**: subir un segundo CV mientras el primero procesa → `PARSE_JOB_ALREADY_ACTIVE`.

**Cierre del navegador**: cerrar la pestaña durante el procesamiento y volver a entrar → se ve el progreso o el resultado, sin re-subir.

---

## 5. Suite automatizada

```bash
cd backend
uv run ruff check . && uv run ruff format --check .
uv run mypy --strict app
uv run pytest tests/unit tests/integration tests/architecture -q --cov=app --cov-report=term-missing
uv run pytest tests/evals -q                      # requiere GOOGLE_API_KEY
cd ../frontend && npm run test && npm run build
```

**Umbrales que deben cumplirse** (todos bloqueantes en CI):

| Comprobación | Umbral | Requisito |
|---|---|---|
| ruff (lint + format) | 0 hallazgos | Art. VI |
| `mypy --strict` | 0 errores | Art. I |
| Cobertura en `app/services` y `app/domain` | ≥ 80% | Art. VI |
| Tasa de error por campo en evals | < 5% | SC-003 |
| Campos inventados en evals | 0 | FR-013, art. IV |
| Detección de no-CV y de PDF escaneado | 100% | SC-008, SC-009 |
| Drift del cliente TS | 0 diferencias | Art. I |

### Pruebas que merecen ejecución explícita

```bash
# Art. II — dependencias unidireccionales
uv run pytest tests/architecture -q
# Falla si api/ importa db/, o si adapters/ importa services/.

# Art. X — ningún camino alterno llega a `complete`
uv run pytest tests/integration/test_confirmation_gate.py -q
# Intenta alcanzar `complete` por reintento de parseo, edición masiva, PATCH
# directo de objetivos y escritura de repositorio. Todos deben fallar. (SC-001)

# FR-034 — aislamiento entre candidatos
uv run pytest tests/integration/test_access_control.py -q
# El candidato B recibe 404 en cada recurso del candidato A: perfil, entradas,
# versiones, documentos y parse jobs.

# ADR-001 — seguridad de sesión
uv run pytest tests/integration/test_auth_security.py -q
# Rotación de refresh, detección de reuso (revoca la familia), expiración,
# revocación de jti y límite de tasa.

# FR-031 — PII fuera de logs
uv run pytest tests/integration/test_no_pii_in_logs.py -q
# Procesa un CV con nombre y teléfono sembrados y verifica que ninguna cadena
# aparece en los logs capturados ni en llm_call_logs.

# Migración reversible (DoD de la constitución)
uv run alembic upgrade head && uv run alembic downgrade base && uv run alembic upgrade head
```

---

## 6. Verificación de los criterios de éxito

| Criterio | Cómo se comprueba |
|---|---|
| **SC-001** — 100% de `complete` con confirmación explícita | `tests/integration/test_confirmation_gate.py` + consulta de auditoría: `SELECT count(*) FROM candidate_profiles p WHERE p.state='complete' AND p.current_version_id IS NULL` debe dar **0** (además el `CHECK` de la base lo hace imposible) |
| **SC-002** — 100% de entradas con `id` estable y origen | `NOT NULL` sobre `origin`, PK sobre `id` y test que verifica que el `id` sobrevive a una edición |
| **SC-003** — error de extracción < 5% | `pytest tests/evals`, métrica bloqueante |
| **SC-004** — p95 < 60 s de subida a entradas revisables | Las evals miden la duración por etapa contra el presupuesto de [research.md](./research.md) R-14 (objetivo p95 ≈ 45 s) |
| **SC-005** — una versión por confirmación, historial íntegro | Test que confirma dos veces y verifica `version_number` 1 y 2, contenido completo en ambas y trigger de inmutabilidad activo |
| **SC-006 / SC-007** — tiempo hasta confirmar, % que enriquece | Métricas de producto: se instrumentan aquí (evento de confirmación con marca de tiempo, conteo de entradas por origen) y se miden en beta (roadmap Fase 5). No son verificables en CI |
| **SC-008** — 100% de rechazos accionables sin crear entradas | Casos de rechazo de la §4 + test que verifica cero filas en `profile_entries` tras cada rechazo |
| **SC-009** — 100% de PDF escaneados detectados antes de extraer | Eval bloqueante + test unitario de la heurística con casos límite (PDF híbrido, CV minimalista) |
| **SC-010** — perfil `complete` sin archivo | Recorrido de captura manual guiada de la §4, automatizado en `tests/integration/test_manual_capture_flow.py` |

---

## 7. Antes de abrir el PR

- [ ] `ruff`, `mypy --strict`, tests, evals y build del front en verde localmente
- [ ] Cliente TS regenerado y commiteado
- [ ] Migración Alembic con `downgrade` **probado**, no solo escrito
- [ ] `.env.example` actualizado si se añadió alguna variable
- [ ] Ningún mensaje de error nuevo fuera de [contracts/errors.md](./contracts/errors.md)
- [ ] Ningún log ni traza con contenido del documento (FR-031)
- [ ] Golden set sin material de usuarios reales (FR-032)
- [ ] **ADR-007 ratificado** si el PR toca el adapter de storage
- [ ] Rama `001-candidate-onboarding`, nunca `main`; commits en inglés (art. IX)
