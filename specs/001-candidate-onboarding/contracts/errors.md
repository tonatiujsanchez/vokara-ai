# Catálogo de errores

**Feature**: 001-candidate-onboarding · **Fecha**: 2026-08-10

Contrato: toda respuesta de error tiene la forma `{ "code", "message", "details"? }`.

- **`code`** — identificador estable en inglés (art. IX: identificadores en inglés). Es lo único de lo que el frontend depende para decidir comportamiento.
- **`message`** — texto accionable en español, resuelto en el backend desde este catálogo. Es la fuente única de verdad del texto: el frontend **no** mantiene su propia tabla de mensajes.
- **`details`** — objeto estructurado opcional (campos inválidos, bloqueadores de confirmación, límites).

Regla no negociable (FR-031, art. V): **ningún mensaje reproduce contenido del documento ni datos personales**. Ni nombres, ni fragmentos del CV, ni rutas de almacenamiento. Los mensajes son plantillas fijas; los únicos valores interpolados son límites y formatos configurados por el sistema.

---

## Subida y validación del archivo — FR-002, SC-008

| `code` | HTTP | Mensaje en español | Cuándo |
|---|---|---|---|
| `FILE_TOO_LARGE` | 400 | «El archivo pesa más de 10 MB. Sube una versión más ligera de tu CV.» | Tamaño por encima de `MAX_UPLOAD_BYTES`; se detecta por cabecera y por corte del stream |
| `UNSUPPORTED_FILE_TYPE` | 400 | «Solo aceptamos PDF y DOCX. Convierte tu CV a alguno de esos formatos e inténtalo de nuevo.» | La firma de bytes no corresponde a PDF ni a DOCX, sea cual sea la extensión |
| `DOCUMENT_CORRUPT` | 400 | «No pudimos abrir el archivo: parece estar dañado. Vuelve a exportarlo desde tu editor e inténtalo otra vez.» | pypdf o python-docx no logran abrirlo |
| `CONSENT_REQUIRED` | 409 | «Antes de subir tu CV necesitamos que aceptes el aviso de privacidad.» | No hay consentimiento para la versión vigente (FR-030) |
| `PARSE_JOB_ALREADY_ACTIVE` | 409 | «Ya estamos procesando un CV tuyo. Espera a que termine para subir otro.» | Índice único parcial sobre `parse_jobs` |
| `PROFILE_ALREADY_SEEDED` | 409 | «Ya tienes un perfil creado a partir de un CV. Volver a subir un CV llegará en una versión próxima.» | Reservado: re-subida con perfil sembrado es la feature 007 |

---

## Procesamiento — FR-004 – FR-007, SC-009

Estos códigos viajan en `parse_job.error_code` (estado `failed`), no como respuesta HTTP de la subida: el archivo ya fue aceptado.

| `code` | Mensaje en español | Cuándo | `is_retryable` |
|---|---|---|---|
| `PDF_WITHOUT_TEXT_LAYER` | «Tu PDF no tiene texto seleccionable: parece un documento escaneado. Por ahora no procesamos escaneos, pero puedes crear tu perfil paso a paso y te guiamos.» | Heurística de densidad de caracteres (research R-03) | No — el reintento daría el mismo resultado |
| `DOCUMENT_NOT_A_RESUME` | «Este documento no parece un CV. Revisa que hayas subido el archivo correcto.» | Clasificador con `is_resume = false` (FR-005) | No |
| `DOCUMENT_TOO_SPARSE` | «Encontramos muy poca información en tu CV. Puedes completar tu perfil paso a paso y te guiamos.» | Menos de `MIN_SEEDED_ENTRIES` entradas extraídas | No |
| `EXTRACTION_FAILED` | «Algo falló al procesar tu CV. Puedes intentarlo de nuevo; no perderás lo que ya hayas escrito.» | Error del proveedor LLM tras agotar reintentos, o salida que no valida | **Sí** (FR-008) |
| `STORAGE_UNAVAILABLE` | «No pudimos leer tu archivo en este momento. Inténtalo de nuevo en unos minutos.» | Fallo del `StoragePort` | **Sí** |
| `INTERNAL_ERROR` | «Ocurrió un error inesperado. Inténtalo de nuevo; si persiste, escríbenos.» | Cualquier excepción no clasificada | **Sí** |

Los tres primeros encaminan a la **captura manual guiada** (FR-007, SC-010): el mensaje va acompañado de esa acción en la UI, de modo que el candidato nunca queda sin salida.

