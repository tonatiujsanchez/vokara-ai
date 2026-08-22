import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { messageOf, type ApiError, ApiRequestError } from "@/features/setup/hooks/apiError";
import {
  useProviderCatalog,
  type Capability,
  type ProviderOption,
} from "@/features/setup/hooks/useProviderCatalog";
import {
  useAcknowledgeDegradation,
  useConfigureCapability,
} from "@/features/setup/hooks/useProviderConfiguration";
import { useSetupState } from "@/features/setup/hooks/useSetupState";

import { CapabilityConfiguration } from "./CapabilityConfiguration";
import { PreflightResult, viewOfConfiguration, viewOfError } from "./PreflightResult";

const CAPABILITIES: Capability[] = ["generation", "embeddings"];

function suggested(options: ProviderOption[]): string {
  return options.find((option) => option.is_suggested_default)?.provider ?? options[0]?.provider ?? "";
}

/**
 * The provider step: two independent choices, their cost, and one preflight each.
 *
 * The layout follows FR-005 literally. Both capabilities show their options and
 * their estimated cost **first**; only below them is any key asked for. A cost
 * rendered under the field it was meant to inform is a cost nobody read in time.
 *
 * The two choices are independent (ADR-011) and the separation is explained in
 * one line that comes from the backend, because the reason is a product fact and
 * not a string this screen should own.
 *
 * When both point at the same provider the candidate types **one** key and the
 * two capabilities are verified separately with it (FR-004, US1 AC4): two PUTs,
 * two preflights, two results — the key being shared changes nothing about the
 * verification.
 *
 * Continuing needs generation and only generation (FR-010). Embeddings without
 * a resolved preflight degrades features that live outside this feature, and
 * says which; it never blocks.
 */
