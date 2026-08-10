# Feature Specification: Onboarding del candidato — del CV maestro al perfil maestro confirmado

**Feature Branch**: `001-candidate-onboarding`

**Created**: 2026-08-09

**Status**: Draft

**Input**: User description: "Onboarding del candidato: el candidato crea cuenta, sube su CV maestro (PDF/DOCX, máx. 10 MB), el sistema siembra el perfil maestro con entradas atómicas identificables marcadas `cv_seed`, el candidato revisa/corrige/elimina/agrega entradas (`user_edited` / `user_added`), completa el cuestionario de objetivos y confirma explícitamente. Solo entonces el perfil pasa a `complete` y queda versionado. Fuera de alcance: matching, ingesta de vacantes, generación de materiales, tracker, notificaciones."

**Referencias normativas**: constitución v1.1.0 (art. III determinismo, art. IV veracidad, art. V privacidad, art. IX idioma, art. X control humano) · `docs/product/roadmap.md` F1.1 y F1.2 · `docs/adr/005-perfil-maestro.md`

## Clarifications

### Session 2026-08-09

- Q: ¿Puede el candidato borrar el archivo de CV que subió sin borrar el perfil maestro que ese archivo sembró? → A: Sí, condicionado a que exista al menos una versión de origen `confirmation`. Mientras el perfil esté solo en `draft` el archivo no se puede borrar y la interfaz explica por qué. Al borrar se advierte explícitamente que se pierde la capacidad de reprocesar y de re-fusionar contra ese archivo; se elimina el binario del almacenamiento pero el registro del documento se conserva marcado como eliminado por el candidato.
- Q: Si el candidato no borra su CV a mano, ¿cuánto tiempo lo conserva Vokara? → A: Mientras la cuenta esté activa, con purga automática del binario tras 12 meses de inactividad de la cuenta (sin login ni actividad; cualquier actividad reinicia el contador), avisando al candidato por correo con antelación. La purga borra el binario y deja el registro del documento marcado como purgado por retención, con el mismo tratamiento que el borrado manual. El perfil y sus entradas sobreviven a la purga.
- Q: ¿Para qué puede usarse el archivo conservado, y puede el sistema reprocesarlo por su cuenta? → A: Usos autorizados: respaldo, descarga por el candidato y reprocesamiento solo a petición explícita. El sistema puede sugerir reprocesar mediante un aviso pasivo dentro de la interfaz del perfil —nunca por correo ni notificación— y el candidato puede desactivar esa sugerencia. Si la acepta, el resultado entra obligatoriamente por el flujo de fusión de FR-030, con sus mismas reglas.
- Q: Al eliminar la cuenta, ¿el borrado es inmediato e irreversible o hay ventana de gracia? → A: Sin ventana de gracia: arranca de inmediato y es irreversible, y el job asíncrono completa en un máximo de 72 horas dejando la verificación de SC-007. Se protege por delante con una confirmación fuerte que exige escribir un texto (el correo de la cuenta o una palabra de confirmación), no solo pulsar un botón, y con la oferta previa de descargar el archivo original y el perfil completo en formato consultable. Que la oferta exista es el requisito; que el candidato la use, no.
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

### User Story 5 - Re-subir el CV maestro sin perder el trabajo manual (Priority: P2)

El candidato que actualizó su CV fuera de Vokara sube una versión nueva del CV maestro. El sistema refresca automáticamente solo las entradas que siguen siendo `cv_seed` puras —las que él nunca tocó—, preserva intactas las `user_edited` y `user_added`, y le presenta los conflictos para que decida entrada por entrada. Aplicar la fusión genera una versión nueva del perfil, de modo que la anterior queda consultable y el candidato puede revertir.

**Why this priority**: el ADR-005 lo identifica como el riesgo principal del modelo de perfil maestro. Perder enriquecimiento manual destruye la confianza en el producto, pero no bloquea el onboarding inicial de un usuario nuevo.

**Independent Test**: sobre un perfil con entradas `cv_seed`, `user_edited` y `user_added`, subir un CV nuevo y verificar que ninguna entrada `user_edited` o `user_added` se pierde ni se sobrescribe sin decisión del candidato, que se generó una versión nueva y que revertir devuelve el perfil al contenido exacto anterior.

**Acceptance Scenarios**:

1. **Given** un perfil con entradas de los tres orígenes, **When** el candidato sube un CV maestro nuevo, **Then** ninguna entrada `user_added` se elimina y ninguna entrada `user_edited` se sobrescribe automáticamente.
2. **Given** una re-subida procesada, **When** el candidato revisa el resultado, **Then** ve de forma explícita qué entradas son nuevas, cuáles tienen conflicto con contenido editado a mano y cuáles quedan sin cambios, y decide entrada por entrada.
3. **Given** una re-subida en curso, **When** el candidato la cancela o el procesamiento falla, **Then** el perfil queda exactamente como estaba antes de la re-subida.
4. **Given** una entrada equivalente que sigue siendo `cv_seed` pura (nunca editada por el candidato), **When** se aplica la re-subida, **Then** el sistema la reemplaza con el contenido del CV nuevo, conservando su identificador y su origen `cv_seed`.
5. **Given** una entrada equivalente con origen `user_edited` o `user_added`, **When** se aplica la re-subida, **Then** el sistema NUNCA la resuelve automáticamente: la presenta como conflicto y el candidato decide entre conservar la suya, tomar la del CV nuevo o quedarse con ambas.
6. **Given** una re-subida aplicada, **When** el candidato consulta el historial, **Then** existe una versión nueva del perfil y la versión anterior a la re-subida sigue siendo consultable.
7. **Given** una re-subida aplicada cuyo resultado no convence al candidato, **When** solicita revertirla, **Then** el perfil vuelve al contenido exacto de la versión anterior a la re-subida, sin pérdida de entradas.
8. **Given** el mismo par de entradas (una existente y una del CV nuevo), **When** el sistema evalúa si son equivalentes, **Then** el resultado es el mismo en cada ejecución y es verificable con casos de prueba explícitos.

---

### User Story 6 - Eliminación verificable de la cuenta (Priority: P2)

El candidato solicita eliminar su cuenta y el sistema borra de forma verificable el CV original, el perfil maestro, todas sus entradas, versiones y derivados. No hay ventana de gracia: antes de confirmar se le ofrece llevarse sus datos y se le advierte que el borrado es irreversible.

**Why this priority**: obligación legal bajo LFPDPPP y requisito no negociable de la constitución (art. V). No bloquea el flujo principal pero debe existir desde esta feature, que es la que crea los datos personales.

**Independent Test**: crear una cuenta, completar el onboarding, solicitar la eliminación y verificar mediante una comprobación automatizada que no queda rastro de CV, perfil, entradas ni versiones.

**Acceptance Scenarios**:

1. **Given** una cuenta con perfil confirmado y CV subido, **When** el candidato solicita la eliminación y la confirma escribiendo el texto de confirmación, **Then** el sistema elimina archivo original, perfil, entradas, versiones y respuestas del cuestionario, y lo reporta como completado.
2. **Given** una eliminación completada, **When** se ejecuta la comprobación de verificación, **Then** el resultado demuestra que no queda ningún dato personal del candidato asociado a esta feature.
3. **Given** un candidato en la pantalla de eliminación, **When** solo pulsa el botón de confirmar sin escribir el texto requerido, **Then** la eliminación no se ejecuta.
4. **Given** un candidato a punto de eliminar su cuenta, **When** revisa la pantalla de confirmación, **Then** se le ofrece descargar el archivo original y el perfil completo en formato consultable antes de continuar, sin que rechazar la descarga bloquee la eliminación.
5. **Given** una eliminación confirmada, **When** el candidato intenta recuperar la cuenta después, **Then** no existe ninguna vía de recuperación: el borrado es irreversible y así se le advirtió antes de confirmar.

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
- **Eliminación de cuenta con un procesamiento en curso**: la eliminación se completa igualmente y cancela el trabajo pendiente.
- **Intento de borrar el archivo con el perfil todavía en `draft`**: se impide y se explica que el archivo solo puede eliminarse una vez que el perfil tenga al menos una versión confirmada.
- **Reprocesar o revertir contra un archivo que el candidato ya borró**: la acción no se ofrece; el sistema indica que el archivo fue eliminado por el propio candidato y en qué fecha. Las entradas que sembró siguen intactas.
- **Reversión de una fusión cuyo archivo de origen fue borrado después**: la reversión sigue siendo posible porque opera sobre versiones del perfil, no sobre el archivo.
- **Cuenta que vuelve a estar activa durante el plazo de aviso de purga**: la purga se cancela y el contador de inactividad se reinicia.
- **Sugerencia de reprocesar desactivada por el candidato**: el aviso deja de mostrarse y el archivo permanece disponible para reprocesar cuando el candidato lo pida por su cuenta.
- **Descarga de un archivo ya borrado o purgado**: la opción no se ofrece y el sistema indica el motivo (eliminado por el candidato o purgado por retención) y la fecha.
- **Purga por inactividad de una cuenta con perfil confirmado**: se purga el binario del archivo; el perfil, sus entradas y sus versiones permanecen intactos y el candidato los encuentra completos al volver.