| `code` | HTTP | Mensaje | Cuándo |
|---|---|---|---|
| `PARSE_JOB_NOT_RETRYABLE` | 409 | «Este procesamiento no se puede reintentar.» | `POST /parse-jobs/{id}/retry` sobre un trabajo que no está en `failed` |

---

## Perfil, entradas y objetivos — FR-016 – FR-022

| `code` | HTTP | Mensaje en español | Cuándo |
|---|---|---|---|
| `VALIDATION_ERROR` | 422 | «Revisa los datos: hay campos con errores.» + `details.fields` | Fallo genérico de Pydantic; `details.fields` lleva el error por campo, en español |
| `SALARY_RANGE_INVALID` | 422 | «El salario mínimo no puede ser mayor que el máximo.» | FR-021 |
| `SALARY_CURRENCY_REQUIRED` | 422 | «Indica la moneda de tu expectativa salarial.» | Hay valor salarial sin moneda (FR-021) |
| `UNSUPPORTED_CURRENCY` | 422 | «Por ahora solo manejamos pesos mexicanos (MXN) y dólares (USD).» | Moneda fuera del conjunto configurado |
| `ENTRY_CONTENT_EMPTY` | 422 | «La entrada está vacía: escribe al menos un dato antes de guardarla.» | Contenido sin ningún campo con valor |
| `ENTRY_TYPE_MISMATCH` | 422 | «El tipo de la entrada no coincide con su contenido.» | `entry_type` ≠ discriminador `kind` del contenido |
| `ENTRY_NOT_FOUND` | 404 | «No encontramos esa entrada.» | Inexistente **o de otro candidato** (FR-034: 404, nunca 403) |

---

## Confirmación — FR-023, FR-024, art. X

| `code` | HTTP | Mensaje en español | Cuándo |
|---|---|---|---|
| `CONFIRMATION_BLOCKED` | 422 | «Todavía no puedes confirmar tu perfil.» + `details.blockers` | Falta contenido obligatorio (FR-024) |
| `NO_PENDING_CHANGES` | 409 | «No hay cambios nuevos que confirmar.» | El perfil está confirmado y el hash coincide con la versión vigente |

`details.blockers` es una lista de `{code, message}` con estos valores posibles:

| `blocker.code` | Mensaje en español |
|---|---|
| `NO_ENTRIES` | «Tu perfil necesita al menos una entrada.» |
| `MISSING_TARGET_ROLE` | «Falta el puesto que buscas.» |
| `MISSING_LOCATION_OR_REMOTE` | «Indica al menos una ubicación o tu preferencia de trabajo remoto.» |
| `MISSING_SALARY_EXPECTATION` | «Falta tu expectativa salarial con moneda.» |

Los bloqueadores también se exponen de forma proactiva en `GET /profile.confirmation_blockers`, para que la UI pueda deshabilitar el botón de confirmar y explicar por qué **antes** de que el candidato lo intente.

---

## Autenticación — ADR-001

| `code` | HTTP | Mensaje en español | Cuándo |
|---|---|---|---|
| `INVALID_CREDENTIALS` | 401 | «Correo o contraseña incorrectos.» | Login fallido. Mensaje idéntico para correo inexistente y contraseña errónea (no revelar qué correos existen) |
| `TOKEN_EXPIRED` | 401 | «Tu sesión expiró. Inicia sesión otra vez.» | Access token vencido |
| `TOKEN_REVOKED` | 401 | «Tu sesión ya no es válida. Inicia sesión otra vez.» | `jti` en la lista de revocados, o reuso de refresh que revocó la familia |
| `EMAIL_ALREADY_REGISTERED` | 409 | «Ese correo ya tiene una cuenta.» | Registro duplicado |
| `WEAK_PASSWORD` | 422 | «La contraseña debe tener al menos 12 caracteres.» | Política de contraseñas |
| `RATE_LIMITED` | 429 | «Demasiados intentos. Espera unos minutos e inténtalo de nuevo.» | Limitador de `/auth/*`; incluye cabecera `Retry-After` |

---

## Uso desde el frontend

- El frontend **no** traduce ni reescribe `message`: lo muestra tal cual. Así el texto tiene un solo dueño (backend) y no se desincroniza (art. IX).
- El frontend usa `code` únicamente para decidir **comportamiento**: qué acción ofrecer (reintentar, ir a captura manual, ir al aviso de privacidad), qué campo resaltar, si mostrar el botón de confirmar.
- Los códigos son parte del contrato: renombrar uno es un cambio incompatible y debe pasar por regeneración del cliente TS y revisión del PR.
