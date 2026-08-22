import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import type { components } from "@/api/schema";

import { DISCLOSURE_VERSION, disclosure, emailStep, providerCatalog, verifiedConfiguration } from "../msw/handlers";
import { server } from "../msw/server";
import { renderAt } from "./renderWithClient";

type SetupState = components["schemas"]["SetupStateModel"];
type EmailStep = components["schemas"]["EmailStepModel"];

const LABEL = "Alertas de empleo";

const REJECTED =
  "Gmail rechazó la App Password. Si tu cuenta es de Workspace o tiene Protección " +
  "Avanzada, las App Passwords están deshabilitadas: usa la vía OAuth.";
const LABEL_MISSING =
  "No encontramos esa etiqueta en tu cuenta. Créala en Gmail y aplica un filtro que mande " +
  "ahí tus alertas de empleo; después vuelve a intentarlo.";
const UNREACHABLE =
  "No pudimos conectarnos a tu correo en este momento. Inténtalo de nuevo, o continúa sin " +
  "vincularlo: no bloquea nada.";

const FAILURES = {
  rejected: { status: 400, code: "EMAIL_APP_PASSWORD_REJECTED", message: REJECTED },
  labelMissing: { status: 422, code: "EMAIL_LABEL_NOT_FOUND", message: LABEL_MISSING },
  unreachable: { status: 503, code: "EMAIL_PROVIDER_UNREACHABLE", message: UNREACHABLE },
} as const;

/**
 * A server that remembers the mail step, with `pending_step` derived as the
 * backend derives it: resolving the step makes it `null` (app/domain/setup.py).
 */
function serverAnswering(failure?: { status: number; code: string; message: string }): void {
  let resolved: EmailStep | null = null;

  server.use(
    http.get("*/api/v1/setup/state", () =>
      HttpResponse.json({
        pending_step: resolved === null ? "email" : null,
        disclosure_acknowledged: true,
        disclosure_acknowledged_at: "2026-08-20T10:00:00Z",
        providers: {
          generation: verifiedConfiguration("generation"),
          embeddings: verifiedConfiguration("embeddings"),
        },
        email_status: resolved?.status ?? "pending",
        is_complete: resolved !== null,
      } satisfies SetupState),
    ),
    http.get("*/api/v1/setup/disclosure", () =>
      HttpResponse.json({ ...disclosure, acknowledged: true, acknowledged_version: DISCLOSURE_VERSION }),
    ),
    http.get("*/api/v1/setup/providers/catalog", () => HttpResponse.json(providerCatalog())),
    http.get("*/api/v1/setup/email", () => HttpResponse.json(resolved ?? emailStep())),
    http.post("*/api/v1/setup/email/link", () => {
      if (failure) {
        return HttpResponse.json(
          { code: failure.code, message: failure.message, details: null },
          { status: failure.status },
        );
      }
      resolved = emailStep({
        status: "linked",
        label: LABEL,
        linked_at: "2026-08-22T10:00:00Z",
        credential_status: "configured",
        linked_confirmation_es:
          `Comprobamos que la etiqueta «${LABEL}» existe y es alcanzable: es la única que ` +
          "Vokara va a leer. En esta versión todavía no lee ningún correo.",
      });
      return HttpResponse.json(resolved);
    }),
    http.post("*/api/v1/setup/email/skip", () => {
      resolved = emailStep({ status: "skipped" });
      return HttpResponse.json(resolved);
    }),
  );
}

async function fillAndLink(): Promise<void> {
  const user = userEvent.setup();
  await screen.findByRole("heading", { level: 1, name: /Vincular tu correo/ });
  await user.click(screen.getByRole("button", { name: "Vincular mi Gmail" }));
  await user.type(screen.getByLabelText("Tu dirección de Gmail"), "alguien@example.com");
  await user.type(screen.getByLabelText("App Password"), "abcd efgh ijkl mnop");
  await user.type(screen.getByLabelText("Etiqueta que Vokara va a leer"), LABEL);
  await user.click(screen.getByRole("button", { name: "Vincular mi correo" }));
}

function stillOnEmail(): void {
  expect(
    screen.getByRole("heading", { level: 1, name: /Vincular tu correo/ }),
  ).toBeInTheDocument();
  expect(screen.queryByRole("heading", { level: 1, name: "Todo listo" })).not.toBeInTheDocument();
}

describe("el paso de correo nunca avanza solo (FR-011, art. X)", () => {
  it("confirma la vinculación nombrando la etiqueta, y no navega", async () => {
    serverAnswering();

    renderAt("/setup/email");
    await fillAndLink();

    // The counterpart of the warning given before the App Password was asked
    // for: we promised to read only that label, so the candidate has to see
    // WHICH one ended up designated (FR-012, FR-013, ADR-012).
    expect(await screen.findByText(new RegExp(`«${LABEL}»`))).toBeInTheDocument();
    expect(screen.getByText(/todavía no lee ningún correo/)).toBeInTheDocument();
    stillOnEmail();
  });

  it.each([
    ["App Password rechazada", FAILURES.rejected, REJECTED],
    ["etiqueta inexistente", FAILURES.labelMissing, LABEL_MISSING],
    ["proveedor inalcanzable", FAILURES.unreachable, UNREACHABLE],
  ])("distingue %s y no navega", async (_name, failure, message) => {
    serverAnswering(failure);

    renderAt("/setup/email");
    await fillAndLink();

    expect(await screen.findByText(message)).toBeInTheDocument();
    stillOnEmail();
  });

  it("solo termina la primera ejecución cuando el candidato lo pide (art. X)", async () => {
    serverAnswering();

    renderAt("/setup/email");
    await fillAndLink();
    await screen.findByText(new RegExp(`«${LABEL}»`));
    stillOnEmail();

    await userEvent.setup().click(screen.getByRole("button", { name: /Continuar/ }));

    expect(await screen.findByRole("heading", { level: 1, name: "Todo listo" })).toBeInTheDocument();
  });

  it("omitir sí avanza: es la acción explícita de terminar", async () => {
    serverAnswering();

    renderAt("/setup/email");
    const user = userEvent.setup();
    await screen.findByRole("heading", { level: 1, name: /Vincular tu correo/ });
    await user.click(screen.getByRole("button", { name: "Omitir este paso" }));

    expect(await screen.findByRole("heading", { level: 1, name: "Todo listo" })).toBeInTheDocument();
  });
});
