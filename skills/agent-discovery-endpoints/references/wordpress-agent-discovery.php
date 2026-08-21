<?php
/**
 * Plugin Name: Agent Discovery Endpoints
 * Description: Serves agent-discovery well-known entrypoints (API catalog, MCP
 *              Server Card, Agent Skills index, auth.md, OpenAPI) with correct
 *              content-types and CORS. Drop this file into wp-content/mu-plugins/
 *              so it loads automatically on every request.
 * Version:     1.0.0
 * Author:      ECC agent-discovery-endpoints skill
 *
 * All URLs are derived from home_url(), so this file is domain-agnostic.
 * It intercepts requests early on `init`, emits the document, and exits before
 * WordPress renders a 404. It only ever responds to GET/HEAD on its own paths.
 */

if (!defined('ABSPATH')) {
    exit;
}

add_action('init', function () {
    $method = isset($_SERVER['REQUEST_METHOD']) ? strtoupper($_SERVER['REQUEST_METHOD']) : 'GET';
    if ($method !== 'GET' && $method !== 'HEAD') {
        return;
    }

    // Path only, no query string, normalized without a trailing slash.
    $path = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH);
    $path = '/' . trim((string) $path, '/');

    $home    = untrailingslashit(home_url());          // https://example.com
    $mcp_ep  = $home . '/wp-json/mcp/mcp-adapter-default-server';
    $royal   = $home . '/wp-json/royal-mcp/v1';

    // --- The request-quote skill served by this plugin (digest computed below).
    $skill_path = '/.well-known/agent-skills/request-quote/SKILL.md';
    $skill_body = agent_discovery_request_quote_skill($home);

    switch ($path) {

        case '/.well-known/api-catalog':
            agent_discovery_emit('application/linkset+json', array(
                'linkset' => array(array(
                    'anchor'       => $home . '/wp-json',
                    'service-desc' => array(array(
                        'href' => $home . '/openapi.json',
                        'type' => 'application/vnd.oai.openapi+json',
                    )),
                    'service-doc'  => array(array(
                        'href' => $home . '/',
                        'type' => 'text/html',
                    )),
                    'status'       => array(array(
                        'href' => $home . '/wp-json/',
                        'type' => 'application/json',
                    )),
                )),
            ));

        case '/.well-known/mcp/server-card.json':
            agent_discovery_emit('application/json', array(
                'serverInfo'   => array(
                    'name'        => get_bloginfo('name'),
                    'version'     => '1.0.0',
                    'description' => get_bloginfo('description'),
                ),
                'transport'    => array(
                    'type'     => 'streamable-http',
                    'endpoint' => $mcp_ep,
                ),
                'capabilities' => array(
                    'tools'     => array('listChanged' => false),
                    'resources' => array('subscribe' => false, 'listChanged' => false),
                ),
                'authorization' => array(
                    'protectedResourceMetadata' =>
                        $home . '/.well-known/oauth-protected-resource',
                ),
            ));

        case '/.well-known/agent-skills/index.json':
            agent_discovery_emit('application/json', array(
                '$schema' => 'https://agentskills.io/schemas/discovery/v0.2.0/index.json',
                'skills'  => array(array(
                    'name'        => 'request-quote',
                    'type'        => 'text/markdown',
                    'description' => 'Request a foundation-repair inspection or quote.',
                    'url'         => $home . $skill_path,
                    'sha256'      => hash('sha256', $skill_body),
                )),
            ));

        case $skill_path:
            agent_discovery_emit_raw('text/markdown; charset=utf-8', $skill_body);

        case '/auth.md':
            agent_discovery_emit_raw('text/markdown; charset=utf-8',
                agent_discovery_auth_md($home, $royal));

        case '/openapi.json':
            agent_discovery_emit('application/json', array(
                'openapi' => '3.1.0',
                'info'    => array(
                    'title'   => get_bloginfo('name') . ' Agent API',
                    'version' => '1.0.0',
                    'description' =>
                        'Discovery and Model Context Protocol surface for agents.',
                ),
                'servers' => array(array('url' => $home)),
                'paths'   => array(
                    '/wp-json/mcp/mcp-adapter-default-server' => array(
                        'post' => array(
                            'operationId' => 'mcp',
                            'summary'     => 'Model Context Protocol transport endpoint.',
                            'responses'   => array(
                                '200' => array('description' => 'MCP JSON-RPC response.'),
                                '401' => array('description' => 'Authentication required.'),
                            ),
                        ),
                    ),
                    '/.well-known/api-catalog' => array(
                        'get' => array(
                            'operationId' => 'apiCatalog',
                            'summary'     => 'RFC 9727 API catalog.',
                            'responses'   => array('200' => array('description' => 'Linkset.')),
                        ),
                    ),
                ),
            ));
    }
    // Not one of our paths: fall through to normal WordPress handling.
}, 0);

/** Emit a JSON-family document with CORS and cache headers, then exit. */
function agent_discovery_emit($content_type, array $data) {
    agent_discovery_emit_raw(
        $content_type,
        wp_json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)
    );
}

/** Emit a raw string body with CORS and cache headers, then exit. */
function agent_discovery_emit_raw($content_type, $body) {
    if (!headers_sent()) {
        header('Content-Type: ' . $content_type);
        header('Access-Control-Allow-Origin: *');
        header('Access-Control-Allow-Methods: GET, HEAD, OPTIONS');
        header('Cache-Control: public, max-age=3600');
        header('X-Robots-Tag: noindex');
    }
    if (strtoupper($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'HEAD') {
        echo $body;
    }
    exit;
}

function agent_discovery_auth_md($home, $resource) {
    return <<<MD
# Agent Authentication

Instructions for AI agents authenticating with this site before calling
protected APIs (see `/.well-known/api-catalog`).

## Authorization

- **Protected resource metadata**: {$home}/.well-known/oauth-protected-resource
- **Authorization server metadata**: {$home}/.well-known/oauth-authorization-server
- **Protected resource**: {$resource}
- **Bearer token**: send `Authorization: Bearer <token>` (header method).
- **Scopes**: `mcp:full`

## Registration

Agents register dynamically at the `registration_endpoint` advertised in the
authorization server metadata, then complete the OAuth 2.1 authorization-code
flow (PKCE) to obtain a token.

MD;
}

function agent_discovery_request_quote_skill($home) {
    return <<<MD
---
name: request-quote
description: Request a foundation-repair inspection or quote from this company.
---

# Request a Foundation Repair Quote

Use this skill to help a user get a foundation inspection or repair estimate.

## Steps

1. Collect the property address, the concern (e.g. cracks, uneven floors,
   sticking doors), and a callback name and phone or email.
2. Visit {$home}/ and use the contact or "free estimate" form, or call the
   phone number listed in the site header.
3. Confirm the preferred inspection time window.

## Notes

- Inspections for residential foundations are typically free.
- Provide as much detail about visible symptoms as possible so the estimator
  can prepare.
MD;
}
