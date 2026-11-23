import { http, HttpResponse } from "msw";

/**
 * Default handlers cover the bootstrap calls every screen makes once the API
 * client exists (WEB-04). Per-test overrides use `server.use(...)`.
 */
export const handlers = [http.get("/api/health", () => HttpResponse.json({ status: "ok" }))];
