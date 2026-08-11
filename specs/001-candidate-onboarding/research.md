# Fase 0 — Investigación y decisiones técnicas

**Feature**: 001-candidate-onboarding · **Fecha**: 2026-08-11 · **Plan**: [plan.md](./plan.md)

Cada entrada resuelve una incógnita del Technical Context. **No queda ningún `NEEDS CLARIFICATION` abierto y no hay decisiones bloqueantes pendientes de ratificación**: las dos que tenía la versión anterior de este documento las cerraron el ADR-007 (almacenamiento) y el ADR-003 junto con el art. VIII v2.1.0 (trazas de LLM sin plataformas externas).

---

## Qué cambió respecto del plan anterior

Registro explícito para que la trazabilidad de la regeneración no dependa del historial de git.

| Decisión anterior (2026-08-10) | Estado | Reemplazo |
|---|---|---|
| **R-06** — `StoragePort` sobre S3/MinIO con cifrado de sobre AES-256-GCM, clave envuelta y `key_version`, marcada *"requiere ratificación (ADR-007)"* | **Reemplazada** | El ADR-007 la reescribió en lugar de ratificarla: `StoragePort` sobre **filesystem local**, **sin cifrado**. El diseño de cifrado queda **diferido**, no descartado, para un eventual despliegue multiusuario. Ver R-06 |
| **R-11** — Concreciones del ADR-001: JWT HS256, refresh opaco con rotación y detección de reuso, revocación de `jti` en Redis, rate limiting | **Eliminada** | El ADR-008 dejó la autenticación sin sujeto. El hueco lo ocupa R-11 en su forma nueva: identidad local sin autenticación |
| **`temperature = 0`** como garantía del determinismo del art. III (aparecía en R-05, R-15 y en `contracts/llm-extraction.md`) | **Retirada como argumento** | Los parámetros de muestreo están deprecados en Gemini 3.x y no todos los proveedores los exponen igual (ADR-003 nota 2026-08-11, ADR-011). El determinismo lo sostienen el esquema tipado, las decisiones de flujo fuera del LLM y las reglas testeables. Ver R-25 |
| **R-20** — Compose con `minio`, despliegue en VPS, ambientes staging/prod | **Reemplazada** | Compose de cuatro servicios en la máquina del usuario, puertos solo en loopback, migraciones automáticas al arranque, CI que valida y no despliega. Ver R-20 |
| **Proveedor único (Gemini)** implícito en todo el pipeline | **Reemplazada** | Generación y embeddings se configuran de forma independiente, con matriz de capacidades declarada como dato y preflight de primera clase. Ver R-22, R-23, R-25 |
| **Sentry** en backend y frontend (R-20, Constitution Check) | **Eliminada** | Prohibido por defecto (art. VIII v2.1.0): errores en logs locales estructurados. Ver R-13 |

Las decisiones que el pivote **no** invalidó —extracción de texto, detección de escaneados y de no-CV, marcado de incompletitud, versionado por hash canónico, transición de orígenes, reintento aditivo, presupuesto de latencia, golden set, sincronía del cliente TS, objetivos en columnas tipadas, paso derivado y concurrencia de edición— se conservan con su numeración y con las referencias a FR actualizadas a la numeración de la spec reescrita.

---

## R-01 · Validación y detección del tipo real del archivo (FR-016, FR-017)

**Decisión.** Validación en tres capas, todas **antes** de encolar:

1. **Tamaño**: rechazo por `Content-Length` y, además, corte duro durante la lectura del stream al superar `MAX_UPLOAD_BYTES` (10 MB, configurable). No confiar en la cabecera sola.
2. **Tipo real por firma de bytes**, no por extensión ni por `Content-Type` del cliente: PDF debe empezar con `%PDF-`; DOCX es un ZIP (`PK\x03\x04`) que debe contener `word/document.xml` y declarar el content type de WordprocessingML. La extensión y el `Content-Type` se ignoran para decidir.
3. **Legibilidad**: apertura efectiva con `pypdf` / `python-docx` dentro de un `try`. Si la librería no puede abrir el documento → `DOCUMENT_CORRUPT`.

**Rationale.** Los tres modos de fallo que la spec exige rechazar (tamaño, formato no soportado, corrupción) tienen causas distintas y mensajes distintos; distinguirlos por reglas es determinista y barato. La firma de bytes es la única señal que un cliente no controla.

**Alternativas consideradas.**
- `python-magic` (libmagic): dependencia con binario del sistema para dos firmas que caben en 15 líneas. Descartada por art. VII.
- Confiar en la extensión: trivialmente falsificable, y un `.pdf` que en realidad es una imagen produciría un perfil basura, justo lo que SC-008 y SC-009 prohíben.
- Validar solo en el worker: dejaría al candidato esperando 30 s para recibir un "tu archivo no sirve". El rechazo debe ser síncrono (FR-017: "antes de procesar").

---

## R-02 · Extracción de texto y CVs a dos columnas o con tablas (US2 AC5, edge case)

**Decisión.**
- **PDF**: `pypdf.PageObject.extract_text(extraction_mode="layout")`, que preserva la disposición espacial en vez de concatenar por orden de flujo interno. Se conserva un salto de página explícito entre páginas.
- **DOCX**: recorrer `document.element.body` en orden de documento e ir emitiendo párrafos y tablas según aparecen; las tablas se serializan fila por fila con separador de celda explícito. **No** basta con `document.paragraphs`: omite todo el contenido dentro de tablas, y una fracción relevante de los CVs del mercado maqueta con tablas invisibles.
- El texto resultante se pasa íntegro al extractor, con marcas de estructura (saltos de página, límites de tabla) intactas.

**Rationale.** El modo `layout` de pypdf reduce la intercalación de columnas sin sumar dependencias; el resto de la robustez la aporta el modelo, que lee texto con estructura mucho mejor que texto barajado. Lo que no se puede estructurar con confianza no se inventa: cae en la regla de completitud de R-05 y llega al candidato marcado como incompleto, que es exactamente lo que pide el escenario US2 AC5.

**Alternativas consideradas.**
- `pdfplumber` con detección de columnas por análisis de cajas: más preciso en el caso difícil, ~3× más lento y añade `pdfminer.six`. Reevaluable si las evals muestran que la columna es la fuente principal de error.
- `PyMuPDF`: el mejor extractor del ecosistema. Su licencia AGPL es compatible con la de Vokara (ADR-010), pero ataría la licencia de cualquier redistribución posterior a cambio de una ventaja que aquí no es decisiva.
- Convertir DOCX a PDF y usar un solo camino: añade LibreOffice al contenedor por una simplificación de código menor, y engorda la imagen que el usuario descarga (art. VII).

---

## R-03 · Detección de PDF escaneado sin capa de texto (FR-021, SC-009)

**Decisión.** Heurística determinista, configurable y probada, evaluada tras la extracción de texto y antes de cualquier llamada al LLM:

```
scanned  ⇔  total_chars < MIN_DOC_CHARS  (por defecto 200)
             OR  (páginas con < MIN_PAGE_CHARS (50) caracteres) / total_páginas ≥ 0.8
```

Un PDF que cae en esta condición produce el error `PDF_WITHOUT_TEXT_LAYER`, cuyo mensaje explica que v1 no procesa documentos escaneados y ofrece la captura manual guiada (FR-022). El documento queda registrado y el binario conservado; el perfil no se toca.

**Rationale.** Un PDF escaneado sí tiene páginas y sí abre correctamente: lo que no tiene es texto. La señal es la densidad de caracteres, no la validez del archivo. Los umbrales viven en la configuración, nunca como constantes en código, y se calibran con el golden set, que incluirá al menos dos PDFs escaneados sintéticos.

**Casos límite cubiertos por los tests.** PDF híbrido (portada escaneada + resto con texto) → no se marca como escaneado si supera el umbral global; PDF de una página con muy poco texto real (CV minimalista) → cae en "contenido mínimo", que es otro camino con su propio mensaje, no un falso "escaneado".

**Alternativas consideradas.**
- Contar imágenes de página completa: más frágil (hay CVs de diseño con fondos a sangre y capa de texto perfecta).
- Intentar la extracción y dejar que el clasificador LLM decida: quema una llamada, es no determinista y contradice el art. III para una decisión que se resuelve contando caracteres.
- Añadir OCR de respaldo: prohibido por FR-021 en v1. Su reevaluación exige ADR propio si introduce una dependencia nueva.

---

## R-04 · Detección de "no es un CV" (FR-020, SC-008)

