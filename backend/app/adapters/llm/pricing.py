"""Estimated cost per provider, shown *before* the API key is asked for.

In local execution the budget stops being the project's: it is information the
user needs in order to decide, and asking for a credit card without saying
first what it will cost is exactly the surprise art. V exists to avoid (FR-005,
roadmap §11.3).

Two rules of shape carry the requirement:

- **Generation and embeddings are estimated and shown separately.** Adding them
  up would suggest that changing the embeddings provider moves the bill, when
  what moves it is generation: their orders of magnitude do not resemble each
  other (ADR-011, research R-27).
- **A figure never travels without its assumption.** A monthly estimate with no
  usage assumption in view is not information, it is a number to argue with —
  so `usage_assumption_es` is not optional decoration, and the invariant is
  tested.

**Scope, explicitly.** Research R-27 puts the *calculation* of these figures in
step 10 of the roadmap, outside this spec: what is fixed here is where they
live, what shape they have and when they are shown, so that filling them in is
editing data and not touching the UI. Every row therefore ships with its
estimate pending, and the catalogue endpoint renders that state honestly rather
than inventing a plausible number — the same rule art. IV applies to the CV
applies to what Vokara says about itself.

Rows exist for every provider of the closed list, not only the offerable ones,
so that verifying a provider stays a one-line change in `capabilities.py`
without leaving an option on screen with no cost beside it.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.adapters.llm.capabilities import CAPABILITY_MATRIX, ProviderId
from app.domain.capability import Capability


@dataclass(frozen=True)
class CapabilityPricing:
    """What the wizard shows next to one option, before asking for the key."""

    provider: ProviderId
    capability: Capability

    # Cost of a month of active search. `None` while the calculation of
    # roadmap step 10 is pending; the UI says so instead of showing a figure.
    estimated_monthly_usd: Decimal | None
    # The usage that produces the figure above, in plain Spanish, so the number
    # can be interpreted rather than believed.
    usage_assumption_es: str | None

    # Whether the provider has a free tier at all, and where it ends. The flag
    # is a fact of the provider; the text is part of the pending calculation.
    has_free_tier: bool | None
    free_tier_es: str | None

    @property
    def is_estimated(self) -> bool:
        return self.estimated_monthly_usd is not None


def _pending(
    provider: ProviderId, capability: Capability, *, has_free_tier: bool | None = None
) -> CapabilityPricing:
    return CapabilityPricing(
        provider=provider,
        capability=capability,
        estimated_monthly_usd=None,
        usage_assumption_es=None,
        has_free_tier=has_free_tier,
        free_tier_es=None,
    )


# Google carries `has_free_tier=True` because that is a documented fact and the
# reason it is the suggested default: it is the only one whose free tier is
# enough to use Vokara for real without a card, and for a public that may be
# without income that is not a cost advantage, it is the difference between
# being able to use it and not (ADR-003, research R-27).
PRICING_CATALOGUE: tuple[CapabilityPricing, ...] = (
    _pending(ProviderId.GOOGLE, Capability.GENERATION, has_free_tier=True),
    _pending(ProviderId.GOOGLE, Capability.EMBEDDINGS, has_free_tier=True),
    _pending(ProviderId.OPENAI, Capability.GENERATION),
    _pending(ProviderId.OPENAI, Capability.EMBEDDINGS),
    # No row for Anthropic embeddings: they do not offer the capability, so
    # there is nothing to price (ADR-011).
    _pending(ProviderId.ANTHROPIC, Capability.GENERATION),
    _pending(ProviderId.DEEPSEEK, Capability.GENERATION),
    _pending(ProviderId.DEEPSEEK, Capability.EMBEDDINGS),
    _pending(ProviderId.MOONSHOT, Capability.GENERATION),
    _pending(ProviderId.MOONSHOT, Capability.EMBEDDINGS),
)

_BY_OPTION: dict[tuple[ProviderId, Capability], CapabilityPricing] = {
    (row.provider, row.capability): row for row in PRICING_CATALOGUE
}


def pricing_for(provider: ProviderId, capability: Capability) -> CapabilityPricing | None:
    """The cost of one option, or None when the provider does not offer it."""
    return _BY_OPTION.get((provider, capability))


def priced_options(capability: Capability) -> tuple[CapabilityPricing, ...]:
    """Every option of one capability that has a price row, in matrix order."""
    return tuple(
        row
        for matrix_row in CAPABILITY_MATRIX
        if (row := pricing_for(matrix_row.provider, capability)) is not None
    )
