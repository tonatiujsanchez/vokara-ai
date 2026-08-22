import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";

import type { components } from "@/api/schema";

import {
  disclosure,
  emailStep,
  providerCatalog,
  DISCLOSURE_VERSION,
} from "../msw/handlers";
import { server } from "../msw/server";
import { renderAt } from "./renderWithClient";

type Configuration = components["schemas"]["ProviderConfigurationModel"];
type SetupState = components["schemas"]["SetupStateModel"];
type Capability = Configuration["capability"];

const VERIFIED_GENERATION = "Tu API key quedó verificada: la salida estructurada funciona.";
const VERIFIED_EMBEDDINGS = "Tu API key quedó verificada: los embeddings funcionan.";
const UNVERIFIED = "Tu API key funciona, pero este modelo no garantiza la salida estructurada.";
const REJECTED = "Tu proveedor rechazó la API key.";
const QUOTA = "Tu API key es válida, pero alcanzaste el límite de tu cuota.";

function verified(capability: Capability): Configuration {
  return {
    capability,
    provider: "proveedor-uno",
    model: capability === "embeddings" ? "modelo-embeddings" : "modelo-uno",
    credential_status: "configured",
    is_usable: true,
    degradation_acknowledged_at: null,
    preflight: {
      result: "verified",
      checked_at: "2026-08-21T10:00:00Z",
      message: capability === "embeddings" ? VERIFIED_EMBEDDINGS : VERIFIED_GENERATION,
      embedding_dim: capability === "embeddings" ? 768 : null,
      affected_features: [],
      degradation_reasons: [],
    },
  };
}

function unverified(capability: Capability): Configuration {
  return {
    capability,
    provider: "proveedor-uno",
    model: "modelo-uno",
    credential_status: "configured",
    is_usable: false,
    degradation_acknowledged_at: null,
    preflight: {
      result: "capability_unverified",
      checked_at: "2026-08-21T10:00:00Z",
      message: UNVERIFIED,
      embedding_dim: null,
      affected_features: [
        { code: "CV_PARSING", message: "Sembrar tu perfil desde el CV puede fallar." },
      ],
      degradation_reasons: ["El CV no trae teléfono: el campo debe quedar en null."],
    },
  };
}

/**
 * `pending_step` derived exactly as `app/domain/setup.py` derives it.
 *
 * A fixture with a frozen step could never reproduce this bug: the whole
 * mechanism is that resolving a capability MOVES the step, and the guard
 * follows it. Hardcoding the answer would test a backend that does not exist.
 */
type PendingStep = NonNullable<SetupState["pending_step"]>;

function pendingStepOf(providers: SetupState["providers"]): PendingStep {
  if (providers.generation?.is_usable !== true) return "providers";
  if (providers.embeddings?.is_usable !== true) return "providers";
  return "email";
}

/** A server that remembers, and that answers each capability what a test tells it to. */
function serverAnswering(answers: Partial<Record<Capability, Configuration | number>>): void {
  const stored: SetupState["providers"] = { generation: null, embeddings: null };

  server.use(
    http.get("*/api/v1/setup/state", () => {
      const pending = pendingStepOf(stored);
      return HttpResponse.json({
        pending_step: pending,
        disclosure_acknowledged: true,
        disclosure_acknowledged_at: "2026-08-20T10:00:00Z",
        providers: stored,
        email_status: "pending",
        is_complete: false,
      } satisfies SetupState);
    }),
    http.get("*/api/v1/setup/disclosure", () =>
      HttpResponse.json({ ...disclosure, acknowledged: true, acknowledged_version: DISCLOSURE_VERSION }),
    ),
    http.get("*/api/v1/setup/providers/catalog", () => HttpResponse.json(providerCatalog())),
    http.get("*/api/v1/setup/email", () => HttpResponse.json(emailStep())),
    http.put("*/api/v1/setup/providers/:capability", ({ params }) => {
      const capability = String(params["capability"]) as Capability;
      const answer = answers[capability];
      if (typeof answer === "number") {
        return HttpResponse.json(
          {
            code: answer === 402 ? "PROVIDER_QUOTA_EXCEEDED" : "PROVIDER_CREDENTIAL_REJECTED",
            message: answer === 402 ? QUOTA : REJECTED,
            details: null,
          },
          { status: answer },
        );
      }
      const configuration = answer ?? verified(capability);
      stored[capability] = configuration;
      return HttpResponse.json(configuration);
    }),
  );
}

async function verifyWithOneKey(): Promise<void> {
  const user = userEvent.setup();
  await screen.findByRole("heading", { level: 1, name: /Tus proveedores de IA/ });
  await user.type(screen.getByLabelText("API key"), "una-llave-cualquiera");
  await user.click(screen.getByRole("button", { name: "Verificar mi llave" }));
}

function stillOnProviders(): void {
  expect(
    screen.getByRole("heading", { level: 1, name: /Tus proveedores de IA/ }),
  ).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: /Vincular tu correo/ })).not.toBeInTheDocument();
}

describe("el paso de proveedores nunca avanza solo (FR-007, art. X)", () => {
  beforeEach(() => {
    serverAnswering({});
  });

  it("muestra el resultado verificado de AMBAS capacidades y no navega", async () => {
    renderAt("/setup/providers");
    await verifyWithOneKey();

    // The regression: resolving the last capability turns pending_step into
    // `email`, and a guard that follows pending_step took the screen away
    // before the candidate could read either result.
    expect(await screen.findByText(VERIFIED_GENERATION)).toBeInTheDocument();
    expect(screen.getByText(VERIFIED_EMBEDDINGS)).toBeInTheDocument();
    // FR-007.2: the verified dimension is part of the result, and it is the
    // thing a candidate has no other way to check.
    expect(screen.getByText(/768/)).toBeInTheDocument();
    stillOnProviders();
  });

  it("muestra la degradación con su motivo y espera el acuse", async () => {
    serverAnswering({ generation: unverified("generation") });

    renderAt("/setup/providers");
    await verifyWithOneKey();

    expect(await screen.findByText(UNVERIFIED)).toBeInTheDocument();
    expect(screen.getByText(/El CV no trae teléfono/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Entiendo lo que pierdo/ }),
    ).toBeInTheDocument();
    stillOnProviders();
  });

  it("muestra la llave rechazada y no navega", async () => {
    serverAnswering({ generation: 401, embeddings: 401 });

    renderAt("/setup/providers");
    await verifyWithOneKey();

    // Both capabilities were configured with the same key, so both report it.
    expect(await screen.findAllByText(REJECTED)).toHaveLength(2);
    stillOnProviders();
  });

  it("muestra la cuota agotada y no navega", async () => {
    serverAnswering({ generation: 402, embeddings: 402 });

    renderAt("/setup/providers");
    await verifyWithOneKey();

    // Both capabilities were configured with the same key, so both report it.
    expect(await screen.findAllByText(QUOTA)).toHaveLength(2);
    stillOnProviders();
  });

  it("solo avanza cuando el candidato lo pide (art. X)", async () => {
    renderAt("/setup/providers");
    await verifyWithOneKey();
    await screen.findByText(VERIFIED_GENERATION);
    stillOnProviders();

    await userEvent.setup().click(screen.getByRole("button", { name: "Continuar" }));

    expect(await screen.findByRole("heading", { name: /Vincular tu correo/ })).toBeInTheDocument();
  });
});
