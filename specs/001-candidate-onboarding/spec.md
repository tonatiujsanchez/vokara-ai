# Feature Specification: Onboarding del candidato — del CV maestro al perfil maestro confirmado

**Feature Branch**: `001-candidate-onboarding`

**Created**: 2026-08-09

**Last Updated**: 2026-08-10 (split en tres specs: 001 camino feliz, 006 ciclo de vida de datos, 007 fusión al re-subir)

**Status**: Draft

**Input**: User description: "Onboarding del candidato: el candidato crea cuenta, sube su CV maestro (PDF/DOCX, máx. 10 MB), el sistema siembra el perfil maestro con entradas atómicas identificables marcadas `cv_seed`, el candidato revisa/corrige/elimina/agrega entradas (`user_edited` / `user_added`), completa el cuestionario de objetivos y confirma explícitamente. Solo entonces el perfil pasa a `complete` y queda versionado. Fuera de alcance: matching, ingesta de vacantes, generación de materiales, tracker, notificaciones."

**Referencias normativas**: constitución v1.1.1 (art. III determinismo, art. IV veracidad, art. V privacidad, art. IX idioma, art. X control humano) · `docs/product/roadmap.md` F1.1 y F1.2 · `docs/adr/005-perfil-maestro.md`

## Dependencias y features relacionadas

Esta spec cubre el **camino feliz del onboarding**: del CV maestro subido a un perfil maestro confirmado y versionado. Dos comportamientos decididos junto con ella viven en specs propias y **quedan fuera de su alcance**:

| Feature | Qué cubre | Qué queda fuera de 001 |
|---|---|---|
| **006 — Ciclo de vida de los datos de la cuenta** (`specs/006-account-data-lifecycle/spec.md`) | Borrado manual del archivo por el candidato, purga por inactividad de la cuenta, usos autorizados del archivo conservado y reprocesamiento a petición, eliminación de cuenta | 001 especifica que el archivo se conserva cifrado (FR-003), pero NO cuánto tiempo, ni cómo se borra, ni para qué más puede usarse |
| **007 — Fusión del perfil maestro al re-subir el CV** (`specs/007-master-profile-merge/spec.md`) | Re-subida de un CV maestro cuando ya existe perfil, estrategia de fusión, criterio de equivalencia entre entradas, versiones de origen `cv_merge` y reversión | 001 cubre la **primera** siembra. Re-subir un CV cuando ya hay entradas `user_edited` / `user_added` no está especificado aquí |

Ambas dependen de 001: requieren perfil maestro, entradas con origen y versionado ya existentes. 001 no depende de ninguna de las dos y es implementable y demostrable por sí sola.

## Clarifications

### Session 2026-08-09

Decisiones tomadas en la sesión de clarify de la feature 001. Las que corresponden a las otras dos specs están copiadas en ellas.

- Q: ¿Puede el CV de un candidato real acabar en el golden set con el que se mide la calidad de extracción? → A: No en v1. El golden set se arma exclusivamente con material ajeno al producto. Habilitar el uso de material de usuarios reales para evals en el futuro requiere un ADR propio y consentimiento opt-in separado, explícito y revocable; NEVER se habilita por un cambio del aviso de privacidad ni por el consentimiento general del servicio.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Siembra del perfil maestro desde el CV (Priority: P1)

El candidato, ya autenticado y con el aviso de privacidad aceptado, entra al onboarding y sube su CV maestro en PDF o DOCX. El sistema acusa recibo de inmediato, procesa el archivo en segundo plano mostrando progreso y, al terminar, presenta el perfil sembrado: una lista de entradas atómicas (experiencias, logros, educación, skills, certificaciones, idiomas, proyectos), cada una con identificador propio y marcada con origen `cv_seed`. El archivo original queda guardado como respaldo, no como fuente de verdad.

**Why this priority**: sin la siembra no hay nada que revisar. Es la entrada de datos que alimenta el resto del producto y el paso donde se materializa el principio del ADR-005: el perfil es una entidad estructurada, no un archivo.

