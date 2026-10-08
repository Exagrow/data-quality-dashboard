// The Observable Framework config for the dashboard.
//
// This is the build time half of the kit: Node loads it from
// observablehq.config.js, so it must not import anything from index.js, which
// is browser code.
//
//   import {dashboardConfig} from "./src/kit/config.js";
//   export default dashboardConfig({title: "...", dataCredit: "..."});

import {readFileSync} from "node:fs";
import {brand} from "../theme/brand.js";

// The icon is the brand's, so the file lives in src/theme/. It is inlined at
// import time, so it needs no request and cannot 404 under a path prefix.
//
// Base64, not percent-encoding: Framework parses the href of a <link> in `head`
// and writes it back out, and that pass escapes the % of a percent-escape a
// second time, which leaves the browser decoding "<%3Fxml" and refusing the
// icon. Base64 has no character for it to escape.
const defaultFaviconSvg = readFileSync(new URL("../theme/favicon.svg", import.meta.url), "utf8");

// A favicon as a data URL, from an SVG string (or an existing data: URL, passed
// through). Base64 rather than percent-encoding: see the note above.
export function faviconDataUrl(svg) {
  if (typeof svg === "string" && svg.startsWith("data:")) return svg;
  return `data:image/svg+xml;base64,${Buffer.from(svg).toString("base64")}`;
}

// Runs in <head> before the page paints. The stylesheet is dark unless <html>
// says data-theme="light", so a visitor never sees a light flash: the page stays
// dark until this script has read a saved choice or the OS setting, and stays
// dark if neither can be read. The toggle button saves an explicit choice; with
// none saved, the page follows the OS as it changes.
const themeScript = `<script>
(function () {
  var root = document.documentElement;
  var query = window.matchMedia ? window.matchMedia("(prefers-color-scheme: light)") : null;
  function saved() {
    try { var t = localStorage.getItem("theme"); return t === "light" || t === "dark" ? t : null; } catch (e) { return null; }
  }
  function apply(theme) { root.dataset.theme = theme; }
  apply(saved() || (query && query.matches ? "light" : "dark"));
  if (query && query.addEventListener) {
    query.addEventListener("change", function (e) { if (!saved()) apply(e.matches ? "light" : "dark"); });
  }
  document.addEventListener("click", function (e) {
    if (!e.target.closest || !e.target.closest("[data-theme-toggle]")) return;
    var next = root.dataset.theme === "light" ? "dark" : "light";
    apply(next);
    try { localStorage.setItem("theme", next); } catch (err) {}
  });
})();
</script>`;

// The typefaces are loaded by src/theme/typography.css, not from here.
const headFor = (favicon) => `${themeScript}
<link rel="icon" href="${faviconDataUrl(favicon)}" type="image/svg+xml">`;

// `title` is the page title. `dataCredit` is the credit that closes the footer,
// and it is markup, not text, so an ampersand in a publisher's name is written
// as &amp;. Anything else in the config object can be overridden: later keys
// win, so a dashboard that needs a sidebar or a different root can say so.
export function dashboardConfig({title, dataCredit, favicon = defaultFaviconSvg, ...overrides} = {}) {
  return {
    title,
    root: "src",
    style: "style.css",
    head: headFor(favicon),
    sidebar: false,
    pager: false,
    toc: false,
    search: false,
    footer: dataCredit
      ? `Copyright ${new Date().getFullYear()} ${brand.name}. Data: ${dataCredit}.`
      : `Copyright ${new Date().getFullYear()} ${brand.name}.`,
    preserveExtension: false,
    preserveIndex: false,
    ...overrides
  };
}
