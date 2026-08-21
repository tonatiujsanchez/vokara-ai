/**
 * El paso de disclosure del wizard. Contenido en T067.
 *
 * T066 lo enruta y lo protege con el guard; esta versión existe para que la
 * tabla de rutas sea navegable y el guard verificable antes de que la pantalla
 * tenga su contenido.
 */
export function DisclosureScreen(): JSX.Element {
  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-2xl font-semibold">Antes de empezar</h1>
    </main>
  );
}
