const fs = require("node:fs");
const path = require("node:path");
const { loadEnvConfig } = require("@next/env");

const rootEnv = path.resolve(__dirname, "../../.env");
const localEnv = path.resolve(__dirname, ".env.local");

if (fs.existsSync(rootEnv) && !fs.existsSync(localEnv)) {
  try {
    fs.linkSync(rootEnv, localEnv);
  } catch {
    try {
      fs.copyFileSync(rootEnv, localEnv);
    } catch {
      // ignore
    }
  }
}

loadEnvConfig(__dirname);
loadEnvConfig(path.resolve(__dirname, "../.."));
