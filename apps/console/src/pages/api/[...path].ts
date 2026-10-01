import type { APIRoute } from "astro";
import { forward } from "../../server/bff";
export const ALL: APIRoute = ({ request, params, locals }) =>
  forward(request, `${params.path}/`, locals);
