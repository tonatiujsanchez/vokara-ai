"""The mail port, deliberately able to do only one thing in 001 (ADR-012, R-26).

`verify_label` and nothing else. The candidate's App Password grants access to
their **entire** mailbox, and what Vokara does with that access is restricted to
checking that the label they designated exists and can be reached. Reading that
label and ingesting job alerts is the sources feature (F1.3.2), out of scope
here — and until it arrives, a port that cannot read a message is a stronger
guarantee than a promise that it will not.

**The scope restriction lives in the implementation, and its tests are
compliance tests, not functional ones**: they verify that no IMAP query leaves
without a label restriction. Widening the read scope is a privacy incident, not
a feature, so it is guarded by a test that fails rather than by a code review
that might not happen (ADR-012).

The credential is not in this signature, for the same reason it is absent from
the LLM ports: it is configuration of the implementation. It reaches the
implementation from local configuration, never from the database (FR-013).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, runtime_checkable


class EmailFailure(StrEnum):
    """Why linking failed, classified by the adapter that tried it.

    Three cases and three different messages, for the same reason the preflight
    has four: «tu contraseña es incorrecta» about an unreachable server sends the
    candidate to regenerate a password that works (contracts/errors.md).
    """

    APP_PASSWORD_REJECTED = "app_password_rejected"  # noqa: S105 — a name, not a value
    LABEL_NOT_FOUND = "label_not_found"
    UNREACHABLE = "unreachable"


class EmailPortError(Exception):
    """A classified failure, carrying no text from the provider.

    The server's message can quote the account back — and, on some servers, the
    credential — so it stops here. What crosses the boundary is the
    classification (FR-008, FR-013).
    """

    def __init__(self, failure: EmailFailure) -> None:
        super().__init__(f"email verification failed: {failure.value}")
        self.failure = failure


@runtime_checkable
class EmailPort(Protocol):
    """Everything Vokara may do with a linked mailbox in this feature.

    One method, and it returns nothing: there is no shape in this interface for
    a message, a subject or a sender to travel through.
    """

    def verify_label(self, label: str) -> None: ...
