# Feature Specification: Onboarding del candidato — de la primera ejecución al perfil maestro confirmado

**Feature Branch**: `001-candidate-onboarding`

**Created**: 2026-08-09

**Last Updated**: 2026-08-10 (reescritura por el pivote local-first: constitución v2.1.0, roadmap v0.4, ADR-007..012)

**Status**: Draft

**Input**: User description: "Onboarding del candidato en una instalación local: el usuario abre Vokara por primera vez, lee la divulgación de qué sale de su máquina y qué no, configura su proveedor de generación y su proveedor de embeddings con sus propias API keys —con verificación previa de capacidades—, opcionalmente vincula su correo, y solo entonces sube su CV maestro (PDF/DOCX, máx. 10 MB). El sistema siembra el perfil maestro con entradas atómicas identificables marcadas `cv_seed`, el candidato revisa/corrige/elimina/agrega entradas (`user_edited` / `user_added`), completa el cuestionario de objetivos y confirma explícitamente. Solo entonces el perfil pasa a `complete` y queda versionado. Fuera de alcance: matching, ingesta de vacantes, generación de materiales, tracker, notificaciones."

**Referencias normativas**: constitución v2.1.0 (art. II adapters, art. III determinismo, art. IV veracidad, art. V privacidad local-first y transparencia, art. VII simplicidad y fricción de instalación, art. VIII observabilidad, art. IX idioma, art. X control humano, art. XI portabilidad de proveedor) · `docs/product/roadmap.md` v0.4 (F1.1, F1.2, §7, §11.2, §11.3, §11.5) · `docs/adr/005-perfil-maestro.md` · `docs/adr/007-almacenamiento-documentos.md` · `docs/adr/008-sin-autenticacion-v1-local.md` · `docs/adr/009-distribucion-local-first.md` · `docs/adr/011-proveedores-llm-y-embeddings.md` · `docs/adr/012-vinculacion-correo-opcional.md`

## Contexto de ejecución

Vokara no se contrata, se ejecuta (ADR-009). Esta feature describe lo que ocurre en **la máquina de una sola persona**: la que instaló Vokara. **No hay registro, login, sesiones ni recuperación de contraseña** (ADR-008); el perfil, sus entradas, sus versiones y sus documentos se asocian al `candidate_id` local fijo de la instalación, que la capa de aplicación resuelve desde configuración local y que el cliente nunca envía.

Por eso el onboarding empieza antes del CV: la primera pantalla no es un formulario de alta, es la divulgación de qué sale de esa máquina y qué no, seguida de la configuración de los proveedores de IA que el propio usuario paga.

## Dependencias y features relacionadas

Esta spec cubre el **camino feliz completo de la primera ejecución**: de abrir Vokara por primera vez a un perfil maestro confirmado y versionado. Dos comportamientos decididos junto con ella viven en specs propias y **quedan fuera de su alcance**:

| Feature | Qué cubre | Qué queda fuera de 001 |
|---|---|---|
| **006 — Ciclo de vida de los datos** (`specs/006-account-data-lifecycle/spec.md`) | Borrado manual del archivo por el candidato, exportación de sus datos en formato consultable y borrado completo de la instalación | 001 especifica que el archivo se conserva en el directorio de datos local (FR-018), pero NO cuánto tiempo, ni cómo se borra, ni para qué más puede usarse |
| **007 — Fusión del perfil maestro al re-subir el CV** (`specs/007-master-profile-merge/spec.md`) | Re-subida de un CV maestro cuando ya existe perfil, estrategia de fusión, criterio de equivalencia entre entradas, versiones de origen `cv_merge` y reversión | 001 cubre la **primera** siembra. Re-subir un CV cuando ya hay entradas `user_edited` / `user_added` no está especificado aquí |

Ambas dependen de 001: requieren perfil maestro, entradas con origen y versionado ya existentes. 001 no depende de ninguna de las dos y es implementable y demostrable por sí sola.

**Efecto del pivote sobre la 006 (pendiente en esa spec, no en esta).** Sin cuentas (ADR-008) la 006 se reduce de forma sustancial: **desaparecen la eliminación de cuenta y su job asíncrono verificable de 72 horas** —no hay cuenta que eliminar ni base central que purgar; desinstalar es borrar el directorio de datos— y **desaparece cualquier aviso previo por correo**, porque no hay servidor que lo envíe (ADR-008, ADR-009). Lo que sobrevive es: **borrar el archivo sin perder el perfil**, **exportar los datos** en formato consultable y **borrar todo** desde la app, inmediato e irreversible y con confirmación escrita. Queda un punto abierto que la 006 debe resolver: el roadmap §7.5 conserva una **purga por retención tras 12 meses de inactividad de la instalación** —reformulada de "inactividad de la cuenta"— con plazo configurable y aviso previo dentro de la app; esta spec no lo decide, solo registra que la referencia original ("purga por inactividad de la cuenta", "eliminación de cuenta") ya no es correcta. También deja de aplicar el cifrado en reposo que la 006 daba por supuesto (ADR-007).

## Clarifications

### Session 2026-08-09

Decisiones tomadas en la sesión de clarify de la feature 001. Las que corresponden a las otras dos specs están copiadas en ellas.

- Q: ¿Puede el CV de un candidato real acabar en el golden set con el que se mide la calidad de extracción? → A: No en v1. El golden set se arma exclusivamente con material ajeno al producto. Habilitar el uso de material de usuarios reales para evals en el futuro requiere un ADR propio y consentimiento opt-in separado, explícito y revocable; NEVER se habilita por un cambio del texto de divulgación ni por el acuse general de la primera ejecución.

### Realineación 2026-08-10 — pivote local-first

No es una sesión de clarify: es la aplicación a esta spec de decisiones ya tomadas y registradas en otros artefactos. Se listan para que la trazabilidad sea explícita.

