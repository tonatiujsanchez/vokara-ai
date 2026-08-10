# Fase 1 — Modelo de datos

**Feature**: 001-candidate-onboarding · **Fecha**: 2026-08-10 · **Plan**: [plan.md](./plan.md) · **Decisiones**: [research.md](./research.md)

Base: Postgres 16 + pgvector. ORM: SQLAlchemy 2.0 tipado (`Mapped[...]`). Migraciones: Alembic, reversibles. Todos los identificadores de tabla, columna y valor de enum en inglés (art. IX).

Convención transversal: **toda** consulta de repositorio recibe el `candidate_id` que la dependencia de autenticación extrajo del token. Ningún endpoint acepta `candidate_id` del cliente (FR-034).

---

## Diagrama de relaciones

```text
candidates ──1:1── candidate_profiles ──1:N── profile_entries
    │                     │                        │
    │                     └──1:N── profile_versions │
    │                                  ▲            │
    │                     current_version_id ───────┘ (FK opcional)
    │
    ├──1:N── privacy_consents
    ├──1:N── refresh_tokens
    └──1:N── documents ──1:N── parse_jobs
                  ▲
                  └── profile_entries.source_document_id (FK opcional)

llm_call_logs (sin FK a datos personales; referencia parse_job_id)
```

---

## Enums

Se declaran como tipos nativos de Postgres para que la base rechace valores fuera de dominio, y como `enum.StrEnum` en `domain/enums.py`.

| Enum | Valores | Notas |
|---|---|---|
| `profile_state` | `draft`, `complete` | Transición única y unidireccional en 001 (FR-027: nunca vuelve a `draft`) |
| `entry_type` | `experience`, `achievement`, `education`, `skill`, `certification`, `language`, `project` | ADR-005 prevé `star_story`; **no** se añade en 001 (art. VII). Añadirlo es un `ALTER TYPE ... ADD VALUE` sin migración de datos |
| `entry_origin` | `cv_seed`, `user_added`, `user_edited` | FR-011. Transiciones en R-09 |
| `version_origin` | `confirmation` | La feature 007 añadirá `cv_merge`. El enum nace con un solo valor **a propósito**: así ningún camino de 001 puede producir otro origen |
| `parse_job_status` | `queued`, `running`, `succeeded`, `failed` | FR-004 |
| `parse_job_step` | `extracting_text`, `classifying`, `extracting_entries`, `persisting` | Para el progreso legible |
| `document_kind` | `pdf`, `docx` | FR-001 |
| `document_availability` | `available` | La feature 006 añadirá `deleted_by_candidate` y `purged_by_retention`. La columna existe desde 001 para que 006 no tenga que retro-poblarla |
| `remote_preference` | `onsite`, `hybrid`, `remote`, `any` | FR-020 |

---

## Tablas

### `candidates`

Cuenta del candidato (ADR-001). No es una entidad de la spec 001; existe porque el onboarding arranca con un candidato autenticado.

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | `uuid` | PK, `gen_random_uuid()` |
| `email` | `citext` | `NOT NULL`, `UNIQUE` |
| `password_hash` | `text` | `NOT NULL` — Argon2id (ADR-001) |
| `is_active` | `boolean` | `NOT NULL DEFAULT true` |
| `created_at` / `updated_at` | `timestamptz` | `NOT NULL DEFAULT now()` |

- `email_verified_at` se omite: la verificación de correo queda diferida (plan §Alcance). Añadirla después es una columna anulable, no una migración destructiva.
- La extensión `citext` da unicidad de correo insensible a mayúsculas sin normalizar a mano en cada consulta.

---

### `privacy_consents` — FR-030

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | `uuid` | PK |
| `candidate_id` | `uuid` | FK → `candidates.id` `ON DELETE CASCADE`, `NOT NULL` |
| `policy_version` | `text` | `NOT NULL` — versión del aviso vigente al aceptar |
| `accepted_at` | `timestamptz` | `NOT NULL DEFAULT now()` |

- Índice: `(candidate_id, policy_version)` único.
- **No** se guardan IP ni user-agent: no son necesarios para la evidencia de consentimiento que exige la spec y serían datos personales adicionales (minimización, art. V).
- La versión vigente vive en `Settings.PRIVACY_POLICY_VERSION`. La subida se rechaza con `CONSENT_REQUIRED` si no existe consentimiento para esa versión.

