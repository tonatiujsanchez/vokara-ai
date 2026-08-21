import type { ReactNode } from "react";

/**
 * A Markdown renderer with a strict whitelist: `##`, `###`, `- ` and `**bold**`.
 *
 * It exists to put the disclosure of article V on screen — the one page where
 * the candidate decides whether to trust Vokara — so two properties matter more
 * than completeness:
 *
 * **Nothing is dropped in silence.** Anything outside the whitelist renders as
 * plain text with its markers visible: a table, a link, a `#` heading or a
 * numbered list all appear literally. FR-001 requires the complete text on
 * screen, and a renderer that quietly swallowed a construct would satisfy the
 * type checker while showing the candidate less than they were promised. Seeing
 * `[algo](url)` on screen is ugly; not seeing `algo` at all is a bug in the
 * disclosure.
 *
 * **No HTML, and no `dangerouslySetInnerHTML`.** Raw HTML in the source is text
 * like any other, because React escapes what it renders. There is no path from
 * the string to the DOM that is not an element built here.
 *
 * Not a general Markdown implementation, and not trying to be: the source is a
 * constant of the backend (`app/domain/disclosure.py`,
 * `app/adapters/email/gmail_imap.py`), never anything a user typed, so the set
 * of constructs is closed and `tests/setup/markdown.test.tsx` pins it. Pulling
 * remark, unified and mdast in for four constructs is the kind of dependency
 * tree article VII asks us to justify, and this one does not justify itself.
 */

type Block =
  | { kind: "h2"; text: string }
  | { kind: "h3"; text: string }
  | { kind: "list"; items: string[] }
  | { kind: "p"; text: string };

/** A soft wrap is not a line break: the paragraph is one flow of text. */
function join(lines: string[]): string {
  return lines.join(" ").replace(/\s+/g, " ").trim();
}

function toList(lines: string[]): Block {
  const items: string[][] = [];
  for (const line of lines) {
    if (line.startsWith("- ")) items.push([line.slice(2)]);
    else items[items.length - 1]?.push(line.trim());
  }
  return { kind: "list", items: items.map(join) };
}

function toBlock(lines: string[]): Block | null {
  const first = lines[0];
  if (first === undefined) return null;

  const rest = lines.slice(1);
  if (first.startsWith("### ")) return { kind: "h3", text: join([first.slice(4), ...rest]) };
  if (first.startsWith("## ")) return { kind: "h2", text: join([first.slice(3), ...rest]) };
  if (lines.some((line) => line.startsWith("- "))) return toList(lines);

  return { kind: "p", text: join(lines) };
}

/** Blocks are separated by a blank line, and by nothing else. */
function parse(source: string): Block[] {
  const blocks: Block[] = [];
  let current: string[] = [];

  for (const line of source.split("\n")) {
    if (line.trim() === "") {
      const block = toBlock(current);
      if (block) blocks.push(block);
      current = [];
    } else {
      current.push(line);
    }
  }

  const last = toBlock(current);
  if (last) blocks.push(last);
  return blocks;
}

/** `**bold**`, and every other marker left exactly as it was written. */
function inline(text: string): ReactNode[] {
  return text
    .split(/\*\*(.+?)\*\*/g)
    .map((part, index) => (index % 2 === 1 ? <strong key={index}>{part}</strong> : part));
}

export function Markdown({ source }: { source: string }): JSX.Element {
  return (
    <>
      {parse(source).map((block, index) => {
        switch (block.kind) {
          case "h2":
            return (
              <h2 key={index} className="mt-6 text-lg font-medium first:mt-0">
                {inline(block.text)}
              </h2>
            );
          case "h3":
            return (
              <h3 key={index} className="mt-5 font-medium">
                {inline(block.text)}
              </h3>
            );
          case "list":
            return (
              <ul key={index} className="mt-2 list-disc space-y-1 pl-6">
                {block.items.map((item, position) => (
                  <li key={position}>{inline(item)}</li>
                ))}
              </ul>
            );
          case "p":
            return (
              <p key={index} className="mt-2">
                {inline(block.text)}
              </p>
            );
        }
      })}
    </>
  );
}