- **Sin cuentas ni autenticación** (ADR-008). Desaparecen registro, login, verificación por correo y "candidato autenticado" como precondición. Una instalación, un candidato, un `candidate_id` local fijo.
- **La primera ejecución entra al alcance de esta feature** (art. V, roadmap §11.2). La divulgación en primera ejecución es una obligación constitucional, no una pantalla de bienvenida opcional, y sin proveedor configurado no hay parseo de CV posible: el wizard es el prerrequisito real del onboarding, no un vecino suyo.
- **Dos proveedores, no uno** (ADR-011): generación y embeddings se configuran de forma independiente, cada uno con su API key y su costo estimado.
- **El preflight de capacidades es requisito funcional, no detalle de implementación** (art. XI, ADR-011). Es lo que impide que una capacidad ausente se descubra a mitad del uso.
- **Sin cifrado en reposo** (ADR-007): los archivos se guardan en claro en el directorio de datos local y el riesgo se divulga en el paso 0.
- **Vinculación de correo opcional** (ADR-012) como paso final y saltable del wizard.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Primera ejecución: divulgación, proveedores y correo (Priority: P1)

Una persona acaba de levantar Vokara en su máquina y abre la aplicación por primera vez. No hay pantalla de registro: lo primero que ve es **qué se queda en su computadora y qué no**. Después configura el proveedor de IA que va a generar (con su API key) y el proveedor que va a calcular embeddings (con la suya), viendo el costo estimado de cada uno **antes** de pegar nada, y Vokara verifica cada llave y cada capacidad en el momento, no en el primer uso real. Al final se le ofrece —de forma claramente saltable— vincular su Gmail para que Vokara lea la etiqueta donde caen sus alertas de empleo. Si cierra el navegador a mitad del proceso, al volver retoma donde iba.

**Why this priority**: es el prerrequisito literal de todo lo demás. Sin la divulgación aceptada no puede subirse un CV (art. V); sin proveedor de generación verificado no hay parseo posible; y sin preflight, una capacidad ausente aparecería como un fallo opaco a mitad del onboarding, que es exactamente lo que el art. XI prohíbe. Es además el punto donde el riesgo nº 1 del modelo local-first —la fricción de instalación (art. VII, ADR-009)— se gana o se pierde.

**Independent Test**: sobre una instalación limpia, recorrer los pasos obligatorios con una llave válida y verificar que queda registrado el acuse de divulgación, que ambos proveedores quedan configurados con su preflight resuelto, que las credenciales no aparecen en la base de datos ni en los logs, que el paso de correo puede omitirse llegando igual al onboarding, y que interrumpir y reabrir retoma en el paso pendiente.

**Acceptance Scenarios**:

1. **Given** una instalación recién levantada, **When** el usuario abre Vokara por primera vez, **Then** ve la pantalla de divulgación sin ningún campo que llenar, con el texto completo a la vista —qué se queda en su máquina, la única excepción (el contenido del CV y de las vacantes enviado al proveedor de IA que él elija), que Vokara no envía nada a sus creadores y que sus archivos quedan sin cifrar en el disco— y no puede avanzar sin un acuse explícito.
2. **Given** la pantalla de divulgación, **When** el usuario no marca el acuse, **Then** el botón de continuar permanece inhabilitado y ninguna otra parte de la aplicación es alcanzable, incluso navegando directamente a la dirección del onboarding.
3. **Given** el acuse registrado, **When** el usuario llega al paso de proveedores, **Then** ve dos configuraciones separadas —generación y embeddings—, con Gemini presugerido en ambas, la razón de que estén separadas en una línea, y el costo estimado por mes de búsqueda activa de cada una **antes** de que se le pida ninguna llave.
4. **Given** el paso de proveedores, **When** el usuario elige el mismo proveedor para generación y embeddings, **Then** se le pide una sola API key y se verifican las dos capacidades por separado con ella.
5. **Given** una API key de generación válida cuyo modelo cumple salida estructurada, **When** el usuario la guarda, **Then** el preflight hace una llamada de prueba contra un esquema real, la marca como verificada y permite avanzar.
6. **Given** una API key mal copiada o revocada, **When** el usuario la guarda, **Then** el preflight la rechaza con un mensaje que dice qué revisar y dónde regenerarla, sin mostrar la llave, sin traza técnica y sin dejar avanzar.
7. **Given** una API key válida cuyo modelo no garantiza salida estructurada, **When** el preflight termina, **Then** el sistema enumera **qué funciones concretas quedan afectadas y por qué**, ofrece cambiar de proveedor y permite continuar con un acuse específico de esa degradación.
8. **Given** una API key válida cuya cuota está agotada, **When** el preflight la prueba, **Then** el sistema lo distingue explícitamente de una llave inválida —la llave sirve, la cuota no—, indica que puede esperar al reinicio de cuota o elegir otro proveedor, y no da la capacidad por verificada.
9. **Given** los proveedores configurados, **When** el usuario llega al paso de correo, **Then** la opción de omitirlo tiene el mismo peso visual que la de continuar, y la pantalla dice qué se gana vinculando y qué **no** se pierde al omitirlo.
10. **Given** el paso de correo, **When** el usuario decide vincular su Gmail, **Then** antes de pedirle nada se le advierte que una App Password da acceso a **toda** su bandeja y que leer solo la etiqueta designada es un compromiso de Vokara verificado por tests, no un límite que Google imponga, y se le avisa por adelantado que las cuentas de Workspace y de Protección Avanzada no admiten App Passwords.
11. **Given** una App Password y una etiqueta indicadas, **When** el usuario confirma la vinculación, **Then** el sistema verifica que la etiqueta existe y es alcanzable antes de darla por vinculada, y guarda la credencial en configuración local, nunca en la base de datos.
12. **Given** un wizard a medias —acuse hecho y proveedor de generación verificado—, **When** el usuario cierra el navegador y vuelve más tarde, **Then** retoma en el paso de embeddings sin que se le pida de nuevo el acuse ni la llave ya verificada.
13. **Given** los pasos obligatorios completos, **When** el usuario termina u omite el paso de correo, **Then** el onboarding del CV queda habilitado y la primera ejecución no vuelve a mostrarse.

