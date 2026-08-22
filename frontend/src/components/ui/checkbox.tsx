import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * A native checkbox, styled.
 *
 * Native rather than a Radix widget for two reasons. It keeps the dependency
 * tree of an installation article VII cares about (`button.tsx` is written the
 * same way, and nothing here needs Radix's behaviour). And it makes «nunca
 * preseleccionado» of FR-002 a property of the DOM the test can read directly:
 * `toBeChecked()` on a real input, with no widget state to mock.
 *
 * It is deliberately **uncontrolled-free**: the caller passes `checked`, so the
 * acknowledgement can never default to true by forgetting a prop.
 */
export interface CheckboxProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "type" | "defaultChecked"> {
  checked: boolean;
}

const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, ...props }, ref) => (
    <input
      type="checkbox"
      className={cn(
        "h-4 w-4 shrink-0 rounded-sm border border-primary accent-primary",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      ref={ref}
      {...props}
    />
  ),
);
Checkbox.displayName = "Checkbox";

export { Checkbox };
