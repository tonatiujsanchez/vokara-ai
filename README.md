# Vokara · Your AI Job Scout

> **Vokara** (*vocation* + *radar*) — Encuentra oportunidades que realmente
> encajan contigo.

Agente de búsqueda de empleo para profesionistas en México: descubre vacantes
donde el candidato encaja de verdad, prepara los materiales de aplicación sin
inventar nada, entrena la entrevista y acompaña el cierre.

Documentación del proyecto:

- Producto (fuente de verdad): [`docs/product/roadmap.md`](docs/product/roadmap.md)
- Decisiones de arquitectura: [`docs/adr/`](docs/adr/)
- Reglas no negociables: [`.specify/memory/constitution.md`](.specify/memory/constitution.md)

## Instalación

Vokara se instala en tu computadora, no se despliega en ningún servidor
(ADR-009). Todo lo que necesitas es Docker.

### Requisitos

| Sistema | Qué instalar |
|---|---|
| **Windows** | WSL2 con Ubuntu + Docker Desktop **con la integración de WSL2 activada** en Settings → Resources → WSL Integration |
| **macOS** | Docker Desktop |
| **Linux** | Docker Engine + el plugin `docker compose` |

**Docker Compose v2.20 o superior.** El `docker-compose.yml` usa
`env_file: [{ path: ../.env, required: false }]`, y el atributo `required`
existe desde la v2.20.0; con una versión anterior el arranque falla. Verificado
sobre Docker 29.1.3 y Compose v2.40.3.

```bash
docker compose version    # debe imprimir v2.20.0 o superior
```

**En Windows, clona el repositorio dentro del sistema de archivos de WSL**
(`~/dev/vokara`), nunca en `/mnt/c/...`: ahí el I/O es lento y rompe la recarga
en caliente (ADR-000). Y en cualquier máquina de desarrollo:

```bash
git config --global core.autocrlf false
```

No hace falta Python ni Node: viven dentro de las imágenes.

### Levantar Vokara

```bash
git clone <url-del-repo> vokara
cd vokara
docker compose -f infra/docker-compose.yml up -d
```

Eso es todo. **No hay ningún `.env` que copiar ni editar**, no hay migraciones
que ejecutar y no hay ningún archivo que tocar a mano.

El primer arranque descarga las imágenes de Postgres y Redis y construye la del
backend: tarda varios minutos. Los siguientes tardan segundos.

### Verificar que quedó bien

```bash
docker compose -f infra/docker-compose.yml ps
curl -s localhost:8000/api/v1/health
```

Cuatro servicios —`api`, `worker`, `postgres` y `redis`— y esta respuesta:

```json
{"status":"ok","database":"ok","migration_revision":"0001"}
```

`migration_revision` es la revisión que la instancia tiene aplicada, leída de la
propia base de datos. Que aparezca significa que **las migraciones se aplicaron
solas al arrancar**: nunca ejecutas un comando de Alembic, ni al instalar ni al
actualizar.

En `ps`, el puerto de `api` debe aparecer como `127.0.0.1:8000->8000/tcp`.
`postgres` y `redis` no publican ningún puerto al host: se alcanzan solo desde
la red interna de Docker. Si ves otra cosa, lee la sección siguiente antes de
seguir.

### El `.env`

**Vokara arranca sin `.env`.** Ninguna variable hace falta para el primer
arranque, y las API keys de tu proveedor de IA se pedirán en la propia
aplicación, no en un archivo.

Si algún día necesitas desviarte de los valores por defecto —cambiar el
directorio donde se guardan tus CVs, fijar otro nombre de modelo—, copia la
plantilla y edita solo lo que quieras cambiar:

```bash
cp .env.example .env
```

El `.env` vive **únicamente en la raíz del repositorio**. No existe
`infra/.env`, y no debe existir: dos ubicaciones para la misma llave son la
causa más previsible del "a mí no me toma la configuración". El `.env` nunca se
commitea; `.env.example` sí, y documenta cada variable disponible.

