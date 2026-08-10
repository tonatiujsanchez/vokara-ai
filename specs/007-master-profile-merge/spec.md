# Feature Specification: Fusión del perfil maestro al re-subir el CV

**Feature Branch**: `007-master-profile-merge`

**Created**: 2026-08-10 (extraída de la spec 001 tras la sesión de clarify del 2026-08-09)

**Status**: Draft

**Input**: Re-subir un CV maestro cuando el perfil ya tiene entradas editadas o agregadas a mano, sin destruir ese trabajo: refresco automático acotado a entradas `cv_seed` puras, conflictos decididos por el candidato, versión de origen `cv_merge` consultable y revertible que no entra en circulación hasta una confirmación.

**Referencias normativas**: constitución v1.1.1 (art. III determinismo, art. IV veracidad, art. X control humano) · `docs/product/roadmap.md` F1.1 · `docs/adr/005-perfil-maestro.md` (identifica la fusión al re-subir como el riesgo principal del modelo de perfil maestro)

## Dependencias y features relacionadas

**Depende de 001 — Onboarding del candidato** (`specs/001-candidate-onboarding/spec.md`). Esta spec presupone que ya existen:

- el perfil maestro y su primera siembra desde un CV (001, FR-009 a FR-014),
- entradas atómicas con identificador estable y origen `cv_seed` / `user_added` / `user_edited` (001, FR-010, FR-011, FR-016, FR-018),
- el versionado del perfil, con versiones de origen `confirmation` y la distinción entre trabajo en curso y versión vigente (001, FR-025 a FR-029),
- la validación y el procesamiento en segundo plano de un archivo subido (001, FR-001 a FR-008), que esta feature reutiliza sin cambios.

**Relacionada con 006 — Ciclo de vida de los datos de la cuenta** (`specs/006-account-data-lifecycle/spec.md`): el reprocesamiento a petición que 006 autoriza desemboca en el flujo de fusión definido aquí (006, FR-004), y un archivo cuyo binario fue borrado o purgado ya no admite fusión (006, FR-011).

**No cubre**: la primera siembra del perfil ni el gate de confirmación (001), ni la retención o el borrado del archivo (006).

## Clarifications

### Session 2026-08-09

La estrategia de fusión se decidió durante `/speckit-specify` de la feature 001 (2026-08-09), resolviendo el pendiente que el ADR-005 había diferido explícitamente a esta feature. La sesión de clarify del mismo día añadió la vía de entrada por reprocesamiento. Ambas decisiones se reubican aquí sin cambios.

- Q: Cuando el CV nuevo contiene una entrada equivalente a una que el candidato ya editó a mano, ¿qué hace el sistema? → A: Refresco automático acotado solo a entradas `cv_seed` puras, con tres condiciones firmes: los conflictos contra `user_edited` / `user_added` NUNCA se resuelven automáticamente, se presentan al candidato para que decida; aplicar la fusión genera una versión nueva y la anterior queda consultable y revertible; y el criterio de equivalencia entre entradas debe ser determinista y testeable.
- Q: Un perfil `complete` que recibe cambios después de una confirmación, ¿vuelve a `draft`? → A: No. Permanece `complete` y los cambios entran en circulación solo al confirmar una versión nueva. En consecuencia, una versión de origen `cv_merge` es consultable y revertible pero NEVER es la versión vigente hasta que exista una confirmación posterior.
- Q: ¿Para qué puede usarse el archivo conservado, y puede el sistema reprocesarlo por su cuenta? → A: Reprocesamiento solo a petición explícita del candidato; si la acepta, el resultado entra obligatoriamente por este flujo de fusión con sus mismas reglas (ver feature 006, FR-003 y FR-004).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Re-subir el CV maestro sin perder el trabajo manual (Priority: P1)

El candidato que actualizó su CV fuera de Vokara sube una versión nueva del CV maestro. El sistema refresca automáticamente solo las entradas que siguen siendo `cv_seed` puras —las que él nunca tocó—, preserva intactas las `user_edited` y `user_added`, y le presenta los conflictos para que decida entrada por entrada. Aplicar la fusión genera una versión nueva del perfil, de modo que la anterior queda consultable y el candidato puede revertir.

**Why this priority**: el ADR-005 lo identifica como el riesgo principal del modelo de perfil maestro. Perder enriquecimiento manual destruye la confianza en el producto y es la razón por la que este flujo existe como feature propia.

