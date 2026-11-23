import { describe, expect, it } from "vitest";
import nextConfig from "../next.config";

/**
 * The rewrite is the only way the browser reaches FastAPI (D-02) and the
 * headers are the app's only CSP, so both are worth a test: a typo here is
 * invisible until a browser blocks something in production.
 */
describe("next.config", () => {
  it("proxies /api/* to the API origin", async () => {
    const rewrites = await nextConfig.rewrites?.();
    expect(rewrites).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          source: "/api/:path*",
          destination: expect.stringMatching(/^https?:\/\/.+\/api\/:path\*$/),
        }),
      ]),
    );
  });

  it("sends the security headers on every route", async () => {
    const headers = await nextConfig.headers?.();
    const all = headers?.flatMap((entry) => entry.headers) ?? [];
    const byKey = new Map(all.map((header) => [header.key, header.value]));

    expect(byKey.get("Strict-Transport-Security")).toContain("max-age=");
    expect(byKey.get("X-Content-Type-Options")).toBe("nosniff");
    expect(byKey.get("Content-Security-Policy")).toContain("default-src 'self'");
    expect(byKey.get("Content-Security-Policy")).toContain("frame-ancestors 'none'");
  });
});