**Independent Test**: subir un CV del golden set y verificar que se crean entradas atómicas identificables con origen `cv_seed`, que el perfil queda en estado `draft` y que el archivo original es recuperable.

**Acceptance Scenarios**:

1. **Given** un candidato autenticado sin perfil previo, **When** sube un CV maestro válido en PDF de 3 MB, **Then** el sistema acepta el archivo, muestra un indicador de progreso y, al completarse, presenta las entradas extraídas agrupadas por tipo, todas con origen `cv_seed`.
2. **Given** un CV maestro procesado, **When** el candidato consulta cualquier entrada, **Then** cada entrada tiene un identificador estable y referenciable y expone su origen.
3. **Given** un CV maestro procesado, **When** se consulta el estado del perfil, **Then** el perfil está en estado `draft` y ninguna funcionalidad posterior del producto está habilitada.
4. **Given** un CV redactado en inglés, **When** se procesa, **Then** cada entrada conserva el idioma original de su contenido y la interfaz sigue en español.
5. **Given** un archivo DOCX con estructura de dos columnas o tablas, **When** se procesa, **Then** el sistema extrae las entradas sin mezclar contenidos de columnas distintas, o marca como incompletas las entradas que no pudo estructurar con confianza.

---

### User Story 2 - Revisión y enriquecimiento del perfil (Priority: P1)

El candidato ve las entradas sembradas, corrige las que están mal, elimina las que no aplican y —lo más importante— agrega entradas nuevas que no estaban en el CV: logros con métricas, proyectos, contexto adicional. Cada entrada que toca queda marcada con su origen real (`user_edited` para las sembradas que modifica, `user_added` para las que crea).

**Why this priority**: es el gate de calidad de todo el producto (roadmap F1.1, ADR-005). El parseo nunca es perfecto y el CV de una hoja no contiene material suficiente para adaptar CVs por vacante sin inventar. Este paso es la diferencia entre un perfil verificable y uno decorativo.

**Independent Test**: sobre un perfil sembrado, editar una entrada, borrar otra y crear una nueva; verificar que los orígenes quedan registrados correctamente y que los cambios persisten entre sesiones.

**Acceptance Scenarios**:

1. **Given** una entrada con origen `cv_seed`, **When** el candidato modifica cualquiera de sus campos y guarda, **Then** la entrada conserva su identificador y su origen pasa a `user_edited`.
2. **Given** un perfil sembrado, **When** el candidato crea una entrada nueva desde cero, **Then** la entrada recibe identificador propio y origen `user_added`.
3. **Given** una entrada que no aplica, **When** el candidato la elimina, **Then** la entrada deja de formar parte del perfil y no reaparece en revisiones posteriores.
4. **Given** una entrada de experiencia sin fechas o una de educación sin institución, **When** el candidato revisa el perfil, **Then** el sistema la señala como incompleta e indica qué falta, sin bloquear la revisión de las demás entradas.
5. **Given** el candidato abandona el onboarding a media revisión, **When** vuelve más tarde, **Then** recupera su perfil `draft` con todos los cambios guardados y el punto del flujo donde se quedó.

---

### User Story 3 - Cuestionario de objetivos (Priority: P1)

El candidato completa un cuestionario corto que define qué busca: puesto objetivo, expectativa salarial (rango y moneda), ubicaciones y preferencia de remoto, industrias de interés y deal-breakers.

**Why this priority**: sin objetivos no hay criterio de búsqueda; el roadmap lo marca como must-have de v1 (F1.2) y forma parte del mismo perfil maestro versionado.

**Independent Test**: completar el cuestionario sobre un perfil `draft` y verificar que las respuestas quedan asociadas al perfil, son editables y viajan en la versión que se genera al confirmar.

**Acceptance Scenarios**:

1. **Given** un perfil en revisión, **When** el candidato completa puesto objetivo, rango salarial con moneda, ubicaciones/remoto, industrias y deal-breakers, **Then** las respuestas quedan guardadas como parte del perfil maestro.
2. **Given** un rango salarial donde el mínimo es mayor que el máximo, **When** el candidato intenta guardar, **Then** el sistema rechaza el valor y explica el error en español.
3. **Given** un cuestionario con campos obligatorios sin responder, **When** el candidato intenta confirmar el perfil, **Then** el sistema no permite la confirmación e indica exactamente qué falta.

