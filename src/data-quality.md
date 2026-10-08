---
title: NYC Rideshare Data Quality
---

```js
// The chrome and palette come from the kit (src/kit/); the tabs and the rule
// cards are this dashboard's own.
import {fmt, kpi, masthead, monthLabel, observeTheme, palette, rows, seriesScale, sourceLine} from "./kit/index.js";
import {tabs} from "./components/tabs.js";
import {collapseButton, dimensionCard, indexResults, jumpLink, revealFromHash, ruleCard, ruleStatus, share, verdictChip} from "./components/quality.js";
```

```js
const meta = FileAttachment("data/quality/meta.json").json();
const registry = FileAttachment("data/quality/rules.json").json();
const monthly = FileAttachment("data/quality/months.json").json();
const volume = FileAttachment("data/quality/volume.json").json();
const examples = FileAttachment("data/quality/examples.json").json();
const quality = FileAttachment("data/quality/quality.parquet").parquet().then(rows);
```

```js
const theme = Generators.observe(observeTheme);
```

```js
const colors = palette(theme);
// The same colours the Operations tab gives the two companies.
const companyColor = seriesScale(theme, ["Uber", "Lyft"]);
```

<div>${masthead("NYC Rideshare Data Quality")}</div>

<div>${tabs("data-quality")}</div>

<div>${sourceLine({html: 'New York City <a href="https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page" target="_blank" rel="noopener noreferrer">Taxi &amp; Limousine Commission</a> trip records, every Uber and Lyft trip in the city. Published monthly, about two months behind. Every rule on this page ran against the full trip files, not a sample.'})}</div>

```js
const stat = indexResults(quality);
const totalTrips = d3.sum(meta.months, (m) => stat("@all/defect", m).checked);
```

<p class="lede">${registry.rules.length} data quality rules in eight dimensions, run against all ${fmt.compact(totalTrips)} trips from ${monthLabel(meta.months[0], "long")} to ${monthLabel(meta.months.at(-1), "long")}. Each finding is sorted into one of three kinds: a defect, a business rule that only looks like one, or a gap in the documentation.</p>

```js
const monthInput = Inputs.select(meta.months.slice().reverse(), {label: "Month", format: (m) => monthLabel(m, "long")});
const companyInput = Inputs.radio(["Both", "Uber", "Lyft"], {label: "Company", value: "Both"});
const month = Generators.input(monthInput);
const company = Generators.input(companyInput);
```

<div class="controls">${monthInput}${companyInput}</div>

```js
// Everything below reads the selected month and company from here.
const ctx = {stat, results: monthly.results, files: monthly.files, volume, examples, month, months: meta.months, company, colors, companyColor, goToRules, goToVerdict};
const prevMonth = meta.months[meta.months.indexOf(month) - 1];
const statuses = (m) => registry.rules.map((r) => ruleStatus(r, {...ctx, month: m}).status);
const found = (m) => statuses(m).filter((s) => s === "warning" || s === "error").length;
const file = (m) => monthly.files.find((f) => f.month === m);
```

```js
function tile(title, value, prior, format, better, kind = "ratio") {
  return kpi({title, value, prior, format, better, kind, vs: prevMonth ? monthLabel(prevMonth) : undefined});
}
```

<div class="grid grid-cols-4 kpis">
  ${tile("Trips checked", stat("@all/defect", month, company).checked, prevMonth && stat("@all/defect", prevMonth, company).checked, fmt.compact, null)}
  ${tile("Trips with at least one defect", stat("@all/defect", month, company).share, prevMonth && stat("@all/defect", prevMonth, company).share, (x) => fmt.pct(x), "down", "points")}
  ${tile("Rules that found something", found(month), prevMonth && found(prevMonth), (x) => `${x} of ${registry.rules.length}`, "down")}
  ${tile("Days from month end to publication", file(month).lag_days, prevMonth && file(prevMonth).lag_days, (x) => `${x} days`, "down")}
</div>

## Scorecard by dimension

<p class="dq-sub">A trip that fails several rules is counted once in each dimension. The line is the share of trips with a defect across the twelve months, and the dot is ${monthLabel(month, "long")}. Each card links down to its rules.</p>

<div class="grid grid-cols-4">
  ${Object.entries(registry.dimensions).map(([name, question]) => dimensionCard(name, question, registry.rules.filter((r) => r.dimension === name), ctx))}
</div>

## Three kinds of findings

```js
function verdictCard(verdict, text) {
  const rules = registry.rules.filter((r) => r.verdict === verdict);
  const hits = rules.filter((r) => ["warning", "error"].includes(ruleStatus(r, ctx).status)).length;
  const trips = stat(`@all/${verdict}`, month, company);
  return html`<div class="card">
    <h2>${verdictChip(verdict)}</h2>
    <p>${text}</p>
    <div class="big">${fmt.compact(trips.failed)} trips</div>
    <div class="dq-sub">${share(trips.share)} of ${monthLabel(month, "long")}, from ${hits} of ${rules.length} rules</div>
    ${jumpLink(`See the ${rules.length} rules below`, "every-rule", () => goToVerdict(verdict))}
  </div>`;
}
```

<div class="grid grid-cols-3">
  ${verdictCard("defect", "The record is wrong, or something that should be there is missing. These are the publisher's to fix, and a consumer's to filter or repair until they are.")}
  ${verdictCard("business rule", "The record is right and the rule was naive. A check written from the data dictionary alone raises a false alarm here, because the business does something the dictionary does not mention.")}
  ${verdictCard("documentation gap", "The record may well be right, but nothing TLC publishes lets a consumer tell. The fix is a sentence in the data dictionary, not a change to the data.")}
