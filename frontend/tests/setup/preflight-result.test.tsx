import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { components } from "@/api/schema";
import {
  PreflightResult,
  viewOfConfiguration,
  viewOfError,
  type PreflightView,
} from "@/features/setup/providers/PreflightResult";

type Configuration = components["schemas"]["ProviderConfigurationModel"];

/** The wording is the backend's, so the fixtures carry the catalogue's texts. */
const MESSAGES = {
  verified: "Tu API key funciona y este modelo cumple lo que necesitamos.",
  unverified: "Tu API key funciona, pero este modelo no garantiza los embeddings.",
  rejected:
    "Tu proveedor rechazó la API key. Verifica que la copiaste completa y que sigue activa " +
    "en la consola de tu proveedor.",
  quota:
    "Tu API key es válida, pero alcanzaste el límite de tu cuota. Puedes esperar a que se " +
    "reinicie o configurar otro proveedor.",
  unreachable:
    "No pudimos comunicarnos con tu proveedor para verificar la llave. Revisa tu conexión e " +
    "inténtalo de nuevo; no hace falta que vuelvas a escribirla.",
} as const;

function configuration(overrides: Partial<Configuration["preflight"]>): Configuration {
  return {
    capability: "embeddings",
    provider: "un-proveedor",
    model: "un-modelo",
    credential_status: "configured",
    is_usable: true,
    degradation_acknowledged_at: null,
    preflight: {
      result: "verified",
      checked_at: "2026-08-20T10:00:00Z",
      message: MESSAGES.verified,
      embedding_dim: null,
      affected_features: [],
      ...overrides,
    },
  };
}

const VIEWS: PreflightView[] = [
  { kind: "verified", message: MESSAGES.verified, embeddingDim: 768 },
  {
    kind: "capability_unverified",
    message: MESSAGES.unverified,
    affected: [
      { code: "SEMANTIC_MATCHING", message: "El matching semántico quedaría desactivado." },
    ],
    acknowledged: false,
  },
  { kind: "credential_rejected", message: MESSAGES.rejected, consoleUrl: null },
  { kind: "quota_exceeded", message: MESSAGES.quota },
  { kind: "provider_unreachable", message: MESSAGES.unreachable },
];

