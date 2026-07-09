# Agent Authentication

This document tells autonomous agents how to register and authenticate with
Example before calling protected APIs. Serve it at `https://example.com/auth.md`.

## Registration

Agents register a client via dynamic client registration:

- **register_uri**: `https://auth.example.com/oauth/register`
- **Supported identity types**: `service_account`, `delegated_user`
- **Supported credential types**: `client_secret`, `private_key_jwt`

## Authorization

- **Authorization server**: `https://auth.example.com`
- **Metadata**: `https://example.com/.well-known/oauth-authorization-server`
- **Protected resource metadata**:
  `https://example.com/.well-known/oauth-protected-resource`
- **Scopes**: `catalog.read`, `orders.write`

## Claims & revocation

- **Claim URL**: `https://auth.example.com/claims`
- **Revocation URL**: `https://auth.example.com/oauth/revoke`

Obtain a token with the `client_credentials` grant, then send
`Authorization: Bearer <token>` to the protected API described in
`/.well-known/api-catalog`.
