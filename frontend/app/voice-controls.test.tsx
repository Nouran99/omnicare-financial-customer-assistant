/** @vitest-environment jsdom */

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ChatResponse } from "../lib/api";
import type { ChatSubmitResult } from "../lib/use-chat-state";
import { VoiceControls } from "./voice-controls";

let recognition: MockRecognition;

class MockRecognition {
  lang = "";
  interimResults = false;
  continuous = false;
  onresult: ((event: { results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }> }) => void) | null = null;
  onerror: ((event: { error?: string }) => void) | null = null;
  onend: (() => void) | null = null;
  start = vi.fn();
  stop = vi.fn();

  constructor() {
    recognition = this;
  }
}

class MockUtterance {
  onend: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(readonly text: string) {}
}

const successfulSubmission: ChatSubmitResult = {
  submitted: true,
  succeeded: true,
  response: {
    response: "Your claim is under review.",
    sources: [],
    tool_calls: [],
  } satisfies ChatResponse,
};

function installRecognition() {
  Object.defineProperty(window, "SpeechRecognition", {
    configurable: true,
    value: MockRecognition,
  });
}

function installSpeechSynthesis() {
  const speechSynthesis = {
    cancel: vi.fn(),
    speak: vi.fn((utterance: MockUtterance) => utterance.onend?.()),
  };
  Object.defineProperty(window, "speechSynthesis", {
    configurable: true,
    value: speechSynthesis,
  });
  vi.stubGlobal("SpeechSynthesisUtterance", MockUtterance);
  return speechSynthesis;
}

function removeSpeechCapabilities() {
  Object.defineProperty(window, "SpeechRecognition", {
    configurable: true,
    value: undefined,
  });
  Object.defineProperty(window, "speechSynthesis", {
    configurable: true,
    value: undefined,
  });
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  removeSpeechCapabilities();
});

describe("VoiceControls", () => {
  beforeEach(() => {
    installRecognition();
  });

  it("shows a visible unsupported fallback without affecting the text composer contract", async () => {
    removeSpeechCapabilities();
    render(<VoiceControls onTranscript={vi.fn()} />);

    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toContain("unavailable in this browser"),
    );
    expect(screen.getByRole("button", { name: "Start voice input" })).not.toBeNull();
  });

  it("shows a permission-denied fallback when the browser rejects microphone access", async () => {
    render(<VoiceControls onTranscript={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Start voice input" }));
    recognition.onerror?.({ error: "not-allowed" });

    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toContain("access was denied"),
    );
    expect(screen.getByRole("alert").textContent).toContain(
      "You can continue with the text composer.",
    );
  });

  it("submits a final transcript through the shared callback and exposes playback", async () => {
    const speechSynthesis = installSpeechSynthesis();
    const onTranscript = vi.fn().mockResolvedValue(successfulSubmission);
    render(<VoiceControls onTranscript={onTranscript} />);

    fireEvent.click(screen.getByRole("button", { name: "Start voice input" }));
    recognition.onresult?.({
      results: [
        {
          isFinal: true,
          0: { transcript: "Check claim CLM-9014" },
        },
      ],
    });

    await waitFor(() =>
      expect(onTranscript).toHaveBeenCalledWith("Check claim CLM-9014"),
    );
    expect(speechSynthesis.speak).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: "Play spoken response" })).not.toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Play spoken response" }));
    expect(speechSynthesis.speak).toHaveBeenCalledTimes(2);
  });

  it("keeps a successful transcript readable when speech synthesis is unavailable", async () => {
    Object.defineProperty(window, "speechSynthesis", {
      configurable: true,
      value: undefined,
    });
    const onTranscript = vi.fn().mockResolvedValue(successfulSubmission);
    render(<VoiceControls onTranscript={onTranscript} />);

    fireEvent.click(screen.getByRole("button", { name: "Start voice input" }));
    recognition.onresult?.({
      results: [
        {
          isFinal: true,
          0: { transcript: "What is my claim status?" },
        },
      ],
    });

    await waitFor(() =>
      expect(screen.getByText(/Spoken playback is unavailable/)).not.toBeNull(),
    );
    expect(screen.queryByRole("button", { name: "Play response" })).toBeNull();
  });
});
