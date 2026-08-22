"""App Password + IMAP, restricted to the label the candidate designated.

The only operation is «does this label exist and can it be reached», because
that is all FR-013 needs before taking the link as established, and because in
001 there is nothing to read yet: ingesting the alerts is the sources feature
(F1.3.2). `imaplib` from the standard library — no dependency for one LIST.

**The restriction is a discipline of this module and Google does not enforce
it.** An App Password grants the whole mailbox. So the pattern of every query is
the designated label, wildcards are refused instead of sent — `*` and `%` in an
IMAP pattern match every mailbox, which is the concrete way a scope restriction
escapes — and `tests/unit/test_email_label_scoping.py` fails if a command that
could read mail ever appears here. FR-012 makes Vokara tell the candidate
precisely this, and the test is what makes the sentence true rather than
reassuring (ADR-012).

The App Password reaches this module from local configuration and is never
persisted, logged or echoed in an error, exactly like an API key (FR-008,
FR-013).
"""

from __future__ import annotations

import imaplib
from collections.abc import Callable, Sequence
from typing import Protocol

from pydantic import SecretStr

from app.adapters.email.base import EmailFailure, EmailPortError
from app.core.logging import get_logger

logger = get_logger(__name__)

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
CONNECT_TIMEOUT_SECONDS = 15

# In an IMAP LIST pattern these two are wildcards: `%` matches within a level and
# `*` across levels. A label carrying either would turn a scoped query into a
# listing of the whole account, so it never reaches the wire.
PATTERN_WILDCARDS = ("*", "%")

# The disclosure FR-012 requires **before** asking for any credential. It lives
# here, with the provider it talks about, and it names it in full — which the
# error catalogue in `domain/` cannot do (art. XI).
EMAIL_DISCLOSURE_MD = """\
## Antes de vincular tu correo

Vincular es **opcional** y puedes omitirlo con un clic: no bloquea nada del
onboarding ni desactiva ninguna función de esta parte de Vokara.

**Una App Password da acceso a toda tu bandeja.** Google no permite limitarla a
una etiqueta. Que Vokara lea **únicamente** la etiqueta que tú designes es un
compromiso nuestro, verificado por nuestras propias pruebas automáticas, no un
permiso que Google imponga. En esta versión Vokara solo comprueba que la
etiqueta existe: todavía no lee ningún correo.

**Si tu cuenta es de Google Workspace o tiene la Protección Avanzada activada,
las App Passwords están deshabilitadas** y este paso no va a funcionar. Para esas
cuentas la vía es OAuth con un proyecto propio de Google Cloud, y está
documentada como opción avanzada.

Tu App Password se guarda en la configuración local de esta instalación: nunca
en la base de datos, nunca en los registros, nunca en un mensaje de error.
"""

OAUTH_DOCS_URL = "https://developers.google.com/gmail/imap/xoauth2-protocol"
LABEL_HELP_URL = "https://support.google.com/mail/answer/118708"
APP_PASSWORD_HELP_URL = "https://myaccount.google.com/apppasswords"  # noqa: S105 — a URL

VALUE_IF_LINKED_ES = (
    "Vokara podrá leer la etiqueta donde caen tus alertas de empleo y sumar esas "
    "vacantes a tus fuentes, sin que tengas que copiarlas a mano."
)
VALUE_IF_SKIPPED_ES = (
    "No pierdes nada de lo demás: subir tu CV, revisar tu perfil, definir tus objetivos "
    "y confirmarlo funcionan igual. Puedes vincular tu correo más adelante."
)

# The counterpart of the warning of FR-012. Before asking for the App Password
# Vokara says that the password opens the WHOLE mailbox and that reading only
# the designated label is a discipline of ours, not a permission Google
# enforces. A promise made in those terms has to come back answered: WHICH label
# ended up designated, verified to exist and be reachable (FR-013, ADR-012).
#
# The second sentence is the honest half. This feature links the mailbox; it
# reads nothing — vacancy ingestion is out of scope for 001 — and letting the
# candidate assume otherwise would be its own quiet lie.
LINKED_CONFIRMATION_ES = (
    "Listo. Comprobamos que la etiqueta «{label}» existe y es alcanzable en tu cuenta: "
    "es la única que Vokara va a leer. En esta versión todavía no lee ningún correo; "
    "cuando empiece, será solo de esa etiqueta."
)


