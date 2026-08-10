# ADR-005 — Perfil maestro como fuente única de verdad del candidato

**Estado:** Aceptado · **Fecha:** 2026-08 · **Enmienda asociada:** constitución v1.1.0

---

## Contexto

El artículo IV de la constitución (Veracidad no negociable) exige que todo
material generado se verifique contra "el perfil base del candidato", pero ese
término no estaba definido en ningún artefacto del proyecto. Sin una definición
precisa, el verificador queda a interpretación del implementador y el guardrail
más importante del producto pierde fuerza.

Además, la generación de CVs adaptados por vacante (F2.1) necesita una base de
contenido más rica que un CV de una hoja: para "adaptar" hace falta tener más
material del que cabe en el documento final, o el modelo termina rellenando —
exactamente lo que el artículo IV prohíbe.

## Decisión

Se adopta el concepto de **perfil maestro** (`candidate_profile`) como fuente
única de verdad sobre el candidato, con estas propiedades:

1. **Es una entidad estructurada en base de datos, no un archivo.** El CV
   maestro que el usuario sube es la *semilla* que lo puebla; el archivo se
   conserva como respaldo y para reprocesamiento futuro, pero no es la fuente
   de verdad.

2. **Se compone de entradas atómicas referenciables** (`profile_entries`), cada
   una con `id` propio y tipo: experiencia, logro, educación, skill,
   certificación, idioma, proyecto, historia STAR.

3. **Es versionado y editable por el usuario.** Crece con el tiempo: logros con
   métricas que no cabían en el CV, proyectos, respuestas del cuestionario de
   objetivos y el banco de historias STAR (F3.4).

4. **Toda afirmación en un material generado referencia su entrada de origen**
   (`source_id`). Una afirmación sin `source_id` válido se bloquea.

5. **Los materiales generados registran la versión del perfil** con la que
   fueron producidos, para auditoría y regeneración.

## Alternativas descartadas

- **CV maestro como archivo de texto libre.** Simple, pero obliga al verificador
  a preguntarle a un LLM "¿esta afirmación está sustentada en este texto?": caro,
  no determinista y contrario al artículo III. Además queda congelado en el
  momento de la subida.
- **Sin perfil maestro; generar cada CV directamente desde el CV original.**
  Reduce el problema a reescribir un documento de una hoja; el modelo no tiene
  material adicional del cual seleccionar y la presión hacia la invención
  aumenta.

## Consecuencias

**Positivas**

- El verificador del artículo IV pasa de juicio semántico de un LLM a una
  **comprobación de trazabilidad determinista**: existe `source_id` válido o no
  existe. Costo casi nulo, testeable con unit tests, alineado al artículo III.
- La generación del CV sastre se convierte en un problema de **selección y
  reformulación** (elegir el subconjunto más relevante de entradas para una
  vacante), no de redacción libre. El riesgo de alucinación baja
  estructuralmente, no por prompt.
- Cartas, mensajes a reclutadores, follow-ups y respuestas del simulador
  comparten la misma base verificable.
- El matching (F1.5) gana señal: skills y logros vienen ya estructurados y
  normalizados contra la taxonomía (ADR-004).

**Costos y riesgos**

- Modelo de datos más complejo que un simple blob de perfil: `candidate_profiles`
  versionado + `profile_entries` + referencias en `generated_assets`.
- La UI de revisión y enriquecimiento del perfil es más trabajo que un formulario
  plano; es el gate de calidad de todo el producto y debe justificar su fricción.
- **Fusión al re-subir un CV maestro:** si el usuario ya editó o agregó entradas
  a mano, un nuevo CV no debe pisarlas. Estrategia resuelta en la feature 001
  (`specs/001-candidate-onboarding/spec.md`): **refresco automático acotado**
  solo a entradas que siguen siendo `cv_seed` puras —nunca tocadas por el
  usuario—, conservando su identificador; los conflictos contra entradas
  `user_edited` o `user_added` NUNCA se resuelven automáticamente, se presentan
  al candidato para que decida entrada por entrada (art. X); y aplicar la
  fusión genera una versión nueva de origen `cv_merge`, consultable y
  revertible al contenido exacto previo, que NO es la versión vigente hasta que
  exista una confirmación explícita (versión de origen `confirmation`). Ver
  FR-030, FR-030a y FR-024a. El riesgo residual se traslada al **criterio de
  equivalencia entre entradas**, que la spec exige determinista y testeable por
  tipo de entrada (FR-030a).
- La reformulación sigue siendo un punto de riesgo: reformular con `source_id`
  válido no garantiza fidelidad al hecho original. Las evals deben incluir casos
  de exageración (p. ej. "participé en" → "lideré").

## Impacto en artefactos existentes

- **Constitución:** enmienda a v1.1.0 (MINOR — amplía guía material sin
  redefinir principios).
- **Roadmap:** F1.1 cambia de "CV → perfil" a "CV maestro → sembrar perfil →
  revisar/enriquecer → confirmar". F2.1 se reformula como selección desde el
  perfil maestro. Sección 4.3 (modelo de datos) incorpora `profile_entries`.
- **Feature 001:** la spec (`specs/001-candidate-onboarding/spec.md`) ya refleja
  el flujo de siembra + enriquecimiento + confirmación explícita y resuelve el
  caso borde de fusión al re-subir (FR-030, FR-030a).