**Decisión.** Paso de clasificación propio, con salida estructurada:

```python
class DocumentClassification(BaseModel):
    is_resume: bool
    document_kind: Literal["resume", "invoice", "contract", "letter", "academic_paper", "other"]
    reason_es: str          # explicación corta, sin PII, para el mensaje al candidato
```

Se ejecuta sobre los primeros `CLASSIFIER_CHARS` (por defecto 6.000) del texto extraído. Si `is_resume` es falso, el pipeline se detiene con `DOCUMENT_NOT_A_RESUME`, **sin crear ninguna entrada** y sin ejecutar la extracción cara.

**Rationale.** Separarlo de la extracción tiene tres ventajas medibles: corta el costo cuando el documento no sirve —que en local lo paga el usuario, no el proyecto—, hace que el fallo sea diagnosticable (sabemos *qué* creyó el modelo que era), y produce una métrica de eval independiente con casos negativos sembrados: factura, contrato, carta, artículo. El art. III se respeta porque el modelo devuelve un booleano tipado y es el **servicio** quien decide el flujo.

**Alternativas consideradas.**
- Un solo prompt que extrae y además marca `is_resume`: ahorra una llamada, pero paga tokens de extracción sobre documentos inútiles y mezcla dos métricas de eval en un solo número.
- Heurística de palabras clave ("experiencia", "educación", "skills"): falsos negativos altísimos en CVs muy visuales o en inglés, falsos positivos en cartas de presentación.

---

## R-05 · Extracción a entradas y marcado de incompletitud (FR-024, FR-027, FR-028)

**Decisión.** Una única llamada `with_structured_output(SeededProfile)`. En el esquema, **todos** los campos que el documento puede no traer son `Optional` con `None` por defecto, y el prompt es explícito: "si el dato no aparece literalmente en el documento, devuelve `null`; nunca lo infieras". Cada entrada devuelve además `language` (ISO 639-1) y `source_excerpt` (fragmento literal del que salió).

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

**Rationale.** La regla de completitud es el mecanismo por el que FR-028 se cumple sin depender de la buena voluntad del modelo: como el esquema permite `null` y las reglas detectan el `null`, la salida natural ante un dato ausente es "entrada incompleta", no "dato inventado". Esta es además exactamente la propiedad que el ADR-011 eligió como criterio de aceptación de un proveedor —"respeta `null` en opcionales"—, de modo que el preflight (R-23) y el pipeline miden lo mismo. `source_excerpt` es barato y hace las evals auditables ("¿de dónde salió esto?"), además de habilitar en la UI el "ver en el CV" que reduce la fricción de revisión.

**Alternativas consideradas.**
- Pedirle al modelo un `confidence` por entrada: números que ningún LLM calibra bien y que acabaríamos umbralizando a ciegas. La ausencia de campo clave es una señal objetiva y verificable.
- Campos obligatorios en el esquema con valores centinela ("N/A", "Desconocido"): fabrica exactamente el dato falso que el art. IV prohíbe.
- Una llamada por tipo de entrada: 7× costo y latencia; el contexto completo del CV mejora la extracción, no la empeora.

---

## R-06 · Almacenamiento del binario: `StoragePort` sobre filesystem local (FR-018, ADR-007)

**Decisión.** Puerto `StoragePort` con cuatro operaciones —`put` / `get` / `delete` / `exists`— y **una sola implementación en v1: filesystem local**. Los archivos viven en el directorio de datos de la instalación; `documents` persiste la `storage_key`, nunca el binario. **Sin cifrado en reposo.**

- La ruta del directorio es **configurable** (`VOKARA_DATA_DIR`) con default sensato por sistema operativo; en Windows, dentro de WSL2 (ADR-000).
- `storage_key` **nunca** se expone en ninguna respuesta de la API ni en ningún mensaje de error (roadmap §11.5: nada de `FileNotFoundError: /data/...`).
- `exists` no es decorativo: el edge case "el directorio de datos desapareció" se resuelve con él, y el error correspondiente es `STORAGE_UNAVAILABLE` con un mensaje que dice que el perfil sigue intacto y que el archivo original no puede reprocesarse.

**Rationale (ADR-007).** El cifrado se retira porque **no protege contra ninguna amenaza real en una instalación local**: la clave maestra viviría en un `.env` junto a los datos que protege, legible por el mismo usuario y por cualquier proceso que corra como él. Quien pueda leer los documentos cifrados puede leer la clave; el cifrado no añade una barrera, añade un paso. El crypto-shredding pierde sentido por lo mismo: en local no hay réplicas ni backups ajenos que perseguir, borrar es `delete` sobre un archivo. Contra la amenaza que **sí** es real —robo o pérdida del equipo— la respuesta correcta es el cifrado de disco del sistema operativo, que guarda la clave fuera del disco y protege el equipo entero; Vokara lo recomienda en el README y **divulga el riesgo en el paso 0 del wizard** (FR-001d) en vez de implementar una versión peor del mismo mecanismo.

El puerto se conserva aunque hoy tenga una sola implementación porque es lo que permite que S3/MinIO —y con él el cifrado— entren después sin tocar `services/`, que no debe saber si detrás hay un disco o un bucket.

**Alternativas consideradas.**
- **S3/MinIO + cifrado de sobre** (la propuesta anterior de este documento): obligaría a cada usuario a levantar un MinIO en su máquina para guardar archivos en un disco que ya tiene, y a gestionar una clave maestra que no protege nada. Un servicio más en el Compose contra el criterio de fricción del art. VII, a cambio de seguridad aparente. **Diferido, no descartado**: si llega un despliegue multiusuario, las premisas vuelven a cumplirse y este diseño es el punto de partida.
- **Cifrar con clave derivada de una contraseña del usuario**: la única variante que daría cifrado real en local, porque el secreto viviría en su cabeza. Descartada por costo de UX: obliga a introducirla en cada arranque, rompe el procesamiento en background (el worker necesitaría la clave en memoria) y perderla significa perder el perfil sin recuperación. Requiere ADR propio si se retoma.
- **Guardar el binario en Postgres (`bytea`)**: evita el puerto, pero infla la base y los dumps, complica el backup del usuario —que es copiar un directorio— y hace peor un trabajo que el filesystem hace bien.

---

## R-07 · Ejecución asíncrona, exposición del progreso y unicidad del trabajo (FR-019, edge cases)

**Decisión.**
- `POST /documents` responde **202** con `document_id` y `parse_job_id`; la tarea Celery se encola **después** del commit de la transacción, para que el worker nunca vea una fila que aún no existe.
- Progreso por **polling**: `GET /parse-jobs/{id}` devuelve `status` (`queued` | `running` | `succeeded` | `failed`), `progress_percent` y `step` (`extracting_text` | `classifying` | `extracting_entries` | `persisting`). El front usa `refetchInterval: 2000` de TanStack Query mientras el estado no sea terminal.
- **Un solo trabajo activo por candidato**, garantizado en base de datos con índice único parcial:
  `CREATE UNIQUE INDEX ... ON parse_jobs (candidate_id) WHERE status IN ('queued','running')`.
- **Idempotencia ante reentrega**: la tarea toma el trabajo con `UPDATE parse_jobs SET status='running' WHERE id=:id AND status='queued'`; si no afecta filas, otra ejecución ya lo tomó y la tarea termina sin hacer nada.
- **Reaper al arranque**: al iniciar, la API marca como `failed` con `error_code = EXTRACTION_FAILED` (reintentable) cualquier trabajo que siga en `running` sin worker vivo. En una instalación local, apagar el equipo a media ejecución es un escenario ordinario, no excepcional.
- Las entradas sembradas se escriben en **una sola transacción al final**. Un trabajo fallido deja cero entradas, lo que hace que el reintento de FR-023 sea una simple inserción y no una reconciliación.

**Rationale.** El polling cada 2 s sobre un recurso ya modelado cuesta una consulta por índice primario y no añade infraestructura; SSE o WebSocket exigirían mantener conexión, afinidad de proceso y un camino de reconexión, para un flujo que dura menos de un minuto y ocurre una vez por candidato (art. VII). Que el candidato cierre el navegador y vuelva funciona gratis: el estado vive en la base, no en la conexión.

**Alternativas consideradas.**
- SSE: reevaluable cuando llegue el simulador de entrevistas, que sí lo necesita (roadmap §4.2).
- Long polling: peor relación complejidad/beneficio que refrescar cada 2 s.
- Semáforo en Redis para la unicidad: un `SETNX` puede quedar huérfano si el worker muere; el índice parcial no puede desincronizarse del estado real porque **es** el estado real.

