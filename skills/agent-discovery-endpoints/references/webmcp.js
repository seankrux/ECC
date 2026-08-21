// WebMCP: expose in-page site actions to AI agents running in the browser.
// Feature-detect before calling; the API is emerging and not yet universal.
// Spec: https://webmachinelearning.github.io/webmcp/
//
// Load this on pages whose actions you want agents to be able to invoke.

function registerWebMcpTools() {
  if (!('modelContext' in navigator) ||
      typeof navigator.modelContext.provideContext !== 'function') {
    return; // WebMCP unsupported in this browser — no-op.
  }

  navigator.modelContext.provideContext({
    tools: [
      {
        name: 'request_quote',
        description: 'Request a service quote for a given address and job type.',
        inputSchema: {
          type: 'object',
          properties: {
            address: { type: 'string', description: 'Service address' },
            jobType: {
              type: 'string',
              enum: ['inspection', 'repair', 'consultation'],
              description: 'Type of job requested',
            },
          },
          required: ['address', 'jobType'],
        },
        async execute({ address, jobType }) {
          const res = await fetch('/api/quotes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ address, jobType }),
          });
          if (!res.ok) {
            return { content: [{ type: 'text', text: `Request failed: ${res.status}` }] };
          }
          const quote = await res.json();
          return {
            content: [
              { type: 'text', text: `Estimated quote: ${quote.amount} ${quote.currency}` },
            ],
          };
        },
      },
    ],
  });
}

if (document.readyState !== 'loading') {
  registerWebMcpTools();
} else {
  document.addEventListener('DOMContentLoaded', registerWebMcpTools);
}
