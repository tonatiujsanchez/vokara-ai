# Tasks: Onboarding del candidato — de la primera ejecución al perfil maestro confirmado

**Feature**: `001-candidate-onboarding` · **Fecha**: 2026-08-11

**Input**: documentos de diseño en `specs/001-candidate-onboarding/`

**Prerequisitos leídos**: [plan.md](./plan.md) · [spec.md](./spec.md) · [research.md](./research.md) · [data-model.md](./data-model.md) · [contracts/](./contracts/) · [quickstart.md](./quickstart.md) · constitución **v2.1.0**

---

## Organización en tres bloques

El trabajo va en **tres bloques con checkpoint verificable entre ellos**. **Ningún bloque empieza sin que el checkpoint del anterior esté en verde.**

| Bloque | Contenido | Fases | Checkpoint |
|---|---|---|---|
| **A — Fundaciones** | Monorepo, tooling, Compose local, migración inicial, CI bloqueante, contrato tipado E2E | 1 y 2 | `docker compose up` levanta cuatro servicios, migraciones automáticas, endpoint que viaja de DB a UI con tipos generados, CI verde |
| **B — Primera ejecución (US1)** | Divulgación, catálogo de proveedores, preflight, correo opcional, reanudación | 3 | Alguien que clona el repo llega de `docker compose up` a "listo para subir CV" sin editar archivos a mano |
| **C — Onboarding (US2–US5)** | Subida, parseo, siembra, revisión, objetivos, confirmación, versionado, evals | 4 a 9 | El recorrido completo de `quickstart.md` pasa |

## Formato: `[ID] [P?] [Story] Descripción`

- **[P]**: paralelizable (archivos distintos, sin dependencias con tareas incompletas)
- **[Story]**: `[US1]`…`[US5]`. Las fases de Setup, Fundaciones y Polish **no** llevan etiqueta de historia
- Cada tarea incluye la ruta exacta de los archivos que toca

## Reglas vinculantes para todas las tareas

1. **Test-first donde sea práctico.** Las tareas marcadas «escribir antes» producen tests que **describen comportamiento que todavía no existe**.
2. **Cada tarea deja el proyecto en verde**: `ruff`, `mypy --strict` y la suite completa pasan al terminarla, y por tanto **CI nunca queda en rojo** aunque se commitee por tarea.
3. **Cómo conviven la regla 1 y la regla 2 — `xfail(strict=True)`.** Un test que aún no puede pasar nace marcado con el ID de la tarea que lo pondrá en verde:

   ```python
   @pytest.mark.xfail(strict=True, reason="verde en T015: infra/docker-compose.yml todavía no existe")
   def test_compose_publishes_only_on_loopback() -> None: ...
   ```

   La tarea que implementa el comportamiento **quita la marca en el mismo commit**. Con `strict=True` el test no puede colarse: si empieza a pasar antes de tiempo, CI falla y avisa de que la premisa cambió. Así se conserva la evidencia ejecutable de que el test fallaba antes de la implementación **sin** dejar la rama en rojo ni un solo commit.

   **Tareas que aplican esta regla**: T014, T041, T054, T057, T085, T093 y T107. Cada test lleva el ID de la tarea concreta que lo pone en verde, no el de la tarea que lo escribió.
4. **Ninguna tarea es más grande de lo que se revisa de una sentada.** Cuando un artefacto grande (la migración, los endpoints de `setup`) no cabe, se parte en tareas consecutivas sobre el mismo archivo.
5. **Idioma** (art. IX): código, identificadores, rutas y commits en inglés; mensajes de UI y de error en español.
6. **Art. V en cada tarea**: ninguna credencial en base de datos, logs, trazas, mensajes de error ni respuestas; ninguna PII del CV en logs ni en trazas.

## Decisión de configuración: un solo `.env`, en la raíz del repositorio

El `.env` vive **exclusivamente en la raíz del repositorio**. Es donde ya lo busca `scripts/verify_providers.py` (sube directorios hasta encontrarlo), donde ya está `.env.example`, y donde el usuario espera encontrarlo. **No existe `infra/.env`.** Dos ubicaciones para la misma llave serían fricción del art. VII y una fuente segura de issues del tipo "a mí no me toma la API key".

Como el comando documentado es `docker compose -f infra/docker-compose.yml up`, Compose toma `infra/` como directorio de proyecto y **buscaría ahí su `.env`**. Se resuelve con dos reglas, ambas verificadas por test:

1. `api` y `worker` declaran `env_file: [{ path: ../.env, required: false }]` — ruta relativa al archivo de Compose, es decir la raíz del repo. `required: false` hace que un clon virgen **sin `.env`** arranque igual.
2. **`infra/docker-compose.yml` no usa interpolación `${...}` en absoluto.** Es la única construcción que leería el `.env` del directorio de proyecto y que reintroduciría en silencio la segunda ubicación. Los valores de infraestructura (usuario, contraseña y nombre de la base, URLs internas) son literales en el Compose: son credenciales de desarrollo local de una base que **no se publica al host**, así que no hay nada que parametrizar.

Queda registrado en [quickstart.md](./quickstart.md) §0 y §1, y el job de instalación limpia (T036) usa exactamente el comando documentado.

---

# BLOQUE A — Fundaciones

> El repositorio no tiene código. Sin este bloque nada de la feature 001 es verificable.

## Fase 1: Setup — monorepo y tooling

**Propósito**: estructura de tres raíces del roadmap §5.1 y herramientas bloqueantes instaladas antes de la primera línea de lógica.

- [X] T001 Crear la estructura del monorepo `backend/`, `frontend/`, `infra/docker/` con `backend/app/` y `backend/tests/{unit,integration,architecture,evals}/`; añadir en la raíz `.gitattributes` con `* text=auto eol=lf`, `.python-version` (3.12) y `.nvmrc` (20 LTS), y ampliar `.gitignore` (ADR-000, research R-20)
- [X] T002 Declarar dependencias y generar el lock en `backend/pyproject.toml` + `backend/uv.lock` (`uv lock`): FastAPI, pydantic v2, pydantic-settings, SQLAlchemy 2.0, Alembic, Celery 5, redis, pypdf, python-docx, langchain-core, langchain-google-genai, structlog, pgvector; dev: pytest, pytest-asyncio, testcontainers[postgres,redis], ruff, mypy. **Sin PyJWT, argon2, boto3 ni Sentry** (plan.md "Explícitamente fuera")
- [X] T003 [P] Configurar ruff (lint + format) y `mypy --strict` en `backend/pyproject.toml`, crear `backend/app/py.typed` y activar el reporte de `# type: ignore` sin justificación
- [X] T004 [P] Añadir `.pre-commit-config.yaml` en la raíz con ruff, ruff-format, mypy, `end-of-file-fixer` y `mixed-line-ending` fijado a LF
- [X] T005 [P] Andamiar el frontend con Vite 5 + React 18 + TypeScript strict en `frontend/`: `package.json`, `package-lock.json`, `tsconfig.json`, `vite.config.ts`
- [X] T006 [P] Configurar Tailwind + shadcn/ui en `frontend/tailwind.config.ts` y `frontend/src/components/ui/`
- [X] T007 [P] Configurar Vitest + React Testing Library + MSW en `frontend/vitest.config.ts` y `frontend/tests/setup.ts`
- [X] T008 [P] Actualizar el `.env.example` **de la raíz** (ya existente) como única plantilla de configuración: dejar claro que **ninguna variable hace falta para arrancar** —las API keys las pide el wizard (FR-008)—, unificar `VOKARA_STORAGE_PATH` bajo el nombre `VOKARA_DATA_DIR` que usan plan y quickstart, y **eliminar `POSTGRES_*`, `DATABASE_URL` y `REDIS_URL`**, que pasan a ser literales del Compose por la decisión de configuración de arriba. **No se crea `infra/.env.example`**

