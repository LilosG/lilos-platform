import { createHmac, randomUUID, timingSafeEqual } from "node:crypto";
import type { ConsoleConfig } from "./config";
export const privateHeaders = {
  "Cache-Control": "private, no-store",
  Vary: "Cookie",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "same-origin",
};
export const correlation = (value: string | null) =>
  value && /^[A-Za-z0-9_-]{1,64}$/.test(value) ? value : randomUUID();
export function safeReturn(value: string | null): string {
  if (!value || value.length > 2000) return "/";
  try {
    const decoded = decodeURIComponent(value);
    if (
      !decoded.startsWith("/") ||
      decoded.startsWith("//") ||
      /[\\\x00-\x1f]/.test(decoded) ||
      decoded.startsWith("/auth/") ||
      decoded.startsWith("/login")
    )
      return "/";
    const url = new URL(value, "https://console.invalid");
    return url.origin === "https://console.invalid"
      ? url.pathname + url.search
      : "/";
  } catch {
    return "/";
  }
}
export function assertHost(request: Request, settings: ConsoleConfig): void {
  const url = new URL(request.url);
  if (
    url.origin !== settings.origin ||
    (request.headers.get("host") && request.headers.get("host") !== url.host)
  )
    throw new Error("HOST_DENIED");
}
const sign = (value: string, secret: string) =>
  createHmac("sha256", secret).update(value).digest("base64url");
export function csrfToken(
  binding: string,
  userId: string | null,
  secret: string,
  now = Date.now(),
): string {
  const expiry = Math.floor(now / 1000) + 3600;
  const nonce = randomUUID();
  return `${expiry}.${nonce}.${sign(`${binding}:${userId ?? "anonymous"}:${expiry}:${nonce}`, secret)}`;
}
export function assertMutation(
  request: Request,
  token: string,
  binding: string,
  userId: string | null,
  settings: ConsoleConfig,
  now = Date.now(),
): void {
  assertHost(request, settings);
  if (
    request.headers.get("origin") !== settings.origin ||
    request.headers.get("sec-fetch-site") === "cross-site"
  )
    throw new Error("ORIGIN_DENIED");
  const [expiry, nonce, signature, extra] = token.split(".");
  if (
    extra ||
    !nonce ||
    !signature ||
    !/^\d+$/.test(expiry) ||
    Number(expiry) < now / 1000 ||
    Number(expiry) > now / 1000 + 3601
  )
    throw new Error("CSRF_DENIED");
  const expected = sign(
    `${binding}:${userId ?? "anonymous"}:${expiry}:${nonce}`,
    settings.csrfSecret,
  );
  if (
    signature.length !== expected.length ||
    !timingSafeEqual(Buffer.from(signature), Buffer.from(expected))
  )
    throw new Error("CSRF_DENIED");
}
export async function boundedBody(
  request: Request,
  maximum: number,
): Promise<string> {
  if (Number(request.headers.get("content-length") ?? 0) > maximum)
    throw new Error("BODY_TOO_LARGE");
  const reader = request.body?.getReader();
  if (!reader) return "";
  const chunks: Uint8Array[] = [];
  let size = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > maximum) {
      await reader.cancel();
      throw new Error("BODY_TOO_LARGE");
    }
    chunks.push(value);
  }
  return Buffer.concat(chunks).toString("utf8");
}
export const cookieOptions = (local: boolean) => ({
  path: "/",
  secure: !local,
  httpOnly: true,
  sameSite: "lax" as const,
});
