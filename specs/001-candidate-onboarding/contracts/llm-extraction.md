# Contrato del componente LLM — puertos, preflight, clasificación y extracción

**Feature**: 001-candidate-onboarding · **Fecha**: 2026-08-11 · Decisiones en [research.md](../research.md) R-04, R-05, R-12, R-13, R-15, R-21, R-22, R-23, R-25

El LLM aparece **tres** veces en toda la feature, siempre como componente con entrada y salida tipadas (art. III). Nunca decide el flujo: devuelve datos que un servicio determinista interpreta. No hay agente, ni herramientas, ni bucle.

```text
[0] preflight de capacidades ──▶ resultado tipado de 4 variantes ──▶ el SERVICIO decide

texto extraído ──▶ [1] clasificación ──is_resume=false──▶ FALLO DOCUMENT_NOT_A_RESUME
                        │                                  (0 entradas creadas)
                   is_resume=true
                        ▼
                   [2] extracción ──▶ reglas de completitud ──▶ persistencia
```

---

## Puertos del adapter (`backend/app/adapters/llm/base.py`)

```python
class StructuredOutputPort(Protocol):
    async def generate[T: BaseModel](
        self,
        *,
        schema: type[T],
        prompt: str,
        purpose: Purpose,              # classification | extraction | preflight
        prompt_version: str,
        trace_context: TraceContext,
    ) -> T: ...

class EmbeddingsPort(Protocol):
    @property
    def model_name(self) -> str: ...
    @property
    def dimensions(self) -> int: ...
    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]: ...
```

**Reglas de forma, vinculantes (ADR-011 decisión 5, ADR-003):**

- **Los dos puertos se configuran de forma independiente**: cada uno con su proveedor, su credencial y su modelo. Ninguna elección condiciona a la otra (FR-004).
- **Ambos admiten `base_url` configurable y credencial opcional.** No aparecen en la firma de los métodos porque son configuración de la implementación, resuelta en `factory.py` desde `Settings`; lo que la regla garantiza es que **ningún punto del código asuma que hay una API key o que el endpoint es el del proveedor**. Añadir Ollama —o cualquier servidor compatible con la API de OpenAI— debe ser una implementación nueva del puerto, **no un refactor del puerto**. Ollama **no se implementa en v1**.
- **Ningún parámetro de muestreo en la firma.** `temperature`, `top_p` y `top_k` están deprecados en Gemini 3.x y no todos los proveedores los exponen igual. Son opcionales y propios de cada implementación: se pasan cuando el proveedor los admite y se omiten cuando no, sin que `services/` se entere. Un `temperature=0` en la capa de servicios o en la firma del puerto es el mismo bug que un `if provider == "..."`: convierte el detalle de un proveedor en un requisito del dominio.
- **Los nombres de modelo vienen de configuración**, con override por variable de entorno y con mensaje de error accionable si el modelo configurado ya no existe (`MODEL_NOT_AVAILABLE`). Nunca constantes en código: Google retiró `gemini-2.0-flash` el 1 de junio de 2026, y un proveedor que deprecia un modelo no debe poder romper una instalación que el usuario no actualizó.

**Implementación en v1: solo Google** (`langchain-google-genai`), usando `with_structured_output(schema)`. Es el único proveedor con la fila de verificación empírica completa en el ADR-011, y FR-009 prohíbe ofrecer lo no verificado. Reintentos: 3 con backoff exponencial ante error de red, 429 o salida que no valida contra el esquema. Cada intento se registra por separado en `llm_call_logs`.

**Matriz de capacidades** (`capabilities.py`): declara las **cinco** filas de la lista cerrada del ADR-011 como dato inmutable, con `verified_on: date | None`. Las cuatro pendientes llevan `None` y **no se ofrecen** (FR-009). Anthropic declara `embeddings=False` explícitamente: no es "sin verificar", es "no lo ofrece". **Ninguna feature consulta el nombre del proveedor**; el único módulo que traduce un identificador a una implementación es `factory.py`, y un test de arquitectura falla si un nombre de proveedor aparece fuera de `adapters/llm/`.

---

## [0] Preflight de capacidades — FR-006, FR-007, SC-012, SC-016

Se ejecuta **al guardar cada credencial**, nunca diferido al primer uso real. Verifica en una misma operación que la credencial es aceptada por el proveedor **y** que la capacidad requerida se cumple.

### Resultado: tipo suma de cuatro variantes

```python
type PreflightOutcome = (
    CredentialRejected        # FR-007.1 — inválida, revocada o mal copiada
    | Verified                # FR-007.2 — capacidad cumplida (embeddings: con dimensión)
    | CapabilityUnverified    # FR-007.3 — credencial válida, capacidad sin garantía
    | QuotaExceeded           # FR-007.4 — la credencial sirve, la cuota no
)
```

Y un caso de entorno que **no es un resultado de capacidad**: `ProviderUnreachable` (sin conexión). Se comunica como "no se pudo verificar", **nunca** como "la llave es incorrecta", y permite reintentar **sin volver a pegar la llave**.