---

## R-08 · Versionado, hash canónico y "cambios sin confirmar" (FR-040 – FR-044)

**Decisión.**
- Cada confirmación inserta una fila en `profile_versions` con `version_number` monotónico por perfil, `origin='confirmation'`, `content` (JSONB con entradas vivas + objetivos) y `content_hash` (SHA-256 de la serialización canónica).
- **Inmutabilidad real**: trigger de Postgres que aborta cualquier `UPDATE` o `DELETE` sobre la tabla. El repositorio tampoco expone métodos de escritura.
- **Serialización canónica** (`domain/canonical.py`): claves ordenadas, sin espacios superfluos, fechas ISO-8601, entradas ordenadas por `id`. Es la única forma de que dos snapshots iguales produzcan el mismo hash.
- `has_unconfirmed_changes` **se deriva**: `hash(trabajo_en_curso) != current_version.content_hash`. No existe columna booleana.
- El detalle de FR-044 ("en qué consisten") lo calcula `domain/diff.py` comparando por `id` contra el snapshot vigente: entradas añadidas, modificadas (con lista de campos), eliminadas y cambios de objetivos.

**Rationale.** Una bandera booleana es correcta solo mientras todo servicio que muta el perfil se acuerde de actualizarla; el día que uno lo olvide, FR-043 se rompe en silencio y sirve trabajo en curso al resto del producto. El hash derivado no puede desincronizarse y además maneja gratis el caso "edité y deshice", que con bandera quedaría reportando cambios inexistentes. El costo es despreciable a esta escala (decenas de entradas, hash en microsegundos).

**Alternativas consideradas.**
- Tabla de eventos de cambio: auditoría más rica, pero es una tabla que nadie consume en 001 (art. VII) y el diff contra el snapshot ya responde la pregunta del usuario.
- Versionado por filas con `valid_from`/`valid_to` en `profile_entries`: modelo temporal completo, mucha más complejidad en cada consulta, y FR-041 solo pide recuperar el contenido íntegro de una confirmación pasada — que es justo lo que un snapshot hace mejor.
- Guardar solo el diff por versión: reconstruir requiere replay y una versión corrupta rompe todo el histórico.

---

## R-09 · Transición de origen de las entradas (FR-026, FR-031)

**Decisión.**
- `cv_seed` → `user_edited` **solo si el contenido cambia de verdad** (comparación del contenido canónico antes/después; un guardado sin cambios no altera el origen).
- `user_added` permanece `user_added` al editarse.
- `user_edited` permanece `user_edited`.
- El `id` nunca cambia (FR-025).

**Rationale.** FR-031 se lee literalmente como "editar cualquier entrada la vuelve `user_edited`", pero el escenario de aceptación US3.1 solo describe la transición desde `cv_seed`, y convertir una entrada creada por el candidato en `user_edited` **destruiría información**: dejaría de constar que la escribió él desde cero. La feature 007 protege por igual a `user_edited` y `user_added` frente a la fusión, así que la distinción no cambia ninguna decisión aguas abajo y sí conserva la procedencia real. SC-002 se cumple igualmente: los tres valores existen y toda entrada tiene uno.

**Registro explícito.** Es una interpretación del plan, no un cambio de la spec. Si producto prefiere la lectura literal, se ajusta en una línea de `entry_service.py` — pero se perdería la trazabilidad de qué escribió el candidato de su puño.

---

## R-10 · Reintento tras fallo sin perder trabajo manual (FR-023)

**Decisión.** `POST /parse-jobs/{id}/retry` solo se acepta si el trabajo está en `failed`. Crea un `parse_job` **nuevo** sobre el **mismo** documento (el binario ya está guardado y validado: no se re-sube nada) y hereda `retry_of_job_id` para la auditoría. La siembra es **estrictamente aditiva**: nunca borra ni pisa entradas existentes.

Como un trabajo fallido no deja entradas (transacción única, R-07), el reintento no puede duplicar nada. Las entradas que el candidato haya creado a mano mientras tanto (`user_added`) quedan intactas por construcción, no por una comprobación.

Este es también el camino del edge case "el proveedor rechaza la llave o agota la cuota durante el parseo": el `parse_job` termina en `failed` con un código accionable que apunta a la configuración de proveedores, el archivo subido no se pierde y el reintento está disponible en cuanto el usuario corrija.

**Rationale.** El requisito "sin perder entradas creadas o editadas manualmente" se satisface por diseño del pipeline, que es más fuerte que satisfacerlo con una salvaguarda que alguien puede quitar en una refactorización.

**Alternativas consideradas.**
- Reintento automático con backoff dentro de Celery: útil para fallos transitorios del proveedor y **sí** se aplica dentro de la llamada al adapter (3 intentos con backoff exponencial ante error de red o 429). Lo que no se automatiza es el reintento del trabajo completo tras un fallo definitivo: FR-023 lo pone en manos del candidato, y un reintento silencioso ocultaría un fallo sistemático de extracción — y, en local, gastaría su cuota sin que él lo decidiera.
- Permitir reintento sobre un trabajo `succeeded`: eso es reprocesamiento, y pertenece a las features 006/007. Se rechaza con `409`.

---

## R-11 · Identidad local sin autenticación (FR-003, FR-049, ADR-008)

**Decisión.** No hay registro, login, sesiones ni tokens. La identidad se resuelve así:

- La migración inicial siembra **una** fila en `candidates` con un `candidate_id` fijo de la instalación.
- `api/deps.py` expone una dependencia `local_candidate_id` que lo resuelve **desde configuración local**. Ningún endpoint lo acepta como parámetro, ni en ruta, ni en query, ni en cuerpo, ni en cabecera (FR-003).
- **Todo repositorio recibe `candidate_id` explícito en su firma**, aunque hoy solo exista un valor posible. Añadir autenticación mañana significa cambiar de dónde sale ese valor —hoy de configuración, mañana de un token—, no reescribir la capa de datos.
- Los tests de repositorio verifican el filtrado **con dos `candidate_id` distintos**, sembrando datos de ambos. Es lo que convierte la disciplina en algo ejecutable en vez de un acuerdo verbal (ADR-008, "Costos y riesgos").
- Un recurso que no pertenece al `candidate_id` en curso responde **404, nunca 403**: no se revela la existencia de recursos ajenos.

**Y la mitigación que sostiene todo lo anterior**: sin autenticación, **dónde escucha la instancia es el único control de acceso que existe**. Se verifica con los dos tests del ADR-008, detallados en R-20.

**Rationale.** Autenticar sería pedirle a alguien que se identifique ante su propia computadora (ADR-008): 4–6 días de desarrollo en código donde los errores son de seguridad, para proteger a un usuario de sí mismo. Lo que sí se conserva —el `candidate_id` explícito— cuesta un parámetro hoy y evita una migración de la capa de datos entera mañana.

**Alternativas consideradas** (todas descartadas en el ADR-008, se listan por trazabilidad).
- **PIN o contraseña local al abrir la app**: sería un bloqueo de UI, no cifrado; los datos siguen en claro en el disco. El problema no es que proteja poco, es que **comunica una protección que no existe** y cambia el comportamiento del usuario en la dirección equivocada.
- **Mantener el ADR-001 "por si acaso"**: toda la superficie de seguridad sin su justificación, y un registro obligatorio antes de usar un programa que ya corre en la propia máquina.
- **Multiusuario local**: quien comparte computadora tiene cuentas del sistema operativo, que separan datos mejor de lo que lo haría Vokara.

---

## R-12 · Embeddings en 001: puerto y preflight sí, vectores no (ADR-003, ADR-011, art. VII)

**Decisión.** Se entregan el puerto `EmbeddingsPort` y su implementación Google, **y su preflight**, porque el wizard configura los dos proveedores por separado y verificar el de embeddings es un requisito funcional (FR-004, FR-006, FR-007.2: la dimensión del vector queda registrada). **No** se persiste ningún vector en 001 porque no existe consumidor: el matching es F1.5 y la normalización de skills es ADR-004, ambos fuera de alcance.

La regla del ADR-003 —cada vector persiste `embedding_model` y `embedding_dim`, con convivencia de dos modelos durante una migración— queda escrita como **convención vinculante** en `data-model.md`, y la extensión `pgvector` se habilita en la primera migración para que la feature que estrene vectores no tenga que tocar la infraestructura.

