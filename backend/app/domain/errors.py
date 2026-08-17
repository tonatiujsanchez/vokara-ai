"""Domain error hierarchy.

Every error carries a stable English `code`, an actionable Spanish `message` and
optional structured `details`. The catalogue of codes and texts is
specs/001-candidate-onboarding/contracts/errors.md, and it is the single owner
of the wording: the frontend shows `message` as is and branches only on `code`
(art. IX, errors.md "Uso desde el frontend").

Three rules hold for every message here:

1. No document content and no personal data (FR-045). Messages are fixed
   templates; the only interpolated values are limits the system configures.
2. No credential, complete or partial, and no technical trace (FR-008, FR-013).
3. What happened, why, and the concrete next step. Without a next step the
   message is incomplete — in a local installation it is all the support there
   is (roadmap 11.5).
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base of every error the product can explain to the candidate."""

    code: str = "INTERNAL_ERROR"
    message: str = (
        "Ocurrió un error inesperado. Inténtalo de nuevo; si persiste, abre un issue "
        "con lo que aparece en la pantalla de diagnóstico."
    )
    http_status: int = 500

    def __init__(self, details: dict[str, Any] | None = None) -> None:
        super().__init__(self.message)
        self.details = details


# ── Primera ejecución: divulgación (FR-001, FR-002, SC-011) ─────────────────


class DisclosureAcknowledgementRequiredError(DomainError):
    """The server gate of research R-29, not the convenience guard of the SPA.

    SC-011 asks that *no* route — direct navigation, a reload, a restart, a curl
    against the API — let a CV be uploaded without the acknowledgement on
    record, so the check cannot live in the frontend.
    """

    code = "DISCLOSURE_ACKNOWLEDGEMENT_REQUIRED"
    message = (
        "Antes de continuar necesitamos que leas y aceptes qué datos se quedan en tu "
        "computadora y qué se envía a tu proveedor de IA."
    )
    http_status = 409


# ── Primera ejecución: proveedores y preflight (FR-004 a FR-010) ────────────
#
# Four results, four messages, because they are four situations. Presenting an
# exhausted quota as an invalid credential sends the candidate to regenerate a
# key that works perfectly (research R-23, contracts/errors.md).


class ProviderCredentialRejectedError(DomainError):
    """FR-007.1. Carries where to regenerate the key, never the key."""

    code = "PROVIDER_CREDENTIAL_REJECTED"
    message = (
        "Tu proveedor rechazó la API key. Verifica que la copiaste completa y que sigue "
        "activa en la consola de tu proveedor."
    )
    http_status = 400

    def __init__(self, *, console_url: str | None = None) -> None:
        super().__init__({"console_url": console_url} if console_url else None)


class ProviderQuotaExceededError(DomainError):
    """FR-007.4. Says out loud that the key works: it is the quota that does not."""

    code = "PROVIDER_QUOTA_EXCEEDED"
    message = (
        "Tu API key es válida, pero alcanzaste el límite de tu cuota. Puedes esperar a que "
        "se reinicie o configurar otro proveedor."
    )
    http_status = 429


class ProviderUnreachableError(DomainError):
    """Not a statement about the credential: about the network (research R-23)."""

    code = "PROVIDER_UNREACHABLE"
    message = (
        "No pudimos comunicarnos con tu proveedor para verificar la llave. Revisa tu "
        "conexión e inténtalo de nuevo; no hace falta que vuelvas a escribirla."
    )
    http_status = 503


class ModelNotAvailableError(DomainError):
    """The concrete event of ADR-011: a provider retired the configured model.

    Actionable because model names live in configuration: the fix is one line of
    the user's own file, and the message says which one.
    """

    code = "MODEL_NOT_AVAILABLE"
    message = (
        "El modelo configurado ya no está disponible en tu proveedor. Actualiza el nombre "
        "del modelo en tu configuración; en la documentación está el vigente."
    )
    http_status = 400

    def __init__(self, *, configured_model: str) -> None:
        super().__init__({"configured_model": configured_model})


class ProviderNotOfferedError(DomainError):
    """FR-009: no empirical verification on record, so it is not on the list."""

    code = "PROVIDER_NOT_OFFERED"
    # The catalogue's row reads «Ese proveedor todavía no está disponible en
    # Vokara.» and stops there. The next step is added because rule 3 of
    # contracts/errors.md applies to every message without exception, and
    # «elige uno de la lista» is the only thing the candidate can do about it.
    message = (
        "Ese proveedor todavía no está disponible en Vokara. Elige uno de los que "
        "aparecen en la lista."
    )
    http_status = 422


class DegradationAcknowledgementRequiredError(DomainError):
    """FR-007.3 and SC-016: the price of continuing with an unverified capability."""

    code = "DEGRADATION_ACKNOWLEDGEMENT_REQUIRED"
    message = (
        "Para continuar con este proveedor necesitamos que confirmes que entiendes qué "
        "funciones no estarán disponibles."
    )
    http_status = 409

    def __init__(self, *, affected_features: list[dict[str, str]] | None = None) -> None:
        super().__init__({"affected_features": affected_features} if affected_features else None)


class GenerationProviderRequiredError(DomainError):
    """FR-010, and only about generation.

    A missing **embeddings** provider never produces this: it degrades the
    features that depend on vectors and says which, which is what art. XI asks
    instead of a block.
    """

    code = "GENERATION_PROVIDER_REQUIRED"
    message = (
        "Antes de subir tu CV necesitas configurar tu proveedor de generación: es el que "
        "lee el documento y arma tu perfil."
    )
    http_status = 409


# ── Primera ejecución: vinculación de correo (FR-011 a FR-013) ──────────────
#
# None of these blocks anything: the step is optional and skipping it is a valid
# way out at any moment (FR-011). Each message says so or leads somewhere.


class EmailAppPasswordRejectedError(DomainError):
    """The warning was given before starting (FR-012); this closes it with a way out."""

    code = "EMAIL_APP_PASSWORD_REJECTED"
    # «cuenta de Workspace» and not the full brand: the guard of art. XI keeps
    # provider names out of `domain/`, and this text does not need the name to
    # be understood — it opens with the mail provider that rejected the password.
    # The complete wording, brand included, belongs to the disclosure the email
    # adapter owns, which is where naming that provider is the module's job
    # (FR-012, ADR-012).
    message = (
        "Gmail rechazó la App Password. Si tu cuenta es de Workspace o tiene "
        "Protección Avanzada, las App Passwords están deshabilitadas: usa la vía OAuth."
    )
    http_status = 400

    def __init__(self, *, oauth_docs_url: str | None = None) -> None:
        super().__init__({"oauth_docs_url": oauth_docs_url} if oauth_docs_url else None)


class EmailLabelNotFoundError(DomainError):
    """The link is **not** taken as established: FR-013 verifies before believing."""

    code = "EMAIL_LABEL_NOT_FOUND"
    message = (
        "No encontramos esa etiqueta en tu cuenta. Créala en Gmail y aplica un filtro que "
        "mande ahí tus alertas de empleo; después vuelve a intentarlo."
    )
    http_status = 422

    def __init__(self, *, help_url: str | None = None) -> None:
        super().__init__({"help_url": help_url} if help_url else None)


class EmailProviderUnreachableError(DomainError):
    """Reminds the candidate that the step is skippable, because it is."""

    code = "EMAIL_PROVIDER_UNREACHABLE"
    message = (
        "No pudimos conectarnos a tu correo en este momento. Inténtalo de nuevo, o "
        "continúa sin vincularlo: no bloquea nada."
    )
    http_status = 503