---

### User Story 4 - Confirmación explícita y versionado (Priority: P1)

El candidato revisa un resumen final del perfil y confirma explícitamente que lo que ve es correcto. Solo entonces el perfil pasa a estado `complete`, se genera una versión consultable e inmutable del perfil, y el resto del producto queda habilitado. Lo que el resto del producto consume es siempre la última versión confirmada, no el contenido de trabajo en curso.

**Why this priority**: es un requisito no negociable de la constitución (art. X, control humano) y la base de auditoría del guardrail de veracidad (art. IV): todo material generado deberá registrar con qué versión del perfil se produjo.

**Independent Test**: intentar alcanzar el estado `complete` por cualquier vía sin la acción de confirmación (incluyendo reintentos de parseo y ediciones masivas) y verificar que es imposible; luego confirmar y verificar que se crea una versión consultable.

**Acceptance Scenarios**:

1. **Given** un perfil `draft` con entradas revisadas y cuestionario completo, **When** el candidato ejecuta la acción de confirmación, **Then** el perfil pasa a `complete` y se crea una versión con marca de tiempo, consultable posteriormente.
2. **Given** un perfil `draft` que cumple todos los requisitos de contenido, **When** el candidato NO confirma, **Then** el perfil permanece en `draft` y las funcionalidades posteriores del producto siguen deshabilitadas.
3. **Given** un perfil ya confirmado, **When** se consulta el historial, **Then** cada confirmación aparece como una versión distinta, consultable y no modificable.
4. **Given** un perfil `complete`, **When** el candidato edita entradas o el cuestionario después, **Then** el perfil permanece `complete`, los cambios quedan como trabajo en curso sobre la última versión confirmada y el resto del producto sigue habilitado sin interrupción.
5. **Given** un perfil `complete` con cambios sin confirmar, **When** cualquier otra parte del producto consulta el perfil, **Then** recibe la última versión confirmada, nunca los cambios pendientes.
6. **Given** un perfil `complete` con cambios sin confirmar, **When** el candidato los confirma, **Then** se crea una versión nueva que pasa a ser la vigente y ya no quedan cambios pendientes.
7. **Given** un perfil `complete` con cambios sin confirmar, **When** el candidato revisa el perfil, **Then** el sistema le indica de forma visible que tiene cambios sin confirmar y cuáles son.

---

### Edge Cases

- **PDF escaneado sin capa de texto**: el sistema lo detecta antes de producir un perfil vacío o basura, informa la limitación (v1 no hace OCR) y encamina al candidato a la captura manual guiada, sin dejarlo sin salida.
- **CV con múltiples columnas o tablas**: no debe intercalar texto de columnas distintas; cuando la confianza de estructuración es baja, marca las entradas afectadas como incompletas para que el candidato las corrija.
- **CV en inglés (o mezcla de idiomas)**: cada entrada conserva su idioma original; la interfaz permanece en español.
- **Archivo que no es un CV** (factura, contrato, foto, documento aleatorio): se detecta y se rechaza con un mensaje claro, sin crear entradas ni perfil sembrado.
- **Entradas incompletas** (experiencia sin fechas, educación sin institución): se conservan y se marcan como incompletas; nunca se inventan datos faltantes.
- **CV vacío o con contenido mínimo** (menos entradas que un umbral razonable): se informa al candidato y se le ofrece construir el perfil manualmente.
- **Archivo corrupto o ilegible**: se rechaza con mensaje explicativo y el perfil queda intacto.
- **Archivo que excede 10 MB o de formato no soportado**: se rechaza antes de procesar, indicando límite y formatos aceptados.
- **Fallo del procesamiento en segundo plano**: el candidato ve un estado de error accionable con opción de reintentar; el perfil no queda a medias ni bloqueado.
- **Subida de un CV nuevo mientras otro está procesándose**: solo un procesamiento activo por candidato; el sistema informa el estado actual.
- **Cierre del navegador durante el procesamiento**: al volver, el candidato ve el resultado o el progreso, sin necesidad de re-subir.
- **Confirmación de un perfil sin ninguna entrada**: se impide, indicando el mínimo requerido.

