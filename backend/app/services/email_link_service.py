"""Linking the mailbox, and skipping it — two equally valid endings (FR-011).

The step is optional and **visibly** optional: skipping is one action, it never
blocks the onboarding and it disables nothing in this feature. That is why
`skip` is a first-class operation here and not the absence of one, and why the
view carries what is gained by linking *and* what is not lost by skipping: a
candidate deciding between two options deserves both halves of the sentence.

The App Password follows the rules of an API key exactly (FR-013 defers to
FR-008): local configuration, never the database, never a log, never an error
message. What `setup_state` records is the **state** of the step and the name of
the designated label, and nothing else.

Failures arrive already classified from the adapter and are translated here into
the three codes of the catalogue. None of them blocks anything: each message
either leads somewhere concrete or reminds the candidate that skipping is a way
out (contracts/errors.md).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from pydantic import SecretStr

from app.adapters.email.base import EmailFailure, EmailPort, EmailPortError
from app.adapters.email.gmail_imap import (
    EMAIL_DISCLOSURE_MD,
    LABEL_HELP_URL,
    LINKED_CONFIRMATION_ES,
    OAUTH_DOCS_URL,
    VALUE_IF_LINKED_ES,
    VALUE_IF_SKIPPED_ES,
    GmailImapEmailPort,
)
from app.core.config import Settings, get_settings
from app.core.credentials import (
    WizardCredential,
    WizardSetting,
    read_credential,
    write_credential,
    write_setting,
)
from app.db.repositories.setup_state_repository import SetupStateRepository
from app.db.session import session_scope
from app.domain.errors import (
    EmailAppPasswordRejectedError,
    EmailLabelNotFoundError,
    EmailProviderUnreachableError,
)
from app.domain.setup import CredentialStatus, EmailStepStatus

SHADOWED_MESSAGE_ES = (
    "Esta App Password también está definida en tu configuración de entorno "
    "(GMAIL_APP_PASSWORD); Vokara usará la que acabas de configurar aquí."
)


@dataclass(frozen=True)
class EmailStepView:
    """The step as the wizard renders it, disclosure included (FR-011, FR-012).

    `disclosure_md` travels with the state and not behind a second request
    because FR-012 requires it to be read **before** any credential is asked
    for: something that arrives after the form is not a warning, it is a note.
    """

    status: EmailStepStatus
    disclosure_md: str
    oauth_docs_url: str
    label: str | None
    linked_at: datetime | None
    credential_status: CredentialStatus
    value_if_linked_es: str
    value_if_skipped_es: str
    # What the candidate is owed once the link succeeds: which label was
    # verified, named, and what Vokara does with it today. `None` in every other
    # state — there is nothing to confirm about a step that was skipped or never
    # taken (FR-013, ADR-012).
    linked_confirmation_es: str | None = None
    configuration_notice_es: str | None = None
    # Always true (FR-011). A field and not a constant so the contract can state
    # it and the frontend can render the two options with the same weight.
    is_skippable: bool = True


PortFactory = Callable[[str, SecretStr], EmailPort]


def _build_port(address: str, credential: SecretStr) -> EmailPort:
    return GmailImapEmailPort(address=address, credential=credential)


def _shadow_notice(settings: Settings) -> str | None:
    """The same honesty the provider step owes: say when two values collide."""
    return SHADOWED_MESSAGE_ES if settings.gmail_app_password is not None else None


def read_step(candidate_id: UUID, settings: Settings | None = None) -> EmailStepView:
    """The state of the step, with everything the screen needs to decide."""
    resolved = settings or get_settings()

    with session_scope() as session:
        row = SetupStateRepository(session).for_candidate(candidate_id)
        status = EmailStepStatus(row.email_step_status) if row else EmailStepStatus.PENDING
        label = row.email_label if row else None
        linked_at = row.email_linked_at if row else None

    stored = read_credential(WizardCredential.GMAIL_APP_PASSWORD, resolved)
    configured = stored is not None or resolved.gmail_app_password is not None

    return EmailStepView(
        status=status,
        disclosure_md=EMAIL_DISCLOSURE_MD,
        oauth_docs_url=OAUTH_DOCS_URL,
        label=label,
        linked_at=linked_at,
        credential_status=(
            CredentialStatus.CONFIGURED if configured else CredentialStatus.NOT_CONFIGURED
        ),
        value_if_linked_es=VALUE_IF_LINKED_ES,
        value_if_skipped_es=VALUE_IF_SKIPPED_ES,
        linked_confirmation_es=(
            LINKED_CONFIRMATION_ES.format(label=label)
            if status is EmailStepStatus.LINKED and label is not None
            else None
        ),
    )


def link(
    candidate_id: UUID,
    *,
    address: str,
    app_password: SecretStr,
    label: str,
    settings: Settings | None = None,
    port_factory: PortFactory | None = None,
) -> EmailStepView:
    """Verify the designated label exists, and only then call it linked (FR-013).

    Written to local configuration before the check, like an API key, so a
    provider that could not be reached can be retried without typing sixteen
    characters again. A link that was not verified is never recorded: the
    candidate would believe a source is feeding them and it would not be.
    """
    resolved = settings or get_settings()

    write_setting(WizardSetting.GMAIL_ADDRESS, address, resolved)
    write_credential(WizardCredential.GMAIL_APP_PASSWORD, app_password, resolved)

    # Resolved here rather than as a default argument, so replacing
    # `_build_port` in this module reaches the call made through an endpoint.
    factory: PortFactory = port_factory or _build_port
    try:
        factory(address, app_password).verify_label(label)
    except EmailPortError as error:
        raise _translated(error) from None

    with session_scope() as session:
        SetupStateRepository(session).record_email_linked(candidate_id, label=label)

    return replace(
        read_step(candidate_id, resolved), configuration_notice_es=_shadow_notice(resolved)
    )


def skip(candidate_id: UUID, settings: Settings | None = None) -> EmailStepView:
    """Skip the step. A valid ending, not a lesser one (FR-011).

    It erases the label and the linking date, which the database also enforces:
    a skipped step must leave no configuration behind, so nothing can later read
    as half-linked.
    """
    with session_scope() as session:
        SetupStateRepository(session).record_email_skipped(candidate_id)

    return read_step(candidate_id, settings)


def _translated(error: EmailPortError) -> Exception:
    """One code per failure, because they lead to three different next steps."""
    match error.failure:
        case EmailFailure.APP_PASSWORD_REJECTED:
            return EmailAppPasswordRejectedError(oauth_docs_url=OAUTH_DOCS_URL)
        case EmailFailure.LABEL_NOT_FOUND:
            return EmailLabelNotFoundError(help_url=LABEL_HELP_URL)
        case EmailFailure.UNREACHABLE:
            return EmailProviderUnreachableError()