**La clasificación del error vive en el adapter**, que es el único que sabe cómo se ve un 401 o un 429 en su proveedor. El servicio recibe la variante ya tipada y nunca inspecciona el error crudo. Ningún mensaje al usuario incluye la traza técnica ni el valor de la llave (FR-008, SC-013).

### Cómo se prueba cada capacidad

Productiviza `scripts/verify_providers.py`, el prototipo con el que se verificó Google el 2026-08-11.

**Generación** — llamada real con `with_structured_output` sobre un **esquema Pydantic anidado con campos opcionales**, aplicado a un CV deliberadamente incompleto: sin teléfono, sin años de experiencia declarados, un empleo sin fechas ni logros y una educación sin título.

> **El criterio de aprobación no es que el parseo funcione.** Es que el modelo devuelva `null` en esos campos **en vez de inventar valores plausibles**. Es exactamente el modo de fallo que el art. IV existe para impedir: un proveedor que rellena opcionales con texto inventado no rompe el parseo, produce afirmaciones sin sustento. Por eso el ADR-011 le da columna propia en la matriz ("respeta `null` en opcionales") y por eso el preflight mide lo mismo que mide el pipeline (R-05).

**Embeddings** — llamada que produzca un vector, registrando **con qué dimensión**. Para Google se solicita `output_dimensionality=768` (truncado MRL desde las 3072 por defecto), y ese valor se persiste como la dimensión verificada de esa configuración.

### Qué permite cada variante

| Variante | Permite avanzar | Efecto en la feature |
|---|---|---|
| `Verified` | Sí | Capacidad disponible. Embeddings: `embedding_dim` registrada |
| `CapabilityUnverified` | Sí, **solo tras acuse específico** | El sistema enumera **qué funciones concretas quedan afectadas y por qué** y ofrece cambiar de proveedor **antes** del acuse. Nunca degradación silenciosa, nunca fallo opaco |
| `CredentialRejected` | No | Mensaje accionable: qué revisar y dónde regenerarla. Nunca la llave, nunca una traza |
| `QuotaExceeded` | No | Se dice como lo que es: la credencial sirve, la cuota no. Dos salidas concretas: esperar al reinicio o configurar otro proveedor |

**Gate de entrada al onboarding (FR-010)**: se exige proveedor de **generación** con `Verified`, o `CapabilityUnverified` con su acuse registrado. La ausencia de proveedor de **embeddings** verificado **nunca** bloquea el onboarding.

---

## [1] Clasificación del documento — FR-020, SC-008

**Entrada**: primeros `CLASSIFIER_CHARS` caracteres del texto extraído (por defecto 6.000).
**Modelo**: el rápido/económico configurado para generación.
**Prompt**: `CV_CLASSIFICATION_V1`.

```python
class DocumentClassification(BaseModel):
    is_resume: bool
    document_kind: Literal[
        "resume", "invoice", "contract", "letter", "academic_paper", "other"
    ]
    reason_es: str = Field(max_length=200)   # explicación breve, sin PII
```

**Interpretación (en el servicio, no en el modelo)**: si `is_resume` es falso, el `parse_job` termina en `failed` con `error_code = DOCUMENT_NOT_A_RESUME` y **cero** entradas creadas. `document_kind` y `reason_es` alimentan el mensaje al candidato; `reason_es` se sanea antes de mostrarse y no puede contener fragmentos del documento.

---

## [2] Extracción a entradas — FR-024, FR-027, FR-028

**Entrada**: texto completo, truncado a `MAX_EXTRACTION_CHARS` (por defecto 120.000; el truncado marca `parse_job.truncated = true`).
**Modelo**: el configurado para generación, **por configuración y no por constante**.
**Prompt**: `CV_EXTRACTION_V1`.

```python
class ExtractedEntry(BaseModel):
    entry_type: EntryType
    content: EntryContent          # unión discriminada, todos los campos Optional
    language: str | None = Field(default=None, pattern=r"^[a-z]{2}$")
    source_excerpt: str | None = Field(default=None, max_length=500)

class SeededProfile(BaseModel):
    entries: list[ExtractedEntry]
```

### Reglas que el esquema hace cumplir por construcción

| Requisito | Cómo lo impone el esquema |
|---|---|
| FR-028 — nunca inventar datos ausentes | **Todos** los campos de contenido son `Optional` con `None` por defecto. El modelo no tiene ninguna presión estructural para rellenar: devolver `null` es una salida válida. Ningún campo admite valores centinela ("N/A", "Desconocido") |
| FR-027 — conservar el idioma original | `language` por entrada, en ISO 639-1. El prompt prohíbe traducir; el contenido viaja tal como aparece en el documento |
| FR-024 — solo los siete tipos | `entry_type` es un enum cerrado; una salida fuera de dominio no valida y dispara reintento |
| FR-028 — marcar incompletas | El modelo **no** decide completitud. La calcula `domain/completeness.py` sobre la entrada ya validada |
| Auditabilidad de las evals | `source_excerpt` permite comprobar que cada campo extraído existe literalmente en el texto fuente |

### Instrucciones del prompt (resumen normativo)

