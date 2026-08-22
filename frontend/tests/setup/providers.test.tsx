import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";

import type { components } from "@/api/schema";
import { ProvidersScreen } from "@/features/setup/providers/ProvidersScreen";

import { SEPARATION_REASON, providerCatalog, providerOption, setupState } from "../msw/handlers";
import { server } from "../msw/server";
import { renderWithClient } from "./renderWithClient";

type Configuration = components["schemas"]["ProviderConfigurationModel"];
type SetupState = components["schemas"]["SetupStateModel"];

function verified(capability: Configuration["capability"]): Configuration {
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

function stateWith(providers: SetupState["providers"]): void {
  server.use(
    http.get("*/api/v1/setup/state", () =>
      HttpResponse.json({ ...setupState("providers"), providers }),
    ),
  );
}

/**
 * A server that remembers, so the screen sees what a real one would.
 *
 * The step renders the configuration the **server** holds, not what a mutation
 * happened to return, so a stub that always answered «nothing configured» would
 * hide the fact that saving a key changes anything.
 */
function rememberingServer(): { calls: { capability: string; body: unknown }[] } {
  const stored: SetupState["providers"] = { generation: null, embeddings: null };
  const calls: { capability: string; body: unknown }[] = [];

  server.use(
    http.get("*/api/v1/setup/state", () =>
      HttpResponse.json({ ...setupState("providers"), providers: stored }),
    ),
    http.put("*/api/v1/setup/providers/:capability", async ({ params, request }) => {
      const capability = String(params["capability"]) as Configuration["capability"];
      calls.push({ capability, body: await request.json() });
      stored[capability] = verified(capability);
      return HttpResponse.json(stored[capability]);
    }),
  );

  return { calls };
}

beforeEach(() => {
  server.use(
    http.get("*/api/v1/setup/providers/catalog", () => HttpResponse.json(providerCatalog())),
    http.get("*/api/v1/setup/state", () => HttpResponse.json(setupState("providers"))),
  );
});

describe("paso de proveedores", () => {
  it("presenta dos configuraciones separadas con la razón de la separación (FR-004, US1 AC3)", async () => {
    renderWithClient(<ProvidersScreen />);

    expect(await screen.findByRole("heading", { name: "Generación" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Embeddings" })).toBeInTheDocument();
    expect(screen.getByText(SEPARATION_REASON)).toBeInTheDocument();
  });

  it("preselecciona la opción que el backend marca como sugerida", async () => {
    renderWithClient(<ProvidersScreen />);

    const suggested = await screen.findAllByRole("radio", { name: /Proveedor Uno/ });
    for (const option of suggested) expect(option).toBeChecked();
  });

  it("muestra el costo estimado de cada capacidad ANTES de pedir ninguna llave (FR-005)", async () => {
    renderWithClient(<ProvidersScreen />);

    const costs = await screen.findAllByText(/al mes/);
    const keyField = screen.getByLabelText("API key");

    // Comprobado por posición en el DOM, no por prosa: un costo que aparece
    // debajo del campo que debía informar llega tarde para informar nada.
    expect(costs.length).toBeGreaterThanOrEqual(2);
    for (const cost of costs) {
      expect(cost.compareDocumentPosition(keyField) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
  });

  it("muestra el supuesto de uso junto a la cifra, para que sea interpretable", async () => {
    renderWithClient(<ProvidersScreen />);

    expect(await screen.findAllByText(/Supone 40 vacantes analizadas al mes/)).not.toHaveLength(0);
  });

  it("dice que el costo está pendiente en vez de inventar una cifra (art. IV)", async () => {
    server.use(
      http.get("*/api/v1/setup/providers/catalog", () => {
        const pending = providerOption({
          estimated_cost: {
            amount_usd: null,
            currency: "USD",
            usage_assumption_es: null,
            has_free_tier: null,
            free_tier_note_es: null,
            is_estimated: false,
            pending_note_es: "Todavía no publicamos el costo estimado de este proveedor.",
          },
        });
        return HttpResponse.json({
          generation: [pending],
          embeddings: [pending],
          separation_reason_es: SEPARATION_REASON,
        });
      }),
    );

    renderWithClient(<ProvidersScreen />);

    expect(await screen.findAllByText(/Todavía no publicamos el costo/)).not.toHaveLength(0);
    expect(screen.queryByText(/al mes/)).not.toBeInTheDocument();
  });
});

describe("el mismo proveedor para las dos capacidades (FR-004, US1 AC4)", () => {
  it("pide una sola llave y verifica cada capacidad por separado con ella", async () => {
    const user = userEvent.setup();
    const { calls } = rememberingServer();

    renderWithClient(<ProvidersScreen />);

    // Ambas capacidades apuntan al proveedor sugerido: un solo campo.
    const field = await screen.findByLabelText("API key");
    expect(screen.queryByLabelText(/API key de generación/)).not.toBeInTheDocument();

    await user.type(field, "una-llave");
    await user.click(screen.getByRole("button", { name: /Verificar mi llave/ }));

    await screen.findAllByText(/Tu API key funciona/);

    expect(calls.map((call) => call.capability)).toEqual(["generation", "embeddings"]);
    expect(calls.map((call) => call.body)).toEqual([
      { provider: "proveedor-uno", api_key: "una-llave" },
      { provider: "proveedor-uno", api_key: "una-llave" },
    ]);
  });

  it("pide una llave por capacidad en cuanto los proveedores difieren", async () => {
    const user = userEvent.setup();
    renderWithClient(<ProvidersScreen />);

    const embeddings = await screen.findByRole("group", { name: "Embeddings" });
    await user.click(within(embeddings).getByRole("radio", { name: /Proveedor Dos/ }));

    expect(screen.queryByLabelText("API key")).not.toBeInTheDocument();
    expect(screen.getByLabelText(/API key de generación/)).toBeInTheDocument();
    expect(screen.getByLabelText(/API key de embeddings/)).toBeInTheDocument();
  });
});

describe("el gate de FR-010", () => {
  it("no deja continuar mientras generación no esté resuelta", async () => {
    renderWithClient(<ProvidersScreen />);

    expect(await screen.findByRole("button", { name: "Continuar" })).toBeDisabled();
  });

  it("deja continuar con generación resuelta aunque embeddings siga sin configurar", async () => {
    stateWith({ generation: verified("generation"), embeddings: null });

    renderWithClient(<ProvidersScreen />);

    expect(await screen.findByRole("button", { name: "Continuar" })).toBeEnabled();
    expect(screen.getByText(/no bloquea nada/)).toBeInTheDocument();  // FR-010, informada
  });

  it("sin el acuse de degradación no se puede avanzar; con él, sí (FR-007.3, SC-016)", async () => {
    const degraded: Configuration = {
      ...verified("generation"),
      is_usable: false,
      preflight: {
        result: "capability_unverified",
        checked_at: "2026-08-20T10:00:00Z",
        message: "Tu API key funciona, pero este modelo no garantiza la salida estructurada.",
        embedding_dim: null,
        affected_features: [
          { code: "CV_PARSING", message: "Sembrar tu perfil desde el CV puede fallar." },
        ],
      },
    };
    const user = userEvent.setup();
    const acknowledged: Configuration = {
      ...degraded,
      is_usable: true,
      degradation_acknowledged_at: "2026-08-20T10:05:00Z",
    };
    let current = degraded;
    server.use(
      http.get("*/api/v1/setup/state", () =>
        HttpResponse.json({
          ...setupState("providers"),
          providers: { generation: current, embeddings: null },
        }),
      ),
      http.post("*/api/v1/setup/providers/:capability/degradation-acknowledgement", () => {
        current = acknowledged;
        return HttpResponse.json(acknowledged, { status: 201 });
      }),
    );

    renderWithClient(<ProvidersScreen />);

    expect(await screen.findByText(/Sembrar tu perfil desde el CV puede fallar/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continuar" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: /Entiendo lo que pierdo/ }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Continuar" })).toBeEnabled(),
    );
  });
});

describe("los cuatro resultados llegan al paso", () => {
  it("una cuota agotada se distingue de una llave inválida y no da la capacidad por buena", async () => {
    const user = userEvent.setup();
    const message =
      "Tu API key es válida, pero alcanzaste el límite de tu cuota. Puedes esperar a que se " +
      "reinicie o configurar otro proveedor.";
    server.use(
      http.put("*/api/v1/setup/providers/:capability", () =>
        HttpResponse.json({ code: "PROVIDER_QUOTA_EXCEEDED", message }, { status: 429 }),
      ),
    );

    renderWithClient(<ProvidersScreen />);
    await user.type(await screen.findByLabelText("API key"), "una-llave");
    await user.click(screen.getByRole("button", { name: /Verificar mi llave/ }));

    expect(await screen.findAllByText(message)).not.toHaveLength(0);
    expect(screen.getByRole("button", { name: "Continuar" })).toBeDisabled();
  });

  it("una llave rechazada muestra qué revisar, sin la llave y sin traza", async () => {
    const user = userEvent.setup();
    const message =
      "Tu proveedor rechazó la API key. Verifica que la copiaste completa y que sigue activa " +
      "en la consola de tu proveedor.";
    server.use(
      http.put("*/api/v1/setup/providers/:capability", () =>
        HttpResponse.json(
          {
            code: "PROVIDER_CREDENTIAL_REJECTED",
            message,
            details: { console_url: "https://ejemplo.invalid/consola" },
          },
          { status: 400 },
        ),
      ),
    );

    renderWithClient(<ProvidersScreen />);
    await user.type(await screen.findByLabelText("API key"), "una-llave-mal-copiada");
    await user.click(screen.getByRole("button", { name: /Verificar mi llave/ }));

    expect(await screen.findAllByText(message)).not.toHaveLength(0);
    expect(document.body.textContent).not.toContain("una-llave-mal-copiada");
    expect(screen.getAllByRole("link", { name: /consola de tu proveedor/i })).not.toHaveLength(0);
  });
});
