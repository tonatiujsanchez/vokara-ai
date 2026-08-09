# Vokara × GitHub Spec Kit — Guía de arranque y prompts

**Objetivo:** iniciar el desarrollo de Vokara con Spec-Driven Development sin desviarse del producto definido en `docs/product/roadmap.md`.

**Regla de oro:** la constitución se escribe UNA vez (proyecto completo). Las specs van POR FEATURE, en rebanadas verticales. Entre cada comando hay revisión humana del artefacto generado — ese es el punto de SDD.

---

## 0. Prerrequisitos e instalación

```bash
# 1. uv (si no está instalado)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Specify CLI (fijar versión: ver github.com/github/spec-kit/releases)
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git

# 3. Verificar herramientas (git, claude, etc.)
specify check

# 4. Crear el proyecto para Claude Code
specify init vokara --integration claude
#    Nota: en versiones previas el flag era --ai claude.
#    Si el comando falla, ejecuta `specify init --help` y usa el flag
#    que muestre tu versión instalada.

cd vokara
git init  # si init no lo hizo
```

**Antes de abrir Claude Code, prepara el contexto del repo:**

```bash
mkdir -p docs/product docs/adr
# Copiar el roadmap al repo — será la fuente de verdad de producto
cp /ruta/a/roadmap_agente_empleo.md docs/product/roadmap.md
git add -A && git commit -m "chore: bootstrap spec-kit + product roadmap"
```

**Crea un `CLAUDE.md` mínimo en la raíz** (el init no siempre lo genera — gap conocido de Spec Kit). No debe duplicar la constitución, solo apuntar a ella:

```markdown
# Claude — reglas de operación en Vokara

1. Lee `.specify/memory/constitution.md` antes de cualquier tarea. Es no negociable.
2. La fuente de verdad de producto es `docs/product/roadmap.md`.
3. Flujo por feature: /speckit.specify → /speckit.clarify → /speckit.plan
   → /speckit.tasks → /speckit.analyze → /speckit.implement.
4. Ante ambigüedad, spec faltante o conflicto con la constitución: DETENTE y pregunta.
5. Código, identificadores y commits en inglés. Specs y docs de producto en español.
```

Abre Claude Code en la raíz del proyecto (`claude`). Si los slash commands `/speckit.*` no aparecen, reinicia la sesión desde la raíz (issue conocido).

---

## 1. `/speckit.constitution` — una sola vez

> Copia y pega esto después del comando:

