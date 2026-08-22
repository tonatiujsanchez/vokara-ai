import { Card } from "@/components/ui/card";
import { Markdown } from "@/lib/markdown";

/**
 * The warning of FR-012, and it is only a warning if it comes first.
 *
 * «Ese aviso MUST darse antes de empezar la configuración, NEVER a mitad de
 * ella» — so this renders on arrival, above everything, and the form is not on
 * screen yet when it does. A notice that appears next to a field the candidate
 * has already filled in is not informing a decision; it is narrating one that
 * was already made.
 *
 * The text is the backend's, whole: it is the adapter that may name the mail
 * provider (art. XI keeps that name out of the domain), and it is the adapter
 * that writes what an App Password actually grants.
 */
export function EmailDisclosure({
  disclosureMd,
  oauthDocsUrl,
}: {
  disclosureMd: string;
  oauthDocsUrl: string;
}): JSX.Element {
  return (
    <Card className="mt-6">
      <article className="text-sm leading-relaxed">
        <Markdown source={disclosureMd} />
      </article>
      <p className="mt-4 text-sm">
        <a className="underline" href={oauthDocsUrl} target="_blank" rel="noreferrer">
          La vía OAuth, para cuentas que no admiten App Passwords
        </a>
      </p>
    </Card>
  );
}
