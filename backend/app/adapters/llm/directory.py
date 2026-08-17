"""How each provider is presented, and where its key is obtained.

The capability matrix answers «what does this provider do»; this answers «what
does the candidate see and where do they get the key». They are separate modules
because they change for different reasons: a row of the matrix moves when
someone verifies a capability empirically (ADR-011), a row here moves when a
provider renames a console.

It lives in `adapters/llm/` for the usual reason — it is made of provider names,
and that is the one place they may appear (art. XI). The service hands the
frontend the finished option, so the frontend never branches by provider
(`contracts/openapi.yaml`, ProviderOption).

Rows exist for every provider of the closed list, not only the offerable ones,
so that verifying one stays a one-line change in `capabilities.py` without
leaving an option on screen with no name and no link beside it.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.adapters.llm.capabilities import ProviderId


@dataclass(frozen=True)
class ProviderProfile:
    """What the wizard shows about one provider, before asking for anything."""

    provider: ProviderId
    display_name: str
    # Where the key is obtained, so the candidate does not have to search for
    # it. The URL travels to the frontend and also into the actionable message
    # of `PROVIDER_CREDENTIAL_REJECTED` (contracts/errors.md).
    credential_url: str
    # Gemini is preselected for both capabilities, and the reason is on screen:
    # it is the only one whose free tier is enough to use Vokara for real
    # without a card (ADR-003). Preselected, never imposed — the rest are shown
    # as equals, not as second-class options (roadmap §11.2).
    is_suggested_default: bool


PROVIDER_DIRECTORY: tuple[ProviderProfile, ...] = (
    ProviderProfile(
        provider=ProviderId.GOOGLE,
        display_name="Google Gemini",
        credential_url="https://aistudio.google.com/apikey",
        is_suggested_default=True,
    ),
    ProviderProfile(
        provider=ProviderId.OPENAI,
        display_name="OpenAI",
        credential_url="https://platform.openai.com/api-keys",
        is_suggested_default=False,
    ),
    ProviderProfile(
        provider=ProviderId.ANTHROPIC,
        display_name="Anthropic Claude",
        credential_url="https://console.anthropic.com/settings/keys",
        is_suggested_default=False,
    ),
    ProviderProfile(
        provider=ProviderId.DEEPSEEK,
        display_name="DeepSeek",
        credential_url="https://platform.deepseek.com/api_keys",
        is_suggested_default=False,
    ),
    ProviderProfile(
        provider=ProviderId.MOONSHOT,
        display_name="Kimi (Moonshot)",
        credential_url="https://platform.moonshot.ai/console/api-keys",
        is_suggested_default=False,
    ),
)

_BY_PROVIDER: dict[ProviderId, ProviderProfile] = {row.provider: row for row in PROVIDER_DIRECTORY}


def profile_of(provider: ProviderId) -> ProviderProfile:
    """The presentation row of a provider. Every member of the closed list has one."""
    return _BY_PROVIDER[provider]


def console_url_of(provider: str) -> str | None:
    """Where to check a rejected key, from the identifier a service holds.

    Takes the plain string because that is what crosses the boundary from the
    request body and from the database, and answers `None` for anything outside
    the closed list rather than raising: an actionable message is better without
    a link than not sent at all.
    """
    try:
        return profile_of(ProviderId(provider)).credential_url
    except ValueError:
        return None
