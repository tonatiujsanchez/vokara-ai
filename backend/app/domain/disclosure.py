"""The disclosure of article V, versioned, as a fact of the domain (FR-001).

Article V asks for this text «en texto claro y en la propia pantalla» on the
first run, and forbids burying it in secondary documentation or taking it as
known. So the text lives here, complete, and travels whole to the screen: the
endpoint returns the body, not a link to it.

**Why it carries a version.** Knowing *what* someone accepted matters as much as
knowing that they accepted. A future feature that sends something new to the
provider — a job description, the profile — changes what this text promises, and
versioning is what lets that change demand a new acknowledgement instead of
being covered by an old yes that said something else (research R-29). It is also
what sustains FR-048: enabling real material for evals can never sneak in by
editing this text, because the accepted version is on record.

The version is therefore **part of the text**, not decoration: editing the body
without moving the version is a bug, and `tests/unit/test_disclosure_version.py`
fails when it happens.
"""

from __future__ import annotations

from dataclasses import dataclass

# The date this wording entered the repository. Any edit to the body below —
# even one word — takes a new version, because an acknowledgement of the old one
# no longer describes what the user is agreeing to.
DISCLOSURE_VERSION = "2026-08-17"

DISCLOSURE_BODY_MD = """\
## Antes de empezar: qué pasa con tus datos

Vokara corre **en tu computadora**. No hay servidor nuestro, no hay cuenta que
crear y no hay base de datos donde guardemos nada tuyo.

### Lo que se queda aquí

Tu CV original, tu perfil maestro, tus entradas, los materiales que generes y tu
historial **no salen de esta máquina**. Viven en el directorio de datos de esta
instalación y en la base de datos que corre junto a ella.

### La única excepción: tu proveedor de IA

Vokara necesita un proveedor de IA para leer tu CV y armar tu perfil, y ese
proveedor **lo eliges tú** y lo pagas con tu propia API key. Lo que sale de tu
máquina es únicamente lo que se le envía a él, y esto es exactamente qué y
cuándo:

- **El contenido de tu CV**, íntegro, cuando lo subes y se procesa para sembrar
  tu perfil.
- **Un fragmento de prueba**, cuando verificamos tu API key al configurarla.

En versiones siguientes se sumarán la descripción de una vacante al analizarla y
tu perfil al generar materiales para postularte. Cuando eso ocurra, este texto
cambiará y te lo volveremos a mostrar: nada nuevo sale de tu máquina sin que lo
sepas antes.

Antes de configurarlo verás el costo estimado de cada proveedor, y tu API key se
guarda en la configuración local de esta instalación: **nunca** en la base de
datos, nunca en los registros, nunca en un mensaje de error.

### Vokara no nos envía nada a nosotros

Cero telemetría, cero analítica, cero reportes de error a terceros. No sabemos
que instalaste Vokara, ni cuándo lo usas, ni qué falla. Si algo se rompe, lo
verás en tu pantalla de diagnóstico y el canal para contarlo es un issue que
abras tú.

### Tus archivos quedan sin cifrar en el disco

El CV que subas y los documentos que generes se guardan **en claro** en tu
directorio de datos. Cualquier programa que corra con tu usuario puede leerlos, y
si te roban el equipo sin protección, su contenido queda expuesto.

No lo ciframos desde la aplicación a propósito: la llave tendría que vivir en
esta misma máquina, junto a los datos que protege, así que no sería una barrera
sino un paso más. La protección que sí funciona es el **cifrado de disco de tu
sistema operativo** —FileVault en macOS, BitLocker en Windows, LUKS en Linux—, y
te recomendamos activarlo antes de subir tu CV.
"""


@dataclass(frozen=True)
class Disclosure:
    """The text the candidate sees, and the version they acknowledge."""

    version: str
    body_md: str

    def covers(self, acknowledged_version: str | None) -> bool:
        """Whether an acknowledgement of that version covers this text.

        Only an exact match does. An older acknowledgement is a yes to a
        different text, and treating it as valid would make the version a
        decoration (FR-002, research R-29).
        """
        return acknowledged_version == self.version


CURRENT_DISCLOSURE = Disclosure(version=DISCLOSURE_VERSION, body_md=DISCLOSURE_BODY_MD)
