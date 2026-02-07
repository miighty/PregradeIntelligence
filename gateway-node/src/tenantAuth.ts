import crypto from 'node:crypto';
import { createClient } from '@supabase/supabase-js';

export type TenantAuthResult =
  | { ok: true; tenantId: string; apiKeyId: string }
  | { ok: false; reason: 'missing' | 'invalid' | 'misconfigured' };

function mustGetEnv(name: string): string | null {
  const v = (process.env[name] ?? '').trim();
  return v.length ? v : null;
}

function hashApiKey(apiKey: string): string {
  // Stable, server-side hash. API keys themselves must never be stored in plaintext.
  const salt = mustGetEnv('PREGRADE_API_KEY_HASH_SALT') ?? 'pregrade_dev_salt_change_me';
  return crypto.createHash('sha256').update(`${salt}:${apiKey}`).digest('hex');
}

export async function validateApiKey(apiKey: string): Promise<TenantAuthResult> {
  const url = mustGetEnv('SUPABASE_URL');
  const serviceKey = mustGetEnv('SUPABASE_SERVICE_ROLE_KEY');

  if (!url || !serviceKey) {
    return { ok: false, reason: 'misconfigured' };
  }

  const supabase = createClient(url, serviceKey, {
    auth: { persistSession: false, autoRefreshToken: false }
  });

  const apiKeyHash = hashApiKey(apiKey);

  const { data, error } = await supabase
    .from('api_keys')
    .select('id, tenant_id, revoked_at')
    .eq('key_hash', apiKeyHash)
    .limit(1)
    .maybeSingle();

  if (error || !data) return { ok: false, reason: 'invalid' };
  if (data.revoked_at) return { ok: false, reason: 'invalid' };

  return { ok: true, tenantId: data.tenant_id, apiKeyId: data.id };
}

export function apiKeyFromHeader(xApiKey: unknown): string | null {
  const apiKeyStr = Array.isArray(xApiKey) ? xApiKey[0] : xApiKey;
  if (typeof apiKeyStr !== 'string' || !apiKeyStr.trim()) return null;
  return apiKeyStr.trim();
}
