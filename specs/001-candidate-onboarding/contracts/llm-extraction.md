# Contrato del componente LLM — clasificación y extracción del CV

**Feature**: 001-candidate-onboarding · **Fecha**: 2026-08-10 · Decisiones en [research.md](../research.md) R-04, R-05, R-13, R-15

El LLM aparece **dos veces** en toda la feature, ambas como componente con entrada y salida tipadas (art. III). No decide el flujo: devuelve datos que un servicio determinista interpreta. No hay agente, ni herramientas, ni bucle.

```text
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
        purpose: Literal["classification", "extraction"],
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

`EmbeddingsPort` se entrega implementado pero **sin consumidor en 001** (research R-12). Toda feature que persista vectores queda obligada por la convención de `data-model.md` §"Convención vinculante para embeddings".

Implementación: `GeminiAdapter` sobre `langchain-google-genai`, usando `with_structured_output(schema)`. Reintentos: 3 con backoff exponencial ante error de red, 429 o salida que no valida contra el esquema. Cada intento se registra por separado en `llm_call_logs`.

---

## [1] Clasificación del documento — FR-005, SC-008

**Entrada**: primeros `CLASSIFIER_CHARS` caracteres del texto extraído (por defecto 6.000).
**Modelo**: el rápido/económico de la familia Gemini (ADR-003).
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

## [2] Extracción a entradas — FR-009, FR-012, FR-013

**Entrada**: texto completo, truncado a `MAX_EXTRACTION_CHARS` (por defecto 120.000; el truncado marca `parse_job.truncated = true`).
**Modelo**: el rápido/económico de la familia (revisable con datos de costo real, ADR-003).
**Prompt**: `CV_EXTRACTION_V1`. `temperature = 0`. Versión de modelo pineada en `Settings`.

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
| FR-013 — nunca inventar datos ausentes | **Todos** los campos de contenido son `Optional` con `None` por defecto. El modelo no tiene ninguna presión estructural para rellenar: devolver `null` es una salida válida. Ningún campo admite valores centinela ("N/A", "Desconocido") |
| FR-012 — conservar el idioma original | `language` por entrada, en ISO 639-1. El prompt prohíbe traducir; el contenido viaja tal como aparece en el documento |
| FR-009 — solo los siete tipos | `entry_type` es un enum cerrado; una salida fuera de dominio no valida y dispara reintento |
| FR-013 — marcar incompletas | El modelo **no** decide completitud. La calcula `domain/completeness.py` sobre la entrada ya validada |
| Auditabilidad de las evals | `source_excerpt` permite comprobar que cada campo extraído existe literalmente en el texto fuente |

### Instrucciones del prompt (resumen normativo)

El texto completo vive en `backend/app/adapters/llm/prompts/cv_extraction_v1.py`. Sus cláusulas no negociables:

1. Extrae únicamente lo que aparece en el documento. Si un dato no está, devuelve `null`. **Nunca** lo deduzcas, lo estimes ni lo completes con conocimiento general.
2. No traduzcas. Cada entrada conserva el idioma en que está escrita; indica cuál en `language`.
3. Descompón en entradas **atómicas**: un puesto es una entrada de experiencia; cada logro cuantificable dentro de ese puesto es una entrada de logro propia.
4. No reformules ni "mejores" el contenido. Copia el hecho como está redactado; la reformulación es trabajo de otra feature y bajo otro guardrail.
5. Si el documento tiene columnas o tablas, no mezcles contenido de bloques distintos. Ante duda sobre a qué bloque pertenece un fragmento, deja los campos afectados en `null` en vez de adivinar.
6. `source_excerpt` es una cita **literal** del documento, nunca un resumen.

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
- Cada llamada registra en `llm_call_logs`: `model`, `prompt_version`, tokens de entrada y salida, costo estimado, latencia, número de intento y `outcome` (art. VIII).
- **Nunca** se registran el prompt renderizado, el texto del CV ni la respuesta del modelo (art. V, research R-13).
- Las evals fijan la versión de prompt bajo prueba; cambiar de versión sin correr las evals es, por definición de la constitución (art. VI), un bug.

---

## Evals — criterios bloqueantes en CI

Ubicación: `backend/tests/evals/`. Golden set en `golden_set/`, compuesto **exclusivamente** de material sintético o del propio equipo (FR-032). Añadir material de un usuario real requiere ADR propio y consentimiento opt-in separado (FR-033): no es un cambio de configuración.

| Métrica | Umbral bloqueante | Requisito |
|---|---|---|
| Tasa de error por campo sobre el golden set | < 5% | SC-003 |
| Campos inventados (valor no presente en el texto fuente) | **0** | FR-013, art. IV |
| Detección de "no es un CV" sobre los negativos del set | 100% | FR-005, SC-008 |
| Detección de PDF sin capa de texto | 100% | FR-006, SC-009 |
| Entradas de CV en inglés con `language` correcto | 100% | FR-012 |
| Casos de exageración detectados como fallo | 100% | Roadmap §6.4, art. IV |

Composición inicial (12 casos, ampliable a 30–50 según roadmap §6.4): 6 CVs sintéticos en español (uno a dos columnas, uno con tablas), 2 en inglés, 1 mixto español/inglés, 1 PDF escaneado, 1 factura (negativo), 1 CV de contenido escaso.

Ejecución en CI: golden set **completo** en todo PR que toque `adapters/llm/`, `services/extraction_service.py`, `domain/completeness.py` o el propio golden set; subconjunto de humo de 3 casos en el resto. Ambos bloqueantes.
