import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { components } from "@/api/schema";

import { unwrap } from "./apiError";
import { setupStateKey } from "./useSetupState";
import type { Capability } from "./useProviderCatalog";

export type ProviderConfiguration = components["schemas"]["ProviderConfigurationModel"];

export interface ConfigureRequest {
  capability: Capability;
  provider: string;
  apiKey: string;
}

/**
 * Saves one capability, which is also what runs its preflight.
 *
 * The preflight happens here and not at first real use (FR-006), so this
 * mutation either returns a configuration with its outcome or fails with one of
 * the catalogue's codes. Both are results, and `PreflightResult` tells the five
 * apart.
 *
 * The key travels in the body and is never returned, never stored on this side
 * and never put in a query cache: what comes back says `configured`,
 * `not_configured` or `rejected`, and nothing else can be said (FR-008).
 */
export function useConfigureCapability(): UseMutationResult<
  ProviderConfiguration,
  Error,
  ConfigureRequest
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ capability, provider, apiKey }: ConfigureRequest) =>
      unwrap(
        api.PUT("/api/v1/setup/providers/{capability}", {
          params: { path: { capability } },
          body: { provider, api_key: apiKey },
        }),
      ),
    onSettled: () => queryClient.invalidateQueries({ queryKey: setupStateKey }),
  });
}

/**
 * The specific acknowledgement of a specific degradation (FR-007.3, SC-016).
 *
 * Per capability, because that is the scope of what is being accepted: losing
 * semantic matching is not the same decision as risking the CV parse, and one
 * yes must not cover the other.
 */
export function useAcknowledgeDegradation(): UseMutationResult<
  ProviderConfiguration,
  Error,
  Capability
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (capability: Capability) =>
      unwrap(
        api.POST("/api/v1/setup/providers/{capability}/degradation-acknowledgement", {
          params: { path: { capability } },
        }),
      ),
    onSettled: () => queryClient.invalidateQueries({ queryKey: setupStateKey }),
  });
}