## Requirements *(mandatory)*

### Functional Requirements

**Subida del CV maestro**

- **FR-001**: El sistema MUST aceptar la subida de un CV maestro en formato PDF o DOCX con tamaño máximo de 10 MB.
- **FR-002**: El sistema MUST rechazar, antes de procesar, archivos que excedan el límite de tamaño, tengan formato no soportado o estén corruptos, indicando el motivo en español y cómo corregirlo.
- **FR-003**: El sistema MUST conservar el archivo original como respaldo asociado al candidato, cifrado en reposo, sin tratarlo como fuente de verdad del perfil. Su ciclo de vida —usos autorizados, borrado y purga— se especifica en la feature 006.
- **FR-004**: El sistema MUST procesar el CV en segundo plano y exponer el estado del procesamiento (en cola, procesando, completado, fallido) al candidato en todo momento.
- **FR-005**: El sistema MUST detectar y rechazar archivos que no sean un CV, con un mensaje claro y sin crear entradas de perfil.
- **FR-006**: El sistema MUST detectar documentos PDF sin capa de texto (escaneados) antes de intentar la extracción, informar al candidato que v1 no procesa documentos escaneados y ofrecerle la captura manual guiada como camino alternativo. El reconocimiento óptico de caracteres (OCR) queda fuera de v1.
- **FR-007**: El sistema MUST ofrecer una captura manual guiada que permita construir un perfil maestro completo sin haber podido sembrarlo desde un archivo; las entradas así creadas se registran con origen `user_added` y siguen el mismo camino de confirmación y versionado que cualquier otro perfil.
- **FR-008**: El sistema MUST permitir al candidato reintentar el procesamiento tras un fallo, sin perder entradas creadas o editadas manualmente.

**Siembra del perfil maestro**

- **FR-009**: El sistema MUST extraer del CV entradas atómicas de los tipos: experiencia, logro, educación, skill, certificación, idioma y proyecto.
- **FR-010**: El sistema MUST asignar a cada entrada un identificador estable y referenciable que no cambie por ediciones posteriores del contenido.
- **FR-011**: El sistema MUST registrar el origen de cada entrada con uno de los valores `cv_seed`, `user_added` o `user_edited`.
- **FR-012**: El sistema MUST conservar el idioma original del contenido de cada entrada, sin traducirlo.
- **FR-013**: El sistema MUST marcar como incompletas las entradas a las que les falten campos clave (p. ej. experiencia sin fechas, educación sin institución) y NEVER inventar o inferir datos ausentes en el documento.
- **FR-014**: El sistema MUST crear el perfil maestro en estado `draft` al sembrarlo, y NEVER habilitar funcionalidades posteriores del producto mientras el perfil no esté `complete`.

**Revisión y enriquecimiento**

- **FR-015**: Los candidatos MUST poder ver todas las entradas sembradas agrupadas por tipo, con indicación de su origen y de si están incompletas.
- **FR-016**: Los candidatos MUST poder editar cualquier campo de cualquier entrada; al hacerlo, el sistema MUST cambiar su origen a `user_edited` conservando el identificador.
- **FR-017**: Los candidatos MUST poder eliminar entradas que no apliquen.
- **FR-018**: Los candidatos MUST poder crear entradas nuevas de cualquiera de los tipos soportados; el sistema MUST registrarlas con origen `user_added`.
- **FR-019**: El sistema MUST persistir cada cambio de forma que el candidato pueda abandonar y retomar el onboarding sin perder trabajo.

**Cuestionario de objetivos**

