// The layout and chrome are the kit's (src/kit/); this file says which dashboard
// this is. The site is static: `npm run build` writes dist/. Every link
// Framework generates is relative, so the same build works at the root of a
// host and under a path prefix.
import {dashboardConfig} from "./src/kit/config.js";

export default dashboardConfig({
  title: "NYC Rideshare Operations",
  dataCredit: "NYC Taxi &amp; Limousine Commission trip records"
});
