import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "@/test/msw/server";

/**
 * Every test gets a real network boundary: MSW serves `/api/*` from the
 * handlers below, and an unmocked request fails the test instead of hanging
 * on a socket.
 */
beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
});
afterAll(() => server.close());
