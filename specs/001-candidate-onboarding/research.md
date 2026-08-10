# Fase 0 — Investigación y decisiones técnicas

**Feature**: 001-candidate-onboarding · **Fecha**: 2026-08-10 · **Plan**: [plan.md](./plan.md)

Cada entrada resuelve una incógnita del Technical Context. No queda ningún `NEEDS CLARIFICATION` abierto; los dos puntos que exceden la autoridad de un plan están marcados como **requiere ratificación** y listados en el plan bajo "Decisiones abiertas".

---

## R-01 · Validación y detección del tipo real del archivo (FR-001, FR-002)

**Decisión.** Validación en tres capas, todas **antes** de encolar:

1. **Tamaño**: rechazo por `Content-Length` y, además, corte duro durante la lectura del stream al superar `MAX_UPLOAD_BYTES` (10 MB, configurable). No confiar en la cabecera sola.
2. **Tipo real por firma de bytes**, no por extensión ni por `Content-Type` del cliente: PDF debe empezar con `%PDF-`; DOCX es un ZIP (`PK\x03\x04`) que debe contener `word/document.xml` y declarar el content type de WordprocessingML. La extensión y el `Content-Type` se ignoran para decidir.
3. **Legibilidad**: apertura efectiva con `pypdf` / `python-docx` dentro de un `try`. Si la librería no puede abrir el documento → `DOCUMENT_CORRUPT`.

**Rationale.** Los tres modos de fallo que la spec exige rechazar (tamaño, formato no soportado, corrupción) tienen causas distintas y mensajes distintos; distinguirlos por reglas es determinista y barato. La firma de bytes es la única señal que un cliente no controla.

**Alternativas consideradas.**
- `python-magic` (libmagic): dependencia con binario del sistema para dos firmas que caben en 15 líneas. Descartada por art. VII.
- Confiar en la extensión: trivialmente falsificable, y un `.pdf` que en realidad es una imagen produciría un perfil basura, justo lo que SC-008 y SC-009 prohíben.
- Validar solo en el worker: dejaría al candidato esperando 30 s para recibir un "tu archivo no sirve". El rechazo debe ser síncrono (FR-002: "antes de procesar").

---

## R-02 · Extracción de texto y CVs a dos columnas o con tablas (US1 AC5, edge case)

**Decisión.**
- **PDF**: `pypdf.PageObject.extract_text(extraction_mode="layout")`, que preserva la disposición espacial en vez de concatenar por orden de flujo interno. Se conserva un salto de página explícito entre páginas.
- **DOCX**: recorrer `document.element.body` en orden de documento e ir emitiendo párrafos y tablas según aparecen; las tablas se serializan fila por fila con separador de celda explícito. **No** basta con `document.paragraphs`: omite todo el contenido dentro de tablas, y una fracción relevante de los CVs del mercado maqueta con tablas invisibles.
- El texto resultante se pasa íntegro al extractor, con marcas de estructura (saltos de página, límites de tabla) intactas.

**Rationale.** El modo `layout` de pypdf reduce la intercalación de columnas sin sumar dependencias; el resto de la robustez la aporta el modelo, que lee texto con estructura mucho mejor que texto barajado. Lo que no se puede estructurar con confianza no se inventa: cae en la regla de completitud de R-05 y llega al candidato marcado como incompleto, que es exactamente lo que pide el escenario US1 AC5.

**Alternativas consideradas.**
- `pdfplumber` con detección de columnas por análisis de cajas: más preciso en el caso difícil, ~3× más lento y añade `pdfminer.six`. Reevaluable si las evals muestran que la columna es la fuente principal de error.
- `PyMuPDF`: el mejor extractor del ecosistema, licencia AGPL. Descartado por licencia.
- Convertir DOCX a PDF y usar un solo camino: añade LibreOffice al contenedor por una simplificación de código menor.

---

## R-03 · Detección de PDF escaneado sin capa de texto (FR-006, SC-009)

**Decisión.** Heurística determinista, configurable y probada, evaluada tras la extracción de texto y antes de cualquier llamada al LLM:

```
scanned  ⇔  total_chars < MIN_DOC_CHARS  (por defecto 200)
             OR  (páginas con < MIN_PAGE_CHARS (50) caracteres) / total_páginas ≥ 0.8
```

