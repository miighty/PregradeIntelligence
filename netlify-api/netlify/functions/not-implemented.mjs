export default async function handler(request) {
  const url = new URL(request.url);
  return new Response(
    JSON.stringify({
      ok: false,
      error: "NOT_IMPLEMENTED",
      path: url.pathname,
      message: "API gateway is not deployed yet; this is a placeholder endpoint.",
    }),
    {
      status: 501,
      headers: {
        "content-type": "application/json; charset=utf-8",
        "cache-control": "no-store",
      },
    }
  );
}