Nota de la verificación del ADR-011: `gemini-embedding-001` devuelve **3072** dimensiones por defecto y soporta truncado MRL vía `output_dimensionality`; Vokara lo fija en **768** para ahorrar espacio en pgvector sin pérdida relevante de calidad. Ese valor se registra junto al resultado del preflight y, en el futuro, junto a cada vector.

**Rationale.** Crear hoy una tabla de embeddings vacía sería infraestructura sin consumidor (art. VII) y, peor, congelaría una decisión de forma (columna vs. tabla por modelo) sin saber aún si el vector va por entrada, por perfil o por ambos. Lo que sí hay que fijar hoy —y se fija— es que el puerto exista, que su preflight funcione y que la regla de persistencia esté escrita antes de que alguien escriba el primer `vector(768)`.

**FR-010 es explícito al respecto**: la ausencia de proveedor de embeddings verificado **nunca** bloquea el onboarding; degrada de forma explícita e informada funciones que quedan fuera de esta feature.

**Alternativas consideradas.**
- Crear ya `profile_entry_embeddings` y poblarla al sembrar: costo de LLM por cada entrada de cada candidato —pagado por él— sin nadie que lea el resultado.
- No pedir el proveedor de embeddings en el wizard y diferirlo a la feature de matching: contradice el ADR-011 y FR-004, y reintroduce exactamente lo que ese ADR evita — descubrir a mitad del uso que el proveedor elegido no ofrece la capacidad.

---

## R-13 · Trazado de llamadas LLM sin filtrar PII (art. VIII, art. V, FR-045, FR-046)

**Decisión.** El decorador de trazado del adapter registra, por llamada: `model`, `prompt_version`, `input_tokens`, `output_tokens`, `estimated_cost_usd`, `latency_ms`, `attempt`, `outcome` y `parse_job_id`. **Nunca** el prompt, el texto del CV ni la salida. El registro va a structlog y a la tabla `llm_call_logs`. Los logs pasan además por un procesador de structlog que elimina claves sensibles conocidas —incluidas las de credenciales— y trunca cualquier valor de texto libre.

**Sin Sentry y sin plataformas de trazas de LLM.** Los errores se capturan en **logs locales estructurados**; enviarlos a un servicio externo exigiría el opt-in explícito del art. V y está desactivado de fábrica (art. VIII v2.1.0). Langfuse, LangSmith y equivalentes quedan **descartadas**, hospedadas o auto-alojadas: su valor está justamente en guardar el contenido de los prompts, y un prompt de Vokara lleva el CV íntegro, es decir PII de principio a fin (ADR-003).

**Rationale.** Los artículos VIII y V no chocan realmente: el art. VIII pide costo, latencia y versión de prompt, y eso es exactamente lo que se traza. Enviar los cuerpos a un tercero es lo que el art. V prohíbe, y no es necesario para nada de lo que el art. VIII exige. En ejecución local estas trazas son además **para el usuario**: son el sustrato del "costo real acumulado" del roadmap §11.3, que llegará en otra feature. La contrapartida —depurar un prompt sin ver la entrada que lo rompió— se asume y se resuelve reproduciendo con el golden set, que es material sintético y sí puede inspeccionarse.

**Alternativas consideradas.**
- Redacción de PII antes de enviar a un observador externo: la redacción fiable de un CV completo (nombres, empresas, escuelas, ciudades) es un problema abierto, y aquí una fuga sería la del propio usuario, no la nuestra.
- Trazar solo cuando falla: perdemos la línea base de costo y latencia, que es justo lo que el art. VIII quiere y lo que el usuario necesita para saber cuánto lleva gastado.

---

## R-14 · Presupuesto de latencia para SC-004 (< 60 s p95)

**Decisión.** Presupuesto por etapa, medido en las evals y verificado en `quickstart.md`:

| Etapa | Objetivo p95 | Nota |
|---|---|---|
| Subida + validación + `put` al filesystem local | 3 s | 10 MB por la API; sin cifrado que pagar (ADR-007) |
| Encolado → worker toma la tarea | 2 s | worker con concurrencia ≥ 2 |
| Extracción de texto (PDF/DOCX) | 3 s | pypdf modo layout, 10 páginas |
| Clasificación (modelo rápido, 6k chars) | 4 s | |
| Extracción estructurada (CV completo) | 30 s | etapa dominante |
| Reglas de completitud + persistencia | 1 s | una transacción |
| Latencia de polling hasta que la UI lo refleja | 2 s | intervalo de 2 s |
| **Total** | **45 s** | **15 s de margen sobre los 60 s de SC-004** |

Si un CV supera `MAX_EXTRACTION_CHARS` (por defecto 120.000 caracteres — un CV de 10 páginas ronda los 30.000), se trunca conservando el inicio del documento y se marca el `parse_job` con `truncated=true`, que la UI comunica al candidato para que revise con más atención. No se trocea ni se paraleliza: el troceo introduce el problema de fusionar entradas duplicadas entre trozos, que es precisamente el problema difícil de la feature 007.

**Rationale.** El presupuesto convierte SC-004 en algo medible por etapa: si un día se incumple, la eval dice cuál etapa se salió, no solo que "va lento". La latencia observada en la verificación del ADR-011 (1,54 s para una extracción con esquema anidado sobre un CV corto) sugiere que los 30 s de la etapa dominante son holgados para el caso típico.

---

## R-15 · Golden set y evals bloqueantes (art. VI, SC-003, FR-047, FR-048)

**Decisión.**
- Ubicación: `backend/tests/evals/golden_set/`, con `<caso>.pdf|docx` + `<caso>.expected.json` versionados en el repo.
- Composición inicial: **12 casos** — 6 CVs sintéticos en español (uno a dos columnas, uno con tablas), 2 en inglés, 1 mixto, 1 PDF escaneado, 1 documento que no es CV (factura), 1 CV mínimo de contenido escaso. Se amplía hacia los 30–50 del roadmap §6.4 conforme avance la Fase 2.
- **Procedencia (FR-047, FR-048)**: material sintético o del propio equipo. Un `CODEOWNERS` sobre el directorio y una nota en su README dejan constancia de que añadir material de un usuario real requiere **ADR propio y consentimiento opt-in separado, explícito y revocable**, y que **nunca** puede habilitarse modificando el texto de divulgación ni apoyándose en el acuse del paso 0. En ejecución local esto es además una imposibilidad arquitectónica: el equipo no tiene acceso a los datos de nadie.
- Métricas: tasa de error por campo (**bloqueante en < 5%**, SC-003), precisión y recall del clasificador de "no es CV" (bloqueante en 100% sobre los negativos del set, SC-008), detección de PDF sin capa de texto (bloqueante en 100%, SC-009), y una métrica de **invención**: campos presentes en la salida cuyo valor no aparece en el texto fuente → bloqueante en 0 (art. IV).
- **Reproducibilidad sin parámetros de muestreo**: el modelo bajo prueba se fija **en configuración** (nunca en una constante) y su nombre queda registrado en el resultado de cada corrida, junto con la versión de prompt. Lo que verifica que la salida sigue siendo aceptable son estas métricas, no la presencia de un parámetro (ADR-003).
- **Portabilidad ejecutable (art. XI)**: la suite está parametrizada por proveedor y toma el que indique la configuración. Hoy solo hay uno implementado, así que corre contra Google; el día que exista el segundo, correrla contra él es cambiar una variable de entorno, no escribir una suite nueva.
- CI: el golden set **completo** en todo PR que toque `adapters/llm/`, `services/extraction_service.py`, `domain/completeness.py` o el propio golden set; subconjunto de humo de 3 casos en el resto. Ambos bloqueantes. Requiere una API key en los secretos del repositorio.

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

## R-17 · Ubicación y validación del cuestionario de objetivos (FR-035 – FR-037)

**Decisión.** Columnas tipadas en `candidate_profiles`, no JSONB: `target_role`, `salary_min`, `salary_max`, `salary_currency`, `remote_preference` (enum `onsite|hybrid|remote|any`), `locations text[]`, `industries text[]`, `deal_breakers text[]`. Validación en dos niveles: Pydantic en la frontera (mensaje en español, FR-036) y `CHECK` en la base (`salary_min <= salary_max`, moneda de tres letras mayúsculas del conjunto permitido).

**Rationale.** Los objetivos son datos consultados por el matching (F1.5) y con validaciones de negocio reales; en columnas son verificables por la base y agregables sin desenrollar JSON. El `CHECK` es la red que impide que un camino futuro (import, script de mantenimiento) salte la validación de Pydantic. Las listas van como `text[]` en vez de tablas hijas porque no tienen atributos propios ni relaciones (art. VII); si mañana una ubicación necesita país y coordenadas, se promueve a tabla.

