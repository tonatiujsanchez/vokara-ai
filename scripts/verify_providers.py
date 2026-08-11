"""
Vokara — verificacion empirica de capacidades de proveedores (ADR-011).

Prueba, por cada proveedor con API key configurada:
  1. Que la llave funciona.
  2. Salida estructurada con esquema Pydantic ANIDADO (como el parseo de CV real).
  3. Que respeta None en campos opcionales ausentes en vez de inventarlos.
     -> Es el criterio critico: un proveedor que rellena huecos produce
        afirmaciones sin sustento en el perfil maestro (constitucion art. IV).
  4. Embeddings: disponibilidad y dimension del vector.

Uso:
    pip install "pydantic>=2" langchain-core langchain-google-genai \
        langchain-openai langchain-anthropic langchain-deepseek

    export GOOGLE_API_KEY=...        # opcional, cada uno
    export OPENAI_API_KEY=...
    export ANTHROPIC_API_KEY=...
    export DEEPSEEK_API_KEY=...
    export MOONSHOT_API_KEY=...      # Kimi

    python verify_providers.py

Los proveedores sin llave se saltan. Salida: tabla lista para pegar en
docs/adr/011-proveedores-llm-y-embeddings.md
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# CARGA DE .env
# Busca .env subiendo desde el directorio del script hasta la raiz del repo.
# Usa python-dotenv si esta disponible; si no, hace un parseo minimo propio.
# Las variables ya exportadas en el shell TIENEN PRECEDENCIA sobre el .env.
# ---------------------------------------------------------------------------


def load_dotenv_file() -> str | None:
    from pathlib import Path

    here = Path(__file__).resolve().parent
    for directory in [here, *here.parents]:
        candidate = directory / ".env"
        if candidate.is_file():
            break
    else:
        return None

    try:
        from dotenv import load_dotenv  # type: ignore[import-not-found]

        load_dotenv(candidate, override=False)
        return str(candidate)
    except ImportError:
        pass

    # Fallback sin dependencias
    for raw in candidate.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:  # el shell gana
            os.environ[key] = value
    return str(candidate)


# ---------------------------------------------------------------------------
# ESQUEMA DE PRUEBA
# Anidado y con opcionales, igual que el parseo real del CV. Un esquema plano
# no revela nada: casi cualquier modelo lo cumple.
# ---------------------------------------------------------------------------


class WorkExperience(BaseModel):
    company: str = Field(description="Nombre de la empresa")
    role: str = Field(description="Puesto ocupado")
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
        description="Logros mencionados EXPLICITAMENTE. Lista vacia si no hay ninguno.",
    )


class Education(BaseModel):
    institution: str
    degree: str | None = Field(
        default=None, description="Titulo obtenido. null si el texto no lo menciona."
    )


class CandidateExtract(BaseModel):
    full_name: str | None = Field(
        default=None, description="Nombre completo. null si el texto no lo menciona."
    )
    email: str | None = Field(
        default=None,
        description="Correo electronico. null si el texto no lo menciona.",
    )
    phone: str | None = Field(
        default=None, description="Telefono. null si el texto no lo menciona."
    )
    years_of_experience: int | None = Field(
        default=None,
        description="Anos de experiencia SOLO si el texto lo indica de forma explicita. "
        "No lo calcules ni lo estimes: si no esta escrito, devuelve null.",
    )
    experiences: list[WorkExperience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    skills: list[str] = Field(
        default_factory=list, description="Habilidades mencionadas explicitamente"
    )


SYSTEM_PROMPT = (
    "Extraes informacion de un CV a un esquema estructurado.\n"
    "REGLA CRITICA: si un dato NO aparece de forma explicita en el texto, el campo "
    "DEBE quedar en null (o lista vacia). Nunca infieras, estimes ni inventes un "
    "valor plausible. Es preferible un campo vacio a un dato no verificable."
)

# CV de prueba deliberadamente INCOMPLETO. Los huecos son la prueba:
#   - sin telefono
#   - sin fechas en el segundo empleo
#   - sin anos de experiencia declarados
#   - sin titulo en la educacion
#   - segundo empleo sin logros
TEST_CV = """
Maria Lopez Hernandez
maria.lopez@example.com

EXPERIENCIA

Desarrolladora Backend — Tecnologias del Norte
2021-03 a 2024-06
- Reduje el tiempo de respuesta de la API de 800ms a 210ms
- Migre el sistema de pagos a una arquitectura de eventos

Desarrolladora Junior — Soluciones Integrales
Participe en el mantenimiento de aplicaciones internas.

EDUCACION

Universidad Autonoma de Guerrero

