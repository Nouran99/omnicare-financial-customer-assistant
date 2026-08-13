export interface ChatRequest {
  user_id: string;
  message: string;
}

export interface ToolCallSummary {
  name: string;
  status: string;
  arguments?: string | null;
  result_summary?: string | null;
}

export interface ChatResponse {
  response: string;
  sources: string[];
  tool_calls: ToolCallSummary[];
}

export interface ErrorResponse {
  error: string;
  detail: string;
  request_id?: string | null;
}

export type ChatApiErrorKind =
  | "http"
  | "malformed_response"
  | "network"
  | "aborted";

export class ChatApiError extends Error {
  readonly kind: ChatApiErrorKind;
  readonly status?: number;
  readonly requestId?: string;

  constructor(
    kind: ChatApiErrorKind,
    message: string,
    options: { status?: number; requestId?: string } = {},
  ) {
    super(message);
    this.name = "ChatApiError";
    this.kind = kind;
    this.status = options.status;
    this.requestId = options.requestId;
  }
}

const CHAT_ENDPOINT = "/api/v1/chat";

const SAFE_ERROR_MESSAGES: Record<number, string> = {
  400: "The request could not be understood.",
  422: "Please check the message and try again.",
  502: "The assistant is temporarily unavailable. Please try again later.",
  503: "The assistant is temporarily unavailable. Please try again later.",
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isOptionalString(value: unknown): value is string | null | undefined {
  return value === undefined || value === null || typeof value === "string";
}

function isToolCallSummary(value: unknown): value is ToolCallSummary {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.name === "string" &&
    typeof value.status === "string" &&
    isOptionalString(value.arguments) &&
    isOptionalString(value.result_summary)
  );
}

function isChatResponse(value: unknown): value is ChatResponse {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.response === "string" &&
    Array.isArray(value.sources) &&
    value.sources.every((source) => typeof source === "string") &&
    Array.isArray(value.tool_calls) &&
    value.tool_calls.every(isToolCallSummary)
  );
}

function isErrorResponse(value: unknown): value is ErrorResponse {
  return (
    isRecord(value) &&
    typeof value.error === "string" &&
    typeof value.detail === "string" &&
    (value.request_id === undefined ||
      value.request_id === null ||
      typeof value.request_id === "string")
  );
}

function safeHttpMessage(status: number): string {
  return SAFE_ERROR_MESSAGES[status] ?? "The request could not be completed safely.";
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    throw new ChatApiError(
      "malformed_response",
      "The assistant returned an invalid response.",
      { status: response.status },
    );
  }
}

export async function sendChat(
  input: ChatRequest,
  options: { signal?: AbortSignal } = {},
): Promise<ChatResponse> {
  let response: Response;
  try {
    response = await fetch(CHAT_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
      signal: options.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ChatApiError("aborted", "The request was cancelled.");
    }
    throw new ChatApiError(
      "network",
      "The assistant could not be reached. Please check your connection and try again.",
    );
  }

  const payload = await readJson(response);
  if (!response.ok) {
    const requestId = isErrorResponse(payload) ? payload.request_id ?? undefined : undefined;
    throw new ChatApiError("http", safeHttpMessage(response.status), {
      status: response.status,
      requestId,
    });
  }

  if (!isChatResponse(payload)) {
    throw new ChatApiError(
      "malformed_response",
      "The assistant returned an invalid response.",
      { status: response.status },
    );
  }

  return payload;
}
