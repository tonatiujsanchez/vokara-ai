import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { messageOf } from "@/features/setup/hooks/apiError";
import { useAcknowledgeDisclosure, useDisclosure } from "@/features/setup/hooks/useDisclosure";

import { DisclosureText } from "./DisclosureText";

/**
 * The first screen of a fresh installation (FR-001, US1 AC1).
 *
 * The acknowledgement lives in local state and starts false — the server's
 * `acknowledged` is deliberately **not** used to seed it. Reaching this screen
 * at all means the current text has no acknowledgement on record, so seeding a
 * checkbox from anything would be a step towards a preselected one, which
 * FR-002 forbids outright.
 *
 * **This screen advances itself, and that is not boilerplate.** Its one button
 * means «continue», so continuing is what pressing it does. The guard used to
 * do it as a side effect of the step becoming satisfied, which also dragged the
 * provider step away from a preflight result nobody had read yet (art. X,
 * FR-007). Navigation belongs to the screen that owns the action.
 *
 * The mutation awaits its own invalidation, so by the time this runs the guard
 * on the next step already sees the acknowledgement and will not bounce back.
 */
export function DisclosureScreen(): JSX.Element {
  const disclosure = useDisclosure();
  const acknowledge = useAcknowledgeDisclosure();
  const navigate = useNavigate();
  const [acknowledged, setAcknowledged] = useState(false);

  if (disclosure.isPending) {
    return (
      <main className="mx-auto max-w-2xl p-8">
        <p className="text-muted-foreground">Cargando…</p>
      </main>
    );
  }

  if (disclosure.isError) {
    return (
      <main className="mx-auto max-w-2xl p-8">
        <h1 className="text-2xl font-semibold">Antes de empezar</h1>
        <p className="mt-4">{messageOf(disclosure.error)}</p>
      </main>
    );
  }

  return (
    <DisclosureText
      bodyMd={disclosure.data.body_md}
      acknowledged={acknowledged}
      onAcknowledgedChange={setAcknowledged}
      onContinue={() =>
        acknowledge.mutate(disclosure.data.version, {
          onSuccess: () => void navigate("/setup/providers"),
        })
      }
      isSubmitting={acknowledge.isPending}
      error={acknowledge.isError ? messageOf(acknowledge.error) : null}
    />
  );
}
