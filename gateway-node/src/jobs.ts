import { createClient } from '@supabase/supabase-js';
import type { AnalyzeRequest, JobStatus } from './contracts.js';
import { proxyAnalyzeToPython } from './pythonProxy.js';

function env(name: string): string | null {
  const v = (process.env[name] ?? '').trim();
  return v.length ? v : null;
}

function getSupabase() {
  const url = env('SUPABASE_URL');
  const key = env('SUPABASE_SERVICE_ROLE_KEY');
  if (!url || !key) return null;
  return createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false }
  });
}

export type CreateJobOptions = {
  tenantId?: string | null;
  requestPayload: AnalyzeRequest;
};

export async function createJob(options: CreateJobOptions): Promise<{ jobId: string } | { error: string }> {
  const supabase = getSupabase();
  if (!supabase) {
    return { error: 'Jobs not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.' };
  }

  const { data, error } = await supabase
    .from('jobs')
    .insert({
      tenant_id: options.tenantId ?? null,
      status: 'pending',
      request_payload: options.requestPayload as unknown as Record<string, unknown>
    })
    .select('id')
    .single();

  if (error || !data) {
    return { error: error?.message ?? 'Failed to create job.' };
  }

  return { jobId: data.id };
}

export async function getJob(
  jobId: string,
  tenantId?: string | null
): Promise<
  | { status: JobStatus; result: Record<string, unknown> | null; error: string | null; created_at: string; completed_at: string | null }
  | { error: string }
> {
  const supabase = getSupabase();
  if (!supabase) {
    return { error: 'Jobs not configured.' };
  }

  let query = supabase.from('jobs').select('status, result, error, created_at, completed_at').eq('id', jobId).limit(1);

  if (tenantId != null && tenantId !== 'anonymous') {
    query = query.or(`tenant_id.is.null,tenant_id.eq.${tenantId}`);
  }

  const { data, error } = await query.maybeSingle();

  if (error) return { error: error.message };
  if (!data) return { error: 'Job not found.' };

  return {
    status: data.status as JobStatus,
    result: data.result as Record<string, unknown> | null,
    error: data.error as string | null,
    created_at: data.created_at,
    completed_at: data.completed_at
  };
}

async function updateJob(
  jobId: string,
  updates: { status: JobStatus; result?: Record<string, unknown> | null; error?: string | null; completed_at?: string | null }
): Promise<void> {
  const supabase = getSupabase();
  if (!supabase) return;

  await supabase.from('jobs').update(updates).eq('id', jobId);
}

export function runJobInBackground(jobId: string): void {
  setImmediate(async () => {
    const supabase = getSupabase();
    if (!supabase) return;

    const { data: row } = await supabase.from('jobs').select('request_payload').eq('id', jobId).limit(1).maybeSingle();
    if (!row || !row.request_payload) return;

    await updateJob(jobId, { status: 'processing' });

    const baseUrl = env('PREGRADE_PYTHON_BASE_URL');
    const timeoutMs = Number.parseInt(process.env.PREGRADE_PYTHON_TIMEOUT_MS ?? '120000', 10) || 120_000;

    if (!baseUrl) {
      await updateJob(jobId, {
        status: 'failed',
        error: 'Python service not configured.',
        completed_at: new Date().toISOString()
      });
      return;
    }

    try {
      const payload = row.request_payload as AnalyzeRequest;
      const resp = await proxyAnalyzeToPython({ baseUrl, timeoutMs }, payload);
      await updateJob(jobId, {
        status: 'completed',
        result: resp.result as Record<string, unknown>,
        completed_at: new Date().toISOString()
      });
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Analysis failed.';
      await updateJob(jobId, {
        status: 'failed',
        error: message,
        completed_at: new Date().toISOString()
      });
    }
  });
}