### Qué está disponible hoy

Esta instalación levanta la API en `127.0.0.1:8000`. La interfaz web del
onboarding está en construcción; mientras tanto, la pantalla de estado se ve
levantando además el archivo de desarrollo, que añade el servidor de Vite en
`127.0.0.1:5173`:

```bash
docker compose -f infra/docker-compose.yml -f infra/docker-compose.override.yml up -d
```

Los dos `-f` son necesarios: el archivo de desarrollo no se carga solo.

### Detener y limpiar

```bash
# Detener. Tus datos se conservan.
docker compose -f infra/docker-compose.yml down

# Ver qué está pasando dentro
docker compose -f infra/docker-compose.yml logs -f api

# Detener Y BORRAR tus datos: elimina los volúmenes vokara_vokara_data
# (tus CVs originales) y vokara_vokara_postgres (tu perfil). No hay deshacer.
docker compose -f infra/docker-compose.yml down -v
```

Desinstalar Vokara es exactamente eso: `down -v` y borrar el directorio del
repositorio. No queda nada en ningún otro sitio, porque nunca hubo nada en
ningún otro sitio.

### Si algo falla

| Lo que ves | Qué pasa |
|---|---|
| `The command 'docker' could not be found in this WSL 2 distro` | Docker Desktop está cerrado o su integración con WSL2 desactivada. Actívala en Settings → Resources → WSL Integration |
| `bind: address already in use` en el puerto 8000 | Otro programa ocupa el puerto. Ciérralo, o cambia el mapeo **conservando el prefijo `127.0.0.1:`** |
| `api` reinicia en bucle | `docker compose -f infra/docker-compose.yml logs api` dice por qué. Si la base tardó en levantar, el arranque reintenta solo |
| El primer arranque parece colgado | Está descargando imágenes. `docker compose -f infra/docker-compose.yml logs -f` lo muestra |

## Vokara solo escucha en tu máquina

Vokara corre localmente y **no tiene cuentas ni contraseña**: una instalación,
una persona. Quien puede abrir la aplicación tiene acceso completo a tu perfil,
tus CVs y los materiales generados.

Por eso los puertos están publicados únicamente en `127.0.0.1` (loopback), es
decir, alcanzables solo desde tu propia computadora. **No cambies esos mapeos en
`docker-compose.yml`.** Exponer Vokara a la red sin autenticación pondría tus
datos personales al alcance de cualquiera en esa red.

Dos advertencias concretas si tienes la tentación de moverlo:

- Un mapeo como `"8000:8000"` (sin la IP) **publica en todas las interfaces**,
  no solo en la tuya.
- **El firewall de tu sistema no te protege de eso.** Docker escribe sus propias
  reglas de red, que se aplican antes que las de `ufw` o `firewalld`: un puerto
  publicado por Docker queda abierto aunque creas tener el firewall cerrado.

## Licencia

Copyright (C) 2026 Vokara contributors

Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo los
términos de la **GNU Affero General Public License** publicada por la Free
Software Foundation, en su **versión 3** o (a tu elección) cualquier versión
posterior.

Este programa se distribuye con la esperanza de que sea útil, pero **SIN NINGUNA
GARANTÍA**; ni siquiera la garantía implícita de COMERCIABILIDAD o IDONEIDAD
PARA UN PROPÓSITO PARTICULAR. Consulta la GNU Affero General Public License para
más detalles.

Deberías haber recibido una copia de la GNU Affero General Public License junto
con este programa (ver [`LICENSE`](LICENSE)). Si no, visita
<https://www.gnu.org/licenses/>.

La AGPL-3.0 añade una condición sobre la GPL: si modificas Vokara y lo ofreces a
usuarios a través de una red, debes poner el código fuente modificado a
disposición de esos usuarios. El razonamiento completo de la elección está en
[ADR-010](docs/adr/010-license.md).