```text
Crea la constitución de Vokara, un agente de búsqueda de empleo (backend Python,
frontend React). La fuente de verdad de producto es docs/product/roadmap.md —
léela antes de redactar. La constitución debe establecer estos artículos como
principios NO negociables:

1. TIPADO ESTRICTO DE EXTREMO A EXTREMO. mypy --strict bloqueante en CI.
   Pydantic v2 en toda frontera de datos: API, salidas de LLM, workers, adapters.
   El cliente TypeScript del frontend se GENERA desde el esquema OpenAPI del
   backend; está prohibido escribir tipos de API a mano en el front.

2. ARQUITECTURA POR CAPAS CON DEPENDENCIAS UNIDIRECCIONALES.
   api → services → repositories/adapters. Prohibida la lógica de negocio en
   routers y en tareas Celery (las tareas solo orquestan servicios). Todo lo
   externo (LLM, fuentes de vacantes, correo, storage, export de documentos)
   vive detrás de un adapter con interfaz propia e intercambiable.

3. DETERMINISMO PRIMERO. Los pipelines (ingesta, parseo, matching, generación
   de materiales) son flujos deterministas y testeables; el LLM participa solo
   como componente con entrada/salida tipada (structured output). El score de
   matching se calcula con reglas + embeddings y sub-scores explicables — nunca
   lo decide texto libre de un modelo. Único componente conversacional/agéntico
   permitido: el simulador de entrevistas.

4. VERACIDAD NO NEGOCIABLE. Todo material generado (CV sastre, cartas, mensajes)
   pasa por un verificador que compara cada afirmación contra el perfil base del
   candidato. Ninguna afirmación sin sustento llega al usuario. El resultado del
   verificador se persiste junto al material generado.

5. PRIVACIDAD Y CUMPLIMIENTO. Los CVs son datos personales (LFPDPPP México).
   Documentos cifrados en reposo; PII fuera de logs y de trazas de LLM; derecho
   de eliminación real y verificable (borrar cuenta = borrar perfil, documentos,
   embeddings y materiales). Prohibido el scraping de plataformas cuyos ToS lo
   prohíben (LinkedIn, Indeed, OCC, Computrabajo) y el auto-apply headless con
   credenciales de usuarios: solo assisted-apply con acción final humana.

6. CALIDAD VERIFICABLE. Tests antes o junto al código (test-first donde sea
   práctico). pytest para unit/integración (testcontainers para Postgres).
   Todo componente que involucre un LLM requiere evals contra golden set
   corriendo en CI; cambiar un prompt sin correr evals es un bug. Cobertura
   mínima 80% en services/ y domain/.

7. SIMPLICIDAD (YAGNI). Una sola base de datos: Postgres 16 + pgvector para
   todo, incluidos embeddings — sin vector-store aparte. Sin microservicios en
   v1. Sin Kubernetes hasta que el volumen lo justifique. Cada dependencia nueva
   se justifica en el plan.

8. OBSERVABILIDAD. Toda llamada a LLM se traza con costo, latencia y versión de
   prompt (Langfuse). Logs estructurados (structlog). Errores en Sentry.

9. IDIOMA. Producto y UX en español primero. Código, identificadores, commits y
   nombres de ramas en inglés. Specs y documentación de producto en español.

GOBERNANZA: modificar la constitución requiere PR aprobado por los fundadores y
un ADR en docs/adr/ que registre la decisión y sus alternativas descartadas.
```

**Gate de revisión:** lee `.specify/memory/constitution.md` completo. Ajusta a mano lo que no refleje su intención. Commit: `docs: project constitution v1`.

---

## 2. Rebanado de features (mapa de specs)

Una spec por feature, en este orden (cada una es una rama `00X-nombre`):

| # | Feature | Cubre (roadmap) |
|---|---|---|
| 001 | candidate-onboarding | F1.1, F1.2 — CV → perfil verificado + cuestionario |
| 002 | job-ingestion | F1.3 (canales API, email, URL), F1.4 — esquema canónico + dedup |
| 003 | matching-engine | F1.5 — score explicable, sub-scores, brechas |
| 004 | application-materials | F2.1–F2.3 — CV sastre + verificador + ATS check + carta |
| 005 | application-tracker | F2.4 — kanban con máquina de estados y eventos |

Regla: una feature a la vez; se mergea antes de abrir la siguiente. (Con la práctica podrán paralelizar 002 y 005, que no se tocan.)

---

## 3. `/speckit.specify` — Feature 001: candidate-onboarding

> Copia y pega después del comando. Nota que NO menciona stack — eso va en el plan.

