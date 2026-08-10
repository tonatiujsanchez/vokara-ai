# Feature Specification: Ciclo de vida de los datos de la cuenta — retención, borrado y eliminación

**Feature Branch**: `006-account-data-lifecycle`

**Created**: 2026-08-10 (extraída de la spec 001 tras la sesión de clarify del 2026-08-09)

**Status**: Draft

**Input**: Ciclo de vida del CV maestro y de los datos de la cuenta: qué usos tiene el archivo conservado, cuánto tiempo vive, cómo lo borra el candidato sin perder su perfil, cómo se purga por inactividad y cómo se elimina la cuenta completa de forma verificable.

**Referencias normativas**: constitución v1.1.1 (art. V privacidad y cumplimiento, art. IX idioma, art. X control humano) · `docs/product/roadmap.md` §7 · `docs/adr/005-perfil-maestro.md`

## Dependencias y features relacionadas

**Depende de 001 — Onboarding del candidato** (`specs/001-candidate-onboarding/spec.md`). Esta spec presupone que ya existen:

- el perfil maestro con estados `draft` / `complete` (001, FR-014, FR-023),
- entradas atómicas con identificador estable y origen `cv_seed` / `user_added` / `user_edited` (001, FR-010, FR-011),
- el versionado del perfil con versiones de origen `confirmation` (001, FR-025, FR-026),
- el archivo original conservado cifrado (001, FR-003), cuyo ciclo de vida especifica esta feature.

**Relacionada con 007 — Fusión del perfil maestro al re-subir el CV** (`specs/007-master-profile-merge/spec.md`): el reprocesamiento a petición que aquí se autoriza (FR-003, FR-004) desemboca en el flujo de fusión definido en 007. Sin 007, el reprocesamiento no tiene destino; el resto de esta spec es independiente.

**No cubre**: la subida, el parseo, la revisión ni la confirmación del perfil (001), ni la estrategia de fusión (007).

## Clarifications

### Session 2026-08-09

Decisiones tomadas en la sesión de clarify de la feature 001 y reubicadas aquí sin cambios.

- Q: ¿Puede el candidato borrar el archivo de CV que subió sin borrar el perfil maestro que ese archivo sembró? → A: Sí, condicionado a que exista al menos una versión de origen `confirmation`. Mientras el perfil esté solo en `draft` el archivo no se puede borrar y la interfaz explica por qué. Al borrar se advierte explícitamente que se pierde la capacidad de reprocesar y de re-fusionar contra ese archivo; se elimina el binario del almacenamiento pero el registro del documento se conserva marcado como eliminado por el candidato.
- Q: Si el candidato no borra su CV a mano, ¿cuánto tiempo lo conserva Vokara? → A: Mientras la cuenta esté activa, con purga automática del binario tras 12 meses de inactividad de la cuenta (sin login ni actividad; cualquier actividad reinicia el contador), avisando al candidato por correo con antelación. La purga borra el binario y deja el registro del documento marcado como purgado por retención, con el mismo tratamiento que el borrado manual. El perfil y sus entradas sobreviven a la purga.
- Q: ¿Para qué puede usarse el archivo conservado, y puede el sistema reprocesarlo por su cuenta? → A: Usos autorizados: respaldo, descarga por el candidato y reprocesamiento solo a petición explícita. El sistema puede sugerir reprocesar mediante un aviso pasivo dentro de la interfaz del perfil —nunca por correo ni notificación— y el candidato puede desactivar esa sugerencia. Si la acepta, el resultado entra obligatoriamente por el flujo de fusión de la feature 007, con sus mismas reglas.
- Q: Al eliminar la cuenta, ¿el borrado es inmediato e irreversible o hay ventana de gracia? → A: Sin ventana de gracia: arranca de inmediato y es irreversible, y el job asíncrono completa en un máximo de 72 horas dejando la verificación. Se protege por delante con una confirmación fuerte que exige escribir un texto (el correo de la cuenta o una palabra de confirmación), no solo pulsar un botón, y con la oferta previa de descargar el archivo original y el perfil completo en formato consultable. Que la oferta exista es el requisito; que el candidato la use, no.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Borrar el CV sin perder el perfil (Priority: P1)

El candidato ya confirmó su perfil y prefiere que Vokara no siga guardando el archivo con sus datos personales. Lo elimina desde su cuenta: el sistema le advierte qué pierde, borra el binario y deja el perfil, sus entradas y sus versiones exactamente como estaban.

**Why this priority**: es el ejercicio más directo de control sobre el dato más sensible que el candidato entrega, y solo tiene sentido una vez que el perfil es autónomo del archivo (ADR-005: el archivo no es la fuente de verdad).

