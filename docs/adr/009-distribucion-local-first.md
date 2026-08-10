# ADR-009 — Distribución local-first open source

**Estado:** Aceptado · **Fecha:** 2026-08 · **Reemplaza a:** ADR-002

---

## Contexto

El ADR-002 desplegaba Vokara como servicio en un VPS Hostinger con Docker
Compose, con ambientes `staging` y `prod`, reverse proxy con TLS y despliegue
por CI vía SSH. Ese modelo convierte al equipo en operador: responsable de
backups, monitoreo, parches, disponibilidad y —lo más pesado— **custodio de los
CVs y datos personales de todos sus usuarios**, con las obligaciones de la
LFPDPPP que eso arrastra.

Para un equipo de 2–3 personas construyendo software comunitario sin modelo de
ingresos, ese rol es el mayor costo fijo del proyecto y el mayor riesgo, y no es
donde está el valor: el valor está en el matching, el verificador de veracidad y
la preparación de entrevistas. Además, el costo variable dominante —las llamadas
al LLM— crece linealmente con los usuarios y no tiene quien lo pague.

## Decisión

Distribuir Vokara como **software open source de ejecución local**. El modelo
completo:

1. **Clonar y ejecutar.** El usuario clona el repositorio y levanta Vokara en su
   máquina con Docker Compose. La instalación es la del ADR-002 menos todo lo
   que servía para operar a terceros.
2. **El usuario aporta su propia API key de LLM.** Configuración local, nunca
   persistida en base de datos ni presente en logs (art. V). El costo variable
   lo controla quien lo genera, y el proyecto no intermedia ni revende consumo.
3. **Sin backend hospedado.** No hay servidor del proyecto, ni cuentas
   (ADR-008), ni datos de usuarios bajo custodia del equipo.
4. **Licencia AGPL-3.0** (ADR-010): quien hospede un Vokara modificado debe
   publicar sus cambios.
5. **Monetización futura por donaciones voluntarias, sin gate de
   funcionalidad.** No habrá edición "pro", ni límites artificiales, ni features
   detrás de pago. Vokara es para gente buscando empleo, es decir, gente que
   puede estar sin ingresos: condicionar funcionalidad al pago excluiría
   exactamente a quien más lo necesita. Las donaciones financian tiempo de
   desarrollo, no acceso.

## Alternativas descartadas

**Mantener el hosting del ADR-002.** Descartado por la combinación de tres
costos que no se pueden pagar a esta escala: custodia de datos personales de
terceros con sus obligaciones legales, operación continua (backups probados,
monitoreo, parches, disponibilidad) y costo de LLM que crece con cada usuario
sin ingreso que lo compense. La ejecución local elimina los tres de una vez: sin
datos de terceros no hay custodia, sin servidor no hay operación, y cada usuario
paga su propio consumo.

**Open core (núcleo abierto, features de pago).** Es el modelo estándar para
financiar open source, y por eso se evaluó. Descartado por el público: un
producto para personas desempleadas cuyas mejores funciones exigen suscripción
resuelve el problema del proyecto creando uno al usuario. Contradice además el
punto 5 de la decisión, que es deliberado y no una consecuencia de no tener
todavía modelo de negocio.

**SaaS hospedado freemium.** Reintroduce todos los costos del ADR-002 y añade el
problema de quién paga las llamadas al LLM del tier gratuito. Inviable sin
financiamiento.

**Distribuir un binario o instalador de escritorio (Tauri, Electron, `pipx`).**
Menor fricción de instalación —criterio explícito del art. VII— y por eso es la
alternativa más seria. Descartada **para v1**, no en general: Vokara necesita
Postgres con pgvector y un worker Celery, así que empaquetarlo significa
resolver la distribución de esos servicios, mantener builds firmados para tres
sistemas operativos y un canal de actualización. Es un proyecto en sí mismo.
Docker Compose ya funciona en las tres plataformas hoy. Si la fricción de
instalación resulta ser el cuello de botella real de adopción, esta decisión se
revisa con un ADR nuevo, con datos en vez de suposiciones.

## Consecuencias

**Positivas**

