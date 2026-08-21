import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import type { components } from "@/api/schema";

import { server } from "../msw/server";
import { renderAt } from "./renderWithClient";

type SetupState = components["schemas"]["SetupStateModel"];
// `exactOptionalPropertyTypes` makes the optional field include `undefined`;
// the wizard only ever deals with a step or its absence.
type PendingStep = NonNullable<SetupState["pending_step"]> | null;

/**
 * Typed against the generated schema: a field renamed in the backend stops this
 * mock compiling too, instead of leaving a green test over a broken app (art. I).
 */
const state = (pending: PendingStep): SetupState => ({
  pending_step: pending,
  disclosure_acknowledged: pending !== "disclosure",
  disclosure_acknowledged_at: null,
  providers: { generation: null, embeddings: null },
  email_status: "pending",
  is_complete: pending === null,
});

function setupStateIs(pending: PendingStep): void {
  server.use(http.get("*/api/v1/setup/state", () => HttpResponse.json(state(pending))));
}

describe("guard de primera ejecución", () => {
  it("no deja alcanzar el onboarding escribiendo su dirección (US1 AC2)", async () => {
    setupStateIs("disclosure");

    renderAt("/onboarding");

    expect(await screen.findByRole("heading", { name: /Antes de empezar/ })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Todo listo/ })).not.toBeInTheDocument();
  });

  it("manda al paso pendiente aunque falte solo el de correo (FR-010)", async () => {
    setupStateIs("email");

    renderAt("/onboarding");

    expect(await screen.findByRole("heading", { name: /Vincular tu correo/ })).toBeInTheDocument();
  });

  it("deja pasar al onboarding cuando ya no queda ningún paso", async () => {
    setupStateIs(null);

    renderAt("/onboarding");

    expect(await screen.findByRole("heading", { name: /Todo listo/ })).toBeInTheDocument();
  });

  it("no deja saltarse un paso escribiendo la dirección de otro posterior", async () => {
    setupStateIs("disclosure");

    renderAt("/setup/email");

    expect(await screen.findByRole("heading", { name: /Antes de empezar/ })).toBeInTheDocument();
  });

  it("no vuelve a mostrar el wizard una vez terminado (FR-015)", async () => {
    setupStateIs(null);

    renderAt("/setup/disclosure");

    expect(await screen.findByRole("heading", { name: /Todo listo/ })).toBeInTheDocument();
  });

  it("al reabrir, la raíz aterriza en el paso pendiente (FR-014)", async () => {
    setupStateIs("providers");

    renderAt("/");

    expect(
      await screen.findByRole("heading", { name: /Tus proveedores de IA/ }),
    ).toBeInTheDocument();
  });

  it("dice qué hacer cuando el servicio local no responde, sin dejar pasar", async () => {
    server.use(http.get("*/api/v1/setup/state", () => HttpResponse.error()));

    renderAt("/onboarding");

    expect(await screen.findByText(/Revisa que Docker esté corriendo/)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Todo listo/ })).not.toBeInTheDocument();
  });

  it("la pantalla de diagnóstico es alcanzable sin pasar por el wizard", async () => {
    server.use(
      http.get("*/api/v1/health", () =>
        HttpResponse.json({ status: "ok", database: "ok", migration_revision: "0001" }),
      ),
    );

    renderAt("/status");

    expect(await screen.findByText("0001")).toBeInTheDocument();
  });
});
