// What the Data Quality tab does with the rule results: look a rule's numbers up for a
// month and a company, decide its status, and draw its card. Formatting, palette and
// chrome come from the kit (src/kit/); the part that knows what a rule is stays here.

import {html} from "npm:htl";
import * as d3 from "npm:d3";
import * as Plot from "npm:@observablehq/plot";
import {fmt, monthAxis, monthLabel, selectedBand, token} from "../kit/index.js";

// The semantic trio, read from the theme's tokens (src/theme/colors.css) when a chart
// asks, so the charts and the pills in quality.css share one definition.
export const semantic = {
  get success() { return token("--dq-success"); },
  get warning() { return token("--dq-warning"); },
  get error() { return token("--dq-error"); }
};

const STATUS_LABEL = {clean: "Clean", warning: "Warning", error: "Error", pending: "Pending"};
// Not the bare words: Framework styles .warning (and .note, .tip, .caution) as callouts.
const STATUS_CLASS = {clean: "is-success", warning: "is-warning", error: "is-error", pending: "is-pending"};
const VERDICT_CLASS = {"defect": "defect", "business rule": "business", "documentation gap": "documentation"};
const VERDICT_LABEL = {"defect": "Defect", "business rule": "Business rule", "documentation gap": "Documentation gap"};
const COMPANIES = ["Uber", "Lyft"];

export function pill(status) {
  return html`<span class=${`pill ${STATUS_CLASS[status]}`}>${STATUS_LABEL[status]}</span>`;
}

export function verdictChip(verdict) {
  return html`<span class=${`chip ${VERDICT_CLASS[verdict]}`}>${VERDICT_LABEL[verdict]}</span>`;
}

// A share small enough to round to 0.0% still happened; say so rather than print zero.
export function share(x) {
  if (!Number.isFinite(x)) return "";
  if (x === 0) return "0%";
  if (x < 0.00005) return "under 0.01%";
  return x < 0.01 ? `${(100 * x).toFixed(2)}%` : fmt.pct(x);
}

// Rule results by rule, month and company, summed over days.
export function indexResults(quality) {
  const byMonth = d3.rollup(
    quality,
    (v) => ({failed: d3.sum(v, (d) => d.failed), checked: d3.sum(v, (d) => d.checked)}),
    (d) => d.rule,
    (d) => d.month,
    (d) => d.company
  );
  return function stat(rule, month, company = "Both") {
    const m = byMonth.get(rule)?.get(month);
    const parts = !m ? [] : company === "Both" ? [...m.values()] : [m.get(company)].filter(Boolean);
    const failed = d3.sum(parts, (d) => d.failed);
    const checked = d3.sum(parts, (d) => d.checked);
    return {failed, checked, share: checked ? failed / checked : NaN};
  };
}

// The month rules' results for one rule and month, under the company filter. Results
// for both companies together always show.
export function monthResults(results, rule, month, company) {
  return results.filter((r) => r.rule === rule && r.month === month && (company === "Both" || r.company === "Both" || r.company === company));
}

// clean, warning, error or pending, for a rule in a month.
export function ruleStatus(rule, {stat, results, month, company}) {
  if (rule.grain === "trip") {
    const s = stat(rule.id, month, company);
    return {status: s.failed > 0 ? rule.severity : "clean", ...s};
  }
  const rs = monthResults(results, rule.id, month, company);
  const failed = rs.filter((r) => r.status === "fail").length;
  const status = failed ? rule.severity : rs.length && rs.every((r) => r.status === "pending") ? "pending" : "clean";
  return {status, failed, checked: rs.length, share: NaN, results: rs};
}

// Trips with at least one defect in a dimension. The pipeline counts them distinctly for
// rules that test one trip at a time. The uniqueness rules test groups of rows instead, and
// an exact duplicate is also a duplicate on the key, so there the largest rule is the count.
function dimensionDefects(name, rules, month, {stat, company}) {
  const distinct = stat(`@${name}/defect`, month, company);
  if (distinct.checked) return distinct;
  const each = rules.filter((r) => r.grain === "trip" && r.verdict === "defect").map((r) => stat(r.id, month, company));
  return each.length ? each.reduce((a, b) => (b.failed > a.failed ? b : a)) : distinct;
}