- El equipo deja de ser operador y custodio: sin obligaciones LFPDPPP como
  responsable de datos, sin guardias, sin backups de terceros.
- La privacidad pasa a ser una propiedad de la arquitectura y no una promesa
  (art. V): los datos están donde el usuario los puso.
- El costo de LLM del proyecto es cero; el del usuario es el que él elija, con
  la capa gratuita de Gemini como default (ADR-003).
- Sin costo marginal por usuario, el proyecto puede crecer sin financiamiento.

**Costos y riesgos**

- **La fricción de instalación se convierte en el principal riesgo de
  adopción.** Quien no logre levantar Docker Compose simplemente no usa Vokara,
  y el público objetivo no es exclusivamente técnico. Por eso el art. VII eleva
  la fricción de instalación a criterio constitucional: cada servicio nuevo en
  el Compose es un usuario menos. Consecuencia operativa concreta: el README
  debe llevar una guía de instalación probada en Windows (WSL2), macOS y Linux,
  y el `docker compose up` debe funcionar sin edición manual más allá de la API
  key.
- **No hay telemetría** (art. V), así que no se sabrá cuánta gente lo instala,
  dónde falla ni qué features usa. Los únicos canales de señal son issues,
  discusiones y reportes voluntarios. Es el precio de la privacidad y hay que
  asumirlo sin buscar atajos: cualquier telemetría exige opt-in explícito y ADR
  propio.
- **Actualizar depende del usuario** (`git pull` + migraciones). Las migraciones
  Alembic deben soportar saltos de varias versiones, porque habrá instalaciones
  meses atrasadas. Una migración que solo funcione desde la versión inmediata
  anterior es un bug.
- Sin backend, no hay features que requieran datos agregados entre usuarios
  (benchmarks de mercado, señales de popularidad de vacantes). Si alguna se
  vuelve central para el producto, este ADR debe reevaluarse.
- Soportar problemas de instalación en máquinas ajenas es un costo de
  mantenimiento nuevo, distinto del de operar un servidor, pero no menor.

## Impacto en artefactos existentes

- **Constitución → v2.0.0 (MAJOR).** Esta decisión es la que motiva la
  enmienda, y este ADR es el que la registra a efectos de la gobernanza, que
  exige "un ADR en `docs/adr/` que registre la decisión y sus alternativas
  descartadas" para modificar la constitución. Cambios derivados: **art. V**
  redefinido ("Privacidad y cumplimiento" → "Privacidad local-first y
  transparencia": sin custodia de datos de terceros, se eliminan el aviso
  LFPDPPP como responsable, el cifrado en reposo obligatorio y la eliminación
  como job verificable; se añaden la divulgación de qué se envía al proveedor de
  LLM, la prohibición de telemetría por defecto y el manejo de API keys);
  **art. VII** modificado (ejecución local en lugar de despliegue en VPS, y la
  fricción de instalación elevada a criterio de alcance); **art. XI** añadido
  (portabilidad de proveedor, consecuencia directa de que la API key la ponga el
  usuario). La v2.1.0 posterior cerró un conflicto derivado en el art. VIII
  (Sentry por defecto contra la prohibición del art. V).
- **ADR-001 y ADR-002 reemplazados.** El pivote deja sin sujeto la
  autenticación (ADR-001 → [ADR-008](008-sin-autenticacion-v1-local.md): sin
  cuentas no hay a quién autenticar) y sin objeto el despliegue hospedado
  (ADR-002 → este ADR). Ambos se conservan marcados Superseded, con su diseño
  intacto como referencia para una eventual versión hospedada.
- **Qué sobrevive del ADR-002:** su Compose, como definición de la ejecución
  local. Lo que queda sin objeto es todo lo relativo a operarlo para terceros:
  staging/prod, despliegue por CI vía SSH, backups centrales, monitoreo y
  umbrales de escalado.
- **`docs/product/roadmap.md`:** §4 (arquitectura), §5 (stack), §7 (seguridad y
  privacidad) y §9 (despliegue y operación) describen un producto hospedado con
  cuentas. Requieren revisión.
- **README:** debe documentar instalación, la divulgación del art. V (qué se
  envía al proveedor de LLM) y la recomendación de cifrado de disco (ADR-007).
