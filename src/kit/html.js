// The small amount of markup plumbing the kit needs.
//
// The kit builds DOM from markup strings rather than from htl, so it carries no
// runtime dependency and every piece of markup can be asserted in a plain Node
// test, where there is no document. Escaping matches what htl does with an
// interpolated value, so a title with an ampersand in it comes out the same as
// it did before the extraction.

export const escapeText = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

export const escapeAttr = (s) => escapeText(s).replace(/"/g, "&quot;");

// Turn a markup string into the element it describes.
export function element(markup) {
  const template = document.createElement("template");
  template.innerHTML = markup.trim();
  return template.content.firstElementChild;
}
