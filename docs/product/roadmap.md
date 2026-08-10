# Roadmap — Vokara · Your AI Job Scout

> **Vokara** (*vocation* + *radar*) — Encuentra oportunidades que realmente encajan contigo.

**Versión:** 0.4 · **Fecha:** Agosto 2026 · **Estado:** Alineado con constitución v2.1.0 y ADR-001..012

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
- **Comunidad de contribuidores:** al distribuirse como software open source (AGPL-3.0, ADR-010), el público incluye a programadores que corren Vokara, reportan issues y contribuyen código. No son un canal de marketing: son parte del producto, y la calidad del repositorio —README, tests, ADRs, facilidad de levantar el entorno— es lo que los habilita o los expulsa.
- **Modo de distribución:** Vokara **no se contrata, se ejecuta**. Cada persona clona el repositorio, lo levanta en su máquina con Docker Compose y aporta su propia API key de LLM (ADR-009). No hay registro ni cuentas (ADR-008): la instancia sirve a una sola persona, la que la instaló. Esto convierte la **fricción de instalación** en un problema de producto de primer nivel (art. VII, §11).
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
5. **No es un servicio hospedado. Vokara no aloja datos de nadie.** No hay servidor del proyecto, ni cuentas, ni base de datos central (ADR-009). Los CVs, el perfil maestro y los materiales generados viven en la máquina de cada persona. La única salida de datos es la llamada al proveedor de LLM que el propio usuario configuró, y se divulga explícitamente (§7).

---

## 2. Especificación funcional por pilar

Prioridad MoSCoW: **[M]** must-have v1 · **[S]** should-have v1 · **[C]** could-have (v1.x) · **[W]** won't-have por ahora.

### Pilar 1 — Descubrimiento de vacantes ideales

- **F1.1 [M] Ingesta de CV maestro** — Upload PDF/DOCX → parseo con extracción LLM + salida tipada (Pydantic) que **siembra el perfil maestro**: entradas atómicas referenciables (experiencia, logros, skills, educación, idiomas — ver ADR-005). El usuario **revisa, corrige y enriquece** el perfil sembrado en UI y lo **confirma** antes de continuar (human-in-the-loop: el parseo nunca es perfecto y este gate define la calidad de todo lo demás). El archivo original se conserva como respaldo, no como fuente de verdad.
- **F1.2 [M] Perfil enriquecido** — Cuestionario corto: objetivo de puesto, salario esperado, ubicación/remoto, industrias, deal-breakers. Normalización de skills contra una **lista propia curada de 200–300 skills** del mercado objetivo, con alias en español e inglés y fallback por similitud de embeddings cuando no hay coincidencia exacta (ADR-004), para que "React.js", "ReactJS" y "React" sean la misma skill — y para que "React Native" no lo sea. ESCO queda como posible importación futura (el esquema `skill_id` + alias es compatible), no como alternativa abierta en v1.
- **F1.3 [M] Fuentes de vacantes (estrategia multi-canal):**
  1. **APIs de agregadores** (legítimas, con datos de México): Adzuna, Jooble, JSearch (RapidAPI, indexa Google for Jobs). Costo bajo, cobertura amplia.
  2. **Correos de alertas en la bandeja del propio candidato (opcional, ADR-012)** — no existe "dirección Vokara": no hay backend que reciba correo. El candidato configura sus alertas en LinkedIn/OCC/Computrabajo/Indeed, crea en su Gmail un **filtro que las etiquete**, y vincula su cuenta en Vokara con **App Password + IMAP**. Vokara lee **únicamente la etiqueta que él designe**, nunca la bandeja completa, y parsea las vacantes del correo. **Ventaja del equipo: ya dominan parseo de correos y adjuntos por el proyecto ALPHA.** Canal 100% dentro de los ToS.
     - **Es opcional y su ausencia no bloquea nada:** sin vincular correo, el canal de APIs de agregadores (1), las career pages (3) y la URL manual (4) siguen funcionando, y el resto del producto —perfil, matching, materiales, preparación— está completo. Lo que se pierde son fuentes automáticas, y se dice de forma explícita, nunca en silencio (art. XI).
     - **Divulgación obligatoria al configurarlo:** una App Password da acceso a **toda** la bandeja; la restricción por etiqueta es una disciplina de Vokara verificada por tests del adapter, no un permiso que Google imponga. El usuario ve esto al vincular, no enterrado en la documentación. La App Password se lee de configuración local y nunca se persiste en base de datos ni aparece en logs (art. V).
     - **Limitación registrada:** las cuentas de Google Workspace y las de Protección Avanzada no admiten App Passwords. Para ellas la vía es OAuth con proyecto propio de Google Cloud, documentada como opción avanzada.
  3. **Career pages directas** — scraping respetuoso (robots.txt) de páginas de carreras de empresas objetivo; los boards de Greenhouse/Lever/Workable exponen JSON público por empresa.
  4. **URL manual** — el usuario pega cualquier URL de vacante y Vokara la analiza al momento.
- **F1.4 [M] Normalización y deduplicación** — Toda vacante, venga de donde venga, se convierte a un esquema canónico `JobPosting`; dedup por hash de (empresa + título normalizado + similitud de descripción) para no mostrar la misma vacante 4 veces.
- **F1.5 [M] Motor de matching con score explicable** — Detalle en sección 4.5. Cada match muestra: score global, sub-scores (cobertura de requisitos obligatorios, semántica, seniority, salario, ubicación), brechas ("te faltan X, Y") y un "por qué encajas" de 2 líneas generado desde los sub-scores (no texto libre inventado).
- **F1.6 [S] Alertas y digest** — Resumen de los nuevos matches sobre umbral de score. **No hay servidor siempre encendido:** el scheduler corre **al arrancar la app** y calcula lo pendiente desde `last_run_at` (¿tocaba digest ayer y la máquina estaba apagada? se genera ahora, no se pierde ni se dispara siete veces). El digest se muestra en la UI al abrir Vokara; enviarlo por correo es opcional y usa la cuenta que el propio candidato vinculó (F1.3.2). El diseño debe ser explícito sobre huecos: el usuario ve "última revisión: hace 3 días", no un silencio indistinguible de "no hay nada nuevo".
- **F1.7 [C] Feedback loop de matching** — Thumbs up/down por vacante ajusta pesos del ranking por usuario.

