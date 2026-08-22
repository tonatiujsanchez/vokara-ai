import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * A short block that says how something went.
 *
 * The tones exist so that four different situations look different — FR-007
 * asks them to be told apart, and a candidate who cannot see at a glance that
 * a quota is not a rejected key has been told four things in one voice.
 */
const alertVariants = cva("rounded-lg border p-4 text-sm", {
  variants: {
    tone: {
      neutral: "bg-muted/40",
      good: "border-emerald-600/40 bg-emerald-50/60",
      caution: "border-amber-600/50 bg-amber-50/60",
      bad: "border-destructive/50 bg-destructive/5",
    },
  },
  defaultVariants: { tone: "neutral" },
});

export interface AlertProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof alertVariants> {}

const Alert = React.forwardRef<HTMLDivElement, AlertProps>(({ className, tone, ...props }, ref) => (
  <div role="status" className={cn(alertVariants({ tone, className }))} ref={ref} {...props} />
));
Alert.displayName = "Alert";

export { Alert, alertVariants };
