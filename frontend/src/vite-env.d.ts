/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "1" — страница работает на снапшоте, без локального бэкенда. */
  readonly VITE_STATIC_DATA?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv & { readonly BASE_URL: string };
}
