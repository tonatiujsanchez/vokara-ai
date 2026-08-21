import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Markdown } from "@/lib/markdown";

// The real disclosure, not a sample of it: the fixture is a byte-for-byte copy
// of DISCLOSURE_BODY_MD, kept honest by
// backend/tests/unit/test_disclosure_fixture_sync.py. Asserting losslessness
// over a text the application does not show would prove nothing (FR-001).
//
// `?raw` rather than `readFileSync`: the test runs in jsdom, where
// `import.meta.url` is not a file URL, and Vite inlines the fixture at
// transform time so the text is the file on disk either way.
import DISCLOSURE from "../fixtures/disclosure.md?raw";

/**
 * The visible text of a source, derived **without** the renderer's parser.
 *
 * Deliberately a different algorithm — split on blank lines with a regex, then
 * strip the four supported markers — so that a bug in the line-by-line parser
 * cannot be mirrored here and cancel itself out.
 */
function visibleBlocks(source: string): string[] {
  return source
    .split(/\n[ \t]*\n/)
    .flatMap((block) => (block.includes("- ") ? block.split(/\n(?=- )/) : [block]))
    .map((text) =>
      text
        .replace(/^#{2,3} /, "")
        .replace(/^- /, "")
        .replace(/\*\*/g, "")
        .replace(/\s+/g, " ")
        .trim(),
    )
    .filter(Boolean);
}

/** What actually reached the DOM, block by block, in order. */
function renderedBlocks(container: HTMLElement): string[] {
  return Array.from(container.querySelectorAll("h2, h3, li, p")).map((element) =>
    (element.textContent ?? "").replace(/\s+/g, " ").trim(),
  );
}

describe("renderizador de Markdown", () => {
  it("lleva el texto COMPLETO de la divulgación a pantalla, sin pérdida (FR-001)", () => {
    const { container } = render(<Markdown source={DISCLOSURE} />);

    expect(renderedBlocks(container)).toEqual(visibleBlocks(DISCLOSURE));
  });

  it("no pierde ni una palabra del original", () => {
    const { container } = render(<Markdown source={DISCLOSURE} />);

    const rendered = renderedBlocks(container).join(" ");
    const words = DISCLOSURE.replace(/^#{2,3} /gm, "")
      .replace(/^- /gm, "")
      .replace(/\*\*/g, "")
      .split(/\s+/)
      .filter(Boolean);

    for (const word of words) expect(rendered).toContain(word);
  });

  it("aplica los cuatro constructos de la lista blanca y ninguno más", () => {
    const { container } = render(
      <Markdown source={"## Título\n\n### Subtítulo\n\nUn **dato** importante.\n\n- uno\n- dos"} />,
    );

    expect(container.querySelector("h2")?.textContent).toBe("Título");
    expect(container.querySelector("h3")?.textContent).toBe("Subtítulo");
    expect(container.querySelector("strong")?.textContent).toBe("dato");
    expect(container.querySelectorAll("li")).toHaveLength(2);
  });

  it("une las negritas que cruzan un salto de línea suave", () => {
    const { container } = render(<Markdown source={"**Si tu cuenta es de Workspace,\nno va a funcionar** y por eso lo decimos antes."} />);

    expect(container.querySelector("strong")?.textContent).toBe(
      "Si tu cuenta es de Workspace, no va a funcionar",
    );
  });

  it("une las continuaciones indentadas de un ítem de lista", () => {
    const { container } = render(<Markdown source={"- El contenido de tu CV, íntegro,\n  cuando lo subes."} />);

    expect(container.querySelector("li")?.textContent).toBe(
      "El contenido de tu CV, íntegro, cuando lo subes.",
    );
  });
});

describe("lo que la lista blanca no soporta", () => {
  it.each([
    ["un enlace", "Consulta [la guía](https://ejemplo.invalid/guia) antes."],
    ["una tabla", "| Proveedor | Costo |\n| --- | --- |\n| uno | dos |"],
    ["un encabezado de nivel 1", "# Título de nivel uno"],
    ["un encabezado de nivel 4", "#### Título de nivel cuatro"],
    ["una cita", "> Algo que alguien dijo."],
    ["una lista numerada", "1. Primero\n2. Segundo"],
    ["código en línea", "Ejecuta `docker compose up` y espera."],
    ["una cursiva", "Esto es *importante* también."],
    ["una regla horizontal", "---"],
  ])("muestra %s como texto plano en vez de descartarlo", (_name, source) => {
    const { container } = render(<Markdown source={source} />);

    const rendered = renderedBlocks(container).join(" ");
    for (const word of source.split(/\s+/).filter(Boolean)) {
      expect(rendered).toContain(word);
    }
  });

  it("no interpreta HTML crudo: lo enseña como texto y no crea nodos", () => {
    const { container } = render(
      <Markdown source={"<script>alert(1)</script> y un <b>negrita falsa</b>."} />,
    );

    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("b")).toBeNull();
    expect(container.textContent).toContain("<script>alert(1)</script>");
    expect(container.textContent).toContain("<b>negrita falsa</b>");
  });

  it("deja intactos unos asteriscos sin pareja", () => {
    const { container } = render(<Markdown source={"Un **dato a medias y nada más."} />);

    expect(container.querySelector("strong")).toBeNull();
    expect(container.textContent).toContain("**dato a medias");
  });
});
