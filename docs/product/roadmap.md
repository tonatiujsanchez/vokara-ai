# Roadmap — Vokara · Your AI Job Scout

> **Vokara** (*vocation* + *radar*) — Encuentra oportunidades que realmente encajan contigo.

**Versión:** 0.3 · **Fecha:** Julio 2026 · **Estado:** Alineado con constitución v1.1.0 y ADR-001..005

---

## 1. Visión y definición del producto

### 1.1 Propósito

> Buscar vacantes "ideales" (con mayor probabilidad de que el candidato cubra el puesto), conseguir la mayor cantidad de entrevistas, preparar al candidato para las entrevistas y posicionarlo para obtener el puesto.

Este propósito se descompone en **4 pilares funcionales** que estructuran todo el proyecto:

| Pilar | Objetivo medible |
|---|---|
| P1 — Descubrimiento | Encontrar y rankear vacantes donde el candidato tiene alta probabilidad real de encajar |
| P2 — Conversión a entrevistas | Maximizar la tasa aplicación → entrevista |
| P3 — Preparación | Que el candidato llegue a cada entrevista con investigación, práctica y respuestas listas |
| P4 — Cierre | Maximizar la tasa entrevista → oferta y el resultado de la negociación |

### 1.2 Usuarios objetivo (v1)

- **Primario:** profesionistas en México buscando empleo activamente (tech, administrativo, ventas, marketing). Español como idioma principal, inglés como secundario.
- **Secundario (fase posterior):** recién egresados; personas cambiando de carrera.
- **No objetivo en v1:** reclutadores/empresas (eso sería otro producto), mercados fuera de LATAM/US-remote.

### 1.3 Métricas de éxito

- **North Star:** entrevistas agendadas por candidato activo por mes.
- **Métricas por pilar:**
  - P1: % de matches marcados como "relevantes" por el usuario (precisión percibida ≥ 70%).
  - P2: tasa aplicación → respuesta positiva; tiempo CV subido → primera aplicación enviada (< 24 h).
  - P3: % de entrevistas con preparación completada; score del simulador antes vs. después.
  - P4: tasa entrevista → oferta; % de ofertas negociadas al alza.
- **Métricas guardián (calidad/ética):** 0 afirmaciones inventadas en CVs generados (validadas por el verificador de veracidad, sección 4.6); tasa de error de parseo de CV < 5%.

### 1.4 Anti-alcance (qué NO es Vokara)

Definir esto desde el día 1 evita meses perdidos:

1. **No hace auto-apply masivo sin supervisión.** Enviar aplicaciones headless con credenciales del usuario viola los ToS de LinkedIn, OCC, Indeed y Computrabajo, y provoca baneos de cuenta. Vokara prepara todo y el humano da el clic final (modelo "assisted apply", igual que Teal, Simplify o Huntr — los productos reales del mercado).
2. **No inventa experiencia ni habilidades.** Reorganiza, reformula y prioriza lo que el candidato realmente tiene. Hay un verificador automático que bloquea afirmaciones sin sustento.
3. **No promete empleo.** Es un multiplicador de esfuerzo, no una garantía.
4. **No scrapea plataformas que lo prohíben** (LinkedIn search, Indeed search). La estrategia de fuentes (sección 2, F1.3) se diseña alrededor de canales legítimos.

---

## 2. Especificación funcional por pilar

Prioridad MoSCoW: **[M]** must-have v1 · **[S]** should-have v1 · **[C]** could-have (v1.x) · **[W]** won't-have por ahora.

### Pilar 1 — Descubrimiento de vacantes ideales

