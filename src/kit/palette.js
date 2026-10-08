// The page theme, and the chart colours that follow it.
//
// The stylesheet owns the chrome (page, cards, text); this file hands the marks
// their colours, because Plot takes colours as values rather than reading CSS.
// It defines none of them: every colour lives in src/theme/colors.css, and this
// file reads the tokens off the page, so there is one definition, not two.

// The theme as a reactive value: the data-theme attribute on <html>, which the
// script in dashboardConfig() sets before the first paint and the toggle button
// flips. Pass it to Framework's Generators.observe:
//
//   const theme = Generators.observe(observeTheme);
export function observeTheme(notify) {
  const read = () => (document.documentElement.dataset.theme === "light" ? "light" : "dark");
  notify(read());
  const observer = new MutationObserver(() => notify(read()));
  observer.observe(document.documentElement, {attributes: true, attributeFilter: ["data-theme"]});
  return () => observer.disconnect();
}

// One colour token from src/theme/colors.css, as the page currently resolves
// it: token("--dq-error"). Reading it forces a style recalculation, so the
// value is right even in the same tick as a theme switch.
export function token(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

// Chart colours for the theme the page is showing. `theme` is not looked up: it
// is taken so that a cell calling palette(theme) runs again when the theme
// changes, and the tokens are read fresh.
//
// `band` shades the selected period on a trend chart. `good` and `bad` are the
// --good and --bad tokens, so a delta drawn in a chart and a delta printed in a
// KPI tile are the same colour.
export function palette(theme) {
  const series = token("--series").split(",").map((c) => c.trim()).filter(Boolean);
  return {
    theme,
    lead: series[0],
    second: series[1],
    series,
    heatLow: token("--heat-low"),
    heatHigh: token("--heat-high"),
    band: token("--band"),
    bandOpacity: Number(token("--band-opacity")),
    good: token("--good"),
    bad: token("--bad")
  };
}

// A Plot `color` option for a set of named series, in the palette's order:
//
//   color: {...seriesScale(theme, ["North", "South"]), legend: true}
//
// Colours cycle if a domain is longer than the palette.
export function seriesScale(theme, domain) {
  const {series} = palette(theme);
  return {domain, range: domain.map((_, i) => series[i % series.length])};
}
