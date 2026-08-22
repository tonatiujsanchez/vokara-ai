import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";

import type { components } from "@/api/schema";
import { DisclosureScreen } from "@/features/setup/disclosure/DisclosureScreen";

import DISCLOSURE_BODY from "../fixtures/disclosure.md?raw";
import { server } from "../msw/server";
import { renderWithClient } from "./renderWithClient";

type Disclosure = components["schemas"]["DisclosureModel"];

const disclosure: Disclosure = {
  version: "2026-08-17",
  body_md: DISCLOSURE_BODY,
  acknowledged: false,
  acknowledged_at: null,
  acknowledged_version: null,
};

beforeEach(() => {
  server.use(http.get("*/api/v1/setup/disclosure", () => HttpResponse.json(disclosure)));
});

describe("pantalla de divulgación", () => {
  it("muestra el texto completo en pantalla, no un enlace (FR-001, US1 AC1)", async () => {
    renderWithClient(<DisclosureScreen />);

    // Los cuatro contenidos obligatorios de FR-001, cada uno con sus palabras.
    expect(await screen.findByText(/no salen de esta máquina/)).toBeInTheDocument();
    expect(screen.getByText(/La única excepción: tu proveedor de IA/)).toBeInTheDocument();
    expect(screen.getByText(/Cero telemetría, cero analítica/)).toBeInTheDocument();
    expect(screen.getByText(/cifrado de disco de tu/)).toBeInTheDocument();
  });

  it("no tiene ningún campo que llenar (US1 AC1)", async () => {
    renderWithClient(<DisclosureScreen />);
    // Nivel 1: el propio texto abre con un `##` que dice casi lo mismo.
    await screen.findByRole("heading", { level: 1, name: "Antes de empezar" });

    expect(screen.queryAllByRole("textbox")).toHaveLength(0);
    expect(screen.queryAllByRole("combobox")).toHaveLength(0);
    expect(screen.queryAllByRole("spinbutton")).toHaveLength(0);
  });

  it("nunca preselecciona el acuse (FR-002)", async () => {
    renderWithClient(<DisclosureScreen />);

    expect(await screen.findByRole("checkbox")).not.toBeChecked();
  });

  it("no preselecciona el acuse ni cuando el servidor dice que hubo uno anterior", async () => {
    server.use(
      http.get("*/api/v1/setup/disclosure", () =>
        HttpResponse.json({
          ...disclosure,
          acknowledged: true,
          acknowledged_version: "2026-01-01",
        }),
      ),
    );

    renderWithClient(<DisclosureScreen />);

    expect(await screen.findByRole("checkbox")).not.toBeChecked();
  });

  it("mantiene continuar inhabilitado sin el acuse, y lo habilita con él (US1 AC2)", async () => {
    const user = userEvent.setup();
    renderWithClient(<DisclosureScreen />);

    const button = await screen.findByRole("button", { name: /Continuar/ });
    expect(button).toBeDisabled();

    await user.click(screen.getByRole("checkbox"));
    expect(button).toBeEnabled();

    await user.click(screen.getByRole("checkbox"));
    expect(button).toBeDisabled();
  });

  it("registra el acuse con la versión que el candidato tuvo a la vista (R-29)", async () => {
    const user = userEvent.setup();
    const bodies: unknown[] = [];
    server.use(
      http.post("*/api/v1/setup/disclosure-acknowledgement", async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json({}, { status: 201 });
      }),
    );

    renderWithClient(<DisclosureScreen />);
    await user.click(await screen.findByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: /Continuar/ }));

    expect(bodies).toEqual([{ disclosure_version: "2026-08-17", acknowledged: true }]);
  });

  it("muestra el mensaje del backend cuando el acuse falla, sin reescribirlo", async () => {
    const user = userEvent.setup();
    const message = "Ya aceptaste esta versión de la divulgación. Puedes continuar.";
    server.use(
      http.post("*/api/v1/setup/disclosure-acknowledgement", () =>
        HttpResponse.json({ code: "DISCLOSURE_ALREADY_ACKNOWLEDGED", message }, { status: 409 }),
      ),
    );

    renderWithClient(<DisclosureScreen />);
    await user.click(await screen.findByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: /Continuar/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent(message);
  });
});
