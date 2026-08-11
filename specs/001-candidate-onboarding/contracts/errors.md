# Catálogo de errores

**Feature**: 001-candidate-onboarding · **Fecha**: 2026-08-11

Contrato: toda respuesta de error tiene la forma `{ "code", "message", "details"? }`.

- **`code`** — identificador estable en inglés (art. IX: identificadores en inglés). Es lo único de lo que el frontend depende para decidir comportamiento.
- **`message`** — texto accionable en español, resuelto en el backend desde este catálogo. Es la fuente única de verdad del texto: el frontend **no** mantiene su propia tabla de mensajes.
- **`details`** — objeto estructurado opcional (campos inválidos, bloqueadores de confirmación, funciones degradadas, límites).

**Tres reglas no negociables:**

1. **Ningún mensaje reproduce contenido del documento ni datos personales** (FR-045, art. V). Ni nombres, ni fragmentos del CV, ni rutas de almacenamiento. Los mensajes son plantillas fijas; los únicos valores interpolados son límites y formatos configurados por el sistema.
2. **Ningún mensaje contiene una credencial, ni completa ni parcialmente, ni una traza técnica** (FR-008, FR-013, SC-013). Un stack trace en la UI es un bug de producto.
3. **Todo error dice qué pasó, por qué y cuál es el siguiente paso concreto** (roadmap §11.5). Sin un siguiente paso, el mensaje está incompleto — y en ejecución local, donde el proyecto no ve los errores de nadie, el mensaje es todo el soporte que hay.

---

## Primera ejecución: divulgación — FR-001, FR-002, SC-011

| `code` | HTTP | Mensaje en español | Cuándo |
|---|---|---|---|
| `DISCLOSURE_ACKNOWLEDGEMENT_REQUIRED` | 409 | «Antes de continuar necesitamos que leas y aceptes qué datos se quedan en tu computadora y qué se envía a tu proveedor de IA.» | No hay acuse registrado para la versión vigente del texto. **Gate de servidor**: se aplica aunque se llame directo a la API, no solo en la SPA |

---

## Primera ejecución: proveedores y preflight — FR-004 – FR-010, SC-012, SC-016

Los cuatro resultados de FR-007 son **cuatro mensajes distintos porque son cuatro situaciones distintas**. Presentar una cuota agotada como credencial inválida manda al usuario a regenerar una llave que funciona perfectamente.

| `code` | HTTP | Mensaje en español | Cuándo |
|---|---|---|---|
| `PROVIDER_CREDENTIAL_REJECTED` | 400 | «Tu proveedor rechazó la API key. Verifica que la copiaste completa y que sigue activa en la consola de tu proveedor.» + `details.console_url` | Preflight con resultado `credential_rejected` (FR-007.1). **Nunca** la llave, nunca una traza |
| `PROVIDER_QUOTA_EXCEEDED` | 429 | «Tu API key es válida, pero alcanzaste el límite de tu cuota. Puedes esperar a que se reinicie o configurar otro proveedor.» | Preflight con resultado `quota_exceeded` (FR-007.4). Se dice explícitamente que **la llave sirve** |
| `PROVIDER_CAPABILITY_UNVERIFIED` | 200 con cuerpo de resultado | «Tu API key funciona, pero este modelo no garantiza [capacidad]. Esto es lo que no podrás hacer:» + `details.affected_features` | Preflight con resultado `capability_unverified` (FR-007.3). **No es un error de transporte**: es un resultado que exige acuse antes de avanzar |
| `PROVIDER_UNREACHABLE` | 503 | «No pudimos comunicarnos con tu proveedor para verificar la llave. Revisa tu conexión e inténtalo de nuevo; no hace falta que vuelvas a escribirla.» | Fallo de red durante el preflight. Se distingue explícitamente de una llave inválida |
| `MODEL_NOT_AVAILABLE` | 400 | «El modelo configurado ya no está disponible en tu proveedor. Actualiza el nombre del modelo en tu configuración; en la documentación está el vigente.» + `details.configured_model` | El proveedor deprecó el modelo configurado. Motivo del ADR-011: un proveedor que retira un modelo no debe romper una instalación que el usuario no actualizó |
| `PROVIDER_NOT_OFFERED` | 422 | «Ese proveedor todavía no está disponible en Vokara.» | Se intentó configurar un proveedor sin verificación empírica registrada, o un endpoint arbitrario (FR-009) |
| `DEGRADATION_ACKNOWLEDGEMENT_REQUIRED` | 409 | «Para continuar con este proveedor necesitamos que confirmes que entiendes qué funciones no estarán disponibles.» | Se intentó avanzar con `capability_unverified` sin el acuse específico (FR-007.3, SC-016) |
| `GENERATION_PROVIDER_REQUIRED` | 409 | «Antes de subir tu CV necesitas configurar tu proveedor de generación: es el que lee el documento y arma tu perfil.» | Gate de entrada al onboarding (FR-010). La ausencia de proveedor de **embeddings** nunca produce este error |

