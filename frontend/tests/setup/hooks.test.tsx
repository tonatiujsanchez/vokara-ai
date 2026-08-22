import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import type { components } from "@/api/schema";

import {
  disclosure,
  emailStep,
  firstRunHandlers,
  providerCatalog,
  setupState,
  verifiedConfiguration,
} from "../msw/handlers";
import { server } from "../msw/server";
import { renderAt } from "./renderWithClient";

type SetupState = components["schemas"]["SetupStateModel"];

/**
 * A server that answers the whole first run and records what was asked of it.
 *
 * What these tests are about is FR-014 — reopening resumes at the pending step
 * and never asks again for the acknowledgement or for a key already verified —
 * and «never asks again» is a statement about requests, so the requests are
 * what gets asserted.
 */
function recordingServer(state: SetupState): { paths: string[] } {
  const paths: string[] = [];

  server.use(
    http.all("*/api/v1/*", async ({ request }) => {
      paths.push(`${request.method} ${new URL(request.url).pathname}`);
      return undefined;
    }),
    http.get("*/api/v1/setup/state", () => HttpResponse.json(state)),
    http.get("*/api/v1/setup/disclosure", () => HttpResponse.json(disclosure)),
    http.get("*/api/v1/setup/providers/catalog", () => HttpResponse.json(providerCatalog())),
    http.get("*/api/v1/setup/email", () => HttpResponse.json(emailStep())),
  );

  return { paths };
}

describe("reanudar la primera ejecución (FR-014, SC-015, US1 AC12)", () => {
  it("con el acuse hecho y solo generación verificada, retoma en proveedores", async () => {
    const halfway: SetupState = {
      ...setupState("providers"),
      disclosure_acknowledged: true,
      disclosure_acknowledged_at: "2026-08-20T10:00:00Z",
      providers: { generation: verifiedConfiguration("generation"), embeddings: null },
    };
    const { paths } = recordingServer(halfway);

    renderAt("/");

    expect(
      await screen.findByRole("heading", { level: 1, name: /Tus proveedores de IA/ }),
    ).toBeInTheDocument();

    // Ni el acuse ni la llave ya verificada se vuelven a pedir.
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(paths).not.toContain("POST /api/v1/setup/disclosure-acknowledgement");
    expect(paths).not.toContain("GET /api/v1/setup/disclosure");
  });

  it("muestra la capacidad ya verificada en vez de volver a pedir su llave", async () => {
    recordingServer({
      ...setupState("providers"),
      providers: { generation: verifiedConfiguration("generation"), embeddings: null },
    });

    renderAt("/");

    expect(await screen.findAllByText(/Tu API key funciona/)).not.toHaveLength(0);
  });

  it("retoma en el correo cuando es lo único que queda", async () => {
    recordingServer(setupState("email"));

    renderAt("/");

    expect(
      await screen.findByRole("heading", { level: 1, name: /Vincular tu correo/ }),
    ).toBeInTheDocument();
  });

  it("no vuelve a mostrar el wizard una vez concluido (FR-015)", async () => {
    const { paths } = recordingServer(setupState(null));

    renderAt("/");

    expect(await screen.findByRole("heading", { level: 1, name: "Todo listo" })).toBeInTheDocument();
    expect(paths).not.toContain("GET /api/v1/setup/disclosure");
  });
});

describe("el wizard avanza solo al resolverse un paso", () => {
  it("omitir el correo concluye la primera ejecución sin navegar a mano", async () => {
    const user = userEvent.setup();
    let current = setupState("email");

    server.use(
      // El estado va primero: entre los handlers de una misma llamada a
      // `server.use`, gana el que se pasa antes.
      http.get("*/api/v1/setup/state", () => HttpResponse.json(current)),
      ...firstRunHandlers("email"),
      http.post("*/api/v1/setup/email/skip", () => {
        current = setupState(null);
        return HttpResponse.json(current);
      }),
    );

    renderAt("/setup/email");

    await user.click(await screen.findByRole("button", { name: /Omitir este paso/ }));

    // La mutación invalida el estado, el guard lo relee y el router se mueve:
    // ninguna pantalla llama a navigate() para esto.
    expect(await screen.findByRole("heading", { level: 1, name: "Todo listo" })).toBeInTheDocument();
  });

  it("aceptar la divulgación lleva al paso siguiente por la misma vía", async () => {
    const user = userEvent.setup();
    let current = setupState("disclosure");

    server.use(
      http.get("*/api/v1/setup/state", () => HttpResponse.json(current)),
      ...firstRunHandlers("disclosure"),
      http.post("*/api/v1/setup/disclosure-acknowledgement", () => {
        current = setupState("providers");
        return HttpResponse.json(current, { status: 201 });
      }),
    );

    renderAt("/setup/disclosure");

    await user.click(await screen.findByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: /Continuar/ }));

    expect(
      await screen.findByRole("heading", { level: 1, name: /Tus proveedores de IA/ }),
    ).toBeInTheDocument();
  });
});