- **F1.1 [M] Ingesta de CV maestro** — Upload PDF/DOCX → parseo con extracción LLM + salida tipada (Pydantic) que **siembra el perfil maestro**: entradas atómicas referenciables (experiencia, logros, skills, educación, idiomas — ver ADR-005). El usuario **revisa, corrige y enriquece** el perfil sembrado en UI y lo **confirma** antes de continuar (human-in-the-loop: el parseo nunca es perfecto y este gate define la calidad de todo lo demás). El archivo original se conserva como respaldo, no como fuente de verdad.
- **F1.2 [M] Perfil enriquecido** — Cuestionario corto: objetivo de puesto, salario esperado, ubicación/remoto, industrias, deal-breakers. Normalización de skills contra una **lista propia curada de 200–300 skills** del mercado objetivo, con alias en español e inglés y fallback por similitud de embeddings cuando no hay coincidencia exacta (ADR-004), para que "React.js", "ReactJS" y "React" sean la misma skill — y para que "React Native" no lo sea. ESCO queda como posible importación futura (el esquema `skill_id` + alias es compatible), no como alternativa abierta en v1.
- **F1.3 [M] Fuentes de vacantes (estrategia multi-canal):**
  1. **APIs de agregadores** (legítimas, con datos de México): Adzuna, Jooble, JSearch (RapidAPI, indexa Google for Jobs). Costo bajo, cobertura amplia.
  2. **Correos de alertas reenviados** — el candidato configura alertas en LinkedIn/OCC/Computrabajo/Indeed y las reenvía (o auto-reenvía) a su dirección Vokara; el sistema parsea las vacantes del correo. **Ventaja del equipo: ya dominan parseo de correos y adjuntos por el proyecto ALPHA.** Canal 100% dentro de los ToS.
  3. **Career pages directas** — scraping respetuoso (robots.txt) de páginas de carreras de empresas objetivo; los boards de Greenhouse/Lever/Workable exponen JSON público por empresa.
  4. **URL manual** — el usuario pega cualquier URL de vacante y Vokara la analiza al momento.
- **F1.4 [M] Normalización y deduplicación** — Toda vacante, venga de donde venga, se convierte a un esquema canónico `JobPosting`; dedup por hash de (empresa + título normalizado + similitud de descripción) para no mostrar la misma vacante 4 veces.
- **F1.5 [M] Motor de matching con score explicable** — Detalle en sección 4.5. Cada match muestra: score global, sub-scores (cobertura de requisitos obligatorios, semántica, seniority, salario, ubicación), brechas ("te faltan X, Y") y un "por qué encajas" de 2 líneas generado desde los sub-scores (no texto libre inventado).
- **F1.6 [S] Alertas y digest** — Correo/notificación diaria o semanal con los nuevos matches sobre umbral de score.
- **F1.7 [C] Feedback loop de matching** — Thumbs up/down por vacante ajusta pesos del ranking por usuario.

### Pilar 2 — Maximizar entrevistas

- **F2.1 [M] CV sastre por vacante** — **Selecciona y reformula** el subconjunto más relevante de entradas del perfil maestro para la vacante (ADR-005): reordena, ajusta el resumen profesional, incorpora keywords de la JD **que el candidato realmente posee**; cada afirmación referencia su entrada de origen (`source_id`). Exporta DOCX y PDF.
- **F2.2 [M] Verificación ATS** — El DOCX generado se re-parsea con el mismo parser de F1.1; si se pierden campos (tablas raras, columnas), se alerta. Chequeo de keywords de la JD presentes/ausentes.
- **F2.3 [M] Carta de presentación por vacante** — Personalizada con empresa + rol + 2-3 puntos de match concretos.
- **F2.4 [M] Tracker de aplicaciones (kanban)** — Máquina de estados: `DESCUBIERTA → GUARDADA → MATERIALES_LISTOS → APLICADA → SCREENING → ENTREVISTA(n) → OFERTA → NEGOCIACIÓN → ACEPTADA / RECHAZADA / SIN_RESPUESTA / RETIRADA`. Cada transición se registra con timestamp (alimenta las métricas del embudo personal).
- **F2.5 [S] Follow-ups automáticos sugeridos** — Si una aplicación lleva N días sin respuesta, Vokara redacta el follow-up y lo deja listo para enviar (o lo envía si el usuario activó ese permiso para su propio correo).
- **F2.6 [S] Mensajes a reclutadores** — Plantillas personalizadas para contacto en frío (LinkedIn/correo) con el ángulo de match específico. El envío es manual (copiar/pegar o mailto), no automatizado.
- **F2.7 [S] Analítica del embudo personal** — "Aplicaste a 40, respondieron 6, entrevistas 3": dónde se cae el candidato y sugerencias (¿CV?, ¿tipo de vacante?, ¿seniority mal calibrado?).
- **F2.8 [C] Extensión de navegador para assisted-apply** — Autollenado de formularios de aplicación con los datos del perfil (así lo resuelven Simplify/Teal). Es la forma correcta y segura de acelerar el apply sin violar ToS. Proyecto propio; va en v1.x.