---

### User Story 2 - Siembra del perfil maestro desde el CV (Priority: P1)

El candidato, con la divulgación acusada y sus proveedores configurados, entra al onboarding y sube su CV maestro en PDF o DOCX. El sistema acusa recibo de inmediato, procesa el archivo en segundo plano mostrando progreso y, al terminar, presenta el perfil sembrado: una lista de entradas atómicas (experiencias, logros, educación, skills, certificaciones, idiomas, proyectos), cada una con identificador propio y marcada con origen `cv_seed`. El archivo original queda guardado como respaldo, no como fuente de verdad.

**Why this priority**: sin la siembra no hay nada que revisar. Es la entrada de datos que alimenta el resto del producto y el paso donde se materializa el principio del ADR-005: el perfil es una entidad estructurada, no un archivo.

**Independent Test**: subir un CV del golden set y verificar que se crean entradas atómicas identificables con origen `cv_seed`, que el perfil queda en estado `draft` y que el archivo original es recuperable.

**Acceptance Scenarios**:

1. **Given** una instalación con la primera ejecución completada y sin perfil previo, **When** el candidato sube un CV maestro válido en PDF de 3 MB, **Then** el sistema acepta el archivo, muestra un indicador de progreso y, al completarse, presenta las entradas extraídas agrupadas por tipo, todas con origen `cv_seed`.
2. **Given** un CV maestro procesado, **When** el candidato consulta cualquier entrada, **Then** cada entrada tiene un identificador estable y referenciable y expone su origen.
3. **Given** un CV maestro procesado, **When** se consulta el estado del perfil, **Then** el perfil está en estado `draft` y ninguna funcionalidad posterior del producto está habilitada.
4. **Given** un CV redactado en inglés, **When** se procesa, **Then** cada entrada conserva el idioma original de su contenido y la interfaz sigue en español.
5. **Given** un archivo DOCX con estructura de dos columnas o tablas, **When** se procesa, **Then** el sistema extrae las entradas sin mezclar contenidos de columnas distintas, o marca como incompletas las entradas que no pudo estructurar con confianza.
6. **Given** una instalación sin acuse de divulgación o sin proveedor de generación verificado, **When** se intenta subir un CV por cualquier vía, **Then** el sistema lo impide e indica qué paso de la primera ejecución falta.

---

### User Story 3 - Revisión y enriquecimiento del perfil (Priority: P1)

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

### User Story 4 - Cuestionario de objetivos (Priority: P1)

El candidato completa un cuestionario corto que define qué busca: puesto objetivo, expectativa salarial (rango y moneda), ubicaciones y preferencia de remoto, industrias de interés y deal-breakers.

**Why this priority**: sin objetivos no hay criterio de búsqueda; el roadmap lo marca como must-have de v1 (F1.2) y forma parte del mismo perfil maestro versionado.

**Independent Test**: completar el cuestionario sobre un perfil `draft` y verificar que las respuestas quedan asociadas al perfil, son editables y viajan en la versión que se genera al confirmar.

**Acceptance Scenarios**:

1. **Given** un perfil en revisión, **When** el candidato completa puesto objetivo, rango salarial con moneda, ubicaciones/remoto, industrias y deal-breakers, **Then** las respuestas quedan guardadas como parte del perfil maestro.
2. **Given** un rango salarial donde el mínimo es mayor que el máximo, **When** el candidato intenta guardar, **Then** el sistema rechaza el valor y explica el error en español.
3. **Given** un cuestionario con campos obligatorios sin responder, **When** el candidato intenta confirmar el perfil, **Then** el sistema no permite la confirmación e indica exactamente qué falta.

---

### User Story 5 - Confirmación explícita y versionado (Priority: P1)

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

**Primera ejecución**

- **Cierre del navegador a mitad del wizard**: al volver, retoma en el paso pendiente conservando lo ya resuelto (acuse, llaves verificadas, correo vinculado). Nunca reinicia desde cero ni vuelve a pedir credenciales verificadas.
- **Sin conexión durante el preflight**: se distingue de una llave inválida —no se pudo verificar, no "es incorrecta"— y se ofrece reintentar sin volver a pegar la llave.
- **Proveedor de embeddings que no ofrece la capacidad** (p. ej. elegir Anthropic ahí): se impide seleccionarlo o se explica en el momento que el matching semántico quedaría inoperante y por qué; nunca se descubre después. Un proveedor sin verificación empírica registrada no aparece en la lista.
- **Cuota agotada durante el preflight**: la llave se reconoce válida, la capacidad queda sin verificar y se ofrecen dos salidas concretas (esperar el reinicio de cuota o configurar otro proveedor).
- **App Password rechazada por ser cuenta de Workspace o con Protección Avanzada**: el aviso se dio antes de empezar; el error remite a la vía OAuth documentada y el paso sigue siendo omitible sin consecuencias.
- **La etiqueta de Gmail indicada no existe o está mal escrita**: la vinculación no se da por buena; se indica cómo crear el filtro y la etiqueta.
- **Intento de saltarse el wizard navegando directo al onboarding**: se impide y se indica qué paso falta.

**Onboarding del CV**

