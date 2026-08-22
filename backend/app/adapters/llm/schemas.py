"""Schemas of the preflight, and the criterion that decides whether it passed.

**The approval criterion is not that the parse works.** It is that the model
returns `null` in the absent fields instead of inventing plausible values. That
is exactly the failure mode art. IV exists to prevent: a provider that fills
optionals with invented text does not break the parse, it produces claims with
nothing to support them — which is why ADR-011 gives it its own column in the
matrix and why the preflight measures the same thing the pipeline measures
(research R-05, R-23, contracts/llm-extraction.md §0).

The schema is **nested** for the same reason. A flat schema reveals nothing:
almost any model satisfies it. The nesting is what makes the test resemble the
real extraction, and the optionals are what remove any structural pressure to
fill a hole — returning `null` is a valid answer, and no field accepts sentinel
values like "N/A" or "Desconocido".

**Optional is not the default here; it is a claim about the sample.** A field is
optional when the sample CV genuinely lacks it, and required when it contains
it. That distinction is the measurement: making a present field optional lets a
model drop it and take the holes with it, which is how two of the five
expectations once passed over an empty list (see `PreflightWorkExperience`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel, Field


class PreflightWorkExperience(BaseModel):
    """One job. Company and role are REQUIRED, and that is what makes the test bite.

    They were optional once, and it hollowed the measurement out: `_second_job`
    matches on the company name, so a model answering `company=None` produced an
    empty match and two of the five expectations passed **vacuously** — the
    preflight reported «respects nulls» about a job it never found. Required
    fields are what the sample actually contains, so demanding them costs an
    honest model nothing and denies a careless one the empty set.
    """

    company: str = Field(description="Nombre de la empresa.")
    role: str = Field(description="Puesto ocupado.")
    start_date: str | None = Field(
        default=None,
        description="Fecha de inicio en formato YYYY-MM. null si el texto no la menciona.",
    )
    end_date: str | None = Field(
        default=None,
        description="Fecha de fin en formato YYYY-MM. null si el texto no la menciona.",
    )
    achievements: list[str] = Field(
        default_factory=list,
        description="Logros mencionados EXPLÍCITAMENTE. Lista vacía si no hay ninguno.",
    )


class PreflightEducation(BaseModel):
    """The institution is in the sample; the degree deliberately is not."""

    institution: str = Field(description="Nombre de la institución.")
    degree: str | None = Field(
        default=None,
        description="Título obtenido. null si el texto no lo menciona.",
    )


class PreflightExtraction(BaseModel):
    """What the model is asked to return for the generation preflight."""

    full_name: str | None = Field(
        default=None, description="Nombre completo. null si el texto no lo menciona."
    )
    email: str | None = Field(
        default=None, description="Correo electrónico. null si el texto no lo menciona."
    )
    phone: str | None = Field(
        default=None, description="Teléfono. null si el texto no lo menciona."
    )
    years_of_experience: int | None = Field(
        default=None,
        description=(
            "Años de experiencia SOLO si el texto lo indica de forma explícita. "
            "No lo calcules ni lo estimes: si no está escrito, devuelve null."
        ),
    )
    experiences: list[PreflightWorkExperience] = Field(default_factory=list)
    education: list[PreflightEducation] = Field(default_factory=list)
    skills: list[str] = Field(
        default_factory=list, description="Habilidades mencionadas explícitamente."
    )


@dataclass(frozen=True)
class NullExpectation:
    """A hole in the sample CV, and how to check the model left it alone."""

    id: str
    description_es: str
    holds: Callable[[PreflightExtraction], bool]


def _second_job(extraction: PreflightExtraction) -> list[PreflightWorkExperience]:
    """The job of the sample that has neither dates nor achievements.

    No `None` guard, because `company` is required: a model that omits it fails
    the parse instead of quietly emptying this list, which is the difference
    between measuring something and measuring nothing.
    """
    return [
        experience for experience in extraction.experiences if "Soluciones" in experience.company
    ]


# One entry per hole of prompts/preflight_v2.INCOMPLETE_CV_SAMPLE. Each is a
# field the sample does not contain, so any value at all is invented.
NULL_EXPECTATIONS: tuple[NullExpectation, ...] = (
    NullExpectation(
        id="phone_absent",
        description_es="El CV no trae teléfono: el campo debe quedar en null.",
        holds=lambda extraction: extraction.phone is None,
    ),
    NullExpectation(
        id="years_of_experience_not_declared",
        description_es="Los años de experiencia no están declarados: no se calculan.",
        holds=lambda extraction: extraction.years_of_experience is None,
    ),
    NullExpectation(
        id="degree_absent",
        description_es="La educación no menciona título: no se infiere uno.",
        holds=lambda extraction: all(entry.degree is None for entry in extraction.education),
    ),
    NullExpectation(
        id="second_job_without_dates",
        description_es="El segundo empleo no trae fechas: no se estiman.",
        holds=lambda extraction: all(
            job.start_date is None and job.end_date is None for job in _second_job(extraction)
        ),
    ),
    NullExpectation(
        id="second_job_without_achievements",
        description_es="El segundo empleo no lista logros: la lista queda vacía.",
        holds=lambda extraction: all(not job.achievements for job in _second_job(extraction)),
    ),
)


def unmet_null_expectations(extraction: PreflightExtraction) -> tuple[NullExpectation, ...]:
    """The holes the model filled in. Empty means the capability is verified.

    Returned rather than raised because the caller has to distinguish «this
    provider invents» from «this provider failed»: the first is a capability
    result, the second is an error (FR-007).
    """
    return tuple(
        expectation for expectation in NULL_EXPECTATIONS if not expectation.holds(extraction)
    )


class EmbeddingsPreflightProbe(BaseModel):
    """The result of the embeddings probe: a vector came back, of this size.

    The dimension is the whole point. It is persisted as the verified dimension
    of that configuration so that a future change is detectable and
    re-embeddable, never a silent corruption (ADR-003, FR-007.2).
    """

    requested_dimensions: int
    observed_dimensions: int

    @property
    def matches_request(self) -> bool:
        return self.requested_dimensions == self.observed_dimensions
