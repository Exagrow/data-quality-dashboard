---
title: NYC Rideshare Operations
---

```js
// The chrome, tiles, palette, formatting and Plot conventions come from the kit
// (src/kit/); the colours, typefaces and logo from the theme (src/theme/).
import {fmt, kpi, masthead, monthAxis, monthLabel, monthTick, observeTheme, palette, rows, selectedBand, seriesScale, sourceLine, windowedLine} from "./kit/index.js";
// The arithmetic that knows what a trip record is stays here.
import {metrics, totals} from "./components/format.js";
import {tabs} from "./components/tabs.js";
```

```js
const meta = FileAttachment("data/trips/meta.json").json();
const daily = FileAttachment("data/trips/daily.parquet").parquet().then(rows);
const hourly = FileAttachment("data/trips/hourly.parquet").parquet().then(rows);
const zones = FileAttachment("data/trips/zones.parquet").parquet().then(rows);
```

```js
// The page theme ("dark" or "light"), updated when the toggle or the OS flips it.
const theme = Generators.observe(observeTheme);
```

```js
// Chart colours follow the theme; every chart that reads `colors` redraws on a toggle.
// (A separate cell, so `theme` arrives here as a value rather than a generator.)
const colors = palette(theme);
// Uber takes the lead colour and Lyft the second. Which company gets which is
// this page's decision; what the lead and second colours are is the kit's.
const companyColor = seriesScale(theme, ["Uber", "Lyft"]);
```

<div>${masthead("NYC Rideshare Operations")}</div>

<div>${tabs("operations")}</div>

<div>${sourceLine({html: 'New York City <a href="https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page" target="_blank" rel="noopener noreferrer">Taxi &amp; Limousine Commission</a> trip records, every Uber and Lyft trip in the city. Published monthly, about two months behind.'})}</div>

<p class="lede">${fmt.compact(d3.sum(daily, (d) => d.trips))} trips across ${meta.months.length} months, ${monthLabel(meta.months[0], "long")} to ${monthLabel(meta.months.at(-1), "long")}: volume, revenue, driver pay and service levels for the two companies that move most of New York.</p>

```js
const boroughs = ["All boroughs", ...d3.sort(new Set(daily.map((d) => d.borough)), (b) => (b === "Unknown" || b === "N/A" ? "~" : b))];
const monthInput = Inputs.select(meta.months.slice().reverse(), {label: "Month", format: (m) => monthLabel(m, "long")});
const companyInput = Inputs.radio(["Both", "Uber", "Lyft"], {label: "Company", value: "Both"});
const boroughInput = Inputs.select(boroughs, {label: "Pickup borough"});
const month = Generators.input(monthInput);
const company = Generators.input(companyInput);
const borough = Generators.input(boroughInput);
```

<div class="controls">${monthInput}${companyInput}${boroughInput}</div>

```js
// Everything below reads from these filtered sets.
const inBorough = (d) => borough === "All boroughs" || d.borough === borough;
const inCompany = (d) => company === "Both" || d.company === company;
const prevMonth = meta.months[meta.months.indexOf(month) - 1];
const monthRows = (data, m) => data.filter((d) => d.month === m && inBorough(d) && inCompany(d));
const current = metrics(totals(monthRows(daily, month)));
const prior = prevMonth ? metrics(totals(monthRows(daily, prevMonth))) : null;
```

```js
// The kit's KPI tile, fed from this month's measures and last month's. A share
// moves in percentage points; everything else moves by a percentage.
function tile(title, key, format, better, kind = "ratio") {
  return kpi({title, value: current[key], prior: prior?.[key], format, better, kind, vs: prevMonth ? monthLabel(prevMonth) : undefined});
}
```

<div class="grid grid-cols-3 kpis">
  ${tile("Trips", "trips", fmt.compact, "up")}
  ${tile("Gross fares", "fares", fmt.moneyCompact, "up")}
  ${tile("Driver pay", "driverPay", fmt.moneyCompact, "up")}
  ${tile("Fare kept by platform", "platformShare", (x) => fmt.pct(x), null, "points")}
  ${tile("Average wait for pickup", "avgWait", fmt.minutes, "down")}
  ${tile("Average trip", "avgMiles", (x) => `${x.toFixed(1)} mi`, null)}
</div>

```js
function dailyTrips(width) {
  const data = d3.rollups(
    daily.filter((d) => inBorough(d) && inCompany(d)),
    (v) => d3.sum(v, (d) => d.trips),
    (d) => d.day,
    (d) => d.company
  ).flatMap(([day, byCompany]) => byCompany.map(([company, trips]) => ({date: new Date(day), company, trips})));
  return Plot.plot({
    width,
    height: 280,
    marginLeft: 50,
    x: {type: "utc", label: null},
    y: {grid: true, label: "Trips per day (7-day average)", tickFormat: "s", zero: true},
    color: {...companyColor, legend: true},
    marks: [
      selectedBand(Plot, month, colors),
      windowedLine(Plot, data, {x: "date", y: "trips", stroke: "company", tip: {format: {y: (v) => fmt.whole(v)}}}),
      Plot.ruleY([0])
    ]
  });
}
```