- **PDF escaneado sin capa de texto**: el sistema lo detecta antes de producir un perfil vacío o basura, informa la limitación (v1 no hace OCR) y encamina al candidato a la captura manual guiada, sin dejarlo sin salida.
- **CV con múltiples columnas o tablas**: no debe intercalar texto de columnas distintas; cuando la confianza de estructuración es baja, marca las entradas afectadas como incompletas para que el candidato las corrija.
- **CV en inglés (o mezcla de idiomas)**: cada entrada conserva su idioma original; la interfaz permanece en español.
- **Archivo que no es un CV** (factura, contrato, foto, documento aleatorio): se detecta y se rechaza con un mensaje claro, sin crear entradas ni perfil sembrado.
- **Entradas incompletas** (experiencia sin fechas, educación sin institución): se conservan y se marcan como incompletas; nunca se inventan datos faltantes.
- **CV vacío o con contenido mínimo** (menos entradas que un umbral razonable): se informa al candidato y se le ofrece construir el perfil manualmente.
- **Archivo corrupto o ilegible**: se rechaza con mensaje explicativo y el perfil queda intacto.
- **Archivo que excede 10 MB o de formato no soportado**: se rechaza antes de procesar, indicando límite y formatos aceptados.
- **El proveedor rechaza la llave o agota la cuota durante el parseo** (verificada en el wizard, caducada después): el candidato ve un estado de error accionable que apunta a la configuración, no un fallo opaco; el archivo subido no se pierde y el parseo es reintentable.
- **Fallo del procesamiento en segundo plano**: el candidato ve un estado de error accionable con opción de reintentar; el perfil no queda a medias ni bloqueado.
- **Subida de un CV nuevo mientras otro está procesándose**: solo un procesamiento activo; el sistema informa el estado actual.
- **Cierre del navegador durante el procesamiento**: al volver, el candidato ve el resultado o el progreso, sin necesidad de re-subir.
- **El directorio de datos desapareció** (el usuario lo movió o lo borró): el perfil sigue intacto; el sistema informa que el archivo original ya no está y que no puede reprocesarse.
- **Confirmación de un perfil sin ninguna entrada**: se impide, indicando el mínimo requerido.

## Requirements *(mandatory)*

### Functional Requirements

**Primera ejecución y divulgación informada**

- **FR-001**: El sistema MUST presentar, al abrirse por primera vez y antes de cualquier campo que llenar, una pantalla de divulgación en texto claro y en la propia pantalla —NEVER solo un enlace, NEVER solo el README— que exponga: (a) que los datos del candidato —CV original, perfil maestro, embeddings, materiales generados e historial— se quedan en su máquina; (b) que existe **una única excepción**: el contenido que Vokara envía al proveedor de IA que él mismo configure, con el detalle de qué se envía y en qué momento (el CV íntegro al parsearlo, y en features posteriores la descripción de la vacante al analizarla y el perfil al generar materiales); (c) que **Vokara no envía nada a sus creadores**: cero telemetría, analítica o reportes de error a terceros; (d) que sus archivos quedan **sin cifrar** en el disco, con la recomendación de activar el cifrado de disco del sistema operativo.
- **FR-002**: El sistema MUST exigir un acuse explícito y afirmativo de esa divulgación —NEVER preseleccionado, NEVER inferido de continuar— y MUST registrar su marca de tiempo. NEVER debe aceptarse la primera subida de un CV maestro sin ese acuse registrado.
- **FR-003**: El sistema MUST NEVER exigir registro, inicio de sesión, contraseña, sesión ni verificación por correo, y MUST NEVER enviar correo alguno. El perfil, sus entradas, sus versiones y sus documentos se asocian al `candidate_id` local fijo de la instalación, que la aplicación resuelve desde configuración local y que NEVER llega desde el cliente.

**Configuración de proveedores de IA (paso obligatorio)**

- **FR-004**: El sistema MUST permitir configurar, de forma **independiente**, un proveedor de **generación** (salida estructurada) y un proveedor de **embeddings**, cada uno elegido de una lista cerrada predefinida y cada uno con su propia API key. Pueden ser el mismo proveedor o dos distintos, y ninguna de las dos elecciones MUST condicionar a la otra. Si el usuario elige el mismo proveedor para ambos, el sistema MUST pedir la llave una sola vez y verificar ambas capacidades por separado con ella.
- **FR-005**: El sistema MUST mostrar, **antes** de solicitar cada API key, el costo estimado por mes de búsqueda activa del proveedor seleccionado, con el supuesto de uso a la vista, y MUST estimarlo **por separado** para generación y para embeddings. Para el proveedor con capa gratuita MUST indicar qué cabe dentro de ella y a partir de qué punto se empieza a pagar.
- **FR-006**: El sistema MUST ejecutar un **preflight de capacidades** al guardar cada API key —NEVER diferirlo al primer uso real—, que verifique en una misma operación que la credencial es aceptada por el proveedor **y** que la capacidad requerida se cumple: para generación, que el modelo devuelve una respuesta conforme a un esquema estructurado real; para embeddings, que produce un vector y con qué dimensión.
- **FR-007**: El sistema MUST distinguir y comunicar de forma diferenciada los **cuatro** resultados posibles del preflight:
  1. **Credencial rechazada** (inválida, revocada o mal copiada): mensaje accionable que dice qué revisar y dónde regenerarla, NEVER una traza técnica y NEVER el valor de la llave. No se da la capacidad por verificada ni se permite avanzar con ese proveedor.
  2. **Credencial válida y capacidad cumplida**: se marca verificada, con la dimensión del vector registrada en el caso de embeddings, y se permite avanzar.
  3. **Credencial válida sin garantía de la capacidad** (p. ej. salida estructurada no garantizada por el modelo): el sistema MUST enumerar **qué funciones concretas quedan afectadas y por qué**, MUST ofrecer cambiar de proveedor y MUST permitir continuar solo tras un acuse específico de esa degradación. NEVER degradación silenciosa, NEVER fallo opaco.
  4. **Cuota agotada o límite de tasa alcanzado**: el sistema MUST decirlo como lo que es —la credencial sirve, la cuota no—, NEVER presentarlo como credencial inválida, y MUST ofrecer esperar al reinicio de cuota o configurar otro proveedor. La capacidad queda sin verificar.
- **FR-008**: El sistema MUST leer y guardar las API keys en **configuración local**. MUST NEVER persistirlas en la base de datos y MUST NEVER exponerlas —ni completas ni parcialmente— en logs, trazas, mensajes de error ni respuestas de la aplicación; el estado consultable de una credencial se limita a "configurada / no configurada / rechazada".
- **FR-009**: El sistema MUST NEVER ofrecer un proveedor cuya verificación empírica de capacidades no esté registrada, y MUST NEVER permitir configurar un endpoint arbitrario en v1.
- **FR-010**: El sistema MUST impedir el acceso al onboarding del CV mientras no exista un proveedor de **generación** configurado con su preflight resuelto (resultado 2 o 3 de FR-007), indicando qué falta. La ausencia de proveedor de **embeddings** verificado NEVER bloquea el onboarding: degrada de forma explícita e informada las funciones que dependen de vectores, que quedan fuera de esta feature.