### Pilar 3 — Preparación de entrevistas

- **F3.1 [M] Dossier de empresa** — Scraping del sitio + noticias recientes + resumen: qué hace, productos, tamaño, cultura declarada, preguntas inteligentes para hacer al entrevistador.
- **F3.2 [M] Banco de preguntas predichas** — A partir de la JD + tipo de rol + seniority: preguntas probables (conductuales + técnicas) con guía de respuesta.
- **F3.3 [M] Simulador de entrevista (chat)** — Conversación multi-turno donde Vokara entrevista al candidato para una vacante específica, luego entrega feedback con rúbrica: estructura STAR, especificidad, relevancia, señales de alerta. Es el único componente genuinamente conversacional/agéntico del sistema (sección 4.4).
- **F3.4 [S] Banco de historias STAR** — Vokara ayuda al candidato a convertir su experiencia en 6-10 historias STAR reutilizables, etiquetadas por competencia (liderazgo, conflicto, resultados...). El simulador las referencia.
- **F3.5 [C] Simulador por voz** — El equipo ya tiene experiencia con Vosk (transcripción español local); práctica hablada con feedback de muletillas y ritmo. Diferenciador fuerte para v1.x.
- **F3.6 [C] Plan de preparación técnica** — Para roles tech: temas a repasar según la JD, con recursos.

### Pilar 4 — Posicionamiento y cierre

- **F4.1 [M] Notas de agradecimiento post-entrevista** — Generadas con detalles de la entrevista (el usuario cuenta cómo le fue; Vokara lo captura al tracker y redacta).
- **F4.2 [S] Módulo de negociación** — Rango salarial de mercado (mejor esfuerzo con datos de las propias vacantes ingestadas + reportes públicos; los datos salariales en México son escasos y hay que ser honestos con el usuario sobre el margen de error), scripts de negociación, simulador de la conversación de oferta.
- **F4.3 [S] Comparador de ofertas** — Tabla normalizada: salario, prestaciones, remoto, crecimiento; ponderada por las prioridades del candidato.
- **F4.4 [C] Aprendizaje de rechazos** — Registrar motivo de rechazo cuando exista y ajustar matching/preparación.

---

## 3. Restricciones, riesgos y decisiones de producto

| Riesgo | Impacto | Mitigación |
|---|---|---|
| ToS de bolsas de trabajo (scraping/auto-apply) | Legal + baneo de cuentas de usuarios | Estrategia de fuentes legítimas (F1.3); assisted-apply, nunca headless; revisión legal en Fase 0 |
| Datos personales sensibles (CVs) | LFPDPPP (México) / GDPR si hay usuarios UE | Aviso de privacidad, cifrado en reposo, derecho de eliminación real (borrar = borrar), retención definida, PII fuera de logs |
| El LLM "mejora" el CV inventando | Daño reputacional grave al usuario y al producto | Verificador de veracidad obligatorio en el pipeline de generación (4.6) |
| Calidad del parseo de CV variable | Todo el matching se degrada | Human-in-the-loop de corrección (F1.1) + suite de evals con golden set propio (§6.4) |
| Costo LLM por usuario | Unit economics | Cachear parseos de JD (una vacante se parsea una vez para todos), embeddings baratos, modelos pequeños para clasificación, modelo grande solo en generación de materiales |
| Cobertura de vacantes insuficiente en México | Producto se siente vacío | Canal de correos de alertas (F1.3.2) garantiza cobertura de LinkedIn/OCC/Computrabajo sin scrapearlos |

---

## 4. Arquitectura

### 4.1 Principio rector: pipelines deterministas + una capa conversacional

La lección de ALPHA aplica aquí: **no todo debe ser "agéntico"**. 

- **Pipelines** (ingesta, parseo, matching, generación de materiales): flujos deterministas y testeables donde el LLM es un componente con entrada/salida tipada (structured output), no un agente que decide. Predecible, barato, debuggeable.
- **Agente conversacional** (**únicamente** el simulador de entrevistas — es el solo componente conversacional/agéntico permitido por la constitución, art. III): aquí sí hay estado, turnos y decisiones del modelo → LangGraph con checkpointer.