---

## Fase 2: Fundaciones (prerrequisitos bloqueantes)

**⚠️ CRÍTICO**: ninguna tarea de US1–US5 puede empezar hasta que esta fase esté completa.

### Capas y test de arquitectura del art. II

> El test del art. II se instala **antes de que existan las capas que debe vigilar**: ese es el momento en que es trivial de pasar y en que queda puesto para siempre.

- [X] T009 Crear el esqueleto vacío de capas en `backend/app/`: `api/v1/`, `domain/`, `services/`, `adapters/{llm,storage,email,text_extraction}/`, `db/{models,repositories,migrations}/`, `workers/tasks/`, `core/`, cada uno con su `__init__.py`
- [X] T010 Test de arquitectura del art. II en `backend/tests/architecture/test_layer_dependencies.py`: falla si `api/` importa `db/`, si `adapters/` importa `services/` o `db/`, si `domain/` importa cualquier otra capa, o si `workers/tasks/` importa `db/` o `adapters/` directamente. Pasa de forma vacua sobre el esqueleto y queda instalado antes que las capas

### Configuración, logging y directorio de datos

- [X] T011 [P] `backend/app/core/config.py` — `Settings` con pydantic-settings leyendo el `.env` **de la raíz del repo**, precedencia **entorno > archivo > defaults**, `SecretStr` para toda credencial, `api_host` **con default a loopback** (lo que exige el test 2 de T014), `VOKARA_DATA_DIR`, nombres de modelo configurables y los umbrales de la feature (`MAX_UPLOAD_BYTES`, `MIN_DOC_CHARS`, `CLASSIFIER_CHARS`, `MAX_EXTRACTION_CHARS`, `MIN_SEEDED_ENTRIES`, intervalo de polling); test de precedencia y de `repr` redactado en `backend/tests/unit/test_config_precedence.py` (research R-21)
- [X] T012 [P] `backend/app/core/logging.py` — structlog con `request_id` y `parse_job_id`, más procesador que elimina claves sensibles por nombre y trunca texto libre; test en `backend/tests/unit/test_log_redaction.py` (research R-13)
- [X] T013 [P] `backend/app/core/data_dir.py` — resolución y verificación del directorio de datos local, con error accionable si no existe o no es escribible; test en `backend/tests/unit/test_data_dir.py`

### Compose local y los DOS tests de binding del ADR-008

> Los dos tests van **en el mismo grupo de tareas que el Compose**, según la "Mitigación obligatoria" del ADR-008. Se escriben primero, con `xfail(strict=True)` donde todavía no pueden pasar (regla 3).

- [X] T014 Escribir los **dos** tests de binding en `backend/tests/integration/test_local_binding.py`: (1) todo `ports:` de `infra/docker-compose.yml` y de `infra/docker-compose.override.yml` trae IP de host explícita y `ipaddress.ip_address(host_ip).is_loopback` es `True` —falla con `"8000:8000"` y con `"0.0.0.0:8000:8000"`—; (2) `socket.getaddrinfo(settings.api_host, None)` resuelve **todas** sus direcciones a loopback. El test 1 nace con `@pytest.mark.xfail(strict=True, reason="verde en T015")` porque el Compose aún no existe; el test 2 pasa desde ya contra el default de T011 y **no lleva marca** (research R-20)
- [X] T015 `infra/docker-compose.yml` con **cuatro servicios y ni uno más**: `api`, `worker`, `postgres` (`pgvector/pgvector:pg16`, tag fijo) y `redis`; `postgres` y `redis` **no se publican en absoluto**; `api` publica en `127.0.0.1:8000:8000` y fija `VOKARA_API_HOST=0.0.0.0` por el proxy de Docker; `api` y `worker` con `env_file: [{ path: ../.env, required: false }]`; **sin ninguna interpolación `${...}`** y **sin `beat`** (research R-20, R-28). Quita el `xfail` del test 1 de T014 y añade `backend/tests/integration/test_compose_env_contract.py`, que falla si aparece un `${` en el Compose o si `api`/`worker` dejan de apuntar a `../.env`
- [X] T016 `infra/docker-compose.override.yml` con hot reload de desarrollo y el servicio `web` en `127.0.0.1:5173:5173`, dentro del alcance de los tests de T014 y T015
- [X] T017 `infra/docker/backend.Dockerfile` multi-stage (builder uv → runtime slim), arrancando uvicorn directamente. **Sin migraciones todavía**: el entrypoint que las aplica llega en T024, cuando ya exista una migración que aplicar
- [X] T018 [P] `infra/docker/frontend.Dockerfile` multi-stage (build Vite → estáticos)

### Base de datos, migración inicial y arranque automático

- [X] T019 `backend/app/db/base.py` y `backend/app/db/session.py`; Alembic en `backend/alembic.ini` y `backend/app/db/migrations/env.py`, con la convención de nombres de constraint
- [X] T020 `backend/tests/conftest.py` con fixtures de testcontainers: Postgres 16 **con pgvector** y Redis reales, más fixture de sesión transaccional por test (art. VI)
- [ ] T021 Migración `0001_candidate_onboarding` (parte 1) en `backend/app/db/migrations/versions/0001_candidate_onboarding.py`: `CREATE EXTENSION IF NOT EXISTS vector`, los **12 tipos enum** de data-model.md y las **9 tablas** en orden de dependencia (`candidates` → `setup_state`, `provider_configurations`, `candidate_profiles` → `documents` → `parse_jobs` → `profile_entries` → `profile_versions` → `llm_call_logs`)
- [ ] T022 Migración `0001` (parte 2), mismo archivo: todos los `CHECK` de data-model.md, índices (incl. `ux_parse_jobs_one_active`, `ix_entries_profile_alive` y el GIN sobre `content`), FK diferida `candidate_profiles.current_version_id` con `use_alter=True`, función y trigger `trg_profile_versions_immutable`, **seed de la fila única de `candidates`**, y `downgrade` inverso exacto
- [ ] T023 Test de reversibilidad en `backend/tests/integration/test_migration_reversibility.py`: `upgrade head` → `downgrade base` → `upgrade head` sobre Postgres real, verificando que la extensión, los enums y el trigger quedan como al inicio (DoD de la constitución)
- [ ] T024 `infra/docker/entrypoint.sh` que ejecuta `alembic upgrade head` **antes** de arrancar uvicorn, cableado como `ENTRYPOINT` en `infra/docker/backend.Dockerfile` y en el servicio `api` del Compose; test en `backend/tests/integration/test_startup_migrates.py` que verifica que un arranque en limpio deja la base en `head` sin que nadie ejecute Alembic a mano (roadmap §11.1, research R-20)

