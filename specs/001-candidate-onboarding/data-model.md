# Fase 1 — Modelo de datos

**Feature**: 001-candidate-onboarding · **Fecha**: 2026-08-11 · **Plan**: [plan.md](./plan.md) · **Decisiones**: [research.md](./research.md)

Base: Postgres 16 + pgvector. ORM: SQLAlchemy 2.0 tipado (`Mapped[...]`). Migraciones: Alembic, reversibles y tolerantes a saltos de varias versiones (ADR-009). Todos los identificadores de tabla, columna y valor de enum en inglés (art. IX).

**Dos convenciones transversales, ambas verificadas por tests:**

1. **Toda consulta de repositorio recibe `candidate_id` explícito**, resuelto por la capa de API desde configuración local. Ningún endpoint lo acepta del cliente (FR-003, FR-049, ADR-008). Hoy solo existe un valor posible; los tests de repositorio verifican el filtrado **con dos** `candidate_id` distintos para que la disciplina sea ejecutable y no un acuerdo verbal.
2. **Ninguna tabla persiste credenciales.** API keys y App Password viven en configuración local (FR-008, FR-013). Lo único que se persiste de ellas es un `credential_fingerprint` —HMAC truncado, no la llave ni un fragmento suyo (research R-24)— que sirve para invalidar un preflight cuando la credencial cambia.

---

## Diagrama de relaciones

```text
candidates ──1:1── candidate_profiles ──1:N── profile_entries
    │                     │                        │
    │                     └──1:N── profile_versions │
    │                                  ▲            │
    │                     current_version_id ───────┘ (FK opcional)
    │
    ├──1:1── setup_state                    (primera ejecución: acuse + paso de correo)
    ├──1:N── provider_configurations        (una fila por capacidad: generation | embeddings)
    └──1:N── documents ──1:N── parse_jobs
                  ▲
                  └── profile_entries.source_document_id (FK opcional)

llm_call_logs (sin FK a datos personales; referencia parse_job_id)
```

Nueve tablas. Ninguna especulativa: durante el diseño se descartaron una tabla `onboarding_steps` (el paso se **deriva**, research R-18), una `profile_entry_embeddings` (sin consumidor en 001, research R-12), una bandera persistida `has_unconfirmed_changes` (se deriva del hash, research R-08) y una tabla de credenciales (viven en configuración, research R-21). Respecto del diseño anterior desaparecen `privacy_consents` y `refresh_tokens`.

---

## Enums

Se declaran como tipos nativos de Postgres para que la base rechace valores fuera de dominio, y como `enum.StrEnum` en `domain/enums.py`.

| Enum | Valores | Notas |
|---|---|---|
| `capability` | `generation`, `embeddings` | ADR-011. Las dos se configuran de forma **independiente**; ninguna condiciona a la otra (FR-004) |
| `preflight_result` | `verified`, `credential_rejected`, `capability_unverified`, `quota_exceeded` | Los **cuatro** resultados que FR-007 exige distinguir. "Sin verificar todavía" no es un valor: es la ausencia de fila |
| `email_step_status` | `pending`, `linked`, `skipped` | FR-011, FR-015. `skipped` es un estado tan terminal como `linked` |
| `profile_state` | `draft`, `complete` | Transición única y unidireccional (FR-042: nunca vuelve a `draft`) |
| `entry_type` | `experience`, `achievement`, `education`, `skill`, `certification`, `language`, `project` | ADR-005 prevé `star_story`; **no** se añade en 001 (art. VII). Añadirlo es un `ALTER TYPE ... ADD VALUE` sin migración de datos |
| `entry_origin` | `cv_seed`, `user_added`, `user_edited` | FR-026. Transiciones en research R-09 |
| `version_origin` | `confirmation` | La feature 007 añadirá `cv_merge`. El enum nace con un solo valor **a propósito**: así ningún camino de 001 puede producir otro origen (FR-040) |
| `parse_job_status` | `queued`, `running`, `succeeded`, `failed` | FR-019 |
| `parse_job_step` | `extracting_text`, `classifying`, `extracting_entries`, `persisting` | Para el progreso legible |
| `document_kind` | `pdf`, `docx` | FR-016 |
| `document_availability` | `available` | La feature 006 añadirá `deleted_by_candidate` y `purged_by_retention`. La columna existe desde 001 para que 006 no tenga que retro-poblarla |
| `remote_preference` | `onsite`, `hybrid`, `remote`, `any` | FR-035 |

