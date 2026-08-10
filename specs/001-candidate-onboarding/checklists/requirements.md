# Specification Quality Checklist: Onboarding del candidato — del CV maestro al perfil maestro confirmado

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-09
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

## Constitution Alignment (Vokara)

- [x] Art. IV — El perfil maestro es fuente de verdad; entradas atómicas con identificador estable y origen registrado (FR-010, FR-011)
- [x] Art. V — Consentimiento, cifrado en reposo, PII fuera de logs y control de acceso (FR-003, FR-030, FR-031, FR-034). El derecho de eliminación se especifica en la feature 006
- [x] Art. IX — Spec en español; identificadores de estado y origen en inglés
- [x] Art. X — Ningún camino marca el perfil como `complete` sin confirmación explícita (FR-023, SC-001)
- [x] ADR-005 — Archivo original como respaldo, no fuente de verdad (FR-003); versionado por confirmación (FR-025). Ciclo de vida del archivo en la feature 006; fusión al re-subir en la 007

## Notes

**Split del 2026-08-10.** Esta spec se dividió en tres sin re-decidir nada: 001 conserva el camino feliz; el ciclo de vida del archivo y de la cuenta pasó a `specs/006-account-data-lifecycle/`; la fusión al re-subir pasó a `specs/007-master-profile-merge/`. La tabla "Trazabilidad — FR anterior → FR nuevo" de cada spec mapea la numeración previa. Las features 006 y 007 aún no tienen checklist propio; generarlos con `/speckit-checklist` antes de planearlas.

Todos los ítems pasan. Las tres ambigüedades abiertas en la primera redacción quedaron resueltas por decisión del producto (2026-08-09):

1. **Fusión al re-subir el CV maestro** — decisión diferida explícitamente por ADR-005 a esta feature. Se adopta **refresco automático acotado a entradas `cv_seed` puras**, con tres condiciones firmes: los conflictos contra `user_edited` / `user_added` nunca se resuelven automáticamente (art. X); aplicar la fusión genera una versión nueva y la anterior queda consultable y revertible; y el criterio de equivalencia entre entradas debe ser determinista y testeable, no criterio del implementador. Vive ahora en 007 (FR-004, FR-005).
2. **PDF escaneado sin capa de texto** (FR-006, FR-007) — sin OCR en v1: se detecta antes de la extracción, se informa la limitación y se encamina a **captura manual guiada**, de modo que el candidato nunca queda sin salida (SC-009, SC-010).
3. **Ediciones posteriores a una confirmación** (User Story 4 / FR-027, FR-028, FR-029) — el perfil **permanece `complete`**; los cambios viven como trabajo en curso sobre la última versión confirmada y solo entran en circulación al confirmar una versión nueva.

Punto de atención para `/speckit-plan`: las decisiones 1 y 3 se cruzan y ahora el cruce vive entre dos specs. Una fusión aplicada genera versión de origen `cv_merge` para poder revertir, pero el resto del producto sigue consumiendo la última versión de origen `confirmation` hasta que el candidato confirme (007/FR-006, 007/SC-004, apoyado en 001/FR-028). Es la lectura que respeta ambas decisiones y el art. X; si el producto prefiere que una fusión aplicada pase a vigente de inmediato, hay que enmendar 007/FR-006 antes de planear.
