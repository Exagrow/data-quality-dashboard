// The Plot conventions the design rules fix, so two dashboards drawing the same
// idea draw it the same way.
//
// Plot is passed in rather than imported: Framework gives every page Plot as a
// global, and taking it as an argument keeps the kit free of a dependency on a
// copy of its own.

import {monthTick} from "./format.js";

// "2026-04" to the half-open UTC interval it covers.
export function monthRange(month) {
  const [y, m] = month.split("-").map(Number);
  return {start: new Date(Date.UTC(y, m - 1, 1)), end: new Date(Date.UTC(y, m, 1))};
}

// The selected period, shaded behind the marks. This is how a dashboard says
// "you are looking at this slice" on a chart that shows the whole run: a band,
// never a dashed rule.
export function selectedBand(Plot, period, colors, options = {}) {
  const {start, end} = typeof period === "string" ? monthRange(period) : period;
  return Plot.rectX([{start, end}], {
    x1: "start",
    x2: "end",
    fill: colors.band,
    fillOpacity: colors.bandOpacity,
    ...options
  });
}

// A month axis: bands, no axis label, and the year printed under the first tick
// and under each January. Spread it into `x` or into `fx`.
export function monthAxis(options = {}) {
  return {type: "band", label: null, tickFormat: monthTick, ...options};
}

// A line of a k-day moving average, k = 7 by default. Daily series are noisy
// enough that the raw line is a smear, and the rules rule out drawing it faint
// underneath, so the average is the line.
export function windowedLine(Plot, data, {k = 7, ...options} = {}) {
  return Plot.lineY(data, Plot.windowY({k, anchor: "end"}, {
    curve: "monotone-x",
    strokeWidth: 2.5,
    ...options
  }));
}