## Requirements *(mandatory)*

### Functional Requirements

**Subida del CV maestro**

- **FR-001**: El sistema MUST aceptar la subida de un CV maestro en formato PDF o DOCX con tamaño máximo de 10 MB.
- **FR-002**: El sistema MUST rechazar, antes de procesar, archivos que excedan el límite de tamaño, tengan formato no soportado o estén corruptos, indicando el motivo en español y cómo corregirlo.
- **FR-003**: El sistema MUST conservar el archivo original como respaldo asociado al candidato, cifrado en reposo, sin tratarlo como fuente de verdad del perfil.
- **FR-003a**: El sistema MUST limitar los usos del archivo conservado a tres: respaldo, descarga por el candidato y reprocesamiento a petición explícita del candidato. NEVER debe usarse para ningún otro fin sin una decisión de producto que lo autorice expresamente.
- **FR-003b**: Los candidatos MUST poder descargar en cualquier momento el archivo original que subieron, mientras su binario siga disponible.
- **FR-003c**: El sistema MUST permitir reprocesar un archivo ya conservado únicamente a petición explícita del candidato, y NEVER re-sembrar el perfil por iniciativa propia. Cuando el sistema tenga motivos para sugerir un reprocesamiento (por ejemplo, tras mejorar el extractor), MUST hacerlo mediante un aviso pasivo dentro de la interfaz del perfil —NEVER por correo, notificación ni ningún canal que interrumpa al candidato— y MUST permitirle desactivar esa sugerencia.
- **FR-003d**: El resultado de un reprocesamiento aceptado MUST entrar por el flujo de fusión de FR-030 con sus mismas reglas: refresco automático solo de entradas `cv_seed` puras, conflictos contra `user_edited` / `user_added` decididos por el candidato, y versión de origen `cv_merge` que no es vigente hasta que exista una confirmación.
- **FR-004**: El sistema MUST procesar el CV en segundo plano y exponer el estado del procesamiento (en cola, procesando, completado, fallido) al candidato en todo momento.
- **FR-005**: El sistema MUST detectar y rechazar archivos que no sean un CV, con un mensaje claro y sin crear entradas de perfil.
- **FR-006**: El sistema MUST detectar documentos PDF sin capa de texto (escaneados) antes de intentar la extracción, informar al candidato que v1 no procesa documentos escaneados y ofrecerle la captura manual guiada como camino alternativo. El reconocimiento óptico de caracteres (OCR) queda fuera de v1.
- **FR-006a**: El sistema MUST ofrecer una captura manual guiada que permita construir un perfil maestro completo sin haber podido sembrarlo desde un archivo; las entradas así creadas se registran con origen `user_added` y siguen el mismo camino de confirmación y versionado que cualquier otro perfil.
- **FR-007**: El sistema MUST permitir al candidato reintentar el procesamiento tras un fallo, sin perder entradas creadas o editadas manualmente.

**Siembra del perfil maestro**

- **FR-008**: El sistema MUST extraer del CV entradas atómicas de los tipos: experiencia, logro, educación, skill, certificación, idioma y proyecto.
- **FR-009**: El sistema MUST asignar a cada entrada un identificador estable y referenciable que no cambie por ediciones posteriores del contenido.
- **FR-010**: El sistema MUST registrar el origen de cada entrada con uno de los valores `cv_seed`, `user_added` o `user_edited`.
- **FR-011**: El sistema MUST conservar el idioma original del contenido de cada entrada, sin traducirlo.
- **FR-012**: El sistema MUST marcar como incompletas las entradas a las que les falten campos clave (p. ej. experiencia sin fechas, educación sin institución) y NEVER inventar o inferir datos ausentes en el documento.
- **FR-013**: El sistema MUST crear el perfil maestro en estado `draft` al sembrarlo, y NEVER habilitar funcionalidades posteriores del producto mientras el perfil no esté `complete`.

