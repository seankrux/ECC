# Threat model — LeadSnap Heatmaps API adapter

A short, honest boundary statement. This adapter is a thin HTTP client for a
**third-party SaaS**. Read this before wiring it into an agent that acts on the
data it returns.

## What this adapter is

- A stdlib-only wrapper over the LeadSnap public API. It makes authenticated
  HTTPS requests and returns parsed JSON.
- Auth is a **personal Sanctum bearer token** scoped to one LeadSnap account.
  It grants the same read/write reach that token has in the LeadSnap UI.

## Trust boundaries

| # | Concern | Mitigation in this adapter | Residual risk owned by caller |
|---|---|---|---|
| 1 | **Token secrecy** | Token is read from `LEADSNAP_API_TOKEN`, never hardcoded, logged, or placed in exception messages (a test asserts this). | Keep the env var out of shell history, CI logs, and commits. Rotate at `account/settings/api-tokens` if exposed. |
| 2 | **Token scope / blast radius** | Adapter defaults to read calls; writes are explicit named methods. | The token itself is not read-only — anyone holding it can create/modify heatmaps and schedules (billable). Treat it as a secret credential. |
| 3 | **Untrusted response data** | Responses are business names, addresses, phone numbers, websites and Google Place data — treat as **untrusted external content**. The adapter does not execute or interpret it. | Sanitize/validate before rendering into prompts, shells, HTML, or downstream tool calls (per repo prompt-defense baseline). |
| 4 | **Transport failure / timeout** | Non-2xx and transport errors raise `LeadSnapError` (with `.status`/`.body`) — never a silent partial result. Default timeout 30s. | Decide retry/backoff policy; a failed write may or may not have been applied server-side (see #6). |
| 5 | **Auth failure** | 401/403 raise `LeadSnapAuthError` distinctly so callers can detect a bad/expired token vs a generic error. | Do not retry auth failures blindly. |
| 6 | **Write side effects & cost** | `create_heatmap` / `create_schedule` queue real, potentially **billable** jobs. They are never called implicitly. | Gate writes behind explicit user intent; be aware a timeout after a POST does not guarantee the job was not created. |
| 7 | **PII handling** | Heatmap/contact data can include personal and business contact details. | Store and forward it in line with your own data-handling and privacy obligations; the adapter neither persists nor caches anything. |

## What it explicitly does NOT do

- **No caching or persistence.** Every call hits the API; nothing is written to
  disk.
- **No rate-limit handling.** If LeadSnap throttles (e.g. HTTP 429), the call
  raises `LeadSnapError` — implement backoff yourself.
- **No schema guarantees.** The API is Beta; fields may change. The client
  returns raw dicts (plus a typed pagination `Page`) rather than freezing a
  schema, and keeps the untouched body on `Page.raw`.
- **No credential management.** It reads one env var; it does not fetch, rotate,
  or store tokens.