Un PDF que cae en esta condición produce el error `PDF_WITHOUT_TEXT_LAYER`, cuyo mensaje explica que v1 no procesa documentos escaneados y ofrece la captura manual guiada (FR-007). El documento queda registrado y el binario conservado; el perfil no se toca.

**Rationale.** Un PDF escaneado sí tiene páginas y sí abre correctamente: lo que no tiene es texto. La señal es la densidad de caracteres, no la validez del archivo. Los umbrales viven en `Settings` (art. VII: "el plazo/umbral es configurable, nunca una constante en código", criterio ya establecido por 006) y se calibran con el golden set, que incluirá al menos dos PDFs escaneados sintéticos.

**Casos límite cubiertos por los tests.** PDF híbrido (portada escaneada + resto con texto) → no se marca como escaneado si supera el umbral global; PDF de una página con muy poco texto real (CV minimalista) → cae en "contenido mínimo", que es otro camino con su propio mensaje, no un falso "escaneado".

**Alternativas consideradas.**
- Contar imágenes de página completa: más frágil (hay CVs de diseño con fondos a sangre y capa de texto perfecta).
- Intentar la extracción y dejar que el clasificador LLM decida: quema una llamada, es no determinista y contradice el art. III para una decisión que se resuelve contando caracteres.
- Añadir OCR de respaldo: prohibido por FR-006 en v1.

---

## R-04 · Detección de "no es un CV" (FR-005, SC-008)

**Decisión.** Paso de clasificación propio con el modelo rápido de Gemini y salida estructurada:

```python
class DocumentClassification(BaseModel):
    is_resume: bool
    document_kind: Literal["resume", "invoice", "contract", "letter", "academic_paper", "other"]
    reason_es: str          # explicación corta, sin PII, para el mensaje al candidato
```

Se ejecuta sobre los primeros `CLASSIFIER_CHARS` (por defecto 6.000) del texto extraído. Si `is_resume` es falso, el pipeline se detiene con `DOCUMENT_NOT_A_RESUME`, **sin crear ninguna entrada** y sin ejecutar la extracción cara.

**Rationale.** Separarlo de la extracción tiene tres ventajas medibles: corta el costo cuando el documento no sirve, hace que el fallo sea diagnosticable (sabemos *qué* creyó el modelo que era), y produce una métrica de eval independiente (precisión/recall del clasificador) con casos negativos sembrados: factura, contrato, carta, artículo. El art. III se respeta porque el modelo devuelve un booleano tipado y es el **servicio** quien decide el flujo.

**Alternativas consideradas.**
- Un solo prompt que extrae y además marca `is_resume`: ahorra una llamada, pero paga tokens de extracción sobre documentos inútiles y mezcla dos métricas de eval en un solo número.
- Heurística de palabras clave ("experiencia", "educación", "skills"): falsos negativos altísimos en CVs muy visuales o en inglés, falsos positivos en cartas de presentación.

---

## R-05 · Extracción a entradas y marcado de incompletitud (FR-009, FR-012, FR-013)

**Decisión.** Una única llamada `with_structured_output(SeededProfile)` con `temperature=0` y modelo pineado. En el esquema, **todos** los campos que el documento puede no traer son `Optional` con `None` por defecto, y el prompt es explícito: "si el dato no aparece literalmente en el documento, devuelve `null`; nunca lo infieras". Cada entrada devuelve además `language` (ISO 639-1) y `source_excerpt` (fragmento literal del que salió).

La **completitud no la decide el modelo**: `domain/completeness.py` aplica reglas por tipo sobre la entrada ya validada.

| Tipo | Campos clave exigidos para `is_complete` |
|---|---|
| `experience` | `title`, `organization`, `start_date` |
| `education` | `institution`, `degree` |
| `achievement` | `description` y (`metric` o `context`) |
| `certification` | `name`, `issuer` |
| `project` | `name`, `description` |
| `language` | `name`, `level` |
| `skill` | `name` |

**Rationale.** La regla de completitud es el mecanismo por el que FR-013 se cumple sin depender de la buena voluntad del modelo: como el esquema permite `null` y las reglas detectan el `null`, la salida natural ante un dato ausente es "entrada incompleta", no "dato inventado". `source_excerpt` es barato y hace las evals auditables ("¿de dónde salió esto?"), además de habilitar en la UI el "ver en el CV" que reduce la fricción de revisión.

