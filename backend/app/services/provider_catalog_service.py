"""What the wizard may offer, per capability, with its cost beside it.

Two filters and the order says what it means: **first** «has this been verified
empirically», then «does it do this». A provider missing from the answer is
missing because nobody measured it, not because it failed (FR-009, ADR-011). To
that the service adds whether an implementation of the port actually exists: a
row can be verified and still have no code behind it, and offering that would be
a promise the wizard cannot keep.

**The frontend does not branch by provider** (art. XI). It receives finished
options — name, link where the key is obtained, default model, estimated cost —
and renders them. That is why the display name and the URL come from the adapter
and not from a table in the SPA: adding a provider must not require touching the
frontend at all.

**The cost travels here** because FR-005 requires it to be on screen *before* any
key is asked for, and separately for each capability: adding the two figures
would suggest that changing the embeddings provider moves the bill, when what
moves it is generation (ADR-011, research R-27). The figures themselves are the
pending work of roadmap step 10; until they exist the catalogue says so instead
of inventing a plausible number — the same rule art. IV applies to the CV,
applied to what Vokara says about itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.adapters.llm.capabilities import ProviderId, capabilities_of
from app.adapters.llm.directory import SEPARATION_REASON_ES, profile_of
from app.adapters.llm.factory import default_model, implemented_and_offerable
from app.adapters.llm.pricing import pricing_for
from app.core.config import Settings, get_settings
from app.domain.capability import Capability

COST_PENDING_ES = (
    "Todavía no publicamos el costo estimado de este proveedor. Consúltalo en su sitio "
    "antes de configurarlo."
)


@dataclass(frozen=True)
class EstimatedCostView:
    """A figure never travels without the assumption that produced it (FR-005)."""

    amount_usd: Decimal | None
    usage_assumption_es: str | None
    # Whether the provider has a free tier at all is a fact about the provider
    # and is known today; what it covers is part of the pending calculation.
    has_free_tier: bool | None
    free_tier_note_es: str | None
    is_estimated: bool
    pending_note_es: str | None
    currency: str = "USD"


@dataclass(frozen=True)
class ProviderOptionView:
    """One offerable option, ready to render without knowing who it is."""

    provider: str
    display_name: str
    is_suggested_default: bool
    credential_url: str
    default_model: str
    embedding_dim: int | None
    estimated_cost: EstimatedCostView


@dataclass(frozen=True)
class ProviderCatalogView:
    """Two lists, because they are two independent choices (ADR-011)."""

    generation: tuple[ProviderOptionView, ...]
    embeddings: tuple[ProviderOptionView, ...]
    separation_reason_es: str = SEPARATION_REASON_ES


def _cost_of(provider: ProviderId, capability: Capability) -> EstimatedCostView:
    pricing = pricing_for(provider, capability)
    if pricing is None or not pricing.is_estimated:
        return EstimatedCostView(
            amount_usd=None,
            usage_assumption_es=None,
            has_free_tier=pricing.has_free_tier if pricing else None,
            free_tier_note_es=pricing.free_tier_es if pricing else None,
            is_estimated=False,
            pending_note_es=COST_PENDING_ES,
        )

    return EstimatedCostView(
        amount_usd=pricing.estimated_monthly_usd,
        usage_assumption_es=pricing.usage_assumption_es,
        has_free_tier=pricing.has_free_tier,
        free_tier_note_es=pricing.free_tier_es,
        is_estimated=True,
        pending_note_es=None,
    )


def options_for(
    capability: Capability, settings: Settings | None = None
) -> tuple[ProviderOptionView, ...]:
    """The closed list for one capability: verified, implemented, priced."""
    resolved = settings or get_settings()

    return tuple(
        ProviderOptionView(
            provider=provider.value,
            display_name=profile_of(provider).display_name,
            is_suggested_default=profile_of(provider).is_suggested_default,
            credential_url=profile_of(provider).credential_url,
            default_model=default_model(provider, capability, resolved),
            embedding_dim=(
                capabilities_of(provider).embedding_dim
                if capability is Capability.EMBEDDINGS
                else None
            ),
            estimated_cost=_cost_of(provider, capability),
        )
        for provider in implemented_and_offerable(capability)
    )


def catalogue(settings: Settings | None = None) -> ProviderCatalogView:
    """Both catalogues in one answer, because the screen configures both."""
    resolved = settings or get_settings()

    return ProviderCatalogView(
        generation=options_for(Capability.GENERATION, resolved),
        embeddings=options_for(Capability.EMBEDDINGS, resolved),
    )