---

## Tablas

### `candidates`

Propietario de los datos de la instalación. **No es una cuenta**: no hay correo, ni contraseña, ni verificación, ni sesión (FR-003, ADR-008). Existe para que `candidate_id` sea una columna real desde la primera migración y todas las queries nazcan acotadas por propietario.

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | `uuid` | PK, `gen_random_uuid()` |
| `created_at` | `timestamptz` | `NOT NULL DEFAULT now()` |

- **La migración inicial siembra exactamente una fila.** Su `id` es el `candidate_id` local fijo de la instalación, que la aplicación resuelve desde configuración (research R-11). Decidir su valor no es alcance de esta spec: la migración lo genera y lo deja disponible para la configuración.
- Una versión hospedada futura añade aquí las columnas de cuenta **encima** de este modelo, sin reescribir repositorios (ADR-008). El diseño de referencia sigue siendo el ADR-001, marcado Superseded.
- **No** se crea la extensión `citext`: existía solo para la unicidad del correo, que ya no hay.

---

### `setup_state` — estado de la primera ejecución (FR-001, FR-002, FR-011 – FR-015)

Fila única por instalación. Registra los hechos del wizard, **nunca el puntero "voy en el paso 2"**: el paso pendiente se deriva de estos hechos (research R-18).

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | `uuid` | PK |
| `candidate_id` | `uuid` | FK → `candidates.id` `ON DELETE CASCADE`, `NOT NULL`, **`UNIQUE`** (1:1) |
| `disclosure_acknowledged_at` | `timestamptz` | `NULL` mientras no se acuse (FR-002) |
| `disclosure_version` | `text` | `NULL` — versión del texto de divulgación **efectivamente acusado** (FR-001, research R-29) |
| `email_step_status` | `email_step_status` | `NOT NULL DEFAULT 'pending'` |
| `email_label` | `text` | `NULL` — etiqueta designada a leer (FR-013). **Nunca** la App Password |
| `email_linked_at` | `timestamptz` | `NULL` |
| `created_at` / `updated_at` | `timestamptz` | `NOT NULL DEFAULT now()` |

```sql
-- El acuse es un hecho con fecha y versión: o están los dos, o no está ninguno
CONSTRAINT disclosure_ack_complete
  CHECK ((disclosure_acknowledged_at IS NULL) = (disclosure_version IS NULL)),

-- Vincular exige etiqueta designada y fecha; omitir no deja rastro de configuración
CONSTRAINT email_linked_requires_label
  CHECK (email_step_status <> 'linked'
         OR (email_label IS NOT NULL AND email_linked_at IS NOT NULL)),
CONSTRAINT email_skipped_has_no_config
  CHECK (email_step_status <> 'skipped'
         OR (email_label IS NULL AND email_linked_at IS NULL))
```

- **NEVER contiene credenciales** (FR-008, FR-013): ni API keys, ni la App Password, ni fragmentos de ellas.
- Guardar `disclosure_version` junto a la fecha es lo que permite que un cambio futuro en qué se envía al proveedor exija un acuse nuevo, en vez de quedar cubierto por uno viejo que decía otra cosa. Es también lo que sostiene FR-048: habilitar material real para evals no puede colarse modificando este texto, porque queda registrado cuál se aceptó.
- La primera ejecución se da por concluida (FR-015) cuando hay acuse, hay proveedor de **generación** resuelto en `provider_configurations` y `email_step_status <> 'pending'`. Es una consulta, no una columna.

---

### `provider_configurations` — proveedores y su preflight (FR-004 – FR-010)

Una fila **por capacidad**. Que sean filas y no columnas es lo que hace que generación y embeddings sean de verdad independientes: se configuran, se verifican y se invalidan por separado (ADR-011).

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | `uuid` | PK |
| `candidate_id` | `uuid` | FK → `candidates.id` `ON DELETE CASCADE`, `NOT NULL` |
| `capability` | `capability` | `NOT NULL` — `UNIQUE (candidate_id, capability)` |
| `provider` | `text` | `NOT NULL` — identificador del catálogo cerrado (FR-004, FR-009) |
| `model` | `text` | `NOT NULL` — nombre de modelo **efectivamente verificado**; su valor por defecto viene de configuración, nunca de una constante (research R-21) |
| `preflight_result` | `preflight_result` | `NOT NULL` (FR-007) |
| `preflight_at` | `timestamptz` | `NOT NULL` |
| `credential_fingerprint` | `text` | `NOT NULL` — HMAC-SHA256 truncado de la credencial con clave derivada local. **No es la credencial ni un fragmento suyo** (research R-24) |
| `embedding_dim` | `integer` | `NULL` — dimensión del vector devuelta por el preflight (FR-007.2). Obligatoria si `capability='embeddings'` y `preflight_result='verified'` |
| `degradation_acknowledged_at` | `timestamptz` | `NULL` — acuse específico de la degradación (FR-007.3) |
| `created_at` / `updated_at` | `timestamptz` | `NOT NULL DEFAULT now()` |