**Independent Test**: sobre un perfil con entradas `cv_seed`, `user_edited` y `user_added`, subir un CV nuevo y verificar que ninguna entrada `user_edited` o `user_added` se pierde ni se sobrescribe sin decisión del candidato, que se generó una versión nueva y que revertir devuelve el perfil al contenido exacto anterior.

**Acceptance Scenarios**:

1. **Given** un perfil con entradas de los tres orígenes, **When** el candidato sube un CV maestro nuevo, **Then** ninguna entrada `user_added` se elimina y ninguna entrada `user_edited` se sobrescribe automáticamente.
2. **Given** una re-subida procesada, **When** el candidato revisa el resultado, **Then** ve de forma explícita qué entradas son nuevas, cuáles se refrescaron automáticamente, cuáles tienen conflicto con contenido editado a mano y cuáles quedan sin cambios, y decide entrada por entrada.
3. **Given** una re-subida en curso, **When** el candidato la cancela o el procesamiento falla, **Then** el perfil queda exactamente como estaba antes de la re-subida.
4. **Given** una entrada equivalente que sigue siendo `cv_seed` pura (nunca editada por el candidato), **When** se aplica la re-subida, **Then** el sistema la reemplaza con el contenido del CV nuevo, conservando su identificador y su origen `cv_seed`.
5. **Given** una entrada equivalente con origen `user_edited` o `user_added`, **When** se aplica la re-subida, **Then** el sistema NUNCA la resuelve automáticamente: la presenta como conflicto y el candidato decide entre conservar la suya, tomar la del CV nuevo o quedarse con ambas.
6. **Given** una entrada existente sin equivalente en el CV nuevo, **When** se aplica la re-subida, **Then** se conserva, cualquiera que sea su origen.
7. **Given** una re-subida aplicada, **When** el candidato consulta el historial, **Then** existe una versión nueva del perfil y la versión anterior a la re-subida sigue siendo consultable.
8. **Given** una re-subida aplicada cuyo resultado no convence al candidato, **When** solicita revertirla, **Then** el perfil vuelve al contenido exacto de la versión anterior a la re-subida, sin pérdida de entradas.

---

### User Story 2 - La fusión no entra en circulación sin confirmación (Priority: P1)

Aplicar una fusión deja el perfil actualizado para el candidato, pero el resto del producto sigue trabajando con la última versión que él confirmó, hasta que confirme también esta.

**Why this priority**: es lo que hace compatible la reversibilidad de la fusión con el gate de control humano del art. X. Sin esta regla, una re-subida pondría contenido no confirmado en manos del generador de materiales.

**Independent Test**: aplicar una fusión sobre un perfil `complete` y verificar que la versión vigente que consume el resto del producto sigue siendo la última de origen `confirmation` hasta que el candidato confirme.

**Acceptance Scenarios**:

1. **Given** una fusión aplicada sobre un perfil `complete`, **When** cualquier otra parte del producto consulta el perfil, **Then** recibe la última versión de origen `confirmation`, nunca la versión `cv_merge`.
2. **Given** una fusión aplicada, **When** se consulta el historial de versiones, **Then** la versión generada aparece con origen `cv_merge`, es consultable y sirve como punto de restauración.
3. **Given** una fusión aplicada sobre un perfil `complete`, **When** el candidato confirma, **Then** se crea una versión de origen `confirmation` que pasa a ser la vigente.
4. **Given** una fusión aplicada sin confirmar, **When** el candidato revisa su perfil, **Then** el sistema le indica que tiene cambios sin confirmar, igual que con cualquier otra edición (001, FR-029).

---

### User Story 3 - Criterio de equivalencia determinista (Priority: P2)

Para saber si una entrada del CV nuevo es "la misma" que una existente, el sistema aplica una regla explícita por tipo de entrada, siempre la misma, y verificable con casos de prueba.

**Why this priority**: es el mecanismo del que depende todo lo demás. Un criterio flojo fusiona cosas distintas o duplica las iguales, y convierte el refresco automático en un riesgo en vez de una comodidad. Es P2 porque se desarrolla junto al flujo, no antes.

**Independent Test**: ejecutar el conjunto de casos de prueba de equivalencia por tipo de entrada y verificar que el veredicto es estable entre ejecuciones y que los casos ambiguos se resuelven como "entradas distintas".