`details.affected_features` es una lista de `{code, message}` que enumera **funciones concretas**, nunca una advertencia genérica:

| `feature.code` | Mensaje en español |
|---|---|
| `CV_PARSING` | «Sembrar tu perfil desde el CV puede fallar o traer datos incompletos.» |
| `SEMANTIC_MATCHING` | «El matching semántico quedaría desactivado. El matching por reglas sigue funcionando.» |

**El estado de una credencial que la API expone es exactamente `configured | not_configured | rejected`.** Ninguna respuesta muestra la llave, ni siquiera parcialmente (roadmap §11.4).

---

## Primera ejecución: vinculación de correo — FR-011 – FR-013

| `code` | HTTP | Mensaje en español | Cuándo |
|---|---|---|---|
| `EMAIL_APP_PASSWORD_REJECTED` | 400 | «Gmail rechazó la App Password. Si tu cuenta es de Google Workspace o tiene Protección Avanzada, las App Passwords están deshabilitadas: usa la vía OAuth.» + `details.oauth_docs_url` | Fallo de autenticación IMAP. El aviso ya se dio **antes** de empezar (FR-012); este mensaje lo remata con la salida |
| `EMAIL_LABEL_NOT_FOUND` | 422 | «No encontramos esa etiqueta en tu cuenta. Créala en Gmail y aplica un filtro que mande ahí tus alertas de empleo; después vuelve a intentarlo.» + `details.help_url` | La etiqueta designada no existe o no es alcanzable. **La vinculación no se da por buena** |
| `EMAIL_PROVIDER_UNREACHABLE` | 503 | «No pudimos conectarnos a tu correo en este momento. Inténtalo de nuevo, o continúa sin vincularlo: no bloquea nada.» | Fallo de red contra IMAP. Recuerda que el paso es omitible |

Ninguno de estos errores bloquea el onboarding: el paso es opcional y omitirlo es una salida válida en cualquier momento (FR-011).

---

## Subida y validación del archivo — FR-016, FR-017, SC-008

| `code` | HTTP | Mensaje en español | Cuándo |
|---|---|---|---|
| `FILE_TOO_LARGE` | 400 | «El archivo pesa más de 10 MB. Sube una versión más ligera de tu CV.» | Tamaño por encima de `MAX_UPLOAD_BYTES`; se detecta por cabecera y por corte del stream |
| `UNSUPPORTED_FILE_TYPE` | 400 | «Solo aceptamos PDF y DOCX. Convierte tu CV a alguno de esos formatos e inténtalo de nuevo.» | La firma de bytes no corresponde a PDF ni a DOCX, sea cual sea la extensión |
| `DOCUMENT_CORRUPT` | 400 | «No pudimos abrir el archivo: parece estar dañado. Vuelve a exportarlo desde tu editor e inténtalo otra vez.» | pypdf o python-docx no logran abrirlo |
| `PARSE_JOB_ALREADY_ACTIVE` | 409 | «Ya estamos procesando un CV tuyo. Espera a que termine para subir otro.» | Índice único parcial sobre `parse_jobs` |
| `PROFILE_ALREADY_SEEDED` | 409 | «Ya tienes un perfil creado a partir de un CV. Volver a subir un CV llegará en una versión próxima.» | Reservado: re-subida con perfil sembrado es la feature 007 |

Los gates de la primera ejecución (`DISCLOSURE_ACKNOWLEDGEMENT_REQUIRED`, `GENERATION_PROVIDER_REQUIRED`) se evalúan **antes** que estos y devuelven 409 sobre la misma subida.

---

## Procesamiento — FR-019 – FR-023, SC-009

Estos códigos viajan en `parse_job.error_code` (estado `failed`), no como respuesta HTTP de la subida: el archivo ya fue aceptado.

| `code` | Mensaje en español | Cuándo | `is_retryable` |
|---|---|---|---|
| `PDF_WITHOUT_TEXT_LAYER` | «Tu PDF no tiene texto seleccionable: parece un documento escaneado. Por ahora no procesamos escaneos, pero puedes crear tu perfil paso a paso y te guiamos.» | Heurística de densidad de caracteres (research R-03) | No — el reintento daría el mismo resultado |
| `DOCUMENT_NOT_A_RESUME` | «Este documento no parece un CV. Revisa que hayas subido el archivo correcto.» | Clasificador con `is_resume = false` (FR-020) | No |
| `DOCUMENT_TOO_SPARSE` | «Encontramos muy poca información en tu CV. Puedes completar tu perfil paso a paso y te guiamos.» | Menos de `MIN_SEEDED_ENTRIES` entradas extraídas | No |
| `PROVIDER_CREDENTIAL_REJECTED` | «Tu proveedor rechazó la API key mientras procesábamos tu CV. Revísala en la configuración; tu archivo no se perdió y puedes reintentar.» | La credencial verificada en el wizard caducó o fue revocada después | **Sí** (FR-023) |
| `PROVIDER_QUOTA_EXCEEDED` | «Alcanzaste el límite de tu cuota mientras procesábamos tu CV. Espera al reinicio o cambia de proveedor; tu archivo no se perdió y puedes reintentar.» | Cuota agotada durante el parseo | **Sí** |
| `EXTRACTION_FAILED` | «Algo falló al procesar tu CV. Puedes intentarlo de nuevo; no perderás lo que ya hayas escrito.» | Error del proveedor tras agotar reintentos, salida que no valida, o trabajo huérfano recuperado por el reaper de arranque | **Sí** |
| `STORAGE_UNAVAILABLE` | «No se encuentra el archivo de tu CV en el directorio de datos. Si moviste o borraste esa carpeta, tu perfil sigue intacto, pero no se puede reprocesar el archivo original.» | Fallo del `StoragePort` o `exists` en falso (ADR-007). **Nunca** se incluye la ruta | **Sí** |
| `INTERNAL_ERROR` | «Ocurrió un error inesperado. Inténtalo de nuevo; si persiste, abre un issue con lo que aparece en la pantalla de diagnóstico.» | Cualquier excepción no clasificada | **Sí** |

