# API Documentation

Base URL: `http://localhost:8000/api/v1` (interactive docs at `/docs`, OpenAPI schema at `/openapi.json`).

## Auth

| Method | Path | Description |
|---|---|---|
| POST | `/auth/signup` | Create a user (email + password + full name) |
| POST | `/auth/login` | Exchange email/password for a JWT (`?email=&password=`) |
| GET | `/auth/oauth/google/authorize` | Get the Google OAuth authorization URL |
| POST | `/auth/oauth/google/callback` | Exchange an authorization code for a JWT |
| GET | `/auth/me` | Current user profile (requires `Authorization: Bearer <token>`) |

## Chat

| Method | Path | Description |
|---|---|---|
| POST | `/chat` | Send a message; routed to the right agent automatically or via `agent` override |
| POST | `/chat/stream` | Same, as a server-sent-events stream (token-by-token) |
| GET | `/chat/{conversation_id}/history` | Full message history for a conversation |

## Documents

| Method | Path | Description |
|---|---|---|
| POST | `/documents/upload` | Multipart file upload (`pdf`, `docx`, `xlsx`, `pptx`, `txt`, `md`) — OCR/chunk/embed happens synchronously |
| GET | `/documents` | List ingested documents and chunk counts |
| POST | `/documents/search` | Hybrid semantic + keyword search with metadata filters |

## Agents

| Method | Path | Description |
|---|---|---|
| GET | `/agents` | List the 6 agents with descriptions and capabilities |
| POST | `/agents/{name}/invoke` | Call a specific agent directly, bypassing the router |

## Admin (requires `admin` role)

| Method | Path | Description |
|---|---|---|
| GET | `/admin/analytics` | Active users, request volume, token usage, cost, latency, search accuracy |
| GET | `/admin/users/count` | Total registered users |

## Auth model

JWTs are HS256-signed, carry `sub` (user id) and `role`, and expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60). RBAC is enforced per-route via FastAPI dependencies (`require_admin`), not just in the frontend.
