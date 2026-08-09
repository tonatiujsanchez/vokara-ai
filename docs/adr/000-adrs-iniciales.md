# Vokara — ADRs iniciales y setup multiplataforma (Windows + macOS)

Copiar cada ADR a `docs/adr/` como archivo independiente antes de ejecutar
`/speckit.constitution`.

---

# ADR-001 — Autenticación con JWT propio

**Estado:** Aceptado · **Fecha:** 2026-07

## Contexto
Vokara maneja CVs, datos personales y materiales generados. Necesita registro,
login, sesiones persistentes en web y recuperación de contraseña. El equipo es
pequeño (2–3 personas) y quiere evitar dependencias de proveedor y costos fijos.

## Decisión
Implementar autenticación propia con JWT en FastAPI:
- **Hash de contraseñas:** Argon2id (`argon2-cffi`). No bcrypt, no SHA.
- **Access token:** JWT firmado (HS256 con secreto rotable, o RS256 si más
  adelante hay más de un servicio), vida corta (15 min), sin datos sensibles en
  el payload — solo `sub`, `exp`, `iat`, `jti`.
- **Refresh token:** opaco, almacenado hasheado en Postgres, vida 30 días,
  **con rotación** (cada uso emite uno nuevo e invalida el anterior) y
  detección de reuso → revoca toda la familia de tokens del usuario.
- **Revocación:** lista de `jti` revocados en Redis con TTL igual al `exp`.
- **Transporte:** refresh token en cookie `httpOnly`, `Secure`, `SameSite=Lax`;
  access token en memoria del frontend (nunca en localStorage).
- **Verificación de correo y reset de contraseña:** tokens de un solo uso con
  expiración corta, enviados por el adapter de correo.
- **Rate limiting** en `/auth/login`, `/auth/register` y `/auth/reset` con
  backoff por IP y por cuenta.

## Alternativas descartadas
- **Clerk / Auth0:** menos trabajo inicial (~4–6 días ahorrados) y flujos
  probados, pero costo mensual desde ~$25 y dependencia de proveedor para un
  componente crítico. Descartado por preferencia de control y costo.
- **OAuth social como único método:** descartado en v1; se puede sumar
  "Continuar con Google" más adelante sin romper este diseño.

## Consecuencias
- **Costo real:** ~4–6 días de desarrollo repartidos en la feature 001, en
  código donde los errores son de seguridad, no de UX. Debe reflejarse en el
  plan y en las tareas, no aparecer como sorpresa.
- Requiere tests de seguridad específicos: rotación de refresh, detección de
  reuso, expiración, revocación al eliminar cuenta.
- Requiere el adapter de correo funcionando antes de poder verificar cuentas
  (dependencia a considerar en el orden de tareas).
- Si más adelante se agrega app móvil, el esquema de cookie debe revisarse
  (tokens en storage seguro nativo).

---

# ADR-002 — Despliegue en VPS Hostinger con Docker Compose

**Estado:** Aceptado · **Fecha:** 2026-07

## Contexto
El equipo ya opera un VPS Hostinger (KVM 2) y tiene experiencia con Docker.
Vokara en v1 tendrá decenas, no miles, de usuarios concurrentes.

## Decisión
Desplegar con **Docker Compose sobre el VPS Hostinger existente**. Servicios:
`api` (FastAPI/uvicorn), `worker` (Celery), `beat` (Celery Beat), `postgres`
(16 + pgvector), `redis`, y `caddy` o `nginx` como reverse proxy con TLS
automático. Frontend servido como estático desde el mismo proxy.

Ambientes: `dev` local (Compose) → `staging` y `prod` en el VPS, separados por
proyecto Compose y base de datos distintas. Despliegue por CI vía SSH
(GitHub Actions → `docker compose pull && up -d` con migraciones Alembic
previas).

## Alternativas descartadas
- **Kubernetes** (aunque el equipo lo conoce por ALPHA): sobredimensionado para
  la escala de v1; añade superficie operativa sin beneficio. Se reevalúa cuando
  haya necesidad real de escalado horizontal o multi-tenant pesado.
- **PaaS (Railway/Fly/Render):** menos operación, pero costo adicional teniendo
  ya un VPS pagado y capacidad ociosa.

## Consecuencias
- El equipo es responsable de backups, monitoreo y parches del sistema.
  **Backup diario de Postgres con restauración probada antes del lanzamiento**
  (probada, no solo configurada).
- Recursos limitados del KVM 2: vigilar consumo de Postgres + Redis + workers.
  Si staging y prod conviven en la misma máquina, limitar recursos por servicio
  en Compose para que staging nunca degrade prod.
- Escalar significa cambiar de plan de VPS o migrar; documentar el umbral
  (p. ej. > 500 usuarios activos o p95 de API > 1s sostenido) que dispara la
  reevaluación.

---

# ADR-003 — Google Gemini como proveedor LLM inicial

