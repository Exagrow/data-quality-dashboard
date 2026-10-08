// Once a month, ask Netlify to rebuild the site. The build does the real work
// (see netlify.toml). A scheduled function has 30 seconds; this needs one.
//
// BUILD_HOOK_URL is a build hook for this site, set as an environment variable
// in Netlify. Anyone holding it can trigger builds, so it is never in the repo.
export default async () => {
  const hook = Netlify.env.get("BUILD_HOOK_URL");
  if (!hook) {
    console.log("monthly-rebuild: BUILD_HOOK_URL is not set; nothing triggered");
    return;
  }
  const response = await fetch(`${hook}?trigger_title=${encodeURIComponent("Monthly data refresh")}`, { method: "POST" });
  console.log(`monthly-rebuild: build requested, Netlify answered ${response.status}`);
};

// The 3rd of each month, 14:17 UTC. TLC publishes about two months behind, on no fixed day.
export const config = { schedule: "17 14 3 * *" };