const worst = (statuses) => (statuses.includes("error") ? "error" : statuses.includes("warning") ? "warning" : statuses.includes("clean") ? "clean" : "pending");

// One card of the scorecard: a dimension, its rules, the trips its defects touch, and
// how that share has moved across the months.
export function dimensionCard(name, question, rules, ctx) {
  const {stat, month, months, company, colors} = ctx;
  const statuses = rules.map((r) => ruleStatus(r, ctx).status);
  const found = statuses.filter((s) => s === "warning" || s === "error").length;
  const defect = dimensionDefects(name, rules, month, ctx);
  const other = d3.sum(["business rule", "documentation gap"], (v) => stat(`@${name}/${v}`, month, company).failed);
  // The headline counts trips only where the dimension has a trip-level defect rule to count
  // them with. Accuracy, whose rules are a business rule and two checks on the whole file,
  // would otherwise print a zero and a share that is not a number.
  const defectRules = rules.filter((r) => r.grain === "trip" && r.verdict === "defect").length;
  const series = months.map((m) => ({month: m, share: dimensionDefects(name, rules, m, ctx).share || 0}));
  const headline = defectRules
    ? html`<div class="big">${fmt.compact(defect.failed)}</div><div class="dq-sub">trips with a defect, ${share(defect.share)} of the month</div>`
    : html`<div class="big">${found} of ${rules.length}</div><div class="dq-sub">${rules.length === 1 ? "check" : "checks"} found something this month</div>`;
  return html`<div class="card dq-dimension">
    <div class="dq-dimension-head"><h2>${name[0].toUpperCase() + name.slice(1)}</h2>${pill(worst(statuses))}</div>
    <h3>${question}</h3>
    ${headline}
    ${defectRules ? sparkline(series, month, colors) : ""}
    <div class="dq-sub">${rules.length} ${rules.length === 1 ? "rule" : "rules"}: ${rules.length - found} clean, ${found} with findings${other ? html`. ${fmt.compact(other)} more trips are explained by a business rule or wait on documentation` : ""}.</div>
    ${rules.length ? jumpLink(`See the ${rules.length} ${rules.length === 1 ? "rule" : "rules"} below`, `rules-${name}`, ctx.goToRules && (() => ctx.goToRules(name))) : ""}
  </div>`;
}

function sparkline(series, month, colors) {
  const top = d3.max(series, (d) => d.share) || 1;
  return Plot.plot({
    width: 260,
    height: 46,
    margin: 4,
    marginTop: 8,
    x: {type: "point", axis: null, domain: series.map((d) => d.month)},
    y: {axis: null, domain: [0, top * 1.1]},
    marks: [
      Plot.areaY(series, {x: "month", y: "share", fill: colors.second, fillOpacity: 0.25}),
      Plot.lineY(series, {x: "month", y: "share", stroke: colors.second, strokeWidth: 2.25}),
      Plot.dot(series.filter((d) => d.month === month), {x: "month", y: "share", r: 4, fill: colors.lead, stroke: colors.lead})
    ]
  });
}

// The rule list below is where the detail lives, so a summary card links down to it
// rather than repeating it. The link falls back to a plain anchor when the page has not
// given the card a way to clear the filters first.
export function jumpLink(text, id, go) {
  return html`<a class="dq-jump" href=${`#${id}`} onclick=${(event) => {
    if (!go) return;
    event.preventDefault();
    history.replaceState(null, "", `#${id}`);
    go();
  }}>${text}</a>`;
}

// Each section can fold its own rules back up, and the filter row carries one that folds
// them all. The button finds its own scope when it is clicked, so the same helper serves
// both: inside a section it closes that section, outside it closes the page.
export function collapseButton(label = "Collapse all") {
  const button = html`<button class="button dq-collapse" type="button" disabled>${label}</button>`;
  const scope = () => button.closest(".dq-group") ?? document;
  const open = () => scope().querySelectorAll("details.dq-rule[open]");
  const sync = () => (button.disabled = !open().length);
  button.addEventListener("click", () => {
    open().forEach((card) => (card.open = false));
    sync();
  });
  // Any card opening or closing anywhere can change whether this button has work to do.
  document.addEventListener("toggle", sync, true);
  requestAnimationFrame(sync);
  return button;
}

// A card opened by hand should be linkable, so the address bar follows the last one opened
// and lets go when it closes.
function trackHash(card, id) {
  const hash = `#rule-${id}`;
  if (card.open) {
    if (location.hash !== hash) history.replaceState(null, "", hash);
  } else if (location.hash === hash) {
    history.replaceState(null, "", location.pathname);
  }
}

