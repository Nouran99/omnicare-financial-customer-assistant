/** @vitest-environment jsdom */

import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ChatResponse } from "./api";
import { useChatState } from "./use-chat-state";

const response: ChatResponse = {
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

const ids = ["user-message-1", "assistant-message-1", "user-message-2", "assistant-message-2"];

function deterministicOptions(sendChat: typeof import("./api").sendChat) {
  let index = 0;
  return {
    userId: "user-1",
    sendChat,
    createId: () => ids[index++] ?? `message-${index}`,
    now: () => "2026-08-13T00:00:00.000Z",
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useChatState", () => {
  it("starts with an empty, idle state", () => {
    const { result } = renderHook(() => useChatState({ userId: "user-1" }));

    expect(result.current.messages).toEqual([]);
    expect(result.current.pending).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("appends the user message before the assistant response and preserves metadata", async () => {
    const sendChat = vi.fn().mockResolvedValue(response);
    const { result } = renderHook(() =>
      useChatState(deterministicOptions(sendChat)),
    );

    let submission: Promise<{ submitted: boolean; succeeded: boolean }>;
    act(() => {
      submission = result.current.submit(" Check my claim ");
    });

    expect(result.current.pending).toBe(true);
    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0]).toMatchObject({
      role: "user",
      content: "Check my claim",
    });

    await act(async () => {
      await submission;
    });

    expect(result.current.pending).toBe(false);
    expect(result.current.error).toBeNull();
    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[1]).toMatchObject({
      role: "assistant",
      content: response.response,
      sources: response.sources,
      tool_calls: response.tool_calls,
    });
    expect(sendChat).toHaveBeenCalledWith({ user_id: "user-1", message: "Check my claim" });
  });

  it("prevents a duplicate submission while the first request is pending", async () => {
    let resolveRequest!: (value: ChatResponse) => void;
    const sendChat = vi.fn(
      () => new Promise<ChatResponse>((resolve) => (resolveRequest = resolve)),
    );
    const { result } = renderHook(() =>
      useChatState(deterministicOptions(sendChat)),
    );

    let first: Promise<{ submitted: boolean; succeeded: boolean }>;
    let second: Promise<{ submitted: boolean; succeeded: boolean }>;
    act(() => {
      first = result.current.submit("First message");
      second = result.current.submit("Second message");
    });

    await expect(second!).resolves.toEqual({ submitted: false, succeeded: false });
    expect(sendChat).toHaveBeenCalledOnce();
    expect(result.current.messages).toHaveLength(1);

    await act(async () => {
      resolveRequest(response);
      await first!;
    });
  });

  it("keeps prior history and the failed user message when a later request fails", async () => {
    const sendChat = vi
      .fn()
      .mockResolvedValueOnce(response)
      .mockRejectedValueOnce(new Error("private network detail"));
    const { result } = renderHook(() =>
      useChatState(deterministicOptions(sendChat)),
    );

    await act(async () => {
      await result.current.submit("First message");
    });
    await act(async () => {
      await result.current.submit("Second message");
    });

    expect(result.current.messages.map((message) => message.content)).toEqual([
      "First message",
      response.response,
      "Second message",
    ]);
    expect(result.current.error).toBe(
      "The message could not be sent safely. Please try again.",
    );
    expect(result.current.pending).toBe(false);
  });

  it("does not submit empty or whitespace-only input", async () => {
    const sendChat = vi.fn().mockResolvedValue(response);
    const { result } = renderHook(() =>
      useChatState(deterministicOptions(sendChat)),
    );

    let outcome: { submitted: boolean; succeeded: boolean };
    await act(async () => {
      outcome = await result.current.submit("   ");
    });

    expect(outcome!).toEqual({ submitted: false, succeeded: false });
    expect(sendChat).not.toHaveBeenCalled();
    expect(result.current.messages).toEqual([]);
    expect(result.current.pending).toBe(false);
  });

  it("clears a safe error without deleting message history", async () => {
    const sendChat = vi.fn().mockRejectedValue(new Error("private detail"));
    const { result } = renderHook(() =>
      useChatState(deterministicOptions(sendChat)),
    );

    await act(async () => {
      await result.current.submit("First message");
    });
    expect(result.current.error).not.toBeNull();

    act(() => {
      result.current.clearError();
    });

    await waitFor(() => expect(result.current.error).toBeNull());
    expect(result.current.messages).toHaveLength(1);
  });
});
