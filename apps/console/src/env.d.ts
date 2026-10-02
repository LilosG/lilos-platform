/// <reference types="astro/client" />
import type { ConsoleConfig } from "./server/config";
import type { requestSession } from "./server/session";
declare global {
  namespace App {
    interface Locals {
      settings: ConsoleConfig;
      auth: ReturnType<typeof requestSession>;
      userId: string | null;
      userEmail?: string | null;
      token: string | null;
      csrf: string;
      binding: string;
      correlationId: string;
    }
  }
}
export {};
