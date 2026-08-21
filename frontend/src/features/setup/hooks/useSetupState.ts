import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { components } from "@/api/schema";

import { unwrap } from "./apiError";

export type SetupState = components["schemas"]["SetupStateModel"];
export type SetupStep = components["schemas"]["SetupStep"];

/**
 * Everything the wizard needs to know about where it is.
 *
 * The key is shared so that every mutation of the first run can invalidate it
 * and the guard re-derives the pending step by itself. There is no client-side
 * copy of the progress: the server derives `pending_step` from the facts it
 * persisted (research R-18), and re-reading it is what makes closing the
 * browser mid-way harmless (FR-014).
 */
export const setupStateKey = ["setup", "state"] as const;

export function useSetupState(): UseQueryResult<SetupState, Error> {
  return useQuery({
    queryKey: setupStateKey,
    queryFn: () => unwrap(api.GET("/api/v1/setup/state")),
  });
}