### Modelos y repositorio base

- [ ] T025 [P] Modelos SQLAlchemy 2.0 tipados de primera ejecución en `backend/app/db/models/{candidate,setup_state,provider_configuration}.py`
- [ ] T026 [P] Modelos SQLAlchemy 2.0 tipados del perfil en `backend/app/db/models/{candidate_profile,profile_entry,profile_version}.py`
- [ ] T027 [P] Modelos SQLAlchemy 2.0 tipados de documentos y trazas en `backend/app/db/models/{document,parse_job,llm_call_log}.py`
- [ ] T028 Repositorio base con **`candidate_id` explícito en toda firma** en `backend/app/db/repositories/base.py`, más test en `backend/tests/integration/test_repository_scoping_base.py` que siembra **dos** `candidate_id` y verifica el filtrado (research R-11, FR-049)

### API mínima y contrato tipado extremo a extremo

- [ ] T029 `backend/app/main.py` (app FastAPI, routers, middleware de `request_id`), `backend/app/api/errors.py` (excepción de dominio → `{code, message, details}` de `contracts/errors.md`) y `backend/app/api/deps.py` con `local_candidate_id` resuelto **desde configuración local**, nunca del cliente (FR-003)
- [ ] T030 `GET /health` en `backend/app/api/v1/health.py` devolviendo `{status, database, migration_revision}` leído de la base, más test de integración en `backend/tests/integration/test_health.py`. **Este es el endpoint que viaja de DB a UI en el checkpoint A**
- [ ] T031 `backend/app/openapi_export.py` — vuelca `openapi.json` sin levantar servidor (`python -m app.openapi_export`), con test que verifica que el volcado es determinista (research R-16)
- [ ] T032 Script `generate:api` en `frontend/package.json` (openapi-typescript) y generación **commiteada** de `frontend/openapi.json` y `frontend/src/api/schema.d.ts`
- [ ] T033 `frontend/src/api/client.ts` con openapi-fetch tipado contra `schema.d.ts`, `frontend/src/routes/` con react-router v6, y una pantalla de estado que consume `GET /health` **con los tipos generados**, no escritos a mano (art. I)
- [ ] T034 [P] Test de front en `frontend/tests/health.test.tsx` (Vitest + RTL + MSW contra el esquema generado)

### CI bloqueante

- [ ] T035 `.github/workflows/ci.yml` con todos los pasos **bloqueantes**: `ruff check` + `ruff format --check` → `mypy --strict` → `pytest` unit + integración con testcontainers **incluidos los dos tests de binding** → reversibilidad de migraciones → **drift del cliente TS** (`git diff --exit-code frontend/openapi.json frontend/src/api/schema.d.ts`) → `vitest` → build del front → build de imágenes (roadmap §9, research R-20)
- [ ] T036 Job de **instalación limpia** en `.github/workflows/ci.yml`: sobre un runner virgen y **sin crear ningún `.env`**, ejecutar exactamente el comando documentado `docker compose -f infra/docker-compose.yml up -d` desde la raíz del repo y verificar que `GET /health` responde. Es la prueba de que la decisión de un solo `.env` en la raíz no rompe el arranque de un clon nuevo
- [ ] T037 [P] Job de verificación de licencias de dependencias compatibles con AGPL-3.0 en `.github/workflows/ci.yml` (ADR-010)

---

## ✅ CHECKPOINT A — Fundaciones

**No se empieza el bloque B hasta que todo esto esté en verde:**

```bash
docker compose -f infra/docker-compose.yml up -d
docker compose -f infra/docker-compose.yml ps        # api, worker, postgres, redis — cuatro
docker compose -f infra/docker-compose.yml port api 8000   # imprime 127.0.0.1:8000
curl -s localhost:8000/api/v1/health                 # {"status":"ok","database":"ok","migration_revision":"0001..."}
docker compose exec postgres psql -U vokara -c "\dx" # extensión vector presente
cd backend && uv run pytest tests/integration/test_local_binding.py tests/architecture -q
cd ../frontend && npm run build                      # la pantalla de estado compila con tipos generados
```

- [ ] Los cuatro servicios levantan con un solo `docker compose up`, **sin editar archivos a mano y sin `.env`**
- [ ] Las migraciones se aplicaron **solas** al arranque; nadie ejecutó un comando de Alembic
- [ ] `GET /health` viaja de Postgres al navegador con tipos generados desde OpenAPI, y renombrar un campo del esquema Pydantic **rompe el build de TypeScript** (prueba negativa de quickstart §2)
- [ ] Los **dos** tests de binding del ADR-008 pasan **sin marca `xfail`**; el test de arquitectura del art. II pasa
- [ ] `test_compose_env_contract.py` pasa: cero interpolaciones `${` y `env_file` apuntando a la raíz
- [ ] CI en verde con todos los pasos bloqueantes, incluida la instalación limpia

---

# BLOQUE B — Primera ejecución (US1)

## Fase 3: User Story 1 — Divulgación, proveedores y correo (Prioridad: P1) 🎯 MVP

**Objetivo**: que alguien que acaba de levantar Vokara vea qué sale de su máquina y qué no, configure de forma **independiente** su proveedor de generación y el de embeddings con preflight de capacidades resuelto, opcionalmente vincule su correo, y pueda interrumpir y retomar sin perder nada.

**Independent Test**: sobre instalación limpia, recorrer los pasos obligatorios con una llave válida y verificar que queda el acuse registrado, que ambos proveedores quedan con su preflight resuelto, que las credenciales no aparecen en la base ni en los logs, que el paso de correo puede omitirse llegando igual al onboarding, y que interrumpir y reabrir retoma en el paso pendiente.

### Art. XI y forma de los puertos (escribir el test primero)

- [ ] T038 [P] [US1] Test de arquitectura del art. XI en `backend/tests/architecture/test_provider_name_isolation.py`: falla si el nombre de un proveedor (`google`, `gemini`, `openai`, `anthropic`, `deepseek`, `kimi`, `moonshot`) aparece **fuera de `backend/app/adapters/llm/`** —en `services/`, `domain/`, `api/`, `db/`, `workers/` o en los tests de esas capas— y si `temperature`, `top_p` o `top_k` aparecen en `services/` o en la firma de un puerto (research R-22, R-25)
- [ ] T039 [US1] Puertos en `backend/app/adapters/llm/base.py`: `StructuredOutputPort.generate` y `EmbeddingsPort` (`model_name`, `dimensions`, `embed_texts`) exactamente como los fija `contracts/llm-extraction.md`, **sin parámetros de muestreo en la firma** y con `base_url` y credencial opcionales resueltos en la implementación; test de forma en `backend/tests/unit/test_port_shape.py`
- [ ] T040 [P] [US1] `backend/app/domain/capability.py` — `Capability` (`generation` | `embeddings`) y el tipo suma `PreflightOutcome` de **cuatro** variantes (`Verified`, `CapabilityUnverified`, `CredentialRejected`, `QuotaExceeded`) más `ProviderUnreachable` como caso de entorno distinto; tests unitarios de exhaustividad en `backend/tests/unit/test_preflight_outcome.py`