// A link shared into this page arrives as a hash. Once the rules are on the page, open what
// it names and scroll to it, and keep doing that when the hash changes later. The first
// render is the only one that acts on its own, so changing a filter does not yank the page.
let revealed = false;

function reveal() {
  const id = location.hash.slice(1);
  if (!id) return false;
  const target = document.getElementById(id);
  if (!target) return false;
  if (target.matches("details.dq-rule")) target.open = true;
  requestAnimationFrame(() => target.scrollIntoView({block: "start"}));
  return true;
}

export function revealFromHash() {
  if (revealed) return;
  revealed = true;
  window.addEventListener("hashchange", reveal);
  // The section renders in the same pass, so give the cards a frame to land.
  if (!reveal()) requestAnimationFrame(reveal);
}

// The rule itself, in SQL, under the sentence that describes it. The box shows the first
// couple of lines; when there is more, it says so and fades the cut edge, and a click
// anywhere in it opens the whole thing.
function formulaBox(rule) {
  if (!rule.sql) return "";
  const tidy = (q) => q.replace(/\s+/g, " ").trim();
  const peek = html`<code class="dq-formula-peek">${tidy(rule.sql)}</code>`;
  const box = html`<details class="dq-formula">
    <summary>
      <span class="dq-formula-head">
        <span class="dq-formula-label">Data Quality Rule</span>
        <span class="dq-formula-more">Show the whole rule<span class="dq-chevron"></span></span>
      </span>
      <span class="dq-formula-peek-wrap">${peek}</span>
    </summary>
    <pre>${tidy(rule.sql)}</pre>
    ${rule.applies_sql ? html`<p class="dq-sub">Checked against the trips where <code>${tidy(rule.applies_sql)}</code>, which is the denominator of the share.</p>` : ""}
  </details>`;
  // Whether the SQL is actually cut off depends on how wide the card ends up, so the class
  // that draws the fade and the hint is set after the box is on the page.
  requestAnimationFrame(() => box.classList.toggle("is-clipped", peek.scrollHeight > peek.clientHeight + 1));
  return box;
}

// A rule, folded. The summary line carries the verdict and the month's number; the body
// (numbers by company, the trend, why it matters, an example, the SQL) is built when it
// is first opened, so a page of forty rules draws forty charts only if asked to.
export function ruleCard(rule, ctx) {
  const s = ruleStatus(rule, ctx);
  const count = rule.grain === "trip"
    ? html`<span class="dq-count">${fmt.whole(s.failed)}</span><span class="dq-share">${share(s.share)}</span>`
    : html`<span class="dq-count">${s.status === "pending" ? "" : `${s.failed} of ${s.checked}`}</span><span class="dq-share">${s.status === "pending" ? "" : "checks failed"}</span>`;
  const body = html`<div class="dq-rule-body"></div>`;
  const card = html`<details class="card dq-rule" id=${`rule-${rule.id}`}>
    <summary>
      <span class="dq-id">${rule.id}</span>
      <span class="dq-name">${rule.name}</span>
      <span class="dq-test-line">${rule.test}</span>
      <span class="dq-tags">${verdictChip(rule.verdict)}${pill(s.status)}</span>
      <span class="dq-numbers">${count}</span>
      <span class="dq-open">Details<span class="dq-chevron"></span></span>
    </summary>
    ${body}
  </details>`;
  card.addEventListener("toggle", () => {
    if (card.open && !body.childNodes.length) body.append(...ruleBody(rule, s, ctx, Math.max(300, body.clientWidth || card.clientWidth - 32)));
    trackHash(card, rule.id);
  });
  return card;
}

