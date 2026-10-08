// Keeps computed results (data/tlc) in Netlify Blobs, so a build only computes
// months nobody has computed yet, and a redeploy wastes nothing.
//
// A build may read the site's permanent store but may only write to its own
// deploy's store (Netlify's rule, so a failed deploy cannot damage live data).
// So: before the build, months are restored from the permanent store "tlc-results".
// After it, every month is written to this deploy's store, and once the deploy
// succeeds, netlify/functions/deploy-succeeded.mjs copies them to the permanent one.
// Results committed to the repo always win over stored ones.
import { cp, mkdir, readdir, rm, stat, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { getStore } from "@netlify/blobs";

const RESULTS = "data/tlc";
const STORE = "tlc-results";
const DEPLOY_BLOBS = ".netlify/blobs/deploy";
const isMonth = (name) => /^\d{4}-\d{2}$/.test(name);
const exists = (p) => stat(p).then(() => true, () => false);

export const onPreBuild = async ({ constants }) => {
  await mkdir(RESULTS, { recursive: true });
  const store = getStore({ name: STORE, siteID: constants.SITE_ID, token: constants.NETLIFY_API_TOKEN });
  const { blobs } = await store.list();
  const months = [...new Set(blobs.map((b) => b.key.split("/")[0]).filter(isMonth))];
  let restored = 0;
  for (const month of months) {
    if (await exists(join(RESULTS, month, "quality.parquet"))) continue; // the repo's copy wins
    for (const { key } of blobs.filter((b) => b.key.startsWith(`${month}/`))) {
      const target = join(RESULTS, key);
      await mkdir(dirname(target), { recursive: true });
      await writeFile(target, Buffer.from(await store.get(key, { type: "arrayBuffer" })));
    }
    restored += 1;
  }
  console.log(`results-cache: ${months.length} month(s) in Blobs, restored ${restored} the repo does not have`);
};

export const onPostBuild = async () => {
  const out = join(DEPLOY_BLOBS, STORE);
  await rm(out, { recursive: true, force: true });
  await mkdir(out, { recursive: true });
  const months = (await readdir(RESULTS)).filter(isMonth);
  for (const month of months) await cp(join(RESULTS, month), join(out, month), { recursive: true });
  console.log(`results-cache: handed ${months.length} month(s) to this deploy; they reach the permanent store when it succeeds`);
};