---

## R-18 · Paso derivado, no persistido — wizard y onboarding (FR-014, US3 AC5)

**Decisión.** Dos pasos derivados por reglas puras, ninguno persistido como "paso actual":

**Primera ejecución** — `GET /setup/state` devuelve `pending_step`:

```
sin acuse de divulgación vigente                → "disclosure"
sin proveedor de generación resuelto            → "providers"
paso de correo pendiente (ni vinculado ni omitido) → "email"
resto                                            → null  (primera ejecución concluida)
```

**Onboarding** — `GET /profile` devuelve `onboarding_step`:

```
primera ejecución no concluida       → "setup"
sin documento y sin entradas         → "upload"
parse_job activo                     → "processing"
último parse_job failed              → "processing_failed"
entradas > 0 y objetivos incompletos → "objectives"
objetivos completos y state=draft    → "confirm"
state=complete                       → "done"
```

**Matiz importante y deliberado.** El **avance** del wizard sí se persiste —acuse con su marca de tiempo y la versión del texto acusado, resultado del preflight de cada capacidad, acuse de degradación, estado del paso de correo— porque FR-014 lo exige literalmente: al reabrir hay que retomar en el paso pendiente sin volver a pedir el acuse ni las credenciales ya verificadas. Lo que **no** se persiste es el puntero "voy en el paso 2": ese se calcula a partir de los hechos registrados. La diferencia importa: un puntero se desincroniza (el usuario cambia de proveedor, una credencial se invalida), los hechos no.

**Rationale.** Un campo persistido de "paso actual" se desincroniza del estado real en cuanto algo pasa fuera del flujo previsto (el candidato borra su última entrada, un trabajo falla, vuelve dos semanas después, rota su API key). Derivarlo lo hace auto-reparable y elimina una columna que ningún requisito pide. La UI navega a la ruta que corresponde a ese valor, así que "retomar donde iba" sale gratis y siempre correcto — que es exactamente lo que miden SC-015 y el escenario US1.12.

---

## R-19 · Concurrencia y guardado del trabajo de revisión (FR-034)

**Decisión.** Guardado explícito por entrada (`PATCH /profile/entries/{id}` al enviar el formulario de esa entrada), con semántica de **último escritor gana**. Sin bloqueo optimista, sin autosave por pulsación de tecla. TanStack Query invalida la lista tras cada mutación.

**Rationale.** El único editor de un perfil es el dueño de la instalación, y hay **una sola** instalación por persona (ADR-008); el conflicto realista es "dos pestañas abiertas", cuyo daño máximo es perder una edición que el candidato acaba de hacer y ve delante. Añadir `If-Match` con `ETag` es correcto pero paga complejidad en cada endpoint y en el cliente para un escenario marginal. Se documenta como decisión consciente y se reevalúa si aparece edición colaborativa (que hoy no está ni en el roadmap, y que el modelo local-first hace improbable).

---

## R-20 · Contenedores, Compose local, binding y CI (ADR-008, ADR-009, roadmap §9 y §11.1)

**Decisión.**

**Compose de cuatro servicios y ni uno más**: `api`, `worker`, `postgres` (imagen `pgvector/pgvector:pg16`, tag fijo) y `redis`. Sin MinIO, sin reverse proxy, sin ambientes remotos.

**Todo puerto publicado lleva IP de host loopback explícita:**

```yaml
services:
  api:
    ports: ["127.0.0.1:8000:8000"]     # NUNCA "8000:8000"
  web:
    ports: ["127.0.0.1:5173:5173"]     # NUNCA "5173:5173"
```

`postgres` y `redis` **no se publican en absoluto**: los servicios se alcanzan por la red interna de Compose. La forma corta `"8000:8000"` publica en todas las interfaces (Docker asume `0.0.0.0`), y **el firewall del host no lo detiene**: las reglas de Docker en la cadena `DOCKER` de la tabla `nat` se evalúan antes que las de `ufw`/`firewalld`. Un `ufw deny 8000` no protege un puerto publicado por Docker.

**Los dos tests del ADR-008, y son dos porque cubren cosas distintas:**

```python
# tests/integration/test_local_binding.py
def test_compose_publishes_only_on_loopback() -> None:
    """Todo puerto publicado en docker-compose.yml fija una IP de host loopback."""
    # Por cada `ports:` de cada servicio: la entrada debe traer IP de host
    # explícita, y ipaddress.ip_address(host_ip).is_loopback debe ser True.
    # Falla tanto con "8000:8000" (sin IP) como con "0.0.0.0:8000:8000".
    # Alcance: también docker-compose.override.yml.

def test_api_host_setting_resolves_to_loopback() -> None:
    """El host configurado para uvicorn fuera de Docker resuelve a loopback."""
    # socket.getaddrinfo(settings.api_host, None) → TODAS las direcciones
    # resueltas cumplen is_loopback. "localhost" pasa (127.0.0.1 y ::1);
    # "0.0.0.0" falla (is_unspecified, no is_loopback).
```

La asimetría que los hace necesarios a los dos: **dentro del contenedor, uvicorn DEBE escuchar en `0.0.0.0`** o el proxy de Docker no lo alcanza. En el despliegue con Compose la protección no la da el bind de la aplicación —que por fuerza es abierto— sino **exclusivamente el mapeo de puertos**. El segundo test cubre el otro modo: ejecutar la API directamente en la máquina, donde sí es el bind lo que protege. Solo el del bind rompería el arranque en contenedor; solo el del Compose dejaría el modo local sin cubrir.

**Migraciones automáticas al arranque** (roadmap §11.1): el entrypoint del contenedor `api` ejecuta `alembic upgrade head` antes de levantar uvicorn. El usuario nunca ejecuta un comando de Alembic, ni en la primera instalación ni al actualizar. Las migraciones deben **soportar saltos de varias versiones**: actualizar depende del usuario (`git pull`), así que habrá instalaciones meses atrasadas y una migración que solo funcione desde la anterior inmediata es un bug (ADR-009).

**Un solo comando después de clonar**: `docker compose up` debe funcionar **sin edición manual de archivos** más allá de lo que el wizard pide después. Nada de "copia el `.env.example`, edita ocho variables y corre las migraciones": la API key la pide el wizard, no el `.env`.

**Versiones fijadas** en todas las máquinas: `.python-version`, `uv.lock`, `.nvmrc`, `package-lock.json`, tags de imagen fijos, y `.gitattributes` con `* text=auto eol=lf` desde el primer commit (WSL2 + macOS, ADR-000).

**CI (GitHub Actions) valida, no despliega** (roadmap §9), todo bloqueante: `ruff check` + `ruff format --check` → `mypy --strict` → `pytest` (unit + integración con testcontainers, **incluidos los dos tests de binding**) → reversibilidad de migraciones → drift del cliente TS → `vitest` → evals → build de imágenes → **prueba de instalación limpia** (levantar el Compose desde cero y verificar que la app responde) → verificación de licencias de dependencias (AGPL-3.0, ADR-010).

**Rationale.** La fricción de instalación es criterio constitucional (art. VII) y el riesgo nº 1 del modelo local-first: cada obstáculo entre `git clone` y el primer uso equivale a una feature que no existe. Los tests de binding no son un criterio de revisión de PR sino un requisito verificable, porque un puerto publicado en `0.0.0.0` sin autenticación detrás es un bug de seguridad, no un detalle de configuración. Las trampas multiplataforma del ADR-000 (CRLF, bind mounts lentos) se cierran desde el primer commit porque son la clase de bug que aparece "en la otra máquina" y cuesta un día encontrar.

---

## R-21 · Configuración y manejo de credenciales (FR-008, FR-013, art. V)

**Decisión.** `pydantic-settings` con precedencia **entorno > archivo `.env` > defaults**, tipado y validado al arranque.

