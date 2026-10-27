import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";

const root = join(process.env.NEXT_DIST_DIR ?? ".next", "static");
const variableNames = [
  "LIVEKIT_API_SECRET",
  "SUPABASE_SERVICE_ROLE_KEY",
  "SARVAM_API_KEY",
  "GEMINI_API_KEY",
  "GROQ_API_KEY",
  "IP_HASH_SECRET",
];

async function filesUnder(path) {
  const entries = await readdir(path, { withFileTypes: true });
  const nested = await Promise.all(
    entries.map((entry) => {
      const child = join(path, entry.name);
      return entry.isDirectory() ? filesUnder(child) : [child];
    }),
  );
  return nested.flat();
}

const files = await filesUnder(root);
const contents = await Promise.all(files.map((path) => readFile(path)));
let failed = false;
for (const name of variableNames) {
  const canary = process.env[name];
  const found = Boolean(canary) && contents.some((content) => content.includes(canary));
  console.log(`${name}: ${found ? "FAIL" : "PASS"}`);
  failed ||= found;
}
if (failed) process.exitCode = 1;