**Revisión y enriquecimiento**

- **FR-014**: Los candidatos MUST poder ver todas las entradas sembradas agrupadas por tipo, con indicación de su origen y de si están incompletas.
- **FR-015**: Los candidatos MUST poder editar cualquier campo de cualquier entrada; al hacerlo, el sistema MUST cambiar su origen a `user_edited` conservando el identificador.
- **FR-016**: Los candidatos MUST poder eliminar entradas que no apliquen.
- **FR-017**: Los candidatos MUST poder crear entradas nuevas de cualquiera de los tipos soportados; el sistema MUST registrarlas con origen `user_added`.
- **FR-018**: El sistema MUST persistir cada cambio de forma que el candidato pueda abandonar y retomar el onboarding sin perder trabajo.

**Cuestionario de objetivos**

- **FR-019**: El sistema MUST capturar, como parte del perfil maestro: puesto objetivo, expectativa salarial (mínimo, máximo y moneda), ubicaciones y preferencia de modalidad remota, industrias de interés y deal-breakers.
- **FR-020**: El sistema MUST validar la coherencia del rango salarial (mínimo ≤ máximo, moneda explícita) y rechazar valores inválidos con explicación en español.
- **FR-021**: Los candidatos MUST poder modificar sus respuestas del cuestionario en cualquier momento antes de confirmar.

**Confirmación y versionado**

- **FR-022**: El sistema MUST exigir una acción de confirmación explícita del candidato para que el perfil pase a estado `complete`. NEVER debe existir un camino —automático, por reintento, por importación o administrativo— que marque un perfil como `complete` sin esa acción.
- **FR-023**: El sistema MUST impedir la confirmación cuando falten los campos obligatorios del cuestionario o cuando el perfil no tenga al menos una entrada, indicando exactamente qué falta.
- **FR-024**: El sistema MUST crear, en cada confirmación, una versión consultable e inmutable del perfil (entradas y respuestas del cuestionario) con marca de tiempo.
- **FR-024a**: El sistema MUST registrar en cada versión qué la originó: la confirmación explícita del candidato (`confirmation`) o la aplicación de una fusión por re-subida de CV (`cv_merge`). Ambas nacen de una acción humana explícita y ambas son consultables y revertibles, pero solo una versión de origen `confirmation` puede ser la versión vigente que el resto del producto consume (constitución art. X). Una fusión aplicada sobre un perfil `complete` deja sus cambios como trabajo en curso hasta que el candidato confirme.
- **FR-025**: El sistema MUST permitir consultar el historial de versiones del perfil de un candidato y recuperar el contenido íntegro de cualquier versión pasada.
- **FR-026**: El sistema MUST mantener el perfil en estado `complete` cuando el candidato edita entradas o respuestas del cuestionario después de una confirmación. Los cambios quedan como trabajo en curso sobre la última versión confirmada y NEVER degradan el perfil a `draft`.
- **FR-026a**: El sistema MUST distinguir el contenido de trabajo en curso de la última versión confirmada, y MUST servir siempre la última versión confirmada a cualquier consumidor del perfil fuera del onboarding. Los cambios sin confirmar NEVER entran en circulación.
- **FR-026b**: El sistema MUST indicar al candidato, de forma visible, cuándo tiene cambios sin confirmar y en qué consisten, y MUST permitirle confirmarlos para generar una versión nueva.

**Re-subida y fusión**

