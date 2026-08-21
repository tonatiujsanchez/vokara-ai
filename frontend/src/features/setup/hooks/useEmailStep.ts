import { useMutation, useQuery, useQueryClient, type UseMutationResult, type UseQueryResult } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { components } from "@/api/schema";

import { unwrap } from "./apiError";
import { setupStateKey, type SetupState } from "./useSetupState";

export type EmailStep = components["schemas"]["EmailStepModel"];

export interface LinkRequest {
  emailAddress: string;
  appPassword: string;
  label: string;
}

export const emailStepKey = ["setup", "email"] as const;

/**
 * The optional step, with everything needed to decide it in one answer.
 *
 * The disclosure travels **with** the state and not behind a second request,
 * because FR-012 requires the warning before the configuration starts: a
 * disclosure that needs its own round trip is a disclosure that can arrive late.
 */
export function useEmailStep(): UseQueryResult<EmailStep, Error> {
  return useQuery({
    queryKey: emailStepKey,
    queryFn: () => unwrap(api.GET("/api/v1/setup/email")),
  });
}

/**
 * Links the mailbox: the App Password is sent once and never comes back.
 *
 * It follows the rules of an API key exactly (FR-013 defers to FR-008), so it
 * is not kept here, not cached and not logged. The label is verified server
 * side before the link is taken as established, which is why the three failures
 * of this call are ordinary results and none of them blocks anything.
 */
export function useLinkEmail(): UseMutationResult<EmailStep, Error, LinkRequest> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ emailAddress, appPassword, label }: LinkRequest) =>
      unwrap(
        api.POST("/api/v1/setup/email/link", {
          body: { email_address: emailAddress, app_password: appPassword, label },
        }),
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: emailStepKey });
      await queryClient.invalidateQueries({ queryKey: setupStateKey });
    },
  });
}

/** Skipping: one action, and a valid ending to the first run (FR-011). */
export function useSkipEmail(): UseMutationResult<SetupState, Error, void> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/setup/email/skip")),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: emailStepKey });
      await queryClient.invalidateQueries({ queryKey: setupStateKey });
    },
  });
}
