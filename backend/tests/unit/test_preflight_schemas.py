"""The preflight schema must make «leave it empty» a valid answer.

If any field were required, a model would have to put something there, and the
preflight would be measuring compliance instead of honesty. These tests fix the
property the schema exists for and check that the criterion catches an inventing
provider (art. IV, contracts/llm-extraction.md §0).
"""

from __future__ import annotations

import pytest

from app.adapters.llm.prompts.preflight_v1 import (
    INCOMPLETE_CV_SAMPLE,
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
def test_the_model_is_never_forced_to_fill_anything(schema: type) -> None:
    """An empty instance validates: returning nothing is a legal answer."""
    assert schema()


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
    assert PREFLIGHT_PROMPT_VERSION == "preflight_v1"
    assert INCOMPLETE_CV_SAMPLE in prompt
    assert "null" in prompt


def test_the_embeddings_probe_reports_the_dimension_it_actually_got() -> None:
    assert EmbeddingsPreflightProbe(
        requested_dimensions=768, observed_dimensions=768
    ).matches_request
    assert not EmbeddingsPreflightProbe(
        requested_dimensions=768, observed_dimensions=3072
    ).matches_request