**Vinculación de correo (paso opcional)**

- **FR-011**: El sistema MUST ofrecer la vinculación de correo como paso **opcional y visiblemente opcional**: omitible con una sola acción, con el mismo peso visual que la de continuar, declarando qué se gana al vincular y qué **no** se pierde al omitirlo. Omitirlo MUST NEVER bloquear el onboarding ni deshabilitar ninguna funcionalidad de esta feature.
- **FR-012**: El sistema MUST divulgar, **antes** de solicitar credencial alguna: (a) que una App Password da acceso a **toda** la bandeja del usuario y que restringir la lectura a la etiqueta designada es un compromiso de Vokara verificado por sus propias pruebas, no un permiso que el proveedor de correo imponga; (b) que las cuentas de Google Workspace y las de Protección Avanzada no admiten App Passwords, con el enlace a la vía alternativa documentada. Ese aviso MUST darse antes de empezar la configuración, NEVER a mitad de ella.
- **FR-013**: El sistema MUST capturar la App Password y la **etiqueta a leer**, MUST verificar que esa etiqueta existe y es alcanzable antes de dar la vinculación por establecida, y MUST tratar la App Password con las mismas reglas que las API keys (FR-008): configuración local, nunca base de datos, nunca logs ni mensajes de error.

**Reanudación de la configuración**

- **FR-014**: El sistema MUST persistir el avance de la primera ejecución paso a paso —acuse de divulgación, proveedores verificados y su resultado de preflight, acuse de degradación si lo hubo, correo vinculado u omitido— de modo que al reabrir la aplicación el usuario retome exactamente en el paso pendiente. MUST NEVER volver a pedir el acuse ni las credenciales ya verificadas, y NEVER exigir reconfigurar desde cero.
- **FR-015**: El sistema MUST dar la primera ejecución por concluida solo cuando los pasos obligatorios (divulgación y proveedor de generación) estén resueltos y el paso de correo esté completado u omitido, y MUST NEVER volver a presentarla en aperturas posteriores.

**Subida del CV maestro**

- **FR-016**: El sistema MUST aceptar la subida de un CV maestro en formato PDF o DOCX con tamaño máximo de 10 MB.
- **FR-017**: El sistema MUST rechazar, antes de procesar, archivos que excedan el límite de tamaño, tengan formato no soportado o estén corruptos, indicando el motivo en español y cómo corregirlo.
- **FR-018**: El sistema MUST conservar el archivo original como respaldo en el directorio de datos local de la instalación, **sin cifrado en reposo** (riesgo divulgado en FR-001), sin tratarlo como fuente de verdad del perfil. Su ciclo de vida —usos autorizados, borrado y exportación— se especifica en la feature 006.
- **FR-019**: El sistema MUST procesar el CV en segundo plano y exponer el estado del procesamiento (en cola, procesando, completado, fallido) al candidato en todo momento.
- **FR-020**: El sistema MUST detectar y rechazar archivos que no sean un CV, con un mensaje claro y sin crear entradas de perfil.
- **FR-021**: El sistema MUST detectar documentos PDF sin capa de texto (escaneados) antes de intentar la extracción, informar al candidato que v1 no procesa documentos escaneados y ofrecerle la captura manual guiada como camino alternativo. El reconocimiento óptico de caracteres (OCR) queda fuera de v1.
- **FR-022**: El sistema MUST ofrecer una captura manual guiada que permita construir un perfil maestro completo sin haber podido sembrarlo desde un archivo; las entradas así creadas se registran con origen `user_added` y siguen el mismo camino de confirmación y versionado que cualquier otro perfil.
- **FR-023**: El sistema MUST permitir al candidato reintentar el procesamiento tras un fallo, sin perder entradas creadas o editadas manualmente.

**Siembra del perfil maestro**

- **FR-024**: El sistema MUST extraer del CV entradas atómicas de los tipos: experiencia, logro, educación, skill, certificación, idioma y proyecto.
- **FR-025**: El sistema MUST asignar a cada entrada un identificador estable y referenciable que no cambie por ediciones posteriores del contenido.
- **FR-026**: El sistema MUST registrar el origen de cada entrada con uno de los valores `cv_seed`, `user_added` o `user_edited`.
- **FR-027**: El sistema MUST conservar el idioma original del contenido de cada entrada, sin traducirlo.
- **FR-028**: El sistema MUST marcar como incompletas las entradas a las que les falten campos clave (p. ej. experiencia sin fechas, educación sin institución) y NEVER inventar o inferir datos ausentes en el documento.
- **FR-029**: El sistema MUST crear el perfil maestro en estado `draft` al sembrarlo, y NEVER habilitar funcionalidades posteriores del producto mientras el perfil no esté `complete`.

**Revisión y enriquecimiento**

- **FR-030**: El candidato MUST poder ver todas las entradas sembradas agrupadas por tipo, con indicación de su origen y de si están incompletas.
- **FR-031**: El candidato MUST poder editar cualquier campo de cualquier entrada; al hacerlo, el sistema MUST cambiar su origen a `user_edited` conservando el identificador.
- **FR-032**: El candidato MUST poder eliminar entradas que no apliquen.
- **FR-033**: El candidato MUST poder crear entradas nuevas de cualquiera de los tipos soportados; el sistema MUST registrarlas con origen `user_added`.
- **FR-034**: El sistema MUST persistir cada cambio de forma que el candidato pueda abandonar y retomar el onboarding sin perder trabajo.

**Cuestionario de objetivos**

