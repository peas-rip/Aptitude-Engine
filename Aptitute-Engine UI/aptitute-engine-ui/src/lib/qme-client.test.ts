import { describe, it, expect, vi } from "vitest";
import { QmeClient, ApiError, toApiError, asApiError } from "./qme-client";

function jsonRes(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Typed `fetch` mock. The bare `mockFetch(async () => …)` form infers a zero-length
 * args tuple, so `mock.calls[0][1]` would not typecheck.
 */
function mockFetch(
  handler: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>,
) {
  return vi.fn(handler);
}

const ENVELOPE = {
  error: {
    code: "INVALID_INPUT",
    message: "test request violates the request rules: count_multiple_of_5 (actual: 12)",
    details: {
      violations: [{ rule: "count_multiple_of_5", actual: 12, expected: "multiple of 5" }],
    },
    request_id: "0f1e2d3c-4b5a-6978-8765-43210fedcba9",
  },
};

describe("QmeClient — success path", () => {
  it("parses a JSON payload", async () => {
    const fetchImpl = mockFetch(async () => jsonRes(200, { status: "ok" }));
    const client = new QmeClient({ baseUrl: "/api/qme", fetchImpl: fetchImpl as typeof fetch });
    await expect(client.get("/health")).resolves.toEqual({ status: "ok" });
  });

  it("joins the path to a baseUrl that has a trailing slash", async () => {
    const fetchImpl = mockFetch(async () => jsonRes(200, {}));
    const client = new QmeClient({
      baseUrl: "/api/qme///",
      fetchImpl: fetchImpl as typeof fetch,
    });
    await client.get("/bank/meta");
    expect(fetchImpl.mock.calls[0][0]).toBe("/api/qme/bank/meta");
  });

  it("appends only defined, non-empty query params", async () => {
    const fetchImpl = mockFetch(async () => jsonRes(200, {}));
    const client = new QmeClient({ baseUrl: "/api/qme", fetchImpl: fetchImpl as typeof fetch });
    await client.get("/chapters/X/knowledge", { topic: "Ratio", skip: undefined, empty: "" });
    expect(fetchImpl.mock.calls[0][0]).toBe("/api/qme/chapters/X/knowledge?topic=Ratio");
  });

  it("sends Content-Type only when there is a body, and X-API-Key when configured", async () => {
    const fetchImpl = mockFetch(async () => jsonRes(200, {}));
    const client = new QmeClient({
      baseUrl: "/api/qme",
      apiKey: "dev-key",
      fetchImpl: fetchImpl as typeof fetch,
    });

    await client.get("/bank/meta");
    let init = fetchImpl.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
    expect((init.headers as Record<string, string>)["X-API-Key"]).toBe("dev-key");

    await client.post("/tests", { count: 10 });
    init = fetchImpl.mock.calls[1][1] as RequestInit;
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
    expect(init.body).toBe('{"count":10}');
  });

  it("omits X-API-Key when none is configured (open dev API)", async () => {
    const fetchImpl = mockFetch(async () => jsonRes(200, {}));
    const client = new QmeClient({ baseUrl: "/api/qme", fetchImpl: fetchImpl as typeof fetch });
    await client.get("/bank/meta");
    const init = fetchImpl.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>)["X-API-Key"]).toBeUndefined();
  });
});

describe("QmeClient — error envelope parsing", () => {
  it("maps an envelope onto ApiError: status, code, details, violations", async () => {
    const fetchImpl = mockFetch(async () => jsonRes(422, ENVELOPE));
    const client = new QmeClient({ baseUrl: "/api/qme", fetchImpl: fetchImpl as typeof fetch });

    const err = await client.post("/tests", {}).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    const api = err as ApiError;
    expect(api.status).toBe(422);
    expect(api.code).toBe("INVALID_INPUT");
    expect(api.message).toContain("count_multiple_of_5");
    expect(api.violations).toEqual([
      { rule: "count_multiple_of_5", actual: 12, expected: "multiple of 5" },
    ]);
    expect(api.fields).toEqual([]);
  });

  it("captures request_id and reports it through onRequestId", async () => {
    const onRequestId = vi.fn();
    const fetchImpl = mockFetch(async () => jsonRes(422, ENVELOPE));
    const client = new QmeClient({
      baseUrl: "/api/qme",
      fetchImpl: fetchImpl as typeof fetch,
      onRequestId,
    });

    const api = (await client.post("/tests", {}).catch((e: unknown) => e)) as ApiError;
    expect(api.requestId).toBe("0f1e2d3c-4b5a-6978-8765-43210fedcba9");
    expect(onRequestId).toHaveBeenCalledWith("0f1e2d3c-4b5a-6978-8765-43210fedcba9");
  });

  it("classifies an unknown envelope code as UNKNOWN_ERROR", async () => {
    const body = {
      error: { code: "SOMETHING_NEW", message: "m", details: {}, request_id: "r" },
    };
    const fetchImpl = mockFetch(async () => jsonRes(418, body));
    const client = new QmeClient({ baseUrl: "/api/qme", fetchImpl: fetchImpl as typeof fetch });
    const api = (await client.get("/x").catch((e: unknown) => e)) as ApiError;
    expect(api.code).toBe("UNKNOWN_ERROR");
    expect(api.status).toBe(418);
    // The message still reaches the UI even though the code is unknown.
    expect(api.message).toBe("m");
  });

  it("exposes field errors from VALIDATION_ERROR", async () => {
    const body = {
      error: {
        code: "VALIDATION_ERROR",
        message: "schema",
        details: { fields: [{ location: "count", message: "Field required" }] },
        request_id: "r2",
      },
    };
    const fetchImpl = mockFetch(async () => jsonRes(422, body));
    const client = new QmeClient({ baseUrl: "/api/qme", fetchImpl: fetchImpl as typeof fetch });
    const api = (await client.post("/tests", {}).catch((e: unknown) => e)) as ApiError;
    expect(api.code).toBe("VALIDATION_ERROR");
    expect(api.fields).toEqual([{ location: "count", message: "Field required" }]);
  });
});

