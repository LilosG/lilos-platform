import type { APIRoute } from "astro";
import { z } from "zod";
import { assertMutation, boundedBody, safeReturn } from "../../server/security";
const actions = [
  "sign-in",
  "sign-out",
  "mfa-verify",
  "mfa-unenroll",
  "session",
];
export const ALL: APIRoute = async ({ request, params, locals, redirect }) => {
  const action = params.action ?? "";
  if (!actions.includes(action)) return new Response(null, { status: 404 });
  if (action === "session" && request.method === "GET")
    return redirect(
      locals.token
        ? safeReturn(new URL(request.url).searchParams.get("return"))
        : `/login/?return=${encodeURIComponent(safeReturn(new URL(request.url).searchParams.get("return")))}`,
      303,
    );
  if (request.method !== "POST") return new Response(null, { status: 405 });
  const client = locals.auth.client;
  try {
    if (
      request.headers.get("content-type")?.split(";", 1)[0] !==
      "application/x-www-form-urlencoded"
    )
      throw new Error("FORM_INVALID");
    const form = new URLSearchParams(await boundedBody(request, 16384));
    const get = (key: string) => form.get(key) ?? "";
    assertMutation(
      request,
      get("csrf"),
      locals.binding,
      locals.userId,
      locals.settings,
    );
    const target = safeReturn(get("return"));
    if (action === "sign-in") {
      const email = z.email().max(320).parse(get("email"));
      const password = z.string().min(1).max(1000).parse(get("password"));
      const { data, error } = await client.auth.signInWithPassword({
        email,
        password,
      });
      if (error || !data.user)
        return redirect(
          `/login/?error=SIGN_IN_DENIED&return=${encodeURIComponent(target)}`,
          303,
        );
      locals.auth.flush(true);
      return redirect(target, 303);
    }
    if (!locals.userId) return new Response(null, { status: 401 });
    if (action === "sign-out") {
      await client.auth.signOut({ scope: "local" });
      locals.auth.clear();
      return redirect("/login/", 303);
    }
    const { data: factors, error: factorError } =
      await client.auth.mfa.listFactors();
    if (factorError) throw new Error("MFA_UNAVAILABLE");
    const id = z.uuid().parse(get("factor_id"));
    const factor = factors.all.find(
      (f) => f.id === id && f.factor_type === "totp",
    );
    if (!factor) throw new Error("MFA_FACTOR_DENIED");
    if (action === "mfa-unenroll") {
      if (factor.status !== "unverified") throw new Error("MFA_FACTOR_DENIED");
      const { error } = await client.auth.mfa.unenroll({ factorId: id });
      if (error) throw new Error("MFA_UNAVAILABLE");
      return redirect(`/mfa/?return=${encodeURIComponent(target)}`, 303);
    }
    const code = z
      .string()
      .regex(/^\d{6}$/)
      .parse(get("code"));
    const { error } = await client.auth.mfa.challengeAndVerify({
      factorId: id,
      code,
    });
    if (error)
      return redirect(
        `/mfa/?error=MFA_INVALID_CODE&return=${encodeURIComponent(target)}`,
        303,
      );
    const { data: assurance, error: assuranceError } =
      await client.auth.mfa.getAuthenticatorAssuranceLevel();
    if (assuranceError || assurance.currentLevel !== "aal2")
      throw new Error("MFA_REQUIRED");
    locals.auth.flush(true);
    return redirect(target, 303);
  } catch {
    locals.auth.flush(false);
    return new Response("Request denied", { status: 403 });
  }
};