El texto completo vive en `backend/app/adapters/llm/prompts/cv_extraction_v1.py`. Sus cláusulas no negociables:

1. Extrae únicamente lo que aparece en el documento. Si un dato no está, devuelve `null`. **Nunca** lo deduzcas, lo estimes ni lo completes con conocimiento general.
2. No traduzcas. Cada entrada conserva el idioma en que está escrita; indica cuál en `language`.
3. Descompón en entradas **atómicas**: un puesto es una entrada de experiencia; cada logro cuantificable dentro de ese puesto es una entrada de logro propia.
4. No reformules ni "mejores" el contenido. Copia el hecho como está redactado; la reformulación es trabajo de otra feature y bajo otro guardrail.
5. Si el documento tiene columnas o tablas, no mezcles contenido de bloques distintos. Ante duda sobre a qué bloque pertenece un fragmento, deja los campos afectados en `null` en vez de adivinar.
6. `source_excerpt` es una cita **literal** del documento, nunca un resumen.

**Ninguna cláusula del prompt nombra a un proveedor ni asume una capacidad suya** (art. XI): el prompt describe la tarea, no el modelo que la ejecuta.

### Posprocesado determinista (`seeding_service`)

Orden fijo, todo por reglas:

1. Validar cada entrada contra la unión discriminada (Pydantic).
2. Descartar entradas cuyo contenido quede completamente vacío tras la validación.
3. Calcular `is_complete` y `missing_fields` con las reglas por tipo de `domain/completeness.py`.
4. Asignar `origin = cv_seed` y `source_document_id`.
5. Si `entries` está por debajo de `MIN_SEEDED_ENTRIES` (por defecto 3), terminar el trabajo con `error_code = DOCUMENT_TOO_SPARSE`, ofreciendo la captura manual (edge case "CV vacío o con contenido mínimo").
6. Insertar **todas** las entradas en una única transacción (research R-07).

---

## Versionado de prompts y trazado

- Cada prompt es una constante con nombre versionado (`CV_EXTRACTION_V1`). Cambiar el texto **exige** una versión nueva; nunca se edita una existente.
- Cada llamada registra en `llm_call_logs`: `capability`, `purpose`, `model`, `prompt_version`, tokens de entrada y salida, costo estimado, latencia, número de intento y `outcome` (art. VIII).
- **Nunca** se registran el prompt renderizado, el texto del CV ni la respuesta del modelo (art. V, FR-046, research R-13). Quedan **descartadas** Langfuse, LangSmith y cualquier plataforma de observabilidad de LLM que capture prompts, hospedada o auto-alojada: su valor está en guardar el contenido, que es justamente lo único que aquí no puede guardarse.
- Las evals fijan la versión de prompt bajo prueba; cambiar de versión sin correr las evals es, por definición de la constitución (art. VI), un bug.

---

## Evals — criterios bloqueantes en CI

Ubicación: `backend/tests/evals/`. Golden set en `golden_set/`, compuesto **exclusivamente** de material sintético o del propio equipo (FR-047). Añadir material de un usuario real requiere **ADR propio y consentimiento opt-in separado, explícito y revocable** (FR-048): no es un cambio de configuración, y **nunca** puede habilitarse modificando el texto de divulgación ni apoyándose en el acuse del paso 0.

| Métrica | Umbral bloqueante | Requisito |
|---|---|---|
| Tasa de error por campo sobre el golden set | < 5% | SC-003 |
| Campos inventados (valor no presente en el texto fuente) | **0** | FR-028, art. IV |
| Detección de "no es un CV" sobre los negativos del set | 100% | FR-020, SC-008 |
| Detección de PDF sin capa de texto | 100% | FR-021, SC-009 |
| Entradas de CV en inglés con `language` correcto | 100% | FR-027 |
| Casos de exageración detectados como fallo | 100% | Roadmap §6.4, art. IV |

**Reproducibilidad sin parámetros de muestreo**: el modelo bajo prueba se fija en configuración y su nombre queda registrado en el resultado de cada corrida, junto con la versión de prompt. Lo que verifica que la salida sigue siendo aceptable son estas métricas, no la presencia de un parámetro (ADR-003).

**Portabilidad ejecutable (art. XI)**: la suite está parametrizada por proveedor y toma el que indique la configuración. Hoy solo hay una implementación, así que corre contra Google; cuando exista la segunda, correrla contra ella es cambiar una variable de entorno, no escribir una suite nueva. Las evals son la prueba ejecutable de que la portabilidad no es solo una afirmación del adapter.

Composición inicial (12 casos, ampliable a 30–50 según roadmap §6.4): 6 CVs sintéticos en español (uno a dos columnas, uno con tablas), 2 en inglés, 1 mixto español/inglés, 1 PDF escaneado, 1 factura (negativo), 1 CV de contenido escaso.

Ejecución en CI: golden set **completo** en todo PR que toque `adapters/llm/`, `services/extraction_service.py`, `domain/completeness.py` o el propio golden set; subconjunto de humo de 3 casos en el resto. Ambos bloqueantes.
