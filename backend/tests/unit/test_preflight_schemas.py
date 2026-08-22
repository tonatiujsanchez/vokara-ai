"""The preflight schema must make «leave it empty» a valid answer — where the CV is empty.

A field the sample CV does not contain is optional, so a model is never forced
to invent it: that is the property the preflight exists to measure, and making
it required would measure compliance instead of honesty.

A field the sample **does** contain is required, and that is the other half.
`company` and `role` were optional once, and it hollowed the measurement out:
two of the five expectations look up the second job by company name, so a model
answering `company=None` produced an empty match and both expectations passed
over an empty list. The preflight then reported «respects nulls» about a job it
never found — which is how it came to disagree with the empirical verification
behind the ADR-011 row (art. IV, contracts/llm-extraction.md §0).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.adapters.llm.prompts.preflight_v2 import (
    INCOMPLETE_CV_SAMPLE,
    PREFLIGHT_INSTRUCTIONS_ES,
    PREFLIGHT_PROMPT_VERSION,
    build_preflight_prompt,
)
from app.adapters.llm.schemas import (
    NULL_EXPECTATIONS,
    EmbeddingsPreflightProbe,
    PreflightEducation,
    PreflightExtraction,
    PreflightWorkExperience,
    unmet_null_expectations,
)

# Fields the sample CV does NOT contain: a model must be free to leave them out.
OPTIONAL_BY_ABSENCE = {
    PreflightExtraction: ("full_name", "email", "phone", "years_of_experience"),
    PreflightWorkExperience: ("start_date", "end_date", "achievements"),
    PreflightEducation: ("degree",),
}

# Fields the sample DOES contain, and which the expectations match on. Optional
# here is not generosity: it is an escape hatch out of being measured.
REQUIRED_BY_PRESENCE = {
    PreflightExtraction: (),
    PreflightWorkExperience: ("company", "role"),
    PreflightEducation: ("institution",),
}

SCHEMAS = (PreflightExtraction, PreflightWorkExperience, PreflightEducation)


def _well_behaved() -> PreflightExtraction:
    """What the sample CV actually says, and nothing more."""
    return PreflightExtraction(
        full_name="María López Hernández",
        email="maria.lopez@example.com",
        experiences=[
            PreflightWorkExperience(
                company="Tecnologías del Norte",
                role="Desarrolladora Backend",
                start_date="2021-03",
                end_date="2024-06",
                achievements=["Reduje el tiempo de respuesta de la API de 800ms a 210ms"],
            ),
            PreflightWorkExperience(
                company="Soluciones Integrales",
                role="Desarrolladora Junior",
            ),
        ],
        education=[PreflightEducation(institution="Universidad Autónoma de Guerrero")],
        skills=["Python", "FastAPI", "PostgreSQL", "Docker"],
    )


@pytest.mark.parametrize("schema", SCHEMAS, ids=lambda schema: schema.__name__)
def test_nothing_the_cv_omits_is_ever_forced(schema: type) -> None:
    """Every hole of the sample is optional: inventing is never the only way out."""
    fields = schema.model_fields
    for name in OPTIONAL_BY_ABSENCE[schema]:
        assert not fields[name].is_required(), f"{schema.__name__}.{name} forces an answer"


@pytest.mark.parametrize("schema", SCHEMAS, ids=lambda schema: schema.__name__)
def test_what_the_cv_does_contain_is_required(schema: type) -> None:
    """Optional here would let a model drop the field and take the holes with it."""
    fields = schema.model_fields
    for name in REQUIRED_BY_PRESENCE[schema]:
        assert fields[name].is_required(), f"{schema.__name__}.{name} can be dropped"


def test_a_job_without_a_company_cannot_dodge_the_expectations() -> None:
    """The regression itself: no company, no match, two expectations passing on air."""
    with pytest.raises(ValidationError):
        PreflightWorkExperience(role="Desarrolladora Junior")  # type: ignore[call-arg]


def test_the_schema_is_nested_because_a_flat_one_reveals_nothing() -> None:
    definitions = PreflightExtraction.model_json_schema()["$defs"]
    assert {"PreflightWorkExperience", "PreflightEducation"} <= set(definitions)


def test_an_honest_answer_meets_every_expectation() -> None:
    assert unmet_null_expectations(_well_behaved()) == ()


@pytest.mark.parametrize(
    ("expectation_id", "invented"),
    [
        ("phone_absent", {"phone": "+52 55 1234 5678"}),
        ("years_of_experience_not_declared", {"years_of_experience": 5}),
    ],
)
def test_an_invented_scalar_is_caught(expectation_id: str, invented: dict[str, object]) -> None:
    extraction = _well_behaved().model_copy(update=invented)
    assert [failure.id for failure in unmet_null_expectations(extraction)] == [expectation_id]


def test_an_invented_degree_is_caught() -> None:
    extraction = _well_behaved().model_copy(
        update={"education": [PreflightEducation(institution="UAGro", degree="Licenciatura")]}
    )
    assert [failure.id for failure in unmet_null_expectations(extraction)] == ["degree_absent"]


def test_invented_dates_and_achievements_on_the_second_job_are_caught() -> None:
    honest = _well_behaved()
    second = honest.experiences[1].model_copy(
        update={
            "start_date": "2019-01",
            "end_date": "2021-02",
            "achievements": ["Mejoré procesos internos"],
        }
    )
    extraction = honest.model_copy(update={"experiences": [honest.experiences[0], second]})

    assert [failure.id for failure in unmet_null_expectations(extraction)] == [
        "second_job_without_dates",
        "second_job_without_achievements",
    ]


def test_every_expectation_explains_itself_in_spanish() -> None:
    """The wizard shows why a provider was rejected, not an id (art. IX)."""
    assert len(NULL_EXPECTATIONS) == 5
    assert len({expectation.id for expectation in NULL_EXPECTATIONS}) == 5
    for expectation in NULL_EXPECTATIONS:
        assert expectation.description_es.endswith(".")


def test_the_sample_cv_keeps_the_holes_the_expectations_measure() -> None:
    """Completing the sample would turn the criterion into a formality."""
    assert "Soluciones Integrales" in INCOMPLETE_CV_SAMPLE
    assert "Universidad Autónoma de Guerrero" in INCOMPLETE_CV_SAMPLE
    # No phone number anywhere in the sample.
    assert not any(
        character.isdigit() for character in INCOMPLETE_CV_SAMPLE.split("HABILIDADES")[1]
    )


def test_the_prompt_carries_its_version_and_the_sample() -> None:
    prompt = build_preflight_prompt()
    assert PREFLIGHT_PROMPT_VERSION == "preflight_v2"
    assert INCOMPLETE_CV_SAMPLE in prompt
    # v2 keeps the rule OUT of the prompt: it travels as a system instruction,
    # which is how the verification behind the ADR-011 row always sent it.
    assert "null" in PREFLIGHT_INSTRUCTIONS_ES
    assert PREFLIGHT_INSTRUCTIONS_ES not in prompt


def test_the_embeddings_probe_reports_the_dimension_it_actually_got() -> None:
    assert EmbeddingsPreflightProbe(
        requested_dimensions=768, observed_dimensions=768
    ).matches_request
    assert not EmbeddingsPreflightProbe(
        requested_dimensions=768, observed_dimensions=3072
    ).matches_request
