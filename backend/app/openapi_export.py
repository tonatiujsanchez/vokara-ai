"""Dump the OpenAPI schema without starting a server.

    uv run python -m app.openapi_export > ../frontend/openapi.json

The frontend build must not need a running backend, and CI regenerates this
file and runs `git diff --exit-code`: change an endpoint without regenerating
the client and the PR fails (art. I, research R-16).

The dump is sorted and ends in a newline, so the diff only ever shows real
contract changes and never a reordering.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from app.main import create_app


def build_openapi() -> dict[str, Any]:
    return create_app().openapi()


def dump_openapi() -> str:
    return json.dumps(build_openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> None:
    sys.stdout.write(dump_openapi())


if __name__ == "__main__":
    main()
