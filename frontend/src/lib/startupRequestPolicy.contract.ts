import { STARTUP_REQUEST_TIMEOUT_MS } from "./startupRequestPolicy";

function expect(condition: boolean, message: string): void {
  if (!condition) throw new Error(message);
}

async function main(): Promise<void> {
  process.env.NEXT_PUBLIC_IDENTITY_MODE = "demo";
  const observedTimeouts: number[] = [];
  const observedRequests: Array<{ url: string; method: string }> = [];
  const originalTimeout = AbortSignal.timeout;
  const originalFetch = globalThis.fetch;

  AbortSignal.timeout = ((milliseconds: number) => {
    observedTimeouts.push(milliseconds);
    return new AbortController().signal;
  }) as typeof AbortSignal.timeout;
  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    observedRequests.push({
      url: input instanceof Request ? input.url : String(input),
      method: init?.method ?? (input instanceof Request ? input.method : "GET"),
    });
    return new Response(JSON.stringify({ session_id: "0123456789abcdef", status: "active" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }) as typeof fetch;

  try {
    const { createSession, getSession } = await import("./api");
    const { fetchCurrentUser } = await import("./appAuth");
    await getSession("0123456789abcdef");
    await createSession();
    await fetchCurrentUser(new Headers());
  } finally {
    AbortSignal.timeout = originalTimeout;
    globalThis.fetch = originalFetch;
  }

  expect(STARTUP_REQUEST_TIMEOUT_MS === 60_000, "startup request budget must remain 60 seconds");
  expect(
    observedTimeouts.length === 3 && observedTimeouts.every((value) => value === STARTUP_REQUEST_TIMEOUT_MS),
    "authentication and session startup requests must use the shared startup timeout",
  );
  expect(
    observedRequests[0]?.url.endsWith("/sessions/0123456789abcdef") && observedRequests[0]?.method === "GET",
    "session restore must check the stored session",
  );
  expect(
    observedRequests[1]?.url.endsWith("/sessions") && observedRequests[1]?.method === "POST",
    "session creation must use the session collection endpoint",
  );
  expect(
    observedRequests[2]?.url.endsWith("/auth/me") && observedRequests[2]?.method === "GET",
    "Entra startup must resolve the current user through /auth/me",
  );

  const { INACTIVITY_TIMEOUT_MS } = await import("./sse");
  expect(
    INACTIVITY_TIMEOUT_MS > STARTUP_REQUEST_TIMEOUT_MS,
    "an active assistant turn must outlive the startup request budget",
  );
}

void main();
