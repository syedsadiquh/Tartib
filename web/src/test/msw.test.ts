import { describe, expect, it } from "vitest";

/** Proves the MSW boundary itself works before any feature test leans on it. */
describe("msw", () => {
  it("serves /api/health from the default handlers", async () => {
    const response = await fetch("/api/health");

    expect(response.ok).toBe(true);
    await expect(response.json()).resolves.toEqual({ status: "ok" });
  });
});