- **FR-027**: El sistema MUST permitir subir un CV maestro nuevo cuando ya existe un perfil, aplicando la misma validación y procesamiento que la primera subida.
- **FR-028**: El sistema MUST garantizar que una re-subida NEVER elimine entradas con origen `user_added` ni sobrescriba entradas con origen `user_edited` sin decisión explícita del candidato.
- **FR-029**: El sistema MUST presentar al candidato el resultado de la fusión antes de aplicarla, distinguiendo entradas nuevas, entradas refrescadas automáticamente, entradas en conflicto y entradas sin cambios, y MUST dejar el perfil intacto si la re-subida se cancela o falla.
- **FR-030**: El sistema MUST aplicar la siguiente estrategia de fusión al re-subir un CV maestro:
  - **a. Refresco automático acotado**: solo las entradas que siguen siendo `cv_seed` puras —sembradas por un CV anterior y nunca editadas por el candidato— se reemplazan automáticamente con el contenido equivalente del CV nuevo, conservando su identificador y su origen `cv_seed`.
  - **b. Conflictos siempre humanos**: cuando una entrada del CV nuevo es equivalente a una entrada `user_edited` o `user_added`, el sistema NEVER la resuelve automáticamente. La presenta como conflicto y el candidato decide entre conservar la existente, adoptar la del CV nuevo o mantener ambas (constitución art. X).
  - **c. Entradas sin equivalente**: las del CV nuevo se incorporan como entradas nuevas con origen `cv_seed`; las existentes sin equivalente en el CV nuevo se conservan, cualquiera que sea su origen, y NEVER se eliminan automáticamente.
  - **d. Versión y reversibilidad**: aplicar una fusión MUST generar una versión nueva del perfil. La versión anterior a la re-subida MUST quedar consultable, y el candidato MUST poder revertir el perfil a ella recuperando su contenido exacto.
- **FR-030a**: El sistema MUST definir un criterio explícito de equivalencia entre una entrada existente y una entrada del CV nuevo, por tipo de entrada. El criterio MUST ser determinista —la misma pareja de entradas produce siempre el mismo veredicto— y MUST ser verificable con un conjunto de casos de prueba que cubra equivalencias positivas, negativas y ambiguas. Ante ambigüedad, el criterio MUST inclinarse a tratarlas como entradas distintas antes que a fusionarlas por error.

**Privacidad y eliminación**

- **FR-031**: El sistema MUST obtener consentimiento explícito del candidato y mostrar el aviso de privacidad antes de aceptar la primera subida de CV.
- **FR-031a**: Los candidatos MUST poder eliminar un archivo de CV subido sin eliminar el perfil maestro que sembró, siempre que el perfil tenga al menos una versión de origen `confirmation`. Mientras el perfil no tenga ninguna versión confirmada, el sistema MUST impedir esa eliminación y explicar al candidato por qué (el perfil todavía no es autónomo del archivo).
- **FR-031b**: El sistema MUST advertir al candidato, antes de que confirme la eliminación de un archivo, que perderá la capacidad de reprocesar ese archivo y de fusionar contra él en el futuro. La eliminación MUST requerir confirmación explícita.
- **FR-031c**: Al eliminar un archivo a petición del candidato, el sistema MUST borrar el binario del almacenamiento y MUST conservar el registro del documento marcado como eliminado por el candidato, con la fecha. Las entradas `cv_seed` sembradas por ese archivo MUST permanecer intactas, conservando su identificador y su origen, y su referencia al documento MUST seguir siendo consultable como documento eliminado.
- **FR-031d**: El sistema MUST conservar el archivo de CV mientras la cuenta esté activa y MUST purgar automáticamente su binario tras 12 meses de inactividad de la cuenta. El reloj de retención MUST medir inactividad de la cuenta —ausencia de inicio de sesión y de cualquier actividad del candidato—, NEVER tiempo transcurrido desde la subida del archivo. Cualquier actividad de la cuenta MUST reiniciar el contador.
- **FR-031e**: El sistema MUST avisar al candidato por correo antes de purgar sus archivos por inactividad, con antelación suficiente para que pueda reactivar su cuenta o descargar el archivo, y MUST cancelar la purga si el candidato registra actividad dentro de ese plazo.
- **FR-031f**: La purga por retención MUST borrar el binario del almacenamiento y conservar el registro del documento marcado como purgado por retención, con la fecha, recibiendo el mismo tratamiento que el borrado manual de FR-031c: las entradas `cv_seed` que sembró permanecen intactas y su referencia sigue siendo consultable. El perfil, sus entradas y sus versiones NEVER se purgan por inactividad.
- **FR-032**: El sistema MUST eliminar, ante la solicitud de baja de cuenta, el archivo original, el perfil, todas sus entradas, todas sus versiones y las respuestas del cuestionario, y MUST exponer una verificación comprobable de que la eliminación se completó. La eliminación de cuenta MUST borrar también los registros de documentos previamente marcados como eliminados por el candidato: la marca de FR-031c es minimización de datos dentro de una cuenta viva, NEVER un sustituto del derecho de eliminación del art. V.
- **FR-032a**: La eliminación de cuenta MUST arrancar de inmediato al confirmarse y MUST ser irreversible. NEVER existe una ventana de gracia ni un estado intermedio recuperable. El proceso MUST completarse en un máximo de 72 horas desde la solicitud.
- **FR-032b**: El sistema MUST exigir, para confirmar la eliminación, que el candidato escriba un texto —el correo de su cuenta o una palabra de confirmación—, NEVER solo la pulsación de un botón de confirmación.
- **FR-032c**: El sistema MUST ofrecer al candidato, antes de que confirme la eliminación, descargar el archivo original y el perfil maestro completo (entradas, respuestas del cuestionario y versiones) en un formato consultable fuera de Vokara. El requisito es que la oferta exista y funcione; que el candidato la use es su decisión y NEVER condiciona la eliminación.
- **FR-033**: El sistema MUST mantener los datos personales del CV (nombre, contacto, historial) fuera de registros de actividad y trazas de procesamiento.
- **FR-033a**: Los archivos, perfiles y entradas de candidatos reales NEVER se usan para construir el golden set, correr evals ni ajustar prompts. El golden set se compone exclusivamente de material ajeno al producto (propio del equipo, de voluntarios fuera del servicio, o sintético).
- **FR-033b**: Habilitar en el futuro el uso de material de usuarios reales con fines de evaluación MUST requerir un ADR propio y un consentimiento opt-in separado del consentimiento de uso del servicio, explícito y revocable en cualquier momento. NEVER puede habilitarse por la vía de modificar el aviso de privacidad ni apoyándose en el consentimiento general del servicio.
- **FR-034**: El sistema MUST restringir el acceso al perfil, sus entradas, versiones y archivos exclusivamente al candidato propietario.