- **FR-035**: El sistema MUST capturar, como parte del perfil maestro: puesto objetivo, expectativa salarial (mínimo, máximo y moneda), ubicaciones y preferencia de modalidad remota, industrias de interés y deal-breakers.
- **FR-036**: El sistema MUST validar la coherencia del rango salarial (mínimo ≤ máximo, moneda explícita) y rechazar valores inválidos con explicación en español.
- **FR-037**: El candidato MUST poder modificar sus respuestas del cuestionario en cualquier momento antes de confirmar.

**Confirmación y versionado**

- **FR-038**: El sistema MUST exigir una acción de confirmación explícita del candidato para que el perfil pase a estado `complete`. NEVER debe existir un camino —automático, por reintento, por importación o administrativo— que marque un perfil como `complete` sin esa acción.
- **FR-039**: El sistema MUST impedir la confirmación cuando falten los campos obligatorios del cuestionario o cuando el perfil no tenga al menos una entrada, indicando exactamente qué falta.
- **FR-040**: El sistema MUST crear, en cada confirmación, una versión consultable e inmutable del perfil (entradas y respuestas del cuestionario) con marca de tiempo y origen `confirmation`.
- **FR-041**: El sistema MUST permitir consultar el historial de versiones del perfil y recuperar el contenido íntegro de cualquier versión pasada.
- **FR-042**: El sistema MUST mantener el perfil en estado `complete` cuando el candidato edita entradas o respuestas del cuestionario después de una confirmación. Los cambios quedan como trabajo en curso sobre la última versión confirmada y NEVER degradan el perfil a `draft`.
- **FR-043**: El sistema MUST distinguir el contenido de trabajo en curso de la última versión confirmada, y MUST servir siempre la última versión confirmada a cualquier consumidor del perfil fuera del onboarding. Los cambios sin confirmar NEVER entran en circulación.
- **FR-044**: El sistema MUST indicar al candidato, de forma visible, cuándo tiene cambios sin confirmar y en qué consisten, y MUST permitirle confirmarlos para generar una versión nueva.

**Privacidad y datos**

- **FR-045**: El sistema MUST mantener los datos personales del CV (nombre, contacto, historial) fuera de registros de actividad y trazas de procesamiento.
- **FR-046**: Las trazas de las llamadas al proveedor de IA MUST registrar únicamente metadatos —modelo, versión de prompt, tokens, costo, latencia, éxito o error— y NEVER el contenido del prompt ni de la respuesta. Esas trazas y los logs son locales; enviarlos a un servicio externo MUST requerir opt-in explícito y está desactivado por defecto.
- **FR-047**: Los archivos, perfiles y entradas de candidatos reales NEVER se usan para construir el golden set, correr evals ni ajustar prompts. El golden set se compone exclusivamente de material ajeno al producto (propio del equipo, de voluntarios fuera del producto, o sintético). Con ejecución local esto es además una imposibilidad arquitectónica: el equipo no tiene acceso a los datos de nadie.
- **FR-048**: Habilitar en el futuro el uso de material de usuarios reales con fines de evaluación MUST requerir un ADR propio y un consentimiento opt-in separado, explícito y revocable en cualquier momento, que implique el envío deliberado del material por parte del propio usuario. NEVER puede habilitarse por la vía de modificar el texto de divulgación de la primera ejecución ni apoyándose en el acuse del paso 0.
- **FR-049**: El sistema MUST acotar toda consulta de perfil, entradas, versiones y documentos al `candidate_id` de la instalación, aunque hoy sea un valor único, y MUST NEVER exponer su interfaz fuera de la máquina del usuario: sin autenticación, dónde escucha la instalación es el único control de acceso que existe (ADR-008).

### Trazabilidad — numeración anterior → numeración nueva

Reescritura del 2026-08-10 por el pivote local-first. La numeración anterior a esta reescritura (spec del split de tres, misma fecha) frente a la actual. El mapeo previo al split vive en el historial de git.

| FR anterior | FR nuevo | Nota |
|---|---|---|
| — | FR-001 | **nuevo**: divulgación de primera ejecución (paso 0) |
| FR-030 | FR-002 | **cambia de significado**: de "consentimiento del aviso de privacidad" a "acuse de la divulgación informada"; sigue siendo bloqueante antes de la primera subida |
| — | FR-003 | **nuevo**: sin cuentas, sin autenticación, sin envío de correo; `candidate_id` local fijo |
| — | FR-004 – FR-010 | **nuevos**: proveedores independientes, costo estimado previo, preflight de capacidades con sus cuatro resultados, credenciales fuera de la base de datos, lista cerrada verificada, gate de entrada al onboarding |
| — | FR-011 – FR-013 | **nuevos**: vinculación de correo opcional con divulgación previa y etiqueta designada |
| — | FR-014 – FR-015 | **nuevos**: wizard resumible y conclusión de la primera ejecución |
| FR-001 – FR-002 | FR-016 – FR-017 | sin cambio |
| FR-003 | FR-018 | **cambia de significado**: desaparece el cifrado en reposo (ADR-007); el archivo vive en claro en el directorio de datos local |
| FR-004 – FR-008 | FR-019 – FR-023 | sin cambio |
| FR-009 – FR-014 | FR-024 – FR-029 | sin cambio (siembra) |
| FR-015 – FR-019 | FR-030 – FR-034 | sin cambio (revisión y enriquecimiento) |
| FR-020 – FR-022 | FR-035 – FR-037 | sin cambio (cuestionario) |
| FR-023 – FR-029 | FR-038 – FR-044 | sin cambio (confirmación y versionado) |
| FR-031 | FR-045 | sin cambio (PII fuera de logs) |
| — | FR-046 | **nuevo**: trazas solo con metadatos, sin envío externo por defecto (art. VIII) |
| FR-032 | FR-047 | sin cambio de fondo; se añade que en local es una imposibilidad arquitectónica |
| FR-033 | FR-048 | mismo alcance; se reformula "aviso de privacidad" → "texto de divulgación y acuse del paso 0" |
| FR-034 | FR-049 | **cambia de significado**: de "acceso restringido al candidato propietario" a "toda consulta acotada al `candidate_id` local + la instancia solo escucha en la máquina del usuario" (ADR-008) |

