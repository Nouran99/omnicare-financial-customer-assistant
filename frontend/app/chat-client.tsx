"use client";

import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";

import { useChatState } from "../lib/use-chat-state";
import { AssistantMessageMetadata } from "./message-metadata";

const STARTER_PROMPTS = [
  {
    title: "Coverage question",
    message: "Does my policy cover sudden pipe bursts?",
  },
  {
    title: "Claim status",
    message: "What is the status of claim CLM-9014?",
  },
  {
    title: "Submit a claim",
    message:
      "I need to submit a water damage claim. My policy number is POL-123, the amount is $750, and a pipe burst in my kitchen.",
  },
] as const;

export function ChatClient() {
  const [userId, setUserId] = useState("policyholder-demo");
  const [message, setMessage] = useState("");
  const errorRef = useRef<HTMLDivElement>(null);
  const chat = useChatState({ userId });
  const canSubmit = Boolean(message.trim()) && !chat.pending;

  useEffect(() => {
    if (chat.error) {
      errorRef.current?.focus();
    }
  }, [chat.error]);

  async function submitMessage() {
    const outcome = await chat.submit(message);
    if (outcome.succeeded) {
      setMessage("");
    }
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submitMessage();
  }

  async function onComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      await submitMessage();
    }
  }

  return (
    <main className="chat-page-shell">
      <header className="product-header">
        <div>
          <p className="eyebrow">OmniCare financial support</p>
          <h1>Policy and claims assistance with visible safeguards.</h1>
        </div>
        <p className="prototype-badge">Prototype · mock data only</p>
      </header>

      <p className="prototype-disclaimer" role="note">
        OmniCare is a technical-assessment prototype. It cannot make real coverage,
        authorization, or claims decisions.
      </p>

      <section className="chat-workspace" aria-labelledby="conversation-heading">
        <aside className="chat-context-panel" aria-label="Conversation settings">
          <div>
            <p className="panel-label">Session identity</p>
            <label className="field-label" htmlFor="user-id">
              User ID
            </label>
            <input
              id="user-id"
              name="user-id"
              value={userId}
              onChange={(event) => setUserId(event.target.value)}
              className="text-input"
              autoComplete="off"
            />
            <p className="field-help">Used only to identify this prototype conversation.</p>
          </div>

          <div className="starter-prompt-section">
            <p className="panel-label">Try an example</p>
            <div className="starter-prompt-list">
              {STARTER_PROMPTS.map((prompt) => (
                <button
                  key={prompt.title}
                  type="button"
                  className="starter-prompt"
                  onClick={() => setMessage(prompt.message)}
                  disabled={chat.pending}
                >
                  <span>{prompt.title}</span>
                  <small>{prompt.message}</small>
                </button>
              ))}
            </div>
          </div>
        </aside>

        <section className="chat-panel" aria-labelledby="conversation-heading">
          <div className="conversation-heading-row">
            <div>
              <p className="panel-label">Assistant conversation</p>
              <h2 id="conversation-heading">How can OmniCare help?</h2>
            </div>
            {chat.pending ? <span className="pending-indicator">Working</span> : null}
          </div>

          <div
            className="message-history"
            aria-live="polite"
            aria-atomic="false"
            aria-busy={chat.pending}
          >
            {chat.messages.length === 0 ? (
              <div className="empty-conversation">
                <p className="empty-kicker">Ready when you are</p>
                <p>
                  Ask about the sample policy, check a mock claim, or begin a guided
                  claim submission through the same secure conversation.
                </p>
              </div>
            ) : (
              chat.messages.map((chatMessage) => (
                <article
                  key={chatMessage.id}
                  className={`message-bubble message-bubble-${chatMessage.role}`}
                  aria-label={chatMessage.role === "user" ? "Your message" : "OmniCare response"}
                >
                  <p className="message-role">
                    {chatMessage.role === "user" ? "You" : "OmniCare"}
                  </p>
                  <p className="message-content">{chatMessage.content}</p>
                  {chatMessage.role === "assistant" ? (
                    <AssistantMessageMetadata
                      sources={chatMessage.sources}
                      toolCalls={chatMessage.tool_calls}
                    />
                  ) : null}
                </article>
              ))
            )}
            {chat.pending ? (
              <div className="assistant-loading" role="status">
                <span className="loading-dot" aria-hidden="true" />
                OmniCare is preparing a safe response…
              </div>
            ) : null}
          </div>

          {chat.error ? (
            <div
              ref={errorRef}
              id="chat-error"
              className="chat-error"
              role="alert"
              tabIndex={-1}
            >
              <span>{chat.error}</span>
              <button type="button" onClick={chat.clearError} aria-label="Dismiss error message">
                Dismiss
              </button>
            </div>
          ) : null}

          <form className="chat-composer" onSubmit={onSubmit}>
            <label className="field-label" htmlFor="message">
              Your message
            </label>
            <textarea
              id="message"
              name="message"
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              onKeyDown={onComposerKeyDown}
              placeholder="Ask a policy or claims question…"
              className="message-input"
              rows={4}
              aria-describedby="message-help"
              disabled={chat.pending}
            />
            <div className="composer-footer">
              <p id="message-help">Press Ctrl/Cmd + Enter to send.</p>
              <button className="send-button" type="submit" disabled={!canSubmit}>
                {chat.pending ? "Sending…" : "Send message"}
              </button>
            </div>
          </form>
        </section>
      </section>
    </main>
  );
}