### 4.2 Diagrama lógico

```
┌─────────────────────────────────────────────────────────────┐
│                     FRONTEND (React + TS)                    │
│  Onboarding · Matches · Kanban · Prep Workspace · Analytics │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST (OpenAPI) + SSE para el simulador
┌──────────────────────────▼──────────────────────────────────┐
│                    API (FastAPI + Pydantic v2)               │
│   routers → services (dominio) → repositories (DB)          │
└───────┬───────────────────────────────┬─────────────────────┘
        │                               │
┌───────▼────────┐              ┌───────▼─────────────────────┐
│  Postgres 16   │              │   Workers (Celery + Redis)   │
│  + pgvector    │              │  · ingesta de fuentes (cron) │
│  (perfiles,    │              │  · parseo CV/JD (LLM)        │
│   vacantes,    │              │  · matching batch            │
│   embeddings,  │              │  · generación de materiales  │
│   tracker)     │              │  · digest de alertas         │
└────────────────┘              └───────┬─────────────────────┘
                                        │
                        ┌───────────────▼───────────────┐
                        │       ADAPTERS (puertos)       │
                        │ · LLM provider (intercambiable)│
                        │ · Fuentes: Adzuna/Jooble/JSearch│
                        │ · Email inbound (alertas)      │
                        │ · Storage (S3-compatible)      │
                        │ · Export DOCX/PDF              │
                        └────────────────────────────────┘
```

### 4.3 Modelo de datos (entidades núcleo)

- `users` — auth, plan.
- `candidate_profiles` — 1:1 con user; perfil maestro versionado (ADR-005); headline, años de experiencia, skills normalizadas, idiomas, expectativa salarial, preferencias (remoto, ubicaciones, industrias), embedding del perfil.
- `profile_entries` — entradas atómicas referenciables del perfil maestro (experiencia, logro, educación, skill, certificación, idioma, proyecto, historia STAR), cada una con `id` propio; sustentan la trazabilidad por `source_id` de los materiales generados.
- `documents` — CVs originales y versiones generadas (tipo, storage_url, hash) y **estado de disponibilidad del binario** (`disponible` | `eliminado_por_candidato` | `purgado_por_retencion`, con fecha y causa). Un documento sin binario conserva su registro y las referencias de las entradas que sembró, pero ya no admite reprocesamiento ni fusión (§7).
- `job_sources` — configuración por canal (api | email_alert | career_page | manual).
- `companies` — nombre, dominio, dossier (jsonb), last_researched_at.
- `job_postings` — esquema canónico: título, company_id, descripción cruda, requisitos estructurados (jsonb, cacheado del parseo LLM), salario min/max, ubicación, tipo remoto, seniority, fuente, URL externa, dedup_hash, embedding (pgvector).
- `matches` — profile_id, job_id, score, sub-scores (jsonb), brechas (jsonb), feedback del usuario.
- `applications` — job_id, estado (enum de la máquina de estados F2.4), canal, fechas, next_action_at.
- `application_events` — timeline auditable de cada transición.
- `generated_assets` — tipo (cv_tailored | cover_letter | followup | thankyou | recruiter_msg), contenido, metadatos del modelo, resultado del verificador de veracidad, referencias `source_id` por afirmación y versión del perfil maestro usada (ADR-005).
- `interview_sessions` — application_id, tipo (mock | prep), transcript, scores de rúbrica, feedback.
- `story_bank` — historias STAR del candidato etiquetadas por competencia.

### 4.4 Dónde entra LangChain/LangGraph (y dónde no)

| Componente | Herramienta | Justificación |
|---|---|---|
| Parseo CV → perfil | `with_structured_output` + Pydantic | Esquema garantizado, reintentos ante formato inválido |
| Parseo JD → requisitos | `with_structured_output` + Pydantic | Ídem; se cachea por vacante |
| Explicación de match | Prompt simple con sub-scores como input | Grounded: el LLM redacta, no calcula |
| Generación CV/carta | Cadena corta: generar → verificar veracidad → export | Pipeline, no agente |
| Simulador de entrevista | **LangGraph** con checkpointer (estado en Postgres) | Multi-turno real, estado de rúbrica, ramas según respuestas |
| Ingesta/scraping/dedup/export | **Python puro** | No hay LLM involucrado; no forzar el framework |