### Pilar 2 — Maximizar entrevistas

- **F2.1 [M] CV sastre por vacante** — **Selecciona y reformula** el subconjunto más relevante de entradas del perfil maestro para la vacante (ADR-005): reordena, ajusta el resumen profesional, incorpora keywords de la JD **que el candidato realmente posee**; cada afirmación referencia su entrada de origen (`source_id`). Exporta DOCX y PDF.
- **F2.2 [M] Verificación ATS** — El DOCX generado se re-parsea con el mismo parser de F1.1; si se pierden campos (tablas raras, columnas), se alerta. Chequeo de keywords de la JD presentes/ausentes.
- **F2.3 [M] Carta de presentación por vacante** — Personalizada con empresa + rol + 2-3 puntos de match concretos.
- **F2.4 [M] Tracker de aplicaciones (kanban)** — Máquina de estados: `DESCUBIERTA → GUARDADA → MATERIALES_LISTOS → APLICADA → SCREENING → ENTREVISTA(n) → OFERTA → NEGOCIACIÓN → ACEPTADA / RECHAZADA / SIN_RESPUESTA / RETIRADA`. Cada transición se registra con timestamp (alimenta las métricas del embudo personal).
- **F2.5 [S] Follow-ups sugeridos** — Si una aplicación lleva N días sin respuesta, Vokara redacta el follow-up y lo deja listo para enviar. Igual que F1.6, la detección corre **al arrancar la app**, no en un cron continuo: se evalúa `next_action_at` de cada aplicación contra la fecha actual y se recuperan todos los vencimientos ocurridos mientras la máquina estuvo apagada, sin duplicar los ya atendidos. El envío nunca es automático: Vokara prepara, el candidato da el clic final (art. X).
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
| **Fricción de instalación** — el público objetivo no es exclusivamente técnico y `docker compose up` ya es una barrera | Adopción: quien no logra levantarlo no usa Vokara. Es el riesgo nº 1 del modelo local-first (ADR-009) | Instalación de un comando; wizard de configuración en la primera ejecución; pantalla de diagnóstico que dice qué falta y cómo arreglarlo; guía probada en Windows (WSL2), macOS y Linux. Alcance de producto, no de operación (art. VII, §11) |
| **El usuario paga su propia inferencia** y el público objetivo puede estar sin ingresos | Abandono al llegar al paso de la API key, o costo inesperado tras usarlo | Gemini por defecto por su capa gratuita —no es una ventaja de costo, es la diferencia entre poder usarlo y no (ADR-003)—; costo estimado visible **antes** de configurar el proveedor; caché agresivo de parseos (una JD se parsea una vez), embeddings baratos, modelo grande solo en generación de materiales |
| El LLM "mejora" el CV inventando | Daño reputacional grave al usuario y al producto | Verificador de veracidad obligatorio en el pipeline de generación (4.6) |
| Calidad del parseo de CV variable | Todo el matching se degrada | Human-in-the-loop de corrección (F1.1) + suite de evals con golden set propio (§6.4) |
| Cobertura de vacantes insuficiente en México | Producto se siente vacío | El canal de correos de alertas (F1.3.2) da cobertura de LinkedIn/OCC/Computrabajo sin scrapearlos, pero es **opcional**: quien no vincule correo depende de agregadores + URL manual, y ese escenario degradado debe ser usable por sí solo |

---

## 4. Arquitectura

### 4.1 Principio rector: pipelines deterministas + una capa conversacional

La lección de ALPHA aplica aquí: **no todo debe ser "agéntico"**. 

- **Pipelines** (ingesta, parseo, matching, generación de materiales): flujos deterministas y testeables donde el LLM es un componente con entrada/salida tipada (structured output), no un agente que decide. Predecible, barato, debuggeable.
- **Agente conversacional** (**únicamente** el simulador de entrevistas — es el solo componente conversacional/agéntico permitido por la constitución, art. III): aquí sí hay estado, turnos y decisiones del modelo → LangGraph con checkpointer.

### 4.2 Diagrama lógico

No hay capa hospedada: **todo lo que aparece dentro del marco corre en la máquina del usuario** (ADR-009). Lo único que sale son las llamadas a servicios externos, y siempre con credenciales del propio usuario.

