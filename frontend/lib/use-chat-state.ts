"use client";

import { useCallback, useRef, useState } from "react";

import {
  ChatApiError,
  type ChatResponse,
  sendChat as defaultSendChat,
} from "./api";

export interface UserChatMessage {
  id: string;
  role: "user";
  content: string;
  created_at: string;
}

export interface AssistantChatMessage {
  id: string;
  role: "assistant";
  content: string;
  sources: string[];
  tool_calls: ChatResponse["tool_calls"];
  created_at: string;
}

export type ChatMessage = UserChatMessage | AssistantChatMessage;

export interface ChatState {
  messages: ChatMessage[];
  pending: boolean;
  error: string | null;
}

export interface ChatSubmitResult {
  submitted: boolean;
  succeeded: boolean;
  response?: ChatResponse;
}

export interface UseChatStateOptions {
  userId: string;
  sendChat?: typeof defaultSendChat;
  createId?: () => string;
  now?: () => string;
}

const EMPTY_STATE: ChatState = {
  messages: [],
  pending: false,
  error: null,
};

function createMessageId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function safeErrorMessage(error: unknown): string {
  if (error instanceof ChatApiError) {
    return error.message;
  }
  return "The message could not be sent safely. Please try again.";
}

export function useChatState({
  userId,
  sendChat = defaultSendChat,
  createId = createMessageId,
  now = () => new Date().toISOString(),
}: UseChatStateOptions) {
  const [state, setState] = useState<ChatState>(EMPTY_STATE);
  const pendingRef = useRef(false);

  const submit = useCallback(
    async (message: string): Promise<ChatSubmitResult> => {
      const normalizedMessage = message.trim();
      if (!normalizedMessage || pendingRef.current) {
        return { submitted: false, succeeded: false };
      }

      pendingRef.current = true;
      const userMessage: UserChatMessage = {
        id: createId(),
        role: "user",
        content: normalizedMessage,
        created_at: now(),
      };
      setState((previous) => ({
        messages: [...previous.messages, userMessage],
        pending: true,
        error: null,
      }));

      try {
        const response = await sendChat({ user_id: userId, message: normalizedMessage });
        const assistantMessage: AssistantChatMessage = {
          id: createId(),
          role: "assistant",
          content: response.response,
          sources: response.sources,
          tool_calls: response.tool_calls,
          created_at: now(),
        };
        setState((previous) => ({
          messages: [...previous.messages, assistantMessage],
          pending: false,
          error: null,
        }));
        pendingRef.current = false;
        return { submitted: true, succeeded: true, response };
      } catch (error) {
        setState((previous) => ({
          ...previous,
          pending: false,
          error: safeErrorMessage(error),
        }));
        pendingRef.current = false;
        return { submitted: true, succeeded: false };
      }
    },
    [createId, now, sendChat, userId],
  );

  const clearError = useCallback(() => {
    setState((previous) => ({ ...previous, error: null }));
  }, []);

  const reset = useCallback(() => {
    pendingRef.current = false;
    setState(EMPTY_STATE);
  }, []);

  return {
    ...state,
    submit,
    clearError,
    reset,
  };
}
