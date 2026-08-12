# Specification Quality Checklist: Onboarding del candidato — de la primera ejecución al perfil maestro confirmado

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-09
**Last Updated**: 2026-08-10 (reescritura de la spec por el pivote local-first; numeración de FRs actualizada)
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Constitution Alignment (Vokara v2.1.0)

- [x] Art. IV — El perfil maestro es fuente de verdad; entradas atómicas con identificador estable y origen registrado (FR-025, FR-026); nunca se inventan datos ausentes (FR-028)
- [x] Art. V — Divulgación obligatoria en la primera ejecución, en pantalla y en texto claro, con acuse bloqueante (FR-001, FR-002); cero telemetría y reportes de error a terceros por defecto (FR-001c, FR-046); API keys y App Password en configuración local, nunca en base de datos ni en logs (FR-008, FR-013); PII fuera de logs y trazas (FR-045). El cifrado en reposo ya no aplica: el archivo vive en claro y el riesgo se divulga (FR-018, ADR-007)
- [x] Art. VII — La fricción de la primera ejecución es alcance de producto: dos pasos obligatorios y uno saltable, resumibles (FR-011, FR-014, FR-015), medidos en SC-014 y SC-015
- [x] Art. VIII — Trazas locales con metadatos únicamente; envío externo solo bajo opt-in y desactivado por defecto (FR-046)
- [x] Art. IX — Spec en español; identificadores de estado, origen y entidades en inglés
- [x] Art. X — Ningún camino marca el perfil como `complete` sin confirmación explícita (FR-038, SC-001)
- [x] Art. XI — Preflight de capacidades con sus cuatro resultados diferenciados y degradación explícita e informada (FR-006, FR-007, SC-012, SC-016); proveedores de generación y embeddings independientes (FR-004); ninguna ramificación por nombre de proveedor (Assumptions)
- [x] ADR-005 — Archivo original como respaldo, no fuente de verdad (FR-018); versionado por confirmación (FR-040). Ciclo de vida del archivo en la feature 006; fusión al re-subir en la 007
- [x] ADR-007 — Storage local sin cifrado en reposo, riesgo divulgado en el paso 0 (FR-001d, FR-018)
- [x] ADR-008 — Sin registro, login ni sesiones; `candidate_id` local fijo resuelto por la aplicación y nunca enviado por el cliente; consultas acotadas por propietario y sin exposición fuera de la máquina (FR-003, FR-049)
- [x] ADR-011 — Lista cerrada de proveedores verificados, configuración independiente de generación y embeddings, costo estimado por separado antes de pedir cada llave (FR-004, FR-005, FR-009)
- [x] ADR-012 — Vinculación de correo opcional y visiblemente omitible, con divulgación previa del alcance real de la App Password y de la limitación de Workspace, y lectura restringida a la etiqueta designada (FR-011, FR-012, FR-013)

## Notes

**Reescritura del 2026-08-10 (pivote local-first).** La spec se realineó con la constitución v2.1.0, el roadmap v0.4 y los ADR-007..012. Cambios estructurales: desaparecen cuentas, registro, login y autenticación (ADR-008); entra una User Story de primera ejecución previa a todo lo demás —divulgación bloqueante, configuración independiente de proveedores de generación y embeddings con preflight de capacidades, y vinculación de correo opcional (ADR-011, ADR-012)—; el preflight pasa a requisito funcional con sus cuatro resultados; el cifrado en reposo sale del alcance (ADR-007). La tabla "Trazabilidad — numeración anterior → numeración nueva" de la spec mapea la numeración previa. Las features 006 y 007 aún no tienen checklist propio; generarlos con `/speckit-checklist` antes de planearlas.

**Pendiente que esta spec registra pero no resuelve (para la 006).** Sin cuentas, la 006 pierde la eliminación de cuenta, su job asíncrono verificable y cualquier aviso previo por correo; conserva borrar el archivo, exportar los datos y borrar todo. El roadmap §7.5 mantiene una purga por retención reformulada como "12 meses de inactividad de la instalación": la 006 debe decidir si la conserva en esos términos o la retira. Es un punto abierto de esa spec, no de esta.

**Dependencia externa de esta feature — desbloqueada el 2026-08-11.** FR-009 impide ofrecer un proveedor sin verificación empírica registrada en la tabla "Estado de verificación" del ADR-011. **Google ya está verificado** (`gemini-3.5-flash-lite` para generación, `gemini-embedding-001` truncado a 768 dimensiones para embeddings), así que el paso 1 del wizard tiene al menos un proveedor ofrecible —y es justamente el default sugerido—: FR-009 deja de bloquear la implementación. Los otros cuatro proveedores siguen pendientes (roadmap §10, paso 2) y hasta verificarse no aparecen en la lista; eso degrada la elección del usuario, no la feature.

Dos hallazgos de esa verificación condicionan el plan, no la spec: los parámetros de muestreo (`temperature`, `top_p`, `top_k`) están deprecados en Gemini 3.x y el adapter no debe asumir que existen —el determinismo del art. III lo sostiene la estructura del pipeline (ADR-003, nota del 2026-08-11)—, y los nombres de modelo van en configuración con override por variable de entorno y error accionable, nunca en constantes de código. `plan.md`, `research.md` y `contracts/llm-extraction.md` todavía fijan `temperature=0` como decisión de diseño y deben corregirse antes de implementar.

Todos los ítems pasan. Las tres ambigüedades abiertas en la primera redacción quedaron resueltas por decisión del producto (2026-08-09) y siguen vigentes tras la reescritura:

1. **Fusión al re-subir el CV maestro** — decisión diferida explícitamente por ADR-005. Se adopta **refresco automático acotado a entradas `cv_seed` puras**, con tres condiciones firmes: los conflictos contra `user_edited` / `user_added` nunca se resuelven automáticamente (art. X); aplicar la fusión genera una versión nueva y la anterior queda consultable y revertible; y el criterio de equivalencia entre entradas debe ser determinista y testeable, no criterio del implementador. Vive en 007 (FR-004, FR-005).
2. **PDF escaneado sin capa de texto** (FR-021, FR-022) — sin OCR en v1: se detecta antes de la extracción, se informa la limitación y se encamina a **captura manual guiada**, de modo que el candidato nunca queda sin salida (SC-009, SC-010).
3. **Ediciones posteriores a una confirmación** (User Story 5 / FR-042, FR-043, FR-044) — el perfil **permanece `complete`**; los cambios viven como trabajo en curso sobre la última versión confirmada y solo entran en circulación al confirmar una versión nueva.

Punto de atención para `/speckit-plan`: las decisiones 1 y 3 se cruzan y el cruce vive entre dos specs. Una fusión aplicada genera versión de origen `cv_merge` para poder revertir, pero el resto del producto sigue consumiendo la última versión de origen `confirmation` hasta que el candidato confirme (007/FR-006, 007/SC-004, apoyado en 001/FR-043). Es la lectura que respeta ambas decisiones y el art. X; si el producto prefiere que una fusión aplicada pase a vigente de inmediato, hay que enmendar 007/FR-006 antes de planear.