```
╔══════════════════════════════════════════════════════════════════════╗
║  MÁQUINA DEL USUARIO — todo corre aquí (Docker Compose, ADR-009)     ║
║  Puertos publicados solo en 127.0.0.1 (ADR-008)                      ║
║                                                                      ║
║  ┌────────────────────────────────────────────────────────────────┐  ║
║  │            FRONTEND (React + TS) — 127.0.0.1:5173              │  ║
║  │   Onboarding · Matches · Kanban · Prep Workspace · Analytics   │  ║
║  └────────────────────────────────────────────────────────────────┘  ║
║                                  │ REST (OpenAPI) + SSE (simulador)  ║
║  ┌───────────────────────────────▼────────────────────────────────┐  ║
║  │           API (FastAPI + Pydantic v2) — 127.0.0.1:8000         │  ║
║  │      routers → services (dominio) → repositories (DB)          │  ║
║  │      sin autenticación; candidate_id local fijo (ADR-008)      │  ║
║  └────────────────────────────────────────────────────────────────┘  ║
║      │                           │                                   ║
║  ┌───▼────────────────┐   ┌──────▼──────────────────────┐            ║
║  │  Postgres 16       │   │  Workers (Celery + Redis)   │            ║
║  │  + pgvector        │   │  · ingesta de fuentes       │            ║
║  │  perfil, vacantes, │   │  · parseo CV/JD (LLM)       │            ║
║  │  embeddings,       │   │  · matching batch           │            ║
║  │  tracker           │   │  · generación de materiales │            ║
║  │  (sin publicar)    │   │  · scheduler al arranque    │            ║
║  └────────────────────┘   └─────────────────────────────┘            ║
║                                  │                                   ║
║        ┌─────────────────────────▼────────────────────────────┐      ║
║        │                ADAPTERS (puertos)                    │      ║
║        │  · LLM · Fuentes · Email · Storage · Export DOCX/PDF │      ║
║        │  Todos apuntan a las credenciales del propio usuario │      ║
║        └──────────────────────────────────────────────────────┘      ║
║        │                         │                                   ║
║      ┌─▼────────────────────┐    │                                   ║
║      │  Filesystem local    │    │                                   ║
║      │  CVs y materiales    │    │                                   ║
║      │  en claro (ADR-007)  │    │                                   ║
║      └──────────────────────┘    │                                   ║
║                                  │                                   ║
╚══════════════════════════════════╩═══════════════════════════════════╝
                                  │  única salida de datos de la máquina
                      ┌───────────▼──────────────────────────────────────────┐
                      │  SERVICIOS EXTERNOS QUE CONFIGURA EL USUARIO         │
                      │  · Proveedor LLM con SU API key (Gemini por defecto) │
                      │  · APIs de agregadores con SUS llaves                │
                      │  · SU Gmail vía IMAP + App Password (ADR-012)        │
                      └──────────────────────────────────────────────────────┘
```

### 4.3 Modelo de datos (entidades núcleo)

- **Sin tabla `users`** (ADR-008): no hay auth ni planes. Se conserva un `candidate_id` con **valor local fijo** asignado en la migración inicial, que la capa de API resuelve desde configuración local —nunca lo envía el cliente— y por el que **toda query de repositorio filtra desde la primera línea de código**. Es lo que permitiría añadir autenticación encima en una eventual versión hospedada sin reescribir la capa de datos.
- `candidate_profiles` — perfil maestro versionado (ADR-005); headline, años de experiencia, skills normalizadas, idiomas, expectativa salarial, preferencias (remoto, ubicaciones, industrias), embedding del perfil.
- `profile_entries` — entradas atómicas referenciables del perfil maestro (experiencia, logro, educación, skill, certificación, idioma, proyecto, historia STAR), cada una con `id` propio; sustentan la trazabilidad por `source_id` de los materiales generados.
- `documents` — CVs originales y versiones generadas (tipo, `storage_key` del filesystem local, hash) y **estado de disponibilidad del binario** (`disponible` | `eliminado_por_candidato` | `purgado_por_retencion`, con fecha y causa). Un documento sin binario conserva su registro y las referencias de las entradas que sembró, pero ya no admite reprocesamiento ni fusión (§7).
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
| LLM | **Multi-proveedor detrás del adapter** (`adapters/llm/`), sobre LangChain (structured output) + LangGraph solo en el simulador. **Gemini es el default** vía `langchain-google-genai`, elegido por su capa gratuita (ADR-003). **Soportados:** OpenAI, Anthropic, DeepSeek y Kimi, **sujetos a verificación de capacidades** —salida estructurada y embeddings— pendiente de **ADR-011** | La API key la pone el usuario, así que el proveedor lo elige él (art. XI). Ninguna feature puede asumir un proveedor: un `if provider == "..."` fuera del adapter es un bug. Si el proveedor configurado no soporta una capacidad, la feature degrada de forma **explícita e informada**, nunca en silencio. El adapter cubre también los **embeddings**; cada vector persiste `embedding_model` y `embedding_dim` para permitir cambio de proveedor re-embebiendo, sin perder datos |
| Documentos | python-docx, WeasyPrint o docx→pdf (ya resuelto en ALPHA) | Reuso directo |
| Email | Lectura IMAP de la etiqueta designada por el usuario, detrás de `EmailPort` (ADR-012) | Opcional. Reuso del know-how de parseo de ALPHA. No hay envío transaccional: sin cuentas no hay verificación ni reset |
| Calidad | ruff (lint+format), pre-commit, pytest + coverage | |

### Frontend
| Capa | Elección | Nota |
|---|---|---|
| Base | React 18 + TypeScript + Vite | SPA; Next.js descartado — ver ADR-006 |
| Server state | TanStack Query | |
| Cliente API | Generado desde OpenAPI (`openapi-typescript` u orval) | El tipado back↔front nunca se desincroniza |
| Formularios | react-hook-form + zod | |
| UI | Tailwind + shadcn/ui | Rápido y consistente |
| Testing | Vitest + React Testing Library + Playwright (e2e) | |

### Infra

**No hay infraestructura del proyecto: hay una instalación en la máquina de cada persona** (ADR-009).

