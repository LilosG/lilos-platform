/// <reference types="astro/client" />

interface ImportMetaEnv {
  readonly PUBLIC_LILOS_API_BASE_URL?: string;
  readonly PUBLIC_LILOS_SUPABASE_URL?: string;
  readonly PUBLIC_LILOS_SUPABASE_ANON_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