---

### `refresh_tokens` — ADR-001

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | `uuid` | PK |
| `candidate_id` | `uuid` | FK → `candidates.id` `ON DELETE CASCADE`, `NOT NULL` |
| `family_id` | `uuid` | `NOT NULL` — identifica la cadena de rotación |
| `token_hash` | `text` | `NOT NULL`, `UNIQUE` — SHA-256 del token opaco |
| `expires_at` | `timestamptz` | `NOT NULL` |
| `used_at` | `timestamptz` | `NULL` — no nulo ⇒ ya rotado |
| `revoked_at` | `timestamptz` | `NULL` |
| `created_at` | `timestamptz` | `NOT NULL DEFAULT now()` |

- Índices: `(candidate_id)`, `(family_id)`, `(expires_at)`.
- **Detección de reuso**: presentar un token con `used_at IS NOT NULL` revoca toda la familia (`UPDATE ... WHERE family_id = ...`) y publica sus `jti` en la lista de revocados de Redis.
- El token en claro nunca se persiste.

---

### `candidate_profiles` — perfil maestro (FR-014, FR-020 – FR-029, ADR-005)

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | `uuid` | PK |
| `candidate_id` | `uuid` | FK → `candidates.id` `ON DELETE CASCADE`, `NOT NULL`, **`UNIQUE`** (1:1) |
| `state` | `profile_state` | `NOT NULL DEFAULT 'draft'` |
| `current_version_id` | `uuid` | FK → `profile_versions.id`, `NULL` mientras no haya confirmación |
| `last_confirmed_at` | `timestamptz` | `NULL` |
| **Objetivos (FR-020)** | | |
| `target_role` | `text` | `NULL` |
| `salary_min` | `numeric(12,2)` | `NULL` |
| `salary_max` | `numeric(12,2)` | `NULL` |
| `salary_currency` | `char(3)` | `NULL` |
| `remote_preference` | `remote_preference` | `NULL` |
| `locations` | `text[]` | `NOT NULL DEFAULT '{}'` |
| `industries` | `text[]` | `NOT NULL DEFAULT '{}'` |
| `deal_breakers` | `text[]` | `NOT NULL DEFAULT '{}'` |
| `created_at` / `updated_at` | `timestamptz` | `NOT NULL DEFAULT now()` |

**Constraints — aquí vive el art. X en la base de datos:**

```sql
-- FR-021: rango salarial coherente y moneda explícita
CONSTRAINT salary_range_valid
  CHECK (salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max),
CONSTRAINT salary_currency_required
  CHECK ((salary_min IS NULL AND salary_max IS NULL) OR salary_currency IS NOT NULL),
CONSTRAINT salary_currency_format
  CHECK (salary_currency IS NULL OR salary_currency ~ '^[A-Z]{3}$'),

-- Art. X / FR-023 / SC-001: `complete` es imposible sin una versión confirmada
CONSTRAINT complete_requires_version
  CHECK (state <> 'complete' OR current_version_id IS NOT NULL)
```

- El conjunto de monedas aceptadas (`MXN`, `USD`) se valida en Pydantic y es configurable; el `CHECK` de formato es la red de seguridad de la base.
- `has_unconfirmed_changes` **no existe como columna**: se deriva comparando hashes (R-08).
- `onboarding_step` **no existe como columna**: se deriva del estado (R-18).
- El perfil se crea de forma perezosa (`get_or_create`) en la primera subida **o** en la primera entrada manual, para que la captura manual guiada (FR-007) no necesite un flujo propio.

---