- **FR-020**: El sistema MUST capturar, como parte del perfil maestro: puesto objetivo, expectativa salarial (mínimo, máximo y moneda), ubicaciones y preferencia de modalidad remota, industrias de interés y deal-breakers.
- **FR-021**: El sistema MUST validar la coherencia del rango salarial (mínimo ≤ máximo, moneda explícita) y rechazar valores inválidos con explicación en español.
- **FR-022**: Los candidatos MUST poder modificar sus respuestas del cuestionario en cualquier momento antes de confirmar.

**Confirmación y versionado**

- **FR-023**: El sistema MUST exigir una acción de confirmación explícita del candidato para que el perfil pase a estado `complete`. NEVER debe existir un camino —automático, por reintento, por importación o administrativo— que marque un perfil como `complete` sin esa acción.
- **FR-024**: El sistema MUST impedir la confirmación cuando falten los campos obligatorios del cuestionario o cuando el perfil no tenga al menos una entrada, indicando exactamente qué falta.
- **FR-025**: El sistema MUST crear, en cada confirmación, una versión consultable e inmutable del perfil (entradas y respuestas del cuestionario) con marca de tiempo y origen `confirmation`.
- **FR-026**: El sistema MUST permitir consultar el historial de versiones del perfil de un candidato y recuperar el contenido íntegro de cualquier versión pasada.
- **FR-027**: El sistema MUST mantener el perfil en estado `complete` cuando el candidato edita entradas o respuestas del cuestionario después de una confirmación. Los cambios quedan como trabajo en curso sobre la última versión confirmada y NEVER degradan el perfil a `draft`.
- **FR-028**: El sistema MUST distinguir el contenido de trabajo en curso de la última versión confirmada, y MUST servir siempre la última versión confirmada a cualquier consumidor del perfil fuera del onboarding. Los cambios sin confirmar NEVER entran en circulación.
- **FR-029**: El sistema MUST indicar al candidato, de forma visible, cuándo tiene cambios sin confirmar y en qué consisten, y MUST permitirle confirmarlos para generar una versión nueva.

**Privacidad**

- **FR-030**: El sistema MUST obtener consentimiento explícito del candidato y mostrar el aviso de privacidad antes de aceptar la primera subida de CV.
- **FR-031**: El sistema MUST mantener los datos personales del CV (nombre, contacto, historial) fuera de registros de actividad y trazas de procesamiento.
- **FR-032**: Los archivos, perfiles y entradas de candidatos reales NEVER se usan para construir el golden set, correr evals ni ajustar prompts. El golden set se compone exclusivamente de material ajeno al producto (propio del equipo, de voluntarios fuera del servicio, o sintético).
- **FR-033**: Habilitar en el futuro el uso de material de usuarios reales con fines de evaluación MUST requerir un ADR propio y un consentimiento opt-in separado del consentimiento de uso del servicio, explícito y revocable en cualquier momento. NEVER puede habilitarse por la vía de modificar el aviso de privacidad ni apoyándose en el consentimiento general del servicio.
- **FR-034**: El sistema MUST restringir el acceso al perfil, sus entradas, versiones y archivos exclusivamente al candidato propietario.

### Trazabilidad — FR anterior → FR nuevo

Numeración previa al split del 2026-08-10 (spec 001 unificada) frente a la actual:

| FR anterior | FR en 001 | Nota |
|---|---|---|
| FR-001 – FR-002 | FR-001 – FR-002 | sin cambio |
| FR-003 | FR-003 | conserva el archivo; ciclo de vida delegado a 006 |
| FR-003a – FR-003d | — | movidos a **006** (FR-001 – FR-004) |
| FR-004 – FR-006 | FR-004 – FR-006 | sin cambio |
| FR-006a | FR-007 | captura manual guiada |
| FR-007 | FR-008 | reintento tras fallo |
| FR-008 – FR-013 | FR-009 – FR-014 | siembra |
| FR-014 – FR-018 | FR-015 – FR-019 | revisión y enriquecimiento |
| FR-019 – FR-021 | FR-020 – FR-022 | cuestionario |
| FR-022 – FR-026b | FR-023 – FR-029 | confirmación y versionado |
| FR-024a | — | movido a **007** (FR-006) |
| FR-027 – FR-030a | — | movidos a **007** (FR-001 – FR-005) |
| FR-031 | FR-030 | consentimiento |
| FR-031a – FR-031f | — | movidos a **006** (FR-005 – FR-010) |
| FR-032 – FR-032c | — | movidos a **006** (FR-012 – FR-015) |
| FR-033 | FR-031 | PII fuera de logs |
| FR-033a – FR-033b | FR-032 – FR-033 | golden set |
| FR-034 | FR-034 | control de acceso |

