import type {
  AnalyzeRequest,
  AnalyzeResponse,
  ErrorResponse,
  GradeRequest,
  GradeResponse
} from './contracts.js';

export type PythonProxyConfig = {
  baseUrl: string;
  timeoutMs: number;
};

export async function proxyAnalyzeToPython(cfg: PythonProxyConfig, payload: AnalyzeRequest): Promise<AnalyzeResponse> {
  const url = new URL('/v1/analyze', cfg.baseUrl).toString();

  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), cfg.timeoutMs);

  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'content-type': 'application/json'
      },
      body: JSON.stringify(payload),
      signal: controller.signal
    });

    const text = await resp.text();

    if (!resp.ok) {
      // Python API returns ErrorResponse envelopes. Bubble them up as-is when possible.
      try {
        const err = JSON.parse(text) as ErrorResponse;
        throw Object.assign(new Error(err.error_message ?? 'Python proxy error'), { status: resp.status, err });
      } catch {
        throw Object.assign(new Error('Python proxy error'), { status: resp.status, err: text });
      }
    }

    return JSON.parse(text) as AnalyzeResponse;
  } finally {
    clearTimeout(t);
  }
}

export async function proxyGradeToPython(cfg: PythonProxyConfig, payload: GradeRequest): Promise<GradeResponse> {
  const url = new URL('/v1/grade', cfg.baseUrl).toString();

  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), cfg.timeoutMs);

  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'content-type': 'application/json'
      },
      body: JSON.stringify(payload),
      signal: controller.signal
    });

    const text = await resp.text();

    if (!resp.ok) {
      try {
        const err = JSON.parse(text) as ErrorResponse;
        throw Object.assign(new Error(err.error_message ?? 'Python proxy error'), { status: resp.status, err });
      } catch {
        throw Object.assign(new Error('Python proxy error'), { status: resp.status, err: text });
      }
    }

    return JSON.parse(text) as GradeResponse;
  } finally {
    clearTimeout(t);
  }
}