```sql
-- FR-007.2: un embeddings verificado SIEMPRE tiene su dimensión registrada
CONSTRAINT embeddings_verified_has_dim
  CHECK (NOT (capability = 'embeddings' AND preflight_result = 'verified')
         OR embedding_dim IS NOT NULL),

-- FR-007.3: avanzar con una capacidad sin garantía EXIGE acuse específico.
-- Sin acuse, la fila existe pero no habilita nada: la degradación silenciosa
-- se vuelve imposible de representar en la base.
CONSTRAINT degradation_ack_only_when_unverified
  CHECK (degradation_acknowledged_at IS NULL
         OR preflight_result = 'capability_unverified'),

-- Solo estos dos resultados dejan usar la capacidad; los otros dos la dejan
-- explícitamente sin verificar (FR-007.1, FR-007.4)
CONSTRAINT dim_only_when_embeddings
  CHECK (embedding_dim IS NULL OR capability = 'embeddings')
```

- **No hay columna de credencial, ni cifrada ni de ningún otro modo.** La llave vive en configuración local y se lee al usar el puerto (FR-008).
- El gate de entrada al onboarding (FR-010) es una consulta sobre esta tabla: existe fila con `capability='generation'` y `preflight_result IN ('verified','capability_unverified')`, y si es `capability_unverified`, con `degradation_acknowledged_at IS NOT NULL`. **La ausencia de fila de `embeddings` nunca bloquea**: degrada funciones que quedan fuera de esta feature.
- `provider` es `text` y no un enum de Postgres a propósito: la lista cerrada vive en la matriz de capacidades del código (research R-22), que es donde puede llevar `verified_on`, dimensión y costo. Un enum en la base obligaría a una migración para añadir un proveedor cuya verificación es un dato, no un cambio de esquema.
- Cambiar de credencial invalida la fila: el `credential_fingerprint` deja de coincidir y el preflight vuelve a exigirse (SC-012).

---

### `candidate_profiles` — perfil maestro (FR-029, FR-035 – FR-044, ADR-005)

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | `uuid` | PK |
| `candidate_id` | `uuid` | FK → `candidates.id` `ON DELETE CASCADE`, `NOT NULL`, **`UNIQUE`** (1:1) |
| `state` | `profile_state` | `NOT NULL DEFAULT 'draft'` |
| `current_version_id` | `uuid` | FK → `profile_versions.id`, `NULL` mientras no haya confirmación |
| `last_confirmed_at` | `timestamptz` | `NULL` |
| **Objetivos (FR-035)** | | |
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
-- FR-036: rango salarial coherente y moneda explícita
CONSTRAINT salary_range_valid
  CHECK (salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max),
CONSTRAINT salary_currency_required
  CHECK ((salary_min IS NULL AND salary_max IS NULL) OR salary_currency IS NOT NULL),
CONSTRAINT salary_currency_format
  CHECK (salary_currency IS NULL OR salary_currency ~ '^[A-Z]{3}$'),

-- Art. X / FR-038 / SC-001: `complete` es imposible sin una versión confirmada
CONSTRAINT complete_requires_version
  CHECK (state <> 'complete' OR current_version_id IS NOT NULL)
