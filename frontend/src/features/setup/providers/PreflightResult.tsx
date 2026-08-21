import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { components } from "@/api/schema";
import type { ApiError } from "@/features/setup/hooks/apiError";

type Configuration = components["schemas"]["ProviderConfigurationModel"];
type AffectedFeature = components["schemas"]["AffectedFeatureModel"];

/**
 * The five outcomes of a preflight, kept apart because they are five situations.
 *
 * FR-007 asks for four results told apart, and `provider_unreachable` is the
 * fifth case the contract keeps deliberately outside that sum: having no
 * connection says nothing about the credential, so it is «no pudimos verificar»
 * and never «tu llave está mal» (research R-23).
 *
 * Collapsing any two of these has a concrete cost. Presenting an exhausted
 * quota as a rejected credential sends the candidate to regenerate a key that
 * works perfectly; presenting an unreachable provider the same way makes them
 * paste it again for nothing.
 */
export type PreflightView =
  | { kind: "verified"; message: string; embeddingDim: number | null }
  | { kind: "capability_unverified"; message: string; affected: AffectedFeature[]; acknowledged: boolean }
  | { kind: "credential_rejected"; message: string; consoleUrl: string | null }
  | { kind: "quota_exceeded"; message: string }
  | { kind: "provider_unreachable"; message: string };

function detailUrl(error: ApiError, key: string): string | null {
  const value = error.details?.[key];
  return typeof value === "string" ? value : null;
}

/** What the API said, as one of the five. Never a guess: an unknown code is not one. */
export function viewOfError(error: ApiError): PreflightView | null {
  switch (error.code) {
    case "PROVIDER_CREDENTIAL_REJECTED":
      return {
        kind: "credential_rejected",
        message: error.message,
        consoleUrl: detailUrl(error, "console_url"),
      };
    case "MODEL_NOT_AVAILABLE":
      return { kind: "credential_rejected", message: error.message, consoleUrl: null };
    case "PROVIDER_QUOTA_EXCEEDED":
      return { kind: "quota_exceeded", message: error.message };
    case "PROVIDER_UNREACHABLE":
      return { kind: "provider_unreachable", message: error.message };
    default:
      return null;
  }
}

/** What a saved configuration says about itself. */
export function viewOfConfiguration(configuration: Configuration): PreflightView {
  const { preflight } = configuration;

  if (preflight.result === "capability_unverified") {
    return {
      kind: "capability_unverified",
      message: preflight.message,
      affected: preflight.affected_features ?? [],
      acknowledged: configuration.degradation_acknowledged_at != null,
    };
  }

  return {
    kind: "verified",
    message: preflight.message,
    embeddingDim: preflight.embedding_dim ?? null,
  };
}

/**
 * The result on screen, with the action that belongs to it.
 *
 * Every text shown here is the backend's `message`. The frontend keeps no table
 * of its own so that the wording has a single owner and cannot drift
 * (contracts/errors.md, art. IX), and it does not name the provider either: the
 * catalogue does, and art. XI keeps that knowledge out of this side entirely.
 */
export function PreflightResult({
  view,
  onAcknowledgeDegradation,
  onChangeProvider,
  onRetry,
  isAcknowledging = false,
}: {
  view: PreflightView;
  onAcknowledgeDegradation?: () => void;
  onChangeProvider?: () => void;
  onRetry?: () => void;
  isAcknowledging?: boolean;
}): JSX.Element {
  switch (view.kind) {
    case "verified":
      return (
        <Alert tone="good">
          <p>{view.message}</p>
          {view.embeddingDim !== null && (
            <p className="mt-1 text-muted-foreground">
              Dimensión del vector verificada: {view.embeddingDim}.
            </p>
          )}
        </Alert>
      );

    case "capability_unverified":
      return (
        <Alert tone="caution">
          <p>{view.message}</p>

          {/* SC-016: nothing is accepted before it is named. */}
          <ul className="mt-2 list-disc space-y-1 pl-6">
            {view.affected.map((feature) => (
              <li key={feature.code}>{feature.message}</li>
            ))}
          </ul>

          {view.acknowledged ? (
            <p className="mt-3 text-muted-foreground">
              Confirmaste que entiendes qué funciones no estarán disponibles.
            </p>
          ) : (
            <div className="mt-3 flex flex-wrap gap-2">
              <Button size="sm" onClick={onAcknowledgeDegradation} disabled={isAcknowledging}>
                {isAcknowledging ? "Guardando…" : "Entiendo lo que pierdo y quiero continuar"}
              </Button>
              <Button size="sm" variant="outline" onClick={onChangeProvider}>
                Elegir otro proveedor
              </Button>
            </div>
          )}
        </Alert>
      );

    case "credential_rejected":
      return (
        <Alert tone="bad">
          <p>{view.message}</p>
          {view.consoleUrl !== null && (
            <p className="mt-2">
              <a className="underline" href={view.consoleUrl} target="_blank" rel="noreferrer">
                Abrir la consola de tu proveedor
              </a>
            </p>
          )}
        </Alert>
      );

    case "quota_exceeded":
      return (
        <Alert tone="caution">
          <p>{view.message}</p>
          <div className="mt-3">
            <Button size="sm" variant="outline" onClick={onChangeProvider}>
              Elegir otro proveedor
            </Button>
          </div>
        </Alert>
      );

    case "provider_unreachable":
      return (
        <Alert tone="caution">
          <p>{view.message}</p>
          {/* The key is still in the form: retrying must not ask for it again. */}
          <div className="mt-3">
            <Button size="sm" variant="outline" onClick={onRetry}>
              Reintentar
            </Button>
          </div>
        </Alert>
      );
  }
}
