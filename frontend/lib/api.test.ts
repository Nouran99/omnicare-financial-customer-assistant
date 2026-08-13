import { afterEach, describe, expect, it, vi } from "vitest";

import { ChatApiError, sendChat } from "./api";

const successPayload = {
  response: "Your claim is under review.",
  sources: [],
  tool_calls: [
    {
      name: "get_claim_status",
      status: "success",
      arguments: "CLM-9014",
      result_summary: "Claim status: Under Review.",
    },
  ],
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("sendChat", () => {
  it("sends the shared request shape and parses a ChatResponse", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(successPayload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await sendChat({ user_id: "user-1", message: "Check my claim" });

    expect(result).toEqual(successPayload);
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: "user-1", message: "Check my claim" }),
      signal: undefined,
    });
  });

  it("maps a backend validation response to a safe frontend error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: "validation_error",
            detail: "message must not be blank",
            request_id: "req-422",
          }),
          { status: 422, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    await expect(sendChat({ user_id: "user-1", message: "" })).rejects.toMatchObject({
      name: "ChatApiError",
      kind: "http",
      status: 422,
      requestId: "req-422",
      message: "Please check the message and try again.",
    });

    await expect(sendChat({ user_id: "user-1", message: "" })).rejects.not.toMatchObject({
      message: "message must not be blank",
    });
  });

  it("maps provider errors without exposing provider payloads", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: "provider_error",
            detail: "The assistant is temporarily unavailable. Please try again later.",
          }),
          { status: 502, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    await expect(sendChat({ user_id: "user-1", message: "Hello" })).rejects.toMatchObject({
      kind: "http",
      status: 502,
      message: "The assistant is temporarily unavailable. Please try again later.",
    });
  });

  it("rejects a successful response with an invalid shape", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ response: "missing arrays" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(sendChat({ user_id: "user-1", message: "Hello" })).rejects.toMatchObject({
      kind: "malformed_response",
      status: 200,
    });
  });

  it("rejects invalid JSON from a successful response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("not-json", {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(sendChat({ user_id: "user-1", message: "Hello" })).rejects.toMatchObject({
      kind: "malformed_response",
      status: 200,
    });
  });

  it("maps network failures to a safe ChatApiError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("socket details")));

    const error = await sendChat({ user_id: "user-1", message: "Hello" }).catch(
      (caught: unknown) => caught,
    );

    expect(error).toBeInstanceOf(ChatApiError);
    expect(error).toMatchObject({ kind: "network" });
    expect((error as Error).message).not.toContain("socket details");
  });

  it("maps AbortError to an explicit cancellation error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new DOMException("aborted", "AbortError")),
    );

    await expect(
      sendChat({ user_id: "user-1", message: "Hello" }),
    ).rejects.toMatchObject({
      kind: "aborted",
      message: "The request was cancelled.",
    });
  });
});
