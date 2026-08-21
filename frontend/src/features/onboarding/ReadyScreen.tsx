import { Link } from "react-router-dom";

/**
 * Where the first run ends: «listo para subir CV» (FR-015, quickstart §3 paso 15).
 *
 * The upload itself is US2 and lands in `onboarding/upload/`. Until then this
 * screen says what is true — the configuration is done and the wizard will not
 * come back — and does not offer a button that would not work. Announcing a
 * capability the build does not have is the kind of claim art. IV forbids about
 * a candidate's history, and it is no better made about Vokara itself.
 */
export function ReadyScreen(): JSX.Element {
  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-2xl font-semibold">Todo listo</h1>
      <p className="mt-2 text-muted-foreground">
        Terminaste la configuración inicial. No volverá a aparecer.
      </p>

      <section className="mt-8 rounded-lg border p-4">
        <h2 className="text-lg font-medium">El siguiente paso es tu CV</h2>
        <p className="mt-2">
          Con tu proveedor de generación verificado, Vokara ya puede leer tu CV y armar tu perfil a
          partir de él. La pantalla para subirlo llega con el onboarding.
        </p>
      </section>

      <p className="mt-6 text-sm text-muted-foreground">
        ¿Algo no responde?{" "}
        <Link className="underline" to="/status">
          Revisa el estado de la instalación
        </Link>
        .
      </p>
    </main>
  );
}
