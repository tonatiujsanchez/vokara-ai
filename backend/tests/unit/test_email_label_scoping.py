"""A compliance test of ADR-012, not a functional one.

What it verifies is a promise Vokara makes and Google does not enforce: an App
Password opens the **whole** mailbox, and the restriction to the designated label
is a discipline of this code. FR-012 requires disclosing exactly that to the
candidate — «un compromiso de Vokara verificado por sus propias pruebas, no un
límite que Google imponga» — so the test is what makes the sentence true.

It is checked twice on purpose:

- **behaviourally**, over a recording double, so a command that escaped the label
  would show up in the transcript;
- **structurally**, over the source, because the day someone adds a `select` and
  a `fetch` to read the alerts, the behavioural test of *this* operation might
  still pass while the module has grown the ability to read everything.

Widening the read scope is a privacy incident, not a feature. That is the whole
reason this file exists.
"""

from __future__ import annotations

import ast
import builtins
import importlib
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import SecretStr

from app.adapters.email.base import EmailPort

ADAPTER_MODULE = "app.adapters.email.gmail_imap"
ADAPTER_SOURCE = (
    Path(__file__).resolve().parents[2] / "app" / "adapters" / "email" / "gmail_imap.py"
)

A_LABEL = "Alertas de empleo"
AN_ADDRESS = "candidata@example.com"
AN_APP_PASSWORD = "abcd efgh ijkl mnop"

# Everything IMAP offers for reading, moving or deleting mail. None of it has
# any business in a feature whose only job is «does this label exist».
FORBIDDEN_COMMANDS: tuple[str, ...] = (
    "select",
    "examine",
    "search",
    "fetch",
    "store",
    "copy",
    "move",
    "append",
    "uid",
    "expunge",
    "delete",
)


class RecordingImap:
    """A double that answers like a server and remembers everything it was asked."""

    def __init__(self, mailboxes: tuple[str, ...] = (A_LABEL,)) -> None:
        self.mailboxes = mailboxes
        self.commands: builtins.list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def _record(self, name: str, *args: object, **kwargs: object) -> None:
        self.commands.append((name, args, kwargs))

    def login(self, user: str, password: str) -> tuple[str, builtins.list[bytes]]:
        self._record("login", user, password)
        return "OK", [b"LOGIN completed"]

    def list(
        self, directory: str = '""', pattern: str = "*"
    ) -> tuple[str, builtins.list[bytes | None]]:
        self._record("list", directory, pattern)
        wanted = pattern.strip('"')
        matches: builtins.list[bytes | None] = [
            f'(\\HasNoChildren) "/" "{mailbox}"'.encode()
            for mailbox in self.mailboxes
            if mailbox == wanted
        ]
        return ("OK", matches) if matches else ("OK", [None])

    def logout(self) -> tuple[str, builtins.list[bytes]]:
        self._record("logout")
        return "BYE", [b"logging out"]

    def __getattr__(self, name: str) -> Callable[..., tuple[str, builtins.list[bytes]]]:
        """Any other IMAP command is recorded too, so nothing can slip through."""

        def command(*args: object, **kwargs: object) -> tuple[str, builtins.list[bytes]]:
            self._record(name, *args, **kwargs)
            return "OK", []

        return command


def build_port(connection: RecordingImap) -> EmailPort:
    module = importlib.import_module(ADAPTER_MODULE)
    port: EmailPort = module.GmailImapEmailPort(
        address=AN_ADDRESS,
        credential=SecretStr(AN_APP_PASSWORD),
        connection_factory=lambda: connection,
    )
    return port


def test_no_imap_query_leaves_without_the_designated_label() -> None:
    """The transcript of a successful verification, command by command."""
    connection = RecordingImap()

    build_port(connection).verify_label(A_LABEL)

    issued = [name for name, _, _ in connection.commands]
    assert issued == ["login", "list", "logout"]

    _, args, kwargs = connection.commands[1]
    pattern = str(kwargs.get("pattern", args[1] if len(args) > 1 else ""))
    assert A_LABEL in pattern


def test_not_a_single_command_that_could_read_a_message_is_ever_issued() -> None:
    """Checked over a failure too: the unhappy path is where scope leaks."""
    connection = RecordingImap(mailboxes=("Otra etiqueta",))
    module = importlib.import_module(ADAPTER_MODULE)

    with pytest.raises(module.EmailPortError):
        build_port(connection).verify_label(A_LABEL)

    issued = {name.lower() for name, _, _ in connection.commands}
    assert not issued & set(FORBIDDEN_COMMANDS)


def test_a_label_with_a_wildcard_is_refused_instead_of_sent() -> None:
    """`*` in an IMAP pattern matches every mailbox: that is the scope escape."""
    connection = RecordingImap()
    module = importlib.import_module(ADAPTER_MODULE)

    for wildcard in ("*", "%", "Alertas*", "%empleo"):
        with pytest.raises(module.EmailPortError):
            build_port(connection).verify_label(wildcard)

    assert "list" not in [name for name, _, _ in connection.commands]


def test_the_module_contains_no_call_that_could_read_mail() -> None:
    """The structural half: what the module *can* do, not just what it did."""
    tree = ast.parse(ADAPTER_SOURCE.read_text(encoding="utf-8"), filename=str(ADAPTER_SOURCE))

    called = {
        node.func.attr.lower()
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert not called & set(FORBIDDEN_COMMANDS), (
        "The mail adapter grew a command that can reach beyond the designated "
        f"label (ADR-012): {sorted(called & set(FORBIDDEN_COMMANDS))}"
    )


def test_the_port_exposes_no_way_to_read_anything() -> None:
    """A method that cannot exist cannot be called by mistake later."""
    module = importlib.import_module(ADAPTER_MODULE)
    port = module.GmailImapEmailPort(
        address=AN_ADDRESS,
        credential=SecretStr(AN_APP_PASSWORD),
        connection_factory=lambda: RecordingImap(),
    )

    public = {name for name in dir(port) if not name.startswith("_")}

    assert public == {"verify_label"}
