import { Navigate, Outlet } from "react-router-dom";

import { messageOf } from "@/features/setup/hooks/apiError";
import {
  useSetupState,
  type SetupState,
  type SetupStep,
} from "@/features/setup/hooks/useSetupState";

/**
 * What a route needs to be true of the first run before it may render.
 *
 * `complete` is the onboarding: FR-010 keeps it out of reach until generation
 * is configured, and FR-002 until the disclosure is acknowledged. `step` is one
 * page of the wizard, reachable only while it is the pending one.
 */
export type Requirement = { kind: "complete" } | { kind: "step"; step: SetupStep };

export function stepPath(step: SetupStep): string {
  return `/setup/${step}`;
}

function Waiting(): JSX.Element {
  return (
    <main className="mx-auto max-w-2xl p-8">
      <p className="text-muted-foreground">Comprobando en qué punto va tu configuración…</p>
    </main>
  );
}

function Unreachable({ message }: { message: string }): JSX.Element {
  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-2xl font-semibold">Vokara</h1>
      <p className="mt-4">{message}</p>
    </main>
  );
}

/**
 * The convenience guard of the SPA — and it is only a convenience.
 *
 * US1 AC2 asks that no other part of the application be reachable without the
 * acknowledgement, «incluso navegando directamente a la dirección del
 * onboarding», and this is what answers that for someone typing a URL. It is
 * **not** the gate: the gate is on the server, refuses the same request with
 * 409 whether or not a browser is involved, and is verified in
 * `tests/integration/test_server_side_disclosure_gate.py` (SC-011). Deleting
 * this component would degrade the experience; it would not open the door.
 *
 * **A step is guarded by its prerequisites, not by equality with
 * `pending_step`.** The distinction is load-bearing. `pending_step` answers
 * «where do I resume», and while the wizard is running it returns `providers`
 * for an unresolved embeddings as well as for an unresolved generation
 * (`app/domain/setup.py`). Pinning navigation to it would leave `/setup/email`
 * unreachable for anyone who chose not to configure embeddings — and since
 * skipping the mail step is what concludes the first run, they could never
 * finish it. That is precisely the blocking FR-010 forbids: the absence of
 * embeddings degrades features that depend on vectors and says so; it never
 * stops anything.
 *
 * So the prerequisites are the mandatory steps and only those: the
 * acknowledgement for everything (FR-002), and a usable generation provider
 * before the mail step and before the onboarding (FR-010).
 */
function prerequisiteOf(step: SetupStep, state: SetupState): SetupStep | null {
  if (!state.disclosure_acknowledged && step !== "disclosure") return "disclosure";
  if (step === "email" && state.providers.generation?.is_usable !== true) return "providers";
  return null;
}

export function FirstRunGuard({ requires }: { requires: Requirement }): JSX.Element {
  const state = useSetupState();

  if (state.isPending) return <Waiting />;
  if (state.isError) return <Unreachable message={messageOf(state.error)} />;

  const pending = state.data.pending_step ?? null;

  // The first run is over: it never shows again, in either direction (FR-015).
  if (requires.kind === "complete") {
    return pending === null ? <Outlet /> : <Navigate to={stepPath(pending)} replace />;
  }
  if (pending === null) return <Navigate to="/onboarding" replace />;

  const missing = prerequisiteOf(requires.step, state.data);
  return missing === null ? <Outlet /> : <Navigate to={stepPath(missing)} replace />;
}

/**
 * Where `/` lands: the pending step, or the onboarding once there is none.
 *
 * This is the automatic resume of FR-014 — reopening the application returns
 * the candidate to exactly the step that is missing, without asking again for
 * the acknowledgement or for a key already verified.
 */
export function FirstRunEntry(): JSX.Element {
  const state = useSetupState();

  if (state.isPending) return <Waiting />;
  if (state.isError) return <Unreachable message={messageOf(state.error)} />;

  const pending = state.data.pending_step ?? null;
  return <Navigate to={pending === null ? "/onboarding" : stepPath(pending)} replace />;
}
