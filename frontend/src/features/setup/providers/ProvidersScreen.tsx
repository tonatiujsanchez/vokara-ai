/**
 * El paso de providers del wizard. Contenido en T068 y T069.
 *
 * T066 lo enruta y lo protege con el guard; esta versión existe para que la
 * tabla de rutas sea navegable y el guard verificable antes de que la pantalla
 * tenga su contenido.
 */
export function ProvidersScreen(): JSX.Element {
  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-2xl font-semibold">Tus proveedores de IA</h1>
    </main>
  );
}