**Acceptance Scenarios**:

1. **Given** el mismo par de entradas (una existente y una del CV nuevo), **When** el sistema evalúa si son equivalentes, **Then** el resultado es el mismo en cada ejecución.
2. **Given** un par ambiguo, **When** el criterio no alcanza a decidir con confianza, **Then** las trata como entradas distintas antes que fusionarlas por error.
3. **Given** el criterio implementado, **When** se ejecuta su suite de pruebas, **Then** cubre equivalencias positivas, negativas y ambiguas para cada tipo de entrada.

---

### Edge Cases

- **Re-subida sobre un perfil todavía en `draft`**: la fusión opera igual sobre las entradas existentes; el perfil sigue sin habilitar el resto del producto hasta su primera confirmación (001, FR-014).
- **Re-subida del mismo archivo ya procesado**: todas las entradas resultan equivalentes y sin cambios; la propuesta de fusión queda vacía y el sistema lo informa en vez de generar una versión sin contenido nuevo.
- **CV nuevo notablemente más pobre que el anterior** (menos entradas): las entradas existentes sin equivalente se conservan; ninguna desaparece por ausencia en el archivo nuevo.
- **Conflicto que el candidato no resuelve**: la fusión no se aplica hasta que todos los conflictos tienen decisión; el perfil permanece intacto mientras tanto.
- **Reversión de una fusión cuyo archivo de origen fue borrado o purgado después**: la reversión sigue siendo posible porque opera sobre versiones del perfil, no sobre el archivo.
- **Segunda re-subida antes de confirmar la fusión anterior**: solo un flujo de fusión activo por candidato; el sistema informa el estado actual y exige cerrar el anterior.
- **Fusión que dejaría el perfil sin ninguna entrada**: no puede ocurrir, porque ninguna entrada existente se elimina automáticamente; si el candidato decide eliminarlas manualmente, aplica el mínimo de confirmación de 001 (FR-024).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema MUST permitir subir un CV maestro nuevo cuando ya existe un perfil, aplicando la misma validación y procesamiento que la primera subida (feature 001, FR-001 a FR-008).
- **FR-002**: El sistema MUST garantizar que una re-subida NEVER elimine entradas con origen `user_added` ni sobrescriba entradas con origen `user_edited` sin decisión explícita del candidato.
- **FR-003**: El sistema MUST presentar al candidato el resultado de la fusión antes de aplicarla, distinguiendo entradas nuevas, entradas refrescadas automáticamente, entradas en conflicto y entradas sin cambios, y MUST dejar el perfil intacto si la re-subida se cancela o falla.
- **FR-004**: El sistema MUST aplicar la siguiente estrategia de fusión al re-subir un CV maestro:
  - **a. Refresco automático acotado**: solo las entradas que siguen siendo `cv_seed` puras —sembradas por un CV anterior y nunca editadas por el candidato— se reemplazan automáticamente con el contenido equivalente del CV nuevo, conservando su identificador y su origen `cv_seed`.
  - **b. Conflictos siempre humanos**: cuando una entrada del CV nuevo es equivalente a una entrada `user_edited` o `user_added`, el sistema NEVER la resuelve automáticamente. La presenta como conflicto y el candidato decide entre conservar la existente, adoptar la del CV nuevo o mantener ambas (constitución art. X).
  - **c. Entradas sin equivalente**: las del CV nuevo se incorporan como entradas nuevas con origen `cv_seed`; las existentes sin equivalente en el CV nuevo se conservan, cualquiera que sea su origen, y NEVER se eliminan automáticamente.
  - **d. Versión y reversibilidad**: aplicar una fusión MUST generar una versión nueva del perfil. La versión anterior a la re-subida MUST quedar consultable, y el candidato MUST poder revertir el perfil a ella recuperando su contenido exacto.
- **FR-005**: El sistema MUST definir un criterio explícito de equivalencia entre una entrada existente y una entrada del CV nuevo, por tipo de entrada. El criterio MUST ser determinista —la misma pareja de entradas produce siempre el mismo veredicto— y MUST ser verificable con un conjunto de casos de prueba que cubra equivalencias positivas, negativas y ambiguas. Ante ambigüedad, el criterio MUST inclinarse a tratarlas como entradas distintas antes que a fusionarlas por error.
- **FR-006**: El sistema MUST registrar en cada versión qué la originó: la confirmación explícita del candidato (`confirmation`) o la aplicación de una fusión por re-subida de CV (`cv_merge`). Ambas nacen de una acción humana explícita y ambas son consultables y revertibles, pero solo una versión de origen `confirmation` puede ser la versión vigente que el resto del producto consume (constitución art. X). Una fusión aplicada sobre un perfil `complete` deja sus cambios como trabajo en curso hasta que el candidato confirme.

