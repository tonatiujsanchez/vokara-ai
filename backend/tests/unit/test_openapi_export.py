"""The dump is deterministic, or the drift check is noise (research R-16)."""

from __future__ import annotations

import json
import subprocess
import sys

from app.openapi_export import build_openapi, dump_openapi


def test_two_dumps_are_byte_identical() -> None:
    assert dump_openapi() == dump_openapi()


def test_the_dump_is_sorted_and_ends_in_a_newline() -> None:
    text = dump_openapi()

    assert text.endswith("\n")
    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def test_the_schema_describes_the_health_endpoint() -> None:
    schema = build_openapi()

    assert "/api/v1/health" in schema["paths"]
    assert schema["info"]["title"] == "Vokara API"


def test_running_it_as_a_module_needs_no_server() -> None:
    """This is the command quickstart 2 documents."""
    result = subprocess.run(
        [sys.executable, "-m", "app.openapi_export"],
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )

    assert json.loads(result.stdout)["paths"]["/api/v1/health"]
    assert result.stdout == dump_openapi()