function ruleBody(rule, s, ctx, width) {
  const {stat, month, company, results, examples} = ctx;
  const parts = [formulaBox(rule)];
  if (rule.grain === "trip") {
    const companies = company === "Both" ? COMPANIES : [company];
    parts.push(html`<table class="dq-table">
      <thead><tr><th>${monthLabel(month, "long")}</th><th>Failed</th><th>${rule.applies ? "Checked (the trips the rule applies to)" : "Checked"}</th><th>Share</th></tr></thead>
      <tbody>${companies.map((c) => {
        const x = stat(rule.id, month, c);
        return html`<tr><td>${c}</td><td>${fmt.whole(x.failed)}</td><td>${fmt.whole(x.checked)}</td><td>${share(x.share)}</td></tr>`;
      })}</tbody>
    </table>`);
    parts.push(html`<div class="dq-chart">${trendChart(rule, ctx, width)}</div>`);
  } else {
    parts.push(html`<ul class="dq-results">${s.results.map((r) => html`<li>${pill(r.status === "fail" ? rule.severity : r.status === "pending" ? "pending" : "clean")} <strong>${r.company === "Both" ? "Both companies" : r.company}.</strong> ${r.detail}</li>`)}</ul>`);
    parts.push(html`<div class="dq-chart">${monthChart(rule, ctx, width)}</div>`);
  }
  parts.push(html`<p><strong>Why it matters.</strong> ${rule.why}</p>`);
  parts.push(html`<p><strong>Our reading: ${VERDICT_LABEL[rule.verdict].toLowerCase()}.</strong> ${rule.note}</p>`);
  const rows = examples[month]?.[rule.id] ?? [];
  if (rows.length) {
    const shown = company === "Both" ? rows : rows.filter((r) => r.company === company);
    const list = shown.length ? shown : rows;
    parts.push(html`<p class="dq-example-head"><strong>Example records</strong>, ${monthLabel(month, "long")}, as published. Trip records carry no rider or driver identifiers.</p>
      <div class="dq-scroll"><table class="dq-table dq-example">
        <thead><tr>${rule.columns.map((c) => html`<th>${c}</th>`)}</tr></thead>
        <tbody>${list.map((r) => html`<tr>${rule.columns.map((c) => html`<td>${r[c] ?? "null"}</td>`)}</tr>`)}</tbody>
      </table></div>`);
  }
  return parts;
}

// Share of checked trips failing the rule, by month and company, with the selected
// month shaded the way the Operations page shades it.
function trendChart(rule, ctx, width) {
  const {stat, months, month, company, colors, companyColor} = ctx;
  const companies = company === "Both" ? COMPANIES : [company];
  const data = months.flatMap((m) => companies.map((c) => ({month: m, company: c, ...stat(rule.id, m, c)})));
  const top = d3.max(data, (d) => d.share) || 0;
  return Plot.plot({
    width,
    height: 220,
    marginLeft: 56,
    fx: monthAxis(),
    x: {axis: null, domain: companies},
    // percent: true scales the values, and the domain is given in the scaled units.
    y: {label: "Share of trips checked (%)", percent: true, grid: true, domain: [0, top ? 100 * top * 1.08 : 1]},
    color: {...companyColor, legend: true},
    marks: [
      Plot.barY([{month}], {fx: "month", y1: 0, y2: top ? top * 1.08 : 0.01, fill: colors.band, fillOpacity: colors.bandOpacity}),
      Plot.barY(data, {fx: "month", x: "company", y: "share", fill: "company", tip: {format: {y: (v) => `${v.toFixed(3)}%`, fx: (m) => monthLabel(m), x: false}, channels: {Failed: (d) => fmt.whole(d.failed), Checked: (d) => fmt.whole(d.checked)}}}),
      Plot.ruleY([0])
    ]
  });
}