export function ProvidersScreen(): JSX.Element {
  const catalog = useProviderCatalog();
  const state = useSetupState();
  const configure = useConfigureCapability();
  const acknowledge = useAcknowledgeDegradation();
  const navigate = useNavigate();

  const [chosen, setChosen] = useState<Partial<Record<Capability, string>>>({});
  const [apiKeys, setApiKeys] = useState<Partial<Record<Capability, string>>>({});
  const [failures, setFailures] = useState<Partial<Record<Capability, ApiError>>>({});

  if (catalog.isPending || state.isPending) {
    return (
      <main className="mx-auto max-w-2xl p-8">
        <p className="text-muted-foreground">Cargando…</p>
      </main>
    );
  }

  if (catalog.isError || state.isError) {
    return (
      <main className="mx-auto max-w-2xl p-8">
        <h1 className="text-2xl font-semibold">Tus proveedores de IA</h1>
        <p className="mt-4">{messageOf(catalog.error ?? state.error)}</p>
      </main>
    );
  }

  const optionsOf = (capability: Capability): ProviderOption[] =>
    capability === "generation" ? catalog.data.generation : catalog.data.embeddings;

  const providerOf = (capability: Capability): string =>
    chosen[capability] ?? suggested(optionsOf(capability));

  const sameProvider = providerOf("generation") === providerOf("embeddings");
  // One key when the provider is the same; the field the candidate types into
  // is generation's, and embeddings reuses its value.
  const keyFor = (capability: Capability): string =>
    (sameProvider ? apiKeys.generation : apiKeys[capability]) ?? "";

  async function submit(capabilities: Capability[]): Promise<void> {
    for (const capability of capabilities) {
      setFailures((current) => ({ ...current, [capability]: undefined }));
      try {
        await configure.mutateAsync({
          capability,
          provider: providerOf(capability),
          apiKey: keyFor(capability),
        });
      } catch (error) {
        if (error instanceof ApiRequestError) {
          setFailures((current) => ({ ...current, [capability]: error.body }));
        }
      }
    }
  }

  const generation = state.data.providers.generation ?? null;
  const embeddings = state.data.providers.embeddings ?? null;
  const configurationOf = (capability: Capability) =>
    capability === "generation" ? generation : embeddings;

  const canContinue = generation?.is_usable === true;

  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-2xl font-semibold">Tus proveedores de IA</h1>
      <p className="mt-2 text-sm text-muted-foreground">{catalog.data.separation_reason_es}</p>

      <CapabilityConfiguration
        title="Generación"
        explanation="Lee tu CV y arma tu perfil."
        options={optionsOf("generation")}
        selected={providerOf("generation")}
        onSelect={(provider) => setChosen((current) => ({ ...current, generation: provider }))}
      />

      <CapabilityConfiguration
        title="Embeddings"
        explanation="Calcula los vectores del matching semántico."
        options={optionsOf("embeddings")}
        selected={providerOf("embeddings")}
        onSelect={(provider) => setChosen((current) => ({ ...current, embeddings: provider }))}
      />

      <Card className="mt-6">
        <h2 className="text-lg font-medium">Tu API key</h2>

        {sameProvider ? (
          <>
            <p className="mt-1 text-sm text-muted-foreground">
              Elegiste el mismo proveedor para las dos, así que basta con una llave. Verificamos
              cada capacidad por separado con ella.
            </p>
            <div className="mt-4">
              <Label htmlFor="api-key-compartida">API key</Label>
              <Input
                id="api-key-compartida"
                type="password"
                autoComplete="off"
                className="mt-1"
                value={apiKeys.generation ?? ""}
                onChange={(event) =>
                  setApiKeys((current) => ({ ...current, generation: event.target.value }))
                }
              />
            </div>
            <Button
              className="mt-4"
              disabled={configure.isPending || keyFor("generation") === ""}
              onClick={() => void submit(CAPABILITIES)}
            >
              {configure.isPending ? "Verificando…" : "Verificar mi llave"}
            </Button>
          </>
        ) : (
          <>
            <p className="mt-1 text-sm text-muted-foreground">
              Elegiste dos proveedores distintos, así que cada uno lleva su propia llave.
            </p>
            {CAPABILITIES.map((capability) => (
              <div key={capability} className="mt-4">
                <Label htmlFor={`api-key-${capability}`}>
                  API key de {capability === "generation" ? "generación" : "embeddings"}
                </Label>
                <Input
                  id={`api-key-${capability}`}
                  type="password"
                  autoComplete="off"
                  className="mt-1"
                  value={apiKeys[capability] ?? ""}
                  onChange={(event) =>
                    setApiKeys((current) => ({ ...current, [capability]: event.target.value }))
                  }
                />
                <Button
                  className="mt-2"
                  size="sm"
                  disabled={configure.isPending || keyFor(capability) === ""}
                  onClick={() => void submit([capability])}
                >
                  {configure.isPending ? "Verificando…" : "Verificar"}
                </Button>
              </div>
            ))}
          </>
        )}
      </Card>

      {CAPABILITIES.map((capability) => {
        const failure = failures[capability];
        const configuration = configurationOf(capability);
        const view = failure ? viewOfError(failure) : configuration ? viewOfConfiguration(configuration) : null;
        if (view === null) return null;

        return (
          <section key={capability} className="mt-4">
            <h3 className="text-sm font-medium">
              {capability === "generation" ? "Generación" : "Embeddings"}
            </h3>
            <div className="mt-2">
              <PreflightResult
                view={view}
                isAcknowledging={acknowledge.isPending}
                onAcknowledgeDegradation={() => acknowledge.mutate(capability)}
                onChangeProvider={() =>
                  setFailures((current) => ({ ...current, [capability]: undefined }))
                }
                onRetry={() => void submit([capability])}
              />
            </div>
          </section>
        );
      })}

      <Button
        className="mt-8"
        disabled={!canContinue}
        onClick={() => void navigate("/setup/email")}
      >
        Continuar
      </Button>
      {/* FR-010 in both directions: generation is what gates, and the absence of
          embeddings degrades explicitly instead of blocking. The second message
          is the «informada» half — leaving without it is a valid choice, and a
          valid choice is one whose consequence was stated. */}
      <p className="mt-2 text-sm text-muted-foreground">
        {!canContinue
          ? "Para continuar necesitas tu proveedor de generación resuelto: es el que lee tu CV."
          : embeddings?.is_usable === true
            ? "Tus dos capacidades están resueltas."
            : "Puedes continuar sin resolver embeddings: no bloquea nada. Hasta que lo configures, las funciones que dependen de vectores quedan fuera."}
      </p>
    </main>
  );
}