### Trazabilidad — FR anterior → FR nuevo

Numeración de la spec 001 unificada (previa al split del 2026-08-10) frente a la de esta feature:

| FR en 001 unificada | FR en 007 | Nota |
|---|---|---|
| FR-027 | FR-001 | re-subida con la misma validación |
| FR-028 | FR-002 | nunca destruye trabajo manual |
| FR-029 | FR-003 | propuesta previa; perfil intacto si falla |
| FR-030 (a–d) | FR-004 (a–d) | estrategia de fusión, sin cambios |
| FR-030a | FR-005 | criterio de equivalencia determinista y testeable |
| FR-024a | FR-006 | origen de versión `confirmation` / `cv_merge` |

| SC en 001 unificada | SC en 007 |
|---|---|
| SC-005 | SC-001 |
| SC-005a | SC-002 |
| SC-005b | SC-003 |
| SC-006a | SC-004 |

### Key Entities *(include if feature involves data)*

- **Propuesta de fusión (`merge_proposal`)**: resultado de una re-subida antes de aplicarse. Atributos: documento nuevo, entradas nuevas, entradas `cv_seed` a refrescar automáticamente, entradas en conflicto con contenido manual (`user_edited` / `user_added`) con la decisión del candidato por cada una, entradas sin cambios, y la versión del perfil previa a la aplicación, que es el punto de reversión.
- **Criterio de equivalencia entre entradas**: regla determinista, definida por tipo de entrada, que decide si una entrada existente y una del CV nuevo describen el mismo hecho. Es lo que habilita el refresco automático de FR-004a y su calidad determina el riesgo de la fusión; se especifica y se prueba explícitamente, no se deja al criterio del implementador.
- **Versión del perfil (`profile_version`)** — *extiende la entidad definida en 001*: gana el atributo de origen con dos valores posibles, `confirmation` y `cv_merge`. Solo las de origen `confirmation` pueden ser la versión vigente; todas son consultables y sirven como punto de restauración.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En 100% de las re-subidas de prueba con entradas `user_added` y `user_edited` presentes, ninguna de esas entradas se pierde ni se sobrescribe sin decisión del candidato.
- **SC-002**: En 100% de las re-subidas aplicadas, el candidato puede revertir el perfil a su contenido exacto previo a la re-subida.
- **SC-003**: El criterio de equivalencia entre entradas tiene un conjunto de casos de prueba que cubre equivalencias positivas, negativas y ambiguas por cada tipo de entrada, y produce el mismo veredicto en ejecuciones repetidas sobre la misma pareja.
- **SC-004**: El 100% de las versiones vigentes (las que consume el resto del producto) tiene origen `confirmation`; ninguna versión generada por una fusión pasa a vigente sin confirmación posterior del candidato.

## Assumptions

- El perfil maestro, sus entradas con origen, su versionado y el pipeline de subida y parseo ya existen tal como los define la feature 001.
- El criterio de equivalencia entre entradas (FR-005) se define en el plan, por tipo de entrada. Su definición precisa —qué campos comparar y con qué tolerancia— es trabajo de diseño, pero su carácter determinista y testeable es requisito de esta spec, no una decisión abierta.
- Una fusión aplicada genera versión para poder revertir; esa versión no altera lo que el resto del producto consume, que sigue siendo la última de origen `confirmation` (FR-006).
- El reprocesamiento de un archivo ya conservado (feature 006, FR-003) entra por este mismo flujo y no requiere reglas propias.
- Solo hay un flujo de fusión activo por candidato a la vez.

## Fuera de alcance

- Primera siembra del perfil, revisión, cuestionario y gate de confirmación (feature 001).
- Retención, borrado manual y purga del archivo (feature 006); esta feature solo consume archivos cuyo binario siga disponible.
- Fusión de perfiles entre cuentas distintas o importación desde fuentes que no sean un CV maestro subido por el propio candidato.
- Resolución automática de conflictos mediante un modelo: los conflictos son decisión humana por definición (art. X).