```

- El conjunto de monedas aceptadas (`MXN`, `USD`) se valida en Pydantic y es configurable; el `CHECK` de formato es la red de seguridad de la base.
- `has_unconfirmed_changes` **no existe como columna**: se deriva comparando hashes (research R-08).
- `onboarding_step` **no existe como columna**: se deriva del estado (research R-18).
- El perfil se crea de forma perezosa (`get_or_create`) en la primera subida **o** en la primera entrada manual, para que la captura manual guiada (FR-022) no necesite un flujo propio.

---

### `profile_entries` — entradas atómicas (FR-024 – FR-028, FR-030 – FR-033)

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | `uuid` | PK — **estable de por vida** (FR-025); es el futuro `source_id` del art. IV |
| `profile_id` | `uuid` | FK → `candidate_profiles.id` `ON DELETE CASCADE`, `NOT NULL` |
| `entry_type` | `entry_type` | `NOT NULL` |
| `origin` | `entry_origin` | `NOT NULL` |
| `content` | `jsonb` | `NOT NULL` — validado por unión discriminada de Pydantic |
| `content_language` | `char(2)` | `NULL` — ISO 639-1 del contenido (FR-027) |
| `is_complete` | `boolean` | `NOT NULL` — calculado por reglas, nunca por el modelo (FR-028) |
| `missing_fields` | `text[]` | `NOT NULL DEFAULT '{}'` — qué falta, para el aviso de US3 AC4 |
| `source_document_id` | `uuid` | FK → `documents.id` `ON DELETE SET NULL`, `NULL` si es `user_added` |
| `source_excerpt` | `text` | `NULL` — fragmento literal del CV del que salió (research R-05) |
| `deleted_at` | `timestamptz` | `NULL` — borrado lógico (FR-032) |
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
- `ON DELETE SET NULL` sobre `source_document_id` **no** se usará en 006 —allí el documento conserva su registro y solo pierde el binario—, pero protege de un borrado accidental de documento sin arrastrar entradas.
- El GIN sobre `content` no es especulativo: la UI de revisión agrupa y filtra por tipo, y la validación de duplicados de 007 consultará por campos del contenido.

**Contenido por tipo** (unión discriminada en `domain/entries.py`; todos los campos no garantizados son opcionales, research R-05):

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

### `documents` — CV maestro original (FR-018)

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | `uuid` | PK |
| `candidate_id` | `uuid` | FK → `candidates.id` `ON DELETE CASCADE`, `NOT NULL` |
| `kind` | `document_kind` | `NOT NULL` — determinado por firma de bytes, no por extensión (research R-01) |
| `original_filename` | `text` | `NOT NULL` |
| `size_bytes` | `integer` | `NOT NULL`, `CHECK (size_bytes > 0 AND size_bytes <= 10485760)` |
| `sha256` | `text` | `NOT NULL` — hash del contenido, para detectar re-subidas idénticas (lo usará 007) |
| `storage_key` | `text` | `NOT NULL` — clave del archivo en el directorio de datos local |
| `availability` | `document_availability` | `NOT NULL DEFAULT 'available'` — **gancho de 006** |
| `availability_changed_at` | `timestamptz` | `NULL` — **gancho de 006** |
| `uploaded_at` | `timestamptz` | `NOT NULL DEFAULT now()` |

- Índice: `(candidate_id, uploaded_at DESC)` para "el más reciente es el vigente".
- **Sin columnas de cifrado** (ADR-007): desaparecen `encryption_key_wrapped`, `encryption_nonce` y `encryption_key_version` del diseño anterior. Los archivos se guardan en claro y el riesgo se divulga en el paso 0 del wizard (FR-001d) y en el README.
- `storage_key` **nunca se expone** en ninguna respuesta de la API ni en ningún mensaje de error: un `FileNotFoundError: /data/...` en la UI es un bug de producto (roadmap §11.5).
- El par `availability` / `availability_changed_at` está aquí por decisión deliberada: 006 solo tendrá que **añadir valores al enum**, no alterar la tabla ni retro-poblar filas.
- Si el usuario mueve o borra el directorio de datos, la fila sobrevive y el `StoragePort.exists` lo detecta; el error es `STORAGE_UNAVAILABLE` y el mensaje aclara que el perfil sigue intacto.

---

### `parse_jobs` — trabajo de procesamiento (FR-019, FR-023)

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
| `truncated` | `boolean` | `NOT NULL DEFAULT false` — el texto superó `MAX_EXTRACTION_CHARS` (research R-14) |
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

- `error_code` guarda un **código**, nunca un mensaje con datos del documento (FR-045). El mensaje en español se resuelve en la capa de API desde el catálogo.
- **No hay columna de mensaje de error libre**, precisamente para que nadie meta ahí una traza con PII.
- El **reaper de arranque** (research R-07) marca como `failed` con código reintentable los trabajos que quedaron en `running` sin worker vivo: apagar el equipo a media ejecución es un escenario ordinario en una instalación local.

---

### `profile_versions` — instantánea inmutable (FR-040, FR-041, FR-043)

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
  RAISE EXCEPTION 'profile_versions is append-only (FR-040)';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_profile_versions_immutable
  BEFORE UPDATE OR DELETE ON profile_versions
  FOR EACH ROW EXECUTE FUNCTION forbid_profile_version_mutation();
```