**Ningún FR de la numeración anterior se elimina.** Los FRs que dependían de un servidor —envío de correo y verificación por correo— no existían como requisitos de 001: vivían como supuesto ("el registro y la autenticación ya existen, ADR-001") y como línea de fuera de alcance. Ambos desaparecen, y la prohibición explícita de enviar correo queda ahora escrita como FR-003.

Los criterios de éxito **conservan su numeración** (SC-001 – SC-010) y se añaden SC-011 – SC-016 para la primera ejecución.

### Key Entities *(include if feature involves data)*

- **Estado de la primera ejecución (`setup_state`)**: registro local del avance del wizard. Atributos: acuse de divulgación con marca de tiempo y versión del texto acusado; proveedor de generación y proveedor de embeddings seleccionados; resultado del preflight de cada uno (verificado | degradado con acuse | rechazado | cuota agotada | sin verificar) con su marca de tiempo y, para embeddings, la dimensión del vector; estado del paso de correo (vinculado | omitido | pendiente) y etiqueta designada; paso pendiente. **NEVER contiene credenciales**: las API keys y la App Password viven en configuración local, fuera de la base de datos (FR-008, FR-013).
- **Perfil maestro (`candidate_profile`)**: entidad estructurada 1:1 con el `candidate_id` local de la instalación; fuente única de verdad sobre el candidato. Atributos: estado (`draft` | `complete`), objetivos de búsqueda (puesto, rango salarial y moneda, ubicaciones y modalidad remota, industrias, deal-breakers), fecha de última confirmación, referencia a la versión vigente y señal de si hay cambios sin confirmar. Distingue el contenido de trabajo en curso (lo que el candidato edita) de la versión vigente (lo que el resto del producto consume).
- **Entrada de perfil (`profile_entry`)**: unidad atómica y referenciable del perfil. Atributos: identificador estable, tipo (experiencia | logro | educación | skill | certificación | idioma | proyecto), contenido estructurado, idioma original, origen (`cv_seed` | `user_added` | `user_edited`), señal de completitud, referencia al documento que la sembró (si aplica).
- **Documento de CV maestro (`document`)**: archivo original subido por el candidato. Atributos: formato, tamaño, hash, fecha de subida, `storage_key` en el directorio de datos local (sin cifrado, ADR-007), estado de procesamiento. Puede haber varios a lo largo del tiempo; el más reciente es el vigente. La feature 006 extiende esta entidad con el estado de disponibilidad del binario.
- **Versión del perfil (`profile_version`)**: instantánea inmutable del perfil. Atributos: número o identificador de versión, marca de tiempo, origen, contenido completo de entradas y objetivos en ese momento. En 001 el único origen posible es `confirmation`; la feature 007 añade el origen `cv_merge`. Es la unidad que los materiales generados referenciarán en features posteriores.
- **Trabajo de procesamiento (`parse_job`)**: unidad de trabajo en segundo plano que convierte un documento en entradas sembradas. Atributos: documento asociado, estado, progreso, resultado o motivo de error.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de los perfiles en estado `complete` tiene una confirmación explícita registrada del candidato; ninguna otra vía produce ese estado (verificable por auditoría del historial de versiones).
- **SC-002**: El 100% de las entradas del perfil tiene identificador estable y origen registrado (`cv_seed` | `user_added` | `user_edited`).
- **SC-003**: La tasa de error de extracción sobre el golden set de CVs es menor al 5% de los campos evaluados.
- **SC-004**: El candidato percibe menos de 60 segundos de espera entre la subida del CV y la aparición de las entradas para revisar, en el percentil 95 de los CVs del golden set.
- **SC-005**: Cada confirmación genera exactamente una versión consultable; el historial permite recuperar el contenido íntegro del perfil en cualquier confirmación pasada.
- **SC-006**: El 80% de los candidatos que suben un CV llega a confirmar su perfil en la misma sesión, en menos de 15 minutos desde la subida.
- **SC-007**: Al menos el 60% de los candidatos agrega o edita al menos una entrada durante la revisión (señal de que el gate de enriquecimiento cumple su función y no es un "siguiente, siguiente").
- **SC-008**: El 100% de los archivos que no son CVs, están corruptos, exceden el límite o tienen formato no soportado se rechazan con un mensaje que el candidato puede accionar, sin crear entradas de perfil.
- **SC-009**: El 100% de los PDF escaneados sin capa de texto se detectan antes de la extracción y encaminan al candidato a la captura manual guiada; ninguno produce un perfil sembrado vacío o con contenido basura.
- **SC-010**: Un candidato que no pudo sembrar su perfil desde un archivo puede llegar igualmente a un perfil `complete` mediante la captura manual guiada.
- **SC-011**: El 100% de las instalaciones que llegan a subir un CV tiene registrado el acuse de divulgación con marca de tiempo; ninguna vía —navegación directa, recarga o reinicio— permite subir sin él.
- **SC-012**: El 100% de las credenciales configuradas pasa por el preflight antes de la primera llamada real del producto; ninguna capacidad ausente se descubre durante el uso.
- **SC-013**: 0 apariciones de API keys, App Passwords o fragmentos de ellas en logs, trazas, mensajes de error, respuestas de la aplicación o la base de datos, auditado sobre una ejecución completa que recorra los cuatro resultados de preflight.
- **SC-014**: Al menos el 80% de los participantes de la prueba de instalación asistida completa los pasos obligatorios de la primera ejecución sin intervención del equipo, y la mediana de ese recorrido es menor a 10 minutos.
- **SC-015**: El 100% de las primeras ejecuciones interrumpidas retoma en el paso pendiente al reabrir, sin volver a solicitar el acuse ni las credenciales ya verificadas.
- **SC-016**: El 100% de los preflight con credencial válida pero sin garantía de la capacidad enumera las funciones afectadas antes de permitir continuar; 0 casos de degradación descubierta después de configurar.

