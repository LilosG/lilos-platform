import { defineMiddleware } from "astro:middleware";
import { randomUUID } from "node:crypto";
import { config } from "./server/config";
import { requestSession } from "./server/session";
import {
  assertHost,
  cookieOptions,
  correlation,
  csrfToken,
  privateHeaders,
} from "./server/security";
export const onRequest = defineMiddleware(async (context, next) => {
  const { request, locals, cookies, url } = context;
  const finish = (response: Response) => {
    for (const [name, value] of Object.entries(privateHeaders))
      response.headers.set(name, value);
    response.headers.set("X-Correlation-ID", locals.correlationId);
    return response;
  };
  locals.correlationId = correlation(request.headers.get("x-correlation-id"));
  try {
    locals.settings = config();
    assertHost(request, locals.settings);
    locals.auth = requestSession(
      cookies,
      locals.settings,
      request.headers.get("cookie") ?? "",
    );
    locals.userId = null;
    locals.token = null;
    if (locals.auth.valid) {
      const { data, error } = await locals.auth.client.auth.getUser();
      if (!error && data.user) {
        const { data: session } = await locals.auth.client.auth.getSession();
        if (session.session?.user.id !== data.user.id)
          throw new Error("SESSION_IDENTITY_INVALID");
        locals.userId = data.user.id;
        locals.token = session.session?.access_token ?? null;
        locals.auth.flush(true);
      } else locals.auth.flush(false);
    }
    const bindingName = locals.settings.local
      ? "lilos-binding"
      : "__Host-lilos-binding";
    locals.binding = cookies.get(bindingName)?.value ?? randomUUID();
    if (!cookies.has(bindingName))
      cookies.set(
        bindingName,
        locals.binding,
        cookieOptions(locals.settings.local),
      );
    locals.csrf = csrfToken(
      locals.binding,
      locals.userId,
      locals.settings.csrfSecret,
    );
    const publicRoute =
      url.pathname === "/login/" || url.pathname.startsWith("/auth/");
    if (!publicRoute && !locals.token) {
      return finish(
        url.pathname.startsWith("/api/")
          ? new Response(JSON.stringify({ code: "AUTH_REQUIRED" }), {
              status: 401,
            })
          : context.redirect(
              `/auth/session/?return=${encodeURIComponent(url.pathname + url.search)}`,
              303,
            ),
      );
    }
    return finish(await next());
  } catch (error) {
    const code = error instanceof Error ? error.message : "CONSOLE_UNAVAILABLE";
    return finish(
      new Response(
        JSON.stringify({
          code: ["HOST_DENIED", "COOKIE_TOO_LARGE"].includes(code)
            ? code
            : "CONSOLE_UNAVAILABLE",
        }),
        {
          status:
            code === "COOKIE_TOO_LARGE"
              ? 431
              : code === "HOST_DENIED"
                ? 403
                : 503,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
  }
});