class ImapConnection(Protocol):
    """The three commands this adapter is allowed to issue, and no others."""

    def login(self, user: str, password: str) -> object: ...

    # The return is `Sequence[object]` because that is all this adapter does
    # with it: ask whether anything came back. Naming the shape of a mailbox
    # listing would be describing data it has no business reading.
    def list(self, directory: str = ..., pattern: str = ...) -> tuple[str, Sequence[object]]: ...

    def logout(self) -> object: ...


def connect_over_tls() -> ImapConnection:
    """A TLS connection to the provider's IMAP endpoint."""
    return imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=CONNECT_TIMEOUT_SECONDS)


def _quoted(label: str) -> str:
    """The label as an IMAP string literal, with nothing left to interpret."""
    escaped = label.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


class GmailImapEmailPort:
    """`EmailPort` over App Password + IMAP, scoped to one label (ADR-012)."""

    def __init__(
        self,
        *,
        address: str,
        credential: SecretStr,
        connection_factory: Callable[[], ImapConnection] = connect_over_tls,
    ) -> None:
        self._address = address
        self._credential = credential
        self._connection_factory = connection_factory

    def verify_label(self, label: str) -> None:
        """Confirm the designated label exists. Raises `EmailPortError` if not.

        Returns nothing on success on purpose: there is no value here that could
        carry the contents of a mailbox back to the caller.
        """
        if not label.strip() or any(wildcard in label for wildcard in PATTERN_WILDCARDS):
            # Refused before the connection: a pattern with a wildcard is not a
            # label, it is a request to list somebody's whole account.
            logger.info("email_label_rejected", reason="wildcard_or_empty")
            raise EmailPortError(EmailFailure.LABEL_NOT_FOUND)

        connection = self._connect()
        try:
            self._login(connection)
            self._assert_label_exists(connection, label)
        finally:
            self._close(connection)

    def _connect(self) -> ImapConnection:
        try:
            return self._connection_factory()
        except OSError as error:
            # No connection says nothing about the password, so it is not
            # reported as a rejection (contracts/errors.md).
            logger.warning("email_provider_unreachable", error_type=type(error).__name__)
            raise EmailPortError(EmailFailure.UNREACHABLE) from None

    def _login(self, connection: ImapConnection) -> None:
        try:
            connection.login(self._address, self._credential.get_secret_value())
        except imaplib.IMAP4.error as error:
            # The server's text can quote the account back, so it stops here:
            # what crosses the boundary is the classification (FR-013).
            logger.info("email_app_password_rejected", error_type=type(error).__name__)
            raise EmailPortError(EmailFailure.APP_PASSWORD_REJECTED) from None
        except OSError as error:
            logger.warning("email_provider_unreachable", error_type=type(error).__name__)
            raise EmailPortError(EmailFailure.UNREACHABLE) from None

    def _assert_label_exists(self, connection: ImapConnection, label: str) -> None:
        try:
            status, mailboxes = connection.list(directory='""', pattern=_quoted(label))
        except (imaplib.IMAP4.error, OSError) as error:
            logger.warning("email_provider_unreachable", error_type=type(error).__name__)
            raise EmailPortError(EmailFailure.UNREACHABLE) from None

        if status != "OK" or not any(mailbox for mailbox in mailboxes):
            # The label name is not logged: it is the candidate's own vocabulary
            # about their job search, which is theirs and not ours (art. V).
            logger.info("email_label_not_found")
            raise EmailPortError(EmailFailure.LABEL_NOT_FOUND)

    def _close(self, connection: ImapConnection) -> None:
        try:
            connection.logout()
        except (imaplib.IMAP4.error, OSError):
            # Failing to say goodbye politely is not a failure of the check.
            logger.info("email_logout_failed")