describe("los cinco resultados del preflight", () => {
  it("cada uno rinde un texto distinto: ninguno se confunde con otro (FR-007)", () => {
    const texts = VIEWS.map((view) => {
      const { container, unmount } = render(<PreflightResult view={view} />);
      const text = container.textContent ?? "";
      unmount();
      return text;
    });

    expect(new Set(texts).size).toBe(VIEWS.length);
  });

  it("muestra el mensaje del backend tal cual, sin tabla propia (art. IX)", () => {
    for (const view of VIEWS) {
      const { unmount } = render(<PreflightResult view={view} />);
      expect(screen.getByText(view.message)).toBeInTheDocument();
      unmount();
    }
  });

  it("una cuota agotada NUNCA se presenta como llave inválida (SC-012)", () => {
    render(<PreflightResult view={{ kind: "quota_exceeded", message: MESSAGES.quota }} />);

    expect(screen.getByText(/tu API key es válida/i)).toBeInTheDocument();
    expect(screen.queryByText(/rechazó la API key/)).not.toBeInTheDocument();
  });

  it("un proveedor inalcanzable no se presenta como llave inválida, y se reintenta", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(
      <PreflightResult
        view={{ kind: "provider_unreachable", message: MESSAGES.unreachable }}
        onRetry={onRetry}
      />,
    );

    expect(screen.getByText(/No pudimos comunicarnos/)).toBeInTheDocument();
    expect(screen.queryByText(/rechazó la API key/)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Reintentar/ }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("registra la dimensión verificada cuando la hay (FR-007.2)", () => {
    render(
      <PreflightResult view={{ kind: "verified", message: MESSAGES.verified, embeddingDim: 768 }} />,
    );

    expect(screen.getByText(/768/)).toBeInTheDocument();
  });
});

describe("acuse específico de degradación (FR-007.3, SC-016)", () => {
  const degraded: PreflightView = {
    kind: "capability_unverified",
    message: MESSAGES.unverified,
    affected: [
      { code: "SEMANTIC_MATCHING", message: "El matching semántico quedaría desactivado." },
      { code: "CV_PARSING", message: "Sembrar tu perfil desde el CV puede fallar." },
    ],
    acknowledged: false,
  };

  it("enumera las funciones concretas afectadas antes de pedir el acuse", () => {
    render(<PreflightResult view={degraded} />);

    expect(screen.getByText(/El matching semántico quedaría desactivado/)).toBeInTheDocument();
    expect(screen.getByText(/Sembrar tu perfil desde el CV puede fallar/)).toBeInTheDocument();
  });

  it("ofrece cambiar de proveedor además de aceptar la degradación", () => {
    render(<PreflightResult view={degraded} />);

    expect(screen.getByRole("button", { name: /Elegir otro proveedor/ })).toBeInTheDocument();
  });

  it("pide el acuse mientras no lo haya, y deja de pedirlo cuando lo hay", async () => {
    const user = userEvent.setup();
    const onAcknowledge = vi.fn();
    const { rerender } = render(
      <PreflightResult view={degraded} onAcknowledgeDegradation={onAcknowledge} />,
    );

    await user.click(screen.getByRole("button", { name: /Entiendo lo que pierdo/ }));
    expect(onAcknowledge).toHaveBeenCalledOnce();

    rerender(<PreflightResult view={{ ...degraded, acknowledged: true }} />);
    expect(screen.queryByRole("button", { name: /Entiendo lo que pierdo/ })).not.toBeInTheDocument();
  });
});

describe("de la respuesta de la API a uno de los cinco", () => {
  it("mapea cada código de error del catálogo a su resultado", () => {
    expect(viewOfError({ code: "PROVIDER_QUOTA_EXCEEDED", message: MESSAGES.quota })?.kind).toBe(
      "quota_exceeded",
    );
    expect(viewOfError({ code: "PROVIDER_UNREACHABLE", message: MESSAGES.unreachable })?.kind).toBe(
      "provider_unreachable",
    );
    expect(viewOfError({ code: "PROVIDER_CREDENTIAL_REJECTED", message: MESSAGES.rejected })?.kind).toBe(
      "credential_rejected",
    );
  });

  it("no inventa un resultado para un código que no es de preflight", () => {
    expect(viewOfError({ code: "INTERNAL_ERROR", message: "Algo falló." })).toBeNull();
  });

  it("lleva la consola del proveedor cuando el backend la manda, y no la inventa", () => {
    const withUrl = viewOfError({
      code: "PROVIDER_CREDENTIAL_REJECTED",
      message: MESSAGES.rejected,
      details: { console_url: "https://ejemplo.invalid/consola" },
    });
    const without = viewOfError({
      code: "PROVIDER_CREDENTIAL_REJECTED",
      message: MESSAGES.rejected,
    });

    expect(withUrl).toMatchObject({ consoleUrl: "https://ejemplo.invalid/consola" });
    expect(without).toMatchObject({ consoleUrl: null });
  });

  it("lee la degradación y su acuse de la configuración guardada", () => {
    const pending = viewOfConfiguration(
      configuration({ result: "capability_unverified", message: MESSAGES.unverified }),
    );
    expect(pending).toMatchObject({ kind: "capability_unverified", acknowledged: false });

    const acknowledged = viewOfConfiguration({
      ...configuration({ result: "capability_unverified", message: MESSAGES.unverified }),
      degradation_acknowledged_at: "2026-08-20T10:05:00Z",
    });
    expect(acknowledged).toMatchObject({ acknowledged: true });
  });

  it("lee la dimensión verificada de una capacidad de embeddings", () => {
    expect(viewOfConfiguration(configuration({ embedding_dim: 768 }))).toMatchObject({
      kind: "verified",
      embeddingDim: 768,
    });
  });
});
