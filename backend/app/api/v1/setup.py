"""The first-run endpoints: disclosure, providers and the optional mail step.

Routers validate and delegate; the rules live in the services (art. II). What
this module owns is the shape of the contract — the response models that
`contracts/openapi.yaml` declares and that the TypeScript client is generated
from (art. I).

Two properties of that shape are requirements rather than choices:

- **No response carries a credential**, not even partially. The only thing the
  API says about one is `configured | not_configured | rejected`, and it is an
  enum precisely so nothing else can be said (FR-008, SC-013).
- **`candidate_id` is never a parameter.** It is resolved from local
  configuration by `api/deps.py`; no endpoint accepts it in a path, a query, a
  body or a header (FR-003, FR-049).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, status
from pydantic import BaseModel, Field, SecretStr

from app.api.deps import CandidateId
from app.api.errors import error_responses
from app.domain.capability import Capability
from app.domain.errors import (
    DegradationAcknowledgementRequiredError,
    DisclosureAcknowledgementRequiredError,
    DisclosureAlreadyAcknowledgedError,
    EmailAppPasswordRejectedError,
    EmailLabelNotFoundError,
    EmailProviderUnreachableError,
    ModelNotAvailableError,
    ProviderCredentialRejectedError,
    ProviderNotOfferedError,
    ProviderQuotaExceededError,
    ProviderUnreachableError,
    ValidationFailedError,
)
from app.domain.setup import CredentialStatus, EmailStepStatus, SetupStep
from app.services import (
    email_link_service,
    preflight_service,
    provider_catalog_service,
    setup_service,
)
from app.services.email_link_service import EmailStepView
from app.services.preflight_service import ProviderConfigurationView
from app.services.provider_catalog_service import ProviderOptionView
from app.services.setup_service import SetupStateView

router = APIRouter(prefix="/setup", tags=["setup"])


# ── modelos de respuesta ────────────────────────────────────────────────────


class AffectedFeatureModel(BaseModel):
    """A concrete function lost to a degradation, never a generic warning."""

    code: str = Field(description="Identificador estable en inglés de la función afectada.")
    message: str = Field(description="Qué deja de funcionar y por qué, en español.")


class PreflightOutcomeModel(BaseModel):
    """One preflight result. Carries no key and no technical trace (FR-007)."""

    result: str = Field(
        description="`verified`, `capability_unverified`, `credential_rejected` o `quota_exceeded`."
    )
    checked_at: datetime = Field(description="Cuándo se verificó, no cuándo se guardó.")
    message: str = Field(description="Mensaje accionable en español.")
    embedding_dim: int | None = Field(
        default=None,
        description=(
            "Dimensión verificada del vector; presente cuando `embeddings` quedó verificado."
        ),
    )
    affected_features: list[AffectedFeatureModel] = Field(
        default_factory=list,
        description=(
            "Funciones concretas afectadas. No vacío cuando el resultado es "
            "`capability_unverified`."
        ),
    )
    degradation_reasons: list[str] = Field(
        default_factory=list,
        description=(
            "POR QUÉ no se dio por verificada la capacidad, en español y observado "
            "en el preflight: qué campo inventó el modelo, o que la respuesta no "
            "tenía la estructura pedida. FR-007.3 exige enumerar las funciones "
            "afectadas «y por qué»; `affected_features` es lo primero y esto lo "
            "segundo. NUNCA una traza técnica ni el texto crudo del proveedor."
        ),
    )


class ProviderConfigurationModel(BaseModel):
    """The configuration of one capability, as the wizard renders it."""

    capability: Capability
    provider: str = Field(description="Identificador del catálogo cerrado.")
    model: str = Field(description="Modelo efectivamente verificado.")
    credential_status: CredentialStatus = Field(
        description="Único estado consultable de una credencial. NUNCA la llave (FR-008)."
    )
    preflight: PreflightOutcomeModel
    degradation_acknowledged_at: datetime | None = None
    is_usable: bool = Field(
        description="Derivado: verificada, o sin garantía CON acuse. Es el gate de FR-010."
    )
    configuration_notice_es: str | None = Field(
        default=None,
        description=(
            "Aviso de configuración: se emite cuando la misma credencial también está "
            "definida en el entorno y Vokara usará la del asistente."
        ),
    )


class EstimatedCostModel(BaseModel):
    """Cost per month of active search, shown before the key is asked for."""

    amount_usd: float | None = Field(
        default=None, description="`null` mientras el cálculo esté pendiente."
    )
    currency: Literal["USD"] = "USD"
    usage_assumption_es: str | None = Field(
        default=None,
        description="El supuesto de uso que produce la cifra, para que sea interpretable.",
    )
    has_free_tier: bool | None = None
    free_tier_note_es: str | None = None
    is_estimated: bool = Field(
        description="Falso mientras no haya cifra: la ausencia se dice, no se inventa."
    )
    pending_note_es: str | None = None


class ProviderOptionModel(BaseModel):
    """One offerable option. Only appears if its verification is on record."""

    provider: str
    display_name: str
    is_suggested_default: bool
    credential_url: str = Field(description="Dónde se obtiene la llave.")
    default_model: str = Field(description="De configuración, nunca de una constante.")
    embedding_dim: int | None = None
    estimated_cost: EstimatedCostModel


class ProviderCatalogModel(BaseModel):
    """Two closed lists, because they are two independent choices (ADR-011)."""

    generation: list[ProviderOptionModel]
    embeddings: list[ProviderOptionModel]
    separation_reason_es: str


class EmailStepModel(BaseModel):
    """The optional step, with everything needed to decide (FR-011, FR-012)."""

    status: EmailStepStatus
    disclosure_md: str = Field(
        description="Divulgación obligatoria PREVIA a pedir credencial alguna (FR-012)."
    )
    oauth_docs_url: str = Field(description="Vía alternativa para cuentas sin App Passwords.")
    label: str | None = Field(default=None, description="Etiqueta designada. Nunca la credencial.")
    linked_at: datetime | None = None
    credential_status: CredentialStatus
    is_skippable: Literal[True] = Field(
        default=True,
        description="Siempre verdadero (FR-011): omitir tiene el mismo peso que continuar.",
    )
    value_if_linked_es: str = Field(description="Qué se gana vinculando.")
    value_if_skipped_es: str = Field(description="Qué NO se pierde al omitirlo.")
    linked_confirmation_es: str | None = Field(
        default=None,
        description=(
            "Confirmación de la vinculación, presente SOLO cuando `status` es `linked`. "
            "Nombra la etiqueta verificada y dice qué hace Vokara con ella hoy: es la "
            "contraparte del aviso de FR-012, que promete leer solo esa etiqueta."
        ),
    )
    configuration_notice_es: str | None = None


class EmailLinkRequest(BaseModel):
    """The App Password travels in the body, is used once and never returned."""

    email_address: str
    app_password: SecretStr = Field(description="Write-only; jamás se devuelve.")
    label: str = Field(description="Etiqueta de Gmail a la que Vokara restringe cada consulta.")


class DisclosureModel(BaseModel):
    """The full text of the disclosure of art. V, to be shown on screen."""

    version: str
    body_md: str = Field(description="Texto completo en español. Nunca solo un enlace.")
    acknowledged: bool
    acknowledged_at: datetime | None = None
    acknowledged_version: str | None = Field(
        default=None,
        description="Versión efectivamente acusada; un acuse viejo no cubre un texto nuevo.",
    )


class ProvidersModel(BaseModel):
    """Both capabilities, `null` where nothing has been configured."""

    generation: ProviderConfigurationModel | None = None
    embeddings: ProviderConfigurationModel | None = None


class SetupStateModel(BaseModel):
    """The facts of the first run, and the two values derived from them."""

    pending_step: SetupStep | None = Field(
        default=None,
        description="`null` ⇔ la primera ejecución concluyó y no vuelve a mostrarse.",
    )
    disclosure_acknowledged: bool
    disclosure_acknowledged_at: datetime | None = None
    providers: ProvidersModel
    email_status: EmailStepStatus
    is_complete: bool


class DisclosureAcknowledgementRequest(BaseModel):
    """`acknowledged` is `True` and nothing else: continuing is not accepting."""

    disclosure_version: str
    acknowledged: Literal[True] = Field(
        description="Acuse explícito y afirmativo. NUNCA preseleccionado, NUNCA inferido (FR-002)."
    )


class ProviderCredentialRequest(BaseModel):
    """The key travels in the body, is used for the preflight and is never returned."""

    provider: str
    api_key: SecretStr = Field(description="Credencial del usuario. Write-only; jamás se devuelve.")
    model: str | None = Field(
        default=None,
        description="Opcional. Sin él se usa el modelo por defecto de la configuración.",
    )


# ── mapeo de vistas de servicio a modelos de respuesta ──────────────────────


def _configuration_model(
    view: ProviderConfigurationView | None,
) -> ProviderConfigurationModel | None:
    if view is None:
        return None

    return ProviderConfigurationModel(
        capability=view.capability,
        provider=view.provider,
        model=view.model,
        credential_status=view.credential_status,
        preflight=PreflightOutcomeModel(
            result=view.preflight.result,
            checked_at=view.preflight.checked_at,
            message=view.preflight.message_es,
            embedding_dim=view.preflight.embedding_dim,
            affected_features=[
                AffectedFeatureModel(code=feature.code, message=feature.message_es)
                for feature in view.preflight.affected
            ],
            degradation_reasons=list(view.preflight.reasons_es),
        ),
        degradation_acknowledged_at=view.degradation_acknowledged_at,
        is_usable=view.is_usable,
        configuration_notice_es=view.configuration_notice_es,
    )


def _email_model(view: EmailStepView) -> EmailStepModel:
    return EmailStepModel(
        status=view.status,
        disclosure_md=view.disclosure_md,
        oauth_docs_url=view.oauth_docs_url,
        label=view.label,
        linked_at=view.linked_at,
        credential_status=view.credential_status,
        value_if_linked_es=view.value_if_linked_es,
        value_if_skipped_es=view.value_if_skipped_es,
        linked_confirmation_es=view.linked_confirmation_es,
        configuration_notice_es=view.configuration_notice_es,
    )


def _option_model(option: ProviderOptionView) -> ProviderOptionModel:
    cost = option.estimated_cost
    return ProviderOptionModel(
        provider=option.provider,
        display_name=option.display_name,
        is_suggested_default=option.is_suggested_default,
        credential_url=option.credential_url,
        default_model=option.default_model,
        embedding_dim=option.embedding_dim,
        estimated_cost=EstimatedCostModel(
            amount_usd=float(cost.amount_usd) if cost.amount_usd is not None else None,
            usage_assumption_es=cost.usage_assumption_es,
            has_free_tier=cost.has_free_tier,
            free_tier_note_es=cost.free_tier_note_es,
            is_estimated=cost.is_estimated,
            pending_note_es=cost.pending_note_es,
        ),
    )


def _state_model(view: SetupStateView) -> SetupStateModel:
    return SetupStateModel(
        pending_step=view.pending_step,
        disclosure_acknowledged=view.disclosure_acknowledged,
        disclosure_acknowledged_at=view.disclosure_acknowledged_at,
        providers=ProvidersModel(
            generation=_configuration_model(view.generation),
            embeddings=_configuration_model(view.embeddings),
        ),
        email_status=view.email_status,
        is_complete=view.is_complete,
    )


# ── divulgación (FR-001, FR-002, FR-014, FR-015) ────────────────────────────


@router.get(
    "/state",
    response_model=SetupStateModel,
    summary="Estado de la primera ejecución y paso pendiente",
    responses=error_responses(),
)
def get_state(candidate_id: CandidateId) -> SetupStateModel:
    """Entry point of the SPA: where the wizard resumes, derived from the facts."""
    return _state_model(setup_service.read_state(candidate_id))


@router.get(
    "/disclosure",
    response_model=DisclosureModel,
    summary="Texto vigente de la divulgación y estado de su acuse",
    responses=error_responses(),
)
def get_disclosure(candidate_id: CandidateId) -> DisclosureModel:
    """The complete text: art. V forbids it being only a link or only the README."""
    view = setup_service.read_disclosure(candidate_id)
    return DisclosureModel(
        version=view.version,
        body_md=view.body_md,
        acknowledged=view.acknowledged,
        acknowledged_at=view.acknowledged_at,
        acknowledged_version=view.acknowledged_version,
    )


@router.post(
    "/disclosure-acknowledgement",
    response_model=SetupStateModel,
    status_code=status.HTTP_201_CREATED,
    summary="Registra el acuse explícito de la divulgación",
    responses=error_responses(
        DisclosureAcknowledgementRequiredError,
        DisclosureAlreadyAcknowledgedError,
        ValidationFailedError,
    ),
)
def post_disclosure_acknowledgement(
    candidate_id: CandidateId, payload: DisclosureAcknowledgementRequest
) -> SetupStateModel:
    """Recorded with its timestamp and the version accepted (FR-002, R-29)."""
    return _state_model(
        setup_service.acknowledge_disclosure(candidate_id, version=payload.disclosure_version)
    )


# ── proveedores y preflight (FR-004 a FR-010) ───────────────────────────────


@router.get(
    "/providers/catalog",
    response_model=ProviderCatalogModel,
    summary="Proveedores ofrecibles por capacidad, con su costo estimado",
    responses=error_responses(),
)
def get_provider_catalog() -> ProviderCatalogModel:
    """The closed list, already resolved: the frontend renders, it does not branch.

    The cost travels here so it can be shown **before** any key is asked for
    (FR-005), estimated separately for each capability.
    """
    view = provider_catalog_service.catalogue()
    return ProviderCatalogModel(
        generation=[_option_model(option) for option in view.generation],
        embeddings=[_option_model(option) for option in view.embeddings],
        separation_reason_es=view.separation_reason_es,
    )


@router.get(
    "/providers/{capability}",
    response_model=ProviderConfigurationModel | None,
    summary="Configuración vigente de una capacidad",
    responses=error_responses(ValidationFailedError),
)
def get_provider_configuration(
    candidate_id: CandidateId, capability: Capability
) -> ProviderConfigurationModel | None:
    """`null` when nothing is configured. Never the credential (FR-008)."""
    return _configuration_model(preflight_service.current_configuration(candidate_id, capability))


@router.put(
    "/providers/{capability}",
    response_model=ProviderConfigurationModel,
    summary="Configura una capacidad y ejecuta su preflight",
    responses=error_responses(
        ProviderCredentialRejectedError,
        ModelNotAvailableError,
        ProviderQuotaExceededError,
        ProviderUnreachableError,
        ProviderNotOfferedError,
        ValidationFailedError,
    ),
)
def put_provider_configuration(
    candidate_id: CandidateId, capability: Capability, payload: ProviderCredentialRequest
) -> ProviderConfigurationModel:
    """The preflight runs **here**, at save time, never deferred (FR-006).

    The three results that do not allow progress leave through the error
    catalogue with their own status and code, because they are three different
    situations and the frontend has to be able to tell them apart without
    reading prose (contracts/errors.md).
    """
    view = preflight_service.configure_capability(
        candidate_id,
        capability,
        provider=payload.provider,
        api_key=payload.api_key,
        model=payload.model,
    )
    configured = _configuration_model(view)
    assert configured is not None  # noqa: S101 — configure_capability never returns None
    return configured


@router.post(
    "/providers/{capability}/degradation-acknowledgement",
    response_model=ProviderConfigurationModel,
    status_code=status.HTTP_201_CREATED,
    summary="Acuse específico de una degradación explícita",
    responses=error_responses(
        DegradationAcknowledgementRequiredError,
        ValidationFailedError,
    ),
)
def post_degradation_acknowledgement(
    candidate_id: CandidateId, capability: Capability
) -> ProviderConfigurationModel:
    """The only way a capability without guarantee becomes usable (FR-007.3).

    Answered 409 when the current preflight is not `capability_unverified`:
    there is no degradation to acknowledge, and recording one would be a
    consent to nothing.
    """
    acknowledged = _configuration_model(
        preflight_service.acknowledge_degradation(candidate_id, capability)
    )
    assert acknowledged is not None  # noqa: S101 — the service raises rather than return None
    return acknowledged


# ── correo, paso opcional (FR-011 a FR-013) ─────────────────────────────────


@router.get(
    "/email",
    response_model=EmailStepModel,
    summary="Estado del paso de correo",
    responses=error_responses(),
)
def get_email_step(candidate_id: CandidateId) -> EmailStepModel:
    """Carries the disclosure with it, because FR-012 requires it **before**.

    A warning that arrives after the form has been filled in is not a warning.
    """
    return _email_model(email_link_service.read_step(candidate_id))


@router.post(
    "/email/link",
    response_model=EmailStepModel,
    summary="Vincula la cuenta de correo y verifica la etiqueta designada",
    responses=error_responses(
        EmailAppPasswordRejectedError,
        EmailLabelNotFoundError,
        EmailProviderUnreachableError,
        ValidationFailedError,
    ),
)
def post_email_link(candidate_id: CandidateId, payload: EmailLinkRequest) -> EmailStepModel:
    """Verifies the label exists before taking the link as established (FR-013).

    Its three failures leave with their own code and none of them blocks
    anything: the step stays skippable at every point.
    """
    return _email_model(
        email_link_service.link(
            candidate_id,
            address=payload.email_address,
            app_password=payload.app_password,
            label=payload.label,
        )
    )


@router.post(
    "/email/skip",
    response_model=SetupStateModel,
    summary="Omite el paso de correo",
    responses=error_responses(),
)
def post_email_skip(candidate_id: CandidateId) -> SetupStateModel:
    """One action, and the first run can conclude. A valid ending (FR-011)."""
    email_link_service.skip(candidate_id)
    return _state_model(setup_service.read_state(candidate_id))