**Estado:** Aceptado · **Fecha:** 2026-07

## Contexto
Vokara usa LLM para: parseo de CV, parseo de JD, explicación de matches,
generación de materiales, verificación de veracidad y simulador de entrevistas.
Además requiere embeddings para el sub-score semántico del matching.

## Decisión
Usar **Google Gemini** como proveedor inicial, detrás del adapter
`adapters/llm/` definido por la constitución (art. 2). Integración vía
`langchain-google-genai` para aprovechar `with_structured_output` con esquemas
Pydantic (constitución art. 3).

Asignación por tarea (revisable con datos de costo real):
- Clasificación y parseo estructurado → modelo rápido/económico de la familia.
- Generación de materiales y simulador → modelo de mayor capacidad.
- Embeddings → modelo de embeddings de Google.

## Alternativas descartadas
- **OpenAI:** el equipo ya lo conoce por ALPHA, pero Gemini ofrece mejor
  relación costo/capacidad para el volumen esperado y un tier gratuito útil
  durante el desarrollo. Sigue siendo el fallback natural.
- **Modelos locales:** descartados en v1 por la carga de operación en un VPS
  compartido.

## Consecuencias — atención al punto de embeddings
- **La dimensión del embedding se filtra al esquema de la base de datos.** La
  columna `vector(N)` de pgvector tiene dimensión fija; cambiar de proveedor de
  embeddings NO se resuelve solo cambiando el adapter: exige re-embeber todos
  los perfiles y vacantes.
  **Mitigación obligatoria desde la primera migración:** almacenar
  `embedding_model` (texto) y `embedding_dim` (int) junto a cada vector, y
  permitir convivencia de dos modelos durante una migración (columna adicional
  o tabla de embeddings separada por modelo).
- Toda llamada al LLM se traza con costo, latencia y versión de prompt
  (constitución art. 8), para poder comparar proveedores con datos reales.
- Las evals del golden set deben poder correrse contra más de un proveedor:
  son la única forma objetiva de justificar un cambio futuro.
- Verificar disponibilidad regional y términos de uso de datos (que los datos
  de usuarios no se usen para entrenamiento) antes de la beta con usuarios
  reales.

---

# ADR-004 — Taxonomía de skills: lista propia curada en v1

**Estado:** Aceptado · **Fecha:** 2026-07

## Contexto
El motor de matching compara skills del perfil contra requisitos de la vacante.
Sin normalización, la comparación literal falla de forma sistemática:

| CV | Vacante | Literal | Correcto |
|---|---|---|---|
| ReactJS | React.js | ✗ | ✓ |
| Postgres | PostgreSQL | ✗ | ✓ |
| JS | JavaScript | ✗ | ✓ |
| Desarrollo web | Web development | ✗ | ✓ |
| React Native | React | ✗ | ✗ (correcto: NO son la misma) |

Un falso negativo aquí significa que el candidato pierde una vacante donde
encajaba: es un fallo directo del propósito del producto.

## Decisión
Construir una **lista propia curada** de 200–300 skills relevantes al mercado
objetivo (tech, administrativo, ventas, marketing en México), versionada en el
repo como YAML y cargada a Postgres por migración.

Esquema por skill:
```yaml
- id: react
  canonical: React
  category: frontend
  aliases: [reactjs, react.js, react 18, react js]
  implies: [javascript]        # relaciones simples, opcionales
```

Reglas de resolución en el matcher, en este orden:
1. Coincidencia exacta con `canonical` o `aliases` (normalizado: minúsculas,
   sin acentos, sin puntuación).
2. Si no hay coincidencia → similitud por embeddings contra el catálogo, con
   umbral; por encima del umbral se resuelve, por debajo se conserva como
   "skill libre" sin normalizar.
3. Las skills libres que aparecen con frecuencia se revisan periódicamente y se
   promueven al catálogo (proceso manual, con métrica de cuántas hay).

Los alias incluyen variantes en **español e inglés**, porque las vacantes
mexicanas mezclan ambos idiomas.

## Alternativas descartadas
- **ESCO** (taxonomía europea, gratuita, multilingüe con español, ~13,900
  skills): completa y bien mantenida, pero pesada para v1 y con vocabulario
  sesgado al mercado europeo. Se contempla importarla después: el esquema
  (`skill_id` + alias) es compatible, así que migrar no rompe el modelo.
- **O\*NET:** solo inglés, orientado al mercado estadounidense.
- **Solo embeddings sin catálogo:** más simple, pero elimina la explicabilidad
  del matching (constitución art. 3) y produce falsos positivos como
  React Native ≈ React.

## Consecuencias
- ~1 día de trabajo inicial de curación + mantenimiento periódico ligero.
- El catálogo es un artefacto de producto, no de código: cambios revisados en PR.
- Las evals de matching deben incluir casos trampa (React Native vs React,
  Java vs JavaScript) para detectar regresiones al ampliar alias.

