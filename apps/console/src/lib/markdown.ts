/** A small, safe markdown renderer for the draft preview. Every character is escaped first, so
 * nothing in a draft can inject markup; only the constructs a long-form draft uses are turned
 * into tags: headings, paragraphs, lists, bold, italic and links to this site or https pages. */
const escapeHtml = (value: string) =>
  value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
const safeHref = (href: string) =>
  /^(\/(?!\/)|https:\/\/)[^\s"'<>]*$/i.test(href) ? href : null;
function inline(raw: string): string {
  let text = escapeHtml(raw);
  text = text.replace(
    /\[([^\]\n]+)\]\(([^)\s]+)\)/g,
    (whole, label: string, href: string) => {
      const target = safeHref(href.replaceAll("&amp;", "&"));
      return target ? `<a href="${escapeHtml(target)}">${label}</a>` : label;
    },
  );
  text = text.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
  text = text.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, "$1<em>$2</em>");
  return text;
}
export function renderMarkdown(source: string): string {
  const out: string[] = [];
  let list: "ul" | "ol" | null = null;
  let paragraph: string[] = [];
  const flushParagraph = () => {
    if (paragraph.length) out.push(`<p>${inline(paragraph.join(" "))}</p>`);
    paragraph = [];
  };
  const closeList = () => {
    if (list) out.push(`</${list}>`);
    list = null;
  };
  for (const line of source.split("\n")) {
    const heading = /^(#{2,3})\s+(.+?)\s*$/.exec(line);
    const bullet = /^\s*[-*]\s+(.+)$/.exec(line);
    const numbered = /^\s*\d+[.)]\s+(.+)$/.exec(line);
    if (!line.trim()) {
      flushParagraph();
      closeList();
    } else if (heading) {
      flushParagraph();
      closeList();
      const level = heading[1].length;
      out.push(`<h${level}>${inline(heading[2])}</h${level}>`);
    } else if (bullet || numbered) {
      flushParagraph();
      const kind = bullet ? "ul" : "ol";
      if (list !== kind) {
        closeList();
        out.push(`<${kind}>`);
        list = kind;
      }
      out.push(`<li>${inline((bullet ?? numbered)![1])}</li>`);
    } else {
      closeList();
      paragraph.push(line.trim());
    }
  }
  flushParagraph();
  closeList();
  return out.join("\n");
}
export interface OutlineEntry {
  level: 2 | 3;
  text: string;
}
/** The headings of a draft, in order, for the outline. */
export function outline(source: string): OutlineEntry[] {
  return [...source.matchAll(/^(#{2,3})\s+(.+?)\s*$/gm)].map((m) => ({
    level: m[1].length as 2 | 3,
    text: m[2].replace(/[*_`]/g, ""),
  }));
}
export const wordCount = (source: string): number =>
  (source.match(/[\w'-]+/g) ?? []).length;
