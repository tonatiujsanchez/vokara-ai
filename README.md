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