Los tres primeros encaminan a la **captura manual guiada** (FR-022, SC-010): el mensaje va acompañado de esa acción en la UI, de modo que el candidato nunca queda sin salida. Los dos de proveedor encaminan a la configuración, no a la captura manual: el problema es reparable.

| `code` | HTTP | Mensaje | Cuándo |
|---|---|---|---|
| `PARSE_JOB_NOT_RETRYABLE` | 409 | «Este procesamiento no se puede reintentar.» | `POST /parse-jobs/{id}/retry` sobre un trabajo que no está en `failed` |

---

## Perfil, entradas y objetivos — FR-030 – FR-037

| `code` | HTTP | Mensaje en español | Cuándo |
|---|---|---|---|
| `VALIDATION_ERROR` | 422 | «Revisa los datos: hay campos con errores.» + `details.fields` | Fallo genérico de Pydantic; `details.fields` lleva el error por campo, en español |
| `SALARY_RANGE_INVALID` | 422 | «El salario mínimo no puede ser mayor que el máximo.» | FR-036 |
| `SALARY_CURRENCY_REQUIRED` | 422 | «Indica la moneda de tu expectativa salarial.» | Hay valor salarial sin moneda (FR-036) |
| `UNSUPPORTED_CURRENCY` | 422 | «Por ahora solo manejamos pesos mexicanos (MXN) y dólares (USD).» | Moneda fuera del conjunto configurado |
| `ENTRY_CONTENT_EMPTY` | 422 | «La entrada está vacía: escribe al menos un dato antes de guardarla.» | Contenido sin ningún campo con valor |
| `ENTRY_TYPE_MISMATCH` | 422 | «El tipo de la entrada no coincide con su contenido.» | `entry_type` ≠ discriminador `kind` del contenido |
| `ENTRY_NOT_FOUND` | 404 | «No encontramos esa entrada.» | Inexistente **o de otro `candidate_id`** (FR-049: 404, nunca 403) |

---

## Confirmación — FR-038, FR-039, art. X

| `code` | HTTP | Mensaje en español | Cuándo |
|---|---|---|---|
| `CONFIRMATION_BLOCKED` | 422 | «Todavía no puedes confirmar tu perfil.» + `details.blockers` | Falta contenido obligatorio (FR-039) |
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

## Errores de arranque y de entorno

No son respuestas de la API —la API todavía no responde— pero son los que más deciden si alguien se queda o se va (roadmap §11.5), así que su texto vive aquí y se prueba a mano en cada release.

| Situación | En vez de | Decir |
|---|---|---|
| Postgres aún no acepta conexiones | `Connection refused: postgres:5432` | «La base de datos no está lista. Suele tardar unos segundos en el primer arranque; si persiste, revisa que Docker esté corriendo.» |
| Puerto ocupado | `bind: address already in use` | «El puerto 8000 ya está en uso por otro programa. Ciérralo o cambia el puerto en tu configuración.» |
| Docker ausente | `command not found: docker` | «Necesitas Docker para ejecutar Vokara. En Windows, además, WSL2.» + enlace a la guía |
| Directorio de datos inaccesible | `PermissionError: /data` | «Vokara no puede escribir en su directorio de datos. Revisa los permisos de esa carpeta o configura otra ruta.» |

---

## Uso desde el frontend

- El frontend **no** traduce ni reescribe `message`: lo muestra tal cual. Así el texto tiene un solo dueño (backend) y no se desincroniza (art. IX).
- El frontend usa `code` únicamente para decidir **comportamiento**: qué acción ofrecer (reintentar, ir a captura manual, ir a la configuración de proveedores, mostrar el acuse de degradación), qué campo resaltar, si mostrar el botón de confirmar.
- **El frontend nunca ramifica por proveedor** (art. XI): renderiza el catálogo y los mensajes que el backend le da. `details.console_url` y `details.oauth_docs_url` vienen del backend por eso mismo.
- Los códigos son parte del contrato: renombrar uno es un cambio incompatible y debe pasar por regeneración del cliente TS y revisión del PR.
