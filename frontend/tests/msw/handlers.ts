import { http, HttpResponse, type RequestHandler } from "msw";

import type { components } from "@/api/schema";

import DISCLOSURE_BODY from "../fixtures/disclosure.md?raw";

/**
 * The first-run endpoints, answered the way a fresh installation would.
 *
 * Every shape is typed against the generated schema, never against a hand
 * written copy: rename a field in a Pydantic model and these stop compiling
 * too, which is the only thing that keeps a mock from drifting into a green
 * test over a broken application (art. I).
 *
 * Tests that mount the real route table need these, because the router renders
 * whichever screen the guard sends them to and that screen fetches its own
 * data. `onUnhandledRequest: "error"` makes forgetting one loud.
 */

type SetupState = components["schemas"]["SetupStateModel"];
type Disclosure = components["schemas"]["DisclosureModel"];
type ProviderCatalog = components["schemas"]["ProviderCatalogModel"];
type ProviderOption = components["schemas"]["ProviderOptionModel"];
type EmailStep = components["schemas"]["EmailStepModel"];
type Configuration = components["schemas"]["ProviderConfigurationModel"];

// `exactOptionalPropertyTypes` puts `undefined` in the optional field; the
// wizard only ever deals with a step or its absence.
export type PendingStep = NonNullable<SetupState["pending_step"]> | null;

export const DISCLOSURE_VERSION = "2026-08-17";

export function verifiedConfiguration(
  capability: Configuration["capability"],
): Configuration {
  return {
    capability,
    provider: "proveedor-uno",
    model: "modelo-uno",
    credential_status: "configured",
    is_usable: true,
    degradation_acknowledged_at: null,
    preflight: {
      result: "verified",
      checked_at: "2026-08-20T10:00:00Z",
      message: "Tu API key funciona y este modelo cumple lo que necesitamos.",
      embedding_dim: capability === "embeddings" ? 768 : null,
      affected_features: [],
    },
  };
}

/**
 * A first run stopped at `pending`, with the facts that stopping there implies.
 *
 * Reaching the mail step means generation is already resolved — FR-010 gates it
 * on exactly that — so a fixture that stopped at `email` with no provider
 * configured would describe a state the backend never produces, and any guard
 * tested against it would be tested against fiction.
 */
export function setupState(pending: PendingStep): SetupState {
  const generationResolved = pending === "email" || pending === null;

  return {
    pending_step: pending,
    disclosure_acknowledged: pending !== "disclosure",
    disclosure_acknowledged_at: pending === "disclosure" ? null : "2026-08-20T10:00:00Z",
    providers: {
      generation: generationResolved ? verifiedConfiguration("generation") : null,
      embeddings: pending === null ? verifiedConfiguration("embeddings") : null,
    },
    email_status: pending === null ? "skipped" : "pending",
    is_complete: pending === null,
  };
}

export const disclosure: Disclosure = {
  version: DISCLOSURE_VERSION,
  body_md: DISCLOSURE_BODY,
  acknowledged: false,
  acknowledged_at: null,
  acknowledged_version: null,
};

/**
 * Two providers with a cost each, and neither of them named after a real one.
 *
 * The frontend renders the catalogue it is given and branches on nobody
 * (art. XI), so the fixtures use invented identifiers on purpose: a test that
 * passed only because the option happened to be called "google" would be
 * testing a coupling the code must not have.
 */
export function providerOption(overrides: Partial<ProviderOption> = {}): ProviderOption {
  return {
    provider: "proveedor-uno",
    display_name: "Proveedor Uno",
    is_suggested_default: true,
    credential_url: "https://ejemplo.invalid/llaves",
    default_model: "modelo-uno",
    embedding_dim: null,
    estimated_cost: {
      amount_usd: 4,
      currency: "USD",
      usage_assumption_es: "Supone 40 vacantes analizadas al mes.",
      has_free_tier: true,
      free_tier_note_es: "La capa gratuita cubre las primeras 20.",
      is_estimated: true,
      pending_note_es: null,
    },
    ...overrides,
  };
}

export const SEPARATION_REASON =
  "Se configuran por separado porque son dos capacidades distintas y puedes pagarlas a " +
  "proveedores distintos.";

export function providerCatalog(overrides: Partial<ProviderCatalog> = {}): ProviderCatalog {
  const second = providerOption({
    provider: "proveedor-dos",
    display_name: "Proveedor Dos",
    is_suggested_default: false,
    default_model: "modelo-dos",
  });

  return {
    generation: [providerOption(), second],
    embeddings: [
      providerOption({ embedding_dim: 768 }),
      { ...second, embedding_dim: 1024 },
    ],
    separation_reason_es: SEPARATION_REASON,
    ...overrides,
  };
}

export const EMAIL_DISCLOSURE_MD =
  "## Antes de vincular tu correo\n\nVincular es **opcional** y puedes omitirlo con un clic.\n\n" +
  "**Una App Password da acceso a toda tu bandeja.** Google no permite limitarla a una " +
  "etiqueta.\n\n**Si tu cuenta es de Google Workspace o tiene la Protección Avanzada " +
  "activada, las App Passwords están deshabilitadas** y este paso no va a funcionar.";

export function emailStep(overrides: Partial<EmailStep> = {}): EmailStep {
  return {
    status: "pending",
    disclosure_md: EMAIL_DISCLOSURE_MD,
    oauth_docs_url: "https://ejemplo.invalid/oauth",
    label: null,
    linked_at: null,
    credential_status: "not_configured",
    is_skippable: true,
    value_if_linked_es:
      "Vokara podrá leer la etiqueta donde caen tus alertas de empleo y sumar esas vacantes.",
    value_if_skipped_es:
      "No pierdes nada de lo demás: subir tu CV, revisar tu perfil y confirmarlo funcionan igual.",
    configuration_notice_es: null,
    ...overrides,
  };
}

/** Everything the wizard reads, so any screen the guard picks can render. */
export function firstRunHandlers(pending: PendingStep): RequestHandler[] {
  return [
    http.get("*/api/v1/setup/state", () => HttpResponse.json(setupState(pending))),
    http.get("*/api/v1/setup/disclosure", () => HttpResponse.json(disclosure)),
    http.get("*/api/v1/setup/providers/catalog", () => HttpResponse.json(providerCatalog())),
    http.get("*/api/v1/setup/email", () => HttpResponse.json(emailStep())),
  ];
}
