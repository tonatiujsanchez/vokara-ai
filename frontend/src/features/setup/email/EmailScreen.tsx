import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { messageOf } from "@/features/setup/hooks/apiError";
import { useEmailStep, useLinkEmail, useSkipEmail } from "@/features/setup/hooks/useEmailStep";

import { EmailDisclosure } from "./EmailDisclosure";
import { EmailLinkForm } from "./EmailLinkForm";

/**
 * The optional step, and visibly optional (FR-011, FR-012, US1 AC9-AC10).
 *
 * Three properties are requirements rather than layout preferences:
 *
 * - **Skipping weighs the same as continuing.** Same variant, same size, side by
 *   side. A «quizá más tarde» in grey text under a primary button is not an
 *   equal option, it is a discouraged one, and FR-011 asks for «el mismo peso
 *   visual» precisely because that pattern is so easy to reach for.
 * - **Both halves of the sentence.** What is gained by linking and what is
 *   **not** lost by skipping, both on screen, because someone choosing between
 *   two options deserves to know what each costs.
 * - **The disclosure comes first.** It is on screen before the form exists, and
 *   the form only appears once the candidate has chosen to link (FR-012).
 *
 * Neither ending navigates by hand: resolving the step changes `pending_step`
 * to `null` and the guard moves on. The first run is over either way.
 */
export function EmailScreen(): JSX.Element {
  const step = useEmailStep();
  const link = useLinkEmail();
  const skip = useSkipEmail();
  const [linking, setLinking] = useState(false);

  if (step.isPending) {
    return (
      <main className="mx-auto max-w-2xl p-8">
        <p className="text-muted-foreground">Cargando…</p>
      </main>
    );
  }

  if (step.isError) {
    return (
      <main className="mx-auto max-w-2xl p-8">
        <h1 className="text-2xl font-semibold">Vincular tu correo</h1>
        <p className="mt-4">{messageOf(step.error)}</p>
      </main>
    );
  }

  const busy = link.isPending || skip.isPending;

  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-2xl font-semibold">Vincular tu correo</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Este paso es opcional. Puedes omitirlo ahora y vincularlo cuando quieras.
      </p>

      <Card className="mt-6">
        <h2 className="text-lg font-medium">Qué ganas y qué no pierdes</h2>
        <p className="mt-2 text-sm">
          <span className="font-medium">Si lo vinculas: </span>
          {step.data.value_if_linked_es}
        </p>
        <p className="mt-2 text-sm">
          <span className="font-medium">Si lo omites: </span>
          {step.data.value_if_skipped_es}
        </p>
      </Card>

      {/* FR-012: el aviso, antes de que exista ningún campo que llenar. */}
      <EmailDisclosure
        disclosureMd={step.data.disclosure_md}
        oauthDocsUrl={step.data.oauth_docs_url}
      />

      {step.data.configuration_notice_es != null && (
        <p className="mt-4 text-sm text-muted-foreground">{step.data.configuration_notice_es}</p>
      )}

      {/* Las dos salidas, con el mismo peso: misma variante y mismo tamaño. */}
      <div className="mt-6 flex flex-wrap gap-3">
        <Button disabled={busy} onClick={() => setLinking(true)}>
          Vincular mi Gmail
        </Button>
        <Button disabled={busy} onClick={() => skip.mutate()}>
          {skip.isPending ? "Omitiendo…" : "Omitir este paso"}
        </Button>
      </div>

      {skip.isError && (
        <p role="alert" className="mt-4 text-sm">
          {messageOf(skip.error)}
        </p>
      )}

      {linking && (
        <EmailLinkForm
          onSubmit={(values) => link.mutate(values)}
          isSubmitting={link.isPending}
          error={link.isError ? messageOf(link.error) : null}
        />
      )}
    </main>
  );
}
