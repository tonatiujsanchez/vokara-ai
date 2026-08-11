# Quickstart — validación de la feature 001

**Feature**: 001-candidate-onboarding · **Fecha**: 2026-08-11

Guía para levantar el entorno y **verificar** que la feature cumple lo que la spec exige. No contiene implementación: los detalles de modelo están en [data-model.md](./data-model.md), los de API en [contracts/openapi.yaml](./contracts/openapi.yaml) y las decisiones en [research.md](./research.md).

> **Esta guía se ejecuta como usuario, no como equipo.** Vokara no se despliega, se instala en una máquina (ADR-009). Si algún paso de esta guía requiere editar un archivo a mano más allá de lo que el wizard pide, eso **es un hallazgo**: contradice roadmap §11.1 y hay que corregirlo antes de cerrar la feature.

---

## 0. Requisitos previos

| Requisito | Comprobación |
|---|---|
| Docker + Docker Compose | `docker compose version` |
| En Windows: trabajar dentro de **WSL2**, con el repo en el FS de WSL (ADR-000) | `pwd` no empieza por `/mnt/c` |
| `git config --global core.autocrlf false` en toda máquina de desarrollo | `git config core.autocrlf` |
| Una API key de un proveedor **con verificación registrada** en el ADR-011 | Hoy: Google. Se pega **en el wizard**, no en un archivo |
| Para desarrollo local fuera de contenedor: uv y Node 20 LTS | `uv --version` · `node --version` |

**No hay `.env` que rellenar para arrancar.** Ni `JWT_SECRET` (no hay auth, ADR-008), ni `DOCUMENT_ENCRYPTION_KEY` (no hay cifrado, ADR-007), ni credenciales de S3 (no hay object storage). Las API keys las pide el wizard y se escriben en configuración local (FR-008). Las variables opcionales —`VOKARA_DATA_DIR`, overrides de nombre de modelo— tienen defaults sensatos y solo se tocan para desviarse de ellos.

### El `.env` vive en la raíz del repositorio, y en ningún otro sitio

**Decisión vinculante.** Hay **un solo** `.env`, en la raíz del repo, junto a `.env.example`. Es donde ya lo busca `scripts/verify_providers.py` y donde el usuario espera encontrarlo. **No existe `infra/.env` ni `infra/.env.example`.** Dos ubicaciones para la misma llave son fricción del art. VII y la causa más previsible del issue "a mí no me toma la API key".

Como el comando documentado es `docker compose -f infra/docker-compose.yml up`, Compose toma `infra/` como directorio de proyecto y **buscaría ahí su `.env`**. Se resuelve con dos reglas, ambas verificadas por `backend/tests/integration/test_compose_env_contract.py`:

1. `api` y `worker` declaran `env_file: [{ path: ../.env, required: false }]` — ruta relativa al archivo de Compose, es decir la raíz del repo. `required: false` hace que un clon virgen **sin `.env`** arranque igual.
2. **`infra/docker-compose.yml` no usa interpolación `${...}`.** Es la única construcción que leería el `.env` del directorio de proyecto y que reintroduciría en silencio la segunda ubicación. Los valores de infraestructura (usuario, contraseña y nombre de la base, URLs internas) son literales en el Compose: son credenciales de desarrollo local de una base que **no se publica al host**, así que no hay nada que parametrizar.

Al añadir una variable nueva, actualizar el `.env.example` **de la raíz** en el mismo commit: es la única forma de que la otra máquina se entere (ADR-000).

---

## 1. Levantar el entorno

```bash
git clone <repo> && cd vokara
docker compose -f infra/docker-compose.yml up
```

Eso es todo. Las migraciones se aplican **solas** al arranque (roadmap §11.1): el usuario nunca ejecuta un comando de Alembic. **Sin copiar ni editar ningún `.env`**: si más tarde creas uno, va en la raíz del repo (§0) y el Compose lo toma vía `env_file: ../.env`.

**Verificación de que el entorno está sano:**

```bash
curl -s localhost:8000/health                              # {"status":"ok"}
docker compose exec postgres psql -U vokara -c "\dx"       # extensión vector presente
docker compose ps                                          # api, worker, postgres, redis — cuatro, ni uno más
```

**Verificación de binding (ADR-008) — hazla a mano una vez, además de los tests:**

```bash
docker compose -f infra/docker-compose.yml port api 8000   # debe imprimir 127.0.0.1:8000
ss -ltn | grep 8000                                        # NUNCA 0.0.0.0:8000 ni *:8000
```