// The charts for the rules that run over a month rather than a trip.
function monthChart(rule, ctx, width) {
  const {results, files, volume, months, month, company, colors} = ctx;
  if (rule.id === "RSN-01") {
    const companies = company === "Both" ? COMPANIES : [company];
    const label = {explained: "Drop with a known cause", unexplained: "Drop with no known cause"};
    const data = volume.filter((d) => companies.includes(d.company) && d.deviation != null)
      .map((d) => ({...d, date: new Date(d.day), status: label[d.flag] ?? "Within 25 percent"}));
    return Plot.plot({
      width,
      height: companies.length * 150 + 60,
      marginLeft: 56,
      marginRight: 46,
      x: {type: "utc", label: null},
      y: {label: "Trips against the same weekday nearby (%)", percent: true, grid: true},
      fy: {label: null, domain: companies},
      color: {domain: ["Within 25 percent", "Drop with a known cause", "Drop with no known cause"], range: [semantic.success, semantic.warning, semantic.error], legend: true},
      marks: [
        selectedBand(Plot, month, colors),
        Plot.ruleX(data, {fy: "company", x: "date", y1: 0, y2: "deviation", stroke: "status", strokeWidth: 2, tip: {format: {y2: (v) => `${v.toFixed(0)}%`, fy: false, y1: false}, channels: {Trips: (d) => fmt.whole(d.trips), Expected: (d) => fmt.whole(d.expected), Cause: (d) => d.cause ?? ""}}}),
        Plot.ruleY([0])
      ]
    });
  }
  if (rule.id === "TML-01") {
    const data = files.map((f) => ({...f, status: f.lag_days > 62 ? "Later than two months" : "Within two months"}));
    return Plot.plot({
      width,
      height: 230,
      marginLeft: 50,
      x: monthAxis(),
      y: {label: "Days from month end to publication", grid: true, domain: [0, Math.max(70, d3.max(data, (d) => d.lag_days) + 5)]},
      color: {domain: ["Within two months", "Later than two months"], range: [semantic.success, semantic.warning], legend: true},
      marks: [
        Plot.barY([{month}], {x: "month", y1: 0, y2: Math.max(70, d3.max(data, (d) => d.lag_days) + 5), fill: colors.band, fillOpacity: colors.bandOpacity}),
        Plot.barY(data, {x: "month", y: "lag_days", fill: "status", inset: 4, tip: {format: {x: (m) => monthLabel(m)}, channels: {Published: "published"}}}),
        Plot.ruleY([62], {stroke: semantic.warning, strokeWidth: 2}),
        Plot.text([{y: 62}], {y: "y", frameAnchor: "right", dy: -8, text: () => "62 days: the two months TLC's data page gives", fill: "currentColor"}),
        Plot.ruleY([0])
      ]
    });
  }
  if (rule.id === "ACC-02") {
    const cell = (m, c) => {
      const r = results.find((x) => x.rule === "ACC-02" && x.month === m && x.company === c);
      if (!r || r.status === "pending") return html`<td title=${r?.detail ?? ""} class="pending">not published</td>`;
      return html`<td title=${r.detail} class=${r.status === "fail" ? "fail" : "ok"}>${r.value === 0 ? "exact" : `${r.value > 0 ? "+" : ""}${(100 * r.value).toFixed(2)}%`}</td>`;
    };
    return html`<div class="dq-scroll"><table class="dq-table dq-reconcile">
      <thead><tr><th>Month</th><th>Uber against the aggregate report</th><th>Lyft against the aggregate report</th><th>Both against the monthly indicators</th></tr></thead>
      <tbody>${months.map((m) => html`<tr class=${m === month ? "selected" : ""}><td>${monthLabel(m)}</td>${cell(m, "Uber")}${cell(m, "Lyft")}${cell(m, "Both")}</tr>`)}</tbody>
    </table></div>
    <p class="dq-sub">Trips in the file against trips in TLC's own aggregate, as a share of the aggregate. The indicators publish trips per day, so a few dozen trips of rounding is expected. Hover a cell for the counts.</p>`;
  }
  // Everything else: one cell a month, in the rule's colours.
  const mine = results.filter((r) => r.rule === rule.id);
  return html`<div class="dq-strip">${months.map((m) => {
    const rs = mine.filter((r) => r.month === m);
    const status = rs.some((r) => r.status === "fail") ? rule.severity : rs.every((r) => r.status === "pending") ? "pending" : "clean";
    return html`<div class=${`dq-cell ${STATUS_CLASS[status]}${m === month ? " selected" : ""}`} title=${`${monthLabel(m)}: ${rs.map((r) => r.detail).join(" ")}`}>${monthLabel(m).slice(0, 3)}</div>`;
  })}</div>`;
}