describe("QmeClient — transport vs HTTP classification", () => {
  it("turns a network/CORS failure into NETWORK_ERROR with status 0", async () => {
    const fetchImpl = mockFetch(async () => {
      throw new TypeError("Failed to fetch");
    });
    const client = new QmeClient({ baseUrl: "/api/qme", fetchImpl: fetchImpl as typeof fetch });
    const api = (await client.get("/health").catch((e: unknown) => e)) as ApiError;
    expect(api.code).toBe("NETWORK_ERROR");
    expect(api.status).toBe(0);
    expect(api.message).toContain("Network request failed");
  });

  it("does NOT treat a non-envelope HTTP 404 as an API envelope (proxy/nginx 404)", async () => {
    const fetchImpl = vi.fn(
      async () => new Response('{"detail":"Not Found"}', { status: 404 }),
    );
    const client = new QmeClient({ baseUrl: "/api/qme", fetchImpl: fetchImpl as typeof fetch });
    const api = (await client.get("/bank/meta").catch((e: unknown) => e)) as ApiError;
    expect(api.code).toBe("UNKNOWN_ERROR");
    expect(api.status).toBe(404);
    expect(api.requestId).toBeUndefined();
  });

  it("maps a non-envelope 401 to UNAUTHORIZED", async () => {
    const fetchImpl = mockFetch(async () => new Response("nope", { status: 401 }));
    const client = new QmeClient({ baseUrl: "/api/qme", fetchImpl: fetchImpl as typeof fetch });
    const api = (await client.get("/bank/meta").catch((e: unknown) => e)) as ApiError;
    expect(api.code).toBe("UNAUTHORIZED");
    expect(api.status).toBe(401);
  });
});

describe("error helpers", () => {
  it("toApiError narrows only ApiError", () => {
    expect(toApiError(new ApiError(422, "INVALID_INPUT", "x"))).toBeInstanceOf(ApiError);
    expect(toApiError(new Error("boom"))).toBeNull();
    expect(toApiError(undefined)).toBeNull();
  });

  it("asApiError always yields something renderable", () => {
    expect(asApiError(new Error("boom")).code).toBe("UNKNOWN_ERROR");
    expect(asApiError("plain string").message).toBe("plain string");
    const original = new ApiError(503, "SERVICE_UNAVAILABLE", "down");
    expect(asApiError(original)).toBe(original);
  });
});

/**
 * Regression: the default `fetchImpl` used to be the raw global `fetch`, called
 * as `this.fetchImpl(…)`. WebIDL then binds `this` to the QmeClient, and Chrome
 * throws "TypeError: Failed to execute 'fetch' on 'Window': Illegal invocation"
 * — which the transport catch turned into NETWORK_ERROR on EVERY call, so the
 * app showed "Can't reach the server" against a healthy backend. Node and
 * jsdom-style mocks never reject a foreign receiver, so only a receiver-strict
 * fake (like Window) catches this.
 */
describe("default fetch receiver", () => {
  it("never invokes the global fetch with itself as the receiver", async () => {
    const receivers: unknown[] = [];
    vi.stubGlobal(
      "fetch",
      function (this: unknown, _input: RequestInfo | URL, _init?: RequestInit) {
        receivers.push(this);
        return Promise.resolve(
          new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
        );
      },
    );
    try {
      const client = new QmeClient({ baseUrl: "/api/qme" });
      await expect(client.get("/health")).resolves.toEqual({ status: "ok" });
    } finally {
      vi.unstubAllGlobals();
    }

    expect(receivers).toHaveLength(1);
    // A bare call passes undefined; an explicit one passes the global. Either
    // is legal. The client instance is not.
    expect(receivers[0] === undefined || receivers[0] === globalThis).toBe(true);
  });

  it("still honours an injected fetchImpl", async () => {
    const fetchImpl = mockFetch(async () => jsonRes(200, { ok: 1 }));
    const client = new QmeClient({ baseUrl: "/api/qme", fetchImpl: fetchImpl as typeof fetch });
    await expect(client.get("/health")).resolves.toEqual({ ok: 1 });
  });
});
