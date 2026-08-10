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

- [x] Art. IV — El perfil maestro es fuente de verdad; entradas atómicas con identificador estable y origen registrado (FR-009, FR-010)
- [x] Art. V — Consentimiento, cifrado en reposo, PII fuera de logs y eliminación verificable (FR-031 a FR-034, SC-007)
- [x] Art. IX — Spec en español; identificadores de estado y origen en inglés
- [x] Art. X — Ningún camino marca el perfil como `complete` sin confirmación explícita (FR-022, SC-001)
- [x] ADR-005 — Archivo original como respaldo, no fuente de verdad (FR-003); versionado por confirmación (FR-024, FR-024a); estrategia de fusión al re-subir resuelta y explícita (FR-030, FR-030a)

## Notes

Todos los ítems pasan. Las tres ambigüedades abiertas en la primera redacción quedaron resueltas por decisión del producto (2026-08-09):

1. **Fusión al re-subir el CV maestro** (User Story 5 / FR-030, FR-030a) — decisión diferida explícitamente por ADR-005 a esta feature. Se adopta **refresco automático acotado a entradas `cv_seed` puras**, con tres condiciones firmes: los conflictos contra `user_edited` / `user_added` nunca se resuelven automáticamente (art. X); aplicar la fusión genera una versión nueva y la anterior queda consultable y revertible; y el criterio de equivalencia entre entradas debe ser determinista y testeable (FR-030a, SC-005b), no criterio del implementador.
2. **PDF escaneado sin capa de texto** (FR-006, FR-006a) — sin OCR en v1: se detecta antes de la extracción, se informa la limitación y se encamina a **captura manual guiada**, de modo que el candidato nunca queda sin salida (SC-011, SC-012).
3. **Ediciones posteriores a una confirmación** (User Story 4 / FR-026, FR-026a, FR-026b) — el perfil **permanece `complete`**; los cambios viven como trabajo en curso sobre la última versión confirmada y solo entran en circulación al confirmar una versión nueva.

Punto de atención para `/speckit-plan`: las decisiones 1 y 3 se cruzan. Una fusión aplicada genera versión (`cv_merge`) para poder revertir, pero el resto del producto sigue consumiendo la última versión de origen `confirmation` hasta que el candidato confirme (FR-024a, SC-006a). Es la lectura que respeta ambas decisiones y el art. X; si el producto prefiere que una fusión aplicada pase a vigente de inmediato, hay que enmendar FR-024a antes de planear.