- **Docker Compose con cuatro servicios y ni uno más:** `api`, `worker` (Celery), `postgres` (16 + pgvector) y `redis`. Imágenes Docker multi-stage. Cada servicio adicional que el usuario deba levantar es un usuario menos, y debe justificarse frente a la alternativa de no tenerlo (art. VII).
- **Puertos publicados SOLO en `127.0.0.1`** — `"127.0.0.1:8000:8000"`, **nunca** `"8000:8000"`. Sin autenticación, dónde escucha la instancia es el único control de acceso que existe (ADR-008). La forma corta publica en todas las interfaces, y **el firewall del host no lo detiene**: las reglas de Docker en la cadena `DOCKER` de `nat` se evalúan antes que las de `ufw`/`firewalld`. `postgres` y `redis` **no se publican en absoluto**; se alcanzan por la red interna de Compose. Dos tests de integración (`tests/integration/test_local_binding.py`) hacen de esto un requisito verificable y no un criterio de revisión de PR.
- **Migraciones Alembic automáticas al arranque**, y deben soportar **saltos de varias versiones**: actualizar depende del usuario (`git pull`), así que habrá instalaciones meses atrasadas. Una migración que solo funcione desde la versión inmediata anterior es un bug (ADR-009).
- **Sin MinIO ni S3.** Los documentos viven en el filesystem local detrás del `StoragePort`, sin cifrado en reposo — no protegería nada cuando la clave estaría en un `.env` junto a los datos que cifra (ADR-007). La protección real se recomienda en el README: cifrado de disco del sistema operativo.
- **Sin Sentry por defecto.** Errores en **logs locales estructurados** (structlog); el envío a un servicio externo solo bajo **opt-in explícito** y desactivado de fábrica (art. VIII, constitución v2.1.0). Un reporte de error arrastra rutas, fragmentos de datos y a veces contenido de prompt: enviarlo por defecto sería la misma fuga que el art. V prohíbe, entrando por la puerta de la operación.
- **Trazas de LLM locales y solo con metadatos** (modelo, versión de prompt, tokens, costo, latencia, éxito/error). **Descartadas Langfuse, LangSmith y cualquier plataforma de observabilidad de LLM que capture prompts**, hospedada o auto-alojada: un prompt de Vokara lleva el CV íntegro, es decir PII de principio a fin (ADR-003). Depurar sin ver la entrada que rompió el prompt se resuelve reproduciendo con el golden set, que es material sintético.
- **Sin Kubernetes, sin reverse proxy con TLS, sin ambientes remotos, sin backups del proyecto.** El backup es que el usuario copie su directorio de datos.
- **GitHub Actions valida, no despliega** (§9).

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
   - **El golden set NUNCA incluye CVs de usuarios reales del producto** (feature 001, FR-033a). Con ejecución local esto deja de ser solo una política y pasa a ser una imposibilidad arquitectónica: el equipo no tiene acceso a los datos de nadie (§7). La regla se conserva escrita porque define qué pasaría si alguien quisiera saltarla: usar material de usuarios reales para evals, golden set o ajuste de prompts exigiría que **ellos lo enviaran deliberadamente** tras un **ADR propio** y un **opt-in explícito y revocable** (FR-033b). Un contribuidor que aporte CVs reales de terceros a la suite de evals está violando esta regla igual que lo estaría el equipo.
   - Métricas: F1 de extracción de campos del CV; precisión@10 del ranking contra etiquetas humanas; tasa de detección del verificador de veracidad (con casos trampa sembrados).
   - **Casos de exageración como fallo:** las evals del verificador incluyen reformulaciones que inflan el hecho original aunque el `source_id` sea válido ("participé en" → "lideré", "apoyé" → "diseñé", métricas infladas). Detectarlas es parte del criterio de aprobación, no un extra (§4.6, constitución art. IV).
   - Corren en CI en cada cambio de prompt/modelo → cambiar un prompt deja de ser un acto de fe.
5. **Definition of Done por feature:** código tipado + tests + eval (si toca LLM) + migración reversible + entrada en docs/adr si hubo decisión de arquitectura.

---

## 7. Seguridad y privacidad

**El modelo cambió de raíz con el pivote local-first.** Vokara no es responsable de datos de nadie: no hay base central que filtrar ni cuentas que vulnerar. La privacidad deja de ser una promesa operativa y pasa a ser una propiedad de la arquitectura — el dato está donde el usuario lo puso (art. V). Lo que la arquitectura *no* puede garantizar se compensa con divulgación explícita, no con silencio.

### 7.1 La frontera: qué sale de la máquina y qué no

- Los datos del candidato —CV original, perfil maestro, embeddings, materiales generados, historial de aplicaciones— **nunca salen de su máquina**. Existe **una sola excepción**: el contenido que Vokara envía al proveedor de LLM que el propio usuario configuró con su API key.
- **Divulgación obligatoria de esa excepción**, en texto claro, **en la primera ejecución y en el README** (§11): qué se envía, a qué proveedor y en qué momento del flujo. Concretamente: el CV íntegro al parsear (F1.1), la descripción de la vacante al parsearla (F1.3/F1.5), el perfil maestro y la JD al generar materiales (F2.1–F2.3), y la conversación al usar el simulador (F3.3). **Prohibido enterrar la divulgación** en documentación secundaria o darla por sabida.
- Se divulga también qué **otros** servicios se contactan cuando el usuario los activa: APIs de agregadores con sus llaves, y su propio Gmail por IMAP si vinculó correo (ADR-012).
- **Cero telemetría, analítica o reportes de error a terceros por defecto.** Cualquier telemetría futura exige **opt-in explícito Y un ADR propio**; sin ambas cosas, no se implementa. Consecuencia asumida: el proyecto no sabrá cuántas instalaciones hay ni dónde fallan, y los únicos canales de señal son issues y reportes voluntarios (ADR-009).
- **Verificar y divulgar en el README, por proveedor soportado**, la disponibilidad regional y los términos de uso de datos —en particular, que no se usen para entrenamiento—. Con ejecución local esa elección es del usuario, y solo puede elegir bien si tiene el dato (ADR-003).

### 7.2 Credenciales: API keys y App Passwords

- Se leen de **configuración local** (variables de entorno o archivo de configuración del usuario, fuera del repositorio). `.env` nunca se commitea; `.env.example` sí, con valores dummy.
- **Prohibido persistirlas en la base de datos. Prohibido que aparezcan en logs, trazas o mensajes de error.** Aplica igual a la API key del LLM, a las llaves de agregadores y a la App Password de Gmail (ADR-012).
- Un mensaje de error de credencial inválida dice **qué hacer** ("la API key de Gemini fue rechazada; genera una nueva en …"), nunca el valor de la clave.
- Revocar es la forma de desvincular: se documenta cómo revocar la App Password desde la cuenta de Google y cómo rotar cada API key.

