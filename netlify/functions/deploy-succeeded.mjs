// Runs when a deploy succeeds (Netlify triggers a function with this name; it
// cannot be called from outside). Copies the results the build handed to the
// deploy into the permanent store, where the next build will find them.
import { getDeployStore, getStore } from "@netlify/blobs";

const STORE = "tlc-results";

export default async (req) => {
  const { payload } = await req.json().catch(() => ({}));
  const deployID = payload?.id;
  const from = deployID ? getDeployStore({ deployID }) : getDeployStore();
  const to = getStore(STORE);
  const { blobs } = await from.list({ prefix: `${STORE}/` });
  await Promise.all(blobs.map(async ({ key }) => {
    await to.set(key.slice(STORE.length + 1), await from.get(key, { type: "arrayBuffer" }));
  }));
  console.log(`deploy-succeeded: copied ${blobs.length} result file(s) from deploy ${deployID} to ${STORE}`);
  return new Response("ok");
};
