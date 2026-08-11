import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import type { components } from "@/api/schema";
import { StatusScreen } from "@/features/status/StatusScreen";

import { server } from "./msw/server";

/**
 * Typed against the generated schema on purpose: if the backend renames a
 * field, this mock stops compiling too. A mock that drifts from the contract
 * is worse than no mock — it keeps the test green while the app breaks
 * (art. I).
 */
const healthy: components["schemas"]["HealthResponse"] = {
  status: "ok",
  database: "ok",
  migration_revision: "0001",
};

describe("pantalla de estado", () => {
  it("muestra lo que responde la API local", async () => {
    server.use(http.get("*/api/v1/health", () => HttpResponse.json(healthy)));

    render(<StatusScreen />);

    expect(await screen.findByText("0001")).toBeInTheDocument();
    expect(screen.getAllByText("ok")).toHaveLength(2);
  });

  it("dice qué hacer cuando el servicio local no responde", async () => {
    server.use(http.get("*/api/v1/health", () => new HttpResponse(null, { status: 503 })));

    render(<StatusScreen />);

    expect(await screen.findByText(/Revisa que Docker esté corriendo/)).toBeInTheDocument();
  });

  it("no inventa una revisión cuando todavía no hay ninguna aplicada", async () => {
    server.use(
      http.get("*/api/v1/health", () =>
        HttpResponse.json({ ...healthy, migration_revision: null }),
      ),
    );

    render(<StatusScreen />);

    expect(await screen.findByText("sin aplicar")).toBeInTheDocument();
  });
});