### 7.3 Control de acceso: bind a loopback como requisito, no como recomendación

- **Sin autenticación** (ADR-008): la instancia sirve a una sola persona, la que la instaló, y la frontera de seguridad real es la sesión del sistema operativo.
- Por eso **el único control de acceso de Vokara es dónde escucha**, y eso lo convierte en un requisito verificable: todo puerto publicado lleva prefijo `127.0.0.1:`, `postgres` y `redis` no se publican, y dos tests de integración fallan si alguien lo rompe (§5 Infra). **Un puerto publicado en `0.0.0.0` es un bug de seguridad, no un detalle de configuración.**
- Si el puerto sale de la máquina no hay nada detrás: cualquiera en esa red lee el perfil, los CVs y los materiales generados. Se dice así de claro en el README.
- **No hay PIN ni pantalla de bloqueo local**, deliberadamente: sería un bloqueo de UI sobre datos en claro, y comunicaría una protección que no existe. Una falsa sensación de seguridad cambia el comportamiento del usuario en la dirección equivocada (ADR-008).

### 7.4 Los archivos quedan en claro — riesgo divulgado

- **Riesgo asumido y divulgado (ADR-007):** los CVs y materiales generados se guardan **sin cifrar** en el filesystem del usuario. Cualquier proceso que corra con su cuenta puede leerlos, y un equipo robado sin cifrado de disco expone su contenido.
- No es una omisión: en local la clave maestra viviría en un `.env` junto a los datos que protege, así que el cifrado de aplicación no añadiría una barrera, añadiría un paso. La respuesta correcta al riesgo real —robo o pérdida del equipo— es el **cifrado de disco del sistema operativo** (FileVault, BitLocker, LUKS), y el README lo recomienda en vez de implementar una versión peor del mismo mecanismo.
- Queda **diferido, no descartado**, para un eventual despliegue multi-usuario, donde las premisas del cifrado en reposo vuelven a cumplirse.

### 7.5 Ciclo de vida del CV original

Borrar es borrar un archivo en un disco: no hay réplicas, backups ni buckets que perseguir, así que no hace falta un job asíncrono verificable. Lo que sí se conserva de la feature 001 es la disciplina de producto (ver `specs/001-candidate-onboarding/spec.md`):

- **Borrado manual por el candidato:** puede eliminar su archivo sin eliminar el perfil que sembró, siempre que exista al menos una versión confirmada del perfil. Antes de confirmar se le advierte que pierde la capacidad de reprocesar y de fusionar contra ese archivo.
- **Purga automática por retención:** tras **12 meses de inactividad de la instalación**, con aviso previo; cualquier actividad reinicia el contador. El plazo es **configurable, nunca una constante en código**. El perfil, sus entradas y sus versiones sobreviven a la purga.
- **Borrar todo:** desinstalar Vokara es borrar el directorio de datos y bajar el Compose. Dentro de la app se ofrece un borrado completo equivalente, inmediato e irreversible, con confirmación escrita y con la opción de exportar antes el archivo original y el perfil completo en formato consultable.
- En todos los casos se elimina el binario del storage y el registro en `documents` queda marcado con la causa.
- **Usos autorizados del CV conservado:** respaldo, descarga por el candidato y reprocesamiento **solo a petición explícita**. El sistema puede sugerir reprocesar con un aviso pasivo en la UI del perfil (desactivable), nunca por correo ni notificación, y nunca re-siembra el perfil por iniciativa propia.

### 7.6 Lo que se conserva del modelo anterior

- **PII fuera de logs y de trazas de LLM** (redacción obligatoria). Las trazas registran metadatos, nunca contenido de prompt ni de respuesta (§5 Infra, ADR-003).
- **Prohibido el scraping de plataformas cuyos ToS lo prohíben** (LinkedIn, Indeed, OCC, Computrabajo) y **prohibido el auto-apply headless**: solo assisted-apply con acción final humana. Estas prohibiciones no se relajan con el pivote — protegen al usuario del baneo de **sus propias** cuentas, y ese riesgo no desaparece al mover el software a su máquina: se traslada a ella.
- **AGPL-3.0** (ADR-010) como garantía legal, no solo de diseño: quien reciba un Vokara modificado conserva el derecho de auditar el código que procesa sus datos personales, y quien hospede un derivado debe publicar sus cambios (AGPL §13).

---

## 8. Plan de desarrollo por fases

> Supuesto: equipo de 2–3 personas (1 backend, 1 frontend/fullstack, producto compartido). Las duraciones son estimaciones honestas, no promesas.

### Fase 0 — Descubrimiento y especificación (1–2 semanas)
**Entregables:** documento de specs cerrado (este roadmap refinado), 5 entrevistas con candidatos reales buscando empleo, revisión legal de fuentes de datos, wireframes de los 5 flujos clave, golden set inicial (10 CVs + 20 JDs), ADRs base.
**Nota de v0.4:** el pivote local-first ocurrió al cierre de esta fase. Dos entregables originales quedaron sin objeto —el aviso de privacidad LFPDPPP (no hay responsable de datos) y los ADR-001/002 (auth y hosting, ahora Superseded por ADR-008 y ADR-009)—, y a cambio se produjeron los ADRs 007–010 y 012 y la constitución v2.1.0. La revisión legal de fuentes **sí sigue vigente**: los ToS de las bolsas de trabajo aplican igual cuando el software corre en la máquina del usuario.
**Criterio de salida:** alcance MoSCoW firmado; nadie discute qué es v1 durante el desarrollo.

