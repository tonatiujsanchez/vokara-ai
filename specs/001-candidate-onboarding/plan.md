# Implementation Plan: Onboarding del candidato — de la primera ejecución al perfil maestro confirmado

**Branch**: `001-candidate-onboarding` | **Date**: 2026-08-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-candidate-onboarding/spec.md`

**Referencias normativas**: constitución **v2.1.0** (arts. I–XI) · `docs/product/roadmap.md` **v0.4** (§5, §5.1, §6, §9, §11) · ADR-003 (Gemini default sugerido + nota de muestreo y determinismo) · ADR-005 (perfil maestro) · ADR-006 (SPA React/Vite) · ADR-007 (storage local sin cifrado) · ADR-008 (sin autenticación) · ADR-009 (distribución local-first) · ADR-011 (proveedores independientes) · ADR-012 (correo opcional)

> **Regeneración del 2026-08-11.** Este plan reemplaza por completo al del 2026-08-10, que fue escrito contra la constitución v1.1.1 y quedó invalidado por el pivote local-first: asumía autenticación JWT (ADR-001), despliegue en VPS (ADR-002), cifrado en reposo del binario y un proveedor de LLM único. Ninguno de esos cuatro supuestos sigue vigente. El registro de qué cambió y por qué está en [research.md](./research.md) §"Qué cambió respecto del plan anterior".

---

## Summary

Esta feature entrega el camino completo desde que alguien abre Vokara por primera vez en su máquina hasta que tiene un perfil maestro confirmado y versionado: divulgación de qué sale de su equipo y qué no, configuración **independiente** del proveedor de generación y del de embeddings con preflight de capacidades, vinculación opcional de correo, subida del CV maestro (PDF/DOCX ≤ 10 MB), siembra del perfil con entradas atómicas `cv_seed`, revisión y enriquecimiento (`user_edited` / `user_added`), cuestionario de objetivos y **confirmación explícita**, momento en que el perfil pasa a `complete` y se materializa una versión inmutable.

**Enfoque técnico.** Todo el producto corre en la máquina del usuario detrás de un `docker compose up` (ADR-009). **No hay autenticación** (ADR-008): el `candidate_id` es un valor local fijo que la capa de API resuelve desde configuración y que el cliente nunca envía, pero que viaja explícito en la firma de cada repositorio para que una eventual versión hospedada añada auth encima en vez de reescribir la capa de datos.

El pipeline de parseo es determinista y de cuatro pasos (validación → extracción de texto → clasificación → extracción estructurada), ejecutado por un worker Celery que **solo orquesta servicios** (art. II). El LLM participa exclusivamente como componente con entrada y salida tipadas vía `with_structured_output` + Pydantic v2 (art. III); todo lo decidible por reglas —completitud, detección de PDF sin capa de texto, validación del rango salarial, elegibilidad de confirmación, diff de cambios sin confirmar— se decide por reglas y se prueba con unit tests. El versionado es una instantánea JSONB inmutable con hash de contenido canónico, y "tienes cambios sin confirmar" se **deriva** comparando hashes, no se mantiene como bandera.

**El determinismo del art. III no depende de ningún parámetro de muestreo.** Proviene de la estructura del pipeline: esquema Pydantic tipado en cada frontera, decisiones de flujo tomadas fuera del modelo y reglas testeables. `temperature`, `top_p` y `top_k` están deprecados en Gemini 3.x (ADR-003, nota del 2026-08-11) y no todos los proveedores los exponen igual, así que **no aparecen en la firma de ningún puerto ni en la capa de servicios**: son opcionales y propios de cada implementación del adapter.

Como el repositorio todavía no tiene código, este plan incluye también las fundaciones mínimas de la Fase 1 del roadmap (monorepo, tooling, CI bloqueante, Compose local con sus dos tests de binding, generación del cliente TS desde OpenAPI). Ver [Alcance](#alcance-y-precondiciones).

---

## Alcance y precondiciones

### Dentro del alcance

| Bloque | Justificación |
|---|---|
| Fundaciones del monorepo (roadmap §5.1), tooling (ruff, mypy `--strict`, pre-commit), CI bloqueante, `docker-compose.yml` con puertos en `127.0.0.1:` y sus **dos** tests de binding | El repo no tiene código. Sin esto nada de 001 es verificable. Roadmap paso 7b + ADR-008 "Mitigación obligatoria" (los tests van en el mismo PR que el Compose) |
| **FR-001 … FR-049 completos** | Es el cuerpo de la feature, incluida la primera ejecución (US1) que la spec reescrita incorporó |
| Adapter `adapters/llm/` con `StructuredOutputPort` y `EmbeddingsPort` **configurados de forma independiente**, matriz de capacidades declarada como dato, **preflight de capacidades como componente de primera clase**, y trazado de costo/latencia/versión de prompt sin PII | ADR-011 + arts. II, VIII y XI |
| Adapter `adapters/storage/` con `StoragePort` sobre filesystem local, sin cifrado | ADR-007 |
| Adapter `adapters/email/` con `EmailPort`, implementación Gmail App Password + IMAP, limitado en 001 a **verificar que la etiqueta designada existe y es alcanzable** | ADR-012, FR-011 – FR-013 |
| Evals de extracción contra golden set, bloqueantes en CI | Art. VI + SC-003 |

### Fuera del alcance (delegado y por qué)

| Excluido | Destino |
|---|---|
| Borrado del archivo, exportación de datos, borrado completo de la instalación, purga por retención | Feature **006**. El modelo de datos deja los ganchos preparados ([data-model.md](./data-model.md) §"Compatibilidad con 006 y 007"); **no se implementan** |
| Re-subida de CV con perfil existente, fusión, criterio de equivalencia, origen de versión `cv_merge`, reversión | Feature **007**. El enum `version_origin` nace con `confirmation` y con espacio explícito para `cv_merge`; **no se implementa** |
| Registro, login, cuentas, sesiones, recuperación de contraseña, **envío de correo de cualquier tipo** | No existen en v1 (ADR-008, ADR-009). No están delegados a otra feature: no hay tal cosa |
| Cifrado en reposo y crypto-shredding | Retirados de v1 (ADR-007). Diferidos a un eventual despliegue multiusuario, no descartados |
| Adapters de proveedor distintos de Google | **Decisión de este plan**, ver [Portabilidad de proveedor](#portabilidad-de-proveedor-con-una-sola-implementación). La verificación empírica del ADR-011 va primero; FR-009 impide ofrecer lo no verificado |
| Lectura y parseo de los correos de alerta | F1.3.2. Aquí se vincula la cuenta y se designa la etiqueta; ingerir vacantes desde ella es la feature de fuentes |
| Vía OAuth con proyecto propio de Google Cloud | ADR-012, opción avanzada. Aquí solo se enlaza como alternativa documentada |
| Pantalla de diagnóstico permanente del sistema | Roadmap §11.4. Esta feature cubre la configuración inicial, no el panel de estado continuo |
| Costo **real** acumulado y kill-switch de funciones caras | Roadmap §11.3. Aquí solo el costo **estimado** antes de pedir la llave (FR-005) |
| Cambio de proveedor desde Ajustes y re-embebido de vectores | ADR-011. Aquí no hay vectores todavía |
| Cálculo y persistencia de embeddings | El **puerto** y su implementación Google se entregan aquí (ADR-011: los dos proveedores se configuran en el wizard, así que el de embeddings debe poder verificarse); no se persiste ningún vector porque en 001 no hay consumidor. La convención de ADR-003 (`embedding_model` + `embedding_dim` junto a cada vector) queda escrita en `data-model.md` y la extensión `pgvector` se habilita en la primera migración. Ver [research.md](./research.md) R-12 |
| Normalización de skills contra taxonomía (ADR-004), matching, generación de materiales, tracker, alertas | Features posteriores del roadmap |
| Playwright e2e, Sentry, Langfuse/LangSmith | E2E: el input del plan fija Vitest + RTL. Sentry: prohibido por defecto (art. VIII v2.1.0). Plataformas de trazas de LLM: descartadas porque su valor es guardar prompts, que aquí son PII íntegra (ADR-003) |

### Sin decisiones abiertas bloqueantes

El plan anterior tenía dos. Ambas están cerradas: el almacenamiento de documentos lo resolvió el **ADR-007**, y el trazado de LLM sin plataformas externas quedó ratificado en el **ADR-003** (nota de consecuencias) y en el **art. VIII v2.1.0**. Este plan no introduce ninguna decisión de arquitectura que requiera un ADR nuevo: la evaluación del runtime asíncrono (research R-28) concluye **mantener** el stack fijado por el roadmap, precisamente para no necesitarlo.

---

## Technical Context

**Language/Version**: Python 3.12 (backend, worker) · TypeScript 5.x sobre Node 20 LTS (frontend)

**Primary Dependencies**:
*Backend* — FastAPI, Pydantic v2, **pydantic-settings**, SQLAlchemy 2.0 (tipado, `Mapped[]`), Alembic, Celery 5 + Redis, pypdf, python-docx, `langchain-core` + `langchain-google-genai`, structlog, `pgvector` (extensión + binding Python para el puerto de embeddings), `imaplib` de la biblioteca estándar para el `EmailPort`.
*Frontend* — React 18, Vite 5, TanStack Query v5, react-hook-form + zod, Tailwind + shadcn/ui, react-router v6, `openapi-typescript` + `openapi-fetch`.

**Explícitamente fuera**: PyJWT y argon2-cffi (no hay auth), boto3 y MinIO (no hay object storage), Sentry (prohibido por defecto), limitador de tasa (no hay endpoints de auth que proteger; la instancia escucha solo en loopback).

**Storage**: Postgres 16 + pgvector — **una sola base de datos** (art. VII) · Redis (**broker de Celery y nada más**: con ADR-008 desaparecieron la revocación de `jti` y el rate limiting, sus otros dos usos) · Filesystem local para los binarios de CV, detrás del `StoragePort`, **sin cifrado** (ADR-007)

**Configuration**: pydantic-settings leyendo `.env`, con precedencia **entorno > archivo > defaults**. API keys y App Password como `SecretStr`, leídas de configuración local y **nunca persistidas en la base de datos** ni presentes en logs, trazas, mensajes de error o respuestas de la API (FR-008, FR-013, art. V). Los **nombres de modelo viven en configuración con override por variable de entorno**, nunca en constantes de código (ADR-011, notas de verificación).

**Testing**: pytest + pytest-asyncio + **testcontainers** (Postgres 16 real y Redis real) · evals de extracción contra golden set en `backend/tests/evals/`, bloqueantes en CI · Vitest + React Testing Library + MSW en frontend · cobertura ≥ 80% en `services/` y `domain/`

**Target Platform**: la máquina del usuario. Docker Compose local probado en Windows (WSL2), macOS y Linux (ADR-009). **Sin VPS, sin staging, sin prod, sin reverse proxy, sin TLS.** CI valida, no despliega (roadmap §9).

**Project Type**: Web application local — monorepo `backend/` + `frontend/` + `infra/` (roadmap §5.1)

**Performance Goals**:
- SC-004: p95 < 60 s desde que termina la subida hasta que hay entradas revisables. Presupuesto por etapa en [research.md](./research.md) R-14 (objetivo p95 ≈ 45 s, 15 s de margen).
- SC-014: mediana del recorrido de los pasos obligatorios de la primera ejecución < 10 min. El preflight de cada credencial responde en < 10 s o informa que no pudo verificar.
- API síncrona: p95 < 300 ms en endpoints de perfil y entradas (sin llamadas a LLM).
- Subida de 10 MB aceptada y encolada en < 3 s.

**Constraints**:
- `mypy --strict` sin `# type: ignore` no justificado; ruff lint + format; ambos bloqueantes en CI.
- **PII fuera de logs y trazas** (FR-045, FR-046): ni contenido del CV, ni prompts, ni respuestas del modelo.
- **Cero credenciales** en base de datos, logs, trazas, mensajes de error o respuestas (FR-008, FR-013, SC-013).
- **Todo puerto publicado del Compose lleva prefijo `127.0.0.1:`**; `postgres` y `redis` no se publican en absoluto (ADR-008).
- Solo **un** `parse_job` activo por candidato, garantizado por índice único parcial, no por lógica de aplicación.
- Sin OCR (FR-021). Sin envío de correo en toda la feature (FR-003).
- Migraciones Alembic reversibles y **tolerantes a saltos de varias versiones** (ADR-009); se aplican **automáticamente al arranque** (roadmap §11.1).
- El cliente TS del frontend se genera desde OpenAPI; CI falla si está desincronizado (art. I).
- Ninguna parte del código fuera de `adapters/llm/` menciona el nombre de un proveedor (art. XI), verificado por test de arquitectura.

