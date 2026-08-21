import { Navigate, Outlet } from "react-router-dom";

import { messageOf } from "@/features/setup/hooks/apiError";
import { useSetupState, type SetupStep } from "@/features/setup/hooks/useSetupState";

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
 * The pending step is read from the server on every navigation rather than
 * kept here, so that a step resolved in another tab, a credential rotated in
 * configuration or a two-week gap all land on the right page without any
 * repair logic (FR-014, research R-18).
 */
export function FirstRunGuard({ requires }: { requires: Requirement }): JSX.Element {
  const state = useSetupState();

  if (state.isPending) {
    return (
      <main className="mx-auto max-w-2xl p-8">
        <p className="text-muted-foreground">Comprobando en qué punto va tu configuración…</p>
      </main>
    );
  }

  if (state.isError) {
    return (
      <main className="mx-auto max-w-2xl p-8">
        <h1 className="text-2xl font-semibold">Vokara</h1>
        <p className="mt-4">{messageOf(state.error)}</p>
      </main>
    );
  }

  const pending = state.data.pending_step ?? null;

  if (requires.kind === "complete") {
    return pending === null ? <Outlet /> : <Navigate to={stepPath(pending)} replace />;
  }

  // The first run is over: the wizard never shows again (FR-015).
  if (pending === null) return <Navigate to="/onboarding" replace />;

  // A step further along than the pending one is not reachable by typing it.
  return pending === requires.step ? <Outlet /> : <Navigate to={stepPath(pending)} replace />;
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

  if (state.isPending) {
    return (
      <main className="mx-auto max-w-2xl p-8">
        <p className="text-muted-foreground">Comprobando en qué punto va tu configuración…</p>
      </main>
    );
  }

  if (state.isError) {
    return (
      <main className="mx-auto max-w-2xl p-8">
        <h1 className="text-2xl font-semibold">Vokara</h1>
        <p className="mt-4">{messageOf(state.error)}</p>
      </main>
    );
  }

  const pending = state.data.pending_step ?? null;
  return <Navigate to={pending === null ? "/onboarding" : stepPath(pending)} replace />;
}