### `profile_entries` — entradas atómicas (FR-009 – FR-013, FR-015 – FR-018)

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | `uuid` | PK — **estable de por vida** (FR-010); es el futuro `source_id` del art. IV |
| `profile_id` | `uuid` | FK → `candidate_profiles.id` `ON DELETE CASCADE`, `NOT NULL` |
| `entry_type` | `entry_type` | `NOT NULL` |
| `origin` | `entry_origin` | `NOT NULL` |
| `content` | `jsonb` | `NOT NULL` — validado por unión discriminada de Pydantic |
| `content_language` | `char(2)` | `NULL` — ISO 639-1 del contenido (FR-012) |
| `is_complete` | `boolean` | `NOT NULL` — calculado por reglas, nunca por el modelo (FR-013) |
| `missing_fields` | `text[]` | `NOT NULL DEFAULT '{}'` — qué falta, para el aviso de US2 AC4 |
| `source_document_id` | `uuid` | FK → `documents.id` `ON DELETE SET NULL`, `NULL` si es `user_added` |
| `source_excerpt` | `text` | `NULL` — fragmento literal del CV del que salió (R-05) |
| `deleted_at` | `timestamptz` | `NULL` — borrado lógico (FR-017) |
| `created_at` / `updated_at` | `timestamptz` | `NOT NULL DEFAULT now()` |

**Constraints e índices:**

```sql
-- Coherencia de procedencia
CONSTRAINT seed_requires_document
  CHECK (origin <> 'cv_seed' OR source_document_id IS NOT NULL),
CONSTRAINT added_has_no_document
  CHECK (origin <> 'user_added' OR source_document_id IS NULL)

CREATE INDEX ix_entries_profile_alive ON profile_entries (profile_id, entry_type)
  WHERE deleted_at IS NULL;
CREATE INDEX ix_entries_content ON profile_entries USING gin (content);
```

- **Todas** las lecturas de la aplicación filtran `deleted_at IS NULL`. El índice parcial lo hace además eficiente.
- `ON DELETE SET NULL` sobre `source_document_id` **no** se usará en 006 —allí el documento conserva su registro y solo pierde el binario (006/FR-007)—, pero protege de un borrado accidental de documento sin arrastrar entradas.
- El GIN sobre `content` no es especulativo: la UI de revisión agrupa y filtra por tipo y la validación de duplicados de 007 consultará por campos del contenido.

**Contenido por tipo** (unión discriminada en `domain/entries.py`; todos los campos no garantizados son opcionales, R-05):

| `entry_type` | Campos de `content` |
|---|---|
| `experience` | `title`, `organization`, `start_date`, `end_date`, `is_current`, `location`, `description`, `highlights[]` |
| `achievement` | `description`, `metric`, `context`, `related_organization`, `occurred_at` |
| `education` | `institution`, `degree`, `field_of_study`, `start_date`, `end_date`, `status` |
| `skill` | `name`, `category`, `level`, `years_of_experience` |
| `certification` | `name`, `issuer`, `issued_at`, `expires_at`, `credential_id` |
| `language` | `name`, `level` (`basic`\|`intermediate`\|`advanced`\|`native`), `certification` |
| `project` | `name`, `description`, `role`, `technologies[]`, `url`, `start_date`, `end_date` |

Las fechas se modelan como `YYYY-MM` o `YYYY` en texto validado por patrón, no como `date`: los CVs rara vez traen día, y forzar un día concreto sería inventar precisión que el documento no tiene (art. IV).

---

### `documents` — CV maestro original (FR-003)

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | `uuid` | PK |
| `candidate_id` | `uuid` | FK → `candidates.id` `ON DELETE CASCADE`, `NOT NULL` |
| `kind` | `document_kind` | `NOT NULL` — determinado por firma de bytes, no por extensión (R-01) |
| `original_filename` | `text` | `NOT NULL` |
| `size_bytes` | `integer` | `NOT NULL`, `CHECK (size_bytes > 0 AND size_bytes <= 10485760)` |
| `sha256` | `text` | `NOT NULL` — hash del contenido en claro, para detectar re-subidas idénticas (lo usará 007) |
| `storage_key` | `text` | `NOT NULL` — clave del objeto cifrado |
| `encryption_key_wrapped` | `bytea` | `NOT NULL` — clave de datos envuelta (R-06) |
| `encryption_nonce` | `bytea` | `NOT NULL` |
| `encryption_key_version` | `smallint` | `NOT NULL DEFAULT 1` |
| `availability` | `document_availability` | `NOT NULL DEFAULT 'available'` — **gancho de 006** |
| `availability_changed_at` | `timestamptz` | `NULL` — **gancho de 006** |
| `uploaded_at` | `timestamptz` | `NOT NULL DEFAULT now()` |