- Toda credencial —API key de generación, API key de embeddings, App Password— se declara como `SecretStr`. Su `repr` es `**********`, así que un log accidental del objeto de configuración no la filtra.
- **Nunca se persisten en la base de datos** (FR-008, FR-013). La única huella que dejan es el `credential_fingerprint` de R-24, que es un digest, no la credencial ni un fragmento suyo.
- **Nunca aparecen en respuestas de la API**: el estado consultable de una credencial se limita a `configured | not_configured | rejected`, y ese enum es todo lo que el contrato HTTP expone (roadmap §11.4: "nunca muestra credenciales, ni siquiera parcialmente").
- El procesador de structlog de R-13 elimina claves sensibles conocidas por nombre y trunca texto libre, como segunda red.
- **Los nombres de modelo van en configuración, con override por variable de entorno** (`VOKARA_GOOGLE_MODEL`, `VOKARA_GOOGLE_EMBEDDING_MODEL`), **nunca en constantes de código**, y con un **mensaje de error accionable** cuando el modelo configurado ya no existe. Motivo concreto del ADR-011: Google retiró `gemini-2.0-flash` el 1 de junio de 2026, y un proveedor que deprecia un modelo no debe poder romper una instalación que el usuario no actualizó — actualizar depende de él (ADR-009).
- Todos los umbrales de la feature (`MAX_UPLOAD_BYTES`, `MIN_DOC_CHARS`, `CLASSIFIER_CHARS`, `MAX_EXTRACTION_CHARS`, `MIN_SEEDED_ENTRIES`, intervalo de polling) viven aquí, no como literales dispersos.

**Rationale.** El art. V convierte el manejo de credenciales en una propiedad verificable, no en una buena práctica: SC-013 exige **0 apariciones** de llaves o fragmentos en logs, trazas, mensajes de error, respuestas o base de datos, auditado sobre una ejecución que recorra los cuatro resultados de preflight. `SecretStr` más el enum de estado más el redactor son tres capas independientes, y ninguna depende de que quien escriba el próximo endpoint se acuerde.

**Alternativas consideradas.**
- Guardar las credenciales cifradas en la base: prohibido explícitamente por FR-008 y por el art. V, y sin sentido en local por el mismo argumento del ADR-007 (la clave viviría junto al dato).
- Pedir la llave en cada arranque para no persistirla en ningún sitio: rompe el worker en background y contradice FR-014 (no volver a pedir credenciales ya verificadas).

---

## R-22 · Matriz de capacidades declarada como dato (FR-009, art. XI, ADR-011)

**Decisión.** Un módulo `adapters/llm/capabilities.py` declara la matriz del ADR-011 como **dato inmutable**, no como comportamiento:

```python
@dataclass(frozen=True)
class ProviderCapabilities:
    provider: ProviderId
    structured_output: bool | None      # None = sin verificar
    respects_null_in_optionals: bool | None
    embeddings: bool | None
    embedding_dim: int | None
    verified_on: date | None            # None ⇒ NO se ofrece en la UI (FR-009)
```

- Se declaran **las cinco filas** de la lista cerrada del ADR-011 (Google, OpenAI, Anthropic, DeepSeek, Kimi/Moonshot). Hoy solo Google tiene `verified_on`; las demás llevan `None` y **no aparecen en el catálogo que la API expone**. Anthropic declara además `embeddings=False` de forma explícita: no es "sin verificar", es "no lo ofrece".
- El catálogo ofrecible se calcula filtrando por `verified_on is not None` **y** por la capacidad pedida: la lista de proveedores de generación y la de embeddings son consultas distintas sobre la misma tabla.
- **Ninguna feature consulta el nombre del proveedor.** Consulta la capacidad. El único módulo que traduce un `ProviderId` a una implementación es `adapters/llm/factory.py`.
- Un **test de arquitectura falla si el nombre de un proveedor aparece fuera de `adapters/llm/`** — en `services/`, `domain/`, `api/`, `db/`, `workers/` o en los tests de esas capas. Con una sola implementación es trivial de pasar, y ese es exactamente el momento de instalarlo: queda puesto antes de que exista la segunda, que es cuando se rompería sin él.

**Rationale.** El art. XI exige que las capacidades se declaren y que una capacidad ausente degrade de forma informada. Una matriz como dato hace que el preflight y la futura pantalla de diagnóstico **lean una tabla** en vez de recorrer casos especiales repartidos por el código, y convierte "añadir un proveedor verificado" en un cambio de datos más una implementación de puerto. La regla del ADR-011 es literal: un `if provider == "..."` fuera del adapter es un bug del art. XI, no un atajo.

**Por qué la matriz no vale por sí sola.** El propio ADR-011 lo dice: "la matriz declarada en el código no vale más que la verificación que la respalda". Por eso `verified_on` es una fecha y no un booleano — una fecha vieja es motivo para volver a probar — y por eso el campo `respects_null_in_optionals` tiene entidad propia: es el modo de fallo más caro, porque un proveedor que rellena opcionales con texto inventado no rompe el parseo, produce afirmaciones sin sustento (art. IV).

---

## R-23 · Preflight de capacidades como componente de primera clase (FR-006, FR-007, SC-012, SC-016)

**Decisión.** Al guardar cada credencial —**nunca diferido al primer uso real**— se ejecuta un preflight que verifica en una misma operación que la credencial es aceptada **y** que la capacidad se cumple. Su resultado es un **tipo suma de cuatro variantes**, que el servicio interpreta y el contrato HTTP expone:

| Variante | Qué significa | Qué permite | FR |
|---|---|---|---|
| `credential_rejected` | Inválida, revocada o mal copiada | Nada: no se da la capacidad por verificada ni se avanza con ese proveedor | FR-007.1 |
| `verified` | Credencial válida y capacidad cumplida. Para embeddings, con la **dimensión registrada** | Avanzar | FR-007.2 |
| `capability_unverified` | Credencial válida, capacidad **sin garantía** | Avanzar **solo** tras un acuse específico de la degradación, habiendo enumerado antes qué funciones concretas quedan afectadas y por qué | FR-007.3 |
| `quota_exceeded` | La credencial sirve, la cuota no | Esperar al reinicio de cuota o configurar otro proveedor. La capacidad queda **sin verificar** | FR-007.4 |

A las que se suma un quinto caso que **no es un resultado de capacidad** sino de entorno: **sin conexión**. Se comunica como "no se pudo verificar", nunca como "la llave es incorrecta", y se ofrece reintentar **sin volver a pegar la llave** (edge case de la spec).

**Cómo se prueba cada capacidad** — productiviza `scripts/verify_providers.py`, que es el prototipo con el que se verificó Google el 2026-08-11:

- **Generación**: una llamada real con `with_structured_output` sobre un **esquema Pydantic anidado con campos opcionales**, aplicado a un CV deliberadamente incompleto (sin teléfono, un empleo sin fechas ni logros, una educación sin título). El criterio de aprobación **no es que el parseo funcione**, sino que el modelo devuelva `null` en esos campos **en vez de inventar valores plausibles**. Es el mismo criterio del art. IV que rige el pipeline (R-05), aplicado como prueba de admisión del proveedor.
- **Embeddings**: una llamada que produzca un vector, registrando **con qué dimensión**. Para Google se solicita `output_dimensionality=768` (truncado MRL desde las 3072 por defecto) y ese valor se persiste en `setup_state` como la dimensión verificada.

**Clasificación de errores del proveedor.** Distinguir `credential_rejected` de `quota_exceeded` de `provider_unreachable` se hace en el **adapter**, que es el único que sabe cómo se ve un 401 o un 429 en su proveedor, y se devuelve como variante del tipo suma. El servicio nunca inspecciona el error crudo, y ningún mensaje al usuario incluye la traza técnica ni el valor de la llave.

**Rationale.** El preflight es lo que impide que una capacidad ausente se descubra a mitad del uso, que es exactamente lo que el art. XI prohíbe y lo que SC-012 y SC-016 miden. Por eso la spec lo eleva a requisito funcional y no a detalle de implementación, y por eso aquí es un servicio propio con su tipo de resultado, y no un `try/except` dentro del formulario. Los cuatro resultados son **cuatro mensajes distintos** porque son cuatro situaciones distintas: presentar una cuota agotada como credencial inválida manda al usuario a regenerar una llave que funciona perfectamente.

**Alternativas consideradas.**
- Verificar solo que la credencial autentica (una llamada de listado de modelos): más barato y más rápido, y no verifica **nada** de lo que importa. Un proveedor puede aceptar la llave y no respetar `null` en opcionales.
- Diferir la verificación al primer parseo real: contradice FR-006 literalmente, y convierte el primer uso del producto en el momento de descubrir que hay que reconfigurar.
- Un booleano `ok/error`: colapsa cuatro situaciones en dos mensajes y hace imposible cumplir FR-007 y SC-016.

---

## R-24 · Sincronía entre la credencial y su preflight (SC-012)