Recuerda por qué importa: sin autenticación, dónde escucha la instancia es el único control de acceso que existe, y **`ufw` no protege un puerto publicado por Docker** — sus reglas en la cadena `DOCKER` de `nat` se evalúan antes.

### Para desarrollo (opcional)

```bash
cd backend && uv sync --frozen
uv run uvicorn app.main:app --reload                       # API en :8000
uv run celery -A app.workers.celery_app worker -l info     # worker, otra terminal. SIN beat
cd ../frontend && npm ci && npm run dev                    # SPA en :5173
```

---

## 2. Contrato tipado extremo a extremo (art. I)

```bash
cd backend && uv run python -m app.openapi_export > ../frontend/openapi.json
cd ../frontend && npm run generate:api        # openapi-typescript → src/api/schema.d.ts
git diff --exit-code frontend/openapi.json frontend/src/api/schema.d.ts
```

**Esperado**: sin diferencias. Un diff aquí significa que alguien cambió la API sin regenerar el cliente; CI falla por lo mismo.

**Prueba negativa (hazla una vez, para creerte el mecanismo)**: renombra un campo de un esquema Pydantic del backend, regenera y ejecuta `npm run build`. El build de TypeScript debe **fallar**. Si compila, el art. I no está realmente aplicado.

---

## 3. Recorrido manual — primera ejecución (US1)

Con la SPA en `localhost:5173`, sobre una **instalación limpia**:

| # | Acción | Resultado esperado | Requisito |
|---|---|---|---|
| 1 | Abrir Vokara por primera vez | Pantalla de divulgación **sin ningún campo que llenar**, con el texto completo a la vista: qué se queda en la máquina, la única excepción, que no se envía nada a los creadores y que los archivos quedan **sin cifrar** | FR-001, US1 AC1 |
| 2 | Intentar continuar sin marcar el acuse | Botón inhabilitado. Navegar directo a `/onboarding` tampoco funciona | FR-002, US1 AC2 |
| 3 | Llamar `POST /documents` con curl, sin acuse | `409 DISCLOSURE_ACKNOWLEDGEMENT_REQUIRED`. **El gate es de servidor**, no del guard de la SPA | SC-011 |
| 4 | Marcar el acuse y continuar | Paso de proveedores con **dos configuraciones separadas**, Gemini presugerido en ambas, la razón de la separación en una línea, y el **costo estimado de cada una antes de pedir ninguna llave** | FR-004, FR-005, US1 AC3 |
| 5 | Elegir el mismo proveedor para ambas | Se pide **una sola** API key y se verifican las dos capacidades por separado con ella | FR-004, US1 AC4 |
| 6 | Guardar una API key válida para generación | Preflight con llamada real contra un esquema; queda **verificada** y permite avanzar | FR-006, US1 AC5 |
| 7 | Guardar una API key mal copiada | Rechazo con qué revisar y dónde regenerarla. **Sin mostrar la llave, sin traza técnica**, sin dejar avanzar | FR-007.1, US1 AC6 |
| 8 | Guardar una llave con cuota agotada | Se distingue explícitamente de una llave inválida —**la llave sirve, la cuota no**— y ofrece esperar o cambiar de proveedor | FR-007.4, US1 AC8 |
| 9 | Configurar embeddings con llave válida | Verificada, con la **dimensión del vector registrada** (768 en Google) | FR-007.2 |
| 10 | Desconectar la red y reintentar un preflight | "No se pudo verificar", **no** "la llave es incorrecta", y se reintenta **sin volver a pegar la llave** | Edge case |
| 11 | Llegar al paso de correo | Omitir tiene **el mismo peso visual** que continuar; la pantalla dice qué se gana y qué **no** se pierde | FR-011, US1 AC9 |
| 12 | Elegir vincular Gmail | **Antes** de pedir nada: aviso de que una App Password da acceso a **toda** la bandeja, que la etiqueta es un compromiso de Vokara verificado por tests, y que Workspace y Protección Avanzada no la admiten | FR-012, US1 AC10 |
| 13 | Dar una etiqueta que no existe | La vinculación **no** se da por buena; se indica cómo crear el filtro y la etiqueta | FR-013, US1 AC11 |
| 14 | Cerrar el navegador con el acuse hecho y solo generación verificada | Al volver, retoma en **el paso de embeddings**; no se vuelve a pedir el acuse ni la llave ya verificada | FR-014, SC-015, US1 AC12 |
| 15 | Terminar u omitir el paso de correo | El onboarding del CV queda habilitado y la primera ejecución **no vuelve a mostrarse** | FR-015, US1 AC13 |