### Key Entities *(include if feature involves data)*

- **Perfil maestro (`candidate_profile`)**: entidad estructurada 1:1 con el candidato; fuente única de verdad sobre él. Atributos: estado (`draft` | `complete`), objetivos de búsqueda (puesto, rango salarial y moneda, ubicaciones y modalidad remota, industrias, deal-breakers), fecha de última confirmación, referencia a la versión vigente y señal de si hay cambios sin confirmar. Distingue el contenido de trabajo en curso (lo que el candidato edita) de la versión vigente (lo que el resto del producto consume).
- **Entrada de perfil (`profile_entry`)**: unidad atómica y referenciable del perfil. Atributos: identificador estable, tipo (experiencia | logro | educación | skill | certificación | idioma | proyecto), contenido estructurado, idioma original, origen (`cv_seed` | `user_added` | `user_edited`), señal de completitud, referencia al documento que la sembró (si aplica).
- **Documento de CV maestro (`document`)**: archivo original subido por el candidato. Atributos: formato, tamaño, hash, fecha de subida, ubicación de almacenamiento cifrado, estado de procesamiento, y estado de disponibilidad del binario (almacenado | eliminado por el candidato | purgado por retención, con fecha). Un candidato puede tener varios a lo largo del tiempo; el más reciente es el vigente. Un documento con el binario eliminado conserva su registro y sus referencias desde las entradas, pero ya no admite reprocesamiento ni fusión.
- **Versión del perfil (`profile_version`)**: instantánea inmutable del perfil. Atributos: número o identificador de versión, marca de tiempo, origen (`confirmation` | `cv_merge`), contenido completo de entradas y objetivos en ese momento. Solo las de origen `confirmation` pueden ser la versión vigente; todas son consultables y sirven como punto de restauración. Es la unidad que los materiales generados referenciarán en features posteriores.
- **Trabajo de procesamiento (`parse_job`)**: unidad de trabajo en segundo plano que convierte un documento en entradas sembradas. Atributos: documento asociado, estado, progreso, resultado o motivo de error.
- **Propuesta de fusión (`merge_proposal`)**: resultado de una re-subida antes de aplicarse. Atributos: documento nuevo, entradas nuevas, entradas `cv_seed` a refrescar automáticamente, entradas en conflicto con contenido manual (`user_edited` / `user_added`) con la decisión del candidato por cada una, entradas sin cambios, y la versión del perfil previa a la aplicación, que es el punto de reversión.
- **Criterio de equivalencia entre entradas**: regla determinista, definida por tipo de entrada, que decide si una entrada existente y una del CV nuevo describen el mismo hecho. Es lo que habilita el refresco automático de FR-030a y su calidad determina el riesgo de la fusión; se especifica y se prueba explícitamente, no se deja al criterio del implementador.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de los perfiles en estado `complete` tiene una confirmación explícita registrada del candidato; ninguna otra vía produce ese estado (verificable por auditoría del historial de todos los perfiles).
- **SC-002**: El 100% de las entradas del perfil tiene identificador estable y origen registrado (`cv_seed` | `user_added` | `user_edited`).
- **SC-003**: La tasa de error de extracción sobre el golden set de CVs es menor al 5% de los campos evaluados.
- **SC-004**: El candidato percibe menos de 60 segundos de espera entre la subida del CV y la aparición de las entradas para revisar, en el percentil 95 de los CVs del golden set.
- **SC-005**: En 100% de las re-subidas de prueba con entradas `user_added` y `user_edited` presentes, ninguna de esas entradas se pierde ni se sobrescribe sin decisión del candidato.
- **SC-005a**: En 100% de las re-subidas aplicadas, el candidato puede revertir el perfil a su contenido exacto previo a la re-subida.
- **SC-005b**: El criterio de equivalencia entre entradas tiene un conjunto de casos de prueba que cubre equivalencias positivas, negativas y ambiguas por cada tipo de entrada, y produce el mismo veredicto en ejecuciones repetidas sobre la misma pareja.
- **SC-006**: Cada confirmación genera exactamente una versión consultable; el historial permite recuperar el contenido íntegro del perfil en cualquier confirmación pasada.
- **SC-006a**: El 100% de las versiones vigentes (las que consume el resto del producto) tiene origen `confirmation`; ninguna versión generada por una fusión pasa a vigente sin confirmación posterior del candidato.
- **SC-007**: Tras eliminar una cuenta, una comprobación automatizada confirma, dentro de las 72 horas siguientes a la solicitud, que no queda ningún dato del CV, perfil, entradas ni versiones asociados a ese candidato, incluidos los registros de documentos marcados como eliminados por el candidato.
- **SC-007a**: Tras eliminar un archivo a petición del candidato, el binario deja de ser recuperable del almacenamiento y el 100% de las entradas que sembró sigue intacto y con su identificador original.
- **SC-007b**: Ningún archivo de CV sobrevive más de 12 meses de inactividad de la cuenta, y el 100% de las purgas por retención va precedida de un aviso al candidato; ninguna purga elimina perfiles, entradas ni versiones.
- **SC-007c**: El 100% de los reprocesamientos de un archivo conservado nace de una petición explícita del candidato y pasa por el flujo de fusión; ninguna re-siembra se aplica al perfil por iniciativa del sistema.
- **SC-008**: El 80% de los candidatos que suben un CV llega a confirmar su perfil en la misma sesión, en menos de 15 minutos desde la subida.
- **SC-009**: Al menos el 60% de los candidatos agrega o edita al menos una entrada durante la revisión (señal de que el gate de enriquecimiento cumple su función y no es un "siguiente, siguiente").
- **SC-010**: El 100% de los archivos que no son CVs, están corruptos, exceden el límite o tienen formato no soportado se rechazan con un mensaje que el candidato puede accionar, sin crear entradas de perfil.
- **SC-011**: El 100% de los PDF escaneados sin capa de texto se detectan antes de la extracción y encaminan al candidato a la captura manual guiada; ninguno produce un perfil sembrado vacío o con contenido basura.
- **SC-012**: Un candidato que no pudo sembrar su perfil desde un archivo puede llegar igualmente a un perfil `complete` mediante la captura manual guiada.