**Alternativas consideradas.**
- Pedirle al modelo un `confidence` por entrada: números que ningún LLM calibra bien y que acabaríamos umbralizando a ciegas. La ausencia de campo clave es una señal objetiva y verificable.
- Campos obligatorios en el esquema con valores centinela ("N/A", "Desconocido"): fabrica exactamente el dato falso que el art. IV prohíbe.
- Una llamada por tipo de entrada: 7× costo y latencia; el contexto completo del CV mejora la extracción, no la empeora.

---

## R-06 · Almacenamiento del binario y cifrado en reposo (FR-003, art. V) — **requiere ratificación (ADR-007)**

**Decisión propuesta.** Puerto `StoragePort` (`put` / `get` / `delete` / `exists`) con implementación S3-compatible vía boto3, y **cifrado de sobre en la aplicación**: se genera una clave de datos AES-256 por objeto, se cifra el contenido con AES-256-GCM, la clave de datos se envuelve con una clave maestra que vive en variable de entorno (`DOCUMENT_ENCRYPTION_KEY`), y se persisten en `documents` la clave envuelta, el nonce y el `key_version`. Backend concreto: **MinIO** en dev (contenedor de Compose) y en el VPS (ADR-002).

**Rationale.**
- El cifrado deja de depender del backend: valga MinIO, Backblaze B2 o Cloudflare R2, el objeto en reposo es ilegible sin la clave maestra. Migrar de proveedor no reabre la discusión de cumplimiento.
- `key_version` permite rotación sin re-cifrar todo el histórico de golpe.
- El borrado de 006 se vuelve doblemente verificable: se borra el objeto **y** se destruye la clave envuelta de la fila; sin la clave, un objeto residual en un backup del bucket es ruido, no dato personal. Esto refuerza directamente 006/SC-001 y 006/SC-002.

**Por qué necesita ADR.** Ningún ADR vigente decide el almacenamiento de objetos, y la DoD de la constitución exige entrada en `docs/adr/` cuando hay decisión de arquitectura. Además compromete recursos del KVM 2, que el ADR-002 ya señala como limitados.

**Alternativas consideradas.**
- **SSE-S3 / SSE-KMS de MinIO**: cifrado del lado del servidor gestionado por el propio MinIO, pero exige operar KES y un proveedor de claves; más piezas en el VPS (art. VII) y la garantía se pierde si algún día el backend cambia.
- **Filesystem del VPS con volumen cifrado**: cero dependencias, pero ata el borrado verificable al sistema de archivos, complica el backup y no sobrevive a un segundo nodo.
- **URLs prefirmadas para subida directa desde el navegador**: descarga a la API, pero salta la validación por firma de bytes de R-01 y la aplicación del límite de tamaño. Con 10 MB de tope, atravesar la API no es un problema de escala.

---

## R-07 · Ejecución asíncrona, exposición del progreso y unicidad del trabajo (FR-004, edge cases)

**Decisión.**
- `POST /documents` responde **202** con `document_id` y `parse_job_id`; la tarea Celery se encola **después** del commit de la transacción, para que el worker nunca vea una fila que aún no existe.
- Progreso por **polling**: `GET /parse-jobs/{id}` devuelve `status` (`queued` | `running` | `succeeded` | `failed`), `progress_percent` y `step` (`extracting_text` | `classifying` | `extracting_entries` | `persisting`). El front usa `refetchInterval: 2000` de TanStack Query mientras el estado no sea terminal.
- **Un solo trabajo activo por candidato**, garantizado en base de datos con índice único parcial:
  `CREATE UNIQUE INDEX ... ON parse_jobs (candidate_id) WHERE status IN ('queued','running')`.
- **Idempotencia ante reentrega**: la tarea toma el trabajo con `UPDATE parse_jobs SET status='running' WHERE id=:id AND status='queued'`; si no afecta filas, otra ejecución ya lo tomó y la tarea termina sin hacer nada.
- Las entradas sembradas se escriben en **una sola transacción al final**. Un trabajo fallido deja cero entradas, lo que hace que el reintento de FR-008 sea una simple inserción y no una reconciliación.

