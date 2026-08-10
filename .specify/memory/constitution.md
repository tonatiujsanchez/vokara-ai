<!--
Sync Impact Report
==================
- Version change: 2.0.0 → 2.1.0 (MINOR: guía materialmente ampliada en un
  principio existente; sin principios nuevos ni eliminados)
- Principio MODIFICADO: VIII. Observabilidad. "Errores capturados en Sentry
  (backend y frontend)" → errores en logs locales estructurados, con el envío a
  un servicio externo sujeto al opt-in explícito del art. V y desactivado por
  defecto.
- CONFLICTO RESUELTO: la contradicción abierta en v2.0.0 entre el art. VIII
  (exigía Sentry) y el art. V (prohíbe enviar reportes de error a terceros por
  defecto) queda cerrada por esta enmienda. El art. V es la norma; el art. VIII
  ya no la contradice, la referencia.
- Principios SIN CAMBIO: I, II, III, IV, V, VI, VII, IX, X, XI.
- Gobernanza: sin cambios (siguen siendo once principios).
- Deferred items / TODOs:
  - Ninguno nuevo. **Pendiente de gobernanza CERRADO:** el ADR exigido para la
    enmienda v2.0.0 es el **ADR-009 — Distribución local-first open source**,
    que registra la decisión y sus alternativas descartadas. Reemplaza al
    ADR-002; el ADR-008 (sin autenticación en v1 local) reemplaza al ADR-001.
    El ADR-006 se conserva vigente con nota.
  - Sigue abierto lo que ya estaba fuera de esta enmienda: `docs/product/roadmap.md`
    (§4, §5, §7, §9) y `specs/001-candidate-onboarding/` describen un producto
    hospedado con cuentas.
- Templates dependientes: sin cambios; plan/spec/tasks leen esta constitución
  en runtime.

Historial previo (v2.0.0, pivote a ejecución local):
- Version change: 1.1.1 → 2.0.0 (MAJOR: redefinición incompatible de
  principios por el pivote a software open source de ejecución local)
- ADR que registra esta enmienda (requisito de gobernanza): **ADR-009 —
  Distribución local-first open source** (`docs/adr/009-distribucion-local-first.md`).
- Contexto del cambio: Vokara deja de ser un servicio hospedado. Cada persona
  clona el repositorio, lo ejecuta en su máquina y aporta su propia API key de
  LLM. Sin backend hospedado, sin cuentas, sin autenticación.
- Principio REDEFINIDO: V. "Privacidad y cumplimiento" → "Privacidad
  local-first y transparencia". Se reescribe alrededor de dos ideas: los datos
  del candidato no salen de su máquina salvo el contenido enviado al proveedor
  de LLM que él mismo configuró, y esa excepción se divulga explícitamente.
  - Añadido: divulgación obligatoria en primera ejecución y en README; cero
    telemetría/analítica/reportes de error a terceros por defecto (telemetría
    futura exige opt-in y ADR propio); API keys leídas de configuración local,
    nunca persistidas en base de datos ni presentes en logs o trazas.
  - Conservado: PII fuera de logs y trazas; prohibición de scraping de
    plataformas con ToS restrictivos; assisted-apply con acción humana final.
  - ELIMINADO: aviso de privacidad LFPDPPP como responsable de datos; cifrado
    en reposo obligatorio; derecho de eliminación como job asíncrono
    verificable. Motivo: sin backend hospedado no hay responsable de datos ni
    base central; borrar es borrar el directorio local.
- Principio MODIFICADO: VII. Simplicidad (YAGNI). "Despliegue con Docker
  Compose sobre VPS (ADR-002)" → "Ejecución local con Docker Compose; sin
  despliegue hospedado en v1". Criterio nuevo: la fricción de instalación es
  parte del alcance del producto.
- Principio AÑADIDO: XI. Portabilidad de proveedor.
- Principios SIN CAMBIO: I, II, III, IV, VI, VIII, IX, X.
- Gobernanza: "diez principios" → "once principios".
- Deferred items / TODOs (estado actualizado en v2.1.0):
  - RESUELTO: el ADR que la gobernanza exigía para esta enmienda es el ADR-009
    (distribución local-first), que además reemplaza al ADR-002; el ADR-008
    (sin autenticación en v1 local) reemplaza al ADR-001. El ADR-006 (SPA) se
    conserva vigente: perdió una de sus cuatro razones, no su conclusión.
  - RESUELTO en v2.1.0: el conflicto entre el art. VIII (exigía Sentry) y el
    art. V (prohíbe enviar reportes de error a terceros por defecto).
- Templates dependientes: sin cambios; plan/spec/tasks leen esta constitución
  en runtime.
- Artefactos de producto a revisar: `docs/product/roadmap.md` (§4 arquitectura,
  §5 stack, §7 seguridad y privacidad, §9 despliegue y operación) describe un
  producto hospedado con cuentas.

Historial previo (v1.1.1, corrección de redacción):
- Version change: 1.1.0 → 1.1.1 (PATCH: corrección de redacción, sin cambio de
  principios)
- Principios: sin cambios. Los diez principios fundamentales permanecen
  idénticos en texto y en alcance.
- Sección modificada: "Restricciones adicionales" — se elimina la enumeración
  de ADRs específicos (001–004) y se sustituye por una referencia genérica a
  `docs/adr/`. Motivo: la lista se desfasaba cada vez que se añadía un ADR (ya
  omitía el 005 y el 006); la regla vinculante no depende de qué ADRs existan
  hoy.
- Deferred items / TODOs: ninguno.
- Templates dependientes: sin cambios; plan/spec/tasks leen esta constitución
  en runtime.

Historial previo (v1.1.0, enmienda por ADR-005):
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

### V. Privacidad local-first y transparencia (NO NEGOCIABLE)