## Assumptions

- El registro, inicio de sesión y autenticación del candidato ya existen (ADR-001) y no forman parte de esta feature; el onboarding arranca con un candidato autenticado.
- El aviso de privacidad y su texto legal se redactan fuera de esta spec (Fase 0 del roadmap); aquí solo se especifica el momento y la obligatoriedad del consentimiento.
- La normalización de skills contra la taxonomía propia (ADR-004, F1.2) es una feature aparte. Esta spec captura las skills como entradas del perfil con su texto original; la normalización se aplicará sobre ellas después.
- Las historias STAR (F3.4) son un tipo de entrada del perfil maestro previsto en el ADR-005, pero se pueblan en la feature de preparación de entrevistas, no en el onboarding.
- Un candidato tiene un solo perfil maestro. Múltiples perfiles u objetivos paralelos quedan fuera de v1.
- El límite de 10 MB y los formatos PDF/DOCX cubren los CVs del mercado objetivo; otros formatos (imágenes, ODT, texto plano) quedan fuera de v1.
- "Espera percibida < 60 s" se mide desde que el candidato termina la subida hasta que puede empezar a revisar entradas, no desde el inicio de la transferencia del archivo.
- El golden set de CVs (roadmap §6.4) existe o se construye como parte del trabajo de esta feature; es la base de medición de SC-003. Se arma con material ajeno al producto (FR-033a): el roadmap ya lo planea antes de tener usuarios, así que esta feature no depende de datos de candidatos reales para cumplir SC-003.
- Los campos obligatorios del cuestionario para poder confirmar son: puesto objetivo, al menos una ubicación o preferencia de remoto, y expectativa salarial con moneda. Industrias y deal-breakers son opcionales.
- El perfil requiere al menos una entrada para poder confirmarse; no se exige un mínimo por tipo.
- El OCR queda fuera de v1 (FR-006). Si la beta muestra que los CVs escaneados son una porción relevante del mercado objetivo, se reevalúa en v1.x con su propio ADR si introduce una dependencia nueva (art. VII).
- La captura manual guiada (FR-006a) reutiliza la misma interfaz de creación de entradas de la User Story 2; no es un flujo paralelo con su propio modelo de datos.
- El trabajo en curso sobre un perfil `complete` no es una versión: solo se materializa como versión al confirmarse (FR-024) o al aplicarse una fusión (FR-024a). No se guardan versiones automáticas por cada edición.
- "Formato consultable fuera de Vokara" (FR-032c) significa que el candidato pueda abrir y leer sus datos sin la plataforma: el archivo original tal cual lo subió, y el perfil en un formato estructurado y legible. El formato concreto se decide en el plan.
- "Antelación suficiente" para el aviso de purga (FR-031e) se interpreta como 30 días naturales antes de la fecha de purga. El valor es configurable y debe coincidir con lo que declare el aviso de privacidad.
- "Actividad de la cuenta" a efectos del reloj de retención (FR-031d) incluye iniciar sesión y cualquier acción del candidato sobre su perfil; la definición exacta del conjunto de eventos se cierra en el plan.
- El criterio de equivalencia entre entradas (FR-030a) se define en el plan, por tipo de entrada. Su definición precisa —qué campos comparar y con qué tolerancia— es trabajo de diseño, pero su carácter determinista y testeable es requisito de esta spec, no una decisión abierta.

## Fuera de alcance

Explícitamente NO forman parte de esta feature:

- Motor de matching y score explicable (F1.5).
- Ingesta y normalización de vacantes por cualquier canal (F1.3, F1.4).
- Generación de materiales: CV sastre, cartas, mensajes, follow-ups (F2.1–F2.3, F2.5, F2.6) y el verificador de veracidad que los acompaña.
- Tracker de aplicaciones (F2.4) y analítica del embudo (F2.7).
- Alertas, digest y notificaciones de producto (F1.6). El aviso previo a la purga por retención (FR-031e) NO cae en esta exclusión: es un correo transaccional exigido por la política de retención, no una notificación de producto. Es el único correo que esta feature envía.
- Normalización de skills contra la taxonomía propia (F1.2, ADR-004).
- Banco de historias STAR y simulador de entrevistas (F3.x).
- Registro, login y gestión de sesión del candidato (ADR-001).
- Uso de material de candidatos reales para evals, golden set o ajuste de prompts (FR-033a). Habilitarlo más adelante exige ADR propio y consentimiento opt-in separado (FR-033b), no es un ajuste de alcance de esta feature.