**Rationale.** El polling cada 2 s sobre un recurso ya modelado cuesta una consulta por índice primario y no añade infraestructura; SSE o WebSocket exigirían mantener conexión, afinidad de proceso y un camino de reconexión, para un flujo que dura menos de un minuto y ocurre una vez por candidato (art. VII). Que el candidato cierre el navegador y vuelva funciona gratis: el estado vive en la base, no en la conexión.

**Alternativas consideradas.**
- SSE: reevaluable cuando llegue el simulador de entrevistas, que sí lo necesita (roadmap §4.2).
- Long polling: peor relación complejidad/beneficio que refrescar cada 2 s.
- Semáforo en Redis para la unicidad: un `SETNX` puede quedar huérfano si el worker muere; el índice parcial no puede desincronizarse del estado real porque **es** el estado real.

---

## R-08 · Versionado, hash canónico y "cambios sin confirmar" (FR-025 – FR-029)

**Decisión.**
- Cada confirmación inserta una fila en `profile_versions` con `version_number` monotónico por perfil, `origin='confirmation'`, `content` (JSONB con entradas vivas + objetivos) y `content_hash` (SHA-256 de la serialización canónica).
- **Inmutabilidad real**: trigger de Postgres que aborta cualquier `UPDATE` o `DELETE` sobre la tabla. El repositorio tampoco expone métodos de escritura.
- **Serialización canónica** (`domain/canonical.py`): claves ordenadas, sin espacios superfluos, fechas ISO-8601, entradas ordenadas por `id`. Es la única forma de que dos snapshots iguales produzcan el mismo hash.
- `has_unconfirmed_changes` **se deriva**: `hash(trabajo_en_curso) != current_version.content_hash`. No existe columna booleana.
- El detalle de FR-029 ("en qué consisten") lo calcula `domain/diff.py` comparando por `id` contra el snapshot vigente: entradas añadidas, modificadas (con lista de campos), eliminadas y cambios de objetivos.

**Rationale.** Una bandera booleana es correcta solo mientras todo servicio que muta el perfil se acuerde de actualizarla; el día que uno lo olvide, FR-028 se rompe en silencio y sirve trabajo en curso al resto del producto. El hash derivado no puede desincronizarse y además maneja gratis el caso "edité y deshice", que con bandera quedaría reportando cambios inexistentes. El costo es despreciable a esta escala (decenas de entradas, hash en microsegundos).

**Alternativas consideradas.**
- Tabla de eventos de cambio: auditoría más rica, pero es una tabla que nadie consume en 001 (art. VII) y el diff contra el snapshot ya responde la pregunta del usuario.
- Versionado por filas con `valid_from`/`valid_to` en `profile_entries`: modelo temporal completo, mucha más complejidad en cada consulta, y FR-026 solo pide recuperar el contenido íntegro de una confirmación pasada — que es justo lo que un snapshot hace mejor.
- Guardar solo el diff por versión: reconstruir requiere replay y una versión corrupta rompe todo el histórico.

---

## R-09 · Transición de origen de las entradas (FR-011, FR-016)

**Decisión.**
- `cv_seed` → `user_edited` **solo si el contenido cambia de verdad** (comparación del contenido canónico antes/después; un guardado sin cambios no altera el origen).
- `user_added` permanece `user_added` al editarse.
- `user_edited` permanece `user_edited`.
- El `id` nunca cambia (FR-010).

**Rationale.** FR-016 se lee literalmente como "editar cualquier entrada la vuelve `user_edited`", pero el escenario de aceptación US2.1 solo describe la transición desde `cv_seed`, y convertir una entrada creada por el candidato en `user_edited` **destruiría información**: dejaría de constar que la escribió él desde cero. La feature 007 protege por igual a `user_edited` y `user_added` frente a la fusión, así que la distinción no cambia ninguna decisión aguas abajo y sí conserva la procedencia real. SC-002 se cumple igualmente: los tres valores existen y toda entrada tiene uno.

**Registro explícito.** Es una interpretación del plan, no un cambio de la spec. Si producto prefiere la lectura literal, se ajusta en una línea de `entry_service.py` — pero se perdería la trazabilidad de qué escribió el candidato de su puño.

---

## R-10 · Reintento tras fallo sin perder trabajo manual (FR-008)

