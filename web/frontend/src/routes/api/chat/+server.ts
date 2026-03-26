import { env } from "$env/dynamic/private";
import type { RequestHandler } from "./$types";

const BACKEND = env.API_BACKEND_URL ?? "http://localhost:8000";

export const POST: RequestHandler = async ({ request }) => {
  const body = await request.text();
  const res = await fetch(`${BACKEND}/api/chat`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body,
  });
  return new Response(res.body, {
    status: res.status,
    headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
  });
};