- El trigger bloquea también el `DELETE`, **incluido el que llega por `ON DELETE CASCADE`**. En 001 no existe ningún camino de borrado, así que la forma completa es la segura. La feature 006, que sí borra, deberá deshabilitarlo dentro de su transacción o restringirlo a `UPDATE`. Queda registrado aquí como nota para 006.
- `version_number` se asigna con `SELECT coalesce(max(version_number), 0) + 1 ... FOR UPDATE` sobre el perfil, dentro de la misma transacción que la confirmación.
- El `content` embebe las entradas **completas**, no referencias: una versión debe poder leerse aunque una entrada se borre después (FR-041, "recuperar el contenido íntegro").

---

### `llm_call_logs` — observabilidad (art. VIII, FR-046, research R-13)

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | `uuid` | PK |
| `parse_job_id` | `uuid` | FK → `parse_jobs.id` `ON DELETE SET NULL`, `NULL` |
| `purpose` | `text` | `NOT NULL` — `classification` \| `extraction` \| `preflight` |
| `capability` | `capability` | `NOT NULL` — permite separar el costo de generación del de embeddings (FR-005, roadmap §11.3) |
| `model` | `text` | `NOT NULL` |
| `prompt_version` | `text` | `NOT NULL` |
| `input_tokens` / `output_tokens` | `integer` | `NOT NULL` |
| `estimated_cost_usd` | `numeric(10,6)` | `NOT NULL` |
| `latency_ms` | `integer` | `NOT NULL` |
| `attempt` | `smallint` | `NOT NULL DEFAULT 1` |
| `outcome` | `text` | `NOT NULL` — `ok` \| `schema_error` \| `provider_error` \| `timeout` |
| `created_at` | `timestamptz` | `NOT NULL DEFAULT now()` |

**Esta tabla no contiene PII ni credenciales por diseño**: ni prompts, ni respuestas, ni identificador de candidato, ni nombre de proveedor en texto libre. Cualquier PR que añada una columna con texto libre del documento viola el art. V. Es además el sustrato del "costo real acumulado" del roadmap §11.3, que llegará en otra feature.

---

## Reglas de negocio con su punto de aplicación

| Regla | FR | Dónde se aplica |
|---|---|---|
| Acuse de divulgación antes de cualquier subida, por cualquier vía | FR-002, SC-011 | Servicio, consultando `setup_state` — gate de **servidor**, no del guard de la SPA |
| Generación y embeddings se configuran de forma independiente | FR-004 | `UNIQUE (candidate_id, capability)`: dos filas, ninguna condiciona a la otra |
| Costo estimado mostrado **antes** de pedir la llave | FR-005 | `provider_catalog_service`, desde el catálogo declarativo (research R-27) |
| Preflight al guardar cada credencial, nunca diferido | FR-006, SC-012 | `preflight_service` + `credential_fingerprint` que invalida al rotar la llave |
| Los cuatro resultados de preflight se distinguen | FR-007 | Enum `preflight_result` + tipo suma en el dominio |
| Avanzar con capacidad sin garantía exige acuse específico | FR-007.3, SC-016 | `CHECK degradation_ack_only_when_unverified` + servicio |
| Credenciales fuera de la base de datos | FR-008, FR-013, SC-013 | Ausencia de columna. `SecretStr` en configuración + redactor de structlog |
| Solo se ofrecen proveedores con verificación registrada | FR-009 | Matriz de capacidades con `verified_on` (research R-22) |
| Sin proveedor de generación resuelto no hay onboarding | FR-010 | Consulta sobre `provider_configurations` en el servicio de documentos |
| Solo PDF/DOCX ≤ 10 MB, no corrupto | FR-016, FR-017 | Servicio (síncrono) + `CHECK` de `size_bytes` |
| Un solo procesamiento activo | edge case | Índice único parcial |
| Entradas sembradas en una sola transacción | FR-023 | `seeding_service` |
| `is_complete` calculado por reglas | FR-028 | `domain/completeness.py` |
| `cv_seed` → `user_edited` solo si cambia el contenido | FR-031, research R-09 | `entry_service` |
| `id` de entrada estable ante edición | FR-025 | Ausencia de cualquier camino que lo reemplace + test |
| Rango salarial coherente | FR-036 | Pydantic (mensaje ES) + `CHECK` |
| Confirmación exige ≥ 1 entrada viva y objetivos obligatorios | FR-039 | `domain/confirmation.py` |
| `complete` solo por confirmación explícita | FR-038, art. X | `confirmation_service` (único escritor de `state`) + `CHECK complete_requires_version` |
| Consumidores externos leen la versión vigente | FR-043 | `version_service.get_current()`; ningún repositorio de entradas se expone fuera del onboarding |
| Cambios sin confirmar visibles y detallados | FR-044 | `content_hash` derivado + `domain/diff.py` |
| Toda consulta acotada al `candidate_id` de la instalación | FR-049 | `candidate_id` explícito en toda firma de repositorio + tests con **dos** ids |
| PII fuera de logs y trazas | FR-045, FR-046 | Procesador de structlog + ausencia de columnas de texto libre en `parse_jobs` y `llm_call_logs` |