**Decisión.** `POST /parse-jobs/{id}/retry` solo se acepta si el trabajo está en `failed`. Crea un `parse_job` **nuevo** sobre el **mismo** documento (el binario ya está guardado y validado: no se re-sube nada) y hereda `retry_of_job_id` para la auditoría. La siembra es **estrictamente aditiva**: nunca borra ni pisa entradas existentes.

Como un trabajo fallido no deja entradas (transacción única, R-07), el reintento no puede duplicar nada. Las entradas que el candidato haya creado a mano mientras tanto (`user_added`) quedan intactas por construcción, no por una comprobación.

**Rationale.** El requisito "sin perder entradas creadas o editadas manualmente" se satisface por diseño del pipeline, que es más fuerte que satisfacerlo con una salvaguarda que alguien puede quitar en una refactorización.

**Alternativas consideradas.**
- Reintento automático con backoff dentro de Celery: útil para fallos transitorios del proveedor y **sí** se aplica dentro de la llamada al adapter (3 intentos con backoff exponencial ante error de red o 429). Lo que no se automatiza es el reintento del trabajo completo tras un fallo definitivo: FR-008 lo pone en manos del candidato, y un reintento silencioso ocultaría un fallo sistemático de extracción.
- Permitir reintento sobre un trabajo `succeeded`: eso es reprocesamiento, y pertenece a 006/FR-003 → 007. Se rechaza con `409`.

---

## R-11 · Autenticación: implementación del ADR-001 (precondición de la feature)

**Decisión.** Sin desviaciones del ADR-001. Concreciones que el ADR deja al plan:

- **Access token**: JWT HS256, `TTL = 15 min`, claims `sub`, `exp`, `iat`, `jti` y nada más. Vive en memoria del frontend (nunca `localStorage`), coherente con ADR-006.
- **Refresh token**: opaco (32 bytes de `secrets.token_urlsafe`), almacenado **hasheado** (SHA-256; no necesita Argon2 porque es de alta entropía, no una contraseña) en `refresh_tokens`, TTL 30 días, cookie `httpOnly` + `Secure` + `SameSite=Lax`, path acotado a `/api/v1/auth`.
- **Rotación y detección de reuso**: cada refresh emite uno nuevo e invalida el anterior. Presentar un refresh ya usado revoca **toda la familia** (`family_id`) y añade sus `jti` a la lista de revocados.
- **Revocación**: `jti` revocados en Redis con TTL igual al `exp` restante; el chequeo se hace en la dependencia `current_candidate`.
- **Rate limiting**: ventana deslizante en Redis sobre `/auth/login`, `/auth/register` y `/auth/refresh`, por IP y por cuenta, con backoff creciente. Implementación propia (~40 líneas tipadas).
- **Verificación de correo y reset de contraseña**: **diferidos** — requieren el adapter de correo y la spec 001 establece que esta feature no envía correo. Se registra como deuda explícita del ADR-001, no como omisión.

**Rationale.** Es el bloque del plan donde un error es de seguridad, no de UX; por eso lleva su propia batería de tests de integración (rotación, reuso, expiración, revocación, límite de tasa) exigida por el propio ADR-001.

---

## R-12 · Embeddings en 001: puerto sí, vectores no (ADR-003, art. VII)

**Decisión.** Se entregan el puerto `EmbeddingsPort` (`embed_texts`, `model_name`, `dimensions`) y su implementación Gemini, con un test de contrato que verifica que la dimensión devuelta coincide con la declarada. **No** se persiste ningún vector en 001 porque no existe consumidor: el matching es F1.5 y la normalización de skills es ADR-004, ambos fuera de alcance.

La regla de ADR-003 —cada vector persiste `embedding_model` y `embedding_dim`, con convivencia de dos modelos durante una migración— queda escrita como **convención vinculante** en `data-model.md`, y la extensión `pgvector` se habilita en la primera migración para que la feature que estrene vectores no tenga que tocar la infraestructura.

**Rationale.** Crear hoy una tabla de embeddings vacía sería infraestructura sin consumidor (art. VII) y, peor, congelaría una decisión de forma (columna vs tabla por modelo) sin saber aún si el vector va por entrada, por perfil o por ambos. Lo que sí hay que fijar hoy —y se fija— es que el puerto exista y que la regla de persistencia esté escrita antes de que alguien escriba el primer `vector(768)`.