### Matriz de capacidades, costo estimado y esquemas de preflight

- [ ] T041 [P] [US1] Escribir antes, con `@pytest.mark.xfail(strict=True, reason="verde en T042")`: `backend/tests/unit/test_capabilities_matrix.py` — la matriz declara **cinco** filas, solo las que tienen `verified_on` no nulo entran en el catálogo ofrecible, el catálogo de generación y el de embeddings son consultas distintas, y Anthropic declara `embeddings=False` explícito (no "sin verificar")
- [ ] T042 [US1] `backend/app/adapters/llm/capabilities.py` — matriz del ADR-011 declarada como **dato inmutable** (`@dataclass(frozen=True) ProviderCapabilities` con `structured_output`, `respects_null_in_optionals`, `embeddings`, `embedding_dim`, `verified_on`), con las cinco filas y solo Google verificado el 2026-08-11. **Quita el `xfail` de T041** (research R-22, FR-009)
- [ ] T043 [P] [US1] `backend/app/adapters/llm/pricing.py` — catálogo declarativo de costo estimado **por separado** para generación y embeddings, con el supuesto de uso a la vista y qué cabe en la capa gratuita; tests en `backend/tests/unit/test_pricing_catalog.py` (FR-005, research R-27)
- [ ] T044 [P] [US1] `backend/app/adapters/llm/schemas.py` — esquema Pydantic **anidado con campos opcionales** para el preflight de generación sobre un CV deliberadamente incompleto (sin teléfono, empleo sin fechas, educación sin título) y esquema del preflight de embeddings; el criterio de aprobación es que el modelo devuelva `null` en vez de inventar (art. IV, `contracts/llm-extraction.md` §0)

### Implementación Google, factory y trazado

- [ ] T045 [US1] `backend/app/adapters/llm/google.py` — **única** implementación de v1 (langchain-google-genai) de ambos puertos con `with_structured_output`, `output_dimensionality=768` en embeddings, 3 reintentos con backoff exponencial ante red/429/salida no conforme, y **clasificación de los errores del proveedor a las cuatro variantes** más `ProviderUnreachable`. La clasificación vive aquí, nunca en el servicio (`contracts/llm-extraction.md`)
- [ ] T046 [US1] `backend/app/adapters/llm/factory.py` — resuelve el puerto desde `Settings`; **único módulo** que traduce un `ProviderId` a una implementación, y único lugar donde puede aparecer un nombre de proveedor junto a `capabilities.py`
- [ ] T047 [US1] `backend/app/adapters/llm/tracing.py` — decorador que registra en structlog y en `llm_call_logs`: `capability`, `purpose`, `model`, `prompt_version`, tokens de entrada y salida, costo estimado, latencia, `attempt` y `outcome`. **Nunca** el prompt, el texto ni la respuesta; test en `backend/tests/unit/test_tracing_has_no_content.py` (art. VIII, FR-046, research R-13)

### Estado del wizard, repositorios y servicios

- [ ] T048 [P] [US1] `backend/app/domain/setup.py` — `pending_step` **derivado por reglas** (`disclosure` → `providers` → `email` → `null`), nunca persistido como puntero; tests exhaustivos de las cuatro ramas en `backend/tests/unit/test_setup_pending_step.py` (research R-18, FR-014)
- [ ] T049 [P] [US1] `backend/app/db/repositories/{setup_state_repository,provider_configuration_repository}.py` con `candidate_id` explícito; test con **dos** `candidate_id` en `backend/tests/integration/test_setup_repository_scoping.py`
- [ ] T050 [US1] `backend/app/services/preflight_service.py` — ejecuta el preflight **al guardar cada credencial**, nunca diferido; **único intérprete** de los cuatro resultados; calcula el `credential_fingerprint` (HMAC-SHA256 truncado con clave derivada local, `hmac` de la estándar) y **invalida la fila cuando la credencial cambia** (research R-23, R-24, SC-012)
- [ ] T051 [US1] `backend/app/services/provider_catalog_service.py` — catálogo ofrecible = matriz filtrada por `verified_on is not None` y por capacidad, más el costo estimado de `pricing.py`; **el frontend no ramifica por proveedor**, renderiza lo que este servicio devuelve (art. XI)
- [ ] T052 [US1] `backend/app/services/setup_service.py` — registro del acuse de divulgación con marca de tiempo y versión, acuse específico de degradación, y regla de conclusión de la primera ejecución (acuse + generación resuelta + `email_step_status <> 'pending'`) (FR-002, FR-007.3, FR-015)
- [ ] T053 [P] [US1] `backend/app/domain/disclosure.py` — texto de divulgación **versionado** con los cuatro puntos obligatorios de FR-001 (qué se queda, la única excepción con detalle de qué y cuándo, cero telemetría, archivos sin cifrar); test de que cambiar el texto exige una versión nueva y que un acuse de versión anterior no cubre a la vigente (research R-29, FR-048)

### Vinculación de correo opcional (escribir el test de cumplimiento primero)

- [ ] T054 [P] [US1] Escribir antes: `backend/app/adapters/email/base.py` con `EmailPort` y el **test de cumplimiento** `backend/tests/unit/test_email_label_scoping.py`, que verifica que **ninguna** consulta IMAP sale sin restricción de etiqueta, marcado con `@pytest.mark.xfail(strict=True, reason="verde en T055")`. Es un test de cumplimiento del ADR-012, no de funcionalidad
- [ ] T055 [US1] `backend/app/adapters/email/gmail_imap.py` — App Password + IMAP (`imaplib` de la estándar), acotado a la etiqueta designada, limitado en 001 a **verificar que la etiqueta existe y es alcanzable**; sin lectura ni parseo de correos. **Quita el `xfail` de T054** (FR-013, fuera de alcance F1.3.2)
- [ ] T056 [US1] `backend/app/services/email_link_service.py` — vincular y omitir, con traducción de fallos a `EMAIL_APP_PASSWORD_REJECTED`, `EMAIL_LABEL_NOT_FOUND` y `EMAIL_PROVIDER_UNREACHABLE`; la App Password vive en configuración local y **nunca** toca la base (FR-013)

### Endpoints de la primera ejecución (contract tests primero)

- [ ] T057 [US1] Escribir antes, con `xfail(strict=True)` por test apuntando a su tarea (`T058` divulgación, `T059` proveedores, `T060` correo): contract tests de los nueve endpoints de `/setup/*` en `backend/tests/integration/test_setup_endpoints.py`, verificados contra `contracts/openapi.yaml` (esquemas `SetupState`, `Disclosure`, `ProviderCatalog`, `PreflightOutcome`, `ProviderConfiguration`, `EmailStep`)
- [ ] T058 [US1] `backend/app/api/v1/setup.py` — divulgación: `GET /setup/state` (con `pending_step` derivado), `GET /setup/disclosure`, `POST /setup/disclosure-acknowledgement`. Quita los `xfail` correspondientes de T057
- [ ] T059 [US1] `backend/app/api/v1/setup.py` — proveedores: `GET /setup/providers/catalog`, `GET` y `PUT /setup/providers/{capability}`, `POST /setup/providers/{capability}/degradation-acknowledgement`. Ninguna respuesta expone la credencial: el estado consultable es exactamente `configured | not_configured | rejected`. Quita los `xfail` correspondientes de T057
- [ ] T060 [US1] `backend/app/api/v1/setup.py` — correo: `GET /setup/email`, `POST /setup/email/link`, `POST /setup/email/skip`. Quita los `xfail` correspondientes de T057
- [ ] T061 [P] [US1] Los diez códigos de error de primera ejecución de `contracts/errors.md` en `backend/app/domain/errors.py` y su mapeo en `backend/app/api/errors.py`, con test de que ningún mensaje incluye la llave, un fragmento suyo ni una traza técnica

