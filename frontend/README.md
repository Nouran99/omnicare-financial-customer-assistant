# OmniCare frontend

The frontend uses one typed `sendChat` client for text and voice-transcript submissions. It calls the same-origin `/api/v1/chat` route and never contacts DeepSeek directly.

The Next.js route handler forwards requests server-side to the backend origin from `BACKEND_ORIGIN`. In Docker Compose this is set to `http://backend:8000`. For local frontend development, start the frontend with `BACKEND_ORIGIN=http://localhost:8000 pnpm dev` while the FastAPI backend is running on port 8000.

`BACKEND_ORIGIN` is intentionally server-only. It is not prefixed with `NEXT_PUBLIC_`, and no provider credential is accepted or stored in frontend environment variables.

## Verification

Run `pnpm test` for mocked-fetch client tests, `pnpm typecheck` for the TypeScript contract, `pnpm lint` for static checks, and `pnpm build` for the production Next.js build.
