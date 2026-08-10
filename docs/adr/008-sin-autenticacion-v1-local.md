# ADR-008 — Sin autenticación en v1 local: una instancia, un usuario

**Estado:** Aceptado · **Fecha:** 2026-08 · **Reemplaza a:** ADR-001

---

## Contexto

El ADR-001 diseñó autenticación propia con JWT: Argon2id, access token de vida
corta, refresh opaco con rotación y detección de reuso, revocación por `jti` en
Redis, verificación de correo y recuperación de contraseña. Un diseño sólido que
costaba **4–6 días de desarrollo en código donde los errores son de seguridad,
no de UX**, según su propia estimación.

Con el pivote a ejecución local (constitución v2.0.0), ese trabajo pierde
sujeto. Cada persona clona el repositorio y lo ejecuta en su máquina, con sus
datos y su API key. **No hay usuarios que distinguir entre sí:** la instancia
sirve a una sola persona, la misma que la instaló, y la frontera de seguridad
real no es un token sino la sesión del sistema operativo. Autenticar sería pedirle
a alguien que se identifique ante su propia computadora.

## Decisión

**Vokara v1 no tiene autenticación.** Sin registro, sin login, sin sesiones, sin
recuperación de contraseña. La API asume que quien la llama es el propietario de
la instalación, porque escucha únicamente en la interfaz local.

**Se conserva `candidate_id` en el modelo de datos**, con un **valor local
fijo** asignado en la migración inicial. No es un vestigio: es lo que hace que
todas las queries de repositorio nazcan acotadas por propietario desde la
primera línea de código.

La diferencia práctica es exactamente esta:

```python
# Con candidate_id desde el día 1 — una versión hospedada añade auth encima
def list_matches(self, candidate_id: CandidateId) -> list[Match]: ...

# Sin él — una versión hospedada reescribe todos los repositorios y tests
def list_matches(self) -> list[Match]: ...
```

En el primer caso, añadir autenticación después significa cambiar **de dónde
sale** el `candidate_id`: hoy de una constante local, mañana del token. La firma
de repositorios y servicios no cambia, y las queries ya filtran. En el segundo,
significa reescribir la capa de datos entera con el producto en producción. El
costo de conservarlo hoy es un parámetro; el de no conservarlo es una migración.

Ese `candidate_id` **nunca lo envía el cliente**: lo resuelve la capa de API a
partir de la configuración local, igual que mañana lo resolvería del token.
Aceptarlo del cliente reintroduciría exactamente el fallo que esta disciplina
busca prevenir.

### Mitigación obligatoria: la instancia solo escucha en loopback

Sin autenticación, **el único control de acceso de Vokara es dónde escucha**. Si
el puerto sale de la máquina, no hay nada detrás: cualquiera en esa red lee el
perfil, los CVs y los materiales generados. Esto no es un criterio de revisión
de PR sino un **requisito verificable**, y se cumple con tres piezas.

**1. Mapeos de puerto explícitos en `docker-compose.yml`.**

```yaml
services:
  api:
    ports:
      - "127.0.0.1:8000:8000"   # NUNCA "8000:8000"
  web:
    ports:
      - "127.0.0.1:5173:5173"   # NUNCA "5173:5173"
```

La forma corta `"8000:8000"` **publica en todas las interfaces**: Docker asume
`0.0.0.0` cuando se omite la IP de host. El error es clásico porque parece
inofensivo y porque **el firewall del host no lo detiene**: Docker inserta sus
propias reglas en la cadena `DOCKER` de la tabla `nat` de iptables, que se
evalúan antes que las reglas de `INPUT` donde viven `ufw` o `firewalld`. El
resultado es un puerto abierto a la red local en una máquina cuyo firewall el
usuario cree que está cerrado. Un `ufw deny 8000` no protege un puerto
publicado por Docker.

La regla aplica a **todo** puerto publicado, no solo a estos dos. `postgres` y
`redis` no deben publicarse en absoluto —los servicios se alcanzan entre sí por
la red interna de Compose—; si alguien los publica temporalmente para depurar,
también con prefijo `127.0.0.1:`.

**2. Test de integración que falle si el host configurado no es loopback.**

```python
# tests/integration/test_local_binding.py
def test_compose_publishes_only_on_loopback() -> None:
    """Todo puerto publicado en docker-compose.yml fija una IP de host loopback."""
    # Por cada `ports:` de cada servicio: la entrada debe traer IP de host
    # explícita, y ipaddress.ip_address(host_ip).is_loopback debe ser True.
    # Falla tanto con "8000:8000" (sin IP) como con "0.0.0.0:8000:8000".

def test_api_host_setting_resolves_to_loopback() -> None:
    """El host configurado para uvicorn fuera de Docker resuelve a loopback."""
    # socket.getaddrinfo(settings.api_host, None) → TODAS las direcciones
    # resueltas cumplen is_loopback. "localhost" pasa (127.0.0.1 y ::1);
    # "0.0.0.0" falla (is_unspecified, no is_loopback).
```