### Fase 1 — Fundaciones (1–2 semanas)
**Entregables:** monorepo con tooling completo (ruff, mypy strict, pre-commit, CI verde), esqueleto FastAPI + Postgres + Alembic + Celery (sin auth, ADR-008), front con layout, **`docker-compose.yml` con los cuatro servicios y puertos en `127.0.0.1:`** más los dos tests de `test_local_binding.py` en el mismo PR que el Compose, **migraciones automáticas al arranque**, `LICENSE` AGPL-3.0 y README con la divulgación del art. V, generación de cliente TS desde OpenAPI integrada al build.
**No hay deploy a staging:** no hay staging. El equivalente a "deploy continuo desde la semana 1" en este modelo es que **el repositorio se levante desde cero en una máquina limpia desde la semana 1**, y que siga haciéndolo en cada PR.
**Criterio de salida:** `docker compose up` levanta todo y un endpoint dummy viaja de DB a UI con tipos generados end-to-end.

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

### Fase 5 — Hardening y pruebas con usuarios reales que corren el software localmente (2–3 semanas)

No hay beta cerrada hospedada porque no hay nada que hospedar. En su lugar: **15–25 candidatos reales instalan Vokara en su propia máquina** y lo usan con sus datos y su API key.

**Entregables:**
- **Prueba de instalación asistida** en Windows (WSL2), macOS y Linux, con al menos un participante no técnico por sistema operativo. **Lo primero que se mide es cuántos logran levantarlo sin ayuda y dónde se atoran los que no** (§11): es la métrica que decide si el modelo de distribución del ADR-009 funciona.
- Corrección de la fricción encontrada, sobre el flujo de §11 (wizard, diagnóstico, mensajes de error).
- Recolección de métricas North Star **por reporte voluntario del participante**, no por telemetría (art. V): el instrumento es una entrevista o un formulario que el usuario llena, y hay que diseñarlo como tal.
- **Costo real de LLM medido por el propio usuario** con las trazas locales, para validar la estimación que §11 le muestra antes de configurar el proveedor.
- Verificación de que la **degradación explícita** funciona: participantes con proveedores distintos a Gemini, y participantes sin correo vinculado, deben tener un producto usable y saber qué les falta y por qué (art. XI).
- Auditoría de seguridad y privacidad enfocada en lo que aplica a este modelo: **binding a loopback verificado en máquinas reales**, ausencia de credenciales en logs y trazas, PII fuera de trazas, y el borrado completo del §7.5.
- Corrección de lo que la prueba rompa (lo hará).

**Criterio de salida:** ≥ 60% de matches marcados relevantes; **≥ 80% de participantes levantan Vokara sin intervención del equipo**; costo LLM medido y coherente con lo estimado; 0 hallazgos críticos de seguridad.

### Fase 6 — Lanzamiento v1 e iteración continua
Release pública en GitHub, ciclo quincenal de release, y el backlog v1.x priorizado por lo que arroje la Fase 5: extensión de navegador (F2.8), simulador por voz (F3.5), feedback loop de matching (F1.7). Si la fricción de instalación resulta ser el cuello de botella real de adopción, el instalador de escritorio vuelve a la mesa con un ADR nuevo y con datos en vez de suposiciones (ADR-009).

**Total estimado a v1 pública: 14–20 semanas.**

---

## 9. Distribución y operación

**El equipo no opera nada.** No hay ambientes, ni servidores, ni deploy: lo que se entrega es un repositorio que otra persona ejecuta (ADR-009). Lo que antes era despliegue, ahora es distribución.

- **Distribución vía GitHub.** El repositorio público es el único canal de entrega: `git clone` + `docker compose up`. No hay artefacto que publicar en otro sitio ni infraestructura que aprovisionar.
- **Versionado por releases.** Cada versión es un tag semántico con release notes en GitHub, y esas notas son la única forma en que el usuario se entera de qué cambió: **no hay canal de actualización automática ni telemetría** para avisarle. Actualizar es cosa suya (`git pull` + migraciones), así que las notas deben decir explícitamente cuándo un cambio requiere acción manual.
- **Migraciones que soportan saltos de varias versiones.** Habrá instalaciones meses atrasadas. Una migración que solo funcione desde la versión inmediata anterior es un bug, y probar el salto largo es parte de la release, no del deploy (ADR-009).
- **CI (GitHub Actions) valida el proyecto, no despliega nada.** Se conserva íntegro como **bloqueante en cada PR**: ruff (lint + format), `mypy --strict`, tests unit e integración, evals de LLM cuando aplique, build de imágenes, verificación de reversibilidad de las migraciones Alembic, y los tests de `test_local_binding.py` que impiden publicar un puerto fuera de loopback. Se añade una **prueba de instalación limpia** —levantar el Compose desde cero y verificar que la app responde—, porque en este modelo esa es la funcionalidad más crítica del producto (§11).
- **Verificación de licencias de dependencias en CI.** Con AGPL-3.0 (ADR-010), una dependencia con licencia incompatible es un bloqueo de merge, no un detalle.
- **Observabilidad local, para el usuario.** Logs estructurados (structlog) y trazas de LLM **con metadatos únicamente** —costo, latencia, tokens, versión de prompt—, visibles en su máquina y útiles para depurar con él. Sin Sentry ni plataformas de trazas de LLM por defecto (§5 Infra, art. VIII, ADR-003). El corolario incómodo: **el proyecto no verá los errores de nadie**; los issues de GitHub son el canal, y por eso los mensajes de error tienen que ser buenos por sí solos (§11).
- **Backups: del usuario, no del proyecto.** El README explica qué copiar —el directorio de datos y un dump de Postgres— y cómo restaurarlo. El proyecto no custodia datos de nadie, así que tampoco puede recuperarlos.
- **Runbook mínimo, reescrito como material para el usuario y para quien atienda issues:** qué hacer cuando una fuente de vacantes cambia formato (alerta de VCR-drift en CI, fix en una release), cuando el proveedor de LLM cae o rechaza la clave (mensaje accionable + cambio de proveedor por configuración, art. XI), cuando la instalación no levanta (pantalla de diagnóstico, §11), y cuando el costo de LLM se dispara (kill-switch de features caras por configuración — aquí el que paga es el usuario, así que el control es suyo).

