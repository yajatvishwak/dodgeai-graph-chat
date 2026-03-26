import { env } from "$env/dynamic/private";
import type { RequestHandler } from "./$types";

const BACKEND = env.API_BACKEND_URL ?? "http://localhost:8000";

export const GET: RequestHandler = async ({ url }) => {
  const limit = url.searchParams.get("limit") ?? "120";
  const res = await fetch(`${BACKEND}/api/graph?limit=${limit}`);
  return new Response(res.body, {
    status: res.status,
    headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
  });
};