```text
Feature: onboarding del candidato — de CV subido a perfil estructurado y
verificado por el usuario.

Contexto de producto: Vokara es un agente de búsqueda de empleo
(docs/product/roadmap.md). Este es el primer eslabón: todo el matching y la
generación de materiales dependerán de la calidad de este perfil.

USER JOURNEY:
1. El candidato crea su cuenta e inicia el onboarding.
2. Sube su CV en PDF o DOCX (límite 10 MB).
3. El sistema extrae un perfil estructurado: datos de contacto, headline,
   resumen profesional, experiencia laboral (empresa, puesto, fechas inicio/fin,
   logros), educación, skills, idiomas con nivel, certificaciones.
4. PASO CRÍTICO — revisión humana: el candidato ve el perfil extraído en una
   interfaz de edición y puede corregir cualquier campo, agregar o eliminar
   entradas. Nada se marca como definitivo sin su confirmación explícita.
5. Completa un cuestionario breve de objetivos: puesto objetivo, expectativa
   salarial (rango y moneda), ubicaciones aceptadas y preferencia de remoto
   (presencial/híbrido/remoto), industrias de interés, deal-breakers.
6. Al confirmar, el perfil queda en estado "completo" y habilita el resto del
   producto (fuera del alcance de esta feature).

CASOS BORDE que la spec debe cubrir:
- PDF escaneado sin capa de texto (¿se soporta OCR en v1 o se informa la
  limitación pidiendo un DOCX? — marcar para clarificación).
- CV con layout de múltiples columnas o tablas.
- CV en inglés (el perfil resultante debe conservar el idioma original de cada
  entrada).
- Archivo que no es un CV (p. ej. una factura): detectarlo y rechazar con
  mensaje claro.
- Campos ausentes (experiencia sin fechas, educación sin institución).
- El usuario vuelve a subir un CV teniendo ya un perfil: comportamiento de
  versionado y qué pasa con las ediciones manuales previas (marcar para
  clarificación).
- Archivo corrupto o que excede el límite de tamaño.

CRITERIOS DE ACEPTACIÓN MEDIBLES:
- El usuario siempre revisa y confirma antes de que el perfil se persista como
  completo; no existe camino que lo omita.
- Tasa de error de extracción < 5% de campos sobre el golden set de CVs de
  prueba.
- El parseo corre en segundo plano con indicador de progreso; percepción de
  espera < 60 segundos para un CV típico.
- Re-subir un CV genera una nueva versión sin pérdida silenciosa de datos.
- Eliminar la cuenta elimina CV, perfil y derivados de forma verificable.

FUERA DE ALCANCE: matching, ingesta de vacantes, generación de materiales,
tracker, notificaciones.
```

**Gate de revisión:** lee `specs/001-candidate-onboarding/spec.md`. Verifica que los criterios sean los tuyos, no inventados. Commit.

---

## 4. `/speckit.clarify` — resolver ambigüedades ANTES del plan

> Ejecútalo siempre después de specify y antes de plan. Puedes orientarlo:

```text
Enfócate en: (1) comportamiento del versionado al re-subir CV y qué pasa con
ediciones manuales previas; (2) política para PDFs escaneados en v1 (OCR sí/no);
(3) campos mínimos obligatorios para considerar un perfil "completo";
(4) flujo exacto de eliminación de datos.
```

Responde con decisiones reales (no "lo que tú creas"). Las respuestas se integran a la spec. Commit.

---

## 5. `/speckit.plan` — aquí SÍ entra el stack

> Copia y pega después del comando:

```text
Genera el plan técnico de la feature 001 usando el stack definido en
docs/product/roadmap.md §5 y respetando la constitución:

BACKEND: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 tipado + Alembic,
Postgres 16 + pgvector, Celery + Redis para el parseo asíncrono del CV.
Extracción de texto: pypdf para PDF con capa de texto, python-docx para DOCX
(OCR según lo decidido en clarify). Parseo a perfil: adapter de LLM con salida
estructurada (LangChain with_structured_output + esquemas Pydantic), proveedor
inicial OpenAI detrás de la interfaz adapters/llm — intercambiable. Storage de
archivos S3-compatible con cifrado en reposo. Auth: [Clerk | JWT propio — según
ADR-001].

FRONTEND: React 18 + TypeScript + Vite, TanStack Query, react-hook-form + zod,
Tailwind + shadcn/ui. Cliente API generado con openapi-typescript a partir del
OpenAPI del backend (script en el build; prohibido tipear a mano).

ESTRUCTURA: monorepo del roadmap §5.1 —
backend/app/{api,domain,services,adapters,db,workers,core}, frontend/src/{api,
features,components}, infra/, docs/.

TESTING: pytest + testcontainers (Postgres real); evals de extracción contra el
golden set en backend/tests/evals (bloqueantes en CI); Vitest + React Testing
Library en front. CI en GitHub Actions: ruff + mypy --strict + tests + evals,
todo bloqueante.

INFRA DEV: Docker multi-stage + docker-compose (api, worker, postgres, redis).
Despliegue objetivo: [Railway/Fly — según ADR-002], staging con auto-deploy
desde main.
```

