"""The prompt of the generation preflight, version 1.

The material is synthetic and written by the team: it is a fixture of the
repository, never a real CV, and the same rule that governs the golden set
applies here (FR-047).

What this prompt asks for is not «parse this». It asks the model to leave
absent data absent, which is the single behaviour the preflight measures
(research R-23, ADR-011).

**v2 separates the instruction from the material.** v1 concatenated them into a
single user message, which handed the model the REGLA CRÍTICA as ordinary text
and diverged from the empirical verification behind the ADR-011 row — that one
always sent the rule as a system instruction. A test that does not run what the
product runs cannot certify it (art. VI).
"""

from __future__ import annotations

PREFLIGHT_PROMPT_VERSION = "preflight_v2"

PREFLIGHT_INSTRUCTIONS_ES = (
    "Extraes información de un CV a un esquema estructurado.\n"
    "REGLA CRÍTICA: si un dato NO aparece de forma explícita en el texto, el "
    "campo DEBE quedar en null (o lista vacía). Nunca infieras, estimes ni "
    "inventes un valor plausible. Es preferible un campo vacío a un dato no "
    "verificable."
)

# Deliberately incomplete, and every hole is a measurement:
#   - no phone number
#   - no declared years of experience
#   - a second job with neither dates nor achievements
#   - an education entry with no degree
INCOMPLETE_CV_SAMPLE = """
María López Hernández
maria.lopez@example.com

EXPERIENCIA

Desarrolladora Backend — Tecnologías del Norte
2021-03 a 2024-06
- Reduje el tiempo de respuesta de la API de 800ms a 210ms
- Migré el sistema de pagos a una arquitectura de eventos

Desarrolladora Junior — Soluciones Integrales
Participé en el mantenimiento de aplicaciones internas.

EDUCACIÓN

Universidad Autónoma de Guerrero

HABILIDADES
Python, FastAPI, PostgreSQL, Docker
"""

# Short and unremarkable on purpose: what the embeddings probe measures is that
# a vector comes back and with which dimension, not what the text says.
EMBEDDINGS_PROBE_TEXT = "Prueba de dimensión del vector."

# Embeddings take no prompt, but `llm_call_logs.prompt_version` is not
# nullable and a trace without a version cannot be compared with another. In
# this feature the only embeddings call is the probe (research R-12), so the
# version of the probe is the honest answer.
EMBEDDINGS_PROBE_VERSION = "embeddings_probe_v1"


def build_preflight_prompt() -> str:
    """The material the model works on: the sample CV and nothing else.

    The instruction travels beside it as `PREFLIGHT_INSTRUCTIONS_ES`, in the
    `instructions` parameter of the port. Keeping them apart is the whole of v2.
    """
    return INCOMPLETE_CV_SAMPLE