**Scale/Scope**: **un usuario por instalación** · 1 perfil · ~20–120 entradas por perfil · CVs de 1–10 páginas · 3 pantallas de primera ejecución (divulgación, proveedores, correo) + 4 de onboarding (subida, revisión, objetivos, confirmación).

---

## Constitution Check

*GATE: debe pasar antes de la Fase 0 y re-evaluarse tras la Fase 1.* Constitución **v2.1.0**, once artículos.

### Evaluación inicial (pre-diseño) — **PASA**

| Artículo | Cómo lo satisface este plan | Estado |
|---|---|---|
| **I. Tipado estricto E2E** | `mypy --strict` bloqueante; Pydantic v2 en request/response, salida del LLM (`with_structured_output`), payload de la tarea Celery, configuración (pydantic-settings) y retorno de adapters; cliente TS generado con `openapi-typescript` y verificado en CI con `git diff --exit-code`. Prohibido tipear la API a mano. | ✅ |
| **II. Capas unidireccionales** | `api/` solo valida y delega; `workers/tasks/` solo orquesta servicios. Todo lo externo detrás de puerto: LLM, embeddings, storage, correo, extracción de texto. Test de arquitectura que falla si `api/` importa `db/` o si `adapters/` importa `services/`. El adapter de LLM cubre también embeddings, con la regla de persistencia (`embedding_model`, `embedding_dim`) escrita antes del primer vector. | ✅ |
| **III. Determinismo primero** | Pipeline de 4 pasos fijos, sin agente, sin herramientas, sin bucle. El LLM aparece **dos** veces, ambas con esquema Pydantic de salida (clasificar, extraer) y una tercera en el preflight, también contra un esquema real. Completitud, detección de PDF sin capa de texto, validación de salario, elegibilidad de confirmación e interpretación del resultado de preflight son **reglas**, no juicio del modelo. **El determinismo no se apoya en ningún parámetro de muestreo** (ADR-003): lo sostienen el esquema tipado, las decisiones fuera del LLM y las evals del golden set. | ✅ |
| **IV. Veracidad** | El perfil maestro es la entidad estructurada fuente de verdad; el archivo es respaldo (FR-018, ADR-005). Entradas atómicas con `id` estable (FR-025) que sostendrán el `source_id` de features posteriores. Todos los campos no garantizados son opcionales y el prompt exige `null` ante ausencia; **el preflight usa ese mismo criterio como prueba de aceptación del proveedor** (ADR-011: un modelo que rellena opcionales con texto inventado produce afirmaciones sin sustento). Las evals incluyen invención y exageración como fallo. | ✅ |
| **V. Privacidad local-first y transparencia** | La divulgación del art. V es la **primera pantalla** y es bloqueante (FR-001, FR-002). Cero telemetría, analítica o reportes de error a terceros. API keys y App Password en configuración local, nunca en base de datos, nunca en logs ni en mensajes de error (FR-008, FR-013). PII fuera de logs y de trazas de LLM (FR-045, FR-046). Golden set sin material de usuarios reales (FR-047, FR-048). Sin scraping y sin auto-apply: fuera de alcance de esta feature. | ✅ |
| **VI. Calidad verificable** | pytest unit + integración contra Postgres y Redis reales (testcontainers). Evals de extracción con golden set bloqueantes en CI. Cobertura ≥ 80% en `services/` y `domain/`. Los tests del `EmailPort` son **tests de cumplimiento** del acotamiento por etiqueta (ADR-012), no de funcionalidad. | ✅ |
| **VII. Simplicidad (YAGNI)** | Una sola base (Postgres + pgvector). Sin microservicios, sin Kubernetes, sin vector-store aparte, **sin MinIO**. Compose de **cuatro** servicios y ni uno más; **se elimina `beat`** porque nada en 001 se agenda (research R-28). Polling en vez de SSE/WebSocket. Cada dependencia nueva justificada en [Complexity Tracking](#complexity-tracking). Embeddings: puerto sí, tabla de vectores no. | ✅ |
| **VIII. Observabilidad** | Toda llamada al LLM traza costo, latencia y versión de prompt — **solo metadatos**, nunca prompt ni respuesta. structlog con `request_id` y `parse_job_id`, con procesador de redacción. **Sin Sentry**: errores en logs locales estructurados; el envío externo exigiría el opt-in del art. V y está desactivado de fábrica. | ✅ |
| **IX. Idioma** | UI, mensajes de error y estos documentos en español. Código, identificadores, ramas y commits en inglés. Los valores de enum (`cv_seed`, `draft`, `complete`) son identificadores → inglés. | ✅ |
| **X. Control humano** | `POST /profile/confirm` es el **único** camino a `complete`. No hay setter administrativo, ni transición desde el worker, ni efecto colateral de reintento o edición masiva. Doble candado: servicio único escritor del estado + `CHECK (state <> 'complete' OR current_version_id IS NOT NULL)`. Además, ningún paso del wizard avanza sin acción explícita del usuario: el acuse de divulgación y el de degradación son afirmativos y nunca preseleccionados (FR-002, FR-007.3). | ✅ |
| **XI. Portabilidad de proveedor** | `StructuredOutputPort` y `EmbeddingsPort` se configuran de forma **independiente**, cada uno con su proveedor, su credencial y su modelo, y ambos admiten **`base_url` configurable y credencial opcional** desde el día 1 (ADR-011 decisión 5). Matriz de capacidades **declarada como dato**, no como comportamiento. **Ninguna feature consulta el nombre del proveedor**, y un test de arquitectura falla si aparece fuera de `adapters/llm/`. Capacidad ausente → degradación explícita e informada con acuse específico (FR-007.3), nunca silenciosa. | ✅ |

**Restricciones adicionales**: stack idéntico al fijado por roadmap §5, **incluida la fila de colas** — la evaluación de research R-28 concluye mantener Celery + Redis, así que no hay cambio de stack que requiera ADR. ADR-003, 005, 006, 007, 008, 009, 011 y 012 respetados sin desviación. ADR-004 no aplica (normalización de skills fuera de alcance). ADR-001 y ADR-002 están Superseded y este plan no los implementa.

### Re-evaluación post-diseño (Fase 1) — **PASA**

Revisados `data-model.md`, `contracts/openapi.yaml`, `contracts/llm-extraction.md`, `contracts/errors.md` y `quickstart.md`:

- **Art. I** — `profile_entries` usa `content JSONB` con discriminador `entry_type`. Verificado que no debilita el tipado: la unión discriminada de Pydantic v2 se serializa en OpenAPI como `oneOf` + `discriminator`, y `openapi-typescript` la traduce a una unión discriminada de TypeScript. El estrechamiento de tipo en el front sigue siendo del compilador. ✅
- **Art. III** — Ningún paso del pipeline delega una decisión de flujo al modelo. Confirmado en `contracts/llm-extraction.md`: la salida del clasificador es un booleano tipado que el servicio interpreta, la del extractor es una lista de entradas que un paso de reglas evalúa, y **el resultado del preflight es un tipo suma de cuatro variantes que decide el servicio**, no el proveedor. Verificado además que ni `plan.md`, ni `research.md`, ni `contracts/llm-extraction.md` invocan `temperature` como argumento de determinismo. ✅
- **Art. V** — Revisado esquema por esquema: ninguna respuesta de la API expone una credencial, ni parcialmente; el estado consultable de una credencial es exactamente `configured | not_configured | rejected`. Ninguna tabla persiste credenciales; `setup_state` guarda el **resultado** del preflight y un `credential_fingerprint` que es un digest HMAC, no la llave ni un fragmento suyo (research R-24). El catálogo de errores no reproduce contenido del documento ni rutas de storage crudas. ✅
- **Art. VII** — Revisada cada tabla nueva contra el alcance: 9 tablas, ninguna especulativa. Se descartaron durante el diseño una tabla `onboarding_steps` (el paso se deriva del estado), una `profile_entry_embeddings` (sin consumidor), una bandera persistida `has_unconfirmed_changes` (se deriva del hash) y una tabla de credenciales (viven en configuración). Se eliminaron respecto del diseño anterior `refresh_tokens` y `privacy_consents`. ✅
- **Art. X** — Doble candado modelado: transición de estado solo en `ConfirmationService`, más `CHECK complete_requires_version` y trigger que impide `UPDATE`/`DELETE` sobre `profile_versions`. ✅
- **Art. XI** — Verificado que el contrato HTTP expone `capability` (`generation` | `embeddings`) como parámetro de ruta y el proveedor como **valor de catálogo**, de modo que el frontend tampoco ramifica por proveedor: renderiza la lista que el backend le da. ✅

Sin violaciones que justificar más allá de lo registrado en [Complexity Tracking](#complexity-tracking).

---

## Portabilidad de proveedor con una sola implementación

En 001 se implementa **un solo adapter de proveedor: Google**. Es el único con la fila de verificación empírica completa en el ADR-011 (2026-08-11: `gemini-3.5-flash-lite` con salida estructurada y respeto de `null` en opcionales; `gemini-embedding-001` truncado a 768 dimensiones vía MRL), y **FR-009 prohíbe ofrecer un proveedor sin verificación registrada**. Implementar hoy los otros cuatro sería escribir código que no se puede probar contra nada real y que la UI no puede mostrar; si alguno falla el criterio de `null`, ese trabajo se descarta. **La verificación empírica va primero, la implementación después.**

Que haya una sola implementación **no relaja el art. XI**. Se sostiene con dos piezas que se entregan en esta feature, no cuando llegue la segunda:

1. **La forma del puerto.** `StructuredOutputPort` y `EmbeddingsPort` admiten **`base_url` configurable y credencial opcional** desde el día 1 (ADR-011 decisión 5). El motivo es concreto: añadir Ollama —o cualquier servidor compatible con la API de OpenAI— debe ser una implementación nueva del puerto, **no un refactor del puerto**. Un puerto que da por sentado "hay una API key" y "el endpoint es el del proveedor" convierte esa adición futura en un cambio que toca todo lo que hay detrás. Los parámetros de muestreo tampoco entran en la firma, por la misma razón y por la nota del ADR-003.
2. **Un test de arquitectura que falla si el nombre de un proveedor aparece fuera de `adapters/llm/`.** Con una sola implementación es trivial de pasar, y ese es exactamente el momento de instalarlo: queda puesto **antes** de que exista la segunda, que es cuando se rompería sin él. Un `if provider == "..."` fuera del adapter es un bug del art. XI, no un atajo, y esta es la forma de que la revisión de PR no dependa de que alguien lo note.

La **matriz de capacidades se declara con las cinco filas** del ADR-011, no solo con Google: las cuatro pendientes llevan `verified_on: null` y la UI no las ofrece (FR-009). Completar una fila es entonces un cambio de datos más una implementación de puerto, sin tocar servicios ni frontend.

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
│   ├── llm-extraction.md       # Puertos, preflight, esquemas de salida y versionado de prompts
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
│   │   ├── deps.py                  # local_candidate_id (de configuración, NUNCA del cliente), sesión DB
│   │   ├── errors.py                # excepciones de dominio → respuesta {code,message,details}
│   │   └── v1/
│   │       ├── setup.py             # divulgación, proveedores + preflight, correo, estado del wizard
│   │       ├── documents.py         # subida, consulta de documento
│   │       ├── parse_jobs.py        # estado, reintento
│   │       ├── profile.py           # perfil, objetivos, confirmación, pending-changes
│   │       ├── profile_entries.py   # CRUD de entradas
│   │       └── profile_versions.py  # historial y detalle de versiones
│   ├── domain/                      # Pydantic v2 + enums + reglas puras (sin I/O)
│   │   ├── enums.py                 # ProfileState, EntryType, EntryOrigin, VersionOrigin, ...
│   │   ├── entries.py               # unión discriminada del contenido por tipo de entrada
│   │   ├── completeness.py          # reglas de completitud por tipo (FR-028)
│   │   ├── objectives.py            # cuestionario + validación de rango salarial (FR-036)
│   │   ├── confirmation.py          # reglas de elegibilidad de confirmación (FR-039)
│   │   ├── diff.py                  # diff trabajo en curso vs versión vigente (FR-044)
│   │   ├── canonical.py             # serialización canónica + content_hash
│   │   ├── setup.py                 # paso pendiente del wizard, derivado por reglas (FR-014)
│   │   ├── capability.py            # Capability (generation | embeddings) y resultado de preflight
│   │   └── errors.py                # jerarquía de errores de dominio
│   ├── services/
│   │   ├── setup_service.py         # acuse, avance del wizard, conclusión de la primera ejecución
│   │   ├── preflight_service.py     # ejecuta y clasifica el preflight; ÚNICO intérprete de sus 4 resultados
│   │   ├── provider_catalog_service.py  # catálogo ofrecible = matriz verificada + costo estimado
│   │   ├── email_link_service.py    # verificación de la etiqueta designada (FR-013)
│   │   ├── document_service.py      # validación, persistencia vía StoragePort, encolado
│   │   ├── extraction_service.py    # orquesta texto → clasificación → extracción tipada
│   │   ├── seeding_service.py       # entradas del LLM → profile_entries (transacción única)
│   │   ├── profile_service.py       # lectura del perfil, paso derivado del onboarding
│   │   ├── entry_service.py         # alta/edición/borrado y transiciones de origen
│   │   ├── objectives_service.py
│   │   ├── confirmation_service.py  # ÚNICO camino a `complete` (art. X)
│   │   └── version_service.py       # snapshot inmutable, historial, diff pendiente
│   ├── adapters/
│   │   ├── llm/
│   │   │   ├── base.py              # StructuredOutputPort, EmbeddingsPort (base_url + credencial opcionales)
│   │   │   ├── capabilities.py      # MATRIZ declarada como dato (ADR-011), con verified_on
│   │   │   ├── pricing.py           # catálogo de costo estimado, generación y embeddings por separado
│   │   │   ├── google.py            # ÚNICA implementación en v1 (langchain-google-genai)
│   │   │   ├── factory.py           # resuelve puerto ← configuración; único lugar que conoce nombres
│   │   │   ├── schemas.py           # esquemas Pydantic de salida del modelo y del preflight
│   │   │   ├── prompts/             # prompts versionados (CV_EXTRACTION_V1, ...)
│   │   │   └── tracing.py           # costo, latencia, versión de prompt (sin PII)
│   │   ├── storage/
│   │   │   ├── base.py              # StoragePort (put/get/delete/exists)
│   │   │   └── local_fs.py          # filesystem local, sin cifrado (ADR-007)
│   │   ├── email/
│   │   │   ├── base.py              # EmailPort
│   │   │   └── gmail_imap.py        # App Password + IMAP, acotado a la etiqueta designada
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
│   │   ├── celery_app.py            # worker SIN beat (research R-28)
│   │   └── tasks/parse_cv.py        # solo orquesta extraction_service + seeding_service
│   └── core/
│       ├── config.py                # pydantic-settings: entorno > .env > defaults; SecretStr; modelos configurables
│       ├── logging.py               # structlog + redactor de PII y de credenciales
│       └── data_dir.py              # resolución y verificación del directorio de datos local
└── tests/
    ├── unit/                        # dominio y servicios con dobles de adapters
    ├── integration/                 # repos y endpoints contra Postgres y Redis reales
    │   └── test_local_binding.py    # los DOS tests exigidos por el ADR-008
    ├── architecture/                # art. II (unidireccionalidad) + art. XI (nombre de proveedor)
    └── evals/
        ├── golden_set/              # CVs sintéticos/propios + esperados (NUNCA de usuarios)
        ├── metrics.py               # tasa de error por campo, precisión del clasificador, invención
        └── test_extraction_evals.py # bloqueante en CI (art. VI, SC-003)

frontend/
├── src/
│   ├── api/
│   │   ├── schema.d.ts              # GENERADO desde OpenAPI — no editar a mano
│   │   └── client.ts                # openapi-fetch tipado
│   ├── features/
│   │   ├── setup/                   # wizard de primera ejecución
│   │   │   ├── disclosure/          # texto completo en pantalla + acuse (FR-001, FR-002)
│   │   │   ├── providers/           # generación y embeddings por separado, costo previo, preflight
│   │   │   └── email/               # vinculación opcional, con divulgación previa (FR-011 – FR-013)
│   │   └── onboarding/
│   │       ├── upload/              # subida + progreso por polling
│   │       ├── review/              # entradas por tipo, origen, incompletas, CRUD
│   │       ├── objectives/          # cuestionario (react-hook-form + zod)
│   │       ├── confirm/             # resumen, bloqueadores, cambios sin confirmar
│   │       └── hooks/               # queries y mutaciones de TanStack Query
│   ├── components/ui/               # shadcn/ui
│   ├── routes/                      # react-router v6 + guard de primera ejecución
│   └── lib/
└── tests/                           # Vitest + RTL + MSW

infra/
├── docker/
│   ├── backend.Dockerfile           # multi-stage (builder uv → runtime slim); entrypoint aplica migraciones
│   └── frontend.Dockerfile          # multi-stage (build Vite → estáticos)
├── docker-compose.yml               # api, worker, postgres(16+pgvector), redis — puertos SOLO 127.0.0.1
├── docker-compose.override.yml      # hot reload en dev, misma regla de binding
└── .env.example

.github/workflows/ci.yml             # ruff · mypy --strict · pytest · binding · evals · drift TS · build · instalación limpia
```

**Structure Decision**: monorepo de tres raíces exactamente como lo fija el roadmap §5.1 (`backend/`, `frontend/`, `infra/`), sin desviaciones. Dentro de `backend/app/` la regla `api → services → repositories/adapters` se hace verificable con tests en `backend/tests/architecture/`, para que los arts. II y XI no dependan de la disciplina de quien revisa el PR. `adapters/text_extraction/` existe como puerto —aunque pypdf y python-docx sean librerías locales, no servicios— porque FR-021 deja el OCR explícitamente reevaluable en v1.x: con puerto es un intercambio, sin puerto es una reescritura. El `docker-compose.yml` vive en la raíz de `infra/` y no en `infra/compose/` para que el comando de instalación sea lo más corto posible (roadmap §11.1).

---

## Complexity Tracking

> Sin violaciones de la constitución que justificar. Esta sección registra la obligación del art. VII de justificar **cada dependencia nueva** y cada complejidad deliberada.

### Dependencias nuevas — backend

| Dependencia | Para qué | Alternativa descartada |
|---|---|---|
| `pypdf` | Extracción de texto de PDF con capa de texto y conteo de caracteres por página para FR-021 | `pdfplumber` (más preciso en tablas, ~3× más lento, arrastra `pdfminer.six`); `PyMuPDF` (excelente, licencia AGPL — compatible con la nuestra pero ataría la licencia de cualquier redistribución, y su ventaja no es decisiva aquí) |
| `python-docx` | Extracción de DOCX recorriendo párrafos y tablas en orden de documento | Descomprimir el OOXML a mano: más código propio para el mismo resultado |
| `langchain-core` + `langchain-google-genai` | `with_structured_output` con esquemas Pydantic (ADR-003) | SDK crudo de Google: perderíamos el reintento ante salida no conforme al esquema y la forma común que abarata la segunda implementación del puerto |
| `pydantic-settings` | Configuración tipada con precedencia entorno > archivo > defaults y `SecretStr` para credenciales | `os.environ` a mano: sin validación, sin tipos y sin redacción automática en `repr`, justo donde una fuga es un incidente (art. V) |
| `structlog` | Logs estructurados con redacción de PII y credenciales | Exigido por art. VIII |
| `celery` + `redis` | Cola del parseo asíncrono | Fijados por roadmap §5. La evaluación completa frente a `arq` y `BackgroundTasks` está en research R-28 |
| `testcontainers[postgres,redis]` | Integración contra servicios reales | Exigido por art. VI. Postgres embebido: no soporta pgvector de forma fiable |
| `pgvector` (paquete Python) | Tipo de columna del puerto de embeddings | Ninguna: es el binding oficial |

`imaplib` y `hmac` son de la biblioteca estándar: el `EmailPort` y el `credential_fingerprint` no añaden dependencia.

### Dependencias nuevas — frontend

| Dependencia | Para qué | Alternativa descartada |
|---|---|---|
| `react-router` v6 | Enrutado de la SPA con code splitting y **guard de primera ejecución** (FR-002, FR-010) | TanStack Router (excelente tipado, menos rodaje en el equipo); enrutado a mano: reinvención |
| `openapi-typescript` + `openapi-fetch` | Cliente generado desde OpenAPI, cero tipos de API a mano (art. I) | `orval` (genera también hooks; más magia y más superficie de generación de la necesaria) |
| `msw` | Mocking de la API en tests de Vitest/RTL contra el mismo contrato OpenAPI | Mocks de `fetch` a mano: se desincronizan del contrato en silencio |

### Complejidades deliberadas (no son violaciones, pero se registran)

| Decisión | Por qué se acepta | Alternativa más simple y por qué se rechazó |
|---|---|---|
| `worker` + `redis` en el Compose para un solo usuario local | El art. VII mide la fricción en **pasos que el usuario ejecuta**, y ninguno de los dos añade alguno: `docker compose up` los levanta igual. A cambio, aíslan una llamada de 30–60 s del event loop de la API y sobreviven a su reinicio (research R-28) | `BackgroundTasks`: −2 servicios, pero el parseo compite con la API por el proceso, un reinicio abandona el trabajo en vuelo y contradice roadmap §5, exigiendo un ADR nuevo para volver a introducir un worker en F1.3/F1.6 |
| `credential_fingerprint` (HMAC truncado) en `setup_state` | Sin él, rotar la llave en el `.env` deja un preflight persistido que miente, contra SC-012. Es un digest, no la llave ni un fragmento suyo (research R-24) | No persistir nada y re-verificar en cada arranque: 2 llamadas de red y su costo en cada `docker compose up`, y un arranque que falla si el proveedor está caído |
| Matriz de capacidades con **cinco** filas y solo una implementada | Declarar la matriz completa hace que completar un proveedor sea datos + una implementación, sin tocar servicios ni front. Las filas sin `verified_on` no se ofrecen (FR-009) | Declarar solo Google: al llegar el segundo proveedor habría que inventar la forma de la matriz con prisa y con dos casos ya en producción |
| `content JSONB` + discriminador en vez de una tabla por tipo de entrada | 7 tipos hoy, historias STAR mañana (ADR-005); una tabla evita 8 esquemas, 8 repos y 8 rutas | Tabla por tipo: más constraints de base, pero multiplica por 8 la superficie de API y de migraciones para un modelo que aún crecerá |
| `content_hash` derivado en lugar de bandera `has_unconfirmed_changes` | Se autocorrige: editar y deshacer deja de reportar cambios pendientes; imposible desincronizar | Bandera booleana: un servicio que olvide actualizarla rompe FR-043/FR-044 en silencio |
| Borrado lógico (`deleted_at`) de entradas | Mantiene el diff contra la versión vigente correcto y no le cierra la puerta a 007 (no resucitar lo que el candidato borró) | Borrado físico: más simple, pero pierde la información que 007 necesita |
| `candidate_id` explícito en toda firma de repositorio, con un solo valor posible | Añadir auth después es cambiar **de dónde sale** el `candidate_id`, no reescribir la capa de datos (ADR-008). Los tests lo verifican con **dos** valores para que la disciplina sea ejecutable | Omitirlo "porque da igual hoy": deuda que solo se cobra el día de la migración a hospedado, cuando ya no hay forma barata de pagarla |
