// The dashboard kit: the page chrome, KPI tile, chart conventions and
// formatting every page here shares.
//
// Everything here runs in the browser, on a page Framework has built. The build
// time half is ./config.js, which Node loads from observablehq.config.js and
// which must not pull any of this in.
//
// The kit carries no colour, typeface or logo of its own. Those are the brand,
// and they live in src/theme/.

export {element, escapeAttr, escapeText} from "./html.js";
export {fmt, monthLabel, monthTick, rows} from "./format.js";
export {observeTheme, palette, seriesScale, token} from "./palette.js";
export {masthead, mastheadHTML, sourceLine, sourceLineHTML} from "./chrome.js";
export {kpi, kpiHTML} from "./kpi.js";
export {monthAxis, monthRange, selectedBand, windowedLine} from "./plot.js";