**Degradación explícita (FR-007.3, SC-016)**: configura un modelo que no garantice salida estructurada. Debe **enumerar qué funciones concretas quedan afectadas y por qué**, ofrecer cambiar de proveedor, y permitir continuar **solo** tras un acuse específico. Un `PUT` que intente avanzar sin ese acuse responde `409 DEGRADATION_ACKNOWLEDGEMENT_REQUIRED`.

**Sin proveedor de embeddings (FR-010)**: omite esa configuración y verifica que el onboarding del CV **sigue habilitado**. Solo se degradan funciones fuera de esta feature, y se dice cuáles.

**Rotación de credencial (SC-012, research R-24)**: con todo verificado, cambia la API key en la configuración y reinicia. El preflight de **esa** capacidad queda invalidado y se vuelve a pedir; el acuse y la otra capacidad **no** se pierden.

---

## 4. Recorrido manual — onboarding del CV (US2–US5)

| # | Acción | Resultado esperado | Requisito |
|---|---|---|---|
| 1 | Subir `golden_set/cv_es_basico.pdf` | Acuse inmediato con indicador de progreso; el estado avanza `queued → running → succeeded` | FR-019, US2 AC1 |
| 2 | Esperar a que termine | Entradas agrupadas por tipo, **todas** con origen `cv_seed`; perfil en `draft` | FR-024, FR-026, FR-029 |
| 3 | Recargar a media revisión | Vuelve al mismo punto del flujo con los cambios guardados | FR-034, US3 AC5 |
| 4 | Editar una entrada `cv_seed` | Mismo `id`, origen ahora `user_edited` | FR-025, FR-031, US3 AC1 |
| 5 | Guardar una entrada sin cambiar nada | El origen **no** cambia | research R-09 |
| 6 | Crear una entrada nueva | Origen `user_added` | FR-033, US3 AC2 |
| 7 | Eliminar una entrada | Desaparece y no reaparece al recargar | FR-032, US3 AC3 |
| 8 | Poner salario mínimo > máximo | Rechazo con mensaje en español | FR-036, US4 AC2 |
| 9 | Intentar confirmar con el cuestionario incompleto | Bloqueado, con la lista exacta de lo que falta | FR-039, US4 AC3 |
| 10 | Completar objetivos y confirmar | Perfil `complete`, versión 1 creada con marca de tiempo | FR-038, FR-040, US5 AC1 |
| 11 | Editar una entrada tras confirmar | Perfil **sigue** `complete`; aviso visible de cambios sin confirmar y su detalle | FR-042, FR-044, US5 AC4/AC7 |
| 12 | Consultar la versión 1 en el historial | Contenido íntegro del momento de la confirmación, **sin** los cambios posteriores | FR-041, FR-043, US5 AC5 |
| 13 | Confirmar los cambios pendientes | Versión 2 creada y vigente; ya no hay cambios pendientes | FR-040, US5 AC6 |

---

## 5. Recorridos de rechazo y salidas alternativas

| Archivo del golden set | Resultado esperado | Requisito |
|---|---|---|
| `cv_escaneado.pdf` (sin capa de texto) | Falla con `PDF_WITHOUT_TEXT_LAYER`, explica que v1 no procesa escaneos y ofrece **captura manual guiada**. Cero entradas creadas | FR-021, SC-009 |
| `factura.pdf` | Falla con `DOCUMENT_NOT_A_RESUME`. Cero entradas, perfil intacto | FR-020, SC-008 |
| `cv_corrupto.pdf` | Rechazo **síncrono** con `DOCUMENT_CORRUPT`; no se crea documento | FR-017 |
| `imagen.png` renombrada a `.pdf` | Rechazo con `UNSUPPORTED_FILE_TYPE` (detección por firma de bytes, no por extensión) | FR-017, research R-01 |
| Archivo de 12 MB | Rechazo con `FILE_TOO_LARGE` antes de leer el cuerpo completo | FR-016 |
| `cv_dos_columnas.pdf` | Entradas sin contenido intercalado entre columnas; lo que no se pudo estructurar llega marcado como incompleto | US2 AC5 |
| `cv_en_ingles.pdf` | Contenido en inglés sin traducir, `content_language = "en"`; la interfaz sigue en español | FR-027, US2 AC4 |
| `cv_minimo.pdf` | `DOCUMENT_TOO_SPARSE` con oferta de construir el perfil manualmente | Edge case |