HABILIDADES
Python, FastAPI, PostgreSQL, Docker
"""


# ---------------------------------------------------------------------------
# EVALUACION DE LA RESPUESTA
# ---------------------------------------------------------------------------

# Campos que DEBEN quedar en None/vacio porque no estan en el CV de prueba.
HALLUCINATION_CHECKS: list[tuple[str, Callable[[CandidateExtract], bool]]] = [
    ("phone debe ser None", lambda r: r.phone is None),
    (
        "years_of_experience debe ser None (no esta declarado)",
        lambda r: r.years_of_experience is None,
    ),
    (
        "degree debe ser None (no hay titulo en el CV)",
        lambda r: all(e.degree is None for e in r.education),
    ),
    (
        "2do empleo sin fechas -> start_date y end_date None",
        lambda r: all(
            exp.start_date is None and exp.end_date is None
            for exp in r.experiences
            if "Soluciones" in exp.company
        ),
    ),
    (
        "2do empleo sin logros -> achievements vacio",
        lambda r: all(
            not exp.achievements for exp in r.experiences if "Soluciones" in exp.company
        ),
    ),
]


@dataclass
class Result:
    provider: str
    model: str
    key_ok: bool = False
    structured_ok: bool = False
    null_ok: bool = False
    null_failures: list[str] = field(default_factory=list)
    latency_s: float | None = None
    embeddings: str = "no probado"
    embedding_dim: int | None = None
    error: str = ""


def check_nulls(parsed: CandidateExtract) -> list[str]:
    return [label for label, ok in HALLUCINATION_CHECKS if not ok(parsed)]


# ---------------------------------------------------------------------------
# PROVEEDORES
# ---------------------------------------------------------------------------


def build_chat(provider: str, model: str) -> Any:
    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        # En Gemini 3.x temperature/top_p/top_k estan DEPRECADOS (ago-2026).
        # No se envian para esos modelos; el determinismo del pipeline viene del
        # esquema tipado y de las reglas fuera del LLM, no del parametro.
        if model.startswith(("gemini-3", "gemini-4")):
            return ChatGoogleGenerativeAI(model=model)
        return ChatGoogleGenerativeAI(model=model, temperature=0)
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model, temperature=0)
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model, temperature=0)
    if provider == "deepseek":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            temperature=0,
            base_url="https://api.deepseek.com/v1",
            api_key=os.environ["DEEPSEEK_API_KEY"],
        )
    if provider == "moonshot":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            temperature=0,
            base_url="https://api.moonshot.ai/v1",
            api_key=os.environ["MOONSHOT_API_KEY"],
        )
    raise ValueError(provider)


def probe_embeddings(provider: str, model: str | None) -> tuple[str, int | None]:
    if model is None:
        return ("No ofrece", None)
    try:
        if provider == "google":
            from langchain_google_genai import GoogleGenerativeAIEmbeddings

            # gemini-embedding-001 y -2 devuelven 3072 dims por defecto, pero
            # soportan truncado MRL a 768/1536 sin perdida relevante de calidad.
            # 768 ahorra ~4x de espacio en pgvector.
            try:
                emb = GoogleGenerativeAIEmbeddings(
                    model=model, output_dimensionality=768
                )
            except TypeError:
                emb = GoogleGenerativeAIEmbeddings(model=model)
        elif provider == "openai":
            from langchain_openai import OpenAIEmbeddings

            emb = OpenAIEmbeddings(model=model)
        elif provider == "deepseek":
            return ("No ofrece", None)
        elif provider == "moonshot":
            return ("No ofrece", None)
        else:
            return ("No ofrece", None)

        vec = emb.embed_query("prueba de dimension del vector")
        return ("OK", len(vec))
    except Exception as exc:  # noqa: BLE001
        return (f"ERROR: {type(exc).__name__}", None)


# provider -> (env var de la llave, modelo de chat por defecto, modelo de embeddings o None)
#
# Los nombres de modelo cambian seguido. Puedes sobreescribir cualquiera sin
# editar este archivo:
#     export VOKARA_GOOGLE_MODEL=gemini-3.5-flash-lite
#     export VOKARA_GOOGLE_EMBED=gemini-embedding-2
PROVIDERS: dict[str, tuple[str, str, str | None]] = {
    "google": ("GOOGLE_API_KEY", "gemini-3.6-flash", "models/gemini-embedding-001"),
    "openai": ("OPENAI_API_KEY", "gpt-4o-mini", "text-embedding-3-small"),
    "anthropic": ("ANTHROPIC_API_KEY", "claude-sonnet-4-5-20250929", None),
    "deepseek": ("DEEPSEEK_API_KEY", "deepseek-chat", None),
    "moonshot": ("MOONSHOT_API_KEY", "kimi-k2-turbo-preview", None),
}


def resolve_models(provider: str) -> tuple[str, str, str | None]:
    """Aplica overrides por variable de entorno sobre los defaults."""
    env_var, chat_model, emb_model = PROVIDERS[provider]
    up = provider.upper()
    chat_model = os.environ.get(f"VOKARA_{up}_MODEL", chat_model)
    emb_override = os.environ.get(f"VOKARA_{up}_EMBED")
    if emb_override:
        emb_model = emb_override
    return env_var, chat_model, emb_model


def verify(provider: str) -> Result | None:
    env_var, chat_model, emb_model = resolve_models(provider)
    if not os.environ.get(env_var):
        print(f"  [skip] {provider}: falta {env_var}")
        return None

    res = Result(provider=provider, model=chat_model)
    print(f"\n== {provider} ({chat_model}) ==")

    try:
        llm = build_chat(provider, chat_model)
        extractor = llm.with_structured_output(CandidateExtract)

        start = time.perf_counter()
        parsed = extractor.invoke(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": TEST_CV},
            ]
        )
        res.latency_s = round(time.perf_counter() - start, 2)
        res.key_ok = True

        if not isinstance(parsed, CandidateExtract):
            parsed = CandidateExtract.model_validate(parsed)
        res.structured_ok = True
        print(f"  salida estructurada: OK ({res.latency_s}s)")

        res.null_failures = check_nulls(parsed)
        res.null_ok = not res.null_failures
        if res.null_ok:
            print("  respeta null en opcionales: OK")
        else:
            print("  respeta null en opcionales: FALLA")
            for f in res.null_failures:
                print(f"    - {f}")

        print(f"  experiencias extraidas: {len(parsed.experiences)}")
        print(f"  skills extraidas: {len(parsed.skills)}")

    except Exception as exc:  # noqa: BLE001
        res.error = f"{type(exc).__name__}: {exc}"
        print(f"  ERROR: {res.error[:200]}")
        low = str(exc).lower()
        if "not_found" in low or "404" in low or "does not exist" in low:
            print(
                f"  -> El modelo '{chat_model}' no existe o fue retirado.\n"
                f"     Consulta los vigentes y reintenta con:\n"
                f"     export VOKARA_{provider.upper()}_MODEL=<modelo-vigente>"
            )
        elif "api key" in low or "401" in low or "unauthorized" in low:
            print(f"  -> Revisa que {env_var} sea correcta y este activa.")

    res.embeddings, res.embedding_dim = probe_embeddings(provider, emb_model)
    print(f"  embeddings: {res.embeddings} (dim={res.embedding_dim})")
    return res


def render_table(results: list[Result]) -> str:
    today = date.today().isoformat()
    lines = [
        "| Proveedor | Modelo | Salida estructurada | Respeta null | Embeddings | Dim | Verificado |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        struct = "Si" if r.structured_ok else ("No" if r.key_ok else "error de llave")
        nulls = "Si" if r.null_ok else ("No" if r.structured_ok else "n/a")
        dim = str(r.embedding_dim) if r.embedding_dim else "n/a"
        lines.append(
            f"| {r.provider} | `{r.model}` | {struct} | {nulls} | {r.embeddings} | {dim} | {today} |"
        )
    return "\n".join(lines)


def main() -> None:
    print("Vokara — verificacion de proveedores (ADR-011)\n")
    env_path = load_dotenv_file()
    if env_path:
        print(f"Variables cargadas de: {env_path}\n")
    else:
        print("No se encontro .env; usando solo variables del shell.\n")
    results: list[Result] = []
    for provider in PROVIDERS:
        r = verify(provider)
        if r:
            results.append(r)

    if not results:
        print("\nNo se probo ningun proveedor. Configura al menos una API key.")
        return

    print("\n\n--- Pega esto en docs/adr/011-proveedores-llm-y-embeddings.md ---\n")
    print(render_table(results))
    print()

    blocked = [r for r in results if r.structured_ok and not r.null_ok]
    if blocked:
        print("ATENCION — proveedores que inventan datos en campos ausentes:")
        for r in blocked:
            print(f"  {r.provider}: {', '.join(r.null_failures)}")
        print(
            "\nUn proveedor que rellena huecos produce afirmaciones sin sustento en el\n"
            "perfil maestro. Antes de habilitarlo en el wizard, prueba reforzando el\n"
            "prompt; si persiste, no debe ofrecerse como opcion (art. IV + FR-009)."
        )


if __name__ == "__main__":
    main()