## Assumptions

- **Una instalación, un candidato** (ADR-008). No hay usuarios múltiples ni perfiles paralelos; el `candidate_id` local fijo lo asigna la migración inicial y no forma parte del alcance de esta spec decidir su valor.
- El texto de la divulgación (FR-001) se redacta como parte de esta feature: **no hay aviso de privacidad LFPDPPP** ni responsable de datos, porque el proyecto no custodia datos de nadie (ADR-009). Lo que se especifica aquí es su contenido obligatorio, su momento y su carácter bloqueante.
- La **lista cerrada de proveedores** y la **matriz de capacidades** vienen del ADR-011. Que un proveedor esté verificado empíricamente es prerrequisito para ofrecerlo (FR-009); llenar esa tabla es trabajo del ADR-011, no de esta spec.
- El **cálculo** del costo estimado por proveedor se produce fuera de esta spec (roadmap §11.3 y paso 10 de §10). Aquí se especifica que debe mostrarse antes de pedir la llave, desglosado y con el supuesto de uso a la vista.
- El preflight verifica una **capacidad**, nunca un nombre de proveedor: ninguna parte de esta feature ramifica por proveedor concreto (art. XI).
- La **instalación** en sí —`docker compose up`, prerrequisitos, migraciones automáticas al arranque (roadmap §11.1)— queda fuera de esta feature; esta spec arranca con la aplicación ya levantada y accesible.
- El aviso de privacidad y su texto legal ya no existen como entregable externo; lo sustituye la divulgación del art. V.
- La normalización de skills contra la taxonomía propia (ADR-004, F1.2) es una feature aparte. Esta spec captura las skills como entradas del perfil con su texto original.
- Las historias STAR (F3.4) son un tipo de entrada del perfil maestro previsto en el ADR-005, pero se pueblan en la feature de preparación de entrevistas.
- El límite de 10 MB y los formatos PDF/DOCX cubren los CVs del mercado objetivo; otros formatos (imágenes, ODT, texto plano) quedan fuera de v1.
- "Espera percibida < 60 s" se mide desde que el candidato termina la subida hasta que puede empezar a revisar entradas, no desde el inicio de la transferencia del archivo.
- El golden set de CVs (roadmap §6.4) existe o se construye como parte del trabajo de esta feature; es la base de medición de SC-003. Se arma con material ajeno al producto (FR-047).
- Los campos obligatorios del cuestionario para poder confirmar son: puesto objetivo, al menos una ubicación o preferencia de remoto, y expectativa salarial con moneda. Industrias y deal-breakers son opcionales.
- El perfil requiere al menos una entrada para poder confirmarse; no se exige un mínimo por tipo.
- El OCR queda fuera de v1 (FR-021). Si la beta muestra que los CVs escaneados son una porción relevante del mercado objetivo, se reevalúa en v1.x con su propio ADR si introduce una dependencia nueva (art. VII).
- La captura manual guiada (FR-022) reutiliza la misma interfaz de creación de entradas de la User Story 3; no es un flujo paralelo con su propio modelo de datos.
- El trabajo en curso sobre un perfil `complete` no es una versión: solo se materializa como versión al confirmarse (FR-040) o al aplicarse una fusión (feature 007). No se guardan versiones automáticas por cada edición.
- Las métricas de comportamiento (SC-006, SC-007, SC-014) se recogen por **observación directa o reporte voluntario** en la prueba de instalación asistida de la Fase 5, nunca por telemetría (art. V).

## Fuera de alcance

Explícitamente NO forman parte de esta feature:

- **Registro, login, cuentas, sesiones y recuperación de contraseña**: no existen en v1 (ADR-008). No es que se especifiquen en otro lado; no hay tal cosa.
- **Envío de correo de cualquier tipo**, incluida cualquier verificación por correo: no hay servidor que lo envíe (ADR-009).
- **Instalación y arranque del entorno** (roadmap §11.1): `docker compose up`, prerrequisitos, binding a loopback y migraciones automáticas.
- **Pantalla de diagnóstico permanente del sistema** (roadmap §11.4): esta feature cubre la configuración inicial, no el panel de estado continuo.
- **Cambio de proveedor desde Ajustes y re-embebido** de vectores existentes (ADR-011): aquí no hay vectores todavía. Incluye la advertencia previa de invalidación al cambiar el proveedor de embeddings.
- **Costo real acumulado consultable y kill-switch de funciones caras** (roadmap §11.3): esta feature solo muestra el costo **estimado** antes de pedir la llave.
- **Vía OAuth con proyecto propio de Google Cloud** (ADR-012, opción avanzada): aquí solo se enlaza como alternativa documentada.
- **Lectura y parseo de los correos de alerta** (F1.3.2): esta feature vincula la cuenta y designa la etiqueta; leer esa etiqueta e ingerir vacantes es la feature de fuentes.
- **Ciclo de vida del archivo y borrado de datos** (feature 006): borrado manual del archivo, exportación y borrado completo de la instalación.
- **Re-subida y fusión del CV maestro** (feature 007): 001 cubre la primera siembra.
- Motor de matching y score explicable (F1.5), incluido el sub-score semántico que depende de embeddings.
- Ingesta y normalización de vacantes por cualquier canal (F1.3, F1.4).
- Generación de materiales: CV sastre, cartas, mensajes, follow-ups (F2.1–F2.3, F2.5, F2.6) y el verificador de veracidad que los acompaña.
- Tracker de aplicaciones (F2.4) y analítica del embudo (F2.7).
- Alertas y digest (F1.6).
- Normalización de skills contra la taxonomía propia (F1.2, ADR-004).
- Banco de historias STAR y simulador de entrevistas (F3.x).
- Uso de material de candidatos reales para evals, golden set o ajuste de prompts (FR-047). Habilitarlo más adelante exige ADR propio y consentimiento opt-in separado (FR-048), no es un ajuste de alcance de esta feature.
