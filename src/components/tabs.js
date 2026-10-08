// The tabs that move between the dashboard's pages. Every page sits at the site root,
// so the same relative links work from each, whether the site is served at the root
// of a host or under a path prefix.
//
// The kit has no tab component. This one uses only the theme's tokens.

import {html} from "npm:htl";

const TABS = [
  {id: "operations", label: "Operations", href: "./"},
  {id: "data-quality", label: "Data Quality", href: "./data-quality"},
  {id: "ui-reference", label: "UI Design Reference", href: "./ui-reference"}
];

export function tabs(active) {
  return html`<nav class="tabs" aria-label="Dashboard pages">${TABS.map(
    (t) => html`<a class=${t.id === active ? "tab active" : "tab"} href=${t.href} aria-current=${t.id === active ? "page" : null}>${t.label}</a>`
  )}</nav>`;
}