**Captura manual guiada completa (SC-010)**: partiendo de un `PDF_WITHOUT_TEXT_LAYER`, crear entradas a mano, completar objetivos y confirmar. Debe llegarse a `complete` sin haber sembrado nada desde archivo (FR-022).

**Reintento (FR-023)**: con el parseo en curso, revoca la API key en la consola del proveedor. El trabajo termina con un código accionable que **apunta a la configuración de proveedores**, no a la captura manual. Crea una entrada a mano, restaura la llave y reintenta: la entrada manual **sigue ahí** y las sembradas se añaden sin duplicar.

**Un solo procesamiento activo**: subir un segundo CV mientras el primero procesa → `PARSE_JOB_ALREADY_ACTIVE`.

**Cierre del navegador**: cerrar la pestaña durante el procesamiento y volver a entrar → se ve el progreso o el resultado, sin re-subir.

**Directorio de datos desaparecido (ADR-007)**: con un perfil sembrado, mueve `VOKARA_DATA_DIR`. El perfil **sigue intacto**; el sistema informa que el archivo original ya no está y que no puede reprocesarse, **sin mostrar la ruta** en el mensaje.

---

## 6. Suite automatizada

```bash
cd backend
uv run ruff check . && uv run ruff format --check .
uv run mypy --strict app
uv run pytest tests/unit tests/integration tests/architecture -q --cov=app --cov-report=term-missing
uv run pytest tests/evals -q                      # requiere una API key en el entorno
cd ../frontend && npm run test && npm run build
```

**Umbrales que deben cumplirse** (todos bloqueantes en CI):

| Comprobación | Umbral | Requisito |
|---|---|---|
| ruff (lint + format) | 0 hallazgos | Art. VI |
| `mypy --strict` | 0 errores | Art. I |
| Cobertura en `app/services` y `app/domain` | ≥ 80% | Art. VI |
| Tasa de error por campo en evals | < 5% | SC-003 |
| Campos inventados en evals | 0 | FR-028, art. IV |
| Detección de no-CV y de PDF escaneado | 100% | SC-008, SC-009 |
| Drift del cliente TS | 0 diferencias | Art. I |
| Licencias de dependencias compatibles con AGPL-3.0 | 0 incompatibles | ADR-010 |

### Pruebas que merecen ejecución explícita

```bash
# ADR-008 — la instancia solo escucha en loopback (los DOS tests, ninguno sustituye al otro)
uv run pytest tests/integration/test_local_binding.py -q
# 1) todo `ports:` de docker-compose.yml (y del override) trae IP de host loopback:
#    falla con "8000:8000" y con "0.0.0.0:8000:8000".
# 2) settings.api_host resuelve SIEMPRE a loopback fuera de Docker.

# Art. II y art. XI — arquitectura
uv run pytest tests/architecture -q
# Falla si api/ importa db/, o si adapters/ importa services/.
# Falla si el nombre de un proveedor aparece FUERA de adapters/llm/.

# Art. X — ningún camino alterno llega a `complete`
uv run pytest tests/integration/test_confirmation_gate.py -q
# Intenta alcanzar `complete` por reintento de parseo, edición masiva, PATCH
# directo de objetivos y escritura de repositorio. Todos deben fallar. (SC-001)

# FR-049 — toda consulta acotada al candidate_id
uv run pytest tests/integration/test_candidate_scoping.py -q
# Siembra datos de DOS candidate_id y verifica que cada repositorio filtra.
# La API responde 404 —nunca 403— ante un recurso de otro propietario.

# FR-006, FR-007 — los cuatro resultados del preflight
uv run pytest tests/integration/test_preflight_outcomes.py -q
# Cada variante con su mensaje y su efecto: rechazada no avanza, cuota agotada
# no se presenta como inválida, sin garantía exige acuse, verificada registra
# la dimensión. Más provider_unreachable como caso distinto. (SC-012, SC-016)

# SC-013 — cero credenciales en ninguna superficie
uv run pytest tests/integration/test_no_credentials_leak.py -q
# Recorre una ejecución completa con los cuatro resultados de preflight y
# verifica 0 apariciones de la llave (ni fragmentos) en logs, trazas, mensajes
# de error, respuestas de la API y CUALQUIER tabla de la base.

# FR-045, FR-046 — PII fuera de logs y trazas
uv run pytest tests/integration/test_no_pii_in_logs.py -q
# Procesa un CV con nombre y teléfono sembrados y verifica que ninguna cadena
# aparece en los logs capturados ni en llm_call_logs.

# ADR-012 — el acotamiento por etiqueta es cumplimiento, no funcionalidad
uv run pytest tests/unit/test_email_label_scoping.py -q
# Verifica que NINGUNA consulta IMAP sale sin restricción de etiqueta.

# Migración reversible (DoD de la constitución)
uv run alembic upgrade head && uv run alembic downgrade base && uv run alembic upgrade head
```