---

## Máquinas de estado

**Primera ejecución** (FR-014, FR-015) — derivada, no persistida como puntero:

```text
disclosure ──acuse──▶ providers ──generación resuelta──▶ email ──vincula|omite──▶ (concluida)
     ▲                    ▲                                 ▲
     └── se retoma exactamente aquí al reabrir, sin volver a pedir lo ya resuelto ──┘
```

Rotar una credencial fuera de la app invalida el preflight de esa capacidad (`credential_fingerprint` deja de coincidir) y el wizard vuelve a `providers` **solo para esa capacidad**. No se pierde el acuse ni la otra configuración.

**Perfil** (FR-029, FR-038, FR-042):

```text
(inexistente) ──crear perezosamente──▶ draft ──POST /profile/confirm──▶ complete
                                        ▲                                  │
                                        └──── NO EXISTE ESTA TRANSICIÓN ───┘
```

Editar entradas u objetivos sobre `complete` **no** cambia el estado: genera cambios sin confirmar (FR-042). Confirmar de nuevo crea una versión nueva y `complete` se mantiene (FR-040, FR-044).

**Trabajo de parseo** (FR-019, FR-023):

```text
queued ──worker toma (UPDATE guarded)──▶ running ──┬──▶ succeeded   (terminal)
                                                    └──▶ failed ──POST /retry──▶ (nuevo job) queued
                                          ▲
                    reaper de arranque ───┘  (running huérfano → failed reintentable)
```

`succeeded` es terminal en 001: volver a procesar un documento ya procesado es reprocesamiento y entra por la fusión de 007. `POST /retry` sobre un trabajo que no está en `failed` devuelve `409`.

---

## Convención vinculante para embeddings (ADR-003, ADR-011)

En 001 **no se persiste ningún vector** (research R-12); sí se verifica la capacidad y se registra su dimensión en `provider_configurations.embedding_dim`. La primera migración ejecuta `CREATE EXTENSION IF NOT EXISTS vector`. Cuando una feature futura persista embeddings, queda obligada a:

1. Guardar `embedding_model` (`text`) y `embedding_dim` (`integer`) **junto a cada vector**, en la misma fila.
2. Permitir la convivencia de dos modelos durante una migración: tabla de embeddings separada con clave `(owner_id, embedding_model)`, no una columna `vector(N)` colgada de la entidad.
3. Obtener siempre las dimensiones del `EmbeddingsPort`, nunca de una constante literal en el código de la migración.

Motivo, textual del ADR-003: la dimensión del embedding se filtra al esquema y cambiar de proveedor exige re-embeber. Con el ADR-011 eso deja de ser una migración del proyecto y pasa a ser **una acción del usuario** —cambiar su proveedor de embeddings desde Ajustes—, así que la UI deberá advertirlo **antes** de permitir el cambio y ofrecer el reprocesamiento. Esa pantalla queda fuera de 001; la regla que la hace posible se escribe aquí.

---

## Compatibilidad con 006 y 007

Verificación explícita de que 001 no bloquea a las dos features que dependen de ella. **Ninguna de las dos se implementa aquí**: lo que sigue son ganchos, no funcionalidad.

### Feature 006 — Ciclo de vida de los datos

