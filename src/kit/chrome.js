// The page chrome: the masthead and the data source line.
//
// The *HTML functions are the markup; the element functions are what a page
// drops into a `${...}` expression.

import {FileAttachment} from "observablehq:stdlib";
import {brand} from "../theme/brand.js";
import {element, escapeAttr, escapeText} from "./html.js";

// The logo is the brand's, so the files live in src/theme/. FileAttachment makes
// Framework copy them into the build and hands back the URL they end up at.
const logoUrl = FileAttachment("../theme/logo.svg").href;
const logoReversedUrl = FileAttachment("../theme/logo-reversed.svg").href;

// Title on the left; logo and theme toggle on the right, on one line. Both
// logos ship and the stylesheet shows the one that suits the theme, so the
// switch costs no request. The toggle carries no state of its own: the script
// in dashboardConfig() listens for a click on [data-theme-toggle] and flips
// the attribute on <html>.
//
// The logo link opens in a new tab, because Framework rewrites an external link
// in a page's own markdown that way and chrome built at runtime never passes
// through that rewrite. A link inside sourceLine() wants the same two
// attributes written out, for the same reason.
export function mastheadHTML(title, {logoHref = brand.url} = {}) {
  return `<header class="masthead">
  <h1>${escapeText(title)}</h1>
  <div class="masthead-end">
    <a class="logo-link" href="${escapeAttr(logoHref)}" title="${escapeAttr(brand.name)}" target="_blank" rel="noopener noreferrer">
      <img class="logo logo-on-light" src="${escapeAttr(logoUrl)}" alt="${escapeAttr(brand.name)}">
      <img class="logo logo-on-dark" src="${escapeAttr(logoReversedUrl)}" alt="${escapeAttr(brand.name)}">
    </a>
    <button type="button" class="theme-toggle" data-theme-toggle aria-label="Switch between dark and light theme">
      <svg class="icon-sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4.5"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8"/></svg>
      <svg class="icon-moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/></svg>
    </button>
  </div>
</header>`;
}

export function masthead(title, options) {
  return element(mastheadHTML(title, options));
}

// The data source is a plain line under the header, not a card. `html` is
// markup, not text: this line usually carries a link to the publisher.
export function sourceLineHTML({label = "Data Source", html = ""} = {}) {
  return `<p class="source"><strong>${escapeText(label)}:</strong> ${html}</p>`;
}

export function sourceLine(options) {
  return element(sourceLineHTML(options));
}
