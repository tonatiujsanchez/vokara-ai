"""The frontend's copy of the disclosure is the disclosure, byte for byte.

`frontend/tests/setup/markdown.test.tsx` checks that the **complete** text
reaches the screen without loss, which FR-001 requires. To check that, the
frontend needs the text — and a copy of it that drifts would keep asserting
losslessness about a text nobody shows any more.

So the copy is a fixture and this test is its drift check: edit
`DISCLOSURE_BODY_MD` without regenerating the fixture and the backend suite
fails. It is the same mechanism CI already uses across the two roots for
`frontend/openapi.json` (`.github/workflows/ci.yml`), applied to the other
string the frontend cannot generate for itself.

Regenerate with:

    uv run python -c "from app.domain.disclosure import DISCLOSURE_BODY_MD; \
import pathlib; \
pathlib.Path('../frontend/tests/fixtures/disclosure.md').write_text(DISCLOSURE_BODY_MD)"
"""

from __future__ import annotations

from pathlib import Path

from app.domain.disclosure import DISCLOSURE_BODY_MD

FIXTURE = Path(__file__).resolve().parents[3] / "frontend" / "tests" / "fixtures" / "disclosure.md"


def test_the_frontend_fixture_is_the_current_disclosure() -> None:
    """Not «contains», not «starts with»: the same bytes.

    FR-001 is about the complete text, so anything weaker here would let the
    frontend prove losslessness over a subset.
    """
    assert FIXTURE.exists(), f"the frontend fixture is missing: {FIXTURE}"

    assert FIXTURE.read_text(encoding="utf-8") == DISCLOSURE_BODY_MD, (
        "the disclosure changed and frontend/tests/fixtures/disclosure.md did not; "
        "regenerate it (see this module's docstring)"
    )