---

# Setup multiplataforma: Windows 11 + macOS

El proyecto se desarrolla alternando dos máquinas (Windows en casa, Mac en
oficina). Estas decisiones evitan la clase de bugs que solo aparecen "en la
otra máquina".

## Regla principal: en Windows, desarrollar dentro de WSL2

No desarrollar en Windows nativo. Con **WSL2 + Ubuntu**, ambas máquinas son
entornos Unix: mismas rutas, mismos scripts bash de Spec Kit, mismo
comportamiento de Docker, mismos permisos de archivos. La alternativa
(PowerShell + scripts `.ps1` en Windows, zsh en Mac) duplica el mantenimiento
de scripts y genera fricción constante.

```powershell
# Windows 11, PowerShell como administrador
wsl --install -d Ubuntu
```

Después, instalar Docker Desktop con el backend WSL2 activado, y clonar el
repo **dentro del sistema de archivos de WSL** (`~/dev/vokara`), nunca en
`/mnt/c/...` — el rendimiento de I/O en `/mnt/c` es malo y rompe el hot-reload.

Al inicializar Spec Kit, usar scripts bash en ambas máquinas (`--script sh`
si la versión del CLI lo pide).

## `.gitattributes` — desde el primer commit

Sin esto, Git convierte los archivos a CRLF en Windows y los scripts fallan
dentro de contenedores Linux con errores incomprensibles
(`bad interpreter: No such file or directory`).

```gitattributes
* text=auto eol=lf
*.png binary
*.jpg binary
*.pdf binary
*.docx binary
```

```bash
git config --global core.autocrlf false   # en ambas máquinas
```

## Trampa de mayúsculas/minúsculas

macOS usa APFS **case-insensitive** por defecto; Linux (contenedores, CI, VPS)
es **case-sensitive**. Un `from app.Services import x` funciona en la Mac y
truena en producción. Mitigaciones:
- CI corre en Linux y detecta el problema antes del merge (obligatorio).
- Convención estricta: módulos y carpetas en `snake_case` minúsculas.

## Versiones fijadas (idénticas en ambas máquinas)

| Herramienta | Mecanismo |
|---|---|
| Python | `.python-version` (uv lo respeta) |
| Dependencias Python | `uv.lock` commiteado |
| Node | `.nvmrc` (o Volta) |
| Dependencias Node | `package-lock.json` commiteado |
| Servicios | `docker-compose.yml` con tags fijos (`postgres:16.4`, no `latest`) |

Regla: **nada se instala global**. Todo corre dentro de Compose o de entornos
gestionados por uv/nvm.

## Secretos y `.env`

`.env` nunca se commitea; `.env.example` sí, con todas las claves y valores
dummy. Los valores reales se sincronizan entre máquinas por gestor de
contraseñas (1Password/Bitwarden), no por chat ni correo. Al agregar una
variable nueva, actualizar `.env.example` en el mismo commit — es la única
forma de que la otra máquina se entere.

## Rendimiento de Docker en Mac

Los bind mounts en macOS son lentos. Para dependencias, usar volúmenes
nombrados en vez de montar desde el host:

```yaml
volumes:
  - ./backend:/app
  - venv:/app/.venv          # named volume, no bind mount
  - node_modules:/app/node_modules
```

## Disciplina de cambio de máquina

1. Antes de cerrar en una máquina: `git add -A && git commit && git push`.
   Incluye WIP si hace falta (`git commit -m "wip: ..."`), rebase después.
2. Al abrir en la otra: `git pull`, luego `uv sync` y `npm ci` (las
   dependencias pueden haber cambiado), y `docker compose up -d --build`.
3. Nunca dejar migraciones Alembic sin commitear: una migración local no
   pusheada convierte a la otra máquina en una base de datos divergente.
4. Trabajar siempre en la rama de la feature activa de Spec Kit
   (`00X-nombre`), nunca directo en `main`.

## Historial de Claude Code entre máquinas

Las sesiones de Claude Code viven en `~/.claude/` y no se sincronizan solas.
Como el contexto real del proyecto está en el repo (constitución, specs, plan,
tasks, `CLAUDE.md`), perder el historial de chat no es crítico — ese es
justamente uno de los beneficios de SDD. Si aun así quieren continuidad de
sesiones entre equipos, `claude-sync` cubre ese caso.

## Checklist de arranque en la segunda máquina

- [ ] WSL2 + Ubuntu (solo Windows) con el repo dentro del FS de WSL
- [ ] Docker Desktop con backend WSL2 / Docker Desktop en Mac
- [ ] `git config --global core.autocrlf false`
- [ ] uv instalado y `uv tool install specify-cli`
- [ ] Claude Code instalado y abriendo en la raíz del repo
- [ ] `.env` poblado desde el gestor de contraseñas
- [ ] `docker compose up -d` levanta y los tests pasan en verde