**Independent Test**: sobre una cuenta con perfil confirmado, borrar el archivo y verificar que el binario no es recuperable, que todas las entradas `cv_seed` siguen intactas con su identificador y que el registro del documento queda marcado con la causa.

**Acceptance Scenarios**:

1. **Given** un perfil con al menos una versión de origen `confirmation`, **When** el candidato elimina el archivo de CV, **Then** el binario deja de existir en el almacenamiento y el perfil, sus entradas y sus versiones permanecen intactos.
2. **Given** un perfil que nunca ha sido confirmado (solo `draft`), **When** el candidato intenta eliminar el archivo, **Then** el sistema lo impide y explica que el archivo solo puede borrarse cuando el perfil tenga al menos una versión confirmada.
3. **Given** un candidato a punto de borrar su archivo, **When** revisa la confirmación, **Then** se le advierte explícitamente que perderá la capacidad de reprocesar ese archivo y de fusionar contra él, y la eliminación exige confirmación explícita.
4. **Given** un archivo eliminado por el candidato, **When** se consulta una entrada que ese archivo sembró, **Then** la entrada conserva identificador y origen, y su referencia al documento sigue siendo consultable indicando que fue eliminado por el candidato y en qué fecha.

---

### User Story 2 - Retención acotada por inactividad (Priority: P1)

El candidato dejó de usar Vokara hace un año. Antes de cumplirse el plazo de retención, recibe un aviso; si no vuelve, el sistema purga el binario de su CV. Su perfil sigue ahí, completo, el día que decida volver.

**Why this priority**: el roadmap §7 compromete "retención definida" y la LFPDPPP espera un plazo explícito. Sin esto, el archivo se conserva de forma indefinida y sin base defendible.

**Independent Test**: simular una cuenta con 12 meses de inactividad y verificar que se emitió el aviso previo, que el binario se purgó, que el registro quedó marcado como purgado por retención y que perfil, entradas y versiones sobrevivieron.

**Acceptance Scenarios**:

1. **Given** una cuenta sin actividad durante 12 meses, **When** vence el plazo de retención, **Then** el sistema purga el binario del archivo y deja el registro del documento marcado como purgado por retención con su fecha.
2. **Given** una cuenta próxima al plazo de purga, **When** el sistema va a purgar, **Then** el candidato recibió antes un aviso por correo con antelación suficiente para reactivar su cuenta o descargar el archivo.
3. **Given** una cuenta avisada de purga inminente, **When** el candidato registra cualquier actividad dentro del plazo, **Then** la purga se cancela y el contador de inactividad se reinicia.
4. **Given** una cuenta purgada por inactividad, **When** el candidato vuelve, **Then** encuentra su perfil, sus entradas y todas sus versiones completos; solo el binario del archivo ya no está.
5. **Given** un archivo subido hace 18 meses en una cuenta usada la semana pasada, **When** se evalúa la retención, **Then** el archivo NO se purga: el reloj mide inactividad de la cuenta, no antigüedad del archivo.

---

### User Story 3 - Usos autorizados y reprocesamiento a petición (Priority: P2)

El candidato puede descargar su archivo cuando quiera. Si Vokara mejora su extractor, se lo hace saber con un aviso discreto dentro de la aplicación; reprocesar es decisión suya, y el resultado nunca pisa su perfil sin pasar por la revisión de conflictos.

**Why this priority**: define el límite entre respaldo pasivo y material de trabajo reutilizable. No bloquea el onboarding, pero sin este límite el archivo conservado se convierte en una tentación de re-sembrar automáticamente (art. X).

**Independent Test**: verificar que el archivo se puede descargar, que ningún reprocesamiento se aplica sin petición del candidato y que el aviso de sugerencia se puede desactivar.

**Acceptance Scenarios**:

1. **Given** un archivo con binario disponible, **When** el candidato pide descargarlo, **Then** obtiene el archivo original tal como lo subió.
2. **Given** una mejora del extractor, **When** el sistema quiere sugerir reprocesar, **Then** lo hace mediante un aviso pasivo dentro de la interfaz del perfil, nunca por correo ni notificación, y nunca aplica nada por su cuenta.
3. **Given** un candidato al que no le interesa la sugerencia, **When** la desactiva, **Then** el aviso deja de mostrarse y el archivo sigue disponible para reprocesar cuando él lo pida.
4. **Given** un candidato que acepta reprocesar, **When** el reprocesamiento termina, **Then** el resultado entra por el flujo de fusión de la feature 007 con sus mismas reglas y nunca se aplica directamente al perfil.
5. **Given** un archivo cuyo binario fue borrado o purgado, **When** el candidato busca descargarlo o reprocesarlo, **Then** la acción no se ofrece y el sistema indica la causa y la fecha.

