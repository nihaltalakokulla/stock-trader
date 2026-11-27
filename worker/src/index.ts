type Env = {
  TWILIO_AUTH_TOKEN: string;
  ALLOWED_PHONE: string;
  SUPABASE_URL: string;
  SUPABASE_SERVICE_KEY: string;
  GITHUB_DISPATCH_TOKEN: string;
  GITHUB_OWNER: string;
  GITHUB_REPO: string;
  GITHUB_REF: string;
  GITHUB_WORKFLOW_FILE?: string;
};

export function parseReply(body: string): "YES" | "NO" | "STOP" | "UNKNOWN" {
  const normalized = body.trim().toUpperCase();
  if (normalized === "YES" || normalized === "NO" || normalized === "STOP") {
    return normalized;
  }
  return "UNKNOWN";
}

function constantTimeEqual(left: string, right: string): boolean {
  const length = Math.max(left.length, right.length);
  let diff = left.length ^ right.length;
  for (let i = 0; i < length; i++) {
    diff |= (left.charCodeAt(i) || 0) ^ (right.charCodeAt(i) || 0);
  }
  return diff === 0;
}

export async function verifyTwilioSignature(
  authToken: string,
  signature: string,
  url: string,
  params: Record<string, string>,
): Promise<boolean> {
  const payload = Object.keys(params)
    .sort()
    .reduce((acc, key) => acc + key + params[key], url);
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(authToken),
    { name: "HMAC", hash: "SHA-1" },
    false,
    ["sign"],
  );
  const digest = await crypto.subtle.sign("HMAC", key, encoder.encode(payload));
  const computed = btoa(String.fromCharCode(...new Uint8Array(digest)));
  return constantTimeEqual(computed, signature);
}

function twiml(message?: string): Response {
  const body = message
    ? `<Response><Message>${message}</Message></Response>`
    : "<Response></Response>";
  return new Response(`<?xml version="1.0" encoding="UTF-8"?>${body}`, {
    headers: { "content-type": "text/xml; charset=utf-8" },
  });
}

function supabaseHeaders(env: Env, extra: Record<string, string> = {}) {
  return {
    apikey: env.SUPABASE_SERVICE_KEY,
    authorization: `Bearer ${env.SUPABASE_SERVICE_KEY}`,
    "content-type": "application/json",
    ...extra,
  };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (request.method !== "POST" || url.pathname !== "/sms-webhook") {
      return new Response("Not found", { status: 404 });
    }

    const form = await request.formData();
    const params: Record<string, string> = {};
    for (const [key, value] of form.entries()) {
      params[key] = String(value);
    }

    const signature = request.headers.get("x-twilio-signature") ?? "";
    if (!(await verifyTwilioSignature(env.TWILIO_AUTH_TOKEN, signature, request.url, params))) {
      return new Response("Invalid signature", { status: 403 });
    }
    if (params.From !== env.ALLOWED_PHONE) {
      return new Response("Unknown sender", { status: 403 });
    }

    const decision = parseReply(params.Body ?? "");
    if (decision === "UNKNOWN") {
      return twiml("Reply YES, NO, or STOP.");
    }

    if (decision === "STOP") {
      const response = await fetch(`${env.SUPABASE_URL}/rest/v1/settings`, {
        method: "POST",
        headers: supabaseHeaders(env, { prefer: "resolution=merge-duplicates" }),
        body: JSON.stringify({ key: "trading_paused", value: true }),
      });
      if (!response.ok) {
        return twiml("Could not pause trading. Check the dashboard.");
      }
      return twiml("Trading paused. Reply from the dashboard to resume.");
    }

    const pendingResponse = await fetch(
      `${env.SUPABASE_URL}/rest/v1/proposals?select=id,expires_at&state=eq.PROPOSED&order=created_at.desc&limit=1`,
      { headers: supabaseHeaders(env) },
    );
    if (!pendingResponse.ok) {
      return twiml("Could not read the pending proposal. Check the dashboard.");
    }
    const pending = (await pendingResponse.json()) as Array<{
      id: string;
      expires_at: string;
    }>;
    if (pending.length === 0) {
      return twiml("No pending proposal.");
    }
    if (Date.now() >= Date.parse(pending[0].expires_at)) {
      return twiml("That proposal has expired.");
    }

    const proposalId = pending[0].id;
    const key = `approval:${proposalId}:${decision}`;
    const insert = await fetch(`${env.SUPABASE_URL}/rest/v1/approvals`, {
      method: "POST",
      headers: supabaseHeaders(env, { prefer: "resolution=ignore-duplicates" }),
      body: JSON.stringify({
        proposal_id: proposalId,
        decision,
        idempotency_key: key,
        source_number: params.From,
      }),
    });
    if (!insert.ok && insert.status !== 409) {
      return twiml("Could not record your reply. Check the dashboard.");
    }

    await fetch(`${env.SUPABASE_URL}/rest/v1/proposals?id=eq.${proposalId}`, {
      method: "PATCH",
      headers: supabaseHeaders(env, { prefer: "return=minimal" }),
      body: JSON.stringify({
        state: decision === "YES" ? "APPROVED" : "REJECTED",
      }),
    });

    if (decision === "YES") {
      const workflow = env.GITHUB_WORKFLOW_FILE ?? "execute.yml";
      const dispatch = await fetch(
        `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/actions/workflows/${workflow}/dispatches`,
        {
          method: "POST",
          headers: {
            authorization: `Bearer ${env.GITHUB_DISPATCH_TOKEN}`,
            accept: "application/vnd.github+json",
            "content-type": "application/json",
            "user-agent": "stock-trader-worker",
          },
          body: JSON.stringify({
            ref: env.GITHUB_REF,
            inputs: { approval_key: key },
          }),
        },
      );
      if (!dispatch.ok) {
        return twiml("Approved, but execution dispatch failed. Check the dashboard.");
      }
      return twiml("Approved. Executing at the next available market price.");
    }

    return twiml("Skipped.");
  },
};
