import { useEffect, useState } from "react";

import { api } from "@/api/client";
import type { components } from "@/api/schema";

type Health = components["schemas"]["HealthResponse"];

type State =
  | { kind: "loading" }
  | { kind: "ready"; health: Health }
  | { kind: "unreachable" };

export function StatusScreen(): JSX.Element {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;

    void api.GET("/api/v1/health").then(({ data }) => {
      if (cancelled) return;
      setState(data ? { kind: "ready", health: data } : { kind: "unreachable" });
    });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-2xl font-semibold">Vokara</h1>
      <p className="mt-2 text-muted-foreground">
        Tu agente de búsqueda de empleo, ejecutándose en tu computadora.
      </p>

      <section className="mt-8 rounded-lg border p-4" aria-labelledby="estado">
        <h2 id="estado" className="text-lg font-medium">
          Estado de la instalación
        </h2>

        {state.kind === "loading" && <p className="mt-2 text-muted-foreground">Comprobando…</p>}

        {state.kind === "unreachable" && (
          <p className="mt-2">
            No pudimos comunicarnos con el servicio local. Revisa que Docker esté corriendo.
          </p>
        )}

        {state.kind === "ready" && (
          <dl className="mt-2 grid grid-cols-2 gap-y-1">
            <dt className="text-muted-foreground">Servicio</dt>
            <dd>{state.health.status}</dd>
            <dt className="text-muted-foreground">Base de datos</dt>
            <dd>{state.health.database}</dd>
            <dt className="text-muted-foreground">Migración aplicada</dt>
            <dd>{state.health.migration_revision ?? "sin aplicar"}</dd>
          </dl>
        )}
      </section>
    </main>
  );
}
