// A KPI tile: a headline number, and how it moved against the period before.
//
// The comparison is either a ratio (kind "ratio", the default: "+4.2%") or a
// difference in percentage points (kind "points": "+1.3 pts"), which is what a
// measure that is already a percentage needs. `better` says which direction is
// good, so the delta can be toned; pass null for a measure that is neither.

import {element, escapeText} from "./html.js";

export function kpiHTML({title, value, prior, format = String, better = null, kind = "ratio", vs} = {}) {
  let delta = "<span>No earlier period to compare</span>";
  if (prior != null && Number.isFinite(prior) && prior !== 0) {
    const change = kind === "points" ? value - prior : value / prior - 1;
    const text = `${change >= 0 ? "+" : ""}${(100 * change).toFixed(1)}${kind === "points" ? " pts" : "%"}`;
    // A change too small to show as a tenth of a point is not worth colouring.
    const tone = better === null || Math.abs(change) < 0.0005 ? "" : (change > 0) === (better === "up") ? "good" : "bad";
    const against = vs == null || vs === "" ? "" : ` vs ${escapeText(vs)}`;
    delta = `<span class="${tone}">${escapeText(text)}</span>${against}`;
  }
  return `<div class="card kpi"><h2>${escapeText(title)}</h2><div class="big">${escapeText(format(value))}</div><div class="delta">${delta}</div></div>`;
}

export function kpi(options) {
  return element(kpiHTML(options));
}
