import type { components } from "@/api/schema";

type EstimatedCost = components["schemas"]["EstimatedCostModel"];

/**
 * What a provider costs per month of active search, **before** any key is asked
 * for (FR-005).
 *
 * A figure never travels without the assumption that produced it, because a
 * number without its assumption is not interpretable: «4 USD» means nothing
 * until you know for how much searching.
 *
 * When there is no figure yet, this says so. Inventing a plausible one would be
 * exactly the fabrication art. IV forbids about a candidate's history, and it is
 * no more acceptable when the subject is Vokara itself.
 */
export function EstimatedCost({ cost }: { cost: EstimatedCost }): JSX.Element {
  return (
    <div className="text-sm">
      {cost.is_estimated && cost.amount_usd != null ? (
        <>
          <p>
            <span className="font-medium">
              ~{cost.amount_usd} {cost.currency} al mes
            </span>{" "}
            de búsqueda activa.
          </p>
          {cost.usage_assumption_es != null && (
            <p className="text-muted-foreground">{cost.usage_assumption_es}</p>
          )}
        </>
      ) : (
        <p className="text-muted-foreground">{cost.pending_note_es}</p>
      )}

      {cost.has_free_tier === true && cost.free_tier_note_es != null && (
        <p className="mt-1 text-muted-foreground">{cost.free_tier_note_es}</p>
      )}
    </div>
  );
}
