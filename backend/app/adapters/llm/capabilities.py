"""The capability matrix of ADR-011, declared as immutable data.

Article XI asks that capabilities be *declared*, so a missing one degrades in
an informed way instead of surfacing halfway through a parse. Declaring them as
data rather than as behaviour is what lets the preflight and the future
diagnostics screen **read a table** instead of walking special cases scattered
around the code, and turns «add a verified provider» into a data change plus an
implementation of the port (research R-22).

`verified_on` is a date and not a boolean on purpose. ADR-011 is explicit that
the matrix «no vale más que la verificación que la respalda»: a row without a
date is not offered at all (FR-009), and an old date is a reason to test again.
Providers change models, deprecate endpoints and alter their structured-output
support without notice.

`respects_null_in_optionals` earns its own column for the same reason it earns
its own paragraph in the ADR: a provider that fills absent optionals with
plausible text does not break the parse, it produces claims with nothing behind
them, which is the failure art. IV exists to prevent.

This module and `factory.py` are the only two places where a provider name may
appear (art. XI, verified by tests/architecture/test_provider_name_isolation.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from app.domain.capability import Capability


class ProviderId(StrEnum):
    """The closed list of ADR-011.

    Closed, and not a free-form endpoint, because the preflight cannot verify
    the unknown: the list is precisely what allows saying in advance what will
    work and what will not. Opening it up is a decision for a later version,
    which is why the ports already admit `base_url` and an optional credential.
    """

    GOOGLE = "google"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    MOONSHOT = "moonshot"


@dataclass(frozen=True)
class ProviderCapabilities:
    """What a provider offers, as measured — never as assumed.

    `None` means «not verified» and is not a synonym for `False`: Anthropic
    declaring `embeddings=False` is a statement about their catalogue, while a
    `None` is a statement about ours.
    """

    provider: ProviderId
    structured_output: bool | None
    respects_null_in_optionals: bool | None
    embeddings: bool | None
    embedding_dim: int | None
    verified_on: date | None


# Re-verified on 2026-08-21 with scripts/verify_providers.py, after the script
# and the product preflight were made to run the SAME test: identical schema,
# identical prompt sent as a system instruction, identical criterion. The
# 2026-08-11 run had certified a test that differed from the one the app ran, so
# the date advances on the strength of the aligned run — the verdict did not
# change (`null` respected in all five holes, 2.1 s, embeddings MRL-truncated to
# 768). The model is `settings.google_model`; a different one of the same
# provider is NOT covered by this row (see ADR-011, «Decisión diferida»).
_GOOGLE_VERIFIED_ON = date(2026, 8, 21)

CAPABILITY_MATRIX: tuple[ProviderCapabilities, ...] = (
    ProviderCapabilities(
        provider=ProviderId.GOOGLE,
        structured_output=True,
        respects_null_in_optionals=True,
        embeddings=True,
        embedding_dim=768,
        verified_on=_GOOGLE_VERIFIED_ON,
    ),
    ProviderCapabilities(
        provider=ProviderId.OPENAI,
        structured_output=None,
        respects_null_in_optionals=None,
        embeddings=None,
        embedding_dim=None,
        verified_on=None,
    ),
    ProviderCapabilities(
        provider=ProviderId.ANTHROPIC,
        structured_output=None,
        respects_null_in_optionals=None,
        # Not «unverified»: they do not offer an embeddings model at all. This
        # single cell is the reason generation and embeddings are configured
        # independently — otherwise choosing Claude would silently cost the
        # semantic matching (ADR-011).
        embeddings=False,
        embedding_dim=None,
        verified_on=None,
    ),
    ProviderCapabilities(
        provider=ProviderId.DEEPSEEK,
        structured_output=None,
        respects_null_in_optionals=None,
        embeddings=None,
        embedding_dim=None,
        verified_on=None,
    ),
    ProviderCapabilities(
        provider=ProviderId.MOONSHOT,
        structured_output=None,
        respects_null_in_optionals=None,
        embeddings=None,
        embedding_dim=None,
        verified_on=None,
    ),
)

_BY_PROVIDER: dict[ProviderId, ProviderCapabilities] = {
    row.provider: row for row in CAPABILITY_MATRIX
}


def capabilities_of(provider: ProviderId) -> ProviderCapabilities:
    """The declared row of a provider. Every member of the closed list has one."""
    return _BY_PROVIDER[provider]


def declares_capability(provider: ProviderId, capability: Capability) -> bool:
    """Whether the provider offers the capability at all, verified or not.

    Only `False` denies it. `None` means nobody measured it yet, and treating
    «unverified» as «does not exist» would quietly shrink the closed list.
    """
    row = capabilities_of(provider)
    if capability is Capability.EMBEDDINGS:
        return row.embeddings is not False
    return row.structured_output is not False


def _supports(row: ProviderCapabilities, capability: Capability) -> bool:
    match capability:
        case Capability.GENERATION:
            # Structured output alone is not enough: a provider that invents
            # values in absent optionals is not offerable for extraction.
            return bool(row.structured_output) and bool(row.respects_null_in_optionals)
        case Capability.EMBEDDINGS:
            return bool(row.embeddings)


def offerable_for(capability: Capability) -> tuple[ProviderCapabilities, ...]:
    """The catalogue the user may choose from, for one capability.

    Two filters, and the order matters for what it says: first «has this been
    verified», then «does it do this». A provider missing from the answer is
    missing because nobody measured it, not because it failed (FR-009).
    """
    return tuple(
        row
        for row in CAPABILITY_MATRIX
        if row.verified_on is not None and _supports(row, capability)
    )
