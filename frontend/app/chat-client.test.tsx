/** @vitest-environment jsdom */

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChatClient } from "./chat-client";

function successResponse() {
  return new Response(
    JSON.stringify({ response: "Your claim is under review.", sources: [], tool_calls: [] }),
    { status: 200, headers: { "Content-Type": "application/json" } },
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("ChatClient", () => {
  it("renders the product purpose, disclaimer, editable user ID, composer, and empty state", () => {
    render(<ChatClient />);

    expect(
      screen.getByRole("heading", { name: "Policy and claims assistance with visible safeguards." }),
    ).not.toBeNull();
    expect(screen.getByRole("note").textContent).toContain("technical-assessment prototype");
    expect((screen.getByLabelText("User ID") as HTMLInputElement).value).toBe(
      "policyholder-demo",
    );
    expect(screen.getByLabelText("Your message")).not.toBeNull();
    expect(screen.getByText("Ready when you are")).not.toBeNull();
    expect((screen.getByRole("button", { name: "Send message" }) as HTMLButtonElement).disabled).toBe(
      true,
    );
  });

  it("allows the visible user ID to be edited and starter prompts to populate the composer", () => {
    render(<ChatClient />);

    fireEvent.change(screen.getByLabelText("User ID"), {
      target: { value: "reviewer-42" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Claim status/ }));

    expect((screen.getByLabelText("User ID") as HTMLInputElement).value).toBe("reviewer-42");
    expect((screen.getByLabelText("Your message") as HTMLTextAreaElement).value).toBe(
      "What is the status of claim CLM-9014?",
    );
    expect((screen.getByRole("button", { name: "Send message" }) as HTMLButtonElement).disabled).toBe(
      false,
    );
  });

  it("shows a pending state and disables duplicate sends until the response resolves", async () => {
    let resolveFetch!: (response: Response) => void;
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>((resolve) => (resolveFetch = resolve))),
    );
    render(<ChatClient />);

    fireEvent.change(screen.getByLabelText("Your message"), {
      target: { value: "Check claim CLM-9014" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));

    expect((screen.getByRole("button", { name: "Sending…" }) as HTMLButtonElement).disabled).toBe(
      true,
    );
    expect(screen.getByRole("status").textContent).toContain("OmniCare is preparing");
    expect((screen.getByRole("textbox", { name: "Your message" }) as HTMLTextAreaElement).disabled).toBe(true);

    resolveFetch(successResponse());

    await waitFor(() => expect(screen.getByText("Your claim is under review.")).not.toBeNull());
    expect((screen.getByRole("button", { name: "Send message" }) as HTMLButtonElement).disabled).toBe(
      true,
    );
  });

  it("submits from the textarea with Ctrl+Enter and keeps the composer keyboard-operable", async () => {
    const fetchMock = vi.fn().mockResolvedValue(successResponse());
    vi.stubGlobal("fetch", fetchMock);
    render(<ChatClient />);

    const messageInput = screen.getByRole("textbox", { name: "Your message" });
    fireEvent.change(messageInput, { target: { value: "Check claim CLM-9014" } });
    fireEvent.keyDown(messageInput, { key: "Enter", ctrlKey: true });

    await waitFor(() => expect(screen.getByText("Your claim is under review.")).not.toBeNull());
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("moves focus to a concise safe error when a provider request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("private socket detail")));
    render(<ChatClient />);

    fireEvent.change(screen.getByRole("textbox", { name: "Your message" }), {
      target: { value: "Check claim CLM-9014" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));

    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("alert")));
    expect(screen.getByRole("alert").getAttribute("tabindex")).toBe("-1");
    expect(screen.getByRole("alert").textContent).not.toContain("private socket detail");
  });

  it("shows a safe error while retaining the user message when the request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("private socket detail")));
    render(<ChatClient />);

    fireEvent.change(screen.getByLabelText("Your message"), {
      target: { value: "Check claim CLM-9014" },
    });
    fireEvent.submit(screen.getByRole("button", { name: "Send message" }).closest("form")!);

    await waitFor(() => expect(screen.getByRole("alert")).not.toBeNull());
    expect(screen.getByRole("alert").textContent).toContain(
      "The assistant could not be reached. Please check your connection and try again.",
    );
    expect(screen.getByRole("article", { name: "Your message" }).textContent).toContain(
      "Check claim CLM-9014",
    );
    expect(screen.queryByText("private socket detail")).toBeNull();
  });
});
