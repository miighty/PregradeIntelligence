import fs from 'fs';
import path from 'path';

export default async function handler() {
  // The spec is copied into public/openapi.yaml at deploy time.
  const p = path.join(process.cwd(), 'public', 'openapi.yaml');
  const yaml = fs.existsSync(p)
    ? fs.readFileSync(p, 'utf8')
    : 'openapi: 3.0.0\ninfo:\n  title: PreGrade API\n  version: stub\n';

  return new Response(yaml, {
    status: 200,
    headers: {
      "content-type": "application/x-yaml; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}