<div class="grid grid-cols-1">
  <div class="card">
    <h2>Trips per day</h2>
    <h3>7-day average of daily trips. The shaded band is the selected month.</h3>
    ${resize((width) => dailyTrips(width))}
  </div>
</div>

```js
const byMonth = d3.rollups(
  daily.filter(inBorough),
  (v) => totals(v),
  (d) => d.month,
  (d) => d.company
).flatMap(([m, byCompany]) => byCompany.map(([company, t]) => ({month: m, company, ...t})));

function faresAndPay(width) {
  const data = byMonth.filter(inCompany).flatMap((d) => [
    {month: d.month, company: d.company, measure: "Gross fares", value: d.fares},
    {month: d.month, company: d.company, measure: "Driver pay", value: d.driver_pay}
  ]);
  const summed = d3.rollups(data, (v) => d3.sum(v, (d) => d.value), (d) => d.month, (d) => d.measure)
    .flatMap(([m, byMeasure]) => byMeasure.map(([measure, value]) => ({month: m, measure, value})));
  return Plot.plot({
    width,
    height: 260,
    marginLeft: 55,
    fx: monthAxis(),
    x: {axis: null, domain: ["Gross fares", "Driver pay"]},
    y: {grid: true, label: "US dollars", tickFormat: (v) => fmt.moneyCompact(v)},
    color: {...seriesScale(theme, ["Gross fares", "Driver pay"]), legend: true},
    marks: [
      Plot.barY(summed, {fx: "month", x: "measure", y: "value", fill: "measure", tip: {format: {y: (v) => fmt.moneyCompact(v), fx: (m) => monthLabel(m)}}}),
      Plot.ruleY([0])
    ]
  });
}

function marketShare(width) {
  return Plot.plot({
    width,
    height: 260,
    marginLeft: 45,
    x: monthAxis(),
    y: {label: "Share of trips", percent: true, grid: true},
    color: {...companyColor, legend: true},
    marks: [
      Plot.barY(byMonth, Plot.stackY({offset: "normalize", order: ["Uber", "Lyft"], x: "month", y: "trips", fill: "company", tip: {format: {y: false}, channels: {Trips: (d) => fmt.whole(d.trips)}}}))
    ]
  });
}
```

<div class="grid grid-cols-2">
  <div class="card">
    <h2>Gross fares and driver pay by month</h2>
    <h3>Base passenger fare, before tolls, taxes, surcharges and tips</h3>
    ${resize((width) => faresAndPay(width))}
  </div>
  <div class="card">
    <h2>Market share by month</h2>
    <h3>Share of trips, Uber against Lyft (ignores the company filter)</h3>
    ${resize((width) => marketShare(width))}
  </div>
</div>

```js
const dayNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const hourRows = monthRows(hourly, month);

function demandHeatmap(width) {
  const data = d3.rollups(hourRows, (v) => d3.sum(v, (d) => d.trips), (d) => d.dow, (d) => d.hour)
    .flatMap(([dow, byHour]) => byHour.map(([hour, trips]) => ({day: dayNames[dow - 1], hour, trips})));
  return Plot.plot({
    width,
    height: 250,
    marginLeft: 40,
    padding: 0.05,
    x: {label: "Hour of pickup", tickFormat: (h) => (h % 3 === 0 ? `${h}` : "")},
    y: {label: null, domain: dayNames},
    color: {type: "linear", range: [colors.heatLow, colors.heatHigh], label: "Trips", legend: true, tickFormat: "s"},
    marks: [Plot.cell(data, {x: "hour", y: "day", fill: "trips", inset: 0.5, tip: {format: {fill: (v) => fmt.whole(v)}}})]
  });
}

function waitByHour(width) {
  const data = d3.rollups(hourRows, (v) => d3.sum(v, (d) => d.wait_seconds) / d3.sum(v, (d) => d.wait_trips) / 60, (d) => d.company, (d) => d.hour)
    .flatMap(([company, byHour]) => byHour.map(([hour, minutes]) => ({company, hour, minutes})));
  return Plot.plot({
    width,
    height: 250,
    marginLeft: 40,
    x: {label: "Hour of pickup", domain: [0, 23]},
    y: {label: "Average wait (minutes)", grid: true, zero: true},
    color: {...companyColor, legend: true},
    marks: [
      Plot.lineY(d3.sort(data, (d) => d.hour), {x: "hour", y: "minutes", stroke: "company", strokeWidth: 2.25, curve: "monotone-x", tip: {format: {y: (v) => `${v.toFixed(1)} min`}}}),
      Plot.ruleY([0])
    ]
  });
}
```

