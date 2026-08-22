import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import type { ProviderOption } from "@/features/setup/hooks/useProviderCatalog";

import { EstimatedCost } from "./EstimatedCost";

/**
 * One capability's choice: the options the backend offers, each with its cost.
 *
 * **No key is asked for here.** The credentials come after both capabilities
 * have shown their cost, which is what FR-005 means by «antes de solicitar cada
 * API key» — a cost that appears below the field it is meant to inform arrives
 * too late to inform anything.
 *
 * Options are rendered, never filtered or reordered on this side: a provider
 * missing from the list is missing because its verification is not on record
 * (FR-009), and deciding that is the backend's job (art. XI).
 */
export function CapabilityConfiguration({
  title,
  explanation,
  options,
  selected,
  onSelect,
  children,
}: {
  title: string;
  explanation: string;
  options: ProviderOption[];
  selected: string;
  onSelect: (provider: string) => void;
  children?: React.ReactNode;
}): JSX.Element {
  return (
    <Card className="mt-4">
      <h2 className="text-lg font-medium">{title}</h2>
      <p className="mt-1 text-sm text-muted-foreground">{explanation}</p>

      <fieldset className="mt-4 space-y-3">
        <legend className="sr-only">{title}</legend>

        {options.map((option) => (
          <div key={option.provider} className="rounded-md border p-3">
            <div className="flex items-center gap-3">
              <input
                type="radio"
                id={`${title}-${option.provider}`}
                name={title}
                value={option.provider}
                checked={selected === option.provider}
                onChange={() => onSelect(option.provider)}
                className="h-4 w-4 accent-primary"
              />
              <Label htmlFor={`${title}-${option.provider}`}>
                {option.display_name}
                {option.is_suggested_default && (
                  <span className="ml-2 text-xs font-normal text-muted-foreground">sugerido</span>
                )}
              </Label>
            </div>

            <div className="mt-2 pl-7">
              <EstimatedCost cost={option.estimated_cost} />
              <p className="mt-1 text-xs text-muted-foreground">Modelo: {option.default_model}</p>
              <p className="mt-1 text-xs">
                <a className="underline" href={option.credential_url} target="_blank" rel="noreferrer">
                  Dónde obtener tu API key
                </a>
              </p>
            </div>
          </div>
        ))}
      </fieldset>

      {children}
    </Card>
  );
}
