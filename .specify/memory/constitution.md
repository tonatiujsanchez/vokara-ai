<!--
Sync Impact Report
==================
- Version change: 1.0.0 → 1.1.0 (MINOR: guía material ampliada, principio nuevo)
- Principio añadido: X. Control humano
- Principio modificado: IV. Veracidad no negociable (define perfil maestro y
  trazabilidad por source_id; ver ADR-005)
- Gobernanza: "nueve principios" → "diez principios"
- Deferred items / TODOs: ninguno.

Historial previo (v1.0.0, ratificación inicial):
- Version change: template (sin versión) → 1.0.0
- Ratificación inicial: se reemplaza el template completo por la constitución de Vokara.
- Principios añadidos:
  - I. Tipado estricto de extremo a extremo
  - II. Arquitectura por capas con dependencias unidireccionales
  - III. Determinismo primero
  - IV. Veracidad no negociable
  - V. Privacidad y cumplimiento
  - VI. Calidad verificable
  - VII. Simplicidad (YAGNI)
  - VIII. Observabilidad
  - IX. Idioma
- Secciones añadidas: Restricciones adicionales; Flujo de desarrollo; Gobernanza.
- Secciones eliminadas: ninguna (todos los placeholders del template quedaron resueltos).
- Deferred items / TODOs: ninguno.
- Templates dependientes: plan/spec/tasks leen esta constitución en runtime; no requieren cambios.
-->

# Constitución de Vokara

Vokara es un agente de búsqueda de empleo (backend Python, frontend React) para
profesionistas en México. La fuente de verdad de producto es
`docs/product/roadmap.md`; las decisiones de arquitectura viven en `docs/adr/`.
Esta constitución prevalece sobre cualquier otra práctica del proyecto.

## Principios fundamentales

### I. Tipado estricto de extremo a extremo (NO NEGOCIABLE)

- `mypy --strict` corre en CI y es bloqueante: un error de tipos impide el merge.
- Pydantic v2 valida TODA frontera de datos: requests/responses de la API,
  salidas de LLM (structured output), payloads de workers y adapters.
- El cliente TypeScript del frontend se GENERA desde el esquema OpenAPI del
  backend como parte del build. Está PROHIBIDO escribir tipos de API a mano en
  el frontend.

Racional: un cambio de esquema debe romper el build, no producción. El tipado
es el contrato entre backend, frontend y LLM.

### II. Arquitectura por capas con dependencias unidireccionales (NO NEGOCIABLE)

- Regla de dependencias: `api → services → repositories/adapters`. Nunca en
  sentido inverso.
- PROHIBIDA la lógica de negocio en routers y en tareas Celery: las tareas
  solo orquestan servicios.
- Todo lo externo (LLM, embeddings, fuentes de vacantes, correo, storage,
  export de documentos) vive detrás de un adapter con interfaz propia e
  intercambiable.
- El adapter de LLM cubre también los embeddings. Cada vector persistido
  almacena su `embedding_model` y `embedding_dim` para permitir migración de
  proveedor sin pérdida de datos (ver ADR-003).

Racional: los proveedores cambian; el dominio no debe enterarse. La
unidireccionalidad mantiene el negocio testeable sin infraestructura.

### III. Determinismo primero (NO NEGOCIABLE)

- Los pipelines (ingesta, parseo, matching, generación de materiales) son
  flujos deterministas y testeables. El LLM participa únicamente como
  componente con entrada/salida tipada (structured output), nunca como agente
  que decide el flujo.
- El score de matching se calcula con reglas + embeddings y sub-scores
  explicables (cobertura de must-haves, semántica, seniority, salario,
  ubicación). NUNCA lo decide texto libre de un modelo; el LLM solo redacta
  explicaciones a partir de sub-scores ya calculados.
- Único componente conversacional/agéntico permitido: el simulador de
  entrevistas.

Racional: predecible, barato, debuggeable y auditable. La explicabilidad del
matching es una feature del producto, no un extra.

### IV. Veracidad no negociable (NO NEGOCIABLE)

- El PERFIL MAESTRO (`candidate_profile`) es la única fuente de verdad sobre el
  candidato: entidad estructurada, versionada y editable por el usuario,
  sembrada a partir del CV maestro que sube y enriquecida con logros,
  proyectos, historias STAR y respuestas del cuestionario. El archivo original
  se conserva como respaldo, pero NO es la fuente de verdad (ver ADR-005).
- El perfil se compone de entradas atómicas referenciables (`profile_entries`),
  cada una con identificador propio.
- Todo material generado (CV sastre, cartas, mensajes, follow-ups, notas) pasa
  por un verificador que exige que CADA afirmación referencie la entrada del
  perfil maestro que la sustenta (`source_id`).
- Una afirmación sin `source_id` válido NO llega al usuario: se bloquea, se
  regenera con la restricción o se marca para revisión humana.
- Reformular una entrada es válido; exagerarla no. Las evals incluyen casos de
  exageración como fallo.
- Los materiales generados persisten el resultado del verificador y la versión
  del perfil maestro con la que fueron producidos (`generated_assets`).

Racional: un CV con afirmaciones inventadas daña al candidato y destruye la
confianza en el producto. Con entradas referenciables, la verificación es una
comprobación de trazabilidad determinista y barata, no un juicio semántico de
un modelo. Métrica guardián: 0 afirmaciones sin sustento.

### V. Privacidad y cumplimiento (NO NEGOCIABLE)

- Los CVs son datos personales bajo la LFPDPPP (México): aviso de privacidad
  y consentimiento explícito obligatorios.
