# Implementation Plan: Onboarding del candidato — del CV maestro al perfil maestro confirmado

**Branch**: `001-candidate-onboarding` | **Date**: 2026-08-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-candidate-onboarding/spec.md`

**Referencias normativas**: constitución v1.1.1 · `docs/product/roadmap.md` §4, §5, §6, §7 · ADR-001 (auth), ADR-002 (VPS + Compose), ADR-003 (Gemini + embeddings), ADR-005 (perfil maestro), ADR-006 (SPA React/Vite)

---

## Summary

Esta feature entrega el camino feliz completo del onboarding: el candidato autenticado acepta el aviso de privacidad, sube su CV maestro (PDF/DOCX ≤ 10 MB), el sistema lo procesa en segundo plano y siembra el perfil maestro con entradas atómicas identificables marcadas `cv_seed`; el candidato revisa, corrige, borra y agrega entradas (`user_edited` / `user_added`), responde el cuestionario de objetivos y **confirma explícitamente**, momento en que el perfil pasa a `complete` y se materializa una versión inmutable.

**Enfoque técnico.** Pipeline determinista en cuatro pasos (validación → extracción de texto → clasificación → extracción estructurada), ejecutado por un worker Celery que **solo orquesta servicios** (art. II). El LLM participa exclusivamente como componente con entrada/salida tipada vía `with_structured_output` + Pydantic v2 (art. III); todo lo que puede decidirse por reglas —completitud de entradas, detección de PDF sin capa de texto, validación del rango salarial, elegibilidad de confirmación, diff de cambios sin confirmar— se decide por reglas y se prueba con unit tests. El estado del procesamiento se expone por polling sobre un recurso `parse_job`. El versionado es una instantánea JSONB inmutable con hash de contenido canónico; el indicador "tienes cambios sin confirmar" se **deriva** comparando el hash del trabajo en curso contra el de la versión vigente, no se mantiene como bandera manual.

Como el repositorio todavía no tiene código, este plan incluye también las fundaciones mínimas de la Fase 1 del roadmap (monorepo, tooling, CI bloqueante, Compose, generación del cliente TS desde OpenAPI) y la autenticación del ADR-001, sin la cual no existe "candidato autenticado". Ver [Alcance y precondiciones](#alcance-y-precondiciones) para el detalle y las dos decisiones que requieren visto bueno antes de implementar.

---

## Alcance y precondiciones

### Dentro del alcance de este plan

| Bloque | Justificación |
|---|---|
| Fundaciones del monorepo (roadmap §5.1), tooling (ruff, mypy `--strict`, pre-commit), CI bloqueante, Compose dev | El repo no tiene código. Sin esto nada de 001 es verificable. Roadmap Fase 1. |
| Auth JWT propio del ADR-001: registro, login, refresh con rotación y detección de reuso, logout, `me`, revocación de `jti` en Redis, rate limiting | La spec 001 **asume** candidato autenticado, pero ADR-001 asigna explícitamente su costo (~4–6 días) "repartidos en la feature 001". El input del plan lo confirma. Se implementa aquí, sin FRs propios de 001. |
| FR-001 … FR-034 completos | Es el cuerpo de la feature. |
| Adapter LLM (`adapters/llm/`) con puertos de **structured output** y **embeddings**, implementación Gemini, trazado de costo/latencia/versión de prompt | ADR-003 + art. II + art. VIII. |
| Evals de extracción contra golden set, bloqueantes en CI | Art. VI + SC-003. |

### Fuera del alcance (delegado y por qué)

| Excluido | Destino |
|---|---|
| Retención, purga, borrado del archivo, descarga, reprocesamiento, eliminación de cuenta | Feature **006**. El modelo de datos deja los ganchos preparados (ver [data-model.md](./data-model.md) §"Compatibilidad con 006 y 007"). |
| Re-subida de CV con perfil existente, fusión, criterio de equivalencia, versión de origen `cv_merge` | Feature **007**. El enum `version_origin` nace con `confirmation` y con espacio explícito para `cv_merge`. |
| Verificación de correo y reset de contraseña (ADR-001) | Requieren el adapter de correo, y la spec 001 establece que esta feature **no envía ningún correo**. Se difieren a la feature de cuenta que introduzca el adapter de correo. Login y registro funcionan sin verificación previa en v1 de desarrollo. |
| Normalización de skills contra taxonomía (ADR-004), matching, generación de materiales, tracker | Features posteriores del roadmap. Las skills se capturan como entradas con su texto original (supuesto de la spec). |
| Cálculo y persistencia de embeddings | El **puerto** y la implementación Gemini se entregan aquí (input del plan + ADR-003); no se persiste ningún vector porque en 001 no hay consumidor. La regla de ADR-003 (`embedding_model` + `embedding_dim` junto a cada vector) queda registrada como convención vinculante en `data-model.md` y la extensión `pgvector` se habilita en la primera migración. Ver [research.md](./research.md) R-12. |
| Playwright e2e | El input del plan fija Vitest + RTL para el front. E2E se incorpora cuando exista staging (roadmap Fase 1/5). |

### Decisiones abiertas que requieren visto bueno antes de `/speckit-implement`

1. **ADR-007 — Almacenamiento de objetos y cifrado en reposo (BLOQUEANTE).** Ningún ADR vigente decide dónde viven los binarios de CV ni cómo se cifran. FR-003 y el art. V lo exigen. Recomendación desarrollada en [research.md](./research.md) R-06: adapter `StoragePort` sobre S3 (boto3) + **cifrado de sobre AES-256-GCM en la aplicación**, con MinIO como backend en dev y en el VPS. Es una decisión de arquitectura: la DoD de la constitución exige entrada en `docs/adr/`. **No implementar el adapter de storage antes de ratificar el ADR-007.**
2. **Trazas LLM sin Langfuse/LangSmith en 001.** El roadmap §9 los nombra; el art. V prohíbe PII en trazas de LLM y el prompt de extracción es PII íntegra. Recomendación (research R-13): trazado propio **solo de metadatos** (modelo, versión de prompt, tokens, costo, latencia, `parse_job_id`) a structlog + tabla `llm_call_logs`; la integración con un observador externo se decide cuando exista un flujo LLM sin PII. No contradice ningún ADR, pero conviene registrarlo como nota en el ADR-003 al cerrar la feature.

---

## Technical Context

**Language/Version**: Python 3.12 (backend, workers) · TypeScript 5.x sobre Node 20 LTS (frontend)

**Primary Dependencies**:
*Backend* — FastAPI, Pydantic v2, SQLAlchemy 2.0 (tipado, estilo declarativo `Mapped[]`), Alembic, Celery 5 + Redis, pypdf, python-docx, LangChain (`langchain-core` + `langchain-google-genai`), argon2-cffi, PyJWT, boto3, structlog, pgvector (extensión + `pgvector` python para el puerto de embeddings).
*Frontend* — React 18, Vite 5, TanStack Query v5, react-hook-form + zod, Tailwind + shadcn/ui, react-router v6, `openapi-typescript` + `openapi-fetch`.

**Storage**: Postgres 16 + pgvector (única base de datos, art. VII) · Redis (broker Celery, revocación de `jti`, rate limiting) · Object storage S3-compatible para binarios de CV, cifrados (pendiente ADR-007)

**Testing**: pytest + pytest-asyncio + testcontainers (Postgres 16 real y Redis real) · evals de extracción contra golden set en `backend/tests/evals/` · Vitest + React Testing Library + MSW en frontend · cobertura ≥ 80% en `services/` y `domain/`

**Target Platform**: Linux (contenedores). Dev: Docker Compose local. Prod/staging: Docker Compose sobre VPS Hostinger KVM 2 (ADR-002). Frontend: estáticos servidos por el reverse proxy.

**Project Type**: Web application — monorepo `backend/` + `frontend/` + `infra/` (roadmap §5.1)

**Performance Goals**:
- SC-004: p95 < 60 s desde que termina la subida hasta que hay entradas revisables. Presupuesto por etapa en [research.md](./research.md) R-14 (objetivo p95 ≈ 50 s, 10 s de margen).
- API síncrona: p95 < 300 ms en endpoints de perfil y entradas (sin llamadas a LLM).
- Subida de 10 MB aceptada y encolada en < 3 s.

**Constraints**:
- `mypy --strict` sin `# type: ignore` no justificado; ruff lint + format; ambos bloqueantes en CI.
- PII (nombre, contacto, historial, texto del CV) **nunca** en logs, trazas ni mensajes de error (FR-031).
- Solo **un** `parse_job` activo por candidato (garantizado por índice único parcial, no por lógica de aplicación).
- Sin OCR (FR-006). Sin envío de correo en toda la feature.
- Migraciones Alembic reversibles (`downgrade` real y probado).
- El cliente TS del frontend se genera desde OpenAPI; CI falla si está desincronizado (art. I).