| SC anterior | SC en 001 |
|---|---|
| SC-001 – SC-004 | SC-001 – SC-004 |
| SC-005, SC-005a, SC-005b | movidos a **007** |
| SC-006 | SC-005 |
| SC-006a | movido a **007** |
| SC-007, SC-007a, SC-007b, SC-007c | movidos a **006** |
| SC-008 – SC-012 | SC-006 – SC-010 |

### Key Entities *(include if feature involves data)*

- **Perfil maestro (`candidate_profile`)**: entidad estructurada 1:1 con el candidato; fuente única de verdad sobre él. Atributos: estado (`draft` | `complete`), objetivos de búsqueda (puesto, rango salarial y moneda, ubicaciones y modalidad remota, industrias, deal-breakers), fecha de última confirmación, referencia a la versión vigente y señal de si hay cambios sin confirmar. Distingue el contenido de trabajo en curso (lo que el candidato edita) de la versión vigente (lo que el resto del producto consume).
- **Entrada de perfil (`profile_entry`)**: unidad atómica y referenciable del perfil. Atributos: identificador estable, tipo (experiencia | logro | educación | skill | certificación | idioma | proyecto), contenido estructurado, idioma original, origen (`cv_seed` | `user_added` | `user_edited`), señal de completitud, referencia al documento que la sembró (si aplica).
- **Documento de CV maestro (`document`)**: archivo original subido por el candidato. Atributos: formato, tamaño, hash, fecha de subida, ubicación de almacenamiento cifrado, estado de procesamiento. Un candidato puede tener varios a lo largo del tiempo; el más reciente es el vigente. La feature 006 extiende esta entidad con el estado de disponibilidad del binario.
- **Versión del perfil (`profile_version`)**: instantánea inmutable del perfil. Atributos: número o identificador de versión, marca de tiempo, origen, contenido completo de entradas y objetivos en ese momento. En 001 el único origen posible es `confirmation`; la feature 007 añade el origen `cv_merge`. Es la unidad que los materiales generados referenciarán en features posteriores.
- **Trabajo de procesamiento (`parse_job`)**: unidad de trabajo en segundo plano que convierte un documento en entradas sembradas. Atributos: documento asociado, estado, progreso, resultado o motivo de error.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de los perfiles en estado `complete` tiene una confirmación explícita registrada del candidato; ninguna otra vía produce ese estado (verificable por auditoría del historial de todos los perfiles).
- **SC-002**: El 100% de las entradas del perfil tiene identificador estable y origen registrado (`cv_seed` | `user_added` | `user_edited`).
- **SC-003**: La tasa de error de extracción sobre el golden set de CVs es menor al 5% de los campos evaluados.
- **SC-004**: El candidato percibe menos de 60 segundos de espera entre la subida del CV y la aparición de las entradas para revisar, en el percentil 95 de los CVs del golden set.
- **SC-005**: Cada confirmación genera exactamente una versión consultable; el historial permite recuperar el contenido íntegro del perfil en cualquier confirmación pasada.
- **SC-006**: El 80% de los candidatos que suben un CV llega a confirmar su perfil en la misma sesión, en menos de 15 minutos desde la subida.
- **SC-007**: Al menos el 60% de los candidatos agrega o edita al menos una entrada durante la revisión (señal de que el gate de enriquecimiento cumple su función y no es un "siguiente, siguiente").
- **SC-008**: El 100% de los archivos que no son CVs, están corruptos, exceden el límite o tienen formato no soportado se rechazan con un mensaje que el candidato puede accionar, sin crear entradas de perfil.
- **SC-009**: El 100% de los PDF escaneados sin capa de texto se detectan antes de la extracción y encaminan al candidato a la captura manual guiada; ninguno produce un perfil sembrado vacío o con contenido basura.
- **SC-010**: Un candidato que no pudo sembrar su perfil desde un archivo puede llegar igualmente a un perfil `complete` mediante la captura manual guiada.

