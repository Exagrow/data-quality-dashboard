// Number and date formatting shared by every dashboard. No dependencies: these
// are Intl and string work, so they run the same in the browser and in Node,
// which is what lets the tests check them without a DOM.

const compact = new Intl.NumberFormat("en-US", {notation: "compact", maximumFractionDigits: 1});
const whole = new Intl.NumberFormat("en-US", {maximumFractionDigits: 0});
const money = new Intl.NumberFormat("en-US", {style: "currency", currency: "USD", maximumFractionDigits: 2});
const moneyCompact = new Intl.NumberFormat("en-US", {style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1});

export const fmt = {
  compact: (x) => compact.format(x),
  whole: (x) => whole.format(x),
  money: (x) => money.format(x),
  moneyCompact: (x) => moneyCompact.format(x),
  pct: (x, digits = 1) => `${(100 * x).toFixed(digits)}%`,
  minutes: (seconds) => `${(seconds / 60).toFixed(1)} min`
};

// "2026-04" to "Apr 2026", or "April 2026" with style "long".
export function monthLabel(month, style = "short") {
  const [y, m] = month.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, 1)).toLocaleString("en-US", {month: style, year: "numeric", timeZone: "UTC"});
}

// Axis ticks for a run of months: "Jul" for most, with the year under the first
// tick and under each January.
export function monthTick(month, i) {
  const [y, m] = month.split("-").map(Number);
  const name = new Date(Date.UTC(y, m - 1, 1)).toLocaleString("en-US", {month: "short", timeZone: "UTC"});
  return i === 0 || m === 1 ? `${name}\n${y}` : name;
}

// Arrow rows to plain objects. Every dashboard that reads a parquet
// FileAttachment needs this before d3 or Plot will touch the rows.
export function rows(table) {
  return Array.from(table, (d) => d.toJSON());
}