**Scale/Scope**: decenas de usuarios en v1 · ~1 perfil por candidato · ~20–120 entradas por perfil · CVs de 1–10 páginas · 4 pantallas de onboarding (subida, revisión, objetivos, confirmación) + auth.

---

## Constitution Check

*GATE: debe pasar antes de la Fase 0 y re-evaluarse tras la Fase 1.*

### Evaluación inicial (pre-diseño) — **PASA**

| Artículo | Cómo lo satisface este plan | Estado |
|---|---|---|
| **I. Tipado estricto E2E** | `mypy --strict` bloqueante; Pydantic v2 en request/response, salida del LLM (`with_structured_output`), payload de tareas Celery y retorno de adapters; cliente TS generado con `openapi-typescript` en el build y verificado en CI con `git diff --exit-code`. Prohibido tipear la API a mano. | ✅ |
| **II. Capas unidireccionales** | `api/` solo valida, autoriza y delega. `workers/tasks/` solo orquesta servicios. Todo lo externo (LLM, embeddings, storage, extracción de texto) detrás de puerto en `adapters/`. El puerto de embeddings existe desde el día 1; su regla de persistencia (`embedding_model`, `embedding_dim`) queda escrita. Test de arquitectura que falla si `api/` importa `db/` o si `adapters/` importa `services/`. | ✅ |
| **III. Determinismo primero** | Pipeline de 4 pasos fijos, sin agente. El LLM aparece dos veces, ambas con esquema Pydantic de salida: clasificar documento y extraer entradas. Completitud, detección de PDF sin capa de texto, validación de salario, elegibilidad de confirmación y diff de cambios pendientes son **reglas**, no juicio del modelo. `temperature=0` y modelo pineado. | ✅ |
| **IV. Veracidad** | El perfil maestro es la entidad estructurada fuente de verdad; el archivo es respaldo (FR-003, ADR-005). Entradas atómicas con `id` estable (FR-010) que sostendrán el `source_id` de features posteriores. El esquema del LLM declara opcionales todos los campos no garantizados y el prompt exige `null` ante ausencia; las evals incluyen casos de invención y de exageración como fallo. Cada versión registra su origen. | ✅ |
| **V. Privacidad** | Consentimiento explícito bloqueante antes de la primera subida (FR-030). TLS en tránsito (proxy) y cifrado en reposo del binario (pendiente ADR-007). Redactor de PII en structlog + trazas LLM solo de metadatos. Acceso al perfil, entradas, versiones y documentos restringido al propietario, con el `candidate_id` tomado **siempre** del token, nunca del cliente. Golden set sin material de usuarios reales (FR-032/FR-033). | ✅ |
| **VI. Calidad verificable** | pytest unit + integración contra Postgres real (testcontainers). Evals de extracción con golden set bloqueantes en CI. Cobertura ≥ 80% en `services/` y `domain/`. Tests de seguridad específicos de ADR-001 (rotación, reuso, expiración, revocación). | ✅ |
| **VII. Simplicidad (YAGNI)** | Una sola base (Postgres + pgvector). Sin microservicios, sin Kubernetes, sin vector-store aparte. Polling en vez de SSE/WebSocket para el progreso. Rate limiter propio de ~40 líneas sobre Redis en vez de una dependencia nueva. Cada dependencia nueva justificada en [Complexity Tracking](#complexity-tracking). Embeddings: puerto sí, tabla de vectores no (sin consumidor en 001). | ✅ |
| **VIII. Observabilidad** | Toda llamada LLM traza costo, latencia y versión de prompt (metadatos, sin PII). structlog con `request_id` y `parse_job_id`. Sentry en back y front. | ✅ |
| **IX. Idioma** | UI, mensajes de error y estos documentos en español. Código, identificadores, ramas y commits en inglés. Los valores de enum (`cv_seed`, `draft`, `complete`) son identificadores → inglés. | ✅ |
| **X. Control humano** | `POST /profile/confirm` es el **único** camino a `complete`. No hay setter administrativo, ni transición desde el worker, ni efecto colateral de reintento o edición masiva. Constraint de base de datos: una fila en `profile_versions` de origen `confirmation` es condición necesaria para que `state='complete'`. Test dedicado que intenta alcanzar `complete` por todas las vías conocidas. | ✅ |

**Restricciones adicionales**: stack idéntico al fijado por roadmap §5; ADR-001, 002, 003, 005 y 006 respetados sin desviación; ADR-004 no aplica (normalización de skills fuera de alcance). Ninguna decisión de este plan contradice un ADR vigente. La única decisión nueva de arquitectura (object storage + cifrado) se canaliza como **ADR-007**, no como excepción.

### Re-evaluación post-diseño (Fase 1) — **PASA**

Revisados `data-model.md`, `contracts/openapi.yaml`, `contracts/llm-extraction.md` y `quickstart.md`:

- **Art. I** — El diseño de `profile_entries` usa `content JSONB` con discriminador `entry_type`. Se verificó que esto **no** debilita el tipado: la unión discriminada de Pydantic v2 se serializa en OpenAPI como `oneOf` + `discriminator`, y `openapi-typescript` la traduce a una unión discriminada de TypeScript. El estrechamiento de tipo en el front sigue siendo del compilador, no del programador. ✅
- **Art. III** — Ningún paso del pipeline delega una decisión de flujo al modelo. Confirmado en `contracts/llm-extraction.md`: la salida del clasificador es un booleano tipado que el servicio interpreta, y la del extractor es una lista de entradas que un paso de reglas evalúa. ✅
- **Art. X** — Modelado con doble candado: transición de estado solo en `ConfirmationService`, y constraint `CHECK (state <> 'complete' OR current_version_id IS NOT NULL)` + trigger que impide `UPDATE`/`DELETE` sobre `profile_versions`. ✅
- **Art. VII** — Se revisó cada tabla nueva contra el alcance: 8 tablas, ninguna especulativa. Se descartaron durante el diseño una tabla `onboarding_steps` (el paso se deriva del estado), una tabla `profile_entry_embeddings` (sin consumidor) y una bandera persistida `has_unconfirmed_changes` (se deriva del hash). ✅
- **Art. V** — El contrato de errores define mensajes en español sin eco del contenido del documento; ningún esquema de respuesta expone rutas de storage crudas. ✅

Sin violaciones que justificar más allá de lo registrado en [Complexity Tracking](#complexity-tracking).

---

## Project Structure

### Documentation (this feature)

```text
specs/001-candidate-onboarding/
├── plan.md                     # Este archivo
├── research.md                 # Fase 0: decisiones técnicas con alternativas
├── data-model.md               # Fase 1: entidades, constraints, migración, ganchos 006/007
├── quickstart.md               # Fase 1: guía de validación ejecutable extremo a extremo
├── contracts/
│   ├── openapi.yaml            # Contrato HTTP de la feature (fuente de diseño)
│   ├── llm-extraction.md       # Contrato de salida estructurada del LLM y versionado de prompts
│   └── errors.md               # Catálogo de códigos de error y mensajes en español
├── checklists/
│   └── requirements.md         # Ya existente
└── tasks.md                    # Fase 2 (/speckit-tasks — NO lo crea este comando)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── main.py                      # app FastAPI, routers, middlewares, handlers de error
│   ├── openapi_export.py            # vuelca openapi.json sin levantar servidor (build del front)
│   ├── api/
│   │   ├── deps.py                  # current_candidate, sesión DB, límites
│   │   ├── errors.py                # excepciones de dominio → respuesta {code,message,details}
│   │   └── v1/
│   │       ├── auth.py              # register, login, refresh, logout, me
│   │       ├── consents.py          # aviso de privacidad vigente + aceptación
│   │       ├── documents.py         # subida, consulta de documento
│   │       ├── parse_jobs.py        # estado, reintento
│   │       ├── profile.py           # perfil, objetivos, confirmación, pending-changes
│   │       ├── profile_entries.py   # CRUD de entradas
│   │       └── profile_versions.py  # historial y detalle de versiones
│   ├── domain/                      # Pydantic v2 + enums + reglas puras (sin I/O)
│   │   ├── enums.py                 # ProfileState, EntryType, EntryOrigin, VersionOrigin, ...
│   │   ├── entries.py               # unión discriminada del contenido por tipo de entrada
│   │   ├── completeness.py          # reglas de completitud por tipo (FR-013)
│   │   ├── objectives.py            # cuestionario + validación de rango salarial (FR-021)
│   │   ├── confirmation.py          # reglas de elegibilidad de confirmación (FR-024)
│   │   ├── diff.py                  # diff trabajo en curso vs versión vigente (FR-029)
│   │   ├── canonical.py             # serialización canónica + content_hash
│   │   └── errors.py                # jerarquía de errores de dominio
│   ├── services/
│   │   ├── auth_service.py          # ADR-001: hash, tokens, rotación, detección de reuso
│   │   ├── consent_service.py
│   │   ├── document_service.py      # validación, cifrado, persistencia, encolado
│   │   ├── extraction_service.py    # orquesta texto → clasificación → extracción tipada
│   │   ├── seeding_service.py       # entradas del LLM → profile_entries (transacción única)
│   │   ├── profile_service.py       # lectura del perfil, paso derivado del onboarding
│   │   ├── entry_service.py         # alta/edición/borrado y transiciones de origen
│   │   ├── objectives_service.py
│   │   ├── confirmation_service.py  # ÚNICO camino a `complete` (art. X)
│   │   └── version_service.py       # snapshot inmutable, historial, diff pendiente
│   ├── adapters/
│   │   ├── llm/
│   │   │   ├── base.py              # StructuredOutputPort, EmbeddingsPort
│   │   │   ├── gemini.py            # implementación langchain-google-genai
│   │   │   ├── schemas.py           # esquemas Pydantic de salida del modelo
│   │   │   ├── prompts/             # prompts versionados (CV_EXTRACTION_V1, ...)
│   │   │   └── tracing.py           # costo, latencia, versión de prompt (sin PII)
│   │   ├── storage/
│   │   │   ├── base.py              # StoragePort (put/get/delete)
│   │   │   ├── s3.py                # boto3, S3-compatible
│   │   │   └── crypto.py            # cifrado de sobre AES-256-GCM (pendiente ADR-007)
│   │   └── text_extraction/
│   │       ├── base.py              # TextExtractionPort
│   │       ├── pdf.py               # pypdf, modo layout
│   │       ├── docx.py              # python-docx recorriendo el body en orden
│   │       └── detection.py         # tipo real por firma, corrupción, PDF sin capa de texto
│   ├── db/
│   │   ├── base.py, session.py
│   │   ├── models/                  # SQLAlchemy 2.0 tipado (Mapped[])
│   │   ├── repositories/            # acceso a datos SIEMPRE acotado por candidate_id
│   │   └── migrations/              # Alembic
│   ├── workers/
│   │   ├── celery_app.py
│   │   └── tasks/parse_cv.py        # solo orquesta extraction_service + seeding_service
│   └── core/
│       ├── config.py                # Settings Pydantic (umbrales, plazos, límites: nada hardcodeado)
│       ├── security.py, logging.py  # structlog + redactor de PII
│       └── rate_limit.py            # limitador Redis propio para /auth/*
└── tests/
    ├── unit/                        # dominio y servicios con dobles de adapters
    ├── integration/                 # repos + endpoints contra Postgres y Redis reales
    ├── architecture/                # test de dependencias unidireccionales (art. II)
    └── evals/
        ├── golden_set/              # CVs sintéticos/propios + esperados (NUNCA de usuarios)
        ├── metrics.py               # tasa de error por campo, precisión del clasificador
        └── test_extraction_evals.py # bloqueante en CI (art. VI, SC-003)

frontend/
├── src/
│   ├── api/
│   │   ├── schema.d.ts              # GENERADO desde OpenAPI — no editar a mano
│   │   └── client.ts                # openapi-fetch + manejo de access token en memoria
│   ├── features/
│   │   ├── auth/                    # login, registro, refresh silencioso
│   │   └── onboarding/
│   │       ├── consent/             # aviso de privacidad y aceptación (FR-030)
│   │       ├── upload/              # subida + progreso por polling
│   │       ├── review/              # entradas por tipo, origen, incompletas, CRUD
│   │       ├── objectives/          # cuestionario (react-hook-form + zod)
│   │       ├── confirm/             # resumen, bloqueadores, cambios sin confirmar
│   │       └── hooks/               # queries y mutaciones de TanStack Query
│   ├── components/ui/               # shadcn/ui
│   ├── routes/                      # react-router v6, code splitting por ruta
│   └── lib/
└── tests/                           # Vitest + RTL + MSW

infra/
├── docker/
│   ├── backend.Dockerfile           # multi-stage (builder uv → runtime slim)
│   └── frontend.Dockerfile          # multi-stage (build Vite → estáticos)
├── compose/
│   ├── docker-compose.yml           # api, worker, postgres(16+pgvector), redis, minio
│   └── docker-compose.override.yml  # hot reload en dev
└── .env.example

.github/workflows/ci.yml             # ruff · mypy --strict · pytest · evals · drift del cliente TS · build
```

**Structure Decision**: monorepo de tres raíces exactamente como lo fija el roadmap §5.1 (`backend/`, `frontend/`, `infra/`), sin desviaciones. Dentro de `backend/app/` la regla de dependencias `api → services → repositories/adapters` se hace verificable con un test de arquitectura en `backend/tests/architecture/`, para que el art. II no dependa de la disciplina de quien revisa el PR. `adapters/text_extraction/` existe como puerto —aunque pypdf y python-docx sean librerías locales, no servicios— porque FR-006 deja el OCR explícitamente reevaluable en v1.x: con puerto es un intercambio, sin puerto es una reescritura.

---

## Complexity Tracking

> Sin violaciones de la constitución que justificar. Esta sección registra la obligación del art. VII de justificar **cada dependencia nueva**.

### Dependencias nuevas — backend

| Dependencia | Para qué | Alternativa descartada |
|---|---|---|
| `pypdf` | Extracción de texto de PDF con capa de texto y conteo de caracteres por página para FR-006 | `pdfplumber` (más preciso en tablas, ~3× más lento y arrastra `pdfminer.six`); `PyMuPDF` (excelente, licencia AGPL — incompatible con producto cerrado) |
| `python-docx` | Extracción de DOCX recorriendo párrafos y tablas en orden de documento | Descomprimir el OOXML a mano: más código propio para el mismo resultado |
| `langchain-core` + `langchain-google-genai` | `with_structured_output` con esquemas Pydantic sobre Gemini | Fijado por ADR-003. SDK crudo de Google: perderíamos el reintento ante salida no conforme al esquema |
| `argon2-cffi` | Hash de contraseñas Argon2id | Fijado por ADR-001 (bcrypt y SHA descartados ahí) |
| `PyJWT` | Firma y verificación del access token | `python-jose`: sin mantenimiento activo y con tipado pobre para `mypy --strict` |
| `boto3` | Cliente S3-compatible | `minio` (atado a un servidor); `httpx` + firma SigV4 a mano (criptografía propia sin necesidad) |
| `structlog` | Logs estructurados con redacción de PII | Exigido por art. VIII |
| `celery` + `redis` | Cola del parseo asíncrono, revocación de `jti`, rate limiting | Fijados por roadmap §5. `arq`/RQ: menos operados por el equipo |
| `testcontainers[postgres,redis]` | Integración contra servicios reales | Exigido por art. VI. Postgres embebido: no soporta pgvector de forma fiable |
| `pgvector` (paquete Python) | Tipo de columna del puerto de embeddings | Ninguna: es el binding oficial |

### Dependencias nuevas — frontend

| Dependencia | Para qué | Alternativa descartada |
|---|---|---|
| `react-router` v6 | Enrutado de la SPA con code splitting por ruta (ADR-006 la implica, no la nombra) | TanStack Router (excelente tipado, menos rodaje en el equipo); enrutado a mano: reinvención |
| `openapi-typescript` + `openapi-fetch` | Cliente generado desde OpenAPI, cero tipos de API a mano (art. I) | `orval` (genera también hooks; más magia y más superficie de generación de la necesaria) |
| `msw` | Mocking de la API en tests de Vitest/RTL contra el mismo contrato OpenAPI | Mocks de `fetch` a mano: se desincronizan del contrato en silencio |

### Complejidades deliberadas (no son violaciones, pero se registran)

| Decisión | Por qué se acepta | Alternativa más simple y por qué se rechazó |
|---|---|---|
| `content JSONB` + discriminador en vez de una tabla por tipo de entrada | 7 tipos hoy, historias STAR mañana (ADR-005); una tabla evita 8 esquemas, 8 repos y 8 rutas | Tabla por tipo: más constraints de base, pero multiplica por 8 la superficie de API y de migraciones para un modelo que aún crecerá |
| `content_hash` derivado en lugar de bandera `has_unconfirmed_changes` | Se autocorrige: editar y deshacer deja de reportar cambios pendientes; imposible desincronizar | Bandera booleana: un servicio que olvide actualizarla rompe FR-028/FR-029 en silencio |
| Borrado lógico (`deleted_at`) de entradas | Mantiene el diff contra la versión vigente correcto y no le cierra la puerta a 007 (no resucitar lo que el candidato borró) | Borrado físico: más simple, pero pierde la información que 007 necesita para no reintroducir entradas descartadas |
| Limitador de tasa propio sobre Redis | ~40 líneas tipadas y testeables; evita dependencia nueva en un punto crítico de seguridad | `slowapi`: envoltorio delgado, tipado irregular bajo `mypy --strict` |