### 4.5 Motor de matching v1 (concreto)

1. **Parseo de JD** (una vez por vacante, cacheado): extraer must-have skills, nice-to-have, años requeridos, seniority, rango salarial, modalidad.
2. **Sub-scores por reglas** (deterministas, testeables):
   - `cobertura_must = |skills_candidato ∩ must_haves| / |must_haves|` (con normalización de taxonomía + similitud de embeddings para matches difusos: "Postgres" ≈ "PostgreSQL").
   - `fit_seniority`, `fit_salario` (solapamiento de rangos), `fit_ubicacion`.
3. **Sub-score semántico:** similitud coseno entre embedding del perfil y de la JD (pgvector).
4. **Score final:** suma ponderada (pesos en config, ajustables); se guardan todos los sub-scores → **explicabilidad gratis**.
5. **Capa de lenguaje:** el LLM redacta "por qué encajas / qué te falta" **solo** a partir de sub-scores y brechas calculadas — nunca inventa el análisis.

Ventaja de este diseño: el ranking es barato (embeddings + reglas), auditable, y el LLM caro solo toca la capa de presentación y el parseo cacheado.

### 4.6 Guardrail de veracidad (no negociable)

Después de generar cualquier material (CV sastre, carta, mensaje, follow-up, nota), un paso verificador exige que **cada afirmación referencie el `profile_entry` del perfil maestro que la sustenta** (`source_id`). No es un juicio semántico de un modelo: es una comprobación de trazabilidad determinista — el `source_id` existe y es válido, o no existe. Barata, testeable con unit tests y alineada al principio de determinismo (§4.1, constitución art. III).

Una afirmación sin `source_id` válido **no llega al usuario**: se bloquea y se regenera con la restricción, o se marca para revisión humana. **Reformular una entrada es válido; exagerarla no** — "participé en" no puede convertirse en "lideré" aunque el `source_id` sea correcto (ver §6.4).

Este check es parte del pipeline, no opcional. En `generated_assets` se persisten el resultado del verificador, las referencias `source_id` por afirmación y la **versión del perfil maestro** con la que se produjo el material, para auditoría y regeneración. Detalle y alternativas descartadas en **ADR-005**.

---

## 5. Stack tecnológico

### Backend
| Capa | Elección | Nota |
|---|---|---|
| Lenguaje | Python 3.12 | |
| Framework | FastAPI | OpenAPI gratis → tipos compartidos con el front |
| Tipado | mypy `--strict` + Pydantic v2 en todas las fronteras | Requisito del proyecto |
| ORM/DB | SQLAlchemy 2.0 (typed) + Alembic · Postgres 16 + pgvector | Una sola DB para todo, incluidos embeddings; no meter un vector-store aparte en v1 |
| Colas | Celery + Redis | El equipo ya lo domina (ALPHA) |
| LLM | Adapter propio sobre LangChain (structured output) + LangGraph solo simulador; proveedor inicial **Google Gemini** vía `langchain-google-genai` (ADR-003) | Proveedor intercambiable desde el día 1. El adapter cubre también los **embeddings**; cada vector persiste `embedding_model` y `embedding_dim` para permitir migración de proveedor sin pérdida de datos |
| Documentos | python-docx, WeasyPrint o docx→pdf (ya resuelto en ALPHA) | Reuso directo |
| Email inbound | Parser de correos de alertas | Reuso del know-how de ALPHA |
| Calidad | ruff (lint+format), pre-commit, pytest + coverage | |

### Frontend
| Capa | Elección | Nota |
|---|---|---|
| Base | React 18 + TypeScript + Vite | |
| Server state | TanStack Query | |
| Cliente API | Generado desde OpenAPI (`openapi-typescript` u orval) | El tipado back↔front nunca se desincroniza |
| Formularios | react-hook-form + zod | |
| UI | Tailwind + shadcn/ui | Rápido y consistente |
| Testing | Vitest + React Testing Library + Playwright (e2e) | |