### Tests de integración de US1

- [ ] T062 [P] [US1] `backend/tests/integration/test_preflight_outcomes.py` — cada una de las cuatro variantes con su mensaje y su efecto: rechazada no avanza, cuota agotada **no** se presenta como llave inválida, sin garantía exige acuse y enumera `affected_features`, verificada registra `embedding_dim`; más `provider_unreachable` como caso distinto (SC-012, SC-016)
- [ ] T063 [P] [US1] `backend/tests/integration/test_setup_resume.py` — con acuse hecho y solo generación verificada, `pending_step` es `providers` para embeddings y no se vuelve a pedir el acuse ni la llave verificada (SC-015, US1 AC12)
- [ ] T064 [P] [US1] `backend/tests/integration/test_no_credentials_leak.py` — recorre una ejecución completa con los cuatro resultados y verifica **0 apariciones** de la llave o fragmentos en logs, trazas, mensajes de error, respuestas de la API y **cualquier** tabla de la base (SC-013)
- [ ] T065 [P] [US1] `backend/tests/integration/test_credential_rotation.py` — rotar la credencial invalida el preflight **solo de esa capacidad**; el acuse y la otra capacidad sobreviven (research R-24)

### Frontend del wizard

- [ ] T066 [US1] Regenerar `frontend/openapi.json` y `frontend/src/api/schema.d.ts`; guard de primera ejecución en `frontend/src/routes/` que impide alcanzar `/onboarding` mientras `pending_step` no sea `null` (FR-002, FR-010)
- [ ] T067 [P] [US1] `frontend/src/features/setup/disclosure/` — texto **completo en pantalla** sin ningún campo que llenar, acuse **nunca preseleccionado**, botón de continuar inhabilitado sin él; test RTL en `frontend/tests/setup/disclosure.test.tsx` (FR-001, FR-002, US1 AC1–AC2)
- [ ] T068 [P] [US1] `frontend/src/features/setup/providers/` — dos configuraciones separadas con la razón de la separación en una línea, costo estimado de cada una **antes** de pedir ninguna llave, y una sola llave cuando el proveedor es el mismo; test RTL (FR-004, FR-005, US1 AC3–AC4)
- [ ] T069 [P] [US1] `frontend/src/features/setup/providers/PreflightResult.tsx` — los cuatro resultados diferenciados y el acuse específico de degradación mostrando `affected_features`; test RTL de que sin acuse no se puede avanzar (FR-007, SC-016)
- [ ] T070 [P] [US1] `frontend/src/features/setup/email/` — omitir con **el mismo peso visual** que continuar, qué se gana y qué **no** se pierde, y la divulgación de la App Password **antes** de pedir nada; test RTL (FR-011, FR-012, US1 AC9–AC10)
- [ ] T071 [US1] `frontend/src/features/setup/hooks/` — queries y mutaciones de TanStack Query para el estado del wizard, con navegación automática al `pending_step` al reabrir (FR-014)

---

## ✅ CHECKPOINT B — Primera ejecución

**No se empieza el bloque C hasta que todo esto esté en verde:**

```bash
cd backend && uv run pytest tests/unit tests/integration tests/architecture -q
cd ../frontend && npm run test && npm run build
```

- [ ] Recorrido manual completo de **quickstart §3, pasos 1 a 15**, sobre instalación limpia: `git clone` → `docker compose up` → divulgación → proveedores → correo → **"listo para subir CV"**, sin editar ni un archivo a mano
- [ ] `POST /documents` con curl y sin acuse responde `409 DISCLOSURE_ACKNOWLEDGEMENT_REQUIRED`: el gate es **de servidor**, no del guard de la SPA
- [ ] Los cuatro resultados de preflight se distinguen; la degradación enumera funciones afectadas y exige acuse
- [ ] Omitir embeddings **no** bloquea el onboarding (FR-010); omitir correo tampoco (FR-011)
- [ ] Cerrar el navegador a mitad y volver retoma en el paso pendiente sin re-pedir acuse ni llaves
- [ ] `test_no_credentials_leak.py` en verde: cero credenciales en cualquier superficie
- [ ] El test de arquitectura del art. XI pasa; ningún nombre de proveedor fuera de `adapters/llm/`
- [ ] **Cero marcas `xfail` vivas** en la suite: `uv run pytest -q -rx` no reporta xfails pendientes del bloque B

---

# BLOQUE C — Onboarding (US2–US5)

## Fase 4: User Story 2 — Siembra del perfil maestro desde el CV (Prioridad: P1)

**Objetivo**: subir un CV maestro PDF/DOCX ≤ 10 MB, procesarlo en segundo plano con progreso visible, y presentar entradas atómicas identificables con origen `cv_seed` sobre un perfil `draft`.

**Independent Test**: subir un CV del golden set y verificar que se crean entradas atómicas identificables con origen `cv_seed`, que el perfil queda en `draft` y que el archivo original es recuperable.

### Dominio, storage y extracción de texto

- [ ] T072 [P] [US2] `backend/app/domain/enums.py` — los 12 enums como `enum.StrEnum` y test de paridad exacta con los tipos nativos de Postgres en `backend/tests/integration/test_enum_parity.py`
- [ ] T073 [P] [US2] `backend/app/domain/entries.py` — unión discriminada de `EntryContent` por `entry_type` con **todos los campos opcionales**, `PartialDate` validada por patrón `YYYY-MM`/`YYYY`; tests de los siete tipos en `backend/tests/unit/test_entry_content.py` (data-model §profile_entries, research R-05)
- [ ] T074 [P] [US2] `backend/app/domain/completeness.py` — reglas de `is_complete` y `missing_fields` **por tipo**, calculadas fuera del modelo; tests exhaustivos en `backend/tests/unit/test_completeness.py` (FR-028)
- [ ] T075 [P] [US2] `backend/app/adapters/storage/base.py` (`StoragePort`: `put`/`get`/`delete`/`exists`) y `local_fs.py` sobre filesystem local **sin cifrado**; tests en `backend/tests/unit/test_local_fs_storage.py` (ADR-007, research R-06)
- [ ] T076 [P] [US2] `backend/app/adapters/text_extraction/{base,detection}.py` — tipo real por **firma de bytes**, detección de corrupción y de PDF sin capa de texto por densidad de caracteres; tests con casos límite (PDF híbrido, CV minimalista, PNG renombrado a `.pdf`) en `backend/tests/unit/test_document_detection.py` (research R-01, R-03)
- [ ] T077 [P] [US2] `backend/app/adapters/text_extraction/{pdf,docx}.py` — pypdf en modo layout y python-docx recorriendo el body en orden; tests con documentos de dos columnas y con tablas que verifican que no se intercala contenido de bloques distintos (research R-02, US2 AC5)