- Índices: `(candidate_id, uploaded_at DESC)` para "el más reciente es el vigente".
- Las tres columnas de cifrado y el par `availability` / `availability_changed_at` están aquí por decisión deliberada: 006 solo tendrá que **añadir valores al enum**, no alterar la tabla ni retro-poblar filas.
- `storage_key` nunca se expone en ninguna respuesta de la API.

---

### `parse_jobs` — trabajo de procesamiento (FR-004, FR-008)

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | `uuid` | PK |
| `candidate_id` | `uuid` | FK → `candidates.id` `ON DELETE CASCADE`, `NOT NULL` (denormalizado a propósito: sostiene el índice de unicidad) |
| `document_id` | `uuid` | FK → `documents.id` `ON DELETE CASCADE`, `NOT NULL` |
| `status` | `parse_job_status` | `NOT NULL DEFAULT 'queued'` |
| `step` | `parse_job_step` | `NULL` |
| `progress_percent` | `smallint` | `NOT NULL DEFAULT 0`, `CHECK (0 <= progress_percent <= 100)` |
| `error_code` | `text` | `NULL` — código estable del catálogo de errores |
| `entries_created` | `integer` | `NOT NULL DEFAULT 0` |
| `truncated` | `boolean` | `NOT NULL DEFAULT false` — el texto superó `MAX_EXTRACTION_CHARS` (R-14) |
| `retry_of_job_id` | `uuid` | FK → `parse_jobs.id`, `NULL` |
| `started_at` / `finished_at` | `timestamptz` | `NULL` |
| `created_at` | `timestamptz` | `NOT NULL DEFAULT now()` |

```sql
-- Edge case "subida de un CV nuevo mientras otro está procesándose":
-- lo garantiza la base, no la lógica de aplicación
CREATE UNIQUE INDEX ux_parse_jobs_one_active
  ON parse_jobs (candidate_id)
  WHERE status IN ('queued', 'running');
```

- `error_code` guarda un **código**, nunca un mensaje con datos del documento (FR-031). El mensaje en español se resuelve en la capa de API desde el catálogo.
- No hay columna de mensaje de error libre, precisamente para que nadie meta ahí una traza con PII.

---

### `profile_versions` — instantánea inmutable (FR-025, FR-026, FR-028)

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | `uuid` | PK |
| `profile_id` | `uuid` | FK → `candidate_profiles.id` `ON DELETE CASCADE`, `NOT NULL` |
| `version_number` | `integer` | `NOT NULL` — monotónico por perfil, `UNIQUE (profile_id, version_number)` |
| `origin` | `version_origin` | `NOT NULL` — solo `confirmation` en 001 |
| `content` | `jsonb` | `NOT NULL` — `{ "objectives": {...}, "entries": [...] }` completo |
| `content_hash` | `text` | `NOT NULL` — SHA-256 de la serialización canónica |
| `created_at` | `timestamptz` | `NOT NULL DEFAULT now()` |

**Inmutabilidad exigible, no prometida:**

```sql
CREATE FUNCTION forbid_profile_version_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'profile_versions is append-only (FR-025)';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_profile_versions_immutable
  BEFORE UPDATE OR DELETE ON profile_versions
  FOR EACH ROW EXECUTE FUNCTION forbid_profile_version_mutation();
```

- El `DELETE` también se bloquea; la eliminación de cuenta de 006 lo hará por `ON DELETE CASCADE` desde `candidates`, que no dispara este trigger de fila... **atención**: sí lo dispara. 006 deberá deshabilitar el trigger dentro de su transacción de borrado o cambiarlo a `BEFORE UPDATE` únicamente. Se deja registrado aquí como nota para 006; en 001 no existe ningún camino de borrado de cuenta, así que el trigger completo es la opción segura.
- `version_number` se asigna con `SELECT coalesce(max(version_number), 0) + 1 ... FOR UPDATE` sobre el perfil, dentro de la misma transacción que la confirmación.
- El `content` embebe las entradas **completas**, no referencias: una versión debe poder leerse aunque una entrada se borre después (FR-026, "recuperar el contenido íntegro").

---