**Gate de revisión:** lee `plan.md`, `data-model.md`, `contracts/` y `research.md` generados. Es el momento de corregir sobre-ingeniería (la constitución art. 7 es tu argumento). Commit.

---

## 6. `/speckit.tasks` → `/speckit.analyze` → `/speckit.implement`

```text
/speckit.tasks
Genera las tareas siguiendo test-first. Marca como [P] las paralelizables.
Cada tarea debe dejar el proyecto en estado verde (tests pasando).
```

Revisa `tasks.md`: ¿el orden respeta dependencias?, ¿hay tareas gigantes que partir? Commit.

```text
/speckit.analyze
```

Corrige toda inconsistencia que reporte entre constitución ↔ spec ↔ plan ↔ tasks ANTES de implementar. Es la red de seguridad barata.

```text
/speckit.implement
```

Durante la implementación: supervisa, corre los tests localmente por bloque de tareas, commit por tarea o grupo lógico (no un mega-commit al final), y si Claude Code se topa con una ambigüedad debe detenerse y preguntar (está en CLAUDE.md).

---

## 7. Semillas para las specs 002–005

Cuando toque cada una, `/speckit.specify` con estas bases (expándelas con journey + casos borde + criterios como en 001):

**002-job-ingestion** — Ingesta multi-canal de vacantes: (a) API de agregador
(Adzuna/Jooble/JSearch) con búsquedas derivadas del perfil; (b) buzón de correo
al que el candidato reenvía sus alertas de LinkedIn/OCC/Computrabajo/Indeed y
Vokara parsea las vacantes del cuerpo del correo; (c) URL pegada manualmente.
Toda vacante se normaliza al esquema canónico JobPosting y se deduplica
(empresa + título normalizado + similitud de descripción). Fuera de alcance:
matching, career pages, alertas salientes.

**003-matching-engine** — Score explicable perfil↔vacante: parseo cacheado de
la JD a requisitos estructurados; sub-scores deterministas (cobertura de
must-haves con normalización de skills, seniority, salario, ubicación) +
sub-score semántico por embeddings; score final ponderado con pesos en config;
brechas por vacante; explicación de 2 líneas generada SOLO desde sub-scores.
Criterio: precisión@10 ≥ objetivo sobre el golden set etiquetado.

**004-application-materials** — Para una vacante elegida: CV sastre (reordena y
reformula sin inventar), verificador de veracidad bloqueante (constitución
art. 4), chequeo ATS (re-parseo del DOCX generado + keywords de la JD
presentes/ausentes), carta de presentación. Export DOCX y PDF versionados.

**005-application-tracker** — Kanban con máquina de estados: DESCUBIERTA →
GUARDADA → MATERIALES_LISTOS → APLICADA → SCREENING → ENTREVISTA(n) → OFERTA →
NEGOCIACIÓN → ACEPTADA/RECHAZADA/SIN_RESPUESTA/RETIRADA. Toda transición
registra evento con timestamp (base de la analítica de embudo F2.7, fuera de
alcance aquí). Estados y transiciones válidas como enum tipado en domain/.

---

## 8. Checklist de decisiones previas (confirmar antes del plan de 001)

- [ ] ADR-001 Auth: Clerk (default propuesto) vs JWT propio.
- [ ] ADR-002 Hosting: Railway (default propuesto) vs Fly vs K8s existente.
- [ ] ADR-003 Proveedor LLM inicial: OpenAI detrás del adapter (default).
- [ ] ADR-004 Taxonomía de skills: lista propia curada v1 (default), ESCO después.
- [ ] Golden set en construcción: 10 CVs anonimizados + 20 JDs (no bloquea 001,
      bloquea sus evals).
- [ ] Aviso de privacidad en redacción (bloquea beta, no el desarrollo).

Cada decisión → un archivo en `docs/adr/` (contexto, decisión, alternativas
descartadas, consecuencias).