---

## 7. Verificación de los criterios de éxito

| Criterio | Cómo se comprueba |
|---|---|
| **SC-001** — 100% de `complete` con confirmación explícita | `test_confirmation_gate.py` + auditoría: `SELECT count(*) FROM candidate_profiles WHERE state='complete' AND current_version_id IS NULL` debe dar **0** (el `CHECK` de la base ya lo hace imposible) |
| **SC-002** — 100% de entradas con `id` estable y origen | `NOT NULL` sobre `origin`, PK sobre `id` y test que verifica que el `id` sobrevive a una edición |
| **SC-003** — error de extracción < 5% | `pytest tests/evals`, métrica bloqueante |
| **SC-004** — p95 < 60 s de subida a entradas revisables | Las evals miden la duración por etapa contra el presupuesto de [research.md](./research.md) R-14 (objetivo p95 ≈ 45 s) |
| **SC-005** — una versión por confirmación, historial íntegro | Test que confirma dos veces y verifica `version_number` 1 y 2, contenido completo en ambas y trigger de inmutabilidad activo |
| **SC-006 / SC-007** — tiempo hasta confirmar, % que enriquece | **Observación directa o reporte voluntario** en la prueba de instalación asistida de la Fase 5. **Nunca por telemetría** (art. V). No verificables en CI |
| **SC-008** — 100% de rechazos accionables sin crear entradas | Casos de la §5 + test que verifica cero filas en `profile_entries` tras cada rechazo |
| **SC-009** — 100% de PDF escaneados detectados antes de extraer | Eval bloqueante + test unitario de la heurística con casos límite (PDF híbrido, CV minimalista) |
| **SC-010** — perfil `complete` sin archivo | Recorrido de captura manual guiada de la §5, automatizado en `test_manual_capture_flow.py` |
| **SC-011** — 100% de acuses registrados; ninguna vía permite subir sin él | Paso 3 de la §3 (curl directo) + test de gate de servidor |
| **SC-012** — 100% de credenciales pasan por preflight antes del primer uso real | `test_preflight_outcomes.py` + test de invalidación por rotación de credencial (research R-24) |
| **SC-013** — 0 credenciales en ninguna superficie | `test_no_credentials_leak.py`, recorriendo los cuatro resultados |
| **SC-014** — 80% completa la primera ejecución sin ayuda, mediana < 10 min | Prueba de instalación asistida de la Fase 5, con personas y cronómetro. No verificable en CI |
| **SC-015** — 100% de primeras ejecuciones interrumpidas retoman en el paso pendiente | Paso 14 de la §3, automatizado en `test_setup_resume.py` |
| **SC-016** — 100% de degradaciones enumeran funciones afectadas antes de continuar | `test_preflight_outcomes.py`, variante `capability_unverified`: `affected_features` no vacío y acuse obligatorio |

---

## 8. Antes de abrir el PR

- [ ] `ruff`, `mypy --strict`, tests, evals y build del front en verde localmente
- [ ] Cliente TS regenerado y commiteado
- [ ] Migración Alembic con `downgrade` **probado**, no solo escrito
- [ ] `.env.example` **de la raíz** actualizado si se añadió alguna variable; sigue sin existir `infra/.env`
- [ ] **Todo puerto nuevo publicado en el Compose lleva prefijo `127.0.0.1:`** y entra en el alcance de `test_local_binding.py` (ADR-008)
- [ ] Ningún mensaje de error nuevo fuera de [contracts/errors.md](./contracts/errors.md), y todos dicen qué pasó, por qué y el siguiente paso
- [ ] Ningún log, traza ni mensaje con contenido del documento (FR-045) ni con credenciales (FR-008, FR-013)
- [ ] **Ningún nombre de proveedor fuera de `adapters/llm/`** (art. XI); ningún `temperature` en `services/` ni en la firma de un puerto (ADR-003)
- [ ] Ningún nombre de modelo en una constante de código: van en configuración con override por variable de entorno (ADR-011)
- [ ] Golden set sin material de usuarios reales (FR-047)
- [ ] `docker compose up` desde cero, en una máquina limpia, sin editar archivos a mano (roadmap §11.1)
- [ ] Rama `001-candidate-onboarding`, nunca `main`; commits en inglés (art. IX)
