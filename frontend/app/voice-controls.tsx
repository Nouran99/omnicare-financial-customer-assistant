"use client";

import { useEffect, useRef, useState } from "react";

import type { ChatResponse } from "../lib/api";
import type { ChatSubmitResult } from "../lib/use-chat-state";

type VoiceStatus =
  | "idle"
  | "listening"
  | "transcribing"
  | "permission-denied"
  | "unsupported"
  | "submitting"
  | "speaking";

type RecognitionError = {
  error?: string;
};

type RecognitionResult = {
  results: ArrayLike<{
    isFinal: boolean;
    0: { transcript: string };
  }>;
};

interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((event: RecognitionResult) => void) | null;
  onerror: ((event: RecognitionError) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

type VoiceWindow = Window & {
  SpeechRecognition?: SpeechRecognitionConstructor;
  webkitSpeechRecognition?: SpeechRecognitionConstructor;
};

interface VoiceControlsProps {
  disabled?: boolean;
  onTranscript: (transcript: string) => Promise<ChatSubmitResult>;
}

function recognitionConstructor(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") {
    return null;
  }
  const browserWindow = window as VoiceWindow;
  return browserWindow.SpeechRecognition ?? browserWindow.webkitSpeechRecognition ?? null;
}

function isSpeechSynthesisAvailable(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.speechSynthesis?.speak === "function" &&
    typeof window.speechSynthesis?.cancel === "function"
  );
}

function statusLabel(status: VoiceStatus): string {
  switch (status) {
    case "listening":
      return "Listening… speak now";
    case "transcribing":
      return "Transcribing your request…";
    case "submitting":
      return "Sending transcript…";
    case "speaking":
      return "Speaking response…";
    case "permission-denied":
      return "Microphone permission was denied.";
    case "unsupported":
      return "Voice input is not supported in this browser.";
    default:
      return "Voice input is ready.";
  }
}

export function VoiceControls({ disabled = false, onTranscript }: VoiceControlsProps) {
  const [status, setStatus] = useState<VoiceStatus>(() =>
    recognitionConstructor() ? "idle" : "unsupported",
  );
  const [speechSupported] = useState(isSpeechSynthesisAvailable);
  const [spokenText, setSpokenText] = useState("");
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const submissionActiveRef = useRef(false);

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
      if (isSpeechSynthesisAvailable()) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  async function submitTranscript(transcript: string) {
    submissionActiveRef.current = true;
    setStatus("submitting");
    const result = await onTranscript(transcript);
    submissionActiveRef.current = false;

    if (result.succeeded && result.response) {
      const responseText = result.response.response;
      setSpokenText(responseText);
      if (speechSupported && isSpeechSynthesisAvailable()) {
        speak(responseText);
      } else {
        setStatus("idle");
      }
    } else {
      setStatus("idle");
    }
  }

  function startListening() {
    if (disabled) {
      return;
    }
    const Constructor = recognitionConstructor();
    if (!Constructor) {
      setStatus("unsupported");
      return;
    }

    const recognition = new Constructor();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.onresult = (event) => {
      setStatus("transcribing");
      const transcript = Array.from(event.results)
        .filter((result) => result.isFinal)
        .map((result) => result[0].transcript)
        .join(" ")
        .trim();
      recognition.stop();
      if (transcript) {
        void submitTranscript(transcript);
      } else {
        setStatus("idle");
      }
    };
    recognition.onerror = (event) => {
      submissionActiveRef.current = false;
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        setStatus("permission-denied");
      } else {
        setStatus("idle");
      }
    };
    recognition.onend = () => {
      if (!submissionActiveRef.current) {
        setStatus((previous) => (previous === "listening" ? "idle" : previous));
      }
    };
    recognitionRef.current = recognition;
    setStatus("listening");
    try {
      recognition.start();
    } catch {
      setStatus("permission-denied");
    }
  }

  function stopListening() {
    recognitionRef.current?.stop();
    setStatus("idle");
  }

  function speak(text: string) {
    if (!isSpeechSynthesisAvailable()) {
      setStatus("idle");
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.onend = () => setStatus("idle");
    utterance.onerror = () => setStatus("idle");
    setStatus("speaking");
    window.speechSynthesis.speak(utterance);
  }

  function stopSpeaking() {
    if (isSpeechSynthesisAvailable()) {
      window.speechSynthesis.cancel();
    }
    setStatus("idle");
  }

  const isListening = status === "listening" || status === "transcribing";
  const canPlay = Boolean(spokenText) && speechSupported && !disabled;

  return (
    <section className="voice-controls" aria-label="Optional voice controls">
      <div className="voice-control-row">
        <button
          type="button"
          className="voice-button"
          onClick={isListening ? stopListening : startListening}
          disabled={disabled || status === "transcribing" || status === "submitting"}
          aria-label={isListening ? "Stop voice input" : "Start voice input"}
        >
          {isListening ? "Stop listening" : "Use voice input"}
        </button>
        {spokenText ? (
          <button
            type="button"
            className="voice-secondary-button"
            onClick={status === "speaking" ? stopSpeaking : () => speak(spokenText)}
            disabled={!canPlay && status !== "speaking"}
            aria-label={status === "speaking" ? "Stop spoken response" : "Play spoken response"}
          >
            {status === "speaking" ? "Stop playback" : "Play response"}
          </button>
        ) : null}
      </div>
      <p className="voice-status" role="status" aria-live="polite">
        {statusLabel(status)}
      </p>
      {status === "permission-denied" ? (
        <p className="voice-fallback" role="alert">
          Microphone access was denied. You can continue with the text composer.
        </p>
      ) : null}
      {status === "unsupported" ? (
        <p className="voice-fallback" role="alert">
          Voice input is unavailable in this browser. You can continue with the text composer.
        </p>
      ) : null}
      {spokenText && !speechSupported ? (
        <p className="voice-fallback">
          Spoken playback is unavailable here; the assistant response remains visible as text.
        </p>
      ) : null}
    </section>
  );
}
