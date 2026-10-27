import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  browser: vi.fn(() => ({ kind: "browser" })),
  server: vi.fn((url: unknown, key: unknown, options: unknown) => {
    void url; void key; void options;
    return { kind: "server" };
  }),
  cookieJar: { getAll: vi.fn(() => [{ name: "session", value: "fake" }]), set: vi.fn() },
}));

vi.mock("@supabase/ssr", () => ({
  createBrowserClient: mocks.browser,
  createServerClient: mocks.server,
}));
vi.mock("next/headers", () => ({ cookies: vi.fn(async () => mocks.cookieJar) }));

import { NextRequest } from "next/server";
import { POST as tokenPost } from "@/app/api/livekit/token/route";
import { POST as releasePost } from "@/app/api/livekit/release/route";
import { createClient as createBrowserClient } from "./client";
import { createClient as createServerClient } from "./server";

describe.each([["token", tokenPost], ["release", releasePost]] as const)("%s request origin", (_name, post) => {
  it("accepts the browser Host even when Next normalizes the internal hostname", async () => {
    const request = new NextRequest("http://localhost:3000/api/livekit/token", { method: "POST", headers: { host: "127.0.0.1:3000", origin: "http://127.0.0.1:3000", "content-type": "text/plain" } });
    expect((await post(request)).status).toBe(415);
  });
  it("rejects requests from a different origin", async () => {
    const request = new NextRequest("http://localhost:3000/api/livekit/token", { method: "POST", headers: { host: "127.0.0.1:3000", origin: "https://untrusted.example.test", "content-type": "text/plain" } });
    expect((await post(request)).status).toBe(403);
  });
});

describe("Supabase auth client setup", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "");
    vi.stubEnv("SUPABASE_URL", "");
    vi.stubEnv("SUPABASE_ANON_KEY", "");
    mocks.browser.mockClear();
    mocks.server.mockClear();
    mocks.cookieJar.getAll.mockClear();
    mocks.cookieJar.set.mockClear();
  });

  it("requires public configuration before creating a browser client", () => {
    expect(() => createBrowserClient()).toThrow("Supabase public auth settings are missing.");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://project.example.test");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "public-anon-test");
    expect(createBrowserClient()).toEqual({ kind: "browser" });
    expect(mocks.browser).toHaveBeenCalledWith("https://project.example.test", "public-anon-test");
  });

  it("exposes cookie read/write adapters and tolerates read-only server components", async () => {
    await expect(createServerClient()).rejects.toThrow("Supabase auth settings are missing.");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://project.example.test");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "public-anon-test");
    await createServerClient();
    const options = mocks.server.mock.calls.at(-1)?.[2] as
      | {
          cookies: {
            getAll: () => unknown;
            setAll: (values: Array<{ name: string; value: string; options: Record<string, unknown> }>) => void;
          };
        }
      | undefined;
    expect(options?.cookies.getAll()).toEqual([{ name: "session", value: "fake" }]);
    options?.cookies.setAll([{ name: "session", value: "new", options: { path: "/" } }]);
    expect(mocks.cookieJar.set).toHaveBeenCalledWith("session", "new", { path: "/" });
    mocks.cookieJar.set.mockImplementation(() => { throw new Error("read only"); });
    expect(() => options?.cookies.setAll([{ name: "session", value: "ignored", options: {} }])).not.toThrow();
  });

  it("falls back to server-only SUPABASE_URL and SUPABASE_ANON_KEY when public keys are not set", async () => {
    vi.stubEnv("SUPABASE_URL", "https://server.example.test");
    vi.stubEnv("SUPABASE_ANON_KEY", "server-anon-test");
    await expect(createServerClient()).resolves.toEqual({ kind: "server" });
    expect(mocks.server).toHaveBeenCalledWith(
      "https://server.example.test",
      "server-anon-test",
      expect.anything()
    );
  });
});