**Decisión.** `setup_state` persiste, junto al resultado del preflight, un `credential_fingerprint`: **HMAC-SHA256 de la credencial con una clave derivada local, truncado**. Al arrancar y antes de cada operación que use el puerto, se recalcula sobre la credencial en configuración y se compara. Si no coincide —o si cambió el proveedor o el modelo configurados— el preflight queda **invalidado** y el wizard vuelve a pedirlo para esa capacidad.

**Por qué hace falta.** Las credenciales viven en configuración local y el resultado del preflight vive en la base (FR-008, FR-014). Son dos sitios distintos que pueden divergir: el usuario rota su llave en el `.env`, o pega otra, y el preflight persistido seguiría diciendo "verificada". SC-012 exige que **el 100% de las credenciales configuradas pase por el preflight antes de la primera llamada real del producto**; sin detección de cambio, ese 100% se rompe en silencio la primera vez que alguien edita su `.env`.

**Por qué no viola FR-008.** El requisito prohíbe persistir la credencial y exponerla "ni completa ni parcialmente". Un HMAC truncado no es la credencial ni un fragmento suyo: es un digest de longitud fija del que no se puede recuperar la entrada, y la clave del HMAC lo hace inútil fuera de esa instalación. Nunca se expone en ninguna respuesta de la API — es un detalle interno del que ni el frontend se entera.

**Alternativas consideradas.**
- **No persistir nada y re-verificar en cada arranque**: dos llamadas de red y su costo —pagado por el usuario— en cada `docker compose up`, y un arranque que se degrada si el proveedor está caído. Contra el criterio de fricción del art. VII.
- **Guardar los últimos cuatro caracteres de la llave** para detectar el cambio: es exactamente el "ni parcialmente" que FR-008 prohíbe.
- **Confiar en que el usuario reconfigure desde la UI si cambia la llave**: el `.env` es editable y editarlo es el camino natural en una app local; asumir lo contrario es diseñar para un usuario que no existe.

---

## R-25 · Forma de los puertos: `base_url`, credencial opcional y sin parámetros de muestreo (ADR-011 decisión 5, ADR-003)

**Decisión.** `StructuredOutputPort` y `EmbeddingsPort` se diseñan **desde el día 1** admitiendo `base_url` configurable y credencial **opcional**, aunque en v1 solo exista una implementación que siempre las tenga:

```python
class StructuredOutputPort(Protocol):
    async def generate[T: BaseModel](
        self, *, schema: type[T], prompt: str, purpose: Purpose,
        prompt_version: str, trace_context: TraceContext,
    ) -> T: ...

class EmbeddingsPort(Protocol):
    @property
    def model_name(self) -> str: ...
    @property
    def dimensions(self) -> int: ...
    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]: ...
```

La `base_url` y la credencial no aparecen en la **firma de los métodos**: son configuración de la implementación, resuelta en `factory.py` desde `Settings`. Lo que la decisión garantiza es que **ninguna de las dos se dé por supuesta**: no hay ningún punto del código que asuma "hay una API key" o "el endpoint es el del proveedor".

**Y una ausencia deliberada: los parámetros de muestreo no están.** Ni `temperature`, ni `top_p`, ni `top_k` aparecen en la firma del puerto, en `services/` ni en `domain/`. Son opcionales y propios de cada implementación: se pasan cuando el proveedor los admite y se omiten cuando no, sin que el resto del código se entere.

**Rationale.** Añadir Ollama —o cualquier servidor compatible con la API de OpenAI, que es el camino natural para quien quiera que *ningún* dato salga de su máquina— debe ser **una implementación nueva del puerto, no un refactor del puerto** (ADR-011 decisión 5). Un puerto que da por sentado que hay credencial y endpoint fijo convierte esa adición futura en un cambio que toca todo lo que hay detrás. **Ollama no se implementa en v1**; lo que se decide aquí es no cerrarle la puerta con la forma de la interfaz.

Sobre el muestreo, la razón es la del ADR-003 (nota del 2026-08-11): `temperature`, `top_p` y `top_k` están **deprecados en Gemini 3.x**, sustituidos por `thinking_level`, que controla el presupuesto de razonamiento y no la aleatoriedad — no son equivalentes ni intercambiables, y no existe un valor de `thinking_level` que "sea" `temperature=0`. **El determinismo que exige el art. III nunca se apoyó en ese parámetro**: lo sostienen el esquema tipado en cada frontera (art. I), las decisiones de flujo tomadas fuera del LLM y los sub-scores calculados con reglas testeables. `temperature=0` tampoco garantizaba reproducibilidad exacta en ningún proveedor. Su desaparición no debilita el art. III porque nunca fue su fundamento. Un `temperature=0` incrustado en `services/` o en la firma del puerto sería el mismo bug que un `if provider == "..."`: convierte el detalle de un proveedor en un requisito del dominio. Lo que verifica que la salida sigue siendo aceptable son las evals del golden set (R-15), no la presencia de un parámetro.

---

## R-26 · `EmailPort` acotado a la etiqueta designada (FR-011 – FR-013, ADR-012)

**Decisión.** `EmailPort` con implementación **Gmail App Password + IMAP**. En 001 se usa **exclusivamente** para una operación: verificar que la etiqueta designada por el usuario **existe y es alcanzable** antes de dar la vinculación por establecida (FR-013). Leer esa etiqueta e ingerir vacantes es la feature de fuentes (F1.3.2), fuera de alcance.

- La App Password y la etiqueta se guardan en **configuración local**, con las mismas reglas que las API keys: nunca en base de datos, nunca en logs ni en mensajes de error (FR-013 remite a FR-008). `setup_state` guarda solo el **estado** del paso (`linked` | `skipped` | `pending`) y el nombre de la etiqueta.
- **El filtro por etiqueta vive en el adapter**, y sus tests son **tests de cumplimiento, no de funcionalidad**: verifican que ninguna consulta IMAP sale sin restricción de etiqueta. Un cambio que amplíe el alcance de lectura es un incidente de privacidad, no una feature (ADR-012).
- **Divulgación previa obligatoria** (FR-012), antes de pedir credencial alguna: que una App Password da acceso a **toda** la bandeja, y que restringir la lectura a la etiqueta es **un compromiso de Vokara verificado por sus propias pruebas, no un permiso que Google imponga**; y que las cuentas de Google Workspace y las de Protección Avanzada **no admiten App Passwords**, con enlace a la vía OAuth documentada. Ese aviso se da **antes** de empezar, nunca a mitad.
- El paso es **omitible con una sola acción y con el mismo peso visual** que continuar (FR-011). Omitirlo no bloquea nada de esta feature.

**Rationale.** Es el punto de la feature donde la asimetría entre lo que el usuario **otorga** y lo que Vokara **usa** es mayor, y la única compensación honesta es decirlo antes y hacerlo verificable después. La vía OAuth sería técnicamente correcta y es la única para cuentas Workspace, pero exige que cada usuario cree su propio proyecto en Google Cloud: diez pasos en una consola de desarrollador contra tres en la configuración de su cuenta, contra el criterio de fricción del art. VII. Se documenta como opción avanzada, no como default.

**Alternativas consideradas** (del ADR-012, por trazabilidad): OAuth como camino principal (fricción), distribuir credenciales OAuth del proyecto en el repo (un `client_secret` en un repo público no es secreto), reenvío manual a una dirección de Vokara (no hay backend), leer la bandeja completa (convertiría un acceso acotado en acceso total sin que el usuario lo note).

---

## R-27 · Costo estimado antes de pedir la llave (FR-005)

**Decisión.** Un catálogo declarativo en `adapters/llm/pricing.py`, junto a la matriz de capacidades, que para cada proveedor ofrecible expone: costo estimado por **mes de búsqueda activa**, el **supuesto de uso** que lo produce (en texto, para que la cifra sea interpretable) y, cuando aplica, **qué cabe dentro de la capa gratuita y a partir de qué punto se empieza a pagar**.

- Se estima **por separado para generación y para embeddings** y se muestra por separado. Sumarlos haría creer que cambiar de proveedor de embeddings mueve la factura, cuando lo que la mueve es la generación: sus órdenes de magnitud no se parecen (ADR-011).
- Se muestra **antes** de que se pida la API key, no después (FR-005 y roadmap §11.3).
- El endpoint del catálogo devuelve estas cifras junto a cada opción, de modo que el frontend las renderiza sin conocer proveedores ni tarifas.

