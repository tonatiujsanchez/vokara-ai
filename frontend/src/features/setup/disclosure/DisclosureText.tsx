import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Markdown } from "@/lib/markdown";

/**
 * The disclosure of article V, on screen and whole.
 *
 * Presentational on purpose: what FR-001 and FR-002 demand is visible in the
 * props and checkable without a server. Three properties are requirements, not
 * styling choices:
 *
 * - **The complete text is here**, rendered from `body_md`. Article V forbids it
 *   being only a link or only the README, so there is no «leer más».
 * - **Nothing to fill in.** The screen has one checkbox and one button; the
 *   first thing anyone sees on a fresh installation is what happens to their
 *   data, not a form (FR-001, US1 AC1).
 * - **The acknowledgement is never preselected** and continuing is not
 *   accepting: `acknowledged` arrives false and the button stays disabled until
 *   the candidate says otherwise (FR-002, US1 AC2).
 */
export function DisclosureText({
  bodyMd,
  acknowledged,
  onAcknowledgedChange,
  onContinue,
  isSubmitting,
  error,
}: {
  bodyMd: string;
  acknowledged: boolean;
  onAcknowledgedChange: (value: boolean) => void;
  onContinue: () => void;
  isSubmitting: boolean;
  error: string | null;
}): JSX.Element {
  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-2xl font-semibold">Antes de empezar</h1>

      <article className="mt-6 text-sm leading-relaxed">
        <Markdown source={bodyMd} />
      </article>

      <div className="mt-8 flex items-start gap-3 rounded-lg border p-4">
        <Checkbox
          id="acuse"
          className="mt-1"
          checked={acknowledged}
          onChange={(event) => onAcknowledgedChange(event.target.checked)}
        />
        <Label htmlFor="acuse" className="leading-relaxed">
          Leí esto y entiendo qué se queda en mi computadora y qué se envía a mi proveedor de IA.
        </Label>
      </div>

      {error !== null && (
        <p role="alert" className="mt-4 text-sm">
          {error}
        </p>
      )}

      <Button className="mt-6" disabled={!acknowledged || isSubmitting} onClick={onContinue}>
        {isSubmitting ? "Guardando…" : "Continuar"}
      </Button>
    </main>
  );
}