| Necesidad de 006 | Estado en 001 |
|---|---|
| Estado de disponibilidad del binario con fecha | Columnas `availability` y `availability_changed_at` ya existen; 006 solo añade valores al enum |
| Entradas `cv_seed` sobreviven al borrado del archivo conservando `id` y origen | `source_document_id` es anulable y el documento conserva su fila; el ciclo de vida del binario no arrastra las entradas |
| Borrado del archivo solo si existe versión `confirmation` | `profile_versions.origin` ya distingue el origen; la comprobación es una consulta, no un cambio de esquema |
| Exportación de los datos en formato consultable | `profile_versions.content` es el snapshot íntegro y `profile_entries` está estructurado por tipo: la exportación es una lectura |
| Descarga del archivo original | `storage_key` persistido y `StoragePort.get` disponible. **Sin claves de cifrado que gestionar** (ADR-007): es una diferencia respecto del diseño anterior |
| Reloj de retención por inactividad de la **instalación** | **Requiere columna nueva** `last_activity_at` en `candidates`. 001 no la crea porque no la usa; es una migración aditiva trivial |
| Borrado completo de la instalación | `ON DELETE CASCADE` desde `candidates` en toda la cadena. **Nota**: el trigger de inmutabilidad de `profile_versions` bloquea ese `DELETE`; 006 debe deshabilitarlo dentro de su transacción o restringirlo a `UPDATE` |
| Eliminación de cuenta y aviso previo por correo | **Ya no aplican**: sin cuentas (ADR-008) y sin servidor que envíe correo (ADR-009). Desinstalar es borrar el directorio de datos |

### Feature 007 — Fusión al re-subir

| Necesidad de 007 | Estado en 001 |
|---|---|
| Versión con origen `cv_merge` | Enum `version_origin` extensible con `ADD VALUE`; `current_version_id` ya permite que una versión exista sin ser vigente |
| Distinguir entradas tocadas por el candidato | `origin` con los tres valores y la transición de research R-09, que preserva `user_added` sin colapsarlo en `user_edited` |
| Punto de reversión al contenido exacto previo | `profile_versions.content` es el snapshot íntegro, no un diff |
| Criterio de equivalencia por tipo | `content` estructurado y tipado por tipo de entrada + índice GIN: la comparación tiene campos comparables, no texto plano |
| Detectar re-subida idéntica | `documents.sha256` ya persistido |
| No resucitar entradas que el candidato borró | Borrado lógico con `deleted_at`: 007 puede consultarlas para no reintroducirlas |
| Un solo flujo de fusión activo | Mismo patrón de índice único parcial ya probado en `parse_jobs` |
| Entrada `merge_proposal` | Tabla nueva de 007; no requiere tocar nada de 001 |

---

## Migración Alembic

Una sola migración `0001_candidate_onboarding`, reversible (DoD de la constitución) y **aplicada automáticamente al arranque** por el entrypoint del contenedor `api` (roadmap §11.1, research R-20).

**upgrade**: `CREATE EXTENSION vector` · tipos enum · tablas en orden de dependencia (`candidates` → `setup_state`, `provider_configurations`, `candidate_profiles` → `documents` → `parse_jobs` → `profile_entries` → `profile_versions` → FK diferida `candidate_profiles.current_version_id`) · índices · función y trigger de inmutabilidad · `llm_call_logs` · **seed de la fila única de `candidates`** con el `candidate_id` local de la instalación.

**downgrade**: inverso exacto, incluidos trigger, función, tipos enum y —solo si nada más la usa— la extensión. Se prueba en CI con `alembic upgrade head && alembic downgrade base && alembic upgrade head` sobre un Postgres real de testcontainers.

**Tolerancia a saltos de varias versiones** (ADR-009): habrá instalaciones meses atrasadas, porque actualizar depende del usuario (`git pull`). Una migración que solo funcione desde la versión inmediata anterior es un bug, y probar el salto largo es parte de la release. En 001 esto todavía es trivial —es la primera migración—, pero la convención se establece aquí: nada de migraciones que dependan de datos escritos por una versión intermedia concreta.

La FK `candidate_profiles.current_version_id` → `profile_versions.id` es circular con `profile_versions.profile_id`; se crea con `ALTER TABLE` posterior en la misma migración (`use_alter=True` en SQLAlchemy).

**No se crea la extensión `citext`**: existía solo para la unicidad del correo de las cuentas, que ya no hay (ADR-008).