---

### User Story 4 - Eliminación verificable de la cuenta (Priority: P1)

El candidato decide irse. Antes de confirmar se le ofrece llevarse sus datos y se le advierte que no hay vuelta atrás; para confirmar tiene que escribir algo, no solo pulsar un botón. El borrado arranca de inmediato y es verificable.

**Why this priority**: obligación legal bajo LFPDPPP y requisito no negociable de la constitución (art. V).

**Independent Test**: crear una cuenta, completar el onboarding, eliminarla y verificar mediante una comprobación automatizada que no queda rastro de archivo, perfil, entradas, versiones ni registros de documentos.

**Acceptance Scenarios**:

1. **Given** una cuenta con perfil confirmado y CV subido, **When** el candidato solicita la eliminación y la confirma escribiendo el texto de confirmación, **Then** el sistema elimina archivo, perfil, entradas, versiones y respuestas del cuestionario, y lo reporta como completado.
2. **Given** una eliminación solicitada, **When** transcurren 72 horas, **Then** la comprobación de verificación demuestra que no queda ningún dato personal del candidato.
3. **Given** un candidato en la pantalla de eliminación, **When** solo pulsa el botón de confirmar sin escribir el texto requerido, **Then** la eliminación no se ejecuta.
4. **Given** un candidato a punto de eliminar su cuenta, **When** revisa la pantalla de confirmación, **Then** se le ofrece descargar el archivo original y el perfil completo en formato consultable, sin que rechazar la descarga bloquee la eliminación.
5. **Given** una eliminación confirmada, **When** el candidato intenta recuperar la cuenta después, **Then** no existe ninguna vía de recuperación: el borrado es irreversible y así se le advirtió antes de confirmar.
6. **Given** una cuenta con documentos previamente marcados como eliminados por el candidato o purgados por retención, **When** se elimina la cuenta, **Then** esos registros también desaparecen.

---

### Edge Cases

- **Intento de borrar el archivo con el perfil todavía en `draft`**: se impide y se explica que el archivo solo puede eliminarse una vez que el perfil tenga al menos una versión confirmada.
- **Reprocesar o revertir contra un archivo que el candidato ya borró**: la acción no se ofrece; el sistema indica que el archivo fue eliminado por el propio candidato y en qué fecha. Las entradas que sembró siguen intactas.
- **Cuenta que vuelve a estar activa durante el plazo de aviso de purga**: la purga se cancela y el contador de inactividad se reinicia.
- **Sugerencia de reprocesar desactivada por el candidato**: el aviso deja de mostrarse y el archivo permanece disponible para reprocesar cuando el candidato lo pida por su cuenta.
- **Descarga de un archivo ya borrado o purgado**: la opción no se ofrece y el sistema indica el motivo (eliminado por el candidato o purgado por retención) y la fecha.
- **Purga por inactividad de una cuenta con perfil confirmado**: se purga el binario del archivo; el perfil, sus entradas y sus versiones permanecen intactos y el candidato los encuentra completos al volver.
- **Eliminación de cuenta con un procesamiento en curso**: la eliminación se completa igualmente y cancela el trabajo pendiente.
- **Cuenta con varios archivos en distintos estados**: cada documento lleva su propio estado de disponibilidad y su propia causa; la purga y el borrado operan por documento, no por cuenta.

## Requirements *(mandatory)*

### Functional Requirements

**Usos autorizados del archivo conservado**

- **FR-001**: El sistema MUST limitar los usos del archivo conservado a tres: respaldo, descarga por el candidato y reprocesamiento a petición explícita del candidato. NEVER debe usarse para ningún otro fin sin una decisión de producto que lo autorice expresamente.
- **FR-002**: Los candidatos MUST poder descargar en cualquier momento el archivo original que subieron, mientras su binario siga disponible.
- **FR-003**: El sistema MUST permitir reprocesar un archivo ya conservado únicamente a petición explícita del candidato, y NEVER re-sembrar el perfil por iniciativa propia. Cuando el sistema tenga motivos para sugerir un reprocesamiento (por ejemplo, tras mejorar el extractor), MUST hacerlo mediante un aviso pasivo dentro de la interfaz del perfil —NEVER por correo, notificación ni ningún canal que interrumpa al candidato— y MUST permitirle desactivar esa sugerencia.
- **FR-004**: El resultado de un reprocesamiento aceptado MUST entrar por el flujo de fusión de la feature 007 con sus mismas reglas: refresco automático solo de entradas `cv_seed` puras, conflictos contra `user_edited` / `user_added` decididos por el candidato, y versión de origen `cv_merge` que no es vigente hasta que exista una confirmación.