**Alternativas consideradas.**
- Crear ya `profile_entry_embeddings` y poblarla al sembrar: costo de LLM por cada entrada de cada candidato, sin nadie que lea el resultado.
- No mencionar embeddings en 001: dejaría al implementador de F1.5 descubriendo la trampa de la dimensión fija de pgvector que el ADR-003 advirtió expresamente.

---

## R-13 · Trazado de llamadas LLM sin filtrar PII (art. VIII vs art. V)

**Decisión.** El decorador de trazado del adapter registra, por llamada: `model`, `prompt_version`, `input_tokens`, `output_tokens`, `estimated_cost_usd`, `latency_ms`, `attempt`, `outcome` y `parse_job_id`. **Nunca** el prompt, el texto del CV ni la salida. El registro va a structlog y a la tabla `llm_call_logs`. Los logs pasan además por un procesador de structlog que elimina claves sensibles conocidas y trunca cualquier valor de texto libre.

Integración con Langfuse/LangSmith: **diferida**, no descartada. Su valor está en inspeccionar entradas y salidas, y en 001 todas contienen PII.

**Rationale.** Los artículos VIII y V no chocan realmente: el art. VIII pide costo, latencia y versión de prompt, y eso es exactamente lo que se traza. Enviar los cuerpos a un tercero es lo que el art. V prohíbe, y no es necesario para nada de lo que el art. VIII exige. Con `parse_job_id` en la traza, un fallo sigue siendo diagnosticable: se reproduce localmente con el documento del candidato solo si él lo autoriza, o con el golden set.

**Alternativas consideradas.**
- Langfuse con redacción de PII antes de enviar: la redacción fiable de un CV completo (nombres, empresas, escuelas, ciudades) es un problema abierto; una fuga sería un incidente de datos personales bajo LFPDPPP.
- Trazar solo cuando falla: perdemos la línea base de costo y latencia, que es justo lo que el art. VIII quiere.

---

## R-14 · Presupuesto de latencia para SC-004 (< 60 s p95)

**Decisión.** Presupuesto por etapa, medido en las evals y verificado en `quickstart.md`:

| Etapa | Objetivo p95 | Nota |
|---|---|---|
| Subida + validación + cifrado + `put` a storage | 3 s | 10 MB por la API |
| Encolado → worker toma la tarea | 2 s | worker con concurrencia ≥ 2 |
| Extracción de texto (PDF/DOCX) | 3 s | pypdf modo layout, 10 páginas |
| Clasificación (modelo rápido, 6k chars) | 4 s | |
| Extracción estructurada (modelo rápido, CV completo) | 30 s | etapa dominante |
| Reglas de completitud + persistencia | 1 s | una transacción |
| Latencia de polling hasta que la UI lo refleja | 2 s | intervalo de 2 s |
| **Total** | **45 s** | **15 s de margen sobre los 60 s de SC-004** |

Si un CV supera `MAX_EXTRACTION_CHARS` (por defecto 120.000 caracteres — un CV de 10 páginas ronda los 30.000), se trunca conservando el inicio del documento y se marca el `parse_job` con `truncated=true`, que la UI comunica al candidato para que revise con más atención. No se trocea ni se paraleliza: el troceo introduce el problema de fusionar entradas duplicadas entre trozos, que es precisamente el problema difícil de la feature 007.

**Rationale.** El presupuesto convierte SC-004 en algo medible por etapa: si un día se incumple, la eval dice cuál etapa se salió, no solo que "va lento".

---

## R-15 · Golden set y evals bloqueantes (art. VI, SC-003, FR-032, FR-033)