- Los datos del candidato —CV original, perfil maestro, embeddings, materiales
  generados, historial de aplicaciones— NUNCA salen de su máquina. Existe UNA
  sola excepción: el contenido que Vokara envía al proveedor de LLM que el
  propio usuario configuró con su API key.
- Esa excepción se divulga de forma explícita y en texto claro EN LA PRIMERA
  EJECUCIÓN y en el README: qué se envía, a qué proveedor y en qué momento del
  flujo. PROHIBIDO enterrar la divulgación en documentación secundaria o darla
  por sabida.
- Vokara NO envía telemetría, analítica ni reportes de error a terceros por
  defecto. Cualquier telemetría futura exige opt-in explícito del usuario Y un
  ADR propio que la justifique; sin ambas cosas, no se implementa.
- Las API keys se leen de configuración local (variables de entorno o archivo
  de configuración del usuario). PROHIBIDO persistirlas en la base de datos.
  PROHIBIDO que aparezcan en logs, trazas o mensajes de error.
- PII fuera de logs y de trazas de LLM (redacción obligatoria).
- PROHIBIDO el scraping de plataformas cuyos ToS lo prohíben (LinkedIn,
  Indeed, OCC, Computrabajo).
- PROHIBIDO el auto-apply headless con credenciales de usuarios: solo
  assisted-apply con acción final humana.

Racional: sin backend hospedado no hay base de datos central que filtrar ni
responsable de datos que vulnerar. La privacidad deja de ser una promesa
operativa y pasa a ser una propiedad de la arquitectura: el dato está donde el
usuario lo puso. Lo único que la arquitectura no puede garantizar es la llamada
al proveedor de LLM, y por eso esa frontera se compensa con divulgación
explícita: el usuario elige el proveedor, pone su clave y sabe exactamente qué
sale de su máquina. Las prohibiciones de scraping y auto-apply se conservan
porque protegen al usuario del baneo de sus propias cuentas, un riesgo que el
pivote a ejecución local no elimina: lo traslada a su máquina.

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
- Ejecución local con Docker Compose; sin despliegue hospedado en v1. Sin
  Kubernetes.
- La fricción de instalación es parte del alcance del producto, no un detalle
  de operación. Cada servicio que el usuario deba levantar en su máquina reduce
  la adopción, y debe justificarse frente a la alternativa de no tenerlo.
- Cada dependencia nueva se justifica en el plan de la feature.

Racional: equipo de 2–3 personas y decenas de usuarios en v1; cada pieza de
infraestructura extra es fricción sin beneficio a esta escala. En ejecución
local esa fricción ya no la absorbe el equipo: la paga cada persona que intenta
correr Vokara, y quien no logra levantarlo simplemente no lo usa. Un servicio
de más no es deuda operativa, es un usuario menos.

### VIII. Observabilidad (NO NEGOCIABLE)

- Toda llamada a LLM se traza con costo, latencia y versión de prompt.
- Logs estructurados con structlog.
- Errores capturados en logs locales estructurados. El envío de errores a un
  servicio externo (Sentry u otro) está disponible solo bajo el opt-in
  explícito que define el artículo V, y desactivado por defecto.

Racional: operar un producto LLM sin trazas de costo y latencia es volar a
ciegas; los datos de tracing son la base para comparar proveedores (ADR-003).
En ejecución local esas trazas son para el usuario y para quien depure con él,
no para un panel del proyecto: la observabilidad se conserva entera, cambia
únicamente hacia dónde puede salir. Un reporte de error arrastra rutas de
archivo, fragmentos de datos y a veces contenido de prompt, así que enviarlo
por defecto sería la misma fuga que el art. V prohíbe, entrando por la puerta
de la operación.

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

### XI. Portabilidad de proveedor (NO NEGOCIABLE)

- Vokara NO depende de un proveedor de LLM concreto. El adapter del artículo II
  define CAPACIDADES —salida estructurada, embeddings— y cada proveedor las
  implementa o declara explícitamente no soportarlas.
- NINGUNA feature puede asumir un proveedor específico: ni en su lógica, ni en
  sus prompts, ni en sus tests. Un `if provider == "..."` fuera del adapter es
  un bug.
- Si una capacidad requerida no está disponible en el proveedor configurado, la
  feature degrada de forma EXPLÍCITA E INFORMADA: el usuario ve qué no puede
  hacerse y por qué. PROHIBIDA la degradación silenciosa y PROHIBIDO el fallo
  opaco.
- El usuario puede cambiar de proveedor sin perder sus datos. Los vectores
  persisten su `embedding_model` y `embedding_dim` (art. II, ADR-003), de modo
  que cambiar de proveedor implica re-embeber, nunca perder el perfil, los
  documentos ni el historial.

Racional: la API key la pone el usuario, así que el proveedor lo elige el
usuario, no el proyecto. Un candidato con acceso a un proveedor y no a otro debe
poder usar Vokara igual; atarse a uno convertiría una decisión suya en un
requisito nuestro. La degradación explícita es la contraparte honesta de esa
libertad: si el proveedor elegido no puede hacer algo, decirlo es parte del
producto.

## Restricciones adicionales

- La fuente de verdad de producto es `docs/product/roadmap.md`; el alcance de
  v1 sigue su priorización MoSCoW y su anti-alcance (sección 1.4).
- Las decisiones de arquitectura viven en `docs/adr/` y son vinculantes.
  PROHIBIDO contradecirlas sin un ADR nuevo que las reemplace.
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
- Los once principios fundamentales son NO NEGOCIABLES: no admiten
  excepciones por conveniencia; solo una enmienda formal puede cambiarlos.

**Version**: 2.1.0 | **Ratified**: 2026-08-09 | **Last Amended**: 2026-08-10