### Infra
Docker multi-stage · **Docker Compose sobre el VPS Hostinger existente** para dev, staging y prod, separados por proyecto Compose y base de datos distintas (ADR-002); reverse proxy con TLS automático (Caddy o nginx) sirviendo también el frontend estático · **Sin Kubernetes en v1** — sobredimensionado para la escala esperada; se reevalúa contra el umbral documentado en ADR-002 · GitHub Actions (CI/CD, deploy por SSH) · Sentry (errores) · Langfuse o LangSmith (trazas y costos LLM) · Logs estructurados (structlog).

### 5.1 Estructura del monorepo

```
vokara/
├── backend/
│   ├── app/
│   │   ├── api/            # routers (sin lógica de negocio)
│   │   ├── domain/         # schemas Pydantic, enums, máquina de estados
│   │   ├── services/       # matching, tailoring, ingestion, interview
│   │   ├── adapters/       # llm/, sources/, email/, storage/, export/
│   │   ├── db/             # models SQLAlchemy, repositories, migrations
│   │   ├── workers/        # tareas Celery
│   │   └── core/           # config, security, deps
│   └── tests/              # unit / integration / evals
├── frontend/
│   └── src/
│       ├── api/            # cliente generado desde OpenAPI
│       ├── features/       # onboarding, matches, tracker, prep
│       └── components/
├── infra/                  # Dockerfiles, compose, CI
└── docs/
    └── adr/                # Architecture Decision Records
```

Regla de dependencias: `api → services → repositories/adapters`. La lógica de negocio nunca vive en routers ni en tareas Celery (las tareas solo orquestan servicios).

---

## 6. Estrategia de calidad y pruebas

1. **Tipado estricto como contrato:** mypy `--strict` en CI (bloqueante); el front consume tipos generados del OpenAPI — un cambio de esquema rompe el build, no producción.
2. **Pirámide de pruebas backend:**
   - Unit: matching por reglas, máquina de estados del tracker, dedup, normalización de skills (aquí vive la mayor parte de la lógica y es 100% determinista → fácil de testear).
   - Integración: repositorios contra Postgres real (testcontainers), endpoints con TestClient.
   - Adapters de fuentes: fixtures grabadas con VCR.py/respx — los tests no golpean APIs externas y detectan cuando una fuente cambia su formato.
3. **Frontend:** Vitest/RTL por feature; Playwright para los 3 flujos críticos (onboarding → match → generar materiales; tracker; simulador).
4. **Evals de LLM (tan importantes como los tests):**
   - Golden set: 30–50 CVs **propios del equipo, de voluntarios con consentimiento específico, o sintéticos** + 50 JDs etiquetadas a mano.
   - **El golden set NUNCA incluye CVs de usuarios reales del producto** (feature 001, FR-033a). Usar material de usuarios reales para evals, golden set o ajuste de prompts requeriría un **ADR propio** y un **consentimiento opt-in explícito, separado del consentimiento de uso del servicio y revocable** (FR-033b). No se habilita por consentimiento general del servicio ni por un cambio del aviso de privacidad.
   - Métricas: F1 de extracción de campos del CV; precisión@10 del ranking contra etiquetas humanas; tasa de detección del verificador de veracidad (con casos trampa sembrados).
   - **Casos de exageración como fallo:** las evals del verificador incluyen reformulaciones que inflan el hecho original aunque el `source_id` sea válido ("participé en" → "lideré", "apoyé" → "diseñé", métricas infladas). Detectarlas es parte del criterio de aprobación, no un extra (§4.6, constitución art. IV).
   - Corren en CI en cada cambio de prompt/modelo → cambiar un prompt deja de ser un acto de fe.
5. **Definition of Done por feature:** código tipado + tests + eval (si toca LLM) + migración reversible + entrada en docs/adr si hubo decisión de arquitectura.

---

## 7. Seguridad y privacidad

