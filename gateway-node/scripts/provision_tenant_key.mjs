#!/usr/bin/env node
/**
 * Provision a tenant + API key in Supabase.
 *
 * Requires:
 *   SUPABASE_URL
 *   SUPABASE_SERVICE_ROLE_KEY
 *   PREGRADE_API_KEY_HASH_SALT
 *
 * Usage:
 *   node scripts/provision_tenant_key.mjs --tenant "Acme Portfolio" --key-name "acme-dev" --prefix "pg_test_"
 */

import crypto from 'node:crypto';
import process from 'node:process';
import { createClient } from '@supabase/supabase-js';

function env(name) {
  const v = (process.env[name] ?? '').trim();
  return v.length ? v : null;
}

function parseArgs(argv) {
  const out = {};
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith('--')) continue;
    const k = a.slice(2);
    const v = argv[i + 1];
    out[k] = v;
    i++;
  }
  return out;
}

function randomApiKey(prefix) {
  // 32 bytes => 64 hex chars. Reasonable entropy.
  const token = crypto.randomBytes(32).toString('hex');
  return `${prefix}${token}`;
}

function hashApiKey(apiKey, salt) {
  return crypto.createHash('sha256').update(`${salt}:${apiKey}`).digest('hex');
}

async function main() {
  const args = parseArgs(process.argv);
  const tenantName = args['tenant'] ?? 'Default Tenant';
  const keyName = args['key-name'] ?? 'default';
  const prefix = args['prefix'] ?? 'pg_live_';

  const supabaseUrl = env('SUPABASE_URL');
  const serviceKey = env('SUPABASE_SERVICE_ROLE_KEY');
  const salt = env('PREGRADE_API_KEY_HASH_SALT');

  if (!supabaseUrl || !serviceKey || !salt) {
    console.error('Missing required env vars: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, PREGRADE_API_KEY_HASH_SALT');
    process.exit(2);
  }

  const supabase = createClient(supabaseUrl, serviceKey, {
    auth: { persistSession: false, autoRefreshToken: false }
  });

  // 1) Create tenant
  const { data: tenant, error: tenantErr } = await supabase
    .from('tenants')
    .insert({ name: tenantName })
    .select('id, name')
    .single();

  if (tenantErr) {
    console.error('Failed to create tenant:', tenantErr);
    process.exit(1);
  }

  // 2) Create key
  const apiKey = randomApiKey(prefix);
  const keyHash = hashApiKey(apiKey, salt);

  const { data: apiKeyRow, error: keyErr } = await supabase
    .from('api_keys')
    .insert({ tenant_id: tenant.id, name: keyName, key_hash: keyHash })
    .select('id, tenant_id, name, created_at')
    .single();

  if (keyErr) {
    console.error('Failed to create api key row:', keyErr);
    process.exit(1);
  }

  console.log('--- Provisioned ---');
  console.log('tenant_id:', tenant.id);
  console.log('tenant_name:', tenant.name);
  console.log('api_key_id:', apiKeyRow.id);
  console.log('api_key_name:', apiKeyRow.name);
  console.log('api_key (PLAINTEXT - store this now, it cannot be recovered):');
  console.log(apiKey);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
