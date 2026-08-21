import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";

import { EmailScreen } from "@/features/setup/email/EmailScreen";

import { emailStep, setupState } from "../msw/handlers";
import { server } from "../msw/server";
import { renderWithClient } from "./renderWithClient";

beforeEach(() => {
  server.use(http.get("*/api/v1/setup/email", () => HttpResponse.json(emailStep())));
});

describe("paso de correo (FR-011, US1 AC9)", () => {
  it("omitir tiene el MISMO peso visual que continuar", async () => {
    renderWithClient(<EmailScreen />);

    const link = await screen.findByRole("button", { name: /Vincular mi Gmail/ });
    const skip = screen.getByRole("button", { name: /Omitir este paso/ });

    // Misma variante y mismo tamaño: un «quizá más tarde» en gris debajo de un
    // botón primario no es una opción igual, es una desalentada.
    expect(skip.className).toBe(link.className);
  });

  it("omitir es una sola acción", async () => {
    const user = userEvent.setup();
    let skipped = 0;
    server.use(
      http.post("*/api/v1/setup/email/skip", () => {
        skipped += 1;
        return HttpResponse.json(setupState(null));
      }),
    );

    renderWithClient(<EmailScreen />);
    await user.click(await screen.findByRole("button", { name: /Omitir este paso/ }));

    expect(skipped).toBe(1);
  });

  it("dice qué se gana vinculando y qué NO se pierde al omitirlo", async () => {
    renderWithClient(<EmailScreen />);

    expect(await screen.findByText(/sumar esas vacantes/)).toBeInTheDocument();
    expect(screen.getByText(/No pierdes nada de lo demás/)).toBeInTheDocument();
  });
});

describe("la divulgación de la App Password (FR-012, US1 AC10)", () => {
  it("está en pantalla ANTES de que exista ningún campo que llenar", async () => {
    renderWithClient(<EmailScreen />);

    expect(await screen.findByText(/da acceso a toda tu bandeja/)).toBeInTheDocument();

    // Un aviso que llega junto al campo ya no informa una decisión: la narra.
    expect(screen.queryByLabelText(/App Password/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Etiqueta/)).not.toBeInTheDocument();
    expect(screen.queryAllByRole("textbox")).toHaveLength(0);
  });

  it("advierte de Workspace y Protección Avanzada por adelantado", async () => {
    renderWithClient(<EmailScreen />);

    expect(
      await screen.findByText(/Workspace o tiene la Protección Avanzada/),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /vía OAuth/i })).toBeInTheDocument();
  });

  it("solo muestra el formulario cuando el candidato elige vincular", async () => {
    const user = userEvent.setup();
    renderWithClient(<EmailScreen />);

    await user.click(await screen.findByRole("button", { name: /Vincular mi Gmail/ }));

    expect(screen.getByLabelText("App Password")).toBeInTheDocument();
    expect(screen.getByLabelText(/Etiqueta que Vokara va a leer/)).toBeInTheDocument();
    // El aviso sigue a la vista mientras se llena: no fue un paso que se cierra.
    expect(screen.getByText(/da acceso a toda tu bandeja/)).toBeInTheDocument();
  });
});

describe("vincular (FR-013, US1 AC11)", () => {
  it("manda dirección, App Password y etiqueta, y no las deja en pantalla", async () => {
    const user = userEvent.setup();
    const bodies: unknown[] = [];
    server.use(
      http.post("*/api/v1/setup/email/link", async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json(emailStep({ status: "linked", label: "Empleo" }));
      }),
    );

    renderWithClient(<EmailScreen />);
    await user.click(await screen.findByRole("button", { name: /Vincular mi Gmail/ }));
    await user.type(screen.getByLabelText(/dirección de Gmail/), "alguien@ejemplo.invalid");
    await user.type(screen.getByLabelText("App Password"), "abcd efgh ijkl mnop");
    await user.type(screen.getByLabelText(/Etiqueta que Vokara va a leer/), "Empleo");
    await user.click(screen.getByRole("button", { name: /Vincular mi correo/ }));

    expect(bodies).toEqual([
      {
        email_address: "alguien@ejemplo.invalid",
        app_password: "abcd efgh ijkl mnop",
        label: "Empleo",
      },
    ]);
    // La credencial viaja en el cuerpo y no queda en ningún texto de la página.
    expect(document.body.textContent).not.toContain("abcd efgh ijkl mnop");
  });

  it("no deja vincular con el formulario a medias", async () => {
    const user = userEvent.setup();
    renderWithClient(<EmailScreen />);

    await user.click(await screen.findByRole("button", { name: /Vincular mi Gmail/ }));
    const submit = screen.getByRole("button", { name: /Vincular mi correo/ });
    expect(submit).toBeDisabled();

    await user.type(screen.getByLabelText(/dirección de Gmail/), "alguien@ejemplo.invalid");
    expect(submit).toBeDisabled();

    await user.type(screen.getByLabelText("App Password"), "una-app-password");
    expect(submit).toBeDisabled();

    await user.type(screen.getByLabelText(/Etiqueta que Vokara va a leer/), "Empleo");
    expect(submit).toBeEnabled();
  });

  it("una etiqueta inexistente NO da la vinculación por buena, y dice cómo crearla", async () => {
    const user = userEvent.setup();
    const message =
      "No encontramos esa etiqueta en tu cuenta. Créala en Gmail y aplica un filtro que mande " +
      "ahí tus alertas de empleo; después vuelve a intentarlo.";
    server.use(
      http.post("*/api/v1/setup/email/link", () =>
        HttpResponse.json({ code: "EMAIL_LABEL_NOT_FOUND", message }, { status: 422 }),
      ),
    );

    renderWithClient(<EmailScreen />);
    await user.click(await screen.findByRole("button", { name: /Vincular mi Gmail/ }));
    await user.type(screen.getByLabelText(/dirección de Gmail/), "alguien@ejemplo.invalid");
    await user.type(screen.getByLabelText("App Password"), "una-app-password");
    await user.type(screen.getByLabelText(/Etiqueta que Vokara va a leer/), "NoExiste");
    await user.click(screen.getByRole("button", { name: /Vincular mi correo/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent(message);
  });

  it("un fallo al vincular no quita la salida de omitir: el paso nunca bloquea", async () => {
    const user = userEvent.setup();
    server.use(
      http.post("*/api/v1/setup/email/link", () =>
        HttpResponse.json(
          {
            code: "EMAIL_APP_PASSWORD_REJECTED",
            message: "Gmail rechazó la App Password.",
            details: { oauth_docs_url: "https://ejemplo.invalid/oauth" },
          },
          { status: 400 },
        ),
      ),
    );

    renderWithClient(<EmailScreen />);
    await user.click(await screen.findByRole("button", { name: /Vincular mi Gmail/ }));
    await user.type(screen.getByLabelText(/dirección de Gmail/), "alguien@ejemplo.invalid");
    await user.type(screen.getByLabelText("App Password"), "una-app-password");
    await user.type(screen.getByLabelText(/Etiqueta que Vokara va a leer/), "Empleo");
    await user.click(screen.getByRole("button", { name: /Vincular mi correo/ }));

    await screen.findByRole("alert");
    expect(screen.getByRole("button", { name: /Omitir este paso/ })).toBeEnabled();
  });
});
