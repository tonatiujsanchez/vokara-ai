# ADR-012 — Vinculación opcional de correo: App Password + IMAP en v1

**Estado:** Aceptado · **Fecha:** 2026-08

---

## Contexto

Una de las fuentes legítimas de vacantes del roadmap son los **correos de
alertas** que el candidato ya recibe (LinkedIn Jobs, OCC, Computrabajo,
newsletters de empleo). Leerlos es la vía que permite descubrir vacantes sin
scrapear plataformas cuyos ToS lo prohíben (art. V). El correo sirve además al
pilar de conversión: detectar respuestas de reclutadores para alimentar el
kanban de aplicaciones.

El ADR-001 preveía un adapter de correo, pero para **enviar** (verificación de
cuenta, reset de contraseña). Con el ADR-008 ese uso desaparece. Lo que queda es
el inverso: **leer** la bandeja del usuario, en su máquina, con sus
credenciales.

En ejecución local el problema cambia de forma. No hay servidor con dominio
verificado ni pantalla de consentimiento de Google aprobada: hay un programa
corriendo en la computadora de alguien que necesita acceso a su propio correo.

## Decisión

La vinculación de correo es **opcional**: Vokara funciona completo sin ella
—perfil, matching por URL manual, materiales, preparación— y quien no la
configure no ve funcionalidad bloqueada, solo menos fuentes automáticas.

**Un `EmailPort` abstrae el acceso a la bandeja** (constitución art. II), con
dos implementaciones:

**1. Gmail App Password + IMAP — el camino de v1.** Tres pasos para el usuario:
activar la verificación en dos pasos, generar una App Password en su cuenta de
Google, y pegarla en la configuración local de Vokara. Se lee de configuración
local y nunca se persiste en la base de datos ni aparece en logs (art. V, misma
regla que las API keys).

**2. OAuth con proyecto propio de Google Cloud — opción avanzada documentada.**
El usuario crea su propio proyecto en Google Cloud, habilita la Gmail API,
genera credenciales OAuth y las configura. Es la vía correcta técnicamente y la
única para cuentas que no admiten App Passwords, pero son del orden de diez
pasos en una consola pensada para desarrolladores. Se documenta, no se pone en
el camino principal.

**Vokara lee únicamente la etiqueta que el usuario designe.** No la bandeja
completa. El usuario crea un filtro en Gmail que etiquete sus alertas de empleo,
indica esa etiqueta en la configuración, y Vokara restringe cada consulta IMAP a
ella.

## Limitación registrada

**Desde marzo de 2025, las cuentas de Google Workspace exigen OAuth y no aceptan
App Passwords.** Las cuentas con **Protección Avanzada** también las tienen
deshabilitadas. Para esos usuarios, el camino de v1 no funciona y la única vía
es la opción 2.

**La cobertura se considera aceptable** porque el público objetivo —profesionistas
en México buscando empleo— usa mayoritariamente Gmail personal para su búsqueda,
no la cuenta corporativa de su empleador actual. Buscar empleo desde el correo de
la empresa en la que uno trabaja es, además, algo que no conviene hacer. La
limitación se documenta en el README junto al enlace a la opción OAuth; no se
descubre a mitad de la configuración.

## Alternativas descartadas

**OAuth como camino principal en v1.** Es lo correcto en un producto hospedado,
donde el proyecto registra la aplicación una vez y todos los usuarios ven una
pantalla de consentimiento. En local eso no aplica: sin servidor con dominio
verificado, cada usuario tendría que crear su propio proyecto de Google Cloud
antes de poder leer su correo. Diez pasos en una consola de desarrollador contra
tres en la configuración de su cuenta. Contra el criterio de fricción de
instalación del art. VII. Se conserva como opción avanzada, no como default.

**Distribuir credenciales OAuth del proyecto en el repositorio.** Eliminaría la
fricción, pero un `client_secret` en un repo público no es secreto, viola los
términos de Google y expone el proyecto a revocación. Descartado sin más.

**Reenvío manual a una dirección de Vokara.** No hay dirección de Vokara: no hay
backend (ADR-009).

**Leer la bandeja completa.** Técnicamente más simple —sin filtro que configurar,
sin etiqueta que explicar— y descartado precisamente por eso: convertiría un
acceso acotado en acceso total sin que el usuario lo note.

**No integrar correo en v1.** Deja fuera la fuente de vacantes más rica que es
compatible con la prohibición de scraping. Se descarta mantener el vacío, pero la
integración se mantiene opcional.

## Consecuencias

**Positivas**

- Vokara accede a la fuente de vacantes más rica disponible sin violar ToS de
  ninguna plataforma (art. V).
- Tres pasos de configuración para la mayoría del público objetivo.
- El `EmailPort` permite añadir Outlook/IMAP genérico después sin tocar
  servicios, y hace que la elección App Password vs. OAuth sea invisible para
  el resto del código.
- Como es opcional, su ausencia degrada el producto de forma explícita e
  informada, nunca en silencio (art. XI, mismo principio).

**Costos y riesgos**

- **Riesgo central: una App Password da acceso a TODA la bandeja del usuario,
  no solo a la etiqueta.** La restricción por etiqueta es una disciplina de
  Vokara, no un permiso que Google imponga: nada impide técnicamente leer el
  resto. Por eso hay dos obligaciones no negociables. Primera, **decírselo al
  usuario explícitamente** en el momento de configurarlo —qué permiso está
  otorgando de verdad y qué se compromete Vokara a leer—, no enterrado en
  documentación. Segunda, **que el código lo cumpla de forma verificable**: el
  filtro por etiqueta vive en el adapter, y sus tests son tests de
  cumplimiento, no de funcionalidad. Un cambio que amplíe el alcance de lectura
  es un incidente de privacidad, no una feature.
- La App Password es una credencial de larga vida en la configuración local del
  usuario. Se documenta cómo revocarla desde la cuenta de Google, y que revocarla
  es la forma de desvincular.
- Los usuarios de Workspace y de Protección Avanzada quedan fuera del camino
  simple (ver limitación registrada).
- Google podría restringir las App Passwords también en cuentas personales. Si
  ocurre, OAuth pasa a ser el único camino y esta decisión se reevalúa; el
  `EmailPort` acota el impacto a una implementación.
- El parseo de correos de alerta es frágil por naturaleza: cada plataforma
  cambia su plantilla sin avisar. Debe fallar de forma visible y no corromper
  datos del perfil.
