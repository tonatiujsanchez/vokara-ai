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
from app.domain.capability import Capability
from app.domain.setup import CredentialStatus, EmailStepStatus, SetupStep
from app.services import setup_service
from app.services.preflight_service import ProviderConfigurationView
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
        ),
        degradation_acknowledged_at=view.degradation_acknowledged_at,
        is_usable=view.is_usable,
        configuration_notice_es=view.configuration_notice_es,
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
)
def get_state(candidate_id: CandidateId) -> SetupStateModel:
    """Entry point of the SPA: where the wizard resumes, derived from the facts."""
    return _state_model(setup_service.read_state(candidate_id))


@router.get(
    "/disclosure",
    response_model=DisclosureModel,
    summary="Texto vigente de la divulgación y estado de su acuse",
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
)
def post_disclosure_acknowledgement(
    candidate_id: CandidateId, payload: DisclosureAcknowledgementRequest
) -> SetupStateModel:
    """Recorded with its timestamp and the version accepted (FR-002, R-29)."""
    return _state_model(
        setup_service.acknowledge_disclosure(candidate_id, version=payload.disclosure_version)
    )