**Decisión.**
- Ubicación: `backend/tests/evals/golden_set/`, con `<caso>.pdf|docx` + `<caso>.expected.json` versionados en el repo.
- Composición inicial: **12 casos** — 6 CVs sintéticos en español (uno a dos columnas, uno con tablas), 2 en inglés, 1 mixto, 1 PDF escaneado, 1 documento que no es CV (factura), 1 CV mínimo de contenido escaso. Se amplía hacia los 30–50 del roadmap §6.4 conforme avance la Fase 2.
- **Procedencia (FR-032/FR-033)**: material sintético o del propio equipo. Un `CODEOWNERS` sobre el directorio y una nota en el README del golden set dejan constancia de que añadir material de un usuario real requiere ADR propio y consentimiento opt-in separado.
- Métricas: tasa de error por campo (**bloqueante en < 5%**, SC-003), precisión y recall del clasificador de "no es CV" (bloqueante en 100% sobre los negativos del set, SC-008), detección de PDF sin capa de texto (bloqueante en 100%, SC-009), y una métrica de **invención**: campos presentes en la salida cuyo valor no aparece en el texto fuente → bloqueante en 0 (art. IV).
- Determinismo: `temperature=0` y versión de modelo pineada en `Settings`.
- CI: el job de evals corre en **todo** PR que toque `adapters/llm/`, `services/extraction_service.py`, `domain/completeness.py` o el propio golden set; en el resto de PRs corre un subconjunto de humo de 3 casos. Ambos bloqueantes. Requiere el secreto `GOOGLE_API_KEY` en el repositorio.

**Rationale.** Las evals son la única prueba de SC-003 y la única forma de que cambiar un prompt deje de ser un acto de fe (art. VI). El filtro por rutas mantiene el costo acotado sin abrir un hueco: nada que afecte a la extracción puede entrar sin pasar el set completo.

**Alternativas consideradas.**
- Evals solo nocturnas: detectan la regresión después del merge, que es tarde. El art. VI dice "corriendo en CI", no "corriendo alguna vez".
- Evals con respuestas grabadas (VCR): deterministas y gratis, pero dejarían de medir al modelo, que es exactamente lo que cambia. VCR sí se usará para adapters de fuentes de vacantes (roadmap §6.2), donde el objetivo es detectar cambios de formato ajenos.

---

## R-16 · Sincronía del cliente TypeScript con OpenAPI (art. I)

**Decisión.** `python -m app.openapi_export > frontend/openapi.json` genera el esquema **sin levantar el servidor**; `npm run generate:api` lo transforma con `openapi-typescript` en `frontend/src/api/schema.d.ts`, y el runtime usa `openapi-fetch` tipado con ese esquema. `schema.d.ts` se commitea. En CI, un paso regenera ambos artefactos y ejecuta `git diff --exit-code`: si alguien cambió un endpoint sin regenerar, el PR falla.

**Rationale.** Es la aplicación literal del art. I ("un cambio de esquema debe romper el build, no producción"). Que el archivo esté commiteado permite además que el build del frontend no dependa de tener un backend a mano.

**Alternativas consideradas.**
- Generar en tiempo de build sin commitear: el diff de un PR deja de mostrar el cambio de contrato, que es justo lo que un revisor necesita ver.
- `orval` con hooks de TanStack Query generados: más ergonómico, pero genera mucho más código y ata la capa de datos del front a un generador. `openapi-fetch` es un cliente delgado y los hooks se escriben a mano una vez.

---

## R-17 · Ubicación y validación del cuestionario de objetivos (FR-020 – FR-022)

**Decisión.** Columnas tipadas en `candidate_profiles`, no JSONB: `target_role`, `salary_min`, `salary_max`, `salary_currency`, `remote_preference` (enum `onsite|hybrid|remote|any`), `locations text[]`, `industries text[]`, `deal_breakers text[]`. Validación en dos niveles: Pydantic en la frontera (mensaje en español, FR-021) y `CHECK` en la base (`salary_min <= salary_max`, moneda de tres letras mayúsculas del conjunto permitido).

**Rationale.** Los objetivos son datos consultados por el matching (F1.5) y con validaciones de negocio reales; en columnas son verificables por la base y agregables sin desenrollar JSON. El `CHECK` es la red que impide que un camino futuro (import, script de mantenimiento) salte la validación de Pydantic. Las listas van como `text[]` en vez de tablas hijas porque no tienen atributos propios ni relaciones (art. VII); si mañana una ubicación necesita país y coordenadas, se promueve a tabla.

---

## R-18 · Paso del onboarding derivado, no persistido (US2 AC5)

**Decisión.** `GET /profile` devuelve `onboarding_step` calculado por reglas puras:

```
sin consentimiento vigente          → "consent"
sin documento y sin entradas        → "upload"
parse_job activo                    → "processing"
último parse_job failed             → "processing_failed"
entradas > 0 y objetivos incompletos→ "objectives"
objetivos completos y state=draft   → "confirm"
state=complete                      → "done"
```

