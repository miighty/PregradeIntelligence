export default async function handler() {
  return new Response(JSON.stringify({ ok: true, service: "pregrade-api", version: "stub" }), {
    status: 200,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}