---

## 10. Primeros 10 pasos concretos (próximas 2 semanas)

1. ~~Registrar dominio y repos de Vokara (verificar disponibilidad de vokara.com / vokara.ai / vokara.mx y del nombre en redes).~~ ✅
2. ~~Escribir los ADRs base (001–010, 012) y pivotar la constitución a v2.1.0.~~ ✅ · **Pendiente: ADR-011** — verificación de capacidades por proveedor (salida estructurada y embeddings en OpenAI, Anthropic, DeepSeek y Kimi), que hoy bloquea la fila de LLM de §5.
3. Entrevistar 5 personas buscando empleo hoy — validar que el flujo del MVP (Fase 2) es lo que necesitan **y observar a dos de ellas intentando instalarlo**: la fricción de instalación se valida con personas, no con suposiciones (§11).
4. Solicitar llaves de Adzuna/Jooble/JSearch y evaluar cobertura real de vacantes en México con 20 búsquedas de prueba. **Documentar además cuántos pasos le cuesta a un usuario obtener las suyas**: en local, cada llave la tramita él.
5. Validar el camino de correo del ADR-012 de punta a punta: crear el filtro y la etiqueta en una cuenta Gmail real, generar una App Password, leer por IMAP **solo esa etiqueta**, y parsear un correo de alerta real de LinkedIn y uno de OCC.
6. Armar el golden set inicial (10 CVs propios, de voluntarios con consentimiento específico, o sintéticos + 20 JDs etiquetadas). Nunca CVs de usuarios del producto (§6.4).
7a. ~~Inicializar el repositorio (Spec Kit, constitución, ADRs, roadmap).~~ ✅
7b. Levantar el monorepo con el tooling de la Fase 1 (`backend/`, `frontend/`, `infra/`, ruff, mypy strict, pre-commit, CI verde) **más el `docker-compose.yml` con puertos en `127.0.0.1:` y sus dos tests de binding en el mismo PR**. Sin deploy: el criterio es que levante desde cero en una máquina limpia.
8. Wireframes de: **wizard de primera ejecución y pantalla de diagnóstico (§11)**, onboarding, lista de matches, detalle de vacante con score, kanban, workspace de preparación.
9. Añadir `LICENSE` (AGPL-3.0, ADR-010) y redactar el README: instalación probada en Windows (WSL2), macOS y Linux; **divulgación del art. V** (qué se envía al proveedor de LLM y cuándo); recomendación de cifrado de disco (ADR-007); nota de que Vokara solo escucha en la máquina del usuario (ADR-008); limitación de App Passwords en cuentas Workspace (ADR-012). **Ya no hay aviso de privacidad LFPDPPP: no somos responsables de datos de nadie.**
10. Calcular el **costo estimado de LLM por mes de búsqueda activa** para cada proveedor soportado, y decidir cómo se le muestra al usuario **antes** de pedirle su API key (§11). El presupuesto ya no es del proyecto: es información que el usuario necesita para decidir.

---

## 11. Experiencia de instalación y primera ejecución

**Esto es un entregable de primer nivel, no documentación de soporte.** El artículo VII eleva la fricción de instalación a criterio constitucional por una razón concreta: en el modelo local-first, quien no logra levantar Vokara simplemente no lo usa, y el público objetivo no es exclusivamente técnico. Cada obstáculo entre `git clone` y el primer match es equivalente a una feature que no existe. Se diseña, se prueba con personas y se corrige como cualquier otra parte del producto (Fase 5).

El estándar de calidad de toda esta sección cabe en una frase: **una persona que sabe usar una computadora pero no programa debe llegar sola desde el repositorio hasta su primer match.**

### 11.1 Instalación de un comando

- **Un solo comando después de clonar.** `docker compose up` —o un script `./install.sh` equivalente que lo envuelva— debe funcionar **sin edición manual de archivos** más allá de lo que el wizard pide después. Nada de "copia el `.env.example`, edita estas ocho variables y luego corre las migraciones": eso es el fallo que esta sección existe para evitar.
- **Migraciones automáticas al arranque** (§5). El usuario nunca ejecuta un comando de Alembic, ni en la primera instalación ni al actualizar.
- **Guía probada, no escrita de memoria**, en Windows (WSL2), macOS y Linux (ADR-009). "Probada" significa ejecutada por alguien en una máquina limpia, y esa prueba corre también en CI (§9).
- **Prerrequisitos explícitos y verificados por el propio instalador**: Docker, versión mínima, y en Windows WSL2. Si falta algo, el mensaje dice qué instalar y enlaza a dónde.
- El objetivo declarado es que la instalación entera se mida en minutos, no en tarde.

### 11.2 Wizard de primera ejecución: dos pasos obligatorios y uno opcional

Al abrir Vokara por primera vez, el usuario entra en un wizard. **No hay registro ni login que atravesar** (ADR-008): lo primero que ve es esto.

**Paso 1 — Divulgación (obligatorio).** Antes de configurar nada, en texto claro y en la pantalla —no en un enlace, no en el README (art. V)—: qué datos se quedan en su máquina, cuál es la **única** excepción (el contenido enviado al proveedor de LLM que él elija), **qué se envía exactamente y en qué momento** (el CV al parsearlo, la JD al parsearla, perfil + JD al generar materiales, la conversación en el simulador), que Vokara **no envía telemetría ni reportes de error a terceros**, y que **sus archivos quedan en claro en el disco** con la recomendación de activar el cifrado de disco del sistema operativo (ADR-007). Se avanza con un acuse explícito.

