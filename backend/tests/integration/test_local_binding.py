"""The two binding tests the ADR-008 requires. Neither replaces the other.

Without authentication, where the instance listens is the only access control
there is, and `ufw` does not protect a port published by Docker: the rules
Docker writes in the DOCKER chain of the nat table are evaluated first
(research R-20).

The asymmetry that makes both necessary: inside the container uvicorn MUST bind
0.0.0.0 or the Docker proxy cannot reach it, so under Compose the protection is
the port mapping alone. Running the API directly on the machine is the other
mode, and there the bind is the protection.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

from app.core.config import get_settings

INFRA = Path(__file__).resolve().parents[3] / "infra"
COMPOSE_FILE = INFRA / "docker-compose.yml"
OVERRIDE_FILE = INFRA / "docker-compose.override.yml"


def _compose_files() -> list[Path]:
    assert COMPOSE_FILE.is_file(), f"No existe {COMPOSE_FILE.name}"
    return [path for path in (COMPOSE_FILE, OVERRIDE_FILE) if path.is_file()]


def _iter_port_entries(compose: Path) -> Iterator[tuple[str, Any]]:
    document: dict[str, Any] = yaml.safe_load(compose.read_text(encoding="utf-8")) or {}
    services: dict[str, Any] = document.get("services") or {}
    for name, service in services.items():
        for entry in (service or {}).get("ports") or []:
            yield name, entry


def _host_ip_of(entry: Any) -> str | None:  # noqa: ANN401 — a YAML node is arbitrary
    """Extract the host IP of a `ports:` entry, or None when it declares none.

    Short syntax: "127.0.0.1:8000:8000", "[::1]:8000:8000", "8000:8000", "8000".
    Long syntax: a mapping with an optional `host_ip` key.
    """
    if isinstance(entry, dict):
        host_ip = entry.get("host_ip")
        return str(host_ip) if host_ip is not None else None

    text = str(entry)
    if text.startswith("["):  # bracketed IPv6
        closing = text.find("]")
        return text[1:closing] if closing != -1 else None

    parts = text.split(":")
    return parts[0] if len(parts) >= 3 else None


def test_compose_publishes_only_on_loopback() -> None:
    """Every published port pins an explicit loopback host IP.

    Fails with "8000:8000" — Docker assumes 0.0.0.0 for the short form — and
    with an explicit "0.0.0.0:8000:8000".
    """
    offenders: list[str] = []

    for compose in _compose_files():
        for service, entry in _iter_port_entries(compose):
            host_ip = _host_ip_of(entry)
            location = f"{compose.name}: servicio {service}: {entry!r}"
            if host_ip is None:
                offenders.append(f"{location} — sin IP de host explícita")
                continue
            try:
                parsed = ipaddress.ip_address(host_ip)
            except ValueError:
                offenders.append(f"{location} — IP de host no válida: {host_ip!r}")
                continue
            if not parsed.is_loopback:
                offenders.append(f"{location} — {host_ip} no es loopback")

    assert not offenders, "Puertos publicados fuera de loopback (ADR-008):\n" + "\n".join(offenders)


def test_api_host_setting_resolves_to_loopback() -> None:
    """The host configured for uvicorn outside Docker resolves to loopback.

    "localhost" passes (127.0.0.1 and ::1); "0.0.0.0" fails, because it is
    unspecified, not loopback.
    """
    host = get_settings().api_host

    resolved = {info[4][0] for info in socket.getaddrinfo(host, None)}
    assert resolved, f"{host!r} no resuelve a ninguna dirección"

    not_loopback = [
        address for address in resolved if not ipaddress.ip_address(address).is_loopback
    ]
    assert not not_loopback, (
        f"api_host={host!r} resuelve a direcciones que no son loopback: {sorted(not_loopback)}"
    )