- Documentos cifrados en reposo; TLS en tránsito.
- PII fuera de logs y de trazas de LLM (redacción obligatoria).
- Derecho de eliminación real y verificable: borrar cuenta = borrar perfil,
  documentos, embeddings y materiales generados (job asíncrono verificable).
- PROHIBIDO el scraping de plataformas cuyos ToS lo prohíben (LinkedIn,
  Indeed, OCC, Computrabajo).
- PROHIBIDO el auto-apply headless con credenciales de usuarios: solo
  assisted-apply con acción final humana.

Racional: el riesgo legal y de baneo de cuentas de usuarios es existencial;
las fuentes legítimas (APIs, correos de alertas, career pages con robots.txt,
URL manual) cubren el alcance sin violar ToS.

### VI. Calidad verificable (NO NEGOCIABLE)

- Tests antes o junto al código (test-first donde sea práctico).
- pytest para unit e integración; integración contra Postgres real con
  testcontainers.
- Todo componente que involucre un LLM requiere evals contra golden set
  corriendo en CI. Cambiar un prompt sin correr evals es un bug.
- Cobertura mínima 80% en `services/` y `domain/`.

Racional: la mayor parte de la lógica es determinista y barata de testear;
las evals convierten los cambios de prompt de acto de fe en cambio medible.

### VII. Simplicidad — YAGNI (NO NEGOCIABLE)

- Una sola base de datos: Postgres 16 + pgvector para todo, incluidos
  embeddings. Sin vector-store aparte.
- Sin microservicios en v1.
- Despliegue con Docker Compose sobre VPS (ver ADR-002); sin Kubernetes en v1.
- Cada dependencia nueva se justifica en el plan de la feature.

Racional: equipo de 2–3 personas y decenas de usuarios en v1; cada pieza de
infraestructura extra es fricción sin beneficio a esta escala.

### VIII. Observabilidad (NO NEGOCIABLE)

- Toda llamada a LLM se traza con costo, latencia y versión de prompt.
- Logs estructurados con structlog.
- Errores capturados en Sentry (backend y frontend).

Racional: operar un producto LLM sin trazas de costo y latencia es volar a
ciegas; los datos de tracing son la base para comparar proveedores (ADR-003).

### IX. Idioma (NO NEGOCIABLE)

- Producto y UX en español primero.
- Código, identificadores, commits y nombres de ramas en inglés.
- Specs y documentación de producto en español.

Racional: los usuarios son hispanohablantes; el código en inglés mantiene
consistencia con el ecosistema y las herramientas.

### X. Control humano (NO NEGOCIABLE)

- El perfil maestro nunca se marca como completo sin revisión y confirmación
  explícita del candidato. No existe camino que omita ese gate.
- Ningún material se envía a terceros sin acción final humana: assisted-apply,
  follow-ups, mensajes a reclutadores y notas post-entrevista se preparan, no
  se envían solos.
- Vokara propone; el candidato decide.

Racional: el candidato es responsable de lo que se dice en su nombre y es quien
mejor conoce su historia. El control humano también es la salvaguarda operativa
que hace viable el modelo assisted-apply del artículo V.

## Restricciones adicionales

- La fuente de verdad de producto es `docs/product/roadmap.md`; el alcance de
  v1 sigue su priorización MoSCoW y su anti-alcance (sección 1.4).
- Las decisiones de arquitectura viven en `docs/adr/` (ADR-001 auth JWT
  propio, ADR-002 VPS + Docker Compose, ADR-003 Gemini detrás del adapter
  LLM, ADR-004 taxonomía de skills propia). PROHIBIDO contradecirlas sin un
  ADR nuevo que las reemplace.
- Stack fijado por el roadmap (sección 5): Python 3.12 + FastAPI + SQLAlchemy
  2.0 + Alembic + Celery/Redis en backend; React 18 + TypeScript + Vite +
  TanStack Query en frontend. Cambios de stack requieren ADR.

## Flujo de desarrollo

- Flujo por feature: `/speckit.specify` → `/speckit.clarify` →
  `/speckit.plan` → `/speckit.tasks` → `/speckit.analyze` →
  `/speckit.implement`. El trabajo vive en ramas `00X-nombre`, nunca directo
  en `main`.
- Ante ambigüedad, spec faltante o conflicto con esta constitución: DETENERSE
  y preguntar antes de implementar.
- CI bloqueante en cada PR: ruff (lint + format), `mypy --strict`, tests,
  evals de LLM cuando aplique, build de imágenes.
- Definition of Done por feature: código tipado + tests + eval (si toca LLM)
  + migración Alembic reversible + entrada en `docs/adr/` si hubo decisión de
  arquitectura.
- Toda revisión de PR verifica el cumplimiento de esta constitución; la
  complejidad añadida debe justificarse en el plan.

## Gobernanza

- Esta constitución prevalece sobre cualquier otra práctica, guía o
  costumbre del proyecto.
- Modificarla requiere un PR aprobado por los fundadores Y un ADR en
  `docs/adr/` que registre la decisión y sus alternativas descartadas.
- Versionado semántico de la constitución: MAJOR para eliminaciones o
  redefiniciones incompatibles de principios; MINOR para principios o
  secciones nuevas o guía materialmente ampliada; PATCH para aclaraciones y
  correcciones de redacción.
- Los diez principios fundamentales son NO NEGOCIABLES: no admiten
  excepciones por conveniencia; solo una enmienda formal puede cambiarlos.

**Version**: 1.1.0 | **Ratified**: 2026-08-09 | **Last Amended**: 2026-08-09
