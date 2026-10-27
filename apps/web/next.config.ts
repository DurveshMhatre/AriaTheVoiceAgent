import fs from "node:fs";
import path from "node:path";
import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";

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

const nextConfig: NextConfig = {
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
  poweredByHeader: false,
  images: { unoptimized: true },
  experimental: { cpus: 1 },
  async headers() {
    return [{ source: "/:path*", headers: [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "Permissions-Policy", value: "microphone=(self), camera=(), geolocation=()" },
      { key: "X-Frame-Options", value: "DENY" },
    ] }];
  },
};
export default nextConfig;