**Rationale.** Un campo persistido de "paso actual" se desincroniza del estado real en cuanto algo pasa fuera del flujo previsto (el candidato borra su última entrada, un trabajo falla, vuelve dos semanas después). Derivarlo lo hace auto-reparable y elimina una columna que ningún otro requisito pide. La UI navega a la ruta que corresponde a ese valor, así que "recuperar el punto del flujo donde se quedó" sale gratis y siempre correcto.

---

## R-19 · Concurrencia y guardado del trabajo de revisión (FR-019)

**Decisión.** Guardado explícito por entrada (`PATCH /profile/entries/{id}` al enviar el formulario de esa entrada), con semántica de **último escritor gana**. Sin bloqueo optimista, sin autosave por pulsación de tecla. TanStack Query invalida la lista tras cada mutación.

**Rationale.** El único editor de un perfil es su propio dueño (FR-034); el conflicto realista es "dos pestañas abiertas", cuyo daño máximo es perder una edición que el candidato acaba de hacer y ve delante. Añadir `If-Match` con `ETag` es correcto pero paga complejidad en cada endpoint y en el cliente para un escenario marginal. Se documenta como decisión consciente y se reevalúa si aparece edición colaborativa (que hoy no está ni en el roadmap).

---

## R-20 · Contenedores, Compose y CI (ADR-002, roadmap §9)

**Decisión.**
- **Dockerfile multi-stage** para backend (etapa `builder` con `uv sync --frozen` → runtime `python:3.12-slim` sin toolchain) y para frontend (build de Vite → estáticos).
- **Compose de dev**: `api`, `worker`, `postgres` (imagen `pgvector/pgvector:pg16`, tag fijo), `redis`, `minio`. Volúmenes nombrados para `.venv` y `node_modules` (trampa de rendimiento de Docker en Mac señalada en ADR-000).
- **Versiones fijadas** en ambas máquinas: `.python-version`, `uv.lock`, `.nvmrc`, `package-lock.json`, tags de imagen fijos, y `.gitattributes` con `* text=auto eol=lf` desde el primer commit (WSL2 + macOS, ADR-000).
- **CI (GitHub Actions)**, todo bloqueante: `ruff check` + `ruff format --check` → `mypy --strict` → `pytest` (unit + integración con testcontainers) → drift del cliente TS → `vitest` → evals → build de imágenes.

**Rationale.** Es la Fase 1 del roadmap ejecutada dentro de esta feature, que es donde primero se necesita. Las trampas multiplataforma del ADR-000 (CRLF, mayúsculas/minúsculas, bind mounts lentos) se cierran desde el primer commit porque son exactamente la clase de bug que aparece "en la otra máquina" y cuesta un día encontrar.

---

## Resumen de incógnitas resueltas

| Incógnita del Technical Context | Resuelta en |
|---|---|
| Cómo detectar formato real, corrupción y tamaño antes de procesar | R-01 |
| Cómo evitar intercalado de columnas y perder tablas | R-02 |
| Cómo detectar PDF escaneado sin OCR | R-03 |
| Cómo detectar que el archivo no es un CV | R-04 |
| Cómo garantizar que no se inventan datos y marcar incompletas | R-05 |
| Dónde y cómo se guarda cifrado el binario | R-06 — **requiere ADR-007** |
| Cómo se expone el progreso y se garantiza un solo trabajo activo | R-07 |
| Cómo se versiona y cómo se detectan cambios sin confirmar | R-08 |
| Cuándo cambia el origen de una entrada | R-09 |
| Cómo reintentar sin perder trabajo manual | R-10 |
| Concreciones del ADR-001 que el ADR deja abiertas | R-11 |
| Qué parte de embeddings entra en 001 | R-12 |
| Cómo cumplir art. VIII sin violar art. V | R-13 — nota para ADR-003 |
| Cómo se cumple el < 60 s de SC-004 | R-14 |
| Composición, procedencia y umbrales del golden set | R-15 |
| Cómo se impide que el cliente TS se desincronice | R-16 |
| Dónde viven y cómo se validan los objetivos | R-17 |
| Cómo se recupera el punto del flujo | R-18 |
| Qué pasa con ediciones concurrentes | R-19 |
| Contenedores, Compose y CI | R-20 |