- Aviso de privacidad y consentimiento explícito (LFPDPPP); los CVs son datos personales.
- Cifrado en tránsito (TLS) y en reposo (storage cifrado para documentos).
- Derecho de eliminación real: borrar cuenta = borrar perfil, documentos, embeddings y materiales generados (job asíncrono verificable).
- **Ciclo de vida del CV original** (decidido en la feature 001; ver `specs/001-candidate-onboarding/spec.md`):
  - **Borrado manual por el candidato:** puede eliminar su archivo sin eliminar el perfil que sembró, siempre que exista al menos una versión confirmada del perfil. Antes de confirmar se le advierte que pierde la capacidad de reprocesar y de fusionar contra ese archivo.
  - **Purga automática por retención:** tras **12 meses de inactividad de la cuenta** —no de tiempo desde la subida—, con aviso previo al candidato; cualquier actividad de la cuenta reinicia el contador. El plazo es **configurable, nunca una constante en código**. El perfil, sus entradas y sus versiones sobreviven a la purga.
  - **Eliminación de cuenta:** inmediata e irreversible, sin ventana de gracia. Exige confirmación escrita (el correo de la cuenta o una palabra de confirmación), no solo un botón, y antes de confirmar se ofrece exportar el archivo original y el perfil completo en formato consultable.
  - En los tres casos se elimina el **binario del storage** y el registro en `documents` queda marcado con la causa.
- **Usos autorizados del CV conservado:** respaldo, descarga por el candidato y reprocesamiento **solo a petición explícita**. El sistema puede sugerir reprocesar con un aviso pasivo en la UI del perfil (desactivable), nunca por correo ni notificación, y nunca re-siembra el perfil por iniciativa propia.
- PII nunca en logs ni en trazas LLM sin redacción.
- Secretos gestionados en el VPS como variables de entorno fuera del repo (`.env` nunca se commitea; `.env.example` sí, con valores dummy); los valores reales se sincronizan entre máquinas por gestor de contraseñas. Rotación de llaves de APIs de fuentes.
- **Autenticación con JWT propio** (ADR-001): Argon2id para contraseñas, access token de vida corta, refresh token opaco con **rotación** y detección de reuso (revoca la familia completa), **revocación de `jti` en Redis** con TTL igual al `exp`; refresh en cookie `httpOnly`/`Secure`/`SameSite=Lax` y access token en memoria del frontend.
- Rate limiting en `/auth/login`, `/auth/register` y `/auth/reset`, con backoff por IP y por cuenta.

---

## 8. Plan de desarrollo por fases

> Supuesto: equipo de 2–3 personas (1 backend, 1 frontend/fullstack, producto compartido). Las duraciones son estimaciones honestas, no promesas.

### Fase 0 — Descubrimiento y especificación (1–2 semanas)
**Entregables:** documento de specs cerrado (este roadmap refinado), 5 entrevistas con candidatos reales buscando empleo, revisión legal de fuentes de datos y aviso de privacidad, wireframes de los 5 flujos clave, golden set inicial (10 CVs + 20 JDs), ADRs 001–005 (auth, hosting, proveedor LLM, taxonomía de skills, perfil maestro).
**Criterio de salida:** alcance MoSCoW firmado; nadie discute qué es v1 durante el desarrollo.

### Fase 1 — Fundaciones (1–2 semanas)
**Entregables:** monorepo con tooling completo (ruff, mypy strict, pre-commit, CI verde), esqueleto FastAPI + auth + Postgres + Alembic + Celery, front con auth y layout, pipeline de deploy a staging funcionando **desde la semana 1** (deploy continuo desde el inicio, no al final), generación de cliente TS desde OpenAPI integrada al build.
**Criterio de salida:** un endpoint dummy viaja de DB a UI en staging con tipos end-to-end.

### Fase 2 — MVP núcleo: del CV al match (5–6 semanas)
**Entregables:**
- F1.1–F1.2: ingesta CV + revisión de perfil en UI.
- F1.3 (canales 1, 2 y 4): un agregador API + parser de correos de alertas + URL manual. (Career pages se posterga a Fase 4 — es el canal más frágil.)
- F1.4–F1.5: normalización, dedup, matching v1 con explicabilidad.
- F2.1–F2.4: CV sastre + verificador de veracidad + check ATS + carta + tracker kanban.
- Evals corriendo en CI.
**Criterio de salida (demo E2E):** un candidato sube su CV, ve 20+ matches rankeados con explicación, genera materiales para 3 vacantes y las mueve en el kanban. **Este es el MVP: si esto no aporta valor solo, nada de lo que sigue lo salvará.**