**Borrado del archivo a petición del candidato**

- **FR-005**: Los candidatos MUST poder eliminar un archivo de CV subido sin eliminar el perfil maestro que sembró, siempre que el perfil tenga al menos una versión de origen `confirmation`. Mientras el perfil no tenga ninguna versión confirmada, el sistema MUST impedir esa eliminación y explicar al candidato por qué (el perfil todavía no es autónomo del archivo).
- **FR-006**: El sistema MUST advertir al candidato, antes de que confirme la eliminación de un archivo, que perderá la capacidad de reprocesar ese archivo y de fusionar contra él en el futuro. La eliminación MUST requerir confirmación explícita.
- **FR-007**: Al eliminar un archivo a petición del candidato, el sistema MUST borrar el binario del almacenamiento y MUST conservar el registro del documento marcado como eliminado por el candidato, con la fecha. Las entradas `cv_seed` sembradas por ese archivo MUST permanecer intactas, conservando su identificador y su origen, y su referencia al documento MUST seguir siendo consultable como documento eliminado.

**Retención y purga por inactividad**

- **FR-008**: El sistema MUST conservar el archivo de CV mientras la cuenta esté activa y MUST purgar automáticamente su binario tras 12 meses de inactividad de la cuenta. El reloj de retención MUST medir inactividad de la cuenta —ausencia de inicio de sesión y de cualquier actividad del candidato—, NEVER tiempo transcurrido desde la subida del archivo. Cualquier actividad de la cuenta MUST reiniciar el contador. El plazo MUST ser configurable, NEVER una constante en código.
- **FR-009**: El sistema MUST avisar al candidato por correo antes de purgar sus archivos por inactividad, con antelación suficiente para que pueda reactivar su cuenta o descargar el archivo, y MUST cancelar la purga si el candidato registra actividad dentro de ese plazo.
- **FR-010**: La purga por retención MUST borrar el binario del almacenamiento y conservar el registro del documento marcado como purgado por retención, con la fecha, recibiendo el mismo tratamiento que el borrado manual de FR-007: las entradas `cv_seed` que sembró permanecen intactas y su referencia sigue siendo consultable. El perfil, sus entradas y sus versiones NEVER se purgan por inactividad.

**Estado de los documentos**

- **FR-011**: Cada documento MUST registrar el estado de disponibilidad de su binario con uno de tres valores —`disponible`, `eliminado_por_candidato`, `purgado_por_retencion`— junto con la fecha del cambio. Un documento sin binario MUST conservar su registro y las referencias de las entradas que sembró, y NEVER admite descarga, reprocesamiento ni fusión.

**Eliminación de la cuenta**

- **FR-012**: El sistema MUST eliminar, ante la solicitud de baja de cuenta, el archivo original, el perfil, todas sus entradas, todas sus versiones y las respuestas del cuestionario, y MUST exponer una verificación comprobable de que la eliminación se completó. La eliminación de cuenta MUST borrar también los registros de documentos previamente marcados como eliminados por el candidato o purgados por retención: esas marcas son minimización de datos dentro de una cuenta viva, NEVER un sustituto del derecho de eliminación del art. V.
- **FR-013**: La eliminación de cuenta MUST arrancar de inmediato al confirmarse y MUST ser irreversible. NEVER existe una ventana de gracia ni un estado intermedio recuperable. El proceso MUST completarse en un máximo de 72 horas desde la solicitud.
- **FR-014**: El sistema MUST exigir, para confirmar la eliminación, que el candidato escriba un texto —el correo de su cuenta o una palabra de confirmación—, NEVER solo la pulsación de un botón de confirmación.
- **FR-015**: El sistema MUST ofrecer al candidato, antes de que confirme la eliminación, descargar el archivo original y el perfil maestro completo (entradas, respuestas del cuestionario y versiones) en un formato consultable fuera de Vokara. El requisito es que la oferta exista y funcione; que el candidato la use es su decisión y NEVER condiciona la eliminación.

### Trazabilidad — FR anterior → FR nuevo

Numeración de la spec 001 unificada (previa al split del 2026-08-10) frente a la de esta feature:

| FR en 001 unificada | FR en 006 | Nota |
|---|---|---|
| FR-003a | FR-001 | usos autorizados |
| FR-003b | FR-002 | descarga |
| FR-003c | FR-003 | reprocesamiento a petición, sugerencia pasiva desactivable |
| FR-003d | FR-004 | el resultado entra por la fusión de 007 |
| FR-031a | FR-005 | borrado condicionado a versión `confirmation` |
| FR-031b | FR-006 | advertencia previa |
| FR-031c | FR-007 | binario fuera, registro marcado |
| FR-031d | FR-008 | 12 meses de inactividad de cuenta; plazo configurable |
| FR-031e | FR-009 | aviso previo y cancelación por actividad |
| FR-031f | FR-010 | purga: binario fuera, perfil intacto |
| — | FR-011 | **nuevo como requisito**, sin decisión nueva: los tres estados de disponibilidad estaban descritos en la entidad `document` de la spec 001 unificada |
| FR-032 | FR-012 | eliminación de cuenta + verificación |
| FR-032a | FR-013 | inmediata, irreversible, ≤ 72 h |
| FR-032b | FR-014 | confirmación escrita |
| FR-032c | FR-015 | exportación previa ofrecida |

| SC en 001 unificada | SC en 006 |
|---|---|
| SC-007 | SC-001 |
| SC-007a | SC-002 |
| SC-007b | SC-003 |
| SC-007c | SC-004 |

### Key Entities *(include if feature involves data)*

- **Documento de CV maestro (`document`)** — *extiende la entidad definida en 001*: además de formato, tamaño, hash, fecha de subida, almacenamiento cifrado y estado de procesamiento, registra el **estado de disponibilidad del binario** (`disponible` | `eliminado_por_candidato` | `purgado_por_retencion`) con la fecha del cambio. Un documento sin binario conserva su registro y las referencias de las entradas que sembró, pero ya no admite descarga, reprocesamiento ni fusión.
- **Reloj de retención de la cuenta**: marca de última actividad del candidato y fecha calculada de purga derivada de ella. Cualquier actividad la desplaza; el aviso previo y la purga se programan a partir de este dato, nunca de la fecha de subida del archivo.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Tras eliminar una cuenta, una comprobación automatizada confirma, dentro de las 72 horas siguientes a la solicitud, que no queda ningún dato del CV, perfil, entradas ni versiones asociados a ese candidato, incluidos los registros de documentos marcados como eliminados por el candidato o purgados por retención.
- **SC-002**: Tras eliminar un archivo a petición del candidato, el binario deja de ser recuperable del almacenamiento y el 100% de las entradas que sembró sigue intacto y con su identificador original.
- **SC-003**: Ningún archivo de CV sobrevive más de 12 meses de inactividad de la cuenta, y el 100% de las purgas por retención va precedida de un aviso al candidato; ninguna purga elimina perfiles, entradas ni versiones.
- **SC-004**: El 100% de los reprocesamientos de un archivo conservado nace de una petición explícita del candidato y pasa por el flujo de fusión; ninguna re-siembra se aplica al perfil por iniciativa del sistema.

## Assumptions

- El perfil maestro, sus entradas, su versionado y el archivo conservado ya existen tal como los define la feature 001.
- "Formato consultable fuera de Vokara" (FR-015) significa que el candidato pueda abrir y leer sus datos sin la plataforma: el archivo original tal cual lo subió, y el perfil en un formato estructurado y legible. El formato concreto se decide en el plan.
- "Antelación suficiente" para el aviso de purga (FR-009) se interpreta como 30 días naturales antes de la fecha de purga. El valor es configurable y debe coincidir con lo que declare el aviso de privacidad.
- "Actividad de la cuenta" a efectos del reloj de retención (FR-008) incluye iniciar sesión y cualquier acción del candidato sobre su perfil; la definición exacta del conjunto de eventos se cierra en el plan, apoyada en lo que ADR-001 registre sobre sesiones.
- El aviso de privacidad declara los plazos de retención aquí definidos; su redacción legal ocurre fuera de esta spec (Fase 0 del roadmap).
- La eliminación de cuenta abarca, en el alcance de v1, los datos creados por las features 001, 006 y 007. Cuando existan materiales generados, matches y tracker, cada feature suma sus propios datos al mismo proceso de eliminación.

## Fuera de alcance

- Subida, parseo, revisión, enriquecimiento y confirmación del perfil (feature 001).
- Estrategia de fusión al re-subir o reprocesar un CV (feature 007); esta spec solo autoriza el reprocesamiento y lo encamina allí.
- Notificaciones de producto (F1.6). El aviso previo a la purga (FR-009) es un correo transaccional exigido por la política de retención, no una notificación de producto, y es el único correo de esta feature.
- Eliminación de datos de features que todavía no existen (matches, materiales generados, tracker): cada una añadirá los suyos al mismo proceso.
- Retención de respaldos de infraestructura y su rotación: es una decisión de operación, no de producto.