**Los dos tests son necesarios y ninguno sustituye al otro**, por una asimetría
que conviene tener presente: **dentro del contenedor, uvicorn DEBE escuchar en
`0.0.0.0`**, o el proxy de Docker no puede alcanzarlo y la aplicación no
responde. Es decir, en el despliegue con Compose la protección no la da el bind
de la aplicación —que por fuerza es abierto— sino **exclusivamente el mapeo de
puertos**. El segundo test cubre el otro caso: ejecutar la API directamente en
la máquina, sin contenedor, donde sí es el bind lo que protege. Escribir solo el
test del bind y aplicarlo al contenedor rompería el arranque; escribir solo el
del compose dejaría sin cubrir el modo local.

**3. Nota explícita en el README** sobre qué significa esto para el usuario (ver
Impacto).

## Alternativas descartadas

**Código de bloqueo local (PIN o contraseña al abrir la app).** Descartado por
la razón que lo hace tentador: *parece* seguridad. Sería un **bloqueo de UI, no
cifrado** — los datos siguen en claro en el disco (ADR-007) y la base de datos
sigue abierta en el puerto de Postgres. Cualquiera con acceso al sistema de
archivos lee todo sin pasar por la pantalla de bloqueo. El problema no es que
proteja poco, es que **comunica una protección que no existe**: un usuario que
ve un candado asume que sus CVs están protegidos y decide en consecuencia
—prestar el equipo, no activar el cifrado de disco—. Una falsa sensación de
seguridad es peor que la ausencia declarada de seguridad, porque cambia el
comportamiento del usuario en la dirección equivocada. La protección real en
local es el cifrado de disco del sistema operativo, y el README lo recomienda
en vez de simularlo.

**Mantener el ADR-001 tal cual "por si acaso".** 4–6 días de desarrollo en
código de seguridad, más su superficie de mantenimiento y sus tests, para
proteger a un usuario de sí mismo. Contra el art. VII y contra el criterio de
fricción de instalación: obligaría a registrarse antes de usar un programa que
ya está corriendo en la propia máquina.

**Multiusuario local (varias cuentas en una instancia).** Ningún caso de uso lo
pide: quien comparte computadora tiene cuentas del sistema operativo, que ya
separan datos mejor de lo que lo haría Vokara. Añadiría toda la complejidad del
ADR-001 sin su justificación.

## Consecuencias

**Positivas**

- Se recuperan 4–6 días de desarrollo y desaparece toda una superficie de
  seguridad que mantener y testear.
- La primera ejecución es inmediata: clonar, configurar la API key, usar. Sin
  registro ni verificación de correo entre el usuario y el producto (art. VII).
- El adapter de correo deja de ser prerrequisito del onboarding —lo era solo
  para verificar cuentas (ADR-001)—, lo que desbloquea el orden de tareas de la
  feature 001 y deja el correo como capacidad opcional (ADR-012).
- Una versión hospedada futura añade auth **encima** del modelo de datos
  existente, sin reescribir repositorios.

**Costos y riesgos**

- **La API no debe exponerse a la red.** Es el riesgo central de esta decisión:
  sin autenticación, cualquiera con acceso de red a la instancia tiene acceso
  total. Se mitiga con las tres piezas verificables de la sección "Mitigación
  obligatoria" —mapeos `127.0.0.1:` en Compose, tests de integración y nota en
  el README—. Un puerto publicado en `0.0.0.0` es un bug de seguridad, no un
  detalle de configuración, y los tests están para que no dependa de que alguien
  lo note en revisión.
- Esos tests protegen una propiedad de configuración, no de código, así que hay
  que sostenerlos: cualquier servicio nuevo que publique un puerto debe entrar
  en su alcance. Un `docker-compose.override.yml` para desarrollo queda sujeto a
  la misma regla.
- El `candidate_id` fijo es una convención que hay que sostener con disciplina:
  filtrar por él en cada query aunque hoy siempre devuelva lo mismo. Un
  repositorio que lo omita "porque da igual" es deuda que solo se cobra el día de
  la migración a hospedado, cuando ya no hay forma barata de pagarla. Los tests
  de repositorio deben verificar el filtrado con al menos dos `candidate_id`
  para que la disciplina sea ejecutable y no un acuerdo verbal.
- Ninguna feature puede asumir "el usuario actual" implícito fuera de la capa de
  API: servicios y repositorios reciben `candidate_id` explícito.

## Impacto en artefactos existentes

- **ADR-001:** marcado Superseded, conservado como diseño de referencia para una
  eventual versión hospedada.
- **`specs/001-candidate-onboarding/`:** desaparecen registro, login, verificación
  de correo y rate limiting de `/auth/*`; el `candidate_id` deja de tomarse del
  token y pasa a resolverse de configuración local. El plan y las tareas
  requieren revisión.
- **`docker-compose.yml` (por crear):** todo puerto publicado con prefijo
  `127.0.0.1:`; `postgres` y `redis` sin publicar.
- **`tests/integration/test_local_binding.py` (por crear):** los dos tests de la
  sección "Mitigación obligatoria". Van en el mismo PR que el Compose, no
  después.
- **README:** nota de que Vokara solo escucha en la máquina del usuario y qué
  implicaría exponerlo (añadida).
- **ADR-006 (SPA React + Vite):** su razón nº 3 —incompatibilidad con el modelo
  de tokens del ADR-001— desaparece con este ADR. La decisión **se sostiene** por
  sus otras tres razones (sin necesidad de SSR/SEO, evitar un segundo servidor
  con lógica, costo de recursos), que el pivote a local refuerza en vez de
  debilitar. No requiere reemplazo, sí una nota.
