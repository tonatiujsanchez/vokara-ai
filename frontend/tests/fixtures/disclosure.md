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
