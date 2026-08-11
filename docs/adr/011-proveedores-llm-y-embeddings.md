# ADR-011 — Proveedores de generación y de embeddings: configuración independiente

**Estado:** Aceptado · **Fecha:** 2026-08

---

## Contexto

El artículo XI de la constitución exige dos cosas a la vez: que Vokara **no
dependa de un proveedor concreto** y que las **capacidades** —salida
estructurada, embeddings— se declaren explícitamente en el adapter, de modo que
una capacidad ausente degrade de forma informada y nunca en silencio.

El ADR-003 fijó Gemini como **default sugerido**, no como proveedor único, y el
roadmap §5 ya enumera OpenAI, Anthropic, DeepSeek y Kimi como soportados
"sujetos a verificación de capacidades, pendiente de ADR-011". Este ADR cierra
ese pendiente.

El problema concreto es que **los proveedores no ofrecen el mismo conjunto de
capacidades**. El caso más claro: **Anthropic no ofrece un modelo de
embeddings**. Vokara los necesita para el sub-score semántico del matching
(art. III, roadmap §4.5). Si generación y embeddings quedaran amarrados al mismo
proveedor, elegir Claude dejaría el matching semántico inoperante —no por una
limitación de Vokara, sino por una decisión de configuración que el usuario no
tenía cómo anticipar.

Ese acoplamiento no lo impone nada técnico: son dos llamadas distintas, a dos
endpoints distintos, con dos modelos distintos. Lo único que las une es la
suposición cómoda de que un usuario configura "un proveedor".

## Decisión

### 1. Generación y embeddings se configuran de forma independiente

El usuario elige **un proveedor para generación** (salida estructurada) y **un
proveedor para embeddings**, y aporta la API key correspondiente a cada uno.
Pueden ser el mismo proveedor o dos distintos; ninguna de las dos elecciones
condiciona a la otra.

La combinación por defecto sugerida es Gemini para ambos, por el criterio de
capa gratuita del ADR-003.

### 2. Proveedores soportados en v1 (lista cerrada, predefinida en la app)

**Generación:** Google Gemini (default sugerido), OpenAI, Anthropic, DeepSeek,
Kimi/Moonshot.

**Embeddings:** Google Gemini (default sugerido), OpenAI, y los demás que la
verificación empírica confirme (ver "Estado de verificación").

La lista es cerrada: el usuario elige de un desplegable, no escribe un endpoint
arbitrario.

### 3. Las capacidades se declaran en una matriz explícita en el código

Cada proveedor declara, como dato y no como comportamiento: si soporta salida
estructurada nativa, si ofrece embeddings y con qué dimensión de vector. Esa
matriz es la que consultan el preflight del wizard y la pantalla de diagnóstico.

**Ninguna feature consulta el nombre del proveedor.** Consulta la capacidad. Un
`if provider == "..."` fuera del adapter es un bug del artículo XI, no un atajo.

### 4. La degradación es explícita e informada

Si el proveedor de generación elegido no garantiza salida estructurada, el
wizard lo dice **en el momento de configurarlo**: qué funciones concretas quedan
afectadas y por qué, y el usuario decide si continúa así o cambia. Lo mismo si
el proveedor de embeddings elegido no ofrece la capacidad. Nunca se descubre a
mitad del uso, y nunca se resuelve solo con un error opaco.

### 5. Los puertos no asumen API key obligatoria ni endpoint fijo

`StructuredOutputPort` y `EmbeddingsPort` se diseñan admitiendo **`base_url`
configurable** y **credencial opcional**. El motivo es concreto: añadir Ollama
—o cualquier servidor compatible con la API de OpenAI— debe ser **una
implementación nueva del puerto, no un refactor del puerto**. Un puerto que da
por sentado "hay una API key" y "el endpoint es el del proveedor" convierte esa
adición futura en un cambio que toca todo lo que hay detrás.

**Ollama no se implementa en v1.** Lo que se decide aquí es no cerrarle la
puerta con la forma de la interfaz.

## Alternativas descartadas

**Un solo proveedor para todo.** Es la configuración más simple de explicar —una
elección, una llave— y se descarta por su consecuencia inmediata: Anthropic no
ofrece embeddings, así que quien elija Claude se queda sin matching semántico.
Una decisión de producto no puede depender de que el usuario acierte con el
proveedor sin saber que estaba eligiendo también sus embeddings.

**Proveedor abierto o arbitrario desde v1** (que el usuario escriba cualquier
`base_url` y cualquier nombre de modelo). Se descarta por dos razones. Primera,
el costo de soporte: cada combinación no probada llega como issue del proyecto.
Segunda, y decisiva, **el preflight de capacidades no puede validar lo
desconocido**: la lista cerrada es justamente lo que permite decir por adelantado
qué va a funcionar y qué no. Se contempla para versiones futuras —Mistral,
Together AI, Groq, Ollama y modelos locales—, y por eso los puertos se diseñan
para admitirlo (decisión 5).

**Elegir el proveedor de embeddings automáticamente a partir del de
generación** (p. ej. "si eliges Anthropic, usamos Gemini para embeddings").
Evita un paso del wizard y se descarta porque haría que Vokara pidiera una
segunda API key —o fallara por no tenerla— sin que el usuario hubiera elegido
nada. Es degradación silenciosa con otro nombre.

## Estado de verificación

La matriz declarada en el código **no vale más que la verificación que la
respalda**. Afirmar que un proveedor soporta salida estructurada sin haberlo
probado contra un esquema Pydantic real es exactamente el fallo opaco que el
artículo XI prohíbe. Esta tabla es el registro de esa verificación y **se
actualiza conforme se prueba cada proveedor**.

