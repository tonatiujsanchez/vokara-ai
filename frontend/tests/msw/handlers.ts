import { http, HttpResponse, type RequestHandler } from "msw";

import type { components } from "@/api/schema";

import DISCLOSURE_BODY from "../fixtures/disclosure.md?raw";

/**
 * The first-run endpoints, answered the way a fresh installation would.
 *
 * Every shape is typed against the generated schema, never against a hand
 * written copy: rename a field in a Pydantic model and these stop compiling
 * too, which is the only thing that keeps a mock from drifting into a green
 * test over a broken application (art. I).
 *
 * Tests that mount the real route table need these, because the router renders
 * whichever screen the guard sends them to and that screen fetches its own
 * data. `onUnhandledRequest: "error"` makes forgetting one loud.
 */

type SetupState = components["schemas"]["SetupStateModel"];
type Disclosure = components["schemas"]["DisclosureModel"];

// `exactOptionalPropertyTypes` puts `undefined` in the optional field; the
// wizard only ever deals with a step or its absence.
export type PendingStep = NonNullable<SetupState["pending_step"]> | null;

export const DISCLOSURE_VERSION = "2026-08-17";

export function setupState(pending: PendingStep): SetupState {
  return {
    pending_step: pending,
    disclosure_acknowledged: pending !== "disclosure",
    disclosure_acknowledged_at: pending === "disclosure" ? null : "2026-08-20T10:00:00Z",
    providers: { generation: null, embeddings: null },
    email_status: pending === null ? "skipped" : "pending",
    is_complete: pending === null,
  };
}

export const disclosure: Disclosure = {
  version: DISCLOSURE_VERSION,
  body_md: DISCLOSURE_BODY,
  acknowledged: false,
  acknowledged_at: null,
  acknowledged_version: null,
};

/** Everything the wizard reads, so any screen the guard picks can render. */
export function firstRunHandlers(pending: PendingStep): RequestHandler[] {
  return [
    http.get("*/api/v1/setup/state", () => HttpResponse.json(setupState(pending))),
    http.get("*/api/v1/setup/disclosure", () => HttpResponse.json(disclosure)),
  ];
}
