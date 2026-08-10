# ADR-007 — Almacenamiento de documentos: `StoragePort` sobre filesystem local, sin cifrado en reposo en v1

**Estado:** Aceptado · **Fecha:** 2026-08

---

## Contexto

La feature 001 (onboarding del candidato) necesita guardar el binario del CV
maestro que el usuario sube. Ningún ADR vigente decidía dónde vive ese archivo,
y por eso `specs/001-candidate-onboarding/plan.md` marcó la decisión como
**bloqueante**: el adapter de storage no debía implementarse sin este ADR.

La propuesta original (`research.md` R-06) era un `StoragePort` sobre S3 vía
boto3 con **MinIO** como backend en dev y en el VPS, más **cifrado de sobre
AES-256-GCM en la aplicación**: clave de datos por objeto, envuelta con una
clave maestra en `DOCUMENT_ENCRYPTION_KEY`, persistiendo clave envuelta, nonce y
`key_version` en `documents`. Ese diseño respondía al art. V de la constitución
v1.1.1, que exigía cifrado en reposo, y habilitaba **crypto-shredding**: borrar
la clave para volver un documento irrecuperable sin tener que sobrescribirlo.

El pivote a ejecución local (constitución v2.0.0) invalida las premisas de esa
propuesta antes de que llegara a ratificarse. Por eso este ADR **la reescribe en
lugar de ratificarla**.

## Decisión

**Se conserva el `StoragePort`** —`put` / `get` / `delete` / `exists`— como
adapter con interfaz propia (constitución art. II), con una **implementación
sobre el filesystem local** como única de v1. Los archivos viven en un
directorio de datos de la instalación; `documents` persiste la `storage_key`,
no el binario.

**Se retira de v1 el cifrado en reposo.** Los documentos se guardan en claro.

El puerto se conserva aunque hoy tenga una sola implementación porque es lo que
permite que S3/MinIO —y con él el cifrado— entren después sin tocar servicios,
y porque `services/` no debe saber si detrás hay un disco o un bucket. Es la
misma razón por la que existe el adapter de LLM.

### Por qué se retira el cifrado

No protege contra ninguna amenaza real en una instalación local. En el modelo
hospedado, el cifrado en reposo defiende contra un atacante que obtiene el disco
o el bucket pero no la clave, que vive en otro sitio (variable de entorno del
proceso, gestor de secretos). **Esa separación no existe en la máquina del
usuario:** la clave maestra estaría en un `.env` junto a los datos que protege,
legible por el mismo usuario y por cualquier proceso que corra como él. Quien
pueda leer los documentos cifrados puede leer la clave. El cifrado no añade una
barrera; añade un paso.

**El crypto-shredding también pierde sentido.** Su valor estaba en borrar de
forma verificable un dato distribuido —réplicas, backups, versiones de un
bucket— destruyendo la clave en vez de perseguir cada copia. En local no hay
copias que perseguir: borrar es `delete` sobre un archivo en un disco.

Contra la amenaza que sí es real en local —robo o pérdida del equipo— la
respuesta correcta es el **cifrado de disco del sistema operativo** (FileVault,
BitLocker, LUKS), que sí guarda la clave fuera del disco y protege el equipo
entero, no solo los archivos de Vokara. Vokara lo recomienda en el README en vez
de implementar una versión peor del mismo mecanismo.

### Diferido, no descartado

El cifrado en reposo y el crypto-shredding **quedan diferidos para un eventual
despliegue multi-usuario**, donde las premisas vuelven a cumplirse: infraestructura
separada del secreto, datos de varias personas en el mismo almacenamiento, backups
fuera del control del titular y un derecho de eliminación que hay que poder
demostrar. Si ese despliegue llega, este ADR se reemplaza y el diseño de
`research.md` R-06 —cifrado de sobre AES-256-GCM con `key_version`— es el punto
de partida, no material de archivo. El `StoragePort` es precisamente lo que hace
que ese cambio sea una implementación nueva y no una reescritura.

## Alternativas descartadas

**Ratificar R-06 tal cual (S3/MinIO + cifrado de sobre).** Obligaría a cada
usuario a levantar un MinIO en su máquina para guardar archivos en un disco que
ya tiene, y a gestionar una clave maestra que no protege nada. Un servicio más
en el Compose, contra el criterio de fricción de instalación del art. VII, a
cambio de seguridad aparente.

**Cifrar con una clave derivada de una contraseña del usuario.** Es la única
variante que daría cifrado real en local, porque el secreto viviría en la cabeza
del usuario y no en el disco. Descartada por su costo de UX frente al alcance de
v1: obliga a introducir la contraseña en cada arranque, rompe el procesamiento
en background de Celery (el worker necesitaría la clave en memoria), y perder la
contraseña significa perder el perfil sin recuperación posible. Es una decisión
de producto, no de infraestructura, y v1 no la necesita para funcionar. Si se
retoma, requiere ADR propio.

**Guardar el binario en Postgres (`bytea`).** Evita el puerto y elimina el
problema del directorio de datos, pero infla la base y los dumps, complica los
backups del usuario y hace peor un trabajo que el filesystem hace bien.

## Consecuencias

**Positivas**

- Cero servicios nuevos en el Compose local para almacenar archivos (art. VII).
- El adapter de storage deja de estar bloqueado: la feature 001 puede
  implementarse.
- Backup y portabilidad triviales para el usuario: copiar un directorio.
- El `StoragePort` mantiene abierta la puerta a S3/MinIO con cifrado sin tocar
  `services/`.

**Costos y riesgos**

- **Riesgo asumido: los CVs y materiales generados quedan en claro en la máquina
  del usuario.** Cualquier proceso que corra con su cuenta puede leerlos, y un
  equipo robado sin cifrado de disco expone su contenido. **Se divulga
  explícitamente en el README**, junto con la recomendación de activar el
  cifrado de disco del sistema operativo. Es una decisión consciente de no
  ofrecer una protección que en este contexto sería teatro, no una omisión.
- El directorio de datos entra en el alcance operativo del usuario: si lo borra,
  la base queda con `storage_key` apuntando a archivos inexistentes. El
  `StoragePort` expone `exists` y el error se maneja con
  `STORAGE_UNAVAILABLE` (ver `specs/001-candidate-onboarding/contracts/errors.md`).
- La ruta del directorio debe ser configurable y tener un default sensato por
  sistema operativo; en Windows, dentro de WSL2 según el setup del ADR-000.

## Impacto en artefactos existentes

- **`specs/001-candidate-onboarding/research.md` R-06:** reemplazado por este
  ADR. La propuesta S3 + cifrado de sobre queda como diseño diferido.
- **`specs/001-candidate-onboarding/plan.md`:** desaparece la decisión abierta
  bloqueante; `adapters/storage/crypto.py` (cifrado de sobre) sale del árbol de
  v1.
- **`specs/001-candidate-onboarding/quickstart.md`:** el gate "ADR-007
  ratificado" queda satisfecho por este documento.
- **`data-model.md`:** `documents` deja de necesitar clave envuelta, nonce y
  `key_version`; conserva `storage_key`.
