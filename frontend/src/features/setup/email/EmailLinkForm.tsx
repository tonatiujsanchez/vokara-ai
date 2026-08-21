import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/**
 * The three things linking needs, asked for only after the warning was given.
 *
 * The label is one of them and not an afterthought: it is what Vokara reads and
 * the only thing it reads, and the server checks it exists before taking the
 * link as established (FR-013). Asking for it here is what makes that promise
 * checkable.
 */
export function EmailLinkForm({
  onSubmit,
  isSubmitting,
  error,
}: {
  onSubmit: (values: { emailAddress: string; appPassword: string; label: string }) => void;
  isSubmitting: boolean;
  error: string | null;
}): JSX.Element {
  const [emailAddress, setEmailAddress] = useState("");
  const [appPassword, setAppPassword] = useState("");
  const [label, setLabel] = useState("");

  const incomplete = emailAddress === "" || appPassword === "" || label === "";

  return (
    <Card className="mt-4">
      <h2 className="text-lg font-medium">Vincular</h2>

      <div className="mt-4">
        <Label htmlFor="email-address">Tu dirección de Gmail</Label>
        <Input
          id="email-address"
          type="email"
          autoComplete="off"
          className="mt-1"
          value={emailAddress}
          onChange={(event) => setEmailAddress(event.target.value)}
        />
      </div>

      <div className="mt-4">
        <Label htmlFor="app-password">App Password</Label>
        <Input
          id="app-password"
          type="password"
          autoComplete="off"
          className="mt-1"
          value={appPassword}
          onChange={(event) => setAppPassword(event.target.value)}
        />
      </div>

      <div className="mt-4">
        <Label htmlFor="etiqueta">Etiqueta que Vokara va a leer</Label>
        <Input
          id="etiqueta"
          className="mt-1"
          value={label}
          onChange={(event) => setLabel(event.target.value)}
        />
        <p className="mt-1 text-xs text-muted-foreground">
          La única que va a leer. Créala en Gmail y manda ahí tus alertas de empleo con un filtro.
        </p>
      </div>

      {error !== null && (
        <p role="alert" className="mt-4 text-sm">
          {error}
        </p>
      )}

      <Button
        className="mt-4"
        disabled={incomplete || isSubmitting}
        onClick={() => onSubmit({ emailAddress, appPassword, label })}
      >
        {isSubmitting ? "Verificando…" : "Vincular mi correo"}
      </Button>
    </Card>
  );
}
