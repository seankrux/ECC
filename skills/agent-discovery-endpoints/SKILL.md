---
name: agent-discovery-endpoints
description: Publish the well-known entrypoints that let AI agents discover a site's capabilities, auth, and tools — DNS-AID records, an RFC 9727 API catalog, auth.md, an MCP Server Card, an Agent Skills index, WebMCP tools, and MPP payment metadata. Use when preparing a site to be "agent-ready" or remediating a low agent-readiness scan.
metadata:
  origin: ECC
---

# Agent Discovery Endpoints

Make a site discoverable and usable by AI agents by publishing the emerging
well-known entrypoints agents probe for. Each mechanism is independent — publish
the ones that fit the site, verify each in isolation, and prefer standards-track
formats over ad-hoc JSON.

## When to Use

Use this skill when:

- an agent-readiness audit reports missing discovery entrypoints (e.g. "API
  Catalog not found", "MCP Server Card not found", "auth.md not found")
- preparing a site or API so autonomous agents can find its content, tools,
  authentication flow, and payment surfaces
- adding machine-readable capability discovery alongside human-facing pages

Each item below is self-contained. Do only what applies — a static content site
needs Discoverability and Content mechanisms, not MPP or WebMCP.

## How It Works

### Principles

1. Serve every well-known file from the exact path agents probe; a 404 reads as
   "unsupported".
2. Return the correct `Content-Type` (e.g. `application/linkset+json`,
   `application/json`) — agents content-negotiate.
3. Keep discovery documents small, cacheable, and CORS-readable
   (`Access-Control-Allow-Origin` for cross-origin agent fetches).
4. Sign and integrity-check where the standard allows (DNSSEC for DNS-AID,
   `sha256` digests for skills) so validating clients get authenticated data.
5. Reference, don't duplicate — link an OpenAPI spec once and point catalogs at
   it rather than copying the surface into every document.

### The seven mechanisms

Templates for each live in `references/`. Copy, then fill in real values.

#### 1. DNS-AID (DNS for AI Discovery)

Publish well-known discovery records under `_agents.<domain>` using ServiceMode
SVCB/HTTPS records with `alpn` and endpoint parameters, e.g.
`_index._agents.example.com` or `_a2a._agents.example.com`. Sign the discovery
zone with DNSSEC so validating resolvers return authenticated data. See
`references/dns-aid.zone` for record examples.
Spec: draft-mozleywilliams-dnsop-dnsaid, RFC 9460 (SVCB/HTTPS).

#### 2. API Catalog (RFC 9727)

Serve `/.well-known/api-catalog` as `application/linkset+json` with a `linkset`
array. Each entry has an `anchor` (the API URL) and link relations
`service-desc` (OpenAPI spec), `service-doc` (docs), and `status` (health). See
`references/api-catalog.json`. Spec: RFC 9727, RFC 9264 (linkset).

#### 3. auth.md (agent registration)

Serve `/auth.md` at the site root with human- and agent-readable registration
instructions, plus `/.well-known/oauth-protected-resource` and an `agent_auth`
block in `/.well-known/oauth-authorization-server` (register_uri, supported
identity and credential types, claim/revocation URLs). See `references/auth.md`,
`references/oauth-protected-resource.json`,
`references/oauth-authorization-server.json`. Spec: workos.com/auth.md.

#### 4. MCP Server Card (SEP-1649)

Serve `/.well-known/mcp/server-card.json` with `serverInfo` (name, version), the
transport endpoint, and `capabilities`. See `references/server-card.json`.
Spec: modelcontextprotocol PR #2127.

#### 5. Agent Skills index (Discovery RFC v0.2.0)

Publish `/.well-known/agent-skills/index.json` with a `$schema` field and a
`skills` array; each entry has `name`, `type`, `description`, `url`, and a
`sha256` digest of the referenced skill. See `references/agent-skills-index.json`
and `references/gen-sha256.sh`. Spec: cloudflare/agent-skills-discovery-rfc.

#### 6. WebMCP (in-browser tools)

Expose site actions to agents in the page by calling
`navigator.modelContext.provideContext()` with tool definitions — each with
`name`, `description`, `inputSchema` (JSON Schema), and an `execute` callback.
Feature-detect before calling. See `references/webmcp.js`.
Spec: webmachinelearning.github.io/webmcp.

#### 7. MPP (Machine Payment Protocol)

Publish `/openapi.json` with `x-payment-info` extensions on payable operations,
declaring `intent` (charge/session), `method` (tempo/stripe/lightning/card),
`amount`, and `currency`. Add MPP middleware (mppx / pympp) to enforce payment.
See `references/openapi-mpp.json`. Spec: mpp.dev.

### Verification

After deploying, verify each endpoint independently:

```bash
# API Catalog — expect application/linkset+json
curl -sI https://example.com/.well-known/api-catalog | grep -i content-type
curl -s  https://example.com/.well-known/api-catalog | jq '.linkset[0].anchor'

# MCP Server Card
curl -s https://example.com/.well-known/mcp/server-card.json | jq '.serverInfo'

# Agent Skills index — verify a digest matches the referenced file
curl -s https://example.com/.well-known/agent-skills/index.json | jq '.skills'

# auth.md
curl -sI https://example.com/auth.md | grep -i '200\|content-type'
curl -s https://example.com/.well-known/oauth-protected-resource | jq .

# DNS-AID — expect SVCB/HTTPS answers with DNSSEC (ad flag)
dig +dnssec _index._agents.example.com SVCB
```

WebMCP and MPP are exercised at runtime: load the page and confirm
`navigator.modelContext` is populated; call a payable operation and confirm a
`402`/payment-required negotiation.

## Examples

- **"API Catalog not found" on a scan** → copy `references/api-catalog.json`,
  point `service-desc` at the site's OpenAPI spec, serve at
  `/.well-known/api-catalog` with `Content-Type: application/linkset+json`,
  re-scan.
- **Making an MCP server discoverable** → publish
  `references/server-card.json` at `/.well-known/mcp/server-card.json` with the
  real transport endpoint and capabilities.
- **Adding agent auth** → serve `auth.md` plus the two OAuth metadata documents
  so agents can self-register before calling protected APIs.
