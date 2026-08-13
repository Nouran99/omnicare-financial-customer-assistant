import { NextResponse } from "next/server";

const SAFE_PROXY_ERROR = "The assistant is temporarily unavailable. Please try again later.";

export const runtime = "nodejs";

function backendChatUrl(): string | null {
  const origin = process.env.BACKEND_ORIGIN?.trim();
  if (!origin) {
    return null;
  }

  try {
    return new URL("/api/v1/chat", origin).toString();
  } catch {
    return null;
  }
}

export async function POST(request: Request): Promise<Response> {
  const target = backendChatUrl();
  if (!target) {
    return NextResponse.json(
      { error: "provider_unavailable", detail: SAFE_PROXY_ERROR },
      { status: 503 },
    );
  }

  let body: string;
  try {
    body = await request.text();
  } catch {
    return NextResponse.json(
      { error: "invalid_request", detail: "The request could not be read safely." },
      { status: 400 },
    );
  }

  try {
    const upstream = await fetch(target, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      cache: "no-store",
    });
    const contentType = upstream.headers.get("content-type") ?? "application/json";
    return new Response(await upstream.arrayBuffer(), {
      status: upstream.status,
      headers: { "Content-Type": contentType },
    });
  } catch {
    return NextResponse.json(
      { error: "provider_unavailable", detail: SAFE_PROXY_ERROR },
      { status: 503 },
    );
  }
}