</div>

## Every rule

```js
const verdictInput = Inputs.radio(["All", "Defects", "Business rules", "Documentation gaps"], {label: "Show", value: "All"});
const foundInput = Inputs.toggle({label: "Only rules that found something", value: false});
const verdictFilter = Generators.input(verdictInput);
const foundOnly = Generators.input(foundInput);
```

<div class="controls">${verdictInput}${foundInput}${collapseAll}</div>

```js
// The cards above jump into this list. A jump clears whichever filter would hide what it
// is pointing at, then scrolls. Reading the inputs rather than their values keeps the
// cards from being rebuilt every time a filter changes.
const VERDICT_TAB = {"defect": "Defects", "business rule": "Business rules", "documentation gap": "Documentation gaps"};

function setInput(input, value) {
  if (input.value === value) return;
  input.value = value;
  input.dispatchEvent(new Event("input", {bubbles: true}));
}

function scrollTo(id) {
  requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView({behavior: "smooth", block: "start"}));
}

function goToRules(dimension) {
  setInput(verdictInput, "All");
  setInput(foundInput, false);
  scrollTo(`rules-${dimension}`);
}

// The same button the sections carry. Outside a section its scope is the whole page.
const collapseAll = collapseButton("Collapse all rules");

function goToVerdict(verdict) {
  setInput(verdictInput, VERDICT_TAB[verdict]);
  setInput(foundInput, false);
  scrollTo("every-rule");
}
```

```js
const wanted = {"All": null, "Defects": "defect", "Business rules": "business rule", "Documentation gaps": "documentation gap"}[verdictFilter];
const shown = registry.rules.filter((r) => (!wanted || r.verdict === wanted) && (!foundOnly || ["warning", "error"].includes(ruleStatus(r, ctx).status)));
```

<p class="dq-sub">${shown.length} of ${registry.rules.length} rules, ${monthLabel(month, "long")}, ${company === "Both" ? "both companies" : company}. Each rule is one line: what it tests, whether it found anything, and how much. Open one for its numbers by company, its trend, why it matters, an example record and the SQL it runs.</p>

<div>
  ${Object.entries(registry.dimensions).filter(([name]) => shown.some((r) => r.dimension === name)).map(([name, question]) => html`<section class="dq-group" id=${`rules-${name}`}>
    <div class="dq-group-head">
      <div>
        <h2 class="dq-group-title">${name[0].toUpperCase() + name.slice(1)}</h2>
        <p class="dq-group-question">${question}</p>
      </div>
      ${collapseButton()}
    </div>
    ${shown.filter((r) => r.dimension === name).map((r) => ruleCard(r, ctx))}
  </section>`)}
</div>

```js
// Runs after the rules above are on the page, so a shared link lands on its rule.
revealFromHash(shown);
```

## Where the documentation and the data part ways

<div class="card dq-docs-card">
  <h2>What TLC's documents say, and what the files do</h2>
  <h3>Documentation is part of the data. Each row is a place where a consumer who trusted the document would be misled.</h3>
  <div class="dq-scroll">
  <table class="dq-table dq-docs">
    <thead><tr><th>Document</th><th>It says</th><th>The data</th><th>Rule</th></tr></thead>
    <tbody>${registry.documentation.map((d) => html`<tr><td>${d.where}</td><td>${d.says}</td><td>${d.data}</td><td>${d.rule ?? ""}</td></tr>`)}</tbody>
  </table>
  </div>
</div>

<div class="notes">

**About the numbers**

- Source: [NYC Taxi & Limousine Commission trip record data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page), High Volume For-Hire Vehicle trips for Uber (HV0003) and Lyft (HV0005). Real public data, published monthly about two months behind. TLC says of these records that it cannot guarantee their accuracy or completeness; this page measures how far that caveat reaches.
- Each month's trip file (about 20 million trips) is downloaded once, checked in full with DuckDB, and deleted. Only counts, rates and up to three example records per rule are kept. The records carry no rider or driver identifiers.
- A share is failed trips over checked trips. Most rules check every trip; a few check only the trips they apply to (the airport fee rules check airport trips), and their cards say so.
- Severity says how hard a finding bites a consumer of the data. The verdict says whose move it is. Both are our reading, and the rule's SQL is on its card so the reading can be checked.
- Publication dates are the files' last-modified dates. A file that TLC re-uploads looks later than it first was, so the lag is an upper bound.
- Trip counts are reconciled against two of TLC's own aggregates: the [FHV Base Aggregate Report](https://data.cityofnewyork.us/Transportation/FHV-Base-Aggregate-Report/2v9c-2k7f) on NYC Open Data and the monthly indicators behind TLC's [aggregated reports](https://www.nyc.gov/site/tlc/about/aggregated-reports.page). The two storms behind the largest one-day drops are documented by the [National Weather Service](https://www.weather.gov/okx/20260125_26) (25 January 2026) and the city's [Emergency Executive Order No. 3](https://www.nyc.gov/mayors-office/news/2026/02/emergency-executive-order-no--3) (the 23 February 2026 travel ban).
- Months shown: ${monthLabel(meta.months[0], "long")} to ${monthLabel(meta.months.at(-1), "long")}. Built ${new Date(meta.built_at).toLocaleDateString("en-US", {dateStyle: "medium"})}.

**The dimensions**

Eight of the nine DAMA International names in [DMBOK2](https://www.damadmbok.org/dmbok2-revisions), chapter 13: accuracy, completeness, consistency, integrity, reasonability, timeliness, uniqueness and validity. The ninth is currency.

</div>
