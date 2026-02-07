import { createClient } from '@supabase/supabase-js';

function env(name: string): string | null {
  const v = (process.env[name] ?? '').trim();
  return v.length ? v : null;
}

export async function logUsage(evt: {
  tenantId?: string;
  apiKeyId?: string;
  requestId?: string;
  route: string;
  statusCode: number;
  durationMs?: number;
  gatekeeperAccepted?: boolean | null;
  reasonCodes?: string[] | null;
}) {
  const url = env('SUPABASE_URL');
  const serviceKey = env('SUPABASE_SERVICE_ROLE_KEY');
  if (!url || !serviceKey) return; // noop if not configured

  const supabase = createClient(url, serviceKey, {
    auth: { persistSession: false, autoRefreshToken: false }
  });

  await supabase.from('usage_events').insert({
    tenant_id: evt.tenantId ?? null,
    api_key_id: evt.apiKeyId ?? null,
    request_id: evt.requestId ?? null,
    route: evt.route,
    status_code: evt.statusCode,
    gatekeeper_accepted: evt.gatekeeperAccepted ?? null,
    reason_codes: evt.reasonCodes ?? null,
    duration_ms: evt.durationMs ?? null
  });
}