### `llm_call_logs` — observabilidad (art. VIII, R-13)

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | `uuid` | PK |
| `parse_job_id` | `uuid` | FK → `parse_jobs.id` `ON DELETE SET NULL`, `NULL` |
| `purpose` | `text` | `NOT NULL` — `classification` \| `extraction` |
| `model` | `text` | `NOT NULL` |
| `prompt_version` | `text` | `NOT NULL` |
| `input_tokens` / `output_tokens` | `integer` | `NOT NULL` |
| `estimated_cost_usd` | `numeric(10,6)` | `NOT NULL` |
| `latency_ms` | `integer` | `NOT NULL` |
| `attempt` | `smallint` | `NOT NULL DEFAULT 1` |
| `outcome` | `text` | `NOT NULL` — `ok` \| `schema_error` \| `provider_error` \| `timeout` |
| `created_at` | `timestamptz` | `NOT NULL DEFAULT now()` |

**Esta tabla no contiene PII por diseño**: ni prompts, ni respuestas, ni identificador de candidato. Cualquier PR que añada una columna con texto libre del documento viola el art. V.

---

## Reglas de negocio con su punto de aplicación

| Regla | FR | Dónde se aplica |
|---|---|---|
| Solo PDF/DOCX ≤ 10 MB, no corrupto | FR-001, FR-002 | Servicio (síncrono) + `CHECK` de `size_bytes` |
| Consentimiento antes de la primera subida | FR-030 | Servicio, consultando `privacy_consents` |
| Un solo procesamiento activo | edge case | Índice único parcial |
| Entradas sembradas en una sola transacción | FR-008 | `seeding_service` |
| `is_complete` calculado por reglas | FR-013 | `domain/completeness.py` |
| `cv_seed` → `user_edited` solo si cambia el contenido | FR-016, R-09 | `entry_service` |
| `id` de entrada estable ante edición | FR-010 | Ausencia de cualquier camino que lo reemplace + test |
| Rango salarial coherente | FR-021 | Pydantic (mensaje ES) + `CHECK` |
| Confirmación exige ≥ 1 entrada viva y objetivos obligatorios | FR-024 | `domain/confirmation.py` |
| `complete` solo por confirmación explícita | FR-023, art. X | `confirmation_service` (único escritor de `state`) + `CHECK complete_requires_version` |
| Consumidores externos leen la versión vigente | FR-028 | `version_service.get_current()`; ningún repositorio de entradas se expone fuera del onboarding |
| Cambios sin confirmar visibles y detallados | FR-029 | `content_hash` derivado + `domain/diff.py` |
| Acceso solo del propietario | FR-034 | `candidate_id` del token en toda firma de repositorio + tests de acceso cruzado |
| PII fuera de logs | FR-031 | Procesador de structlog + ausencia de columnas de texto libre en `parse_jobs` y `llm_call_logs` |

---

## Máquinas de estado

**Perfil** (FR-014, FR-023, FR-027):

```text
(inexistente) ──crear perezosamente──▶ draft ──POST /profile/confirm──▶ complete
                                        ▲                                  │
                                        └──── NO EXISTE ESTA TRANSICIÓN ───┘
```

Editar entradas u objetivos sobre `complete` **no** cambia el estado: genera cambios sin confirmar (FR-027). Confirmar de nuevo crea una versión nueva y `complete` se mantiene (FR-025, FR-029).

**Trabajo de parseo** (FR-004, FR-008):

```text
queued ──worker toma (UPDATE guarded)──▶ running ──┬──▶ succeeded   (terminal)
                                                    └──▶ failed ──POST /retry──▶ (nuevo job) queued
```

`succeeded` es terminal en 001: volver a procesar un documento ya procesado es reprocesamiento (006/FR-003) y entra por la fusión de 007. `POST /retry` sobre un trabajo que no está en `failed` devuelve `409`.

---

## Convención vinculante para embeddings (ADR-003)

En 001 **no se persiste ningún vector** (R-12). La primera migración sí ejecuta `CREATE EXTENSION IF NOT EXISTS vector`. Cuando una feature futura persista embeddings, queda obligada a:

1. Guardar `embedding_model` (`text`) y `embedding_dim` (`integer`) **junto a cada vector**, en la misma fila.
2. Permitir la convivencia de dos modelos durante una migración: tabla de embeddings separada con clave `(owner_id, embedding_model)`, no una columna `vector(N)` colgada de la entidad.
3. Obtener siempre las dimensiones del `EmbeddingsPort`, nunca de una constante literal en el código de la migración.

Motivo, textual del ADR-003: la dimensión del embedding se filtra al esquema y cambiar de proveedor exige re-embeber. Escribir la regla ahora es más barato que descubrirla con datos en producción.

---

## Compatibilidad con 006 y 007

Verificación explícita de que 001 no bloquea a las dos features que dependen de ella.

### Feature 006 — Ciclo de vida de los datos

| Necesidad de 006 | Estado en 001 |
|---|---|
| Estado de disponibilidad del binario con fecha (006/FR-011) | Columnas `availability` y `availability_changed_at` ya existen; 006 solo añade valores al enum |
| Entradas `cv_seed` sobreviven al borrado del archivo conservando `id` y origen (006/FR-007) | `profile_entries` no tiene FK obligatoria al documento en su ciclo de vida: `source_document_id` es anulable y el documento conserva su fila |
| Borrado del archivo solo si existe versión `confirmation` (006/FR-005) | `profile_versions.origin` ya distingue el origen; la comprobación es una consulta, no un cambio de esquema |
| Descarga del archivo original (006/FR-002) | Clave de cifrado y `storage_key` persistidos por documento; el `StoragePort` ya expone `get` |
| Reloj de retención por inactividad (006/FR-008) | **Requiere columna nueva** `last_activity_at` en `candidates`. 001 no la crea porque no la usa; es una migración aditiva trivial |
| Eliminación de cuenta borra perfil, entradas y versiones (006/FR-012) | `ON DELETE CASCADE` desde `candidates` en toda la cadena. **Nota**: el trigger de inmutabilidad de `profile_versions` bloquea el `DELETE`; 006 debe deshabilitarlo dentro de su transacción de borrado o restringirlo a `UPDATE` |

### Feature 007 — Fusión al re-subir

| Necesidad de 007 | Estado en 001 |
|---|---|
| Versión con origen `cv_merge` (007/FR-006) | Enum `version_origin` extensible con `ADD VALUE`; `current_version_id` ya permite que una versión exista sin ser vigente |
| Distinguir entradas tocadas por el candidato (007/FR-002, FR-004) | `origin` con los tres valores y la transición de R-09, que preserva `user_added` sin colapsarlo en `user_edited` |
| Punto de reversión al contenido exacto previo (007/SC-002) | `profile_versions.content` es el snapshot íntegro, no un diff |
| Criterio de equivalencia por tipo (007/FR-005) | `content` estructurado y tipado por tipo de entrada + índice GIN; la comparación tiene campos comparables, no texto plano |
| No resucitar entradas que el candidato borró | Borrado lógico con `deleted_at`: 007 puede consultarlas para no reintroducirlas |
| Un solo flujo de fusión activo por candidato (007, supuesto) | Mismo patrón de índice único parcial ya probado en `parse_jobs` |
| Entrada `merge_proposal` (007) | Tabla nueva de 007; no requiere tocar nada de 001 |

---

## Migración Alembic

Una sola migración `0001_candidate_onboarding`, reversible (DoD de la constitución):

**upgrade**: `CREATE EXTENSION citext` · `CREATE EXTENSION vector` · tipos enum · tablas en orden de dependencia (`candidates` → `privacy_consents`, `refresh_tokens`, `candidate_profiles` → `documents` → `parse_jobs` → `profile_entries` → `profile_versions` → FK diferida `candidate_profiles.current_version_id`) · índices · función y trigger de inmutabilidad · `llm_call_logs`.

**downgrade**: inverso exacto, incluidos trigger, función, tipos enum y —solo si nada más las usa— las extensiones. Se prueba en CI con `alembic upgrade head && alembic downgrade base && alembic upgrade head` sobre un Postgres real de testcontainers.

La FK `candidate_profiles.current_version_id` → `profile_versions.id` es circular con `profile_versions.profile_id`; se crea con `ALTER TABLE` posterior en la misma migración (`use_alter=True` en SQLAlchemy).
