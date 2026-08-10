# ADR-006 — Frontend como SPA con React 18 + TypeScript + Vite

**Estado:** Aceptado · **Fecha:** 2026-08

---

## Contexto

El roadmap (§5, tabla Frontend) fija **React 18 + TypeScript + Vite** como base,
pero no precisa si la aplicación se construye como SPA o sobre un framework con
renderizado en servidor. La diferencia no es de herramienta: cambia dónde vive
la frontera entre cliente y servidor, cómo viaja el token de acceso y cuántos
procesos hay que operar en el VPS.

La aplicación de Vokara —onboarding, matches, kanban, workspace de preparación,
analítica— vive **completa detrás de login**. No hay superficie pública dentro
de la aplicación: nada de lo que renderiza es indexable ni compartible sin
sesión.

## Decisión

Construir la aplicación de Vokara como **SPA (Single Page Application)** con
React 18 + TypeScript + Vite, servida como estáticos desde el mismo reverse
proxy que ya define el ADR-002. **Next.js queda descartado.**

La frontera de servidor es una sola: la API FastAPI. El frontend es un cliente
que consume esa API con el cliente TypeScript generado desde OpenAPI
(constitución art. I).

## Alternativas descartadas

**Next.js.** Descartado por cuatro razones, en orden de peso:

1. **SEO, SSR e ISR no aportan valor aquí.** La aplicación entera está detrás de
   login; el renderizado en servidor resolvería un problema que Vokara no tiene.
2. **El servidor de Next sería redundante y un riesgo arquitectónico.** FastAPI
   ya es la capa de servidor. Un segundo servidor con capacidad de ejecutar
   lógica es exactamente el lugar donde la lógica de negocio empieza a filtrarse
   fuera de `services/`, contra la regla de dependencias unidireccionales de la
   constitución (art. II). No basta con prohibirlo por convención: la forma más
   barata de que no ocurra es que ese servidor no exista.
3. **Incompatible con el modelo de tokens del ADR-001.** El ADR-001 mantiene el
   access token **en memoria del cliente**, nunca en storage persistente. En
   Server Components ese token simplemente no existe: adoptar Next obligaría a
   rediseñar la autenticación completa (dónde vive el access token, cómo se
   refresca desde el servidor, qué pasa con la rotación y la detección de reuso)
   sin ganar nada a cambio.
4. **Costo de recursos en el VPS.** El KVM 2 del ADR-002 ya corre Postgres,
   Redis, la API, los workers y el proyecto ALPHA. Un proceso Node permanente
   más compite por memoria con servicios que sí son necesarios (art. VII).

## Alcance de esta decisión

Esta decisión cubre **la aplicación** (todo lo que vive detrás de login). El
**sitio de marketing público** —landing, precios, blog— será un **deployable
separado** cuando se necesite, con su propio ciclo de vida y su propio dominio o
subdominio. **Astro** es el candidato preferente por experiencia previa del
equipo. Ese sitio sí tiene requisitos de SEO reales, y precisamente por eso no
comparte stack ni proceso con la aplicación. Construirlo no reabre este ADR.

## Consecuencias

**Positivas**

- Una sola frontera de servidor (FastAPI) y una sola capa donde puede vivir
  lógica de negocio: el art. II se sostiene por arquitectura, no por disciplina.
- El modelo de auth del ADR-001 funciona tal como está diseñado, sin
  adaptaciones.
- El build produce estáticos que sirve el proxy ya definido en el ADR-002: cero
  procesos nuevos que operar, monitorear o parchear en el VPS.
- Ciclo de desarrollo rápido (Vite) y despliegue trivial: subir archivos.

**Costos y riesgos**

- **Migrar de Vite a Next más adelante no es trivial:** routing, data fetching y
  auth se rediseñan. Es un costo asumido conscientemente; la probabilidad de
  necesitarlo en una aplicación que vive detrás de login es baja, y el disparador
  sería un cambio de producto (abrir contenido al público sin sesión), no una
  preferencia técnica.
- La carga inicial de una SPA es mayor que la de una página renderizada en
  servidor. Se mitiga con code splitting por ruta; no es crítico en una
  aplicación de sesión larga donde el usuario entra una vez y trabaja dentro.
- Si algún día hace falta contenido público dentro de la aplicación (perfiles
  compartibles, ofertas indexables), este ADR debe reevaluarse con uno nuevo.

## Impacto en artefactos existentes

- **Roadmap §5, tabla Frontend, fila Base:** se anota "SPA; Next.js descartado —
  ver ADR-006".
- **Constitución:** sin cambios. Esta decisión refuerza los artículos II y VII;
  no los modifica.
- **ADR-001:** sin cambios. Este ADR preserva su modelo de tokens; era una de
  las razones del descarte.
- **ADR-002:** sin cambios. El frontend estático ya estaba previsto como
  servido por el reverse proxy.
