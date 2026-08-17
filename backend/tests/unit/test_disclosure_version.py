"""Editing the disclosure costs a new version, and an old yes does not cover it.

Two guarantees, and the first one is the unusual one: the digest of the text is
pinned here next to the version it belongs to. Change a word of the body without
moving the version and this test fails, which is the only mechanism that makes
`disclosure_version` mean something — otherwise it is a string that drifts away
from the text it names while every acknowledgement keeps saying "accepted"
(research R-29, FR-048).

The four mandatory points of FR-001 are checked as content, not as shape: art. V
forbids burying the disclosure, and a text that lost the paragraph about
unencrypted files would still be a perfectly well-formed text.
"""

from __future__ import annotations

import hashlib

import pytest

from app.domain.disclosure import CURRENT_DISCLOSURE, DISCLOSURE_BODY_MD, DISCLOSURE_VERSION

# version -> sha256 of the body that version names. Adding a row here is part of
# changing the text; editing an existing row is what this test exists to catch.
PUBLISHED_DIGESTS: dict[str, str] = {
    "2026-08-17": "8c069d4f6d45593021dba035ce777a626c415781e581e913f30a8eac747bb093",
}


def digest_of(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def test_the_current_text_matches_the_digest_of_its_version() -> None:
    assert DISCLOSURE_VERSION in PUBLISHED_DIGESTS, (
        "The disclosure changed version without publishing the digest of the new "
        "text. Add the row to PUBLISHED_DIGESTS (research R-29)."
    )
    assert digest_of(DISCLOSURE_BODY_MD) == PUBLISHED_DIGESTS[DISCLOSURE_VERSION], (
        "The disclosure text changed but its version did not. An acknowledgement "
        "of that version would claim to cover a text nobody accepted: bump "
        "DISCLOSURE_VERSION and publish its digest (FR-001, FR-002)."
    )


@pytest.mark.parametrize(
    ("point", "must_contain"),
    [
        # (a) the data stays on the machine
        ("qué se queda", "no salen de esta máquina"),
        # (b) the single exception, with what is sent and when
        ("la única excepción", "El contenido de tu CV"),
        ("cuándo se envía", "cuando lo subes y se procesa"),
        # (c) nothing travels to the makers of Vokara
        ("cero telemetría", "Cero telemetría"),
        # (d) files are left unencrypted, with the actionable recommendation
        ("archivos sin cifrar", "**en claro**"),
        ("cifrado de disco", "cifrado de disco de tu"),
    ],
)
def test_the_text_covers_the_four_mandatory_points(point: str, must_contain: str) -> None:
    assert must_contain in DISCLOSURE_BODY_MD, f"The disclosure lost point «{point}» (FR-001)"


def test_the_text_names_the_three_disk_encryption_tools_the_user_may_have() -> None:
    """«Activa el cifrado de disco» is advice; naming the tool is a next step."""
    for tool in ("FileVault", "BitLocker", "LUKS"):
        assert tool in DISCLOSURE_BODY_MD


def test_it_promises_a_new_acknowledgement_when_what_is_sent_changes() -> None:
    """The promise is the reason the version exists; it is written down."""
    assert "te lo volveremos a mostrar" in DISCLOSURE_BODY_MD


def test_the_body_is_the_whole_text_and_not_a_link_to_it() -> None:
    """Art. V: never only a link, never only the README."""
    assert len(DISCLOSURE_BODY_MD) > 1_000
    assert "http://" not in DISCLOSURE_BODY_MD
    assert "https://" not in DISCLOSURE_BODY_MD


def test_an_acknowledgement_of_the_current_version_covers_it() -> None:
    assert CURRENT_DISCLOSURE.covers(DISCLOSURE_VERSION) is True


@pytest.mark.parametrize("acknowledged", [None, "", "2026-01-01", "2026-08-16"])
def test_no_other_acknowledgement_covers_it(acknowledged: str | None) -> None:
    """An acknowledgement of an older text is a yes to something else."""
    assert CURRENT_DISCLOSURE.covers(acknowledged) is False