### Fase 3 — Preparación de entrevistas (3–4 semanas)
**Entregables:** F3.1 dossier de empresa, F3.2 preguntas predichas, F3.3 simulador (LangGraph + SSE streaming en UI + rúbrica), F3.4 banco de historias STAR.
**Criterio de salida:** flujo completo "tengo entrevista el jueves" → dossier + práctica + feedback en < 30 min de uso.

### Fase 4 — Conversión y cierre (2–3 semanas)
**Entregables:** F2.5 follow-ups, F2.6 mensajes a reclutadores, F2.7 analítica del embudo, F4.1 thank-you notes, F4.2 negociación básica, F4.3 comparador de ofertas, F1.6 digest de alertas, canal career pages (F1.3.3).
**Criterio de salida:** el ciclo de vida completo de una búsqueda vive dentro de Vokara.

### Fase 5 — Hardening y beta cerrada (2–3 semanas)
**Entregables:** beta con 15–25 candidatos reales, instrumentación de métricas North Star, pruebas de carga sobre ingesta y matching, auditoría de seguridad (OWASP top 10) y privacidad (flujo de eliminación verificado), presupuesto de costo LLM por usuario medido con datos reales, corrección de lo que la beta rompa (lo hará).
**Criterio de salida:** ≥ 60% de matches marcados relevantes en beta; costo LLM/usuario dentro del presupuesto; 0 hallazgos críticos de seguridad.

### Fase 6 — Lanzamiento v1 e iteración continua
Lanzamiento público, ciclo quincenal de release, y el backlog v1.x priorizado por datos de la beta: extensión de navegador (F2.8), simulador por voz (F3.5), feedback loop de matching (F1.7).

**Total estimado a v1 pública: 14–20 semanas.**

---

## 9. Despliegue y operación

- **Ambientes:** dev (Compose local) → staging (auto-deploy en merge a `main`) → prod (deploy por tag, con aprobación).
- **CI (GitHub Actions):** lint + mypy + tests + evals LLM + build de imágenes en cada PR (todo bloqueante); migraciones Alembic aplicadas automáticamente en deploy con verificación de reversibilidad.
- **Observabilidad:** Sentry (errores back y front), Langfuse/LangSmith (cada llamada LLM con costo, latencia y trazas — indispensable para operar un producto LLM sin volar a ciegas), dashboards de métricas de producto desde la Fase 5.
- **Backups:** Postgres diario con restauración probada (no solo configurada — probada) antes del lanzamiento.
- **Runbook mínimo:** qué hacer cuando una fuente de vacantes cambia formato (alerta de VCR-drift), cuando el proveedor LLM cae (fallback de proveedor vía adapter), y cuando el costo LLM se dispara (kill-switch de features caras por config).

---

## 10. Primeros 10 pasos concretos (próximas 2 semanas)

1. ~~Registrar dominio y repos de Vokara (verificar disponibilidad de vokara.com / vokara.ai / vokara.mx y del nombre en redes).~~ ✅
2. ~~Escribir ADR-001 a 005 (auth, hosting, proveedor LLM, taxonomía de skills, perfil maestro).~~ ✅
3. Entrevistar 5 personas buscando empleo hoy — validar que el flujo del MVP (Fase 2) es lo que necesitan.
4. Solicitar llaves de Adzuna/Jooble/JSearch y evaluar cobertura real de vacantes en México con 20 búsquedas de prueba.
5. Configurar el buzón inbound y validar el parseo de un correo de alerta real de LinkedIn y uno de OCC.
6. Armar el golden set inicial (10 CVs propios, de voluntarios con consentimiento específico, o sintéticos + 20 JDs etiquetadas). Nunca CVs de usuarios del producto (§6.4).
7a. ~~Inicializar el repositorio (Spec Kit, constitución, ADRs, roadmap).~~ ✅
7b. Levantar el monorepo con el tooling de la Fase 1 (`backend/`, `frontend/`, `infra/`, ruff, mypy strict, pre-commit, CI verde, deploy a staging).
8. Wireframes de: onboarding, lista de matches, detalle de vacante con score, kanban, workspace de preparación.
9. Redactar aviso de privacidad y flujo de consentimiento.
10. Definir el presupuesto de costo LLM objetivo por usuario activo/mes.