### Prompts y pipeline determinista

- [ ] T078 [P] [US2] Prompts versionados `backend/app/adapters/llm/prompts/{cv_classification_v1,cv_extraction_v1}.py` con las seis cláusulas no negociables de `contracts/llm-extraction.md`; test de que ninguno nombra a un proveedor ni asume una capacidad suya (art. XI)
- [ ] T079 [US2] `backend/app/services/extraction_service.py` — orquesta texto → clasificación → extracción tipada; **el servicio interpreta `is_resume`**, el modelo no decide el flujo (art. III); tests con dobles del puerto en `backend/tests/unit/test_extraction_service.py`
- [ ] T080 [US2] `backend/app/services/seeding_service.py` — posprocesado determinista en el orden fijo de seis pasos, `DOCUMENT_TOO_SPARSE` bajo `MIN_SEEDED_ENTRIES`, inserción de **todas** las entradas en una única transacción; tests en `backend/tests/unit/test_seeding_service.py`
- [ ] T081 [US2] `backend/app/services/document_service.py` — validación síncrona (tamaño con corte del stream, firma de bytes, corrupción), **gate FR-010** contra `provider_configurations`, persistencia por `StoragePort`, creación del `parse_job` y encolado; tests en `backend/tests/unit/test_document_service.py`
- [ ] T082 [US2] `backend/app/workers/celery_app.py` (**sin beat**, research R-28) y `backend/app/workers/tasks/parse_cv.py` que **solo orquesta servicios**; ampliar `backend/tests/architecture/test_layer_dependencies.py` para que falle si la tarea contiene lógica de negocio (art. II)
- [ ] T083 [US2] Reaper de arranque en `backend/app/workers/celery_app.py` — marca como `failed` con código reintentable los `parse_jobs` que quedaron en `running` sin worker vivo; test en `backend/tests/integration/test_startup_reaper.py` (research R-07)

### Repositorios y endpoints de US2

- [ ] T084 [P] [US2] Repositorios `backend/app/db/repositories/{document_repository,parse_job_repository,candidate_profile_repository,profile_entry_repository}.py` con `candidate_id` explícito y filtrado de `deleted_at IS NULL`; tests con **dos** `candidate_id`
- [ ] T085 [US2] Escribir antes, con `xfail(strict=True)` por test apuntando a su tarea (`T086` documentos, `T087` parse-jobs): contract tests de `/documents` y `/parse-jobs` en `backend/tests/integration/test_documents_endpoints.py` contra `contracts/openapi.yaml` (`UploadAccepted`, `Document`, `ParseJob`)
- [ ] T086 [US2] `backend/app/api/v1/documents.py` — `POST /documents` con rechazo antes de leer el cuerpo completo y `GET /documents/{document_id}`; `storage_key` **nunca** se expone en ninguna respuesta ni mensaje. Quita los `xfail` correspondientes de T085
- [ ] T087 [US2] `backend/app/api/v1/parse_jobs.py` — `GET /parse-jobs/current`, `GET /parse-jobs/{job_id}` y `POST /parse-jobs/{job_id}/retry`, aceptado solo desde `failed`, creando un job nuevo sobre el mismo documento con `retry_of_job_id`, estrictamente aditivo. Quita los `xfail` correspondientes de T085 (research R-10, FR-023)
- [ ] T088 [P] [US2] Códigos de error de subida y procesamiento de `contracts/errors.md` en `backend/app/domain/errors.py`, con la columna de reintentable respetada y **sin ningún mensaje que reproduzca contenido del documento o rutas** (FR-045)
- [ ] T089 [P] [US2] `backend/tests/integration/test_rejection_paths.py` — escaneado, no-CV, corrupto, PNG renombrado, 12 MB y contenido escaso: cada uno con su código y **cero filas** en `profile_entries` (SC-008, SC-009)
- [ ] T090 [US2] `frontend/src/features/onboarding/upload/` — subida, indicador de progreso por polling de 2 s, y estados de error accionables que apuntan a la configuración cuando corresponde; tests RTL en `frontend/tests/onboarding/upload.test.tsx`

**Checkpoint US2**: un CV del golden set produce entradas `cv_seed` agrupadas por tipo sobre un perfil `draft`, y el archivo original es recuperable.

---

## Fase 5: User Story 3 — Revisión y enriquecimiento del perfil (Prioridad: P1)

**Objetivo**: ver, corregir, eliminar y agregar entradas, con el origen real registrado en cada una.

**Independent Test**: sobre un perfil sembrado, editar una entrada, borrar otra y crear una nueva; verificar que los orígenes quedan correctos y que los cambios persisten entre sesiones.

- [ ] T091 [P] [US3] `backend/app/services/entry_service.py` — alta, edición, borrado lógico y transición `cv_seed → user_edited` **solo si el contenido cambia**, preservando `user_added` sin colapsarlo; el `id` nunca se reemplaza; tests en `backend/tests/unit/test_entry_service.py` (research R-09, FR-025, FR-031)
- [ ] T092 [P] [US3] `backend/app/services/profile_service.py` — lectura del perfil con creación perezosa (`get_or_create`) y `onboarding_step` **derivado** por reglas; tests de las siete ramas en `backend/tests/unit/test_onboarding_step.py` (research R-18)
- [ ] T093 [US3] Escribir antes, con `xfail(strict=True)` por test apuntando a su tarea (`T094` entradas, `T095` perfil): contract tests de `/profile/entries` y `GET /profile` en `backend/tests/integration/test_entries_endpoints.py` (`ProfileEntry`, `EntryCreate`, `EntryPatch`, `Profile`)
- [ ] T094 [US3] `backend/app/api/v1/profile_entries.py` — `GET`/`POST /profile/entries` y `GET`/`PATCH`/`DELETE /profile/entries/{entry_id}`; un recurso de otro `candidate_id` responde **404, nunca 403**. Quita los `xfail` correspondientes de T093 (FR-049)
- [ ] T095 [US3] `GET /profile` en `backend/app/api/v1/profile.py`, devolviendo estado, objetivos y `onboarding_step`. Quita los `xfail` correspondientes de T093
- [ ] T096 [P] [US3] `backend/tests/integration/test_entry_identity.py` — el `id` de una entrada sobrevive a la edición y una entrada borrada no reaparece en revisiones posteriores (SC-002, FR-032)
- [ ] T097 [US3] `frontend/src/features/onboarding/review/` — entradas agrupadas por tipo con su origen y marca de incompleta indicando qué falta, sin bloquear la revisión de las demás; CRUD completo; tests RTL (FR-030, US3 AC4)
- [ ] T098 [US3] Captura manual guiada (FR-022) en `frontend/src/features/onboarding/review/`, **reutilizando el mismo formulario de entradas**, alcanzable desde `PDF_WITHOUT_TEXT_LAYER` y `DOCUMENT_TOO_SPARSE`; test RTL de que las entradas nacen `user_added` (SC-010)

**Checkpoint US3**: editar, borrar y crear entradas registra los tres orígenes correctamente y sobrevive a una recarga.