**Paso 2 — Proveedor de LLM y API key, con preflight de capacidades (obligatorio).**
- Elección de proveedor con **Gemini preseleccionado** y la razón dicha en la propia pantalla: es el único con capa gratuita suficiente para usar Vokara de verdad sin tarjeta (ADR-003). Los demás aparecen como iguales, no como opciones de segunda.
- Enlace directo a dónde se obtiene la llave de cada proveedor, con los pasos contados.
- **Preflight al guardar la clave, no en el primer uso real.** Vokara hace una llamada de prueba y verifica las **capacidades** que necesita —salida estructurada y embeddings (art. XI, ADR-011)— antes de dejar avanzar. Los tres resultados posibles son distintos y se comunican distinto: llave válida y completa → adelante; llave válida pero **sin alguna capacidad** → se dice **qué funciones concretas no estarán disponibles y por qué**, y el usuario decide si continúa así o cambia de proveedor (degradación explícita e informada, nunca silenciosa); llave rechazada → mensaje accionable, nunca un stack trace.
- La clave se guarda en **configuración local**, nunca en la base de datos, y nunca aparece en logs ni en mensajes de error (art. V, §7.2).

**Paso 3 — Vincular correo (opcional, y visiblemente opcional).**
- Se puede **omitir con un clic** y llegar igual al producto completo. La pantalla dice qué se gana vinculando (una fuente de vacantes más rica: LinkedIn, OCC, Computrabajo vía sus correos de alerta) y qué **no** se pierde al omitirlo (todo lo demás: agregadores, URL manual, matching, materiales, preparación).
- Si el usuario acepta: los tres pasos del ADR-012 —verificación en dos pasos, App Password, etiqueta de Gmail— guiados con capturas, más la **divulgación obligatoria** de que una App Password da acceso a **toda** la bandeja y que leer solo la etiqueta designada es un compromiso de Vokara verificado por tests, no un límite que Google imponga.
- **Aviso por adelantado** de que las cuentas de Google Workspace y las de Protección Avanzada no admiten App Passwords, con el enlace a la vía OAuth. Se dice **antes** de empezar, no a mitad de la configuración.

### 11.3 Transparencia de costo

- **Antes** de pedir la API key, el wizard muestra el **costo estimado por mes de búsqueda activa** para el proveedor seleccionado, con el supuesto de uso a la vista ("~X vacantes analizadas y ~Y materiales generados al mes") para que la cifra sea interpretable y no un número mágico.
- Para Gemini se indica explícitamente **qué cabe dentro de la capa gratuita** y a partir de qué punto se empieza a pagar.
- Después, el **costo real acumulado** es consultable en la app desde las trazas locales (§5 Infra). El usuario tiene que poder responder "¿cuánto llevo gastado?" sin salir de Vokara.
- **Kill-switch por configuración** para las funciones caras (generación de materiales, simulador), porque aquí quien paga la inferencia es él y el control debe ser suyo (§9).

### 11.4 Pantalla de diagnóstico del sistema

Una pantalla permanente en la app —no solo del wizard— que responde "¿está todo bien?" sin pedirle al usuario que lea logs ni abra una terminal. Verifica y muestra el estado de:

- Los cuatro servicios del Compose (`api`, `worker`, `postgres`, `redis`) y su conectividad.
- Versión de esquema y **migraciones pendientes** tras un `git pull`.
- Proveedor de LLM configurado, resultado del **preflight de capacidades** y **qué funciones están degradadas** por ello.
- Correo vinculado o no, y si la etiqueta configurada existe y es alcanzable.
- Llaves de agregadores presentes y válidas.
- Directorio de datos: ruta, espacio disponible y **documentos con `storage_key` cuyo archivo ya no existe** (ADR-007).
- **Que los puertos estén publicados solo en loopback** — si algo quedó expuesto, es una advertencia de seguridad visible, no una línea en un log (§7.3).
- **Nunca muestra credenciales**, ni siquiera parcialmente: solo "configurada / no configurada / rechazada".

Es también la primera cosa que se le pide a alguien que abre un issue: sin telemetría, esta pantalla es el reporte de estado del proyecto (§9).

### 11.5 Mensajes de error que dicen qué hacer

Regla, no aspiración: **todo error que el usuario pueda ver le dice qué pasó, por qué y cuál es el siguiente paso concreto.** Un stack trace en la UI es un bug de producto.

| En vez de | Decir |
|---|---|
| `Connection refused: postgres:5432` | "La base de datos no está lista. Suele tardar unos segundos en el primer arranque; si persiste, revisa la pantalla de diagnóstico." |
| `401 Unauthorized` | "Tu proveedor rechazó la API key. Verifica que la copiaste completa y que sigue activa en [enlace a la consola del proveedor]." |
| `429 Too Many Requests` | "Alcanzaste el límite de tu capa gratuita de Gemini. Puedes esperar al reinicio de cuota o configurar otro proveedor en Ajustes." |
| `imaplib.error: AUTHENTICATIONFAILED` | "Gmail rechazó la App Password. Si tu cuenta es de Google Workspace, las App Passwords están deshabilitadas: usa la vía OAuth [enlace]." |
| `NotImplementedError: embeddings` | "El proveedor que configuraste no ofrece embeddings, así que el matching semántico está desactivado. El matching por reglas sigue funcionando. Para activarlo, cambia de proveedor en Ajustes." |
| `FileNotFoundError: /data/...` | "No se encuentra el archivo de tu CV en el directorio de datos. Si moviste o borraste esa carpeta, tu perfil sigue intacto, pero no se puede reprocesar el archivo original." |

Ningún mensaje incluye una API key, una App Password ni PII (§7.2). Los tres errores más probables de la primera ejecución —Docker ausente, puerto ocupado, API key inválida— se prueban a mano en cada release: son los que deciden si alguien se queda o se va.