## Assumptions

- El registro, inicio de sesión y autenticación del candidato ya existen (ADR-001) y no forman parte de esta feature; el onboarding arranca con un candidato autenticado.
- El aviso de privacidad y su texto legal se redactan fuera de esta spec (Fase 0 del roadmap); aquí solo se especifica el momento y la obligatoriedad del consentimiento.
- La normalización de skills contra la taxonomía propia (ADR-004, F1.2) es una feature aparte. Esta spec captura las skills como entradas del perfil con su texto original; la normalización se aplicará sobre ellas después.
- Las historias STAR (F3.4) son un tipo de entrada del perfil maestro previsto en el ADR-005, pero se pueblan en la feature de preparación de entrevistas, no en el onboarding.
- Un candidato tiene un solo perfil maestro. Múltiples perfiles u objetivos paralelos quedan fuera de v1.
- El límite de 10 MB y los formatos PDF/DOCX cubren los CVs del mercado objetivo; otros formatos (imágenes, ODT, texto plano) quedan fuera de v1.
- "Espera percibida < 60 s" se mide desde que el candidato termina la subida hasta que puede empezar a revisar entradas, no desde el inicio de la transferencia del archivo.
- El golden set de CVs (roadmap §6.4) existe o se construye como parte del trabajo de esta feature; es la base de medición de SC-003. Se arma con material ajeno al producto (FR-032): el roadmap ya lo planea antes de tener usuarios, así que esta feature no depende de datos de candidatos reales.
- Los campos obligatorios del cuestionario para poder confirmar son: puesto objetivo, al menos una ubicación o preferencia de remoto, y expectativa salarial con moneda. Industrias y deal-breakers son opcionales.
- El perfil requiere al menos una entrada para poder confirmarse; no se exige un mínimo por tipo.
- El OCR queda fuera de v1 (FR-006). Si la beta muestra que los CVs escaneados son una porción relevante del mercado objetivo, se reevalúa en v1.x con su propio ADR si introduce una dependencia nueva (art. VII).
- La captura manual guiada (FR-007) reutiliza la misma interfaz de creación de entradas de la User Story 2; no es un flujo paralelo con su propio modelo de datos.
- El trabajo en curso sobre un perfil `complete` no es una versión: solo se materializa como versión al confirmarse (FR-025) o al aplicarse una fusión (feature 007). No se guardan versiones automáticas por cada edición.

## Fuera de alcance

Explícitamente NO forman parte de esta feature:

- **Ciclo de vida del archivo y de la cuenta** (feature 006): borrado manual del archivo, purga por inactividad, descarga, reprocesamiento a petición y eliminación de cuenta.
- **Re-subida y fusión del CV maestro** (feature 007): 001 cubre la primera siembra; re-subir un CV sobre un perfil ya enriquecido se especifica aparte.
- Motor de matching y score explicable (F1.5).
- Ingesta y normalización de vacantes por cualquier canal (F1.3, F1.4).
- Generación de materiales: CV sastre, cartas, mensajes, follow-ups (F2.1–F2.3, F2.5, F2.6) y el verificador de veracidad que los acompaña.
- Tracker de aplicaciones (F2.4) y analítica del embudo (F2.7).
- Alertas, digest y notificaciones (F1.6). Esta feature no envía ningún correo.
- Normalización de skills contra la taxonomía propia (F1.2, ADR-004).
- Banco de historias STAR y simulador de entrevistas (F3.x).
- Registro, login y gestión de sesión del candidato (ADR-001).
- Uso de material de candidatos reales para evals, golden set o ajuste de prompts (FR-032). Habilitarlo más adelante exige ADR propio y consentimiento opt-in separado (FR-033), no es un ajuste de alcance de esta feature.