---

## Fase 6: User Story 4 — Cuestionario de objetivos (Prioridad: P1)

**Objetivo**: capturar puesto objetivo, expectativa salarial con moneda, ubicaciones y modalidad remota, industrias y deal-breakers como parte del perfil maestro.

**Independent Test**: completar el cuestionario sobre un perfil `draft` y verificar que las respuestas quedan asociadas, son editables y viajan en la versión que se genera al confirmar.

- [ ] T099 [P] [US4] `backend/app/domain/objectives.py` — modelo del cuestionario y validación de coherencia del rango salarial y de moneda del conjunto configurado, con mensajes en español; tests en `backend/tests/unit/test_objectives_validation.py` (FR-036, research R-17)
- [ ] T100 [US4] `backend/app/services/objectives_service.py` y `PATCH /profile/objectives` en `backend/app/api/v1/profile.py`, con contract test contra `ObjectivesPatch` y verificación de que los códigos `SALARY_RANGE_INVALID`, `SALARY_CURRENCY_REQUIRED` y `UNSUPPORTED_CURRENCY` salen del catálogo
- [ ] T101 [US4] `frontend/src/features/onboarding/objectives/` con react-hook-form + zod, editable en cualquier momento antes de confirmar; tests RTL en `frontend/tests/onboarding/objectives.test.tsx` (FR-037)

**Checkpoint US4**: el cuestionario guarda, valida el rango salarial en español y es editable.

---

## Fase 7: User Story 5 — Confirmación explícita y versionado (Prioridad: P1)

**Objetivo**: que `complete` solo se alcance por una acción explícita del candidato, que cada confirmación materialice una versión inmutable y que los cambios sin confirmar sean visibles y no entren en circulación.

**Independent Test**: intentar alcanzar `complete` por cualquier vía sin la acción de confirmación y verificar que es imposible; luego confirmar y verificar que se crea una versión consultable.

- [ ] T102 [P] [US5] `backend/app/domain/canonical.py` — serialización canónica y `content_hash` SHA-256 estable ante reordenamientos irrelevantes; tests en `backend/tests/unit/test_canonical_hash.py` (research R-08)
- [ ] T103 [P] [US5] `backend/app/domain/confirmation.py` — elegibilidad y lista de `blockers` (`NO_ENTRIES`, `MISSING_TARGET_ROLE`, `MISSING_LOCATION_OR_REMOTE`, `MISSING_SALARY_EXPECTATION`); tests en `backend/tests/unit/test_confirmation_rules.py` (FR-039)
- [ ] T104 [P] [US5] `backend/app/domain/diff.py` — diff del trabajo en curso contra la versión vigente, derivado de hashes y **nunca de una bandera persistida**; tests en `backend/tests/unit/test_pending_diff.py` (FR-044, research R-08)
- [ ] T105 [US5] `backend/app/services/version_service.py` — snapshot JSONB con las entradas **completas** (no referencias), `version_number` asignado con `SELECT ... FOR UPDATE` en la misma transacción, historial y `get_current()`; tests en `backend/tests/unit/test_version_service.py`
- [ ] T106 [US5] `backend/app/services/confirmation_service.py` — **único escritor de `state`** (art. X), que confirma y versiona en una sola transacción; tests en `backend/tests/unit/test_confirmation_service.py`
- [ ] T107 [US5] Escribir antes, con `@pytest.mark.xfail(strict=True, reason="verde en T108")`: contract tests de `POST /profile/confirm`, `GET /profile/pending-changes`, `GET /profile/versions` y `GET /profile/versions/{version_id}` en `backend/tests/integration/test_versions_endpoints.py`
- [ ] T108 [US5] `POST /profile/confirm` y `GET /profile/pending-changes` en `backend/app/api/v1/profile.py`, más `backend/app/api/v1/profile_versions.py` con el historial y el detalle de versión. **Quita los `xfail` de T107**
- [ ] T109 [US5] `backend/tests/integration/test_confirmation_gate.py` — intentar alcanzar `complete` por reintento de parseo, edición masiva, `PATCH` directo de objetivos y escritura directa de repositorio; **todos deben fallar** (SC-001, art. X)
- [ ] T110 [P] [US5] `backend/tests/integration/test_version_immutability.py` — trigger activo ante `UPDATE` y `DELETE`, dos confirmaciones producen versiones 1 y 2 con contenido íntegro, y la versión 1 no refleja cambios posteriores (SC-005, FR-041, FR-043)
- [ ] T111 [US5] `frontend/src/features/onboarding/confirm/` — resumen final, bloqueadores con la lista exacta de lo que falta, aviso visible de cambios sin confirmar con su detalle, e historial de versiones; tests RTL (FR-039, FR-044, US5 AC7)

**Checkpoint US5**: confirmar crea versión, editar después mantiene `complete` con aviso de cambios pendientes, y ningún camino alterno alcanza `complete`.

---

## Fase 8: Evals contra golden set

> Bloqueantes en CI (art. VI, SC-003). Sin ellas, cambiar un prompt es un acto de fe.

- [ ] T112 [P] [US2] Golden set de **12 casos** en `backend/tests/evals/golden_set/` (6 CVs sintéticos en español —uno a dos columnas, uno con tablas—, 2 en inglés, 1 mixto, 1 PDF escaneado, 1 factura como negativo, 1 CV escaso) con su `<caso>.expected.json`, un `README.md` de procedencia y `CODEOWNERS` sobre el directorio. **Material sintético o del propio equipo, nunca de usuarios reales** (FR-047, FR-048, research R-15)
- [ ] T113 [US2] `backend/tests/evals/metrics.py` — tasa de error por campo, **invención** (valor no presente en el texto fuente, comprobada vía `source_excerpt`), precisión del clasificador de no-CV, detección de PDF sin capa de texto, corrección de `language` y casos de exageración
- [ ] T114 [US2] `backend/tests/evals/test_extraction_evals.py` con los seis umbrales bloqueantes de `contracts/llm-extraction.md`, **parametrizado por proveedor desde configuración** y registrando modelo y versión de prompt en el resultado de cada corrida (art. XI, ADR-003)
- [ ] T115 [US2] Medición del presupuesto de latencia por etapa dentro de las evals, contra la tabla de research R-14 (objetivo p95 ≈ 45 s, bloqueante en 60 s) para SC-004
- [ ] T116 Integrar las evals en `.github/workflows/ci.yml` con filtro por rutas: golden set **completo** en todo PR que toque `adapters/llm/`, `services/extraction_service.py`, `domain/completeness.py` o el propio golden set; subconjunto de humo de 3 casos en el resto. **Ambos bloqueantes**

---

## Fase 9: Polish y transversales