<div class="grid grid-cols-2">
  <div class="card">
    <h2>When New Yorkers ride</h2>
    <h3>Trips by weekday and hour, ${monthLabel(month, "long")}</h3>
    ${resize((width) => demandHeatmap(width))}
  </div>
  <div class="card">
    <h2>Wait for pickup through the day</h2>
    <h3>Request to pickup, ${monthLabel(month, "long")}</h3>
    ${resize((width) => waitByHour(width))}
  </div>
</div>

```js
const zoneTable = d3.rollups(monthRows(zones, month), (v) => totals(v), (d) => d.zone_id)
  .map(([zone_id, t]) => {
    const first = zones.find((z) => z.zone_id === zone_id);
    const m = metrics(t);
    return {
      Zone: first.zone ?? `Zone ${zone_id}`,
      Borough: first.borough,
      Trips: t.trips,
      "Gross fares": t.fares,
      "Avg fare": m.avgFare,
      "Pay per trip": t.trips ? t.driver_pay / t.trips : NaN,
      "Wait (min)": m.avgWait / 60,
      "Miles": m.avgMiles,
      "Airport trips": t.airport_trips
    };
  });
const zoneTotal = d3.sum(zoneTable, (d) => d.Trips);

function topZones(width) {
  const top = d3.sort(zoneTable, (d) => -d.Trips).slice(0, 12);
  return Plot.plot({
    width,
    height: 330,
    marginLeft: 190,
    x: {label: "Trips", grid: true, tickFormat: "s"},
    y: {label: null, domain: top.map((d) => d.Zone)},
    marks: [
      Plot.barX(top, {x: "Trips", y: "Zone", fill: colors.lead, tip: {channels: {Borough: "Borough", Share: (d) => fmt.pct(d.Trips / zoneTotal)}, format: {x: (v) => fmt.whole(v)}}}),
      Plot.ruleX([0])
    ]
  });
}
```

```js
const zoneSearch = Inputs.search(zoneTable, {placeholder: "Search zones or boroughs"});
const zoneMatches = Generators.input(zoneSearch);
```

```js
function airportShare(width) {
  const data = byMonth.filter(inCompany).map((d) => ({month: d.month, company: d.company, share: d.airport_trips / d.trips, trips: d.airport_trips}));
  return Plot.plot({
    width,
    height: 330,
    marginLeft: 45,
    fx: monthAxis(),
    x: {axis: null, domain: ["Uber", "Lyft"]},
    y: {label: "Share of trips", percent: true, grid: true},
    color: {...companyColor, legend: true},
    marks: [
      Plot.barY(data, {fx: "month", x: "company", y: "share", fill: "company", tip: {format: {y: (v) => `${v.toFixed(1)}%`, fx: (m) => monthLabel(m)}, channels: {"Airport trips": (d) => fmt.whole(d.trips)}}}),
      Plot.ruleY([0])
    ]
  });
}
```

<div class="grid grid-cols-2">
  <div class="card">
    <h2>Busiest pickup zones</h2>
    <h3>Top 12 of ${zoneTable.length} zones, ${monthLabel(month, "long")}</h3>
    ${resize((width) => topZones(width))}
  </div>
  <div class="card">
    <h2>Airport pickups</h2>
    <h3>Share of trips starting or ending at LaGuardia, JFK or Newark (trips charged the airport fee)</h3>
    ${resize((width) => airportShare(width))}
  </div>
</div>

<div class="grid grid-cols-1">
  <div class="card">
    <h2>Every pickup zone</h2>
    <h3>${monthLabel(month, "long")}, by pickup zone. Averages are per trip; pay is driver pay. Search, or click a column to sort.</h3>
    ${zoneSearch}
    ${Inputs.table(zoneMatches, {
      // Nothing on this page reads a selection, so the checkbox column would do nothing.
      select: false,
      rows: 15,
      sort: "Trips",
      reverse: true,
      width: {Zone: 230, Borough: 110},
      format: {
        Trips: fmt.whole,
        "Gross fares": fmt.moneyCompact,
        "Avg fare": fmt.money,
        "Pay per trip": fmt.money,
        "Wait (min)": (x) => x.toFixed(1),
        "Miles": (x) => x.toFixed(1),
        "Airport trips": fmt.whole
      }
    })}
  </div>
</div>

<div class="notes">

**About the numbers**

- Source: [NYC Taxi & Limousine Commission trip record data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page), High Volume For-Hire Vehicle trips for Uber (HV0003) and Lyft (HV0005). Every trip is reported by the company to the city; this page summarises them by day, hour and pickup zone.
- Gross fares are the base passenger fare, before tolls, taxes, surcharges and tips. "Fare kept by platform" is gross fares minus driver pay, as a share of gross fares; driver pay can include incentives, so read it as an approximation.
- Wait is the time from the ride request to pickup. Records with a request after the pickup, or a wait over two hours, are left out of the average.
- Months shown: ${monthLabel(meta.months[0], "long")} to ${monthLabel(meta.months.at(-1), "long")}. Built ${new Date(meta.built_at).toLocaleDateString("en-US", {dateStyle: "medium"})}.

</div>