**Límite explícito de alcance.** El **cálculo** de las cifras es trabajo del paso 10 del roadmap, fuera de esta spec (Assumptions). Lo que este plan fija es **dónde viven, con qué forma y en qué momento se muestran**, de modo que llenarlas sea editar datos y no tocar la UI.

**Rationale.** En ejecución local el presupuesto ya no es del proyecto: es información que el usuario necesita para decidir, y pedirle una tarjeta de crédito sin decirle antes cuánto va a costar sería exactamente la clase de sorpresa que el art. V busca evitar. Que Gemini sea el default sugerido se apoya en este mismo dato: es el único con capa gratuita suficiente para usar Vokara de verdad sin tarjeta (ADR-003), y para un público que puede estar sin ingresos eso no es una ventaja de costo, es la diferencia entre poder usarlo y no poder.

---

## R-28 · Runtime del parseo asíncrono: Celery **sin beat** (art. VII, roadmap §5)

**Decisión.** Se mantiene **Celery + Redis** como fija el roadmap §5, con el worker como servicio del Compose, y **se elimina `beat`**: nada en 001 se agenda, y un proceso más sin tarea periódica es infraestructura sin consumidor.

Se registra además un hecho que cambia la evaluación: **Redis hoy queda exclusivamente como broker de Celery.** Con el ADR-008 desaparecieron sus otros dos usos previstos (revocación de `jti` y rate limiting de `/auth/*`), que ya no existen.

**La evaluación que el input del plan pidió.** El art. VII eleva la fricción de instalación a criterio de alcance con una frase inequívoca: *"cada servicio que el usuario deba levantar en su máquina reduce la adopción, y debe justificarse frente a la alternativa de no tenerlo"*. La pregunta legítima es si `worker` + `redis` —dos de los cuatro servicios— se justifican para un solo usuario local cuando existen alternativas con menos piezas.

| Opción | Servicios | Consecuencias |
|---|---|---|
| **Celery + Redis (elegida)** | 4 | Fijado por roadmap §5 y por "Restricciones adicionales" de la constitución: no requiere ADR. El parseo corre fuera del proceso de la API, así que una llamada de 30–60 s no compite con ella; sobrevive al reinicio del contenedor de API; reintentos y backoff vienen dados |
| `arq` en lugar de Celery | 4 | **También** necesita Redis y un proceso worker: el conteo de servicios no baja y la fricción de instalación no mejora en nada. A cambio exige un ADR que reemplace la fila de colas del roadmap §5. Paga el costo del cambio sin cobrar el beneficio que motiva la pregunta |
| `FastAPI BackgroundTasks` | 2 | La única con reducción real. Costos: el parseo compite con la API por el proceso; un reinicio abandona el trabajo en vuelo sin reintento automático; contradice roadmap §5 y exige ADR nuevo; y F1.3 (sondeo de correo) y F1.6 (digest) reintroducirían un worker poco después, con la migración hecha dos veces |

**Rationale de la elección.** El argumento decisivo es qué mide exactamente el art. VII. Su criterio es *"cada servicio que el usuario deba levantar"*, y ni `worker` ni `redis` añaden **un solo paso** al usuario: no se configuran, no piden credenciales, no aparecen en el `.env` y no se mencionan en el README más allá de la lista de contenedores. `docker compose up` levanta dos o cuatro con el mismo comando y la misma espera. El costo real de tenerlos es memoria —Redis ronda las decenas de MB— y una imagen más que descargar la primera vez; el costo de no tenerlos es que una llamada de 30–60 s al proveedor ocupe el proceso que sirve la UI, en un flujo donde el usuario está mirando la barra de progreso.

La fricción que sí decide la adopción está en otro sitio y este plan la ataca donde vive: que `docker compose up` funcione **sin editar archivos** (R-20), que las migraciones se apliquen solas y que el wizard pida la API key en la UI en vez de en un `.env`. Bajar de cuatro contenedores a dos no mueve ninguna de esas tres agujas.

**Qué haría revisar esta decisión.** Si la prueba de instalación asistida de la Fase 5 (SC-014) muestra que la descarga de imágenes o el consumo de memoria son un obstáculo real en las máquinas del público objetivo, la alternativa de `BackgroundTasks` vuelve a la mesa **con datos en vez de suposiciones** — y entonces sí con su ADR, como exige la constitución para cambiar el stack del roadmap §5.

---

## R-29 · Divulgación versionada y acuse bloqueante (FR-001, FR-002, SC-011)

**Decisión.**
- El texto de divulgación vive **en el repositorio, versionado**, y su versión vigente en configuración. `setup_state` registra el acuse con su **marca de tiempo y la versión del texto acusado**: saber *qué* aceptó el usuario es tan importante como saber que aceptó.
- El acuse es **explícito y afirmativo**: nunca preseleccionado, nunca inferido de pulsar "continuar" (FR-002). Sin él, el botón de continuar permanece inhabilitado.
- **El gate es de servidor, no de UI.** Sin acuse registrado, ningún endpoint del onboarding responde: la subida de un CV se rechaza con `DISCLOSURE_ACKNOWLEDGEMENT_REQUIRED` (409) aunque se llame directamente a la API. El guard del frontend es comodidad, no control — SC-011 exige que *ninguna vía* (navegación directa, recarga o reinicio) permita subir sin él.
- El contenido obligatorio del texto son los cuatro puntos de FR-001: (a) los datos se quedan en la máquina; (b) la **única** excepción, con qué se envía y en qué momento; (c) Vokara **no envía nada a sus creadores** —cero telemetría, analítica o reportes de error—; (d) los archivos quedan **sin cifrar** en el disco, con la recomendación de activar el cifrado de disco del sistema operativo.

**Rationale.** El art. V exige la divulgación "en texto claro y en la propia pantalla" en la primera ejecución, y prohíbe expresamente enterrarla en documentación secundaria o darla por sabida. Versionar el texto es lo que permite que un cambio futuro en qué se envía —una feature nueva que mande la vacante al proveedor, por ejemplo— pueda exigir un acuse nuevo en vez de quedar cubierto por uno viejo que decía otra cosa. Y es también lo que sostiene FR-048: habilitar el uso de material real para evals **nunca** puede colarse por la vía de modificar este texto, precisamente porque queda registrado cuál se aceptó.

---

## Resumen de incógnitas resueltas

| Incógnita del Technical Context | Resuelta en |
|---|---|
| Cómo detectar formato real, corrupción y tamaño antes de procesar | R-01 |
| Cómo evitar intercalado de columnas y perder tablas | R-02 |
| Cómo detectar PDF escaneado sin OCR | R-03 |
| Cómo detectar que el archivo no es un CV | R-04 |
| Cómo garantizar que no se inventan datos y marcar incompletas | R-05 |
| Dónde se guarda el binario y por qué sin cifrado | R-06 (ADR-007) |
| Cómo se expone el progreso y se garantiza un solo trabajo activo | R-07 |
| Cómo se versiona y cómo se detectan cambios sin confirmar | R-08 |
| Cuándo cambia el origen de una entrada | R-09 |
| Cómo reintentar sin perder trabajo manual | R-10 |
| Cómo se resuelve la identidad sin autenticación | R-11 (ADR-008) |
| Qué parte de embeddings entra en 001 | R-12 |
| Cómo cumplir el art. VIII sin violar el art. V, y sin Sentry | R-13 |
| Cómo se cumple el < 60 s de SC-004 | R-14 |
| Composición, procedencia y umbrales del golden set | R-15 |
| Cómo se impide que el cliente TS se desincronice | R-16 |
| Dónde viven y cómo se validan los objetivos | R-17 |
| Cómo se retoma el wizard y el onboarding donde se quedaron | R-18 |
| Qué pasa con ediciones concurrentes | R-19 |
| Compose local, binding a loopback, migraciones al arranque y CI | R-20 (ADR-008, ADR-009) |
| Dónde viven las credenciales y los nombres de modelo | R-21 |
| Cómo se declaran las capacidades sin ramificar por proveedor | R-22 (ADR-011) |
| Qué verifica el preflight y cuáles son sus cuatro resultados | R-23 |
| Cómo se evita que un preflight persistido mienta tras rotar la llave | R-24 |
| Qué forma tienen los puertos y por qué no llevan `temperature` | R-25 (ADR-011, ADR-003) |
| Qué hace el `EmailPort` en 001 y qué se divulga antes | R-26 (ADR-012) |
| Dónde vive el costo estimado y cuándo se muestra | R-27 |
| Si Celery sigue justificado para un solo usuario local | R-28 |
| Cómo se versiona la divulgación y por qué el gate es de servidor | R-29 |