- [ ] T117 [P] `backend/tests/integration/test_candidate_scoping.py` — siembra datos de **dos** `candidate_id` y verifica que **todos** los repositorios filtran, y que la API responde 404 y nunca 403 ante un recurso ajeno (FR-049)
- [ ] T118 [P] `backend/tests/integration/test_no_pii_in_logs.py` — procesa un CV con nombre y teléfono sembrados y verifica que ninguna cadena aparece en los logs capturados ni en `llm_call_logs` (FR-045, FR-046)
- [ ] T119 [P] `backend/tests/integration/test_storage_unavailable.py` — con el directorio de datos movido, el perfil sigue intacto y el mensaje `STORAGE_UNAVAILABLE` **no incluye la ruta** (ADR-007, edge case)
- [ ] T120 [P] Divulgación del art. V en `README.md` —qué se queda en la máquina, la única excepción, cero telemetría, archivos sin cifrar— más la instalación en un solo comando y la ubicación única del `.env` en la raíz (art. V, roadmap §11.1)
- [ ] T121 [P] Verificar cobertura ≥ 80% en `backend/app/services` y `backend/app/domain` y añadir el umbral como paso bloqueante en `.github/workflows/ci.yml` (art. VI)
- [ ] T122 Regenerar y commitear `frontend/openapi.json` y `frontend/src/api/schema.d.ts`; actualizar el `.env.example` **de la raíz** con toda variable añadida y confirmar drift cero
- [ ] T123 Ejecutar el recorrido completo de `specs/001-candidate-onboarding/quickstart.md` §§1–7 sobre una instalación limpia y cerrar la checklist de §8 antes de abrir el PR

---

## ✅ CHECKPOINT C — Onboarding

- [ ] Recorrido manual completo de **quickstart §4** (subida → revisión → objetivos → confirmación → versión 2)
- [ ] Todos los recorridos de rechazo de **quickstart §5** con su código y cero entradas creadas
- [ ] Captura manual guiada llega a `complete` sin haber sembrado desde archivo (SC-010)
- [ ] Reintento tras fallo conserva las entradas manuales y no duplica las sembradas (FR-023)
- [ ] Suite completa de **quickstart §6** en verde, con todos sus umbrales
- [ ] **Cero marcas `xfail` vivas** en toda la suite: `uv run pytest -q -rx` no reporta ninguna
- [ ] Todos los criterios de **quickstart §7** verificados (los verificables en CI; SC-006, SC-007 y SC-014 quedan para la prueba de instalación asistida de la Fase 5 del roadmap)
- [ ] Checklist de **quickstart §8** completa

---

## Dependencias y orden de ejecución

### Dependencias entre bloques

- **Bloque A** no depende de nada; empieza de inmediato
- **Bloque B** requiere **CHECKPOINT A en verde**
- **Bloque C** requiere **CHECKPOINT B en verde**

### Dependencias entre fases

- Fase 1 (Setup) → Fase 2 (Fundaciones) → Fase 3 (US1) → Fases 4–7 (US2–US5) → Fase 8 (Evals) → Fase 9 (Polish)
- Dentro del bloque C, US2 → US3 → US4 → US5 en orden: la revisión necesita entradas sembradas, la confirmación necesita objetivos. Las cuatro son P1 y ninguna es opcional para el checkpoint C

### Dependencias internas destacadas

**La numeración es ejecutable en orden estricto: ninguna tarea depende de otra con ID mayor.**

| Tarea | Depende de | Por qué |
|---|---|---|
| T015, T016 | T011, T014 | El default loopback de `api_host` y los tests de binding se escriben antes |
| T024 | T017, T021, T022, T023 | El entrypoint aplica `alembic upgrade head`: necesita Dockerfile **y** una migración ya probada |
| T030 | T019–T022, T029 | `GET /health` lee la revisión de Alembic de la base |
| T033 | T031, T032 | La UI consume tipos generados desde el volcado de OpenAPI |
| T036 | T015, T024, T030 | La instalación limpia verifica Compose + migración automática + `/health` |
| T042 | T041 | Matriz test-first (`xfail` → verde) |
| T045, T046 | T039, T040, T042 | La implementación necesita puertos, tipo suma y matriz |
| T050 | T045, T049 | El preflight necesita el adapter y el repositorio de configuraciones |
| T055 | T054 | El test de acotamiento por etiqueta se escribe antes que el adapter |
| T058–T060 | T057 | Contract tests primero |
| T079, T080 | T073, T074, T078 | El pipeline necesita dominio, reglas de completitud y prompts |
| T081 | T050, T075, T076, T077 | Validación, storage y el gate FR-010 |
| T086, T087 | T085 | Contract tests primero |
| T094, T095 | T093 | Contract tests primero |
| T106 | T102, T103, T105 | Confirmar exige hash canónico, reglas y servicio de versiones |
| T108 | T107 | Contract tests primero |
| T114 | T112, T113, T045, T079 | Las evals corren contra el pipeline real y el golden set |

### Oportunidades de paralelización

**Bloque A** — T003 a T008 en paralelo tras T002. T011, T012 y T013 en paralelo. T025, T026 y T027 en paralelo tras T022. T018, T034 y T037 en paralelo.

**Bloque B** — T038, T040, T041, T043, T044 en paralelo al inicio de la fase. T048, T049, T053 y T054 en paralelo. T062 a T065 en paralelo. T067 a T070 en paralelo tras T066.

**Bloque C** — T072 a T077 en paralelo al inicio de US2. T091, T092 y T096 en paralelo. T102, T103 y T104 en paralelo. T117 a T121 en paralelo en Polish.

```bash
# Ejemplo: arranque en paralelo de la fase 4 (US2)
Task: "T072 domain/enums.py + test de paridad con Postgres"
Task: "T073 domain/entries.py — unión discriminada por tipo"
Task: "T074 domain/completeness.py — reglas por tipo"
Task: "T075 adapters/storage — StoragePort + local_fs"
Task: "T076 adapters/text_extraction/detection.py — firma, corrupción, escaneado"
Task: "T077 adapters/text_extraction/{pdf,docx}.py — dos columnas y tablas"
```

---

## Estrategia de implementación

### MVP: Bloque A + Bloque B

Las fundaciones más la primera ejecución ya son un incremento demostrable: alguien clona el repo, levanta el Compose, lee la divulgación, configura sus dos proveedores con preflight resuelto y llega a "listo para subir CV". Es el punto donde se mide el riesgo nº 1 del modelo local-first (la fricción de instalación, art. VII / SC-014) y donde se valida SC-014 con personas reales antes de construir el onboarding encima.

### Entrega incremental

1. Bloque A → checkpoint A → el repositorio es verificable y CI protege todo lo que venga después
2. Bloque B → checkpoint B → **MVP demostrable**, prueba de instalación asistida posible
3. US2 → siembra funcional contra el golden set
4. US3 → gate de calidad del perfil
5. US4 → objetivos
6. US5 → confirmación y versionado; el producto queda habilitado
7. Evals y Polish → checkpoint C y PR

### Notas

- `[P]` = archivos distintos, sin dependencias pendientes
- Todo test «escribir antes» nace con `xfail(strict=True)` y el ID de la tarea que lo pondrá en verde; esa tarea quita la marca en el mismo commit (regla 3)
- Un `xfail` que sobrevive a su tarea es un bug de proceso: los checkpoints B y C lo verifican con `pytest -rx`
- Commit por tarea o por grupo lógico, en inglés, en la rama `001-candidate-onboarding`, nunca en `main`
- Cualquier ambigüedad, spec faltante o conflicto con la constitución: **detenerse y preguntar** (CLAUDE.md regla 5)