"Respeta `null` en opcionales" tiene columna propia porque es el modo de fallo
más común y más caro: un proveedor que rellena campos opcionales con texto
inventado en vez de dejarlos vacíos no rompe el parseo —produce afirmaciones sin
sustento, que es lo que el artículo IV existe para impedir—.

| Proveedor | Modelo de generación | Salida estructurada | Respeta `null` en opcionales | Embeddings | Dimensión | Verificado (fecha) |
|---|---|---|---|---|---|---|
| google | `gemini-3.5-flash-lite` | Sí | Sí | OK | 768 | 2026-08-11 |
| OpenAI | pendiente | pendiente | pendiente | pendiente | pendiente | pendiente |
| Anthropic | pendiente | pendiente | pendiente | **No ofrece** | n/a | pendiente |
| DeepSeek | pendiente | pendiente | pendiente | pendiente | pendiente | pendiente |
| Kimi / Moonshot | pendiente | pendiente | pendiente | pendiente | pendiente | pendiente |

Un proveedor con verificación "pendiente" **no se anuncia como soportado en la
UI ni en el README**: aparece cuando su fila está completa.

### Notas de la verificación de Google (2026-08-11)

- **Método.** Esquema Pydantic anidado con campos opcionales, aplicado sobre un
  CV deliberadamente incompleto: sin teléfono, sin años de experiencia
  declarados, un empleo sin fechas ni logros y una educación sin título. El
  criterio de aprobación no es que el parseo funcione, sino que el modelo
  devuelva `null` en esos campos **en vez de inventar valores plausibles** —que
  es el modo de fallo que el artículo IV existe para impedir—. Latencia
  observada: 1.54 s.
- **Dimensión de embeddings.** `gemini-embedding-001` devuelve **3072** por
  defecto, pero soporta truncado MRL vía `output_dimensionality`. Se fija en
  **768** para ahorrar espacio en pgvector sin pérdida relevante de calidad. Ese
  valor queda registrado como `embedding_dim` junto a cada vector (ADR-003), de
  modo que un cambio futuro de dimensión sea detectable y re-embebible, no una
  corrupción silenciosa.
- **Parámetros de muestreo.** `temperature`, `top_p` y `top_k` están
  **DEPRECADOS en Gemini 3.x**. El adapter **no debe asumir que existen**. El
  determinismo que exige el artículo III proviene de la estructura del pipeline
  —esquema tipado en cada frontera, decisiones de flujo fuera del LLM, reglas
  testeables—, no del parámetro de temperatura (ver nota del ADR-003).
- **Nombres de modelo.** Google retiró `gemini-2.0-flash` el **1 de junio de
  2026**. Los nombres de modelo **NO deben vivir en constantes de código**: van
  en configuración, con override por variable de entorno y con un **mensaje de
  error accionable** cuando el modelo configurado ya no exista. Un proveedor que
  deprecia un modelo no debe poder romper una instalación que el usuario no
  actualizó (ADR-009: actualizar depende de él).

## Consecuencias

**Positivas**

- Ningún usuario queda sin una capacidad del producto por haber elegido el
  proveedor "equivocado" para generación. La elección de Claude deja de implicar
  la pérdida del matching semántico.
- La matriz de capacidades convierte el artículo XI en algo verificable: el
  preflight y la pantalla de diagnóstico (§11.4) leen datos, no casos especiales
  repartidos por el código.
- El usuario puede optimizar costo por separado: generación en el proveedor que
  prefiera, embeddings en el más barato que sirva.
- Los puertos con `base_url` y credencial opcional dejan Ollama y los modelos
  locales a una implementación de distancia, sin comprometerse a ellos en v1.

**Costos y riesgos**

- **Cambiar el proveedor de embeddings invalida los vectores ya persistidos.**
  La dimensión cambia y hay que **re-embeber** todo: perfil y vacantes. La UI
  debe advertirlo **antes** de permitir el cambio —no después— y ofrecer el
  reprocesamiento como parte de la operación, no como un paso que el usuario
  descubra por su cuenta. Es el mismo punto que el ADR-003 ya marcó sobre
  `embedding_model` y `embedding_dim`: aquí se vuelve visible en la UI porque
  ahora el cambio de proveedor de embeddings es una acción de usuario, no una
  migración del proyecto.
  **Cambiar el proveedor de generación no tiene ese efecto**: no persiste nada.
  Los dos cambios se comunican distinto porque son distintos.
- El wizard gana un paso: **dos proveedores que configurar en vez de uno**, con
  su costo estimado mostrado por separado. Es fricción real contra el artículo
  VII, y se acepta porque la alternativa es que una parte del producto no
  funcione sin explicación. Se mitiga con el default sugerido —Gemini para
  ambos, una sola llave— que resuelve el caso común en una elección.
- **Cada proveedor añadido incrementa la superficie de prueba.** Las evals del
  golden set deben poder correr contra más de uno (ADR-003, art. VI): son la
  prueba ejecutable de que la portabilidad no es solo una afirmación del
  adapter.
- La verificación empírica es trabajo continuo: los proveedores cambian modelos,
  deprecan endpoints y modifican su soporte de salida estructurada sin avisar.
  Una fila verificada tiene fecha por eso, y una fecha vieja es motivo para
  volver a probar.

## Impacto en artefactos existentes

- **Roadmap §5 (fila LLM):** refleja la configuración independiente de los dos
  proveedores y la lista cerrada de v1.
- **Roadmap §11.2 (wizard):** el paso de proveedor configura generación y
  embeddings por separado, con preflight y costo estimado independientes.
- **ADR-003:** sigue vigente sin cambios. Gemini continúa siendo el default
  sugerido; este ADR precisa que lo es **para ambas configuraciones**, por
  separado.
- **Constitución:** sin cambios. Este ADR implementa el artículo XI; no lo
  modifica.
