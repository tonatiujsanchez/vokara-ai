# ADR-010 — Licencia del proyecto: AGPL-3.0

**Estado:** Aceptado · **Fecha:** 2026-08

---

## Contexto

Vokara es software comunitario dirigido a personas buscando empleo. El
repositorio no tenía archivo `LICENSE`: sin licencia explícita, el código queda
bajo copyright exclusivo por omisión y nadie —ni contribuidores ni usuarios—
tiene permiso legal para usarlo, modificarlo o redistribuirlo. La ausencia de
licencia no es neutral: es la opción más restrictiva posible.

El modo de uso previsto es **ejecución local por parte del propio candidato**:
quien usa Vokara corre su propia instancia, con sus propios documentos y sus
propias credenciales de proveedores. **No existe un backend hospedado por el
proyecto** que terceros consuman como servicio.

Ese modelo importa para la elección de licencia. Los datos que Vokara procesa
—CV, historial laboral, perfil maestro— son datos personales sensibles
(constitución art. V). Cuando el software corre en la máquina del usuario, la
única garantía real de que "hace lo que dice" es que su código sea auditable y
siga siéndolo en cualquier derivado que ese usuario reciba.

Hay además una restricción técnica concreta: **PyMuPDF, la biblioteca candidata
para el parseo de PDF del CV maestro, se distribuye bajo AGPL-3.0** (con licencia
comercial alternativa de pago). Cualquier licencia permisiva para Vokara sería
incompatible con enlazarla, y obligaría a pagar licencia comercial o a
sustituirla por una alternativa inferior.

## Decisión

Licenciar Vokara bajo **GNU Affero General Public License v3.0 (AGPL-3.0)**.

El texto íntegro y sin modificar de la licencia vive en `LICENSE`, en la raíz del
repositorio. El README lleva el aviso de licencia estándar.

La cláusula que motiva la elección es la **sección 13 de la AGPL**: si alguien
modifica Vokara y lo ofrece a usuarios **a través de una red**, debe poner el
código fuente modificado a disposición de esos usuarios. La GPL ordinaria no
cubre ese caso —hospedar no es distribuir— y es exactamente el caso que aquí
interesa cerrar.

## Alternativas descartadas

**MIT y Apache 2.0.** Son la vía de máxima adopción: cualquiera integra el código
sin obligaciones de reciprocidad, y son las licencias que las empresas aceptan
sin revisión legal. Se descartan por su consecuencia directa: **permiten
hospedar comercialmente el trabajo en forma cerrada**. Un tercero podría tomar
Vokara, ofrecerlo como SaaS de pago y no devolver nada —ni el código, ni las
mejoras, ni la posibilidad de auditar qué hace ese servicio con los CVs de sus
usuarios. Para un proyecto comunitario cuyo valor es el trabajo acumulado en el
matching, el verificador de veracidad y los prompts, ese es el escenario que la
licencia debe impedir. Apache 2.0 aporta además concesión expresa de patentes,
ventaja real que no compensa la anterior; la AGPL-3.0 incluye su propia
concesión de patentes en la sección 11.

**GPL-3.0.** Mantiene el copyleft pero solo se dispara con la distribución. Como
el SaaS no distribuye binarios, deja abierto precisamente el hueco que la AGPL
cierra. Descartada por insuficiente para este propósito.

**Sin licencia (statu quo).** Copyright exclusivo por omisión: nadie puede
contribuir ni usar el software legalmente. Incompatible con el carácter
comunitario del proyecto.

## Consecuencias

**Positivas**

- **Habilita el uso de PyMuPDF** sin licencia comercial ni sustituto técnico
  inferior. La compatibilidad deja de ser un problema abierto.
- **Cualquier fork hospedado debe publicar sus cambios** a los usuarios de ese
  servicio (AGPL §13). Las mejoras de terceros vuelven al ecosistema, no se
  privatizan.
- El usuario que corre Vokara con sus datos personales puede auditar el código
  que los procesa, y conserva ese derecho sobre cualquier versión modificada que
  reciba. Refuerza el art. V de la constitución con una garantía legal, no solo
  con una promesa de diseño.

**Costos y riesgos**

- **Menor adopción corporativa.** Muchas empresas prohíben por política interna
  incorporar código AGPL en sus productos. Vokara pierde ese canal de adopción y
  de contribuciones. Es el costo aceptado a cambio de la reciprocidad.
- La AGPL es **viral hacia el resto del código**: toda dependencia que se enlace
  debe ser compatible con AGPL-3.0. Añadir una dependencia con licencia
  incompatible (p. ej. propietaria o GPL-2.0-only) pasa a ser un bloqueo de
  merge, no un detalle. Verificar la licencia entra en la justificación de
  dependencia nueva que ya exige el art. VII.
- Ofrecer en el futuro una versión hospedada **cerrada** del propio Vokara
  requeriría acuerdo de licencia de contribuyentes (CLA) o relicenciamiento con
  consentimiento de todos los autores. Si esa opción llega a interesar, el CLA
  debe adoptarse **antes** de aceptar contribuciones externas, no después.

## Alcance

La premisa de ejecución local de este ADR dejó de ser una suposición: la
constitución v2.0.0 (art. VII) y el ADR-009 la fijan como modelo de
distribución, y el ADR-002 —que desplegaba `staging` y `prod` en un VPS propio—
quedó Superseded. No hay servicio hospedado del proyecto cuyo código pudiera
divergir del repositorio.

Lo que esta licencia cambia es la situación de **un tercero** que hospede un
Vokara modificado: ese tercero queda obligado a publicar sus modificaciones a
los usuarios de su servicio (AGPL §13).

Si en el futuro el proyecto operara un servicio hospedado como producto
principal, la obligación seguiría cumpliéndose mientras el repositorio público
refleje el código desplegado. Cerrar ese código sí requeriría un ADR nuevo que
reemplace a este.

## Impacto en artefactos existentes

- **`LICENSE` (nuevo):** texto íntegro de AGPL-3.0.
- **`README.md`:** incorpora el aviso de licencia estándar.
- **Constitución:** sin cambios. Esta decisión refuerza el art. V; no lo
  modifica.
- **Roadmap §5 (stack):** al fijar PyMuPDF como parser de PDF, anotar que su
  licencia AGPL es compatible por esta decisión —ver ADR-010.
- **Numeración:** este ADR toma el número 010 por instrucción explícita; los
  números 007–009 quedan libres. Los ADRs 001–004 viven agrupados en
  `000-adrs-iniciales.md`.
