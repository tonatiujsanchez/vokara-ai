import { useMutation, useQuery, type UseMutationResult, type UseQueryResult } from "@tanstack/react-query";
import { useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { components } from "@/api/schema";

import { unwrap } from "./apiError";
import { setupStateKey, type SetupState } from "./useSetupState";

export type Disclosure = components["schemas"]["DisclosureModel"];

export const disclosureKey = ["setup", "disclosure"] as const;

export function useDisclosure(): UseQueryResult<Disclosure, Error> {
  return useQuery({
    queryKey: disclosureKey,
    queryFn: () => unwrap(api.GET("/api/v1/setup/disclosure")),
  });
}

/**
 * Records the acknowledgement, and only ever an affirmative one.
 *
 * The version travels with it because an acknowledgement of an older text is a
 * yes to something else (FR-002, research R-29); the server refuses one, and
 * sending the version the candidate actually read is this side's half of that.
 *
 * Invalidating the setup state is what advances the wizard: the guard re-reads
 * `pending_step` and the router moves on by itself.
 */
export function useAcknowledgeDisclosure(): UseMutationResult<SetupState, Error, string> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (version: string) =>
      unwrap(
        api.POST("/api/v1/setup/disclosure-acknowledgement", {
          body: { disclosure_version: version, acknowledged: true },
        }),
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: setupStateKey });
      await queryClient.invalidateQueries({ queryKey: disclosureKey });
    },
  });
}